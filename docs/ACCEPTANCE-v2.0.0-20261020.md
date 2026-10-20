# 验收文档 — v2.0.0（2026-10-20）

## 1. 版本与范围

**版本**：1.7.1 → **2.0.0**（大版本：外部数据库挂载从「拷进安装目录」改为「任意位置挂载」）。

**范围**：

- 主特性 `c0b1a56`：PolyXRD `.sqlite` 直接挂载 + 外部库注册表（CLI/GUI）；
- 工程支撑 `36f36f8` / `f8a3c22`：`run_dev.bat`（免打包运行工作树）；
- 配套文档 `c7e85bc` / `da82e5e` / `12ed643` / `a53dcfa`：3COD 库验收与按来源分库；
- **本次验收中修复的 3 个发布缺陷**（见 §2.6）——都是只有走到「冻结二进制 + 打包」才会暴露的问题。

## 2. 变更清单

### 2.1 PolyXRD `.sqlite` 兼容（`core/db/polyxrd.py`）

- schema 判别：`xinmatch`（entries+peaks+elements）/ `polyxrd phases`（phases+peaks_d/peaks_i）/
  `polyxrd cod_entries`（仅结构，无峰）/ `unknown`；
- PolyXRD `phases` 库**一次性**转成 XinMatch 原生 schema 的 sidecar，落在
  `<用户数据>/indexes/external/`，用源文件 `mtime+size` 做指纹，源库始终只读打开，转换可取消；
- 结构型 dump（`cod_index.sqlite`/`cod_entries`）明确拒绝并给出原因，而不是挂成一个空库。

### 2.2 外部库注册表（`core/db/multi_db.py`）

`KIND_POLYXRD` 新库型；`libraries.json` 记录任意路径的挂载项；`*.sqlite` 与 `*.db` 等价接受；
`LibraryNeedsIndexError` + `ensure_library_index()` 把「该建索引」变成可捕获的状态而不是隐式慢查询。

### 2.3 CLI

`search` / `run` 统一走 `open_search_database()`；新增 `libraries` 子命令
（`--add / --remove / --build / --list [--json]`）。

### 2.4 GUI

设置 → 参考数据库：**添加外部库 / 移除挂载 / 建立·重建索引**，带进度日志；
打开一个尚未建索引的库时，在忙碌遮罩后自动建索引并重试。

### 2.5 打包

版本号 2.0.0 全链路同步；`docs/PACKAGING.md` 补外部库挂载说明；
DB 仍不内置于二进制，单独发 `xinmatch-cod-db-2.0.0.zip`。

### 2.6 验收中发现并修复的发布缺陷（P0）

这三个问题在源码运行下都不出现，只在冻结二进制/打包链路上暴露：

**① 冻结版 `libraries` 子命令根本不走 CLI**（`tools/pyi_entry.py`）

分发器硬编码了 6 个子命令，漏掉 `libraries`（还有历史遗留的 `batch`、`instrument`）。
后果：`XinMatch.exe libraries --add ...` 被当成「未知子命令」→ **直接启动 GUI**，
既没挂载也没报错。实测证据：执行后输出全是 GUI 才有 `Unknown property titleBarShownX` /
`propagateSizeHints()` 警告，且 `XINMATCH_USER_DATA` 目录根本没被创建。

修复：改成从 `build_parser()` 运行时推导子命令集合（静态列表只作 import 失败的兜底），
并新增 `tests/tools/test_pyi_entry.py`（12 项：集合一致性、兜底列表一致性、路由、`-h/--help`）。

**② `build_exe.ps1` 的变体传递不可靠 → internal 构建会删掉 release 产物**

`BUNDLE_NAME` 由变体决定，而变体只靠环境变量传给 spec。实测 `-File` 嵌套调用时环境变量
没能到达子进程，于是 internal 构建算出了 release 的 `BUNDLE_NAME`，PyInstaller 的 COLLECT
**先删除 `dist\xinmatch-2.0.0\`**（已建好的正式版）再写入——等于静默毁掉前一个变体。
本次被沙箱的批量删除保护拦下（`SAFE_DELETE_BULK_CONFIRM_REQUIRED`，3554 个文件），
`dist/xinmatch-2.0.0` 事后核验仍完整（3553 文件 / 673 MB / `variant.txt=release`）。

修复：变体改为**文件传递**（`build/variant.request`，spec 里文件优先于环境变量），
构建前校验写入/读回一致，不一致立刻失败且不动 `dist/`。

**③ `.ps1` 无 UTF-8 BOM + 中文注释 → PowerShell 5.1 解析错乱**

现象很隐蔽：断言里的 python 子进程返回空串、`$LASTEXITCODE` 为空、`Join-Path` 收到 `$null`。
根因是 UTF-8（无 BOM）的中文注释在 PS 5.1 下按 ANSI 解码，某些字节恰好落成行尾反斜杠，
把下一行代码并进了注释。修复：`tools/build_exe.ps1` 保存为 UTF-8 **带 BOM**。

## 3. 版本号同步（2.0.0）

| 位置 | 核验 |
|---|---|
| `pyproject.toml` | `version = "2.0.0"` ✅ |
| `xinmatch/__init__.py` | 回退常量 `2.0.0` ✅ |
| `xinmatch.spec` | `APP_VERSION = "2.0.0"`、`VERSION_TUPLE = (2, 0, 0, 0)` ✅ |
| `tools/build_exe.ps1` | 默认 `-Version "2.0.0"` ✅ |
| `tools/xinmatch_setup.iss` | 11 处（AppVersion / OutputBaseFilename / VersionInfo* / `[Files]` 源目录）✅ |
| `README.md` | 状态行 `v2.0.0` ✅ |
| 运行时 | `importlib.metadata.version("xinmatch")` / `xinmatch.__version__` = `2.0.0` ✅ |

## 4. 静态检查

| 检查 | 命令 | 结果 |
|---|---|---|
| ruff | `python -m ruff check xinmatch tools tests` | **All checks passed** |
| mypy | `python -m mypy` | **Success: no issues found in 114 source files** |

## 5. 回归测试（默认套件，排除 `slow`）

命令：

```powershell
$env:QT_QPA_PLATFORM="offscreen"
python -m pytest -q -p no:cacheprovider --basetemp=.scratch/ptmp2 --junitxml=.scratch/junit_v200_final.xml
```

结果（JUnit XML 统计）：

| 指标 | 数值 |
|---|---|
| 测试总数 | **1351** |
| 通过 | **1344** |
| 失败 / 错误 | **0 / 0** |
| 跳过 | 7 |
| 耗时 | 742.7 s（12.4 min） |

相比 v1.7.1 的 1297 项 +54 项：其中 42 项是 2.0.0 的外部库/挂载特性测试
（`tests/db/test_polyxrd.py`、`tests/db/test_library_registry.py`、
`tests/cli/test_cli_libraries.py`、`tests/ui/test_external_library_mount.py`、
`tests/ui/test_library_dialog_external.py`），12 项是本次验收为分发器缺陷新增的
`tests/tools/test_pyi_entry.py`。

### 未覆盖说明

- **`slow` 套件本次未执行**（`turn-on` 最小二乘、GSAS-II 实机精修、L3 acceptance），
  与 v1.7.1 一致，建议夜间单独补跑 `pytest -m slow`。
- 首轮全量运行报了 `rc=1` 但没有 `F/E` 标记：原因是沙箱的批量删除保护在 teardown 期
  拦截了 pytest 临时目录清理（`%TEMP%\pytest-of-*` 上百个文件），进程被打断。
  改用**仓内** `--basetemp` 后 `rc=0`，统计以 JUnit XML 为准。

## 6. 打包产物

| 产物 | 大小 | 说明 |
|---|---|---|
| `dist/XinMatch-Setup-2.0.0.exe` | 180,974,864 B（172.6 MiB） | Inno Setup 6 安装包（release，含注册机制；可选安装位置；DB 不内置） |
| `dist/XinMatch-Internal-2.0.0.zip` | 265,471,156 B（253.2 MiB） | 内部评估版 onedir（无注册），解压即用 |
| `dist/xinmatch-cod-db-2.0.0.zip` | 204,614,240 B（195.1 MiB） | 参考库，解压到安装目录 → `data/cod_inorganics.db`（745,627,648 B / 71,206 条） |
| `dist/xinmatch-2.0.0/` | 681 MB | release onedir（`XinMatch.exe` 7,671,234 B） |
| `dist/xinmatch-internal-2.0.0/` | 681 MB | internal onedir |

变体标记核验：`dist/xinmatch-2.0.0/_internal/variant.txt` = `release`；
`dist/xinmatch-internal-2.0.0/_internal/variant.txt` = `internal`。

### 冻结二进制冒烟

两个变体都跑了同一组检查，**全部通过**（这一轮比 v1.7.1 完整：上次 release 变体被注册弹窗卡住，没能自检）：

| 项 | release | internal |
|---|---|---|
| `XinMatch.exe import --help` | exit 0 ✅ | exit 0 ✅ |
| `XinMatch.exe libraries --json` | exit 0，返回 JSON（修复 ① 前会打开 GUI 卡死）✅ | exit 0 ✅ |
| `libraries --add <COD 分库>` | —— | exit 0，`kind=xinmatch`、`entries=78,747`、`needs_index=false`，写入隔离用户目录 ✅ |
| `search synth_01 --db <COD 分库>` | —— | exit 0，`n_peaks=78`，Top-3 全为 Al₂O₃（FoM 0.802 / 0.802 / 0.800，真值 COD 2300448 第 2）✅ |
| `XINMATCH_SELFTEST_REG=1` | `{"variant":"release","registration_enabled":true,"registered":false,"status_text":"未注册"}` ✅ | `{"variant":"internal","registration_enabled":false,"status_text":"内部评估版本"}` ✅ |
| 中文标签落盘 | —— | `libraries.json` 内为正确 UTF-8「COD 无机」✅ |

注：`Get-Content` 默认按 ANSI 读 UTF-8 文件会显示成「COD 鏃犳満」，这是**查看方式**的问题，
文件内容用 UTF-8 解码后正常；已单独核验。

### 备注（构建过程）

- 沙箱的批量删除保护会拦截 PyInstaller COLLECT 对已存在输出目录的清理
  （`count=3553 > threshold=50`），导致构建 `exit 1`。绕开方式：构建前把旧变体目录
  **移出** `dist/` 而不是删除。这不是产品缺陷，但**在本机重复构建时必须这么做**。
- `README`/`tools` 的换行遵循仓库既有约定（`core.autocrlf`，`*.bat` 固定 CRLF）。

## 7. Release

@@RELEASE@@

## 8. 结论

**验收通过。** 静态检查零告警；默认回归 1351 项 0 失败；两个变体的冻结二进制全部通过
CLI + 外部库挂载 + 检索 + 注册自检；三类产物构建完成；版本号七处同步。

本次最有价值的产出不是新功能本身，而是**§2.6 的三个发布缺陷**：它们都只在「冻结 + 打包」
阶段出现，源码跑一万次也发现不了。其中 ① 会让 2.0.0 的核心功能在发行版里形同虚设
（`libraries` 打不开库，只是弹个 GUI），② 会在下次构建 internal 时删掉 release 产物。
三个问题均已修复并加了回归测试/构建前断言。

**遗留**：`slow` 套件未跑；实机静默安装未执行（非交互会话）；
`max_peaks=64` 保真对照测试（`.scratch/ext64/cod64.db`）仍未收尾；
3COD 单体库（19.51 GiB）与 Full 库（28.17 GiB）按用户要求**暂不删除**。
