# 验收文档 — v1.6.1 版本发布（2026-10-16）

## 一、版本范围

| 项目 | 内容 |
|---|---|
| 版本 | 1.6.0 → **1.6.1** |
| 增量 | **SMPF → FPFM（Full Pattern Fitting Match）更名**（commit `cc12b9c`，30 文件）+ 并行会话合并的 March-Dollase 择优取向修正（`33a7f45`）+ 双许可切换（PolyXRD Academic/Commercial，`0a2c9c6` 等）+ README logo + COD 打包规范文档与 sync-COD 工具包 |
| 性质 | 小幅版本升级：纯更名 + 兼容层，**无算法/功能变更**（March-Dollase 为并行会话独立合入并自带测试） |
| 产物 | PyInstaller onedir + 单文件安装版（Inno Setup）+ 便携 zip（DB 均单独挂载）+ COD DB 压缩包 |

## 二、更名与兼容设计

- **更名范围**：模块 `core/search/smpf.py` → `fpfm.py`（git mv 保留历史）；`SmpfConfig→FpfmConfig`、`search_match_smpf→search_match_fpfm`、`SEARCH_MODE_SMPF_FULL→SEARCH_MODE_FPFM_FULL`、UI 文案、`docs/TERMINOLOGY.md` 词条 50（注明 v1.6.1 前旧称 SMPF）、README 状态行。
- **三层向后兼容**（旧 `smpf` 写法全部静默接受，附 3 个回归测试）：
  1. CLI `--mode smpf` 别名 → `cmd_search` 归一化为 `fpfm`（choices 保留 `smpf`，帮助文本注明 legacy）；
  2. 批处理 YAML `mode: smpf` → `_validate_config` 原位归一化为 `fpfm`；
  3. 持久化配置键 `smpf_kalpha*` → `load_config` 在**合并前**迁移为 `fpfm_*`（先迁移磁盘字典再 merge，旧用户设置仍优先于新默认值）。
- **无需迁移项**：`SEARCH_MODE_SMPF_FULL` 的值（`smpf_full`→`fpfm_full`）仅运行时使用、从不落盘（代码检索核实无持久化路径）。

## 三、执行动作清单（已逐项确认）

- [x] **更名实施**：git mv 6 文件 + 全量替换 24 文件；ruff --fix 处理 import 排序（I001）。
- [x] **兼容层 + 回归测试**：`test_legacy_smpf_mode_alias_accepted`（CLI 报告 `"mode": "fpfm"`）、`test_batch_legacy_smpf_mode_normalized`、`test_legacy_smpf_config_keys_migrated`（tmp YAML `smpf_*` 载入为 `fpfm_*` 无残留）。
- [x] **版本号同步**（1.6.0→1.6.1）：`pyproject.toml`、`xinmatch.spec`（APP_VERSION / **VERSION_TUPLE (1,6,1,0)** 逗号格式 / COLLECT name）、`tools/build_exe.ps1` $Version、`tools/xinmatch_setup.iss`（11 处）、README 状态行；`pip install -e . --no-deps` 后 `xinmatch.__version__ == "1.6.1"` 实测。
- [x] **静态检查**：ruff 全量 **All checks passed**；mypy **109 files 0 errors**。
- [x] **快速子集冒烟**：cli + batch 相关用例 10 passed（含 3 个兼容回归测试）。
- [x] **全量回归**：核心套件（default venv，含全部 slow）+ UI/CLI 套件（python310 offscreen）——结果见 §四。
- [x] **PyInstaller onedir 构建**：`dist/xinmatch-1.6.1/`（版本资源 1.6.1；COD DB 不内置，随包挂载）。
- [x] **COD DB 压缩包**：`dist/xinmatch-cod-db-1.6.1.zip`（zip 内路径 `data/cod_inorganics.db`，解压即挂载）。
- [x] **Inno Setup 单文件安装版**：`dist/XinMatch-Setup-1.6.1.exe`。
- [x] **便携免安装版**：`dist/XinMatch-Portable-1.6.1.zip`（本地保留，不上传）。
- [x] **GitHub Release**：tag `v1.6.1`，上传 `XinMatch-Setup-1.6.1.exe` + `xinmatch-cod-db-1.6.1.zip`。
- [x] **提交推送**：`cc12b9c` + 文档提交，master 推送 + tag 推送。

## 四、验证方式与覆盖

| 验证 | 方式 | 结果 |
|---|---|---|
| 版本号 | `import xinmatch` + 五处文件核验 | 1.6.1 ✅ |
| 静态 | ruff 全量 + mypy 全量 | All checks passed / 0 errors (109 files) |
| 兼容层 | 3 个专项回归测试 | CLI/batch/config 三路 legacy `smpf` 均通过 |
| 回归 | 核心 junit + UI/CLI junit（python310） | 核心 **1091 passed / 0 failed / 5 skipped**（5035s，含全部 slow）；UI+CLI **237 passed / 0 failed**（322s） |
| 产物 | dist/ 清单 + exe 版本资源 + DB zip 结构回读 | onedir 673 MB（VersionInfo 1.6.1）；DB zip 210,227,894 B（内含 `data/cod_inorganics.db`）；Setup exe 180,890,797 B；便携 zip 270,687,783 B；`XinMatch.exe search --help` exit 0（`--mode {peaks,fpfm,smpf}`，帮助注明旧称 smpf 仍接受） |
| Release | `gh release view v1.6.1` 资产核对 | Setup exe + DB zip 均 uploaded |

## 五、诚实边界

- 便携包仅本地保留，未上传 GitHub（沿用 v1.6.0 约定）。
- Setup 安装版未做「全新机器」实机安装冒烟（无干净 VM）；安装逻辑沿用 1.6.0 已验证流程。
- 旧配置键迁移覆盖 `smpf_` 前缀键（当前仅 kalpha 三键）；若未来出现其他历史键需追加映射。
- 并行会话的 March-Dollase 修正随本版首次进入 Release，其专项测试已含于核心套件。

## 六、结论

**验收通过。** v1.6.1 全部发布门禁通过：更名完成且三层向后兼容、版本同步到位、静态检查全绿、全量回归 0 失败、四类产物构建完成、Release 上传成功。
