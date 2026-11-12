# XinMatch v3.7.0 发布说明

**发布日期**：2026-11-12
**类型**：工具链修复 + 基准尺子恢复（**不改检索算法、不改库格式**）

## 变更

- **合成谱尺子恢复**：用 v3 检索库（`COD-Inorg-20261020.xinDB`）重新生成 13 组合成谱，
  `load_pattern` 13/13 通过；基准产物 `docs/bench/synth-20261112.json`。
  相位级 Top-1 **11/13**、Top-5 **12/13**、相召回 **19/24**；
  条目级（严格 entry_id）Top-1 7/13、Top-5 12/13。
- **生成器路径修复**：`tools/generate_synthetic_patterns.py` 的 `CARD_DB` 由迁移前硬编码
  绝对路径改为仓库相对 `data/cod_inorganics.db`，三个取卡函数在库缺失时返回 `None`
  而不是中断整个生成流程；新增 `tests/test_synthetic_generator_paths.py` 钉住路径不再漂移。
- **验收工具修复**：`tools/verify_binary.py` 改用标准库 `zipfile` 解压便携包，
  不再依赖本机安装 7-Zip。
- 版本三处同步 **3.7.0**（`pyproject.toml` / `xinmatch/__init__.py` /
  `tools/xinmatch_setup.iss`），`xinmatch.spec` 仍从 pyproject 推导、无字面量。

## 兼容性

- `.xinDB` / `.xinm` / `config.yaml` 格式**无变更**，可直接沿用旧库与旧存档。
- 检索算法未改动，候选排序行为与 v3.6.4 一致。

## 资产

| 文件 | 大小 | SHA-256 |
|---|---:|---|
| `XinMatch-Setup-3.7.0.exe` | 255,257,841 B（243.4 MiB） | `ea3b9225bb0f5b2de0e5b9ebafdb6455b0e8705e8ffa8f84b1d76f48aeea6565` |

> 便携 zip（`XinMatch-Portable-3.7.0.zip`，371,700,155 B / 354.5 MiB，
> SHA-256 `6d09f6707037834be40235af5c66a9b44b422aa0b1f6541e2f84fde5735c0b1b`）
> 按项目约定**只构建、不随 Release 发布**。

## 验收

5 轮自动验收全过（`tools/verify_binary.py`，报告 `.scratch/binary_verify_370.json`）：

- 轮 1：SHA-256 清单回读一致（Setup / Portable）。
- 轮 2：便携包解压 3,682 项、冻结 CLI 识别内置库 **78,035 相**（118,640,640 B）、
  `variant=release`、随包 logo 与源码逐字节一致。
- 轮 3：冻结 GUI 三钩子（REG = release / registration_enabled、LIBS 7 条、
  ABOUT PNG 9,117 B）+ 3 次冷启动 exit 0。
- 轮 4：`/VERYSILENT /CURRENTUSER` 静默安装成功，`variant=release`，内置库随装。
- 轮 5：安装后真实谱（5-1，118 峰）检索 → 5 候选，榜首 `96-210-0189`。

按项目红线第 6 条，安装包在 Release 转正前需**人工双击验收**。

## 数据来源（不入 Git）

三把尺子的输入数据位于本机数据目录：

- 合成谱：`D:\test_XRD\synthetic_v3`
- 真实谱：`D:\test_XRD\temp\smz xrd analysis`
- IUCr：`D:\test_XRD\IUCr\txt`

PDF-2（ICDD 版权数据）不在本仓库与 Release 中。
