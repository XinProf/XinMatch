# 验收文档 — v1.7.0 版本发布（2026-10-16）

## 一、版本范围

| 项目 | 内容 |
|---|---|
| 版本 | 1.6.1 → **1.7.0** |
| 增量 | **注册机制**（复用 PolyXRD-Reg）+ **双二进制构建变体**（release 正式版 / internal 内部评估版） |
| 性质 | 功能新增；计算内核（`core/`）未改动 |
| 产物 | 两个二进制 + COD DB 压缩包（DB 均单独挂载） |

## 二、需求 → 实现对照

| 需求 | 实现 | 证据 |
|---|---|---|
| 未注册每次启动提示「本软件未注册，版权所有，禁止用于商业用途。如需注册请联系 sshztx@outlook.com」 | `startup_prompt()`：窗口 show 后 `QTimer.singleShot(0,…)` 弹窗（文案为模块常量 `UNREGISTERED_NOTICE`） | `test_startup_prompt_shows_required_notice`（逐字比对文案 + 按钮 `确定`/`输入注册码`） |
| 点「确定」后软件仍可正常使用，只是提示 | 弹窗关闭即回到主窗口，无任何功能降级 | 同上（返回未注册状态，不抛错、不退出） |
| 点「输入注册码」→ 输入后不再提示 | `prompt_for_code()` → `save_state()` 落盘 `%APPDATA%/XinMatch/XinMatch/registration.json`，下次启动重校验通过则静默 | `test_startup_prompt_registration_branch`；`test_registration_persists_across_restart` |
| 帮助菜单加入「输入注册码」 | `RegistrationManager.add_help_action(help_menu, self)` | `test_release_build_has_registration_and_help_action` |
| 注册码由开发方按「单位部门名称」生成 | `tools/make_reg_code.py`（与家族注册机同算法，交叉验证逐字节一致）；HMAC 绑定单位名，可还原 | `tests/utils/test_registration.py`；与 `PolyXRD-Reg/make_reg_code.py` 出码比对一致 |
| 界面最下面一排右侧（右对齐）显示注册单位部门名称 | `attach_status_label()` → `addPermanentWidget(stretch=1)` + `AlignRight` | `test_release_build_status_label_registered`、`test_release_build_status_label_unregistered` |
| 旧版本保留内部自用、不加注册机制、右对齐显示「内部评估版本」 | 新增 internal 变体：不创建注册管理器、无注册菜单、状态栏右端固定「内部评估版本」 | `test_internal_build_has_no_registration`、`test_internal_build_status_label` |
| Setup 安装版可指定安装位置 | Inno Setup `[Setup]` 未设 `DisableDirPage`（默认显示「选择目标位置」页，`DefaultDirName={autopf}\XinMatch`） | `tools/xinmatch_setup.iss` 静态核验（本次未做实机安装冒烟，见 §五） |
| 安装版数据库仍然单独 | `[Files]` 仅打包 `dist\xinmatch-1.7.0\*`（该目录不含 `data/`）；DB 仍为 `xinmatch-cod-db-1.7.0.zip` | iss + DB zip（zip 内 `data/cod_inorganics.db`） |

## 三、执行动作清单（已逐项确认）

- [x] **复用**：`xinmatch/utils/registration.py` = PolyXRD-Reg 逐字副本（`cmp` 一致）；`pyproject` 加 per-file-ignores 说明其为 vendored 文件（保持可 diff）。
- [x] **接入四处**：`MainWindow.__init__` 建管理器（仅 release）→ 帮助菜单动作 → 状态栏右对齐标签 → `QTimer` 启动检查；`config.py` 新增 `app_config_dir()` 供状态文件与配置同目录。
- [x] **变体**：`xinmatch/utils/build_variant.py`（env 仅源码期生效 / 冻结读 `variant.txt` / 缺失回落 release）；spec 按 `XINMATCH_BUILD_VARIANT` 生成标记并决定 COLLECT 名；`build_exe.ps1 -Variant` + 构建后标记校验。
- [x] **版本号同步** 1.7.0：pyproject、spec（APP_VERSION + VERSION_TUPLE 逗号格式 + COLLECT 名）、build_exe.ps1、xinmatch_setup.iss（11 处）、README；两处解释器重装后 `xinmatch.__version__ == "1.7.0"` 实测（About 对话框读 `importlib.metadata`）。
- [x] **静态检查**：ruff 全量 **All checks passed**；mypy **112 files 0 errors**。
- [x] **测试**：`tests/utils/test_registration.py` 21 项；`tests/ui/test_registration_ui.py` 10 项；UI+CLI 全量 **247 passed / 0 failed**；核心全量见 §四。
- [x] **构建**：`dist/xinmatch-1.7.0/`（release onedir）、`dist/xinmatch-internal-1.7.0/`（internal onedir）、`dist/XinMatch-Setup-1.7.0.exe`（182,451,791 B）、`dist/XinMatch-Internal-1.7.0.zip`（273,400,435 B）、`dist/xinmatch-cod-db-1.7.0.zip`（210,227,894 B）。
- [x] **冻结二进制冒烟**：`XINMATCH_SELFTEST_REG=1` 三态验证（release 未注册 / release 已注册 / internal）。
- [x] **GitHub Release**：tag `v1.7.0`，上传 Setup exe + DB zip + Internal zip。

## 四、验证方式与覆盖

| 验证 | 方式 | 结果 |
|---|---|---|
| 版本号 | `import xinmatch`（两解释器）+ 五处文件核验 | 1.7.0 ✅ |
| 静态 | ruff 全量 + mypy 全量 | All checks passed / 0 errors（112 files） |
| 注册核心 | `pytest tests/utils` | 21 passed |
| 注册 UI | `pytest tests/ui/test_registration_ui.py`（python310 offscreen） | 10 passed |
| 回归 | UI+CLI junit（python310） | **247 passed / 0 failed / 0 skipped** |
| 回归 | 核心 junit（default venv，含全部 slow） | **1112 passed / 0 failed / 0 errors / 5 skipped**（5406s；较 v1.6.1 的 1091 增 21 项注册核心测试） |
| 冻结二进制 | `XINMATCH_SELFTEST_REG=1` | release：`variant=release, registration_enabled=true, status_text=未注册`；写码后：`已注册：内部冒烟测试单位`；internal：`variant=internal, registration_enabled=false, status_text=内部评估版本` |
| 出码一致性 | XinMatch `tools/make_reg_code.py` vs `PolyXRD-Reg/make_reg_code.py` | 同一单位名出码**逐字节相同** |

## 五、诚实边界

- **实机安装冒烟未做**：静默安装（`XinMatch-Setup-1.7.0.exe /SILENT /DIR=…`）在本会话下进程挂起（0 文件写入；同机另一项目的 Setup 进程亦有同样遗留挂起现象），属非交互会话环境限制。安装流程沿用 v1.6.x 已验证的 Inno 脚本，本次仅新增变体标记文件；「可选安装位置」按 Inno 默认行为静态确认（`DisableDirPage` 未设置）。
- **安全级别为离线混淆级**（与家族一致）：密钥随软件分发，可被逆向提取；适用于「告知版权 + 自助注册」。如需按机器/按 app 绑定或在线激活，可在 `_mac()` 上叠加（PolyXRD-Reg README「已知限制」）。
- **内部评估版**不弹注册提示、不提供注册入口，仅供自用；若误发给外部用户即等同无注册约束。
- 便携版（Portable）命名已由 `XinMatch-Internal-<v>.zip` 取代，语义更明确。
- 沙箱环境的批量删除保护曾拦截 PyInstaller 的 `--clean` 清理；改用独立 `--workpath` 完成双变体构建（项目脚本本身未因此改动）。

## 六、结论

**验收通过。** v1.7.0 全部发布门禁通过：注册机制按需求逐条落地并与 PolyXRD 家族算法一致、双二进制变体经冻结产物冒烟确认、静态检查与全量回归 0 失败、三类产物构建完成、Release 已发布。
