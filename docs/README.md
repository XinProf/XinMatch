# docs 索引

本目录是 XinMatch 的文档库。**新增文档请先在这里登记一行**，避免文档散落
（此前根目录同时存在 `ROADMAP.md` / `ROADMAP_v2` / `ROADMAP_v3`、
`FUNCTION_MAP.md` / `FUNCTION_MAP_v43` 等 8 个 md）。

## 入口

| 文档 | 内容 |
|---|---|
| [`../README.md`](../README.md) | 项目介绍、安装、快速开始 |
| [`STATUS.md`](STATUS.md) | 路线图任务完成状态（按 Phase / T 编号） |
| [`../ROADMAP_v3.md`](../ROADMAP_v3.md) | **当前**路线图（v1/v2 为历史版本） |
| [`../FUNCTION_MAP_v43.md`](../FUNCTION_MAP_v43.md) | **当前**功能映射（对齐参考软件 4.3） |

## 规范与工程化

| 文档 | 内容 |
|---|---|
| [`CONVENTIONS.md`](CONVENTIONS.md) | 跨平台 / 编码 / 数值 / 依赖规范 |
| [`TERMINOLOGY.md`](TERMINOLOGY.md) | 术语映射表（参考软件 ↔ 本软件 ↔ IUCr/ICDD） |
| [`mypy_baseline.md`](mypy_baseline.md) | 类型检查基线与豁免历史 |
| [`PACKAGING.md`](PACKAGING.md) | PyInstaller 打包与交付 |
| [`打包交付说明-v1.0.0.md`](打包交付说明-v1.0.0.md) | v1.0.0 交付清单 |
| [`pytest_full_run_hang_rootcause.md`](pytest_full_run_hang_rootcause.md) | 全量测试耗时根因与分块运行方案 |

## 算法与数据

| 文档 | 内容 |
|---|---|
| [`../FOM_MODEL.md`](../FOM_MODEL.md) | FoM / P 值模型 |
| [`fpfm_mechanism.md`](fpfm_mechanism.md) | FPFM 全谱拟合机制与参数决策 |
| [`fpfm_research_notes.md`](fpfm_research_notes.md) | FPFM 研究笔记 |
| [`COD打包规范_CIF到SQLite.md`](COD打包规范_CIF到SQLite.md) | CIF → SQLite 打包规范 |
| [`COD多库挂载说明.md`](COD多库挂载说明.md) | 多参考库挂载机制 |
| [`COD全库优选去重库治理.md`](COD全库优选去重库治理.md) | 优选去重库的构造与治理 |
| [`sample_expansion_20261011.md`](sample_expansion_20261011.md) | 样品集扩充 |
| [`样品集扩充计划-T0.3-T0.4.md`](样品集扩充计划-T0.3-T0.4.md) | TiO₂ 标定系列计划 |

## 评审与交接

| 文档 | 内容 |
|---|---|
| [`CODE_REVIEW-20261018.md`](CODE_REVIEW-20261018.md) | 全量代码评审 + 分批改进方案（含实施状态） |
| [`HANDOVER.md`](HANDOVER.md) | 交接总览 |
| [`HANDOVER-20261012.md`](HANDOVER-20261012.md) / [`HANDOVER-20261013.md`](HANDOVER-20261013.md) | 历次交接记录 |

## 验收记录

`ACCEPTANCE-*.md` 为各任务/版本的验收证据（命令、数字、commit hash）；
`l3_golden_*.json` / `l3_*.html` / `l3_traceup_report.md` 为 L3 金标准回归产物；
[`TiO2-定量对照-20261014.md`](TiO2-定量对照-20261014.md) 为参考软件定量对照。
