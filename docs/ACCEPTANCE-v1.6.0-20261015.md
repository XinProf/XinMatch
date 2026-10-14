# 验收文档 — v1.6.0 版本发布（2026-10-15）

## 一、版本范围

| 项目 | 内容 |
|---|---|
| 版本 | 1.5.0 → **1.6.0** |
| 增量 | 1.5.0 发布后全部开发：**T6.0**（检索预筛策略修复 + 性能优化）、**T14.3**（批处理脚本收尾 + 主 CLI 接入）、**T14.4**（串口仪器控制）、**T2.4**（Bruker RAW v3/v4 读取）、**T0.2**（参考软件版本 diff）、**T0.5**（术语映射表）、**T0.3/T0.4**（TiO₂ 标准样品集 + 定量验证） |
| 产物 | PyInstaller onedir + 单文件安装版（Inno Setup）+ 便携 zip（DB 均单独挂载）+ COD DB 压缩包 |

## 二、执行动作清单（已逐项确认）

- [x] **版本号同步**（1.5.0→1.6.0）：`pyproject.toml` version、`xinmatch.spec` APP_VERSION/**VERSION_TUPLE**/COLLECT name、`tools/build_exe.ps1` $Version、`tools/xinmatch_setup.iss`（AppVersion/AppVerName/OutputBaseFilename/VersionInfo×4/[Files] Source）、README 状态行；`pip install -e .` 后 `xinmatch.__version__ == "1.6.0"` 实测。
- [x] **静态检查清零**（本次新修 24 处存量欠账）：
  - ruff 6 处：`cli/main.py`（matplotlib 未用导入删除、DataPoint 注解用途标注）、`le_bail.py` E402 import 移顶、`backfill_cells.py` numpy 未用删除、`smpf.py` SIM108 ternary、`test_smpf.py` I001 排序 → 全量 **All checks passed**；
  - mypy 18 处：14 处 `no-any-return`（Qt/numpy stub Any 传播，type: ignore 标注，行为零变化）+ 3 处 `fom_criteria` ndarray.max → `np.max(...)`（语义等价）+ 1 处 `le_bail` np.trapz → getattr 双备 → **Success: no issues found in 109 source files**。
- [x] **全量回归**：核心套件 **1089 passed / 0 failed / 0 error / 46 skipped**（5668s，含 SMPF slow、Rietveld、turn_on 发散等全部慢测试）；UI 套件（python310）**209 passed / 0 failed**（377s，含 pdf2_source_config）；ruff/mypy 全绿。
- [x] **PyInstaller onedir 构建**：`dist/xinmatch-1.6.0/`（XinMatch.exe 版本资源 1.6.0；COD DB 不内置，随包挂载）。
- [x] **COD DB 压缩包**：`dist/xinmatch-cod-db-1.6.0.zip`（210.2 MB，745.6 MB→deflate-9；zip 内路径 `data/cod_inorganics.db`，解压即挂载）。
- [x] **Inno Setup 单文件安装版**：`dist/XinMatch-Setup-1.6.0.exe`（DB 不内置，安装后解压 DB zip 到安装目录）。
- [x] **便携免安装版**：`dist/XinMatch-Portable-1.6.0.zip`（本地保留，DB 单独挂载）。
- [x] **GitHub Release**：tag `v1.6.0`，上传 `XinMatch-Setup-1.6.0.exe` + `xinmatch-cod-db-1.6.0.zip`（便携包不上传）。
- [x] **提交推送**：版本同步 + 静态修复 + 验收/STATUS 提交并推送，master 0/0 同步。

## 三、为什么这次发布比较费时间（按耗时排序）

1. **全量回归的固有成本**：1.6.0 含 1.5.0 后全部代码增量（检索预筛、批处理、串口、Bruker RAW、参考软件比对、TiO₂ 定量），发布门禁须跑含慢测试的完整核心套件——**1089 用例 5668 秒（~94 分钟）**，其中 turn_on 发散测试单测 ~35 分钟、SMPF/Rietveld slow 测试各数十秒至分钟级。UI 另需 python310 解释器（PySide6）跑 209 用例 377 秒。这是算法/集成固有成本，非异常。
2. **静态检查存量清零**：1.5.0 后各提交只按「本轮文件」做 lint/type 检查，全量 ruff/mypy 暴露 24 处存量欠账（ruff 6 + mypy 18）。mypy 的 18 处中 14 处是 Qt/numpy 类型 stub 的 `no-any-return`（Any 传播）——逐处核对上下文确认语义等价后标注，避免误改核心行为；fom_criteria 3 处 `arr.max()` 改 `np.max(arr)` 属 mypy 重载要求（行为等价）；另修 `le_bail` 的 numpy 2.0 `trapz` 兼容写法。此步耗时主要在「核对而非修改」。
3. **测试环境差异排查**：default venv 无 PySide6，`tests/db/test_pdf2_source_config.py`（import UI 模块）在核心套件收集期即报错——归因后核心套件显式排除该文件（属 UI 依赖，归 UI 套件跑，209 用例已覆盖）。
4. **版本号同步的经典坑**：`VERSION_TUPLE = (1, 5, 0, 0)` 用逗号格式（非 `1.5.0` 点格式），批量替换 `1.5.0→1.6.0` 会漏掉它——人工核验发现并修复（v1.4.0 时漏过 COLLECT name，同族坑）。
5. **打包链路**：PyInstaller onedir（~1.2 GB 产物）+ 745.6 MB DB 压缩（deflate-9，~4 分钟）+ Inno Setup 编译 + 便携 zip 压缩（~274 MB）——构建与压缩均为磁盘/CPU 密集操作。

## 四、验证方式与覆盖

| 验证 | 方式 | 结果 |
|---|---|---|
| 版本号 | `import xinmatch` + 五处文件核验 | 1.6.0 ✅ |
| 静态 | ruff 全量 + mypy 全量 | All checks passed / 0 errors (109 files) |
| 回归 | 核心 junit + UI junit | 1089+209 全过，0 failed |
| 产物 | dist/ 清单 + exe 版本资源 + DB zip 结构回读 | 见 §二 |
| Release | gh release view v1.6.0 资产核对 | Setup exe + DB zip |

## 五、诚实边界

- 便携包（Portable zip）按要求仅本地保留，未上传 GitHub。
- Setup 安装版未做「全新机器」实机安装冒烟（无干净 VM）；安装逻辑沿用 1.5.0 已验证流程（Inno Setup + DB 挂载约定）。
- 核心套件排除的 `test_pdf2_source_config.py` 已在 UI 套件中覆盖（209 用例含之）。
- 1.5.0 产物保留在 dist/ 未清理（发布历史留存；如需清理可另执行）。

## 六、结论

**验收通过。** v1.6.0 全部发布门禁通过：版本同步到位、静态检查清零、全量回归 0 失败、四类产物构建完成、Release 上传成功、仓库 0/0 同步。任务 #35 关闭。
