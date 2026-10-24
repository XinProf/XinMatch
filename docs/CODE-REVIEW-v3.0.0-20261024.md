# XinMatch v3.0.0 全面评估报告（2026-10-24）

> **基线**：`master` @ `beda021`，版本号 **3.0.0**（`pyproject.toml` / `xinmatch.__version__` /
> `xinmatch.spec` / 安装脚本一致）。评估含 **代码审查 + 真实缺陷修复 + 检索性能优化 +
> 三个无机物 `.xinDB` 库独立验收 + 文档一致性**。
>
> **方法**：4 个互不重叠的并行审查任务（核心内核 / CLI·GUI·打包 / 检索性能 / 三库验收）+ Lead 交叉复核；
> 所有结论以**本轮实测**为准，历史文档数字只作对照（发现 6 处对不上，见 §1.4）。
> 每个修复都有「复现 → 修复 → 回归测试」，每个性能数字都有「旧实现 oracle 逐位 parity」。
>
> 配套文档：[三库验收](ACCEPTANCE-3COD-20261024.md) · [v3.0.0 发布验收](ACCEPTANCE-v3.0.0-20261023.md) ·
> [v3.0.0-验收报告](v3.0.0-验收报告.md) · [状态记录](STATUS.md)

---

## 0. 结论速览

**一句话**：v3.0.0 的「单一 `.xinDB` 格式 + 内置默认库」方向正确、三个库结构自洽、检索能力可用；
但**发布记录失真（测试数、质量门、打包遗漏）**，且峰引擎有两类会产生「假峰相」的边界缺陷
（已发布库中 COD 8 相、PCOD 7 相）。本轮已修复引擎与工具链缺陷、把检索提速 3.2×、恢复
ruff/mypy 全绿，并给出重建与发布建议。

| 维度 | 判定 | 关键证据 |
|---|---|---|
| **三库可用性** | COD **WARN（可发布）**、PCOD **PASS**、TCOD **PASS** | `validate_xindb` 0 FAIL；独立全量复核（118 万条 id / 全部 chunk）0 违规；自召回 COD 38/40、PCOD 40/40、TCOD 40/40（§5） |
| **代码缺陷** | 17 个真实缺陷（**P1×5** / P2×8 / P3×4）已全部修复并回归 | 峰引擎假峰 15 相、`batch --json` 污染、路径 `#` 幽灵文件、坏环境变量遮蔽内置库等（§3） |
| **静态质量** | 修复前 **ruff 218 / mypy 6** → 修复后 **0 / 0** | v3.0.0 发布时未跑质量门，CI 实际是红的（§6.3） |
| **检索性能** | PCOD 端到端 **5222 → 1624 ms（3.22×）**，prescreen **3568 → 881 ms（4.05×）**；候选与排序**逐位不变** | 旧实现 oracle parity：COD 20 / TCOD 20 / PCOD 66 组 + 端到端检索，0 fail（§4） |
| **测试基线** | 复验前 **1347 passed / 6 skipped / 51 deselected / 1 xfailed**（16m47s）；修复+新增测试后 **1411 passed / 4 skipped / 53 deselected / 1 xfailed**（13m01s），**0 failed** | 两次都含 UI、`QT_QPA_PLATFORM=offscreen`；历史声明「1570 passed」按本次实测更正（§6） |
| **发布产物** | `SHA256SUMS.txt` 与三个附件**全部一致**；分发包内 `.xinDB` 与验收库逐字节相同；冻结版开箱检索 78,036 相 | §1.2 |
| **文档一致性** | 8 处不一致：已修 5 处、登记 3 处 | §7 |

---

## 1. 基线与交付物一致性

### 1.1 环境

| 项 | 值 |
|---|---|
| Python / numpy / scipy / gemmi | 3.10.11 / 2.2.6 / 1.15.3 / 0.7.5 |
| PySide6 / pyqtgraph / PyInstaller | 6.11.2 / 0.13.7 / 6.22.3 |
| ruff / mypy / pytest | 0.16.10 / 2.4.0 / 9.1.1 |
| 真实库（只读） | `XinMatch-DataBase/data/{COD,PCOD,TCOD}-Inorg-20261020.xinDB` |

> 与建库时环境（Python 3.13 / numpy 2.5）不同：`docs/v3.0.0-验收报告.md` §8.3/§8.4 的**绝对耗时**
> 不可直接横比；本报告的加速比是**同机同条件**测的，可跨机比较。

### 1.2 发布产物核对（v3.0.0 三个附件）

| 附件 | 实测体积 | SHA-256 前 16 | 与 `SHA256SUMS.txt` |
|---|---|---|---|
| `XinMatch-Setup-3.0.0.exe` | 256,400,880 B（244.5 MiB） | `de567ddbbb8cafed…` | ✅ |
| `XinMatch-Internal-3.0.0.zip` | 356,466,971 B（340.0 MiB） | `b252249956477d16…` | ✅ |
| `XinMatch-Databases-COD-Inorg-3.0.0.zip` | 91,175,782 B（86.9 MiB） | `9c1f6f982033634f…` | ✅ |

- 库分发包内只有 `COD-Inorg-20261020.xinDB`（118,710,272 B），其 SHA-256
  `328c6acb96f504df…` 与 §5 验收的库文件**逐字节相同** —— 分发的就是验收过的那份。
- 便携包内有 `data/COD-Inorg-20261020.xinDB` 与 `_internal/variant.txt`（内容 `internal`）。
- 冻结版 `dist/xinmatch-3.0.0/XinMatch.exe libraries --json`（清空 `XINMATCH_XINDB_DIR`）→
  `xindb_cod_inorg` `available=true / entries=78036`、路径 `<exe>/data/COD-Inorg-20261020.xinDB`，exit 0。

### 1.3 版本号一致性

`pyproject.toml` `3.0.0` = `xinmatch/__init__.py` fallback `3.0.0` = `xinmatch.spec` `APP_VERSION`
/ `VERSION_TUPLE (3,0,0,0)` = `tools/xinmatch_setup.iss` `AppVersion 3.0.0`；About 对话框动态读取
`xinmatch.__version__`（实测显示「版本 3.0.0」）。**一致**。

### 1.4 历史文档数字对账（以本轮实测为准）

| # | 文档声明 | 实测 | 处理 |
|---|---|---|---|
| 1 | v3.0.0 全量回归 **1570 passed / 4 skipped / 1 xfail**（RELEASE-NOTES / ACCEPTANCE-v3.0.0） | **1347 passed / 6 skipped / 51 deselected / 1 xfailed**（默认 `-m "not slow"`，含 `tests/ui`，16m47s）。同一文档 §5 又自述 `tests/ui` **未跑** | 已在 `STATUS.md` 与本报告更正；建议 Release notes 加勘误 |
| 2 | `mypy 114 files 0 errors`、`ruff All checks passed`（v2.0.0 记录） | v3.0.0 实际 **mypy 6 errors / ruff 218 errors**（`ruff check .`；`ruff check xinmatch tools tests` 218 含 tools 探针） | 本轮已修到 **0/0**（§6.3） |
| 3 | `STATUS.md` 最新只到 v2.0.0 | v3.0.0 已发布但未登记 | 本轮补 v3.0.0 与复验两节 |
| 4 | v3.0.0-验收报告 §7.5：库统一放 `PolyXRD-DataBase/xindb/`，`~/.xinmatch/libraries` | 实际库在 `XinMatch-DataBase/data/`，注册表是 `~/.xinmatch/libraries.json` | 新验收文档按实际路径写；旧报告属历史记录，不改写 |
| 5 | v3.0.0-验收报告 §8.6 只登记 3 条 `d=1.0` 假峰 | 还有 **5 条 COD + 7 条 PCOD** 的 `d=0.7703` 假峰（另一类根因，本轮新发现） | 已登记进 `ACCEPTANCE-3COD-20261024.md` §8.1，引擎已修 |
| 6 | README §3.4 PCOD「150.0（全为上限截断）」 | 实测均值 **149.9824**，**581 相 <150**（6 个 `n_peaks=1`） | 建议改文案（不阻塞） |
| 7 | README §5「本机 data/ 有 `_backup/` 两个历史副本」 | `XinMatch-DataBase/data/` 只有 3 个 `.xinDB`，无 `_backup/` | 建议删/改该句 |
| 8 | README §4/§6 `96-210-4629`「a=b=c=1、体积=1」 | 库内该行晶胞字段为 **NULL** | 建议改为「NULL（源 CIF 占位值被丢弃，应剔除）」 |

> 教训：发布验收应把**命令 + 原始输出**固化进仓库（本轮报告即按此办理：命令、JSON、SHA-256 全可复跑）。

---

## 2. 代码结构与质量评估

### 2.1 规模

| 范围 | 文件 | 行数（含注释/空行） | 代码行（非空非注释） |
|---|---:|---:|---:|
| `xinmatch/` 包 | 116 | 33,449 | 26,806 |
| ├ `core/db`（v3 读写栈） | 16 | 6,287 | 4,960 |
| ├ `core/search` | 11 | 4,244 | 3,438 |
| ├ `core/refine` | 11 | 3,819 | 2,985 |
| ├ `core/io` | 13 | 2,818 | 2,196 |
| ├ `ui` | 20 | 6,098 | 4,989 |
| └ 其余 core + cli + utils | 45 | 10,183 | 8,238 |
| `tests/` | 110 | 20,608 | 15,217 |
| `tools/`（建库/验收/探针） | 39 | 12,670 | 10,401 |

测试/源码 ≈ 0.57（按代码行），对科学计算项目属健康；但**覆盖率未入 CI**，实际覆盖未知。

### 2.2 架构优点（值得保留）

1. **内核 / GUI 解耦彻底**：`core/**` 纯 numpy + dataclass，`tests/ui` 之外全部无 Qt 依赖，
   可在无显示环境跑（本轮 1347 项里绝大多数如此）。
2. **v3 读写栈设计干净**：`schema_v3`（DDL/meta 契约）→ `writer_v3`（分块列存 + 断点续跑）→
   `reader_v3`（只读 + 预筛）→ `search_v3`（数据访问），**评分/排序复用未改动的 v2 scorer**，
   「候选生成换了、打分没换」是正确取舍，也是本轮 parity 能成立的原因。
3. **一个检索路径 + 明确拒绝旧格式**：v2 行表/PolyXRD/PDF-2 运行期读取层删除，`open_search_database`
   对 `.db/.sqlite` 明确报错而不是静默降级；`multi_db` 的库目录解析链（env → 内置 → sibling）考虑到了
   源码态/冻结态差异。
4. **可验证性**：`validate_xindb` 只读、只用公开 schema；`_compare_xindb_peaks` / parity 测试能证明
   「只动元数据不动物理」「优化不改排序」；本轮沿用了这套方法论。
5. **性能结构清晰**：预筛矩阵（32 强峰）只剪枝、全反射重算排序，避免了「截断改变名次」的经典错误。

### 2.3 技术债与风险（建议排期）

| 项 | 现状 | 风险 | 建议 |
|---|---|---|---|
| v2 行表代码残留 | `core/db/{build_cod,index_build,manager,query_filter,query_peaks,user_db,schema}.py` ≈ 50 KB 仍在；`search_match` 保留 `sqlite3.Connection` 分支 | 用户把 `.xinDB` 用 `sqlite3.connect` 传进去会得到 `no such table: peaks`；两套路径长期维护成本 | v3.1 删除或至少对 `sqlite3.Connection` 给出「请用 `XinDBReader`」的明确错误 |
| 测试可移植性 | 8 个测试文件引用**已删除的 v2 库** `data/cod_inorganics.db`（745 MB，不在 git）；约 20 处硬编码 `D:\Project\XRD\...` 外部数据 | CI（干净 checkout）大量 `skip`，本机跑又快又依赖私有数据；默认套件 17 分钟大半耗在这些真实库用例 | 迁移到 `tests/fixtures` 的小 `.xinDB` + 环境变量；真实库用例统一 `@pytest.mark.slow` / `integration` |
| 默认套件时长 | 本机 16m47s；`tests/search/test_synthetic_acceptance.py`、`tests/ui/test_search_mode.py` 的 FPFM 真实库用例**未标 slow** | 与「默认快套件」定位不符；CI 上因缺数据反而快，掩盖问题 | 标注/迁移（同上） |
| GUI 占位模块 | 15 个功能模块动作中 `restraints / user_db / indexing / rietveld / quant_analysis / microstructure / data_export` 仍是 `_placeholder()`（只弹状态栏提示）；核心能力（指标化、定量、Rietveld 向导）只在别处/部分接线 | README 的「完整 GUI」表述偏乐观；用户点菜单无响应 | 逐模块接线或从菜单隐藏；README 用「已接线模块」清单 |
| 超大单文件 | `writer_v3.py` 1246 行、`main_window.py` 1225 行、`fpfm.py` 1032 行、`cli/main.py` 869 行 | 可维护性；`main_window` 拆分自 v2.0.0 起推迟 | `main_window` 按面板/动作拆；`writer_v3` 拆「写出/续跑/校验」 |
| 无覆盖率门槛 | CI 只跑 ruff+mypy+pytest，无 `--cov` 阈值 | 新代码（尤其 `ui`、`tools`）回归靠自觉 | 加 `--cov=xinmatch --cov-report=xml`，先设 70% 软门槛 |
| 文档重复/过期 | 根目录 8 个 ROADMAP/功能映射历史稿；`docs/` 40+ 文件；v3 报告 §7.5 路径已过期 | 新读者容易拿旧文档当现状 | 保留 `docs/README.md` 索引并标注「当前/历史」；过期文档加 `> 历史` 头 |

---

## 3. 本轮发现并修复的缺陷

> 全部改动在工作树（未 push），每个修复都有复现脚本与 pytest 回归；详细证据见各任务报告
> （`.scratch/review-v3/{core-audit,ui-cli-audit,perf,db-acceptance}.md`，不随仓库提交）。

### 3.1 P1 —— 会产出错误结果 / 发布产物不可用

| ID | 位置 | 现象 | 根因 | 修复与验证 |
|---|---|---|---|---|
| **P1-1** | `core/db/peak_compute.py`（`measurable`、`_lorentz_polarization`） | **COD 5 相 + PCOD 7 相**的峰表只剩 1 条 `d=0.77029997 Å, I=1000` 的假峰，真实粉图丢失（`96-254-30089` 真峰被压到 I=0.013） | ① `2d > λ` 在 d 恰为 λ/2 时被浮点舍入判为真，2θ=180° 反射进入峰表；② LP 因子 `1/cosθ` 在 180° 发散（raw I 1e16–1e21）；③ norm-1000 后真峰相对强度 < `REL_INTENSITY_CUTOFF=1e-5` 全被滤掉 | `2d > λ·(1+1e-9)`；LP 三角因子取 floor（正常角度 `np.maximum` 返回原值，逐位不变）。12 相全部恢复真峰（122/228/152/413/79/2287/…/753 条）；120 个随机正常 CIF `(d,I)` **逐位一致 0 mismatch**；`tests/db/test_peak_compute_edges.py` 16 项 |
| **P1-2** | `core/db/peak_compute.py`、`cif_meta.py` | COD 3 相只有 1 条 `d=1.0 Å` 假峰：`96-156-3735/3736` 本应 150/114 峰，`96-210-4629` 源数据无晶胞本应剔除 | gemmi 读不到晶胞时**静默保留默认占位胞 (1,1,1,90,90,90)**；其中两相 `_cell_length_a` 写在文件尾部单列 `loop_`，文本其实可恢复 | 新增 `_cell_is_usable()`（按精确参数元组检测占位胞，不用 gemmi `is_crystal()`）+ `_recover_cell()` 文本六参数重建；失败则返回 `None`（判不可计算）。3735→150 峰、3736→114 峰、2104629→None；合成用例覆盖 |
| **P1-3** | `core/db/multi_db.py` | 过期 `XINMATCH_XINDB_DIR`（目录已删）时，冻结版把**内置默认库判为 unavailable**（`libraries --json` 里 `available=false`），用户只看到「未找到库」 | `xindb_default_dir()` 无条件返回 env 覆盖目录，不检查其中有无 `.xinDB` | env 目录无 `.xinDB` 时 `logger.warning`（按值去重）并回退 `data/` → sibling；有库时仍 env 优先。本机实测修复后 `resolve_default()` = `available=True entry_count=78036`；新增 5 条回归 |
| **P1-4** | `core/db/reader_v3.py` | 库路径含 `#` 时 `file:{path}?mode=ro` 被当 URI fragment → **打开错误路径并创建 0 字节幽灵文件** | 手动拼接 SQLite URI，未转义 | 改 `path.resolve().as_uri() + "?mode=ro"`；`hash#tag.xinDB` 回归通过、无幽灵文件 |
| **P1-5** | `cli/main.py`（`cmd_batch`） | `batch --json` 的 stdout 混入 `core.batch` 的进度行 → **`json.loads` 直接失败**（机器不可用） | 核心层用 `print` 往 stdout 报进度 | `--json` 时 `redirect_stdout(sys.stderr)`；实测 stdout 1144 B 纯 JSON、进度在 stderr；新增 2 条 CLI 回归 |

### 3.2 P2 —— 特定路径崩溃 / 静默错误

| ID | 位置 | 现象 | 修复 |
|---|---|---|---|
| **P2-1** | `core/db/search_v3.py` | 实验峰含 `2θ<=0` 时「前 N 个 d」与「前 N 个强度」错位 → 强度挂到别的测量窗，候选排序/截断可能静默挤掉真相 | 改为单遍 `(d, intensity)` 配对；`tests/db/test_search_v3.py` 5 项（旧实现会失败） |
| **P2-2** | `core/batch.py` | `samples: ["a.xy"]`（非 mapping）时整批抛 `AttributeError` 直接崩 | `_validate_config` 逐项校验并给可读 `ValueError`；新增回归 |
| **P2-3** | `core/db/reader_v3.py` | `probe()` 对非整数 `schema_version` 抛 `ValueError`（`list_libraries()` / GUI 崩） | try/except → `(False, "schema_version:<raw>")`；回归覆盖 |
| **P2-4** | `core/db/reader_v3.py` | `element_index()` 对长度非 4 倍数的 `element_inv` BLOB 抛 `ValueError` | 截断到整 uint32 前缀（与 `_decode_flat` 容忍语义一致） |
| **P2-5** | `ui/dialogs/config.py` | GUI 配置 YAML **非原子写**（中断即半截文件）+ `load_config` 不处理损坏文件 → 之后所有读配置功能抛异常 | `*.tmp` + `fsync` + `os.replace` 原子替换；损坏/非 mapping/目录路径 → 记 warning 并返回默认值（不改用户文件）；新增 5 项 UI 测试 |
| **P2-6** | `cli/main.py`（`cmd_report`） | `report --input-report X` 省略 `-o` 时 `Path(None)` 崩溃；且把 `search --json` 的摘要静默渲染成**空报告** | 校验输入形态并给出明确错误；默认输出名跟随格式；自动建父目录；新增 5 项回归 |
| **P2-7** | `ui/main_window.py` | 参考库在探测后被删/损坏时抛 `LibraryNotAvailableError` 之外的异常 → 逃逸进 Qt 槽，用户只见 traceback | 动作边界 `except Exception` → 记录日志 + 可读错误框；新增 1 项 UI 回归 |
| **P2-8** | `xinmatch.spec` / `pyproject.toml` | 冻结包与 wheel **漏收 `core/db/data/atomic_scattering_params.json`**：开发机正常，冻结包一旦 CIF→峰计算即 `FileNotFoundError` | spec 增加该 datas；`pyproject.toml` 的 `package-data` 补 `data/*.json` |

### 3.3 P3 —— 一致性与健壮性

| ID | 位置 | 修复 |
|---|---|---|
| **P3-1** | `reader_v3._get_conn` | 无锁，GUI/后台线程首次并发可能各建一条连接并泄漏一条 → `_conn_lock` 双检 |
| **P3-2** | `cli/main.py` `libraries` | 文本模式表格后又重复打印通用摘要 | 子命令自报 `_output_printed`，跳过重复输出 |
| **P3-3** | `cli/main.py` `libraries` | `--add` / `--remove` 声称互斥却未互斥（同时给出静默只执行 add） | `add_mutually_exclusive_group()` |
| **P3-4** | `cli/main.py` | `--db` 帮助仍写 `.db`、顶层描述漏列子命令、缺文件只回显路径 | 文案补全 + `FileNotFoundError` 中文前缀 |

### 3.4 静态质量门（v3.0.0 发布时实际是红的）

| 命令 | 复验前 | 复验后 |
|---|---|---|
| `python -m ruff check xinmatch tools tests` | **218 errors**（`tools/_probe_peak_convention.py` 172、`tools/validate_peak_engine.py` 23、其余 23） | **0 error** |
| `python -m mypy` | **6 errors / 4 files**（`cif_meta.py:197,496`、`peak_compute.py:383`、`batch.py:313`、`reader_v3.py:271,285`） | **0 error（119 files）** |
| `pytest`（默认 `-m "not slow"`，含 UI） | — | 见 §6 |

> `_probe_peak_convention.py` 是归档的一次性探针（峰口径冻结证据），按项目既有惯例在
> `pyproject.toml` 的 `per-file-ignores` 中显式豁免并注明理由；其余 `tools/` 全部修到 0。

---

## 4. 检索性能优化（逐位等价前提下的 3.2×）

对象 `core/db/reader_v3.py`（+314/−104）。**硬约束**：`prescreen` 的 `candidate_ids`（顺序）、
`truncated`、`n_hits`，`fetch_peaks` 的键顺序与全部 float64 值，以及端到端 `search_match_v3`
的候选 id 顺序与 FoM，必须与旧实现**逐位一致**。

| 阶段（PCOD，106 万相，1.69 GiB） | 改前 | 改后 | 加速 |
|---|---:|---:|---:|
| 冷启动矩阵加载 | 318.7 ms | 140.3 ms | 2.27× |
| `prescreen`（40 峰 × 5 组中位） | 3568.1 ms | **881.0 ms** | **4.05×** |
| `fetch_peaks(800)` | 1399.1 ms | 688.5 ms | 2.03× |
| `fetch_peaks(50)` | 1304 ms | **96.5 ms** | **13.5×** |
| `search_match_v3` 端到端 | **5222.2 ms** | **1624.1 ms** | **3.22×** |
| COD / TCOD prescreen | 235.8 / 114.5 ms | 61.1 / 34.6 ms | 3.86× / 3.31× |
| COD / TCOD 端到端 | 534.8 / 351.1 ms | 315.4 / 240.8 ms | 1.70× / 1.46× |
| PCOD 矩阵常驻（private） | 262.1 MiB | **136.8 MiB** | −48% |
| PCOD 进程峰值 private | 2620.3 MiB | **1328.6 MiB** | −49% |

> 折算到发布验收机器（该机比本机快约 19%）：prescreen ≈ **743 ms**、端到端 ≈ **1409 ms**。
> 两个目标（prescreen ≤1.2 s、端到端 ≤2.5 s）**均达成**。

**做了什么**
1. `prescreen` 按 **8192 行块**（1 MiB，驻 L2）处理，块内跑完全部测量窗——矩阵从「每窗全量扫一遍
   （PCOD 40 遍 ≈5 GB 内存流量）」变为「只读一遍」；行内 `any` 用「bool 块视作 uint64、3 次 OR」
   替代 NumPy 慢路径（该项单独 ~590 → ~150 ms）。
2. `_matrix()` 只保留 `top_d` + 一维 `main_i`（`top_i` 其余 31 列从不使用），游标迭代替代 `fetchall`。
3. `fetch_peaks` 用缓存的 chunk 布局表 + `bisect` 定位 + 按 chunk 分组，**只读含候选的 chunk**；
   连接加 `PRAGMA mmap_size=2 GiB`（只读映射页可回收，private 内存不涨）。
4. 顺带修复 §3.1 P1-4 与 §3.2 P2-3/2-4、§3.3 P3-1。

**等价性证据**：旧实现完整副本作 oracle（SHA-256 记录在 perf.md）——COD 20 组 / TCOD 20 组 /
PCOD 66 组（63 个参数组合，含 `min_match 1/2/3`、`tolerance 0.01/0.02/0.05`、`tolerance_rel`、
3 组元素过滤、`rank_limit 50/800`、48 组触发截断）**0 fail**；合成库参数叉积 ≈628 组；
端到端 3 库 × 2 查询候选顺序与 FoM 逐位一致。PCOD 全量 parity 进程峰值 private 2.33 GiB（< 2.5 GiB 上限）。

**残余限制**：800 个候选在 106 万相里几乎铺满全部 260 个 chunk 时，`fetch_peaks` 仍须读全量峰数据
（只剩 ~2×）。再降需要 schema v3.1（`entries.first_peak_off` 或 d 值倒排），与 v3.0.0-验收报告
§8.4 的建议一致，本轮未改 schema。

---

## 5. 三个无机物库 `.xinDB` 验收

> 完整证据：[`ACCEPTANCE-3COD-20261024.md`](ACCEPTANCE-3COD-20261024.md)（含 entry_id 级坏相清单与复现命令）。

| 库 | 相数 | `validate_xindb` | 独立全量复核 | 自召回 Top-1 / Top-5 | 判定 |
|---|---:|---|---|---|---|
| **COD-Inorg** | 78,036 | 26 项，0 FAIL / 1 WARN（已知 `96-210-4629` 退化晶胞） | 除 1 条已登记退化晶胞外 0 违规；**新发现 5 条 180° 假峰相** | **38/40 (95%) / 40/40**；2 例 Top-1 失配均为库内**重复相** | **WARN（可发布，登记 8 坏相）** |
| **PCOD-Inorg** | 1,061,953 | 25 项，0 FAIL / 0 WARN | 全部 260 chunk / 全部 entry 0 违规；**新发现 7 条 180° 假峰相** | **40/40 / 40/40**（中位 6.08 s，CPU 6.05 s） | **PASS（可发布，建议重建）** |
| **TCOD-Inorg** | 46,846 | 25 项，0 FAIL / 0 WARN | 0 违规 | **40/40 / 40/40**（中位 0.540 s） | **PASS（可直接发布）** |

**核心声明全部复核通过**：相数/反射数/块数、文件字节、`journal_mode=DELETE`、无 `-wal/-shm` 侧车、
`integrity_check=ok`、meta 全部必需键、`library_kind/data_date` 与文件名一致、三个 `entry_id` 号段
（0 / +2e7 / +1e8）互不重叠且 **118 万条 id 全量**可归属到源 manifest、`element_inv` 与
`entries.elements` **全量双向一致**、`elem_mask`（63 位截断口径）逐 entry 0 不一致、
来源对账差 = `skipped_no_peaks`（COD 1162 / PCOD 9 / TCOD 97，精确闭合）。

**已知数据缺口（不阻塞发布，需 Release notes 登记）**
1. **COD 8 条坏相 + PCOD 7 条坏相**：3 条 `d=1.0`（gemmi 占位晶胞）+ 5+7 条 `d=0.7703`（180° 边界）。
   根因已在本轮代码修复（§3.1 P1-1/P1-2），**重建即可清除**（见 §8.1）。
2. COD 2,002 组 `(formula, a, b, c)` 相同的重复相（4,475 entry）→ 自召回 Top-1 落到同结构另一条，
   属源数据固有歧义；是否去重是产品决策（`docs/COD全库优选去重库治理.md`）。
3. COD 127 条无空间群/晶系（磁结构/超空间群源数据缺失）、11 条 `crystal_system` NULL；
   PCOD/TCOD 无此问题。
4. `meta.cif_source` 仍是迁移前旧路径（build-time 记录，下次重建自动更新）；
   PCOD 仅 19 种元素是 GRINSP 预测集的客观构成，不是丢数据。

**召回裕度记录（只记录未修）**：`prescreen` 的 `min_match=2` 在 PCOD 上几乎不剪枝
（**1,057,102 / 1,061,953 = 99.5%** 的相命中 ≥2 个测量窗，COD 96.4% / TCOD 95.3%），
候选 800 完全由 prescreen 排序后截断，真值在 PCOD 上的召回裕度偏小。
这属于参数/schema 级设计（需 d 值倒排或更高 `min_match` 才能显著剪枝），已列入 §8.3。

**发布产物一致性**：主仓库 `XinMatch-Databases-COD-Inorg-3.0.0.zip` 内的 `.xinDB` 与本次验收的库
逐字节相同（SHA-256 `328c6acb…`），`SHA256SUMS.txt` 三个附件全部吻合（§1.2）。

**修复后引擎的建库链路复跑（Lead 抽样验收）**：用工作树（含本轮补丁）跑
`tools.build_cod_inorg_xindb --source COD --limit 40 --workers 2` →
40 相 / 4,997 反射 / **0 errors** / 1.5 s（**1,592 相/分钟**，与 README 的 1,590 一致）；
产物 `validate_xindb` **25 项 0 FAIL / 0 WARN**。
（注：文件名必须是 `<library_kind>-<data_date>.xinDB`；用 `lead_slice.xinDB` 这类名字时
`M3.identity` 会按设计 FAIL —— 文档里已有这条提醒，实测再次确认。）

---

## 6. 测试与 CI 评估

### 6.1 复验实测（本轮，`QT_QPA_PLATFORM=offscreen`，本机真实库在位，默认 `-m "not slow"`）

| 时点 | 结果 | 选中 / 收集 | 用时 | 退出码 |
|---|---|---|---:|---|
| **复验前基线**（v3.0.0 原样） | **1347 passed / 6 skipped / 1 xfailed / 51 deselected** | 1354 / 1405 | 16m47s | 0 |
| **修复 + 新增回归后**（本报告工作树） | **1411 passed / 4 skipped / 1 xfailed / 53 deselected，0 failed** | 1416 / 1469 | **13m01s** | 0 |

- `53 deselected` = `slow` 标记（turn-on 最小二乘、GSAS-II 子进程、L3 验收 curve_fit 等，`pytest -m slow` 单独跑）。
- 修复后比基线多 **62 项**（本轮新增回归约 60 项），用时反而少 4 分钟——差异主要来自**并发负载**
  （基线跑的时候有 3 个团队任务在读同一批 1.7 GB 库，修复后是串行空闲跑）。
- 唯一 warning 是 CLI 仪器绘图在 Agg 后端 `plt.show` 的无害提示。
- 最慢 15 项（`--durations=15`）几乎全是仓库外真实数据用例：`test_synthetic_acceptance` 的
  session setup **296 s**、`test_search_mode` 的 FPFM 真实库用例 34–52 s、`test_batch_core` 的
  FPFM 用例 31 s —— 印证 §6.2「默认套件被真实库用例拖长」的判断。

### 6.2 发现的问题

1. **「全量 1570 passed」不可复现**（§1.4 #1）：实际默认集 1354 项、含 UI 跑 1347 passed。
2. **默认套件不是「快套件」**：本机 16m47s，主要耗时在
   `tests/search/test_synthetic_acceptance.py`（13 组合成谱 × 745 MB v2 库整库检索，单文件约 10 分钟）
   与 `tests/ui/test_search_mode.py` 的 FPFM 真实库用例——它们**未标 `slow`**。
3. **本地私有数据依赖**：8 个测试文件引用已删除的 v2 库 `data/cod_inorganics.db`（不在 git），
   约 20 处硬编码 `D:\Project\XRD\...`；CI 干净 checkout 上这些用例 skip（CI 记录「4 skipped」远少于本地），
   造成「CI 绿 ≠ 本机绿」的反向偏差。
4. **无覆盖率门槛**：`--cov` 未进 CI；`ui`/`tools` 覆盖靠自觉。
5. **`tests/ui` 需要 `QT_QPA_PLATFORM=offscreen`**，否则本机默认 `pytest` 会在 Qt 模态框处挂住
   （README/CI 有提示，但 `pyproject.toml` 的 `addopts` 未兜底设置；建议 CI 与本机都显式）。

### 6.3 静态质量门（结论）

本轮已恢复到 **ruff 0 / mypy 0**（§3.4）。建议 CI **锁定工具版本**（`ruff==0.16.*`、`mypy==2.4.*`），
否则「ruff 新版新增规则」会让老仓库突然变红（本轮 218 条里 172 条来自一条归档探针文件）。

### 6.4 收尾回归（代码冻结后执行）

```
QT_QPA_PLATFORM=offscreen python -m pytest -q -p no:cacheprovider --durations=15
→ 1411 passed, 4 skipped, 1 xfailed, 53 deselected, 0 failed (EXIT=0, 13m01s)
```

并用 `python -m pytest --collect-only` 复核：**1416 / 1469 collected（53 slow deselected）**。
与 §6.1 的基线对比：新增 62 项回归、0 失败。同一冻结树上：

```
python -m ruff check xinmatch tools tests   → All checks passed!
python -m mypy                              → Success: no issues found in 119 source files
```

---

## 7. 文档一致性（已修 / 待修）

| # | 项 | 状态 |
|---|---|---|
| 1 | `docs/STATUS.md` 缺 v3.0.0 | ✅ 已补 v3.0.0 发布 + 2026-10-24 复验两节 |
| 2 | `docs/README.md` 索引未列 v3 文档、验收记录 | ✅ 已重排索引（含本报告、3COD 复验、发布说明） |
| 3 | `xinmatch/__init__.py` 顶层 API 文档仍写 `SQLite database` / `.db file` | ✅ 改为 `.xinDB` / v3 列存库 |
| 4 | `tools/build_cod_xindb.py` 文档仍有 `PolyXRD-DataBase/xindb` 旧路径示例 | ⏳ 低优先（代码注释，不影响运行） |
| 5 | README §3.4 PCOD「全为上限截断」、§5 `_backup/`、§4 退化晶胞「=1」 | ⏳ 建议下次改 README 时一并修正（§1.4 #6/#7/#8） |
| 6 | v3.0.0-验收报告 §7.5 库路径、§8.6 坏相只列 3 条 | ⏳ 历史记录不改写；新文档 `ACCEPTANCE-3COD-20261024.md` 已按实际补齐 |
| 7 | Release notes / ACCEPTANCE-v3.0.0 的「1570 passed」 | ⏳ 建议发布 v3.0.1 时加勘误（§6.1） |
| 8 | `docs/` 下大量历史文档无「历史」标记 | ⏳ 低优先 |

---

## 8. 下一步建议（按优先级）

### 8.1 立即（发布 v3.0.1 前必须）

1. **重建 COD-Inorg 与 PCOD-Inorg**（用本仓库含补丁的 `xinmatch`，`--workers 14`，COD ≈58 min / PCOD ≈12.7 h）：
   - 预期 COD：78,036 → **78,035** 相（`96-210-4629` 源数据无晶胞被剔除），
     `n_peaks=1` 的坏相 8 → **0**，其余相峰表与旧库逐位一致（用 `tools/_compare_xindb_peaks.py` 全量比对）；
   - 预期 PCOD：相数不变（1,061,953），7 条坏相恢复（150 峰/条），`n_peaks=1` 坏相 → **0**；
   - TCOD 无需重建（未发现同类），但建议重建后复跑同口径扫描。
   - ⚠ 必须先处理本机 `XINMATCH_XINDB_DIR` 指向旧目录的问题，或显式 `--out`。
2. **同步 `XinMatch-DataBase` 仓库的 vendored `xinmatch/core/db/{peak_compute,cif_meta,multi_db}.py`**
   （否则在 DB 仓库里建库仍会用旧引擎）。
3. **重打发布产物**（`tools/build_exe.ps1` 两变体 + 库 zip + `SHA256SUMS.txt`）：本轮修了 spec 漏收
   `atomic_scattering_params.json`；现有 v3.0.0 冻结包在「CIF→峰计算」路径上会 `FileNotFoundError`
   （当前 GUI 未接线该功能，属潜在缺陷）。
4. **发布说明加勘误**：`1570 passed` → 实测数字；COD/PCOD 各 8/7 条已知坏相（重建后清除）；
   默认库解析对坏环境变量的修复。

### 8.2 短期（1–2 周）

1. **测试可移植性**：把 `data/cod_inorganics.db` 依赖迁到 `tests/fixtures/*.xinDB`；硬编码
   `D:\Project\XRD\...` 改为 `XINMATCH_TESTDATA` 环境变量 + `skipif`；真实库/FPFM 用例统一
   `@pytest.mark.slow`，让默认 `pytest` 回到分钟级、CI 与本地同集。
2. **CI 加覆盖率与工具版本锁**（`--cov` 先软门槛；`ruff`/`mypy` 固定版本）。
3. **`validate_xindb` 增加峰引擎边界检查**（本轮的 12 条坏相 `validate_xindb` 全部抓不到）：
   建议加 `E5.single_peak`（`n_peaks==1` 且 `all_d ≈ d_min` → WARN/FAIL）与
   `E6.peak_count_consistency`（同 formula+cell 的峰数应相近），把这类缺陷挡在建库环节。
4. **`core/batch.py` 进度直接写 stderr**（去掉 CLI 侧改道兜底）。
5. **v3 库重建后更新 README/验收文档数字**（相数、反射数、命中率）。
6. **`auto_process` 的逐峰 `curve_fit` 是 CLI 端到端瓶颈**（只记录未修）：CLI `search/process/batch`
   实测端到端 6.6 s 中 **5.6 s（84%）** 花在预处理阶段的逐峰 `curve_fit`（33 峰 × ~0.23 s），
   真正的 `search_match` 仅 0.34 s（GUI 只用 `find_peaks` 故 0.82 s）。建议：对不关心峰形的检索路径
   提供「不做 curve_fit」的快速预处理；或把 `curve_fit` 批量化/并行化。`cProfile` 原始数据见
   `.scratch/review-v3/repro/`（ui-cli-audit 报告 F12）。

### 8.3 中期（1–2 个月）

1. **schema v3.1**：`entries.first_peak_off` 或 d 值倒排，把 PCOD `fetch_peaks(800)` 从 0.69 s 压到
   亚秒级端到端；同时可把 `prescreen min_match=2` 在 PCOD 上「几乎不剪枝」（99.5% 相命中）的问题
   用「d 值分箱倒排 + 交集」一并解决（候选更小、召回裕度更大）。
2. **GUI 收尾**：把 7 个占位模块接线或从菜单隐藏；`main_window.py` 拆分；库诊断（显示
   「库来源：环境变量/内置/外挂」）。
3. **v2 行表代码清理**：删除 `query_peaks`/`query_filter`/`build_cod`/`index_build`/`user_db`/`schema`
   或明确标注「仅 v2 兼容」，`search_match` 对 `sqlite3.Connection` 给可读错误。
4. **COD 重复相治理**：2,002 组同结构重复相影响 Top-1 唯一性；按 `docs/COD全库优选去重库治理.md`
   做「保留高质量条目」的去重库（可作为可选库发布，不改默认库）。

### 8.4 长期 / 不建议现在做

- **COD-Full / PCOD-Full / TCOD-Full** 三库（预估 COD ~36 h / 870 MB、PCOD ~12.7 h、TCOD ~4–6 h）：
  先把无机三库的坏相与发布产物清干净再排期。
- **Ed25519 注册升级**：会让已发出的注册码作废，需商业决策；维持现状。
- **`max_peaks=64` 保真对照**：v3 的 150 上限已被 G4a/G4b 验收覆盖，除非要压缩体积，不建议动。
- **有机/全库检索**：当前只发布无机子集；有机样品检索需另建 Full 库（见上）。

---

## 9. 复现命令

```powershell
$PY = 'D:\Project\XRD\python310\python.exe'
cd D:\Project\XRD\XinMatch
$env:QT_QPA_PLATFORM = 'offscreen'

# 静态门
& $PY -m ruff check xinmatch tools tests        # 期望 0
& $PY -m mypy                                   # 期望 0（119 files）

# 回归（含 UI；默认排除 slow）
& $PY -m pytest -p no:cacheprovider
# 慢套件（turn-on / GSAS-II / L3）
& $PY -m pytest -m slow -p no:cacheprovider

# 三库结构 + 端到端验收（只读）
cd D:\Project\XRD\XinMatch-DataBase
& $PY -m tools.validate_xindb data\COD-Inorg-20261020.xinDB --sample-chunks 20 --json out_cod.json
& $PY -m tools.validate_xindb data\PCOD-Inorg-20261020.xinDB --json out_pcod.json
& $PY -m tools.validate_xindb data\TCOD-Inorg-20261020.xinDB --sample-chunks 12 --json out_tcod.json
# 自召回脚本见 docs/ACCEPTANCE-3COD-20261024.md §10.2

# 重建（含本轮峰引擎补丁；务必显式 --out）
& $PY -m tools.build_cod_inorg_xindb --source COD --data-date 20261020 --workers 14 -v `
    --out D:\Project\XRD\XinMatch-DataBase\data\COD-Inorg-20261020.xinDB
```

---

## 10. 附录：本轮改动文件（工作树）

| 类别 | 文件 |
|---|---|
| 峰引擎 | `xinmatch/core/db/peak_compute.py`、`cif_meta.py` |
| v3 读写/检索 | `xinmatch/core/db/reader_v3.py`、`search_v3.py`、`multi_db.py`、`batch.py` |
| CLI / GUI | `xinmatch/cli/main.py`、`ui/main_window.py`、`ui/dialogs/config.py`、`xinmatch/__init__.py` |
| 打包 | `xinmatch.spec`、`pyproject.toml` |
| 工具 | `tools/validate_xindb.py`、`validate_peak_engine.py`、`build_cod_*.py`、`_probe_*.py` 等（lint/文档） |
| 测试 | 新增 `tests/db/{test_peak_compute_edges,test_search_v3,test_reader_v3_perf}.py`；修改 7 个既有测试文件 |
| 文档 | `docs/STATUS.md`、`docs/README.md`、`docs/ACCEPTANCE-3COD-20261024.md`、本报告 |

> 全部改动未 push；`.scratch/review-v3/` 下的原始报告/JSON/脚本为本地证据（不入 git）。
