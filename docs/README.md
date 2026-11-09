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
| [`RELEASE-NOTES-v3.6.2.md`](RELEASE-NOTES-v3.6.2.md) | **当前版本**（v3.6.2）发布说明：谱图区交互改造（谱图下方参考线分区 / 快捷图标行 / 点击坐标轴切显示） |
| [`RELEASE-NOTES-v3.6.1.md`](RELEASE-NOTES-v3.6.1.md) | v3.6.1 发布说明：图例重复 / 精修向导卡死 / 晶系误判三处报障修复（二进制已构建，未人工验收） |
| [`RELEASE-NOTES-v3.6.0.md`](RELEASE-NOTES-v3.6.0.md) | v3.6.0 发布说明：GUI 11 个菜单动作接通 + 峰位精修 LM 提速 + 周期表重设计 |
| [`RELEASE-NOTES-v3.5.0.md`](RELEASE-NOTES-v3.5.0.md) | v3.5.0 发布说明：元素「必须不含」约束落地 + 版本号单一真相源 |
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
| [`基准报告-物相检索-v3.md`](基准报告-物相检索-v3.md) | **检索基准（v3.2.0 + v3.3.0 §11）**：合成谱 + 13 组真实谱 + IUCr CPD 三套尺子，条目级 / 相位级双口径 Top-1/Top-5/序贯回收、聚簇效果、GUI 折叠口径、预筛名额扫描与根因；§11 记录密集卡反制与强线锚定的实测权衡；§17 新增真实谱**矿物名级**细口径（分母 43→50，多晶型分列 + 固溶体家族）；§18 峰位精修换 LM（预处理 35.2 s→0.35 s）；§19 四库检索成本实测与 `schema v3.1` 不做 的决策依据；§20 `3-1` 类次相召回：名额/排序假说被否定、元素约束把相召回抬到 30/43；§20.7 元素约束产品化（样品元素一行输入）；§21 `prescreen_order` 默认值裁定（保持 `intensity`，细口径 2×2 重测 + 可复现参数）；§22 COD 全库「峰抽取标定」P0 只读调研：症结已随 v3 库链路消失，不重建库；§23 全库候选池稀释：元素上界下两库收敛，正解是 §20.7 的样品元素输入；§24 大库元素约束引导落地 GUI（常显状态 + 非阻塞提示）；§25 元素约束补到 CLI（`--sample-elements` 与 GUI 共用 core 补集语义，真实库禁元素卡 11/20→0/20）；§26 T0.8 FoM P 值深挖结案（权重保持发布值 / 不做运行时全局 LP 修正 / 次相缺失在 recall 层；LP = 洛伦兹-偏振因子；区分「决策结案」与「精确 P 定义反推未完成」）；§27 大库元素约束引导补到 CLI（阈值下沉 core 共用，stderr 非阻塞提示，`--json` stdout 保持纯 JSON）；**§28 IUCr CPD 标准谱接入：第三把尺子**（真实谱 + 官方 weighed wt%，`CPD-1A`…`1H` 1.15 %→94.81 % 八档配比；`tools/bench_iucr.py`，19 样本/48 相；含量—召回曲线；库 78k→532k 给元素时相召回 45/48 一格未动）；**§29 族级口径修复：从「族代表卡」到「族内任一成员」**（BAUXITE 的 Boehmite 被错拼 `Bohmite` 代表卡挡住 → 族级 IUCr 44→45/48、真实谱细 20→22/50；连带推翻 §28.2「双向偏差」的一半）；**§30 序贯单质卡：证据驱动的「不动」决策**（窄规则零增益、宽规则让 6/6 单质标样第 1 轮失效 → 默认保持取榜首）；**§31 择优取向 / 强度形失配的只读调研**（98 相里峰位失配 0 个；29 个强度形失配的主因是**参考弱线被别的相强峰误配**而非择优取向；换 `trim/quantile/median` 估计量是「涨 7 跌 4」的零和交换 → `P_intensity` 不动；顺带查清 Top-1 的一处「退化」是别名表缺项、新榜首就是方解石 R-3c）；**§32 上游配对与 FoM 分量消融**（配对本已一对一、5,721 卡 0 次违反；弱线占配对数 71.6 %/78.3 % 但只贡献 34.4 %/47.8 % 的 `ΣΔ²`，失败卡主因是「参考强线在实测里本来就弱」；五分量消融按尺子分开：`peakpos`/`npeaks` 承重、`intensity` +3 全在 IUCr、`i_scale` 是唯一双尺子同向候选 → 配对与权重都不动）；**§33 `i_scale` 三把尺子 A/B**（`clamp1.0` 三把尺子零变化 ⇒ 无界尾巴是假警报；`i_scale=0` 召回 16/16 · 39→40 · 31→32 但 `fp_above` 两把变差 → 条件②不通过，`i_scale` 降为不推荐；横向结论：单点排序改动都在 ±3 相量级，Top-20 是软边界）；**§34 候选池上界**（2000 卡池里 98 相只缺 1 相且为预筛漏捞，1001–2000 名 = 0；`candidate_limit` 1000→2000 反而 70→69；28 相是排序问题中位名次 52；唯一量级够的旋钮是 Top-N（**§35 口径修正**：GUI 按族合并显示，族级现状 20 行 = 81/98 = 82.7 %，提到 50 行 = 89/98，收益 **+8 相**而非卡级 +14；计算成本零；方案 B = 第 4 个设置项「候选列表族数上限」，必须走设置项否则 UI 测试钳位失效）；**§36 方案 B 落地：候选列表行数上限 `max_display_rows`**（默认 50、YAML 持久化；`_candidate_row_budget()` 换算 fetch = min(1000, max(200, 4×N))，GUI 三处检索显式传 `top_n=fetch`，表格模型层截断（折叠按族/展开按卡），报告改 `visible_results()` 同源，`.xinm` 存档保持全量；CLI/引擎零改动；§35.4 测试钳位实测无影响）；**§37 真值别名表补齐 + §31.5 分类更正**（TRUTH_FINE / BAUXITE 补 Calcite←Calcium Carbonate/CaCO3、Boehmite←Bohmite、Feldspar←Orthoclase 四个晶胞核实的别名；刻意不收 Corundum←eta-Al-oxid —— 96-110-1168 空间群 Fd-3m 是 η-Al₂O₃ 过渡氧化铝，正确拒绝；两把尺子重跑逐项零变化） |
| [`检索基准-v3-诊断-20261104.md`](检索基准-v3-诊断-20261104.md) | 合成谱 vs 库不同源（v2 卡强度 ↔ v3 库 LP 修正）的定位过程 |
| [`数据库重建-v3.0.0-线路图.md`](数据库重建-v3.0.0-线路图.md) | v3 列存库重建链路与验收闸门 |
| [`数据库提速瘦身-v3.0.0-线路图.md`](数据库提速瘦身-v3.0.0-线路图.md) | 列存 / CSR / 分块方案的量化论证 |
| [`COD打包规范_CIF到SQLite.md`](COD打包规范_CIF到SQLite.md) | CIF → SQLite 打包规范（v2 时代历史稿；**Dual-Schema 未采纳**，只留 schema 对比价值） |
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
