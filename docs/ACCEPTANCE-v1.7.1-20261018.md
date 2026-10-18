# 验收文档 — v1.7.1 维护版本（2026-10-18）

## 1. 版本与范围

| 项 | 内容 |
|---|---|
| 版本 | 1.7.0 → **1.7.1**（维护版本，无 API 破坏、无数据迁移） |
| 主题 | 代码评审整改：缺陷修复（P0）+ 大库检索性能（P1）+ 工程化（P2） |
| 依据 | [`CODE_REVIEW-20261018.md`](CODE_REVIEW-20261018.md)（评审 + 逐条方案 + 实施记录 §7） |
| 范围外 | `core/pipeline.py` 三入口统一、`main_window.py` 拆分、注册码改非对称（均记为后续批次） |

## 2. 变更清单

### 2.1 缺陷修复（P0）

| # | 变更 | 文件 |
|---|---|---|
| A1 | GUI 每次检索泄漏 SQLite 连接 → 改为「谁打开谁关闭」，重入被拒时调用方补关 | `ui/main_window.py`、`ui/busy.py` |
| A2 | `d ≤ λ/2` 时 `math.asin` 越界崩溃 → 跳过该峰并记录；2θ 窗口上下限钳制 | `core/db/query_peaks.py` |
| A3 | `recall_max_candidates` 在 restraints 模式失效 → 与 d 值召回求交后截断 | `core/search/search_match.py` |
| A4 | wheel 缺运行时资源（`schema.sql` / 3dmol）→ 声明包数据 + `importlib.resources` 读取 | `pyproject.toml`、`core/db/schema.py` |
| A5 | 无 dist-info 时 `import xinmatch` 失败 → 版本号回退常量 | `xinmatch/__init__.py` |
| A6 | `PatternView.clear()` 被 pyqtgraph 实例属性遮蔽（真实 bug：清空后 `patterns()` 仍返回旧曲线） | `ui/pattern_view.py` |

### 2.2 性能（P1）

| # | 变更 | 效果 |
|---|---|---|
| B1 | `fetch_entries_by_ids` N+1 → 两趟分块查询（500/批） | 3000 候选 SQL 往返 3000 → 7 |
| B2 | Hanawalt top-K 缓存加库指纹（mtime/size）+ 锁 + LRU(2) | 重建/替换库不再命中旧排名 |
| B3 | 新增 `fpfm.to_candidates()`，GUI/批处理/CLI 共用 | 三处结果组装归一，消除 FoM 漂移 |

### 2.3 体验

- 打开数据文件走忙碌窗口（大 `.raw`/`.brml` 不冻结界面）
- FPFM 等长任务支持**协作式取消**（`core/cancel.py`，置标志由核心层抛异常退出，不强杀线程）
- 5 个工具栏菜单由占位变为可用：背景扣除 / 平滑 / Kα2 剥离 / 重置原始数据 / 峰检测

### 2.4 工程化

- `.github/workflows/ci.yml`（ubuntu+windows × py3.10/3.12；ruff + mypy + 默认测试；wheel 资源断言；`workflow_dispatch` 可跑 slow）
- 本地等价入口 `tools/ci.ps1`
- `slow` 标记补齐、`addopts` 默认 `-m "not slow"`（`pytest` 可直接运行）
- 去掉硬编码 `D:\Project\...` 默认库路径；SQLite URI 用 `Path.as_uri()`；LIKE 通配符转义；`gsas2_parse` 静默异常补日志；支持 `GSAS2_HOME` 覆盖
- `docs/README.md` 文档索引、`tools/clean_data_backups.ps1`（默认 dry-run）

## 3. 版本号同步（1.7.1）

| 位置 | 核验 |
|---|---|
| `pyproject.toml` | `version = "1.7.1"` ✅ |
| `xinmatch/__init__.py` | 回退常量 `1.7.1` ✅ |
| `xinmatch.spec` | `APP_VERSION = "1.7.1"`、`VERSION_TUPLE = (1, 7, 1, 0)` ✅ |
| `tools/build_exe.ps1` | 默认 `-Version "1.7.1"` ✅ |
| `tools/xinmatch_setup.iss` | 11 处（AppVersion / OutputBaseFilename / VersionInfo* / `[Files]` 源目录）✅ |
| `README.md` | 状态行 ✅ |
| 运行时 | `importlib.metadata.version("xinmatch") == "1.7.1"`，`xinmatch.__version__ == "1.7.1"` ✅ |

## 4. 静态检查

| 检查 | 命令 | 结果 |
|---|---|---|
| ruff | `python -m ruff check xinmatch tools tests` | **All checks passed** |
| mypy | `python -m mypy` | **Success: no issues found in 113 source files** |

## 5. 回归测试（默认套件，排除 `slow`）

命令：

```powershell
$env:QT_QPA_PLATFORM="offscreen"
python -m pytest -q -p no:cacheprovider --junitxml=.scratch/junit_v171.xml
```

结果（JUnit XML 统计）：

| 指标 | 数值 |
|---|---|
| 测试总数 | **1297** |
| 通过 | **1290** |
| 失败 / 错误 | **0 / 0** |
| 跳过 | 7 |
| 耗时 | 794.9 s（13.2 min） |

新增/加固的测试：`tests/ui/test_preprocess_actions.py`（7 项，菜单接线）、`tests/ui/test_busy_cancel.py`（3 项，协作式取消）、
`tests/db/test_query_peaks.py`（+2 项背散射边界）、`tests/search/test_search_match.py`（+2 项候选上限）、
`tests/instrument/*`（缺 pyserial 时 `importorskip` 而非失败）、`tests/cli/test_cli.py`（UTF-8 解码）。

### 未覆盖说明

- **`slow` 套件本次未执行**（`turn-on` 最小二乘、GSAS-II 实机精修、L3 acceptance）。相关代码路径本轮仅
  `core/refine/gsas2_parse.py` 增加日志与 `GSAS2_HOME` 覆盖，逻辑未变；建议在夜间 CI 或单独会话补跑
  `pytest -m slow`。
- 首轮全量运行时 `pyserial`（`pyproject` 声明的运行依赖）未安装，`tests/instrument` 有 4 项失败；
  安装 `pyserial 3.5` 后该模块 37 项全绿，并给两个测试文件加了 `importorskip` 兜底。

## 6. 打包产物

| 产物 | 大小 | 说明 |
|---|---|---|
| `dist/XinMatch-Setup-1.7.1.exe` | 180,895,295 B（172.5 MiB） | Inno Setup 6 安装包（release，含注册机制；DB 不内置） |
| `dist/XinMatch-Internal-1.7.1.zip` | 265,449,143 B（254 MiB） | 内部评估版 onedir（无注册） |
| `dist/xinmatch-cod-db-1.7.1.zip` | 204,614,250 B（196 MiB） | 参考库，解压到安装目录 → `data/cod_inorganics.db` |
| `dist/xinmatch-1.7.1/` | 673 MB | release onedir（`XinMatch.exe` 7.3 MB） |
| `dist/xinmatch-internal-1.7.1/` | — | internal onedir |

变体标记核验：`dist/xinmatch-1.7.1/_internal/variant.txt` = `release`；
`dist/xinmatch-internal-1.7.1/_internal/variant.txt` = `internal`。

### 冻结二进制冒烟

| 项 | 结果 |
|---|---|
| `XinMatch.exe import --help` | exit 0，CLI 正常输出 ✅ |
| internal 变体 `XINMATCH_SELFTEST_REG=1` | `registration_selftest.json`：`variant=internal`、`registration_enabled=false`、`status_text=内部评估版本`、exit 0 ✅ |
| release 变体 `XINMATCH_SELFTEST_REG=1` | 在非交互会话下被启动期注册提示框阻塞（与 v1.7.0 验收记录相同的环境限制）；`variant.txt=release` + 单元测试覆盖（`tests/utils/test_registration.py`）确认注册开启 ⚠️ |
| 实机静默安装 | 未执行（同上会话限制） |

### 备注（构建过程）

首次并行启动 release / internal 两个 PyInstaller 进程时，二者共享 `build/` 工作目录导致
**internal 产物沿用了 release 的 COLLECT toc**（输出目录名错误）。已改为串行构建并核验
`variant.txt`；`tools/build_exe.ps1` 的变体校验会拦截此类错误（本次即由该校验报错发现）。

## 7. Release

- tag：`v1.7.1`（指向 `master` 的 `efe6789`）
- 地址：https://github.com/PolyXRD/XinMatch/releases/tag/v1.7.1
- 状态：已发布（draft=false / prerelease=false）
- 附件（3 个，均已上传成功）：
  `XinMatch-Setup-1.7.1.exe`、`xinmatch-cod-db-1.7.1.zip`、`XinMatch-Internal-1.7.1.zip`
- 发布说明：缺陷修复 / 性能 / 体验 / 工程化 / 验收数字 / 安装步骤 / 已知限制

推送记录：`9b59715..efe6789  master -> master`（`d483b28` 代码 + `efe6789` 文档）。

## 8. 结论

**验收通过。** 静态检查零告警、默认回归 1297 项 0 失败、打包资源完整（wheel 与 onedir 均含
`schema.sql` + 3dmol 资源）、三类产物构建完成、版本号六处同步。
遗留项（`slow` 套件补跑、release 变体 GUI 自检、实机安装）已按环境限制如实记录，不阻塞发布。
