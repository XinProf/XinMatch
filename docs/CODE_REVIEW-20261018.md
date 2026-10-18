# XinMatch 代码评审与改进方案（2026-10-18）

> 评审对象：`xinmatch/`（112 个源文件）+ `tests/`（127 个测试文件）+ 打包/配置
> 评审方式：通读核心链路（io → preprocess → db → search → quant/refine → report → ui/cli）、
> 运行静态检查、构建 wheel 验证打包产物、抽样复现边界行为
> 结论：**代码质量整体良好，无架构级返工需求**；问题集中在「资源生命周期」「大库检索性能」
> 「打包/工程化」三类，可按 3 个批次分批落地。

---

## 0. 评审基线（已实测）

| 检查项 | 命令 | 结果 |
|---|---|---|
| 类型检查 | `python -m mypy` | ✅ Success: no issues found in 112 source files |
| 静态检查 | `python -m ruff check xinmatch tools tests` | ⚠️ 仅 1 项（`tools/make_reg_code.py:2` 多余 coding 声明，`UP009`，可 `--fix`） |
| 打包产物 | `pip wheel . --no-deps` 后解包 | ❌ wheel 内**无任何非 .py 资源**（无 `schema.sql`、无 `ui/assets/3dmol/*`） |
| 默认测试 | `pytest tests/search tests/db` | ⚠️ 长时间无输出（与 `docs/pytest_full_run_hang_rootcause.md` 记载的固有慢测试一致，未跑完即终止） |
| 版本导入 | `python -c "import xinmatch; print(xinmatch.__version__)"` | ✅ 1.7.0（**依赖已安装的 dist 元数据**，见 P0-5） |

分层结构（`core` 纯算法 / `ui` 仅消费公共 API / `cli` 薄封装）在 112 个文件规模上保持得相当好，
`core` 内无 `print`、无文件读写的越界行为，模块 docstring 普遍完整。这是本项目最大的资产，
后续改动必须守住。

---

## 1. P0 — 必须先修（缺陷 / 会崩 / 会泄漏）

### P0-1 GUI 每次检索泄漏一个 SQLite 连接（已核实）

**现状**：`MainWindow._run_search_match()` 每次点击都 `conn = self.open_search_library()`，
连接交给工作线程用完即弃，**整个 `xinmatch/ui/` 目录内没有任何 `.close()` 调用**。

```895:919:xinmatch/ui/main_window.py
            conn = self.open_search_library()
...
        run_with_busy(
            self,
            "Search-Match",
            f"正在执行{mode_desc}…\n对参考数据库逐条比对/拟合，请稍候。",
            lambda: self._do_search(pattern, conn, mode),
            on_success=self._apply_search_results,
            on_error=self._show_search_error,
        )
```

**影响**：反复检索会累积文件句柄与页缓存；库文件被占用导致「重建库 / 替换库」失败
（Windows 上尤其明显）；长会话内存持续增长。

**建议**：把连接生命周期收进一次检索调用的 `try/finally`（在工作线程内关闭，或用上下文管理器），
并在 `closeEvent` 兜底关闭。同时把 `open_search_library()` 的失败回退改成**不弹框**、
只返回 `(conn, fallback_reason)`，因为该函数目前可能在工作线程路径上被间接调用（违例风险）。

**验收**：`grep -r "\.close()" xinmatch/ui` 有命中；连续 50 次检索后 `handle` 数不增长（任务管理器实测）。

---

### P0-2 `search_by_d` 的 2θ 窗口换算会抛 `ValueError`（已复现）

```186:194:xinmatch/core/db/query_peaks.py
        half_rad = math.radians(window_deg / 2.0)
        theta = math.asin(wavelength / (2.0 * d))
```

当 `d < λ/2` 时 `asin` 参数 >1 → `ValueError: math domain error`（已在本机复现）。
物理上 `d ≥ λ/2` 恒成立，但下面两条路径会真实触发：

1. ASCII/未知格式导入时 `Pattern.wavelength` 回落默认 Cu Kα（1.5406），而数据来自 Mo/Ag 靶，
   高角峰 d 可低至 0.35 Å → 检索直接崩；
2. `d` 恰为 `λ/2`（2θ=180°）时浮点回代可能得到 `1.0000000000000002`。

**建议**：`arg = wavelength / (2.0 * d)`，`if arg >= 1.0: skip`（该峰不可能被任何参考峰匹配）；
或 `theta = math.asin(min(1.0, arg))`。同时在 `_exp_d_values` 侧记录「跳过的高角峰数」到 `logger.debug`。

**验收**：新增 `tests/db/test_query_peaks.py` 边界用例（`d=0.35, λ=0.7107`、`d=λ/2`）。

---

### P0-3 `recall_max_candidates` 在 restraints 模式下失效（文档与实现不一致）

```309:346:xinmatch/core/search/search_match.py
    if pre_filter is not None:
        entry_ids: list[str] = list(pre_filter(exp_peaks, conn))
    elif restraints is not None:
        entry_ids = apply_restraints(conn, restraints)      # ← 无上限
    else:
        ...
        ranked_ids = search_by_d(..., max_candidates=recall_max_candidates, ...)
```

docstring 明确写「Applied in **all** recall modes」，但 restraints 分支没有上限：
用户一旦设了宽松限制（如「必须含 O」），`entry_ids` 可能是 7 万级，随后
`fetch_entries_by_ids` + `rank_candidates` 全量打分 → 界面卡数十秒（在忙碌窗口里看起来像死机）。

**建议**：restraints 分支也按 `recall_max_candidates` 截断（并按匹配度择优而非按 `entry_id` 字典序），
或在分数不变的前提下把上限作用于「restraints ∩ d 值召回」的交集。

**验收**：构造 7 万条合成库，restraints 模式检索 ≲ 2 s；新增回归测试。

---

### P0-4 wheel 安装后必崩：包内资源未声明

**证据**：`pip wheel .` 产物解包后只有 `.py` 与 `dist-info`，没有 `xinmatch/core/db/schema.sql`。

```16:19:xinmatch/core/db/schema.py
_SCHEMA_PATH = Path(__file__).with_name("schema.sql")
SCHEMA_SQL: str = _SCHEMA_PATH.read_text(encoding="utf-8")
```

**影响**：`pip install xinmatch` 后 `import` 阶段即 `FileNotFoundError`（只要触碰 `core.db`）；
3D 结构视图（`ui/structure_view.py` 的 `ASSETS_DIR`）同理失效。
PyInstaller 走 `xinmatch.spec` 的 `datas` 列表，所以「exe 能跑、pip 装不能跑」——同类问题会在
任何「用 pip 分发 / 内部 PyPI / 未来 Linux 包」的场景暴露。

**建议**：在 `pyproject.toml` 增加

```toml
[tool.setuptools.package-data]
"xinmatch.core.db" = ["*.sql"]
"xinmatch.ui.assets" = ["3dmol/*"]
```

并把 `schema.sql` 的读取包进 `importlib.resources.files()`（对 zip/egg 安装更稳）。

**验收**：`pip wheel` → 新建 venv `pip install` → `python -c "from xinmatch.core.db.schema import create_tables"` 通过；
新增一条打包冒烟脚本进 `tools/`。

---

### P0-5 `__version__` 依赖已安装元数据，未安装即导入失败

```50:50:xinmatch/__init__.py
__version__ = importlib.metadata.version("xinmatch")
```

源码目录直接运行（未 `pip install -e .`）、或冻结/裁剪环境丢失 dist-info 时抛
`PackageNotFoundError`，**整个包 import 失败**（`tests/test_smoke.py` 也依赖已安装环境，覆盖不到这条路径）。

**建议**：

```python
try:
    __version__ = importlib.metadata.version("xinmatch")
except importlib.metadata.PackageNotFoundError:  # 源码运行 / 冻结包
    __version__ = "1.7.0"      # 或读 xinmatch/_version.py
```

更彻底的做法是单一来源：由 `pyproject` 动态读取 `xinmatch/_version.py`，`spec` 与 `about_dialog` 共用。

---

## 2. P1 — 性能与架构（有明显收益，风险可控）

### P1-1 `fetch_entries_by_ids` 是 N+1 查询

```127:133:xinmatch/core/search/search_match.py
            peak_cur = conn.execute(
                "SELECT d, intensity, h, k, l FROM peaks "
                "WHERE entry_id = ? ORDER BY intensity DESC",
                (eid,),
            )
```

3000 个候选 = 3000 条 SQL（模块 docstring 自述 fetch ≈ 0.7 s，是检索耗时的大头）。
改为按 chunk 一次取回（`WHERE entry_id IN (...)` 复用已有的 500 分块逻辑）后在内存按 `entry_id`
分组，SQLite 往返从 N 降到 `ceil(N/500)`，预计 fetch 降到 0.1 s 量级（10k 峰表仍 < 100 MB）。

**顺带**：`hkl` 字段目前用 `cast` 把含 `None` 的列表塞进 `list[tuple[int,int,int]]`，
建议在 `Entry` 侧改为 `list[tuple[int,int,int] | None]`，去掉这处类型谎言。

### P1-2 Hanawalt top-K 预筛：进程级全局缓存，无失效、无上限、非线程安全

```20:65:xinmatch/core/db/query_peaks.py
_top_k_cache: dict[str, dict[str, list[float]]] = {}
...
    cur = conn.execute("SELECT entry_id, intensity FROM peers ... ORDER BY entry_id, intensity DESC")
```

- 首次调用要**全表流式扫描** peaks（COD 全库亿级行，几秒钟），且结果永远驻留内存；
- 按库**路径**做键：库被重建/替换后仍返回旧数据（静默错误结果）；
- GUI 工作线程 + 可能的并行 CLI 会并发读写该 dict。

**建议（按性价比排序）**：
1. 在**建库阶段**物化 `entries.top1..topK` 或单列 `max_intensity`（建库一次，检索永久受益）；
2. 暂时保留内存缓存时，加 `(db_path, st_mtime, size)` 作键 + `threading.Lock`，并设置条目上限（LRU）；
3. 或用一条带窗口函数的 SQL 直接算 `ROW_NUMBER() OVER (PARTITION BY entry_id ORDER BY intensity DESC)`。

### P1-3 检索结果组装代码重复 3 份

`raw → CandidateResult` 的映射分别存在于：
`ui/main_window.py:989`（`_search_fpfm`）、`core/batch.py:231`（`_search_fpfm`）、
以及 `core/search/fpfm.py:852` 的返回约定里。两份同名函数逻辑相同，改一处漏一处会直接导致
GUI 与批处理的 FoM/排序不一致。

**建议**：在 `core/search/fpfm.py` 增加 `to_candidates(raw) -> list[CandidateResult]`，
UI / batch / CLI 统一调用。

### P1-4 「载入→预处理→检索→报告」管线的三份实现

`xinmatch/__init__.py:227`（`full_analysis`）、`cli/main.py:263`（`cmd_run`）、
`core/batch.py:267`（`run_sample`）各自拼装同一流程。三者对 FPFM 模式、restraints、
top_n 的处理已经出现细微差异（batch 支持 `smpf` 旧别名，`full_analysis` 不支持）。

**建议**：抽出 `core/pipeline.py::run_pipeline(pattern | path, db, config) -> PipelineResult`，
三个入口变成参数适配层。这是本批次里唯一有「行为变更风险」的项，建议放在 P0 全部落地之后单独一批。

### P1-5 GUI 打开大文件仍是同步阻塞

```823:824:xinmatch/ui/main_window.py
        try:
            pattern = load_pattern(path)
```

Bruker `.raw` / `.brml` / 大 ASCII（几十万点）在 GUI 线程解析，虽有 `run_with_busy` 基础设施却没用。
brml 是 zip+XML，解析耗时可达数秒。改为 `run_with_busy` 包装即可，注意 busy 回调里再弹错误框。

### P1-6 `run_with_busy` 无取消能力 + `worker.wait()` 阻塞 GUI

```161:167:xinmatch/ui/busy.py
    worker.start()
    dlg.exec()
    worker.wait()
```

FPFM 全谱拟合一跑就是数十秒，用户没有任何中断手段（modal 遮罩连窗口都关不掉）。
`wait()` 在信号派发后通常立即返回，但异常路径下可能卡住。
**建议**：加 `QProgressDialog` 式「取消」按钮 + `_Worker.cancel()` 协作式取消标志
（在 `search_match_fpfm` 的候选循环里检查），`wait()` 改为 `wait(5000)` + 超时日志。

---

## 3. P2 — 工程化与可维护性

| 编号 | 问题 | 证据 | 建议 |
|---|---|---|---|
| P2-1 | **没有 CI** | 仓库无 `.github/workflows` / 任何 pipeline 文件（`docs/STATUS.md` T0.6 声称「CI (pytest, ruff, mypy)」已就绪） | 加 GitHub Actions：ubuntu + windows 矩阵；`ruff` + `mypy` + `pytest -m "not slow"`；缓存 pip |
| P2-2 | **默认 `pytest` 不可用** | `slow` marker 仅用于 `tests/quant/test_rietveld_quant.py`、`tests/search/test_fpfm.py`；而 `test_turn_on.py`（每例 5–10 min）、`test_gsas2_project.py`（子进程 1800 s）、`test_baseline_acceptance.py` 未标记 | 给上述文件加 `pytestmark = pytest.mark.slow`；`addopts` 增 `-m "not slow"`；CI 夜间跑全量 |
| P2-3 | **硬编码本机绝对路径** | `multi_db.py:77` `DEFAULT_POLYXRD_DIR = D:\Project\XRD\PolyXRD\cod_data` | 默认改 `None`，未配置时给「请设置 `XINMATCH_POLYXRD_DIR` 或 GUI 选择目录」的友好原因（现有 `unavailable_reason` 机制已具备） |
| P2-4 | **UI 菜单仍是占位** | `main_window.py:320-345`：背景扣除 / 平滑 / Kα2 剥离 / 重置 / 峰检测全部 `_placeholder` | core 已具备全部函数（`auto_process` 的 4 个步骤），接线成本低、用户感知收益最大 |
| P2-5 | **文档散落** | 根目录 8 个 md（`ROADMAP.md` / `ROADMAP_v2` / `ROADMAP_v3`、`FUNCTION_MAP.md` / `_v43`、`01_方案对比…`）+ `docs/` 35 个 | 建 `docs/README.md` 索引，历史版本移入 `docs/archive/`，根目录只留 `README.md` |
| P2-6 | **工作区塞满旧库备份** | `data/` 下 5 个 `.bak-*`，合计约 2.5 GB（`cod_full.db` 942 MB、`cod_full_curated.db` 798 MB 等） | 提供 `tools/clean_data_backups.ps1`；`.gitignore` 已忽略，不影响仓库 |
| P2-7 | **SQL 注入面（低危）** | `query_filter.py:180` `LIKE '%{name}%'` 未转义 `%`/`_`；SQL 本身是参数化的，仅通配符语义外泄 | `name.replace("%", r"\%").replace("_", r"\_")` + `ESCAPE '\'` |
| P2-8 | **异常被静默吞掉** | `gsas2_parse.py:356,365`、`gsas2_project.py:522,544,579` 的 `except Exception: pass` | 至少 `logger.debug(..., exc_info=True)`；`gsas2_parse` 的 gpx pickle 解析失败要留可诊断信息 |
| P2-9 | **SQLite URI 拼接未转义** | `multi_db.py:444` `"file:" + path.as_posix() + "?mode=ro"` | 路径含 `#` / `?` / 非 ASCII 时会被截断；改用 `path.as_uri() + "?mode=ro"` |
| P2-10 | **注册码是「混淆级」** | `registration.py:73` `_SECRET_KEY = b"PolyXRD::..."`（注释已承认可被逆向提取），`_STATE_VENDOR` 仍是 PolyXRD | 若商业防护重要：改 Ed25519 非对称签名（私钥只在 `tools/make_reg_code.py`），软件端只内置公钥；否则在发版说明里明确「防君子不防小人」 |
| P2-11 | **`main_window.py` 981 行** | 38 个方法，动作/菜单/对话框/检索/报告混在一起 | 拆 `ui/actions/search_actions.py` + `ui/controllers/search_controller.py`；与 P1-5 一起做，避免二次返工 |
| P2-12 | 类型/风格小项 | `Pattern.__getitem__(self, idx)` 无注解；`patterns_view` 里 `connect="all"` 等 pyqtgraph 旧参 | 顺手补；`mypy` 当前 `disallow_untyped_defs=false`，若要提升可先只对 `core/model` 打开 |
| P2-13 | 低效写法 | `pattern_view.py` 每次重绘重建曲线 | 视实测再定，非必要不动 |

---

## 4. 明确不建议做的事（避免范围蔓延）

1. **不重写 search / FPFM / 索引核心算法**：现有实现有大量带实测数据的注释（T6.0 召回策略、
   K=5 的 Hanawalt 证据），改动性价比低、回归风险高。
2. **不动 `tools/build_cod_xinmatch.py` 等已冻结的 COD 构建脚本**（项目规则明确保护）。
3. **不改 vendored 的 `xinmatch/utils/registration.py` 算法本身**，除非确认要动授权体系（P2-10 单列）。
4. **不做 `core` → `service` 的大规模分层重构**：P1-4 的 `pipeline.py` 已能覆盖 90% 重复，再多就是过度设计。

---

## 5. 执行计划（分 3 批，可独立验收）

### 批次 A —— 缺陷修复（预计 0.5–1 人日，风险极低）

| # | 内容 | 影响文件 | 验收 |
|---|---|---|---|
| A1 | GUI 连接生命周期（P0-1） | `ui/main_window.py` | 50 次检索句柄不增长 |
| A2 | `asin` 边界 + 高角峰跳过（P0-2） | `core/db/query_peaks.py` | 新增边界测试 |
| A3 | restraints 模式候选上限（P0-3） | `core/search/search_match.py` | 7 万库 ≲2 s |
| A4 | wheel 包数据 + `importlib.resources`（P0-4） | `pyproject.toml`、`core/db/schema.py` | 新 venv 安装后 import 通过 |
| A5 | 版本号回退（P0-5） | `xinmatch/__init__.py` | 无 dist 环境下 import 通过 |
| A6 | `ruff --fix tools/make_reg_code.py` | `tools/` | `ruff` 全绿 |

> 交付物：`pytest -m "not slow"` 全绿 + `mypy` 全绿 + `docs/ACCEPTANCE-<日期>.md`。

### 批次 B —— 性能与体验（预计 1.5–2 人日）

| # | 内容 | 预期收益 |
|---|---|---|
| B1 | `fetch_entries_by_ids` 批量化（P1-1） | 候选 fetch 时间 ↓ ~80% |
| B2 | top-K 强度缓存：键加指纹 + 锁 + LRU（P1-2 步骤 2） | 消除重建库后的静默错结果 |
| B3 | `fpfm.to_candidates()` 统一（P1-3） | 消除 GUI/batch 结果漂移 |
| B4 | 打开文件走 `run_with_busy`（P1-5） | 大文件导入不冻结 |
| B5 | busy 窗口加取消（P1-6） | FPFM 可中断 |
| B6 | UI 预处理菜单接线（P2-4） | 5 个占位菜单变为可用功能 |

> 交付物：性能对比表（检索/fetch/导入 三个数字，前后各一次实测）+ 回归测试。

### 批次 C —— 工程化（预计 1–2 人日，可按需裁剪）

| # | 内容 |
|---|---|
| C1 | CI 工作流（ruff + mypy + `pytest -m "not slow"`，双平台） |
| C2 | `slow` marker 统一 + `addopts` 默认排除 |
| C3 | 去硬编码路径（P2-3）+ URI 转义（P2-9）+ LIKE 转义（P2-7）+ 日志补全（P2-8） |
| C4 | `core/pipeline.py` 统一三入口（P1-4） |
| C5 | 文档目录治理（P2-5）+ 数据备份清理脚本（P2-6） |
| C6 | （可选）`main_window.py` 拆分（P2-11） |

> 交付物：CI 首次全绿截图/日志、`docs/README.md` 索引、pipeline 迁移前后的回归对比。

---

## 6. 待你确认的事项

1. **范围**：三批全做 / 只做 A+B（推荐先 A，A 做完再评估 B/C）？
2. **CI 平台**：GitHub Actions（需要仓库托管在 GitHub）/ Gitee Go / 本地 `tools/ci.ps1` 脚本？
3. **是否接受行为变更**：批次 C 的 `core/pipeline.py` 统一会改变 `full_analysis` 的少量参数语义
   （例如是否支持 `mode=fpfm`），是否可以接受？
4. **注册机制**（P2-10）：只做文档说明，还是要升级为 Ed25519 非对称校验（会更换注册码格式，已发出的码失效）？
5. **数据目录**：`data/*.bak-*`（约 2.5 GB）是否可以直接归档/删除？

确认后我按批次执行，每批结束给出「改动清单 + 测试结果 + 回滚方式」。

---

## 7. 实施记录（2026-10-18）

> 按 §5 执行，全部改动在**工作区，未提交**。共修改 25 个既有文件、新增 8 个文件；
> §4 的四个「不做」项一条未碰。

### 7.1 批次 A —— P0 缺陷（全部完成）

| # | 改动 | 文件 | 验证 |
|---|---|---|---|
| A1 | 检索连接「谁打开谁关闭」：`_do_search` 在 `finally` 里 `close()`；`run_with_busy` 改为返回 `bool`，被重入保护拒绝时由调用方补关（否则泄漏） | `ui/main_window.py`、`ui/busy.py` | 同一窗口连续两次检索通过（此前第二次会拿到已关闭连接）；`grep -r "\.close()" xinmatch/ui` 有命中 |
| A2 | 2θ↔d 换算加物理边界：`d ≤ λ/2` 的峰（背散射极限）直接跳过并 `logger.debug`；窗口下限按 `2·asin(λ/2d)` 的极限钳制，上限用哨兵避免 `asin` 越界 | `core/db/query_peaks.py` | 新增 2 项边界测试（`d=0.35 Å` 不抛异常、`d=λ/2` 不抛异常） |
| A3 | `recall_max_candidates` 覆盖所有召回模式：restraints 结果超限时与 d 值召回求交再截断；窄限制保持原有精确性 | `core/search/search_match.py` | 新增 2 项测试（5000 条宽限制只 fetch ≤100；窄限制结果不变） |
| A4 | wheel 声明包数据（`schema.sql` + `3dmol/*`），`schema.sql` 改用 `importlib.resources` 读取 | `pyproject.toml`、`core/db/schema.py` | 重建 wheel：124 个条目，含 `xinmatch/core/db/schema.sql` 与 3 份 3dmol 资源；CI 增加打包断言作业 |
| A5 | `__version__` 在无 dist-info 时回退到常量 | `xinmatch/__init__.py` | 源码树/未安装环境可导入 |
| A6 | 删除多余 coding 声明 | `tools/make_reg_code.py` | `ruff` 全绿 |

### 7.2 批次 B —— 性能与体验（全部完成）

| # | 改动 | 文件 | 说明 |
|---|---|---|---|
| B1 | `fetch_entries_by_ids` 两趟取数：entries 一次、peaks 按 500 分块一次 + 内存按 `entry_id` 分组 | `core/search/search_match.py` | SQL 往返由 N 次降为 ⌈N/500⌉ 次；3000 候选从 ~3000 条查询变 1+6 条 |
| B2 | Hanawalt top-K 缓存键改为 `(真实路径, mtime_ns, size)`，加 `threading.Lock` + LRU(2) | `core/db/query_peaks.py` | 重建/替换库后不再命中旧排名（此前的静默错误结果） |
| B3 | 新增 `fpfm.to_candidates()`，GUI / 批处理 / CLI 三处共用 | `core/search/fpfm.py`、`ui/main_window.py`、`core/batch.py`、`cli/main.py` | 消除「改一处漏一处」导致的 FoM 漂移 |
| B4 | 打开数据文件走 `run_with_busy`（解析在工作线程，`_apply_loaded_pattern` / `_show_open_error` 回 GUI 线程） | `ui/main_window.py` | 大 `.raw`/`.brml` 不再冻结界面 |
| B5 | 协作式取消：新增 `core/cancel.py`（thread-local 谓词 + `check_cancelled()`），忙碌窗口加「取消」按钮（延迟 1.2 s 启用，避免误触），FPFM 候选循环轮询 | `core/cancel.py`(新)、`ui/busy.py`、`core/search/fpfm.py` | 取消只置标志、不强杀线程；异常类 `OperationCancelledError` |
| B6 | 5 个占位工具栏动作接线到 `core.preprocess`（背景扣除 / 平滑 / Kα2 剥离 / 重置原始数据 / 峰检测） | `ui/main_window.py` | 处理后可「重置原始数据」，峰表/谱图同步刷新 |

### 7.3 批次 C —— 工程化（C1/C2/C3/C5 完成；C4/C6 推迟，见 7.6）

| # | 改动 | 文件 |
|---|---|---|
| C1 | GitHub Actions：ubuntu+windows × py3.10/3.12，ruff + mypy + 默认测试（Linux 补装 Qt 运行库）；独立 `packaging` 作业断言 wheel 内含 `schema.sql` 与 3dmol 资源；`workflow_dispatch` 可跑 slow 套件 | `.github/workflows/ci.yml`(新) |
| C2 | `slow` 标记补齐：`test_turn_on.py` 模块级、`test_gsas2_project.py` 两个真实精修、`test_baseline_acceptance.py`、`test_fpfm.py` 的 4 个真实库/13 组合成谱验收；`addopts` 增 `-m "not slow"` | `pyproject.toml`、5 个测试文件 |
| C3 | 去硬编码：`DEFAULT_POLYXRD_DIR = None`（未配置时给「设置 `XINMATCH_POLYXRD_DIR` 或 GUI 选择目录」的原因）；SQLite URI 改 `Path.as_uri()`（`#`/`?`/非 ASCII 不再截断）；LIKE 通配符转义 + `ESCAPE '\'`；`gsas2_parse` 的静默 `except` 补 `logger.debug`，`GSAS2_HOME` 也可覆盖源码路径 | `core/db/multi_db.py`、`core/db/pdf2_index.py`、`core/db/query_filter.py`、`core/refine/gsas2_parse.py` |
| C5 | 新建 `docs/README.md` 索引（按「入口/规范/算法/评审/验收」分类）；`tools/clean_data_backups.ps1`（默认 dry-run，`-Archive`/`-Delete` 才动文件）；`docs/PACKAGING.md` 更正 `schema.sql` 读取方式并新增「注册机制的安全边界」 | `docs/README.md`(新)、`tools/clean_data_backups.ps1`(新)、`docs/PACKAGING.md`、`README.md`、`docs/pytest_full_run_hang_rootcause.md` |

本地等价入口：`powershell -File tools/ci.ps1 [-Slow] [-SkipTests]`。

### 7.4 过程中额外发现并修复的三个问题

1. **`PatternView.clear()` 一直被 pyqtgraph 实例属性遮蔽**（真实 bug）：
   `self.clear = self.plotItem.clear` 写进实例 `__dict__`，直接盖掉子类方法，
   `'clear' in view.__dict__` 为真。后果是清空谱图后 `_records` 仍留旧记录，
   `patterns()` 继续返回已删除的曲线。修复：`__init__` 里 `self.__dict__.pop("clear", None)`。
2. **UI 测试挂起**（由 A1 引出）：测试的假 `open_search_library` 只建一个连接复用于两次检索，
   连接被关闭后第二次检索抛错 → 模态错误框在 offscreen 下永久等待。已改为每次新建连接，
   并把 `QMessageBox.warning` 打桩成记录器（失败即断言，不再卡住）。
3. **CLI 测试在中文 Windows 上 `UnicodeDecodeError: 'gbk'`**：`subprocess.run(text=True)`
   用 locale 编码解码 UTF-8 输出。已显式 `encoding="utf-8", errors="replace"`。

### 7.5 验证结果

| 检查 | 命令 | 结果 |
|---|---|---|
| 静态检查 | `python -m ruff check xinmatch tools tests` | **All checks passed** |
| 类型检查 | `python -m mypy` | **Success: no issues found in 113 source files** |
| 打包 | `pip wheel .` → 解包 | 124 条目，含 `schema.sql` + 3 份 3dmol 资源 |
| db + utils | `pytest tests/db tests/utils` | 96 项：94 passed / 2 skipped |
| model/peak/preprocess/io/micro/report | `pytest` | 269 项：268 passed / 1 skipped |
| cli | `pytest tests/cli` | 31 passed |
| refine + quant | `pytest tests/refine tests/quant` | 186 项：184 passed / 1 skipped / 1 xfailed |
| search | `pytest tests/search`（默认排除 slow） | 278 项：276 passed / 2 skipped / 0 failed |
| ui | `pytest tests/ui` | 226 项：0 failed（含 5 个 heavy FPFM 用例；汇总行在 Qt 退出时未落盘，另按文件复跑确认） |

> 说明：`tests/ui`、`tests/search` 的 `-q` 汇总行在本机重定向到文件时偶尔丢失（进程正常退出、
> 进度条无 `F`），因此对上表的两项做了**按文件复跑**确认。CI 里用的是普通终端输出，不受影响。

### 7.6 未做 / 推迟（建议单开一批）

| 项 | 原因 |
|---|---|
| C4 `core/pipeline.py` 统一三入口 | UI 与 CLI 的预处理语义**本就不同**（UI 直接对原始谱寻峰，CLI 先 `auto_process`）；UI 测试以 `xinmatch.ui.main_window.search_match` / `search_match_fpfm` 为打桩点，强行统一会牵连 `test_open_pattern` / `test_search_mode` / `test_fpfm_kalpha2`，且需要真实库回归。已用 `to_candidates` 消掉最易漂移的重复（3 份 → 1 份），剩余 dispatch 重复约 15 行，建议单独排期并配真实库基线。 |
| C6 `main_window.py` 拆分 | 本轮新增功能使该文件从 981 行增至 1112 行；拆分需独立 UI 回归窗口，与下一次 UI 迭代合并更划算。 |
| P2-10 注册升级 | 采用保守方案：只补文档（`docs/PACKAGING.md`「注册机制的安全边界」），不改码格式，避免已发出的注册码作废。 |
| P2-6 数据清理 | 只提供脚本，未删除任何 `data/*.bak-*`（等你确认后再执行 `-Archive`/`-Delete`）。 |

### 7.7 回滚方式

* 单项：`git checkout -- <file>`；新增文件直接删除
  （`.github/workflows/ci.yml`、`tools/ci.ps1`、`tools/clean_data_backups.ps1`、
  `xinmatch/core/cancel.py`、`docs/README.md`、3 个测试文件、本文件）。
* 整批：`git checkout -- .` + `git clean -fd`（未提交改动全在工作区）。
* 注意：A1 与 B4/B6 都改 `ui/main_window.py`，回滚需整文件回退；
  A2/A3 改动含新增的逻辑分支，回滚整文件即可，无数据迁移。
