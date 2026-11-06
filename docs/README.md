# docs 索引

本目录是 XinMatch 的文档库。**新增文档请先在这里登记一行**，避免文档散落
（此前根目录同时存在 `ROADMAP.md` / `ROADMAP_v2` / `ROADMAP_v3`、
`FUNCTION_MAP.md` / `FUNCTION_MAP_v43` 等 8 个 md）。

## 入口

| 文档 | 内容 |
|---|---|
| [`../README.md`](../README.md) | 项目介绍、安装、快速开始 |
| [`STATUS.md`](STATUS.md) | 路线图任务完成状态（按 Phase / T 编号，含每个版本的发布记录） |
| [`../ROADMAP_v3.md`](../ROADMAP_v3.md) | **当前**路线图（v1/v2 为历史版本） |
| [`../FUNCTION_MAP_v43.md`](../FUNCTION_MAP_v43.md) | **当前**功能映射（对齐参考软件 4.3） |
| [`RELEASE-NOTES-v3.5.0.md`](RELEASE-NOTES-v3.5.0.md) | **当前版本**（v3.5.0）发布说明：元素「必须不含」约束落地 + 版本号单一真相源 |
| [`RELEASE-NOTES-v3.4.0.md`](RELEASE-NOTES-v3.4.0.md) | v3.4.0 发布说明（导出物相分析 `.xinm`） |
| [`RELEASE-NOTES-v3.3.0.md`](RELEASE-NOTES-v3.3.0.md) | v3.3.0 发布说明：少线相 ★ 强线锚定标记 |
| [`RELEASE-NOTES-v3.2.0.md`](RELEASE-NOTES-v3.2.0.md) | v3.2.0 发布说明（相位级身份 + 候选折叠） |
| [`RELEASE-NOTES-v3.1.0.md`](RELEASE-NOTES-v3.1.0.md) | v3.1.0 发布说明（序贯物相鉴定） |

## 规范与工程化

| 文档 | 内容 |
|---|---|
| [`CONVENTIONS.md`](CONVENTIONS.md) | 跨平台 / 编码 / 数值 / 依赖规范 |
| [`TERMINOLOGY.md`](TERMINOLOGY.md) | 术语映射表（参考软件 ↔ 本软件 ↔ IUCr/ICDD） |
| [`mypy_baseline.md`](mypy_baseline.md) | 类型检查基线与豁免历史 |
| [`PACKAGING.md`](PACKAGING.md) | PyInstaller 打包与交付 |
| [`../tools/verify_binary.py`](../tools/verify_binary.py) | **发布产物 5 轮二进制稳健性验收**（哈希 / 便携启动 / 冻结 GUI / 静默安装 / 安装后检索，产出 JSON 报告） |
| [`打包交付说明-v1.0.0.md`](打包交付说明-v1.0.0.md) | v1.0.0 交付清单（历史） |
| [`pytest_full_run_hang_rootcause.md`](pytest_full_run_hang_rootcause.md) | 全量测试耗时根因与分块运行方案 |

## 算法与数据

| 文档 | 内容 |
|---|---|
| [`../FOM_MODEL.md`](../FOM_MODEL.md) | FoM / P 值模型（五分量、3640 条候选 NNLS 拟合的发布权重、留一交叉验证）。**注意**：它解出的是「权重如何组合」，不是每个 `P_xxx` 的精确算法；T0.8 已以「证据驱动的不动决策」结案，见基准报告 §26 |
| [`fpfm_mechanism.md`](fpfm_mechanism.md) | FPFM 全谱拟合机制与参数决策 |
| [`fpfm_research_notes.md`](fpfm_research_notes.md) | FPFM 研究笔记 |
| [`峰口径冻结-v3.0.0.md`](峰口径冻结-v3.0.0.md) | v3 `.xinDB` 峰口径（波长 / d 范围 / DW / norm-1000）的冻结依据 |
| [`基准报告-物相检索-v3.md`](基准报告-物相检索-v3.md) | **检索基准（v3.2.0 + v3.3.0 §11）**：合成谱 + 13 组真实谱两套尺子，条目级 / 相位级双口径 Top-1/Top-5/序贯回收、聚簇效果、GUI 折叠口径、预筛名额扫描与根因；§11 记录密集卡反制与强线锚定的实测权衡；§17 新增真实谱**矿物名级**细口径（分母 43→50，多晶型分列 + 固溶体家族）；§18 峰位精修换 LM（预处理 35.2 s→0.35 s）；§19 四库检索成本实测与 `schema v3.1` 不做 的决策依据；§20 `3-1` 类次相召回：名额/排序假说被否定、元素约束把相召回抬到 30/43；§20.7 元素约束产品化（样品元素一行输入）；§21 `prescreen_order` 默认值裁定（保持 `intensity`，细口径 2×2 重测 + 可复现参数）；§22 COD 全库「峰抽取标定」P0 只读调研：症结已随 v3 库链路消失，不重建库；§23 全库候选池稀释：元素上界下两库收敛，正解是 §20.7 的样品元素输入；§24 大库元素约束引导落地 GUI（常显状态 + 非阻塞提示）；§25 元素约束补到 CLI（`--sample-elements` 与 GUI 共用 core 补集语义，真实库禁元素卡 11/20→0/20）；§26 T0.8 FoM P 值深挖结案（权重保持发布值 / 不做运行时全局 LP 修正 / 次相缺失在 recall 层；LP = 洛伦兹-偏振因子；区分「决策结案」与「精确 P 定义反推未完成」） |
| [`检索基准-v3-诊断-20261104.md`](检索基准-v3-诊断-20261104.md) | 合成谱 vs 库不同源（v2 卡强度 ↔ v3 库 LP 修正）的定位过程 |
| [`数据库重建-v3.0.0-线路图.md`](数据库重建-v3.0.0-线路图.md) | v3 列存库重建链路与验收闸门 |
| [`数据库提速瘦身-v3.0.0-线路图.md`](数据库提速瘦身-v3.0.0-线路图.md) | 列存 / CSR / 分块方案的量化论证 |
| [`COD打包规范_CIF到SQLite.md`](COD打包规范_CIF到SQLite.md) | CIF → SQLite 打包规范（v2 时代，历史参考） |
| [`../XinMatch-DataBase/docs/构建与验收手册.md`](../XinMatch-DataBase/docs/构建与验收手册.md) | **参考库构建与验收手册**（姊妹仓库：六个库 COD/PCOD/TCOD × Inorg/Full 的构建、校验、验收；CIF 源在 `../sync-COD`） |
| [`COD多库挂载说明.md`](COD多库挂载说明.md) | 多参考库挂载机制（v2 时代，挂载概念仍适用） |
| [`COD全库优选去重库治理.md`](COD全库优选去重库治理.md) | 优选去重库的构造与治理（含 COD 重复相分析） |
| [`sample_expansion_20261011.md`](sample_expansion_20261011.md) | 样品集扩充 |
| [`样品集扩充计划-T0.3-T0.4.md`](样品集扩充计划-T0.3-T0.4.md) | TiO₂ 标定系列计划 |

## 评审与交接

| 文档 | 内容 |
|---|---|
| [`CODE-REVIEW-v3.0.0-20261024.md`](CODE-REVIEW-v3.0.0-20261024.md) | **当前**：v3.0.0 全面代码评估 + 缺陷修复 + 三库验收结论 + 下一步建议 |
| [`v3.0.0-验收报告.md`](v3.0.0-验收报告.md) | v3.0.0 实现过程与建库/峰引擎/检索验收（2026-10-23） |
| [`CODE_REVIEW-20261018.md`](CODE_REVIEW-20261018.md) | v2.0.0 前全量代码评审 + 分批改进方案（含实施状态） |
| [`HANDOVER-20261106.md`](HANDOVER-20261106.md) | **当前交接记录**（2026-11-06）：目标 / 设计 / 拆分原则 / 验收方法 / 进展 / 坑与经验 / 下一步 / 备忘 |
| [`HANDOVER.md`](HANDOVER.md) | 交接总览（2026-10-08，架构与任务拆分标准仍适用） |
| [`HANDOVER-20261012.md`](HANDOVER-20261012.md) / [`HANDOVER-20261013.md`](HANDOVER-20261013.md) | 历次交接记录 |

## 验收记录

`ACCEPTANCE-*.md` 为各任务/版本的验收证据（命令、数字、commit hash）。

| 文档 | 内容 |
|---|---|
| [`../XinMatch-DataBase/docs/ACCEPTANCE-20261101-rebuild.md`](../../XinMatch-DataBase/docs/ACCEPTANCE-20261101-rebuild.md) | **2026-11-01/04 参考库重建与 Full 库验收**（COD/TCOD/PCOD-Inorg + TCOD/COD-Full：0 FAIL、坏相清零、与 Inorg 公共相逐字节一致；PCOD-Full 等价跳过） |
| [`ACCEPTANCE-3COD-20261024.md`](ACCEPTANCE-3COD-20261024.md) | **三个无机物库 `.xinDB` 的独立复验**（COD / PCOD / TCOD：结构、来源、元素索引、峰载荷、自召回） |
| [`ACCEPTANCE-3COD-20261020.md`](ACCEPTANCE-3COD-20261020.md) | 3COD 建库当次验收（v2.0.0 时期） |
| [`ACCEPTANCE-v3.0.0-20261023.md`](ACCEPTANCE-v3.0.0-20261023.md) | v3.0.0 发布验收（`.xinDB` 收口 + 内置默认库） |
| [`ACCEPTANCE-v2.0.0-20261020.md`](ACCEPTANCE-v2.0.0-20261020.md) | v2.0.0 发布验收（PolyXRD `.sqlite` 兼容） |
| [`TiO2-定量对照-20261014.md`](TiO2-定量对照-20261014.md) | 参考软件定量对照 |

`l3_golden_*.json` / `l3_*.html` / `l3_traceup_report.md` 为 L3 金标准回归产物；
其余 `ACCEPTANCE-*.md` 为更早任务的验收证据。
