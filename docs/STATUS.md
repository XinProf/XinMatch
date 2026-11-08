# Implementation status

Tracks progress against [ROADMAP_v3.md](../ROADMAP_v3.md).

Legend: ⬜ not started · 🟡 in progress · ✅ done

## Phase 0 — Knowledge base & golden baseline

| ID | Task | Status |
|----|------|--------|
| T0.1 | Extract official doc library (169 topics) | ✅ |
| T0.2 | Re-extract against latest 参考软件, diff versions | ✅ (2026-10-14：本机 Match4.qch=4.3 Build 360；重建 tools/extract_help.py 提取 170 主题；tools/diff_help_versions.py 双层 diff → docs/version_diff_4.2.329_vs_latest.md：无新增实质功能主题/无删除，实质变更 38 篇均 ≤4.6% 且主体为旧提取丢失公式/斜体标记，功能面一致) |
| T0.3 | Build standard sample set (20–30 samples) | ✅ (2026-10-14：TiO₂ 金红石-锐钛矿标定系列接入（`D:\Project\XRD\XRData\TiO2\`，13 样品：6 标定 5–50% + 3 验证 8/18/36% + 4% 重复性×2 + 纯相金红石/锐钛矿，标称 wt% 全知，GB/T 30893-2014 方法学）；含既有 13 组合成谱 + 13 组精选真实谱；样品索引 `tests/fixtures/SAMPLE_INDEX.md` §3b；回归测试 `tests/quant/test_tio2_intensity_ratio.py` 4 项（数据缺失自动 skip）) |
| T0.4 | Run 参考软件 baseline on the sample set | ✅ (2026-10-14：TiO₂ 系列 XinMatch 定量端到端验证——标定 K=1.3748（岛津参考 1.2234）、验证 8/18/36%→7.98/17.73/35.44%（绝对误差 −0.25/−1.5/−1.6%，优于参考强度比值法 −7.4/−8.0/−7.6%）、全谱/局部谱两路径差 ≤0.2%、4% 重复性 0.0008（GB/T 限值 0.18%）、18% 全谱检索 top-8 全 TiO₂；对照 `docs/TiO2-定量对照-20261014.md` + 验收 `docs/ACCEPTANCE-T0.3-T0.4-20261014.md`) |
| T0.5 | Terminology mapping table | ✅ (2026-10-14：docs/TERMINOLOGY.md 九域三层映射：参考软件 4.3.360 IndexTable 3,514 词/166 主题 ↔ XinMatch UI 73 控件文本+8 CLI ↔ IUCr/ICDD 标准术语；高频词全覆盖，状态 [x]/[规划]/[—] 标注) |
| T0.6 | Project skeleton + CI (pytest, ruff, mypy) | ✅ (2026-10-10：mypy 配置落地（pyproject [tool.mypy]，files=xinmatch + search/refine 基线豁免），26 源文件纯类型层修复，**109 错误 → 0（81 源文件）**，`python -m mypy` 与 `mypy xinmatch` 均 Success；豁免清单见 docs/mypy_baseline.md。pytest/ruff 此前已就绪) |
| T0.7 | Cross-platform conventions | ✅ |
| T0.8 | Reverse-engineer FoM P-value definitions from baseline CSV | ✅ (2026-11-06 文档收尾结案：以**证据驱动的不动决策**结案 —— 权重保持发布值、不做运行时全局 LP 修正、次相缺失归 recall 层；精确 P 定义反推需多组参考软件 CSV，列为外部依赖而非阻塞。结论正文见下方 §T0.8 与 `docs/基准报告-物相检索-v3.md` §26) |

## Phase 1 — Core data models (`core/model/`)

| ID | Task | Status |
|----|------|--------|
| T1.1 | Pattern dataclass | ✅ |
| T1.2 | Peak dataclass | ✅ |
| T1.3 | Entry (reference DB entry) | ✅ |
| T1.4 | Phase (selected phase) | ✅ |
| T1.5 | Restraints | ✅ |
| T1.6 | Project (with undo/redo) | ✅ |

## Phase 2 — Diffraction data I/O (`core/io/`)

| ID | Task | Status |
|----|------|--------|
| T2.1 | Format auto-detection | ✅ |
| T2.2 | Free formats (6) | ✅ |
| T2.3 | PANalytical (.rd/.udf/.udi) | ✅ |
| T2.4 | Bruker (.uxd/.brml; .raw v1/v3) | ✅ (`.uxd/.brml` 此前完成；**2026-10-14 补齐 RAW v3/v4**：`core/io/bruker_raw.py` `read_bruker_raw_v3`（RAW1.01 多块容器，真实 data035 WC 残余应力谱 10 块验证、文件完全消费）+ `read_bruker_raw_v4`（RAW4.00 段式容器，含 seg30 光源段 Ka/anode 解析）；detect 新增 FMT_RAW3/RAW4 + `load_pattern` 分发；**v1（magic `RAW `）结论：无公开格式文档 + GSAS-II 官方拒绝支持 → 不可实现**（与 GSAS-II 同结论，验收文档声明）；12 新测试 + tests/io 100 全绿；验收 `docs/ACCEPTANCE-T2.4-20261014.md`） |
| T2.8 | Exporters (ASCII profile + peak list) | ✅ |
| T2.9 | Unified `load_pattern()` entry | ✅ |
| T2.10 | 全谱图格式补齐（对齐 PolyXRD 可解析全集，2026-10-10） | ✅ (`core/io/xrdml.py` XRDML、`mdi.py` MDI（丢首点校正）、`shimadzu_txt.py` 岛津文本导出、`vendor_misc.py` RAS/CPI/PLV/ESG/GDF；detect 修复二进制魔数限定 .raw 扩展名，文本型 .raw 保留文本签名路径；22 格式全 dispatch，真实 4-1.mdi 峰位与 .dat 对齐 <0.02°) |

## Phase 3 — Raw data preprocessing (`core/preprocess/`)

| ID | Task | Status |
|----|------|--------|
| T3.1 | Smoothing (MA + Savitzky-Golay) | ✅ |
| T3.2 | Background (SNIP + polynomial + manual) | ✅ |
| T3.3 | Background subtraction | ✅ |
| T3.4 | Kα2 stripping (Rachinger) | ✅ |
| T3.5 | Zero point correction | ✅ |
| T3.8 | Auto processing pipeline | ✅ |

## Phase 4 — Peak search & profile fitting (`core/peak/`)

| ID | Task | Status |
|----|------|--------|
| T4.1 | Peak search (derivative method) | ✅ |
| T4.2 | Peak position refinement | ✅ |
| T4.3 | Peak shape functions (4) | ✅ |
| T4.4 | Profile fitting (multi-peak LSQ) | ✅ |
| T4.6 | Peak data → profile | ✅ |

## Phase 5 — Reference database (`core/db/`)

| ID | Task | Status |
|----|------|--------|
| T5.1 | COD → SQLite builder (insert logic) | ✅ |
| T5.2 | Schema (4 tables + 9 indexes) | ✅ |
| T5.3 | Inverted index (elements + d) | ✅ |
| T5.4 | d-value search (LaB6 → top-3) | ✅ |
| T5.5 | Multi-field combined search | ✅ |
| T5.6 | User database CRUD | ✅ |
| T5.7 | Database manager (multi-db) | ✅ |

## Phase 6 — Search-Match (`core/search/`)

| ID | Task | Status |
|----|------|--------|
| T6.1 | Peak correlation (greedy + Hungarian) | ✅ |
| T6.2 | FoM criteria (5 components, weights from FOM_MODEL.md) | ✅ |
| T6.3 | Weighted sum + sort → CandidateResult list | ✅ |
| T6.4 | Full-pattern search-match main loop (search_match) | ✅ |
| T6.5 | Marked-peak search (search_marked_peaks wrapper) | ✅ |
| T6.7 | CandidateList model (sort/filter/select/unassociated) | ✅ |
| T6.0 | Hanawalt/Fink coarse pre-filter | ✅ |
| T6.6 | PFSM (full-spectrum fitting FoM) | ✅ |
| T6.8 | Auto FoM recompute on phase selection | ✅ |
| T6.9 | L3 acceptance (Top-10 vs 参考软件 baseline) | ✅ (real COD db 71,199 entries: **13/13 samples top1 = ground-truth phase**; vs 参考软件 CSV: Top-5 overlap 67.7% ≥ 60% PASS, Top-1 agreement 69.2% (9/13) < 80% FAIL — 4 mismatches are multi-phase 5-x samples where both sides pick a true phase; FoM weight sweep (4 combos) all stop at 9/13, not reproducible by linear weights; see docs/l3_golden_acceptance_cod.html) |
| T6.9c | **L3 追平（2026-10-10）** | ✅ Top-1 一致率 **9/13 → 11/13（84.6% ≥ 80% PASS）**、Top-5 重叠 **67.7% → 83.1% PASS**。两处 FoM 算法修正（`core/search/fom_criteria.py`）：① 强度归一化改用「匹配峰最大值」（消除多相次相 I_scale 尺度效应重复惩罚，翻转 5-2/5-2b Hematite）；② sigma_pos 0.1→0.15（修复 4-1 胶着回归，CaF₂ 曾以 0.001 压 ZnO）。终态仅剩 5-1（参考 Magnesite 96-900-0381 快照内容错位为 Teruggite）与 5-3（参考 Kaolinite 96-900-9231 快照缺失）两处不匹配；**13/13 top1 均为真相相**；诊断确认库中这些相正常条目均在、纯排序问题，FPFM 权重模拟崩坏彻底排除权重路线、未补库。详见 docs/l3_traceup_report.md |
| T6.9b | COD 全库检索质量核验（2026-10-10） | ✅ (用 `data/cod_full.db` 112,734 条目重跑同基线：Top-1 一致率反而降至 1/13——全库含大量重复/低质量卡片稀释排序。**结论：默认检索保持精选无机库 71,199 正确，全库仅作覆盖性挂载**；L3 追平不靠换库，方向仍是逆向参考软件 FoM 内部逻辑或补条目) |
| T6.10 | Weight tuning (grid/Bayesian) | ✅ (R²=0.9971 ≥ 0.9913 baseline; keep published weights) |
| T6.11 | **序贯物相鉴定（v3.1.0）**：确认一相 → 扣除其贡献 → 剩余峰再检索 → 再确认 | ✅ (`core/search/sequential.py`：`SequentialIdentifier` 以原始峰列表为基准、每次变更整体重建（相关峰 / 计数域比例因子 / 逐峰残差 / 已解释掩码），`search_residual()` 在剩余峰上跑同一 FoM 引擎并把 pairs 映射回原始峰索引、同时剔除已确认条目；GUI 候选列表双击/回车/「确认该相」→ 匹配列表 + 峰列表关联标记 + 谱图参考线条，双击匹配列表回滚；验收 `docs/序贯物相鉴定-v3.1.0.md`，测试 `tests/search/test_sequential.py` + `tests/ui/test_sequential_ui.py`) |
| T6.12 | **相位级身份 + 候选聚簇（v3.2.0）**：同相异卡合并、双口径基准 | ✅ (`core/search/phase_key.py`：元素集 + 晶胞（轴长 ±1% / 角 ±1.5°）+ 空间群判同一物相，**有晶胞以晶胞为准**、缺晶胞才退回**化学式比值**（容差 0.25，Z 无关），故占位度变体 `Al1.499`/`Al2` 合并且多晶型不误合；`group_same_phase()` 贪心按排名分组、族代表即族内最优卡。GUI `CandidateListTable` 默认折叠（“变体”列显示 `N 条`、tooltip 逐卡列 entry_id + 晶胞、右键「展开同相变体」/「合并同相变体」切换）；`tools/bench_pattern_set.py` 给出条目级 + 相位级双口径；`tools/generate_synthetic_patterns.py --peak-source v3` 用同一库取强度重建合成谱（旧谱尺子与库不同源）。结果见 `docs/基准报告-物相检索-v3.md`：新谱相位级 Top-1 11/13、Top-5 12/13、序贯完整回收 10/13、相召回 19/24（条目级 7/13 / 11/13 / 2/13 / 9/24，两口径之差全部来自库内同相多卡）；测试 `tests/search/test_phase_key.py` + `tests/ui/test_tables.py`) |
| T6.13 | **第二组基准：13 组真实测量谱（v3.2.0）** | ✅ (`tools/bench_real_samples.py`：L3 金标准 13 组实测谱 + `auto_process` 全链路 + 生产库，真值以化学式比值承载（固溶体 1-2 / 黑云母 / 角闪石显式排除，不进分母）。COD-Inorg 结果：整谱 Top-1 命中真相相 **10/12**、Top-5 12/12、相召回 Top-20 卡 **24/43** / 折叠后族级 **27/43**、序贯完整回收 5/12；`5-3` 单样品验证折叠的实质增益（1/5 → 5/5，针铁矿洪水）。报告见 `docs/基准报告-物相检索-v3.md` §9) |
| T6.14 | **预筛名额双路分配 + `fetch_peaks` 参数上限修复（v3.2.0）** | ✅ 根因：`XinDBReader.prescreen` 按 `主峰命中 → 强度加权命中 → 命中数` 排序取前 N，隐含假设"真相相最强线在实测谱里也不弱"，对次相不成立 —— 3-1 的 Al₂O₃/CaF₂ 在 800 名额下不入榜（`candidate_limit=8000` 时 rank 197），`n_hits=75970/78035` 说明 800 名额在做全部判别。**修复**：`DEFAULT_RANK_LIMIT` 800→1000，新增 `diversify_slots`（默认 20%，传 0 恢复旧行为），排序切成 80% 沿用原三级判据 + 20% 只按 `强度加权命中 → 命中数`，次序为 legacy 段在前、diverse 段在后。5 配置扫描（合成 + 真实两套基准）后选定 1000/200：合成相位级 T1 10→**11**/13、T5 11→**12**/13、序贯 9→**10**/13、相召回 18→**19**/24；真实谱 T5 11→**12**/12、卡级 20→**24**/43、族级 24→**27**/43、序贯 4→**5**/12。代价：COD 0.37→0.41 s（+11%）、PCOD 1.50→1.89 s（+26%）。**顺带修复**：`fetch_peaks` 单条 `IN (…)` 超 SQLite 参数上限被 `except sqlite3.Error` 吞成空结果（`candidate_limit=40000` 返回 0 候选），改为 900 一批，回归 `tests/db/test_reader_v3_fetch.py`；名额分配回归 `tests/db/test_prescreen_diversity.py`。详见 `docs/基准报告-物相检索-v3.md` §10 |
| T6.15 | **任务 #7「序贯密集卡反制」调查（3.3.0，负结果）** | ✅ 已定性、**不改 FoM 权重**：在自洽 v3 基准（合成 `synthetic_v3` 序贯 10/13·19/24、真实 5/12·23/43，均与 §2/§9.2 吻合）上，穷举 4 类局部重排——`npeaks→实测侧强度覆盖`（9/8）、混合 β（9）、位置门控（8~9）、近平局 ε（8~10）、**整族排除**（合成/真实均**与基线逐项相同**）、`ncorr→参考侧强度覆盖`（9）——**无一超过基线 10/13**。诊断实测根因：①真相相靠「少而精」（synth_01 ZnO rank22 覆盖 0.861 但 int 0.020），假密集卡靠「多而杂」，单一覆盖指标会同时抬高另一类假卡；②synth_07 KCl、synth_10 Fe 是**少线相、根本不在候选池**（召回问题）；③synth_10 真 Fe₃O₄ 与 Si 掺杂尖晶石五项**逐位相同**（本征近平局）。**结论**：局部强度加权覆盖不是密集卡问题的解，硬上会伤合成尺子，违反「Top-1/Top-5 不退化」；保持 3.2.0 冻结权重口径。详见 `docs/基准报告-物相检索-v3.md` §11.1–§11.4 |
| T6.16 | **强线锚定：少线相标记（v3.3.0）** | ✅ 已落地、**默认只标记不重排**（用户裁定）。机制：最强参考线命中 ≥0.30×最强残差峰 + `P(2θ)`≥0.98 + 匹配对≥2 + `P(ncorr)`≥0.50 + 参考反射数≤20（护栏直接排掉 40~150 线的密集卡）。实现 `AnchorPolicy` / `_anchor_ok()` / `_anchor_flags()` / `_promote_anchored()`，结果进 `ResidualSearchResult.anchored_ids`；GUI 候选表第一列色带显示 `★` + tooltip + 状态栏提示，排序不动。**实测权衡**：合成序贯 10/13→**11/13**、相召回 19/24→**21/24**（synth_07 NaCl rank10 被抬上来）；真实 `3-2` 第 2 轮把 `Bi1.284O2.988Y0.684`（pos **0.984**，比真 CaF₂ 的 0.928 还准）抬到首位，误确认后残差被污染，CaF₂ 5 轮也找不回 → 真实序贯完整 5/12→4/12（r5：6/12→5/12）、序贯内相召回 23/43→22/43。单线/双线/双线+比值三种变体八项指标完全相同，说明判别力不足而非阈值问题。**根因**：合成谱带精确参考强度，真实谱没有 → 合成尺子系统性高估此规则。默认口径与 3.2.0 逐项相同（真实 T1 10/12·T5 12/12·序贯 5/12·卡召回 24/43·族级 27/43）。开关 `search_residual(promote_anchored=True)` 留作离线实验；下一步需样品侧元素合理性（XRF）才能挡掉此类假卡。详见 §11.5，测试 `tests/search/test_sequential.py` + `tests/ui/test_tables.py` + `tests/ui/test_sequential_ui.py` |

## Phase 7 — Restraints application (`core/search/`)

| ID | Task | Status |
|----|------|--------|
| T7 | Apply restraints to DB search + candidate pruning + scoring | ✅ |

## Phase 8 — Quantitative analysis (`core/quant/`)

| ID | Task | Status |
|----|------|--------|
| T8.1 | RIR quantitative (adiabatic + reference-ratio) | ✅ |
| T8.2 | Internal standard method | ✅ (IUCr CPD-1c CaF₂ err < 0.12 wt%) |
| T8.3 | Rietveld quantitative (depends on Phase 10) | ✅ (`core/quant/rietveld_quant.py` 委托 GSAS-II 闭环：build→run→parse→wt%。**本轮补强（2026-10-09）**：COD 标准 CIF（COD **1000017** Al₂O₃ / **2300112** ZnO / **1000054** Brucite，fixtures 新增 `*_cod.cif`）替换手写 CIF；分阶段 March-Dollase 择优取向（移到 scale/背景/晶胞/峰形/原子收敛之后，避免 r 负值致 MD 积分 NaN）；修复 3 个真实 bug——① GSAS-II 子进程继承父进程 PYTHONPATH 污染致 pyspg/pypowder 加载失败（剖面静默关闭，Rwp 假 80%），② 二进制 fortran DLL 子目录未注册（`os.add_dll_directory`），③ 旧 `{'PO': True}` 是 GSAS-II `set_HAP_refinements` 无效键被静默忽略；仪器默认改为标准 Cu Kα 1.54056/1.54439 Å + 合理 Caglioti 起点（生产应用实测 .prm）。**结果**：主相 ZnO（~94 wt%）误差从旧偏 7–12 wt% 降至 **<1.3 wt%**（CPD-1c：ZnO −1.05 / Al₂O₃ +1.02 / CaF₂ +0.04；3-1：−1.28 / +1.27 / +0.02；4-1：ZnO +0.39 / Al₂O₃ +2.78 / CaF₂ +1.14；Rwp 16.9/23.0/17.5%）。**诚实残余**：4-1 Brucite（最大相 36.26 wt%）仍偏 **−4.31 wt%**——对照实验（无 PO −4.49% vs 有 PO −4.31%）证明单参数 MD [001] 几乎不动 r，归因层状织构需球谐模型 + 轻/重相微吸收衬度 + 无实测仪器 .prm；测试对 ZnO/Al₂O₃/CaF₂ 门 <3 wt%、Brucite 门 <6 wt% 并注明残余，未放宽断言。含 3 个新 `@pytest.mark.slow` 端到端用例) |
| T8.4 | DOC amorphous content | ✅ (test_xrd 3-2 glass err 4.81 wt% < 7% threshold) |

## Phase 9 — Indexing (`core/index/`)

| ID | Task | Status |
|----|------|--------|
| T9.1 | d-spacing formulas for 7 crystal systems | ✅ |
| T9.2 | Treor (trial-and-error) — cubic full, others simplified | ✅ |
| T9.3 | Dicvol (dichotomy) — cubic full, others simplified | ✅ |
| T9.4 | Solution ranking + dedup + Smith-Snyder/de Wolff FOM | ✅ |

## Phase 11 — Microstructure (`core/micro/`)

| ID | Task | Status |
|----|------|--------|
| T11.1 | Scherrer crystallite size (+ Williamson-Hall) | ✅ |
| T11.2 | Microstrain (Williamson-Hall full) | ✅ (synthetic D/ε recovery < 10% err) |
| T11.3 | DOC (if not in T8.4) | ✅ (covered by T8.4) |

## Phase 12 — Report & export (`core/report/`)

| ID | Task | Status |
|----|------|--------|
| T12.1 | Report data model (SampleInfo / CandidateEntry / Report) | ✅ |
| T12.2 | Renderers: HTML / text / markdown / PDF (weasyprint lazy) | ✅ |
| T12.3 | Figure export: PNG / SVG (matplotlib Agg) | ✅ |

## Phase 10 — Refinement (`core/refine/`)

> **架构决策（2026-10-08）**：XinMatch **不自研精修算法**（Le Bail / Rietveld / 残差 / 峰形模型 / 结构因子 / 策略化精修）。
> 生产路径是把物相鉴定结果 + 对应 CIF + 原始谱图交给 **GSAS-II**（通过 `GSASIIscriptable` API）完成精修，
> XinMatch 只负责：① 构造 GSAS-II 项目 / ② 暴露参数给 GUI / ③ 解析 GSAS-II 输出（Rwp、cif、prf）。
> GUI 参考 **MAUD** 的向导式交互（比 GSAS-II 原生 GUI 直观）。
>
> 因此 T10.1–T10.5、T10.7 的自研实现仅作**参考/交叉验证**用，不进生产路径；
> **T10.6b（GSAS-II 适配层）是精修唯一的生产集成点**。
> （参考软件 集成 FullProf，XinMatch 选择 GSAS-II，因为它是 Python 编写可嵌入式集成。）

| ID | Task | Status | 说明 |
|----|------|--------|------|
| T10.1 | Peak model (pseudo-Voigt + asymmetry + Caglioti U/V/W) | ✅ (reference only) | 自研，仅用于交叉验证，**非生产路径** |
| T10.2 | Structure factor (scattering factors, DW, LP, multiplicity) | ✅ (reference only) | 同上 |
| T10.3 | Le Bail decomposition | ✅ (reference only) | 同上 |
| T10.4 | Rietveld refinement (scale + cell + peak_width + zero) | ✅ (reference only) | 同上 |
| T10.5 | Residuals (Rp/Rwp/R_exp/χ²/GoF) | ✅ (reference only) | 同上；生产上由 GSAS-II 输出 |
| T10.6 | FullProf adapter | ❌ not doing | 参考软件 用 FullProf，XinMatch 选 GSAS-II |
| T10.6b | **GSAS-II adapter (production path)** | ✅ | `gsas2_adapter.py`：Protocol + Local fallback + `.gss` 解析 + lazy import |
| T10.7 | Strategy turn-on (Parameter Turn-On) | ✅ (reference only) | 自研策略化；生产上由 GSAS-II 的 refine controls 承担 |
| T10.8 | GSAS-II 项目构造器（CIF + Pattern → GSAS-II .gpx 项目） | ✅ | `gsas2_project.py`：driver+清单自包含，Gsas2NotAvailableError 优雅降级；cpd-1c 三相机实测 Rwp≈59% |
| T10.9 | GSAS-II 结果解析（Rwp / 精修后 CIF / prf 残差谱） | ✅ | `gsas2_parse.py`：.lst/.prf/精修CIF/.gpx 解析回填 Phase/Pattern/RFactorSection；真实 fixture 验证 |

## Phase 14 — CLI & scripting (`cli/`)

| ID | Task | Status |
|----|------|--------|
| T14.1 | CLI pipeline (import → process → search → quantify → report) | ✅ |
| T14.2 | Python API (`xinmatch/__init__.py`) | ✅ |
| T14.3 | Batch scripting (JSON/YAML config) | ✅ (`tools/batch_runner.py`：配置驱动批量流水线 load→preprocess→search→report（复用 core API 不重写算法）；单样品错误隔离不中断；每样品 HTML/MD/TXT 报告 + 汇总 `batch_summary.md`/`.json`；相对路径相对配置目录解析；CLI `python tools/batch_runner.py config.yaml`；示例 `tools/batch_config.example.yaml`；9 个新测试含 YAML/JSON 端到端) |
| T14.4 | Serial instrument control | ✅ (`xinmatch/core/instrument/`：端口扫描 + 安全打开（pyserial 懒加载、`loop://` URL 兼容）；流式采集器 `SerialCollector`（多分隔符/科学计数解析、on_point 实时回调、EOF/秒数/点数/外部停止、两列 ASCII 落盘且可被 load_pattern 直接导入）；CLI `instrument scan` / `instrument collect`（`--live-plot` 实时绘制，matplotlib 懒加载缺失降级）；pyproject 新增 `pyserial>=3.5`；37 新测试 + batch.py 3 处 mypy 欠账清偿；验收 `docs/ACCEPTANCE-T14.4-20261014.md`。GUI 采集面板留后续，core 的 on_point 回调即 GUI 实时绘制接入点) |

## Phase 13 — GUI (`ui/` · PySide6)

> **精修 GUI 特别说明**：精修面板采用 **MAUD 风格向导式交互**（分步引导：选相 → 选背景 → 选精修参数组 → 运行 → 查看 R 因子与残差），
> 但所有实际计算委托给 GSAS-II（T10.6b）。XinMatch 不重写精修算法，只重写交互体验。
> 参考软件：`C:\MAUD3`（MAUD 界面）、`参考软件安装目录`（参考软件 工作流）。

| ID | Task | Status |
|----|------|--------|
| T13.0 | GUI architecture (PySide6 native + QWebEngineView for 3D/report) | ✅ |
| T13.1 | Main window skeleton (menu/toolbar/statusbar/dock panels) | ✅ |
| T13.2 | Pattern view (pyqtgraph, multi-pattern, zoom/trace) | ✅ |
| T13.3 | Peak / candidate / match list tables | ✅ (`ui/tables.py`：Peak/Candidate/Match 三表 QTableView，排序/右键菜单/双击选中信号，已挂载进候选/峰列表/匹配 dock) |
| T13.4 | Periodic table element selector (3-state) | ✅ (`ui/periodic_table.py`：118 元素红/黄/绿三态循环 + Toggle 启用开关，语义对齐 core 三态元素过滤；已挂载"限制条件"页) |
| T13.5 | Dialogs (import / experiment / options) | ✅ (`ui/dialogs/`：导入选项/实验详情/13 类选项/颜色线型四对话框，统一 YAML 配置 load/save；选项与颜色对话框已接线到"设置"菜单) |
| T13.6 | Shortcut mapping | ✅ (`ui/shortcuts.py`：67 条对照 function_keys.md 全量映射，QAction 方式已安装到主窗口并验证触发) |
| T13.7 | Themes | ✅ (`ui/theme.py`：浅/深主题语义令牌 + QPalette/QSS，对比度断言两主题无不可读控件；图标用 Qt 标准图标；主窗口"设置"菜单可切换) |
| **T13.8** | **Refinement wizard GUI (MAUD-style, delegates to GSAS-II)** | ✅ (`ui/refinement_wizard.py`：四步向导——选已鉴定相→背景处理→勾选 Scale/Cell/Profile/Atoms→运行→R 因子+残差谱+精修后晶胞；无 GSAS-II 时友好降级提示；计算全委托 T10.6b/T10.8/T10.9 不重写算法；结果信号 refinement_finished。**已接线主窗口**（2026-10-09）：菜单"精修(&E)"→"打开精修向导…" Ctrl+Shift+W；`set_pattern()`/`set_candidates()` 喂数，选中候选优先否则全部候选；无候选/无实验谱/无 CIF 时 QMessageBox 友好提示不崩溃；`refinement_finished→` 状态栏显示 Rwp) |

## Phases 14–16

See [ROADMAP_v3.md](../ROADMAP_v3.md).

- **Phase 15 打包 ✅（2026-10-09）**：PyInstaller **onedir**（db 512 MB，onefile 解压不可接受）；`xinmatch.spec` + `tools/build_exe.ps1` + `tools/pyi_entry.py`（单入口调度器按 argv 分派 CLI/GUI——踩坑：PyInstaller 6.22 多脚本切片并不会让第二个 exe 跑第二个脚本）；PySide6 走内置 hook、pyqtgraph `collect_all`、gemmi pyd 自动收集、`data/cod_inorganics.db` 随包（exe 同级 data/）、`schema.sql` 随包（import 时 read_text）；GSAS-II 不可打包，无 GSAS-II 环境按 `GSAS2_AVAILABLE` 降级；产物 `dist/xinmatch-1.0.0/`（~1.18 GB）；构建/冒烟/限制见 [PACKAGING.md](PACKAGING.md)。
- **Phase 16 3D 结构可视化 ✅（2026-10-09）**：`ui/structure_view.py`（QWebEngineView + **3Dmol.js 2.5.5 本地打包**，禁外部 CDN；gemmi 0.7.5 解析 CIF→JSON 纯函数 `cif_to_structure_data()`，晶胞从 CIF 标签直读剥 esd；COD ref_id→归档 CIF 路径规则实测核对）；主窗口"精修(&E)"→"3D 结构视图…" Ctrl+Shift+V，无 CIF 时空态页。精修后 CIF 接入 3D 留待后续（`Gsas2RefineOutcome` 未携带精修 CIF 路径）。
- **About/图标**：About 对话框动态读 `xinmatch.__version__`（importlib.metadata，当前 1.0.0，不得硬编码）；主窗口图标 `assets/logo.png`（原创生成，随本版提交）。

剩余：T0.8 FoM P 值深挖、COD 全库检索质量上游修复（峰抽取标定）、T14.4 的 GUI 串口采集面板（后续）、Bruker RAW v1（无格式文档，需真实样本逆向）、Bruker RAW v4 真实验收（需 RAW4.00 样本）。

## COD 全库检索质量治理（2026-10-10，Organizer o_000EpGLcrJB 任务 1）✅

**交付**：`tools/build_cod_full_curated.py`（幂等可复跑）、`data/cod_full_curated.db`（**94,553 entries / 9,328,888 peaks / 836.3MB**，schema 与全库一致、无孤立条目、无残留多卡簇）、`multi_db.py` 注册 `cod_full_curated`、24 新测试 + 交付文档。

**L3 三列对比**（run_acceptance 实测）：

| 库 | entries | Top-1 一致率 | Top-5 重叠 | 判定 |
|---|---:|---:|---:|---|
| cod_inorganics（默认） | 71,199 | **84.6%（11/13）** | 83.1% | PASS |
| cod_full（全库直查） | 112,734 | 7.7%（1/13） | 46.2% | FAIL |
| cod_full_curated（优选去重） | 94,553 | 7.7%（1/13） | 33.8% | FAIL |

**根因**：去重不提升 Top-1——全库 quality/year 质量字段全空；同 entry_id 全库仅 21 峰 vs 无机库 30–38 峰（全库 CIF→峰抽取稀疏 → FoM 区分度弱），离群相胜出。真正杠杆在上游 `tools/build_cod_full_xinmatch.py` 峰抽取（峰窗口/强度标定），已单独立项。优选库价值 = 瘦身去冗余底座（−16.1% entries），**默认检索保持无机库**。

## 全量 pytest"挂起"根因定性（2026-10-10，Organizer o_000EpGLcrJB 任务 2）✅

**"挂起"是误观察**：faulthandler + py-spy 进程栈铁证显示主线程从未进入 matplotlib，始终在 `scipy.optimize.least_squares` 数值雅可比（`test_rollback_triggers_when_optimizer_diverges`，test_turn_on.py:219——故意触发优化器发散）密集计算：max_nfev=400 × 数值雅可比 × structure_factor 重算，**单测孤立运行（零争用）即 35+ 分钟**，算法固有成本。

**修复**：`tests/report/conftest.py` autouse fixture（强制 Agg 后端 + 清理残留 figure，防御性；未改断言/运行时行为）。pyproject 未动。

**验收**：单进程全量 EXIT=0，**1124 passed + 2 skipped + 1 xfailed，用时 53:17**（完整跑完、无挂起）；分块对账一致（A 953+1xf 10:49 / B 130+1sk 42:56 / C 41+1sk 2.7s），无顺序惩罚。固有慢测试清单：turn_on 发散测试（~35min）、GSAS-II 子进程（timeout 1800s）、baseline_acceptance curve_fit——后续建议收敛发散测试拟合预算（需改测试行为），CI 采用分块方案。

## 合成谱 XinMatch 侧检索修复（2026-10-11）✅

**背景**：用户参考软件 FPFM 验收合成谱 13/13（jingzhun 全 Top-1 FoM=1.0000，归档 `tests/baseline/ref20261011/` + `docs/sample_expansion_20261011.md`）；XinMatch 侧标准检索仅 **3/13** 真相相进 Top-20。

**根因（三条，均不在 FoM 参数）**：
1. **生成器峰强度用 CIF 结构因子**（`tools/build_cod_full_xinmatch.compute_peaks_from_cif`，动态范围 1e17，如 BaTiO₃ (110) 2.45e21 vs 次强峰 59188）→ 归一化后次峰全部淹没，实验谱强度分布与库卡片（0-100 相对强度）严重不匹配 → FoM `intensity` 失真（真相相 0.133 vs 真实谱 0.86）。
2. **库内无该编号时回退 CIF**（强度仍失真）→ 改为**库内同元素集卡片**（peaks 最多者）。
3. **无机库系统性缺常见相**：NaCl/KCl/MgO/CuO 无任何元素集匹配卡片（参考软件 COD-Inorg 库均有）→ 从 `cod_full.db` 导入 4 卡补库（`96-900-6388/3133/6475/8961`，备份 `data/cod_inorganics.bak-*.db`，gitignore 排除）。

**修复**：`tools/generate_synthetic_patterns.py`——`_card_peaks()`（精确 entry_id）→ `_card_peaks_by_formula()`（同元素集 fallback）→ CIF 兜底三级强度来源；噪音默认 0.001、峰形尾部余弦衰减（消除 5×FWHM 硬截断台阶伪峰，次要）。

**结果**（现状 FoM + 默认无机库，`tests/search/test_synthetic_acceptance.py` 6 用例）：

| 指标 | 修复前 | 修复后 |
|---|---:|---:|
| 真相相 Top-20 | 3/13 | **13/13** |
| 真相相 Top-5 | 3/13 | **13/13** |
| 真相相 Top-1 | 1/13 | **11/13** |
| L3 真实谱 Top-1 一致 | 11/13 | **11/13**（未退化，MISS 仍为已知基线快照差异 5-1/5-3） |

FoM 参数（DEFAULT_WEIGHTS、sigma_intensity=10、window=0.3°）**全程未动**。剩余：synth_06（BaTiO₃，rank3，intensity 残余差异）、synth_11（CaSO₄/CaCO₃，rank2）。

## FPFM（全谱拟合检索）实现（2026-10-11）✅

**交付**：`xinmatch/core/search/fpfm.py`（完整流水线：峰列表预筛 150 卡 → 7 参数受限最小二乘全谱拟合精排 → Rwp/GOF/FoM 排序）；`pfsm.py` 保留 `pfsm_score`/`pfsm_rank` 兼容层（签名不变）；`tests/search/test_fpfm.py`（单元 + 合成验收 + 真实记录 + 性能守卫）；机制文档 `docs/fpfm_mechanism.md`。

**关键设计（经实验验证）**：
1. 背底**内吸收不预扣除**——Rwp 权重 w=1/y，预扣除背底致低强度残差点被过度惩罚（Rwp≈0.42、GOF≈9.4）；改为二次背底基纳入最小二乘，真相 Rwp≈0.09、错误相 0.26–0.28，分离显著。
2. 全局单 FWHM（init 0.2°，bounds 0.08–0.6°）：Caglioti 在扫描区间近似恒定，单参数稳、快；合成谱收敛 0.151° 贴合生成器 0.15° 下限。
3. 峰形评估用每反射 ±1.5° 局部窗（全网格 M×N 广播致 150 卡精排 492s → 局部窗 12–28s）。
4. 预筛复用 `search_match`（recall_strongest_peak=True，top_n=150）；双线配置 `wavelength_kalpha2=1.5444`（合成单线 None）。
5. FoM=exp(−Rwp/σ)，σ=0.25。

**合成谱 13 组验收**：**Top-1 13/13、Top-5 13/13、Top-20 13/13**（目标 ≥12/13，达成 13/13）。单谱总耗时 44.5–64.7s。

**真实谱 13 组（Kα1/Kα2 双线）**：全部跑通、候选非空；Top-1 均命中任一真相相（LiFePO4/NCM811/ZnO/TiO2/Magnesite/Hematite/Goethite/Gibbsite/Quartz）。单谱 61.4–104.8s，<120s。记录模式不设硬断言。

**测试/性能**：`pytest tests/search` 全绿；`ruff check` 全绿。L3 峰列表回归（`tools/run_acceptance`）保持 13/13 top1 真相相、未退化。

**局限**：未做择优取向/晶胞微调/多相解叠/角度依赖 Caglioti 宽化；后续接 GSAS-II 做完整 Rietveld。


## 统一检索入口 + GSAS-II 高级拟合接口（2026-10-11）✅

**A. 统一检索入口（峰列表 FoM / FPFM 双模式）**

**交付**：`xinmatch/ui/main_window.py`——工具栏新增检索模式下拉框 `_search_mode_combo`（「峰列表 FoM（寻峰）」「FPFM 全谱拟合（不寻峰）」，切换仅更新内部状态、不自动触发检索）；`_run_search_match` 按模式分支执行；模块级 `fpfm_results_to_candidates()` 把 FPFM `(Entry, score_dict)` 适配为 `CandidateResult`（`fom` + `p_values{rwp,rexp,gof}`），`self._candidates` 元素类型不变（精修向导 / 3D 视图 / CIF 导出链路不破）；FPFM 分支不寻峰、不覆盖峰列表（保留上次峰列表）；Kα2 双线（1.5444）留作后续旋钮。新增测试 `tests/ui/test_search_mode.py`（控件存在性/切换行为/纯函数转换/双模式冒烟/FPFM Top-1 命中/`_selected_candidate_results` 回归锚点）。

**冒烟结果**（offscreen + 真实默认库 + 合成谱 synth_06）：

| 模式 | 候选数 | Top-5 | 峰列表 |
|---|---:|---|---|
| 峰列表 FoM | 20 | 全 "Ba O3 Ti" | 84 行（写入） |
| FPFM 全谱拟合 | 10（测试限 top_n=10） | Top-3 全 "Ba O3 Ti"（fom 0.701/0.700/0.700） | 保持 84 行（不覆盖） |

**FPFM 命中（UI 级，is_truth 元素集+比例口径）**：synth_06 Top-1 = 96-210-0858 "Ba O3 Ti" ✓；synth_09 Top-1 = 96-101-0519 "C 1 2 1"（fom 0.614，第二名 0.044）✓。

**验收**：`pytest tests/ui/test_search_mode.py tests/ui/test_main_window.py tests/search/test_synthetic_acceptance.py tests/search/test_fpfm.py` = **47 passed / 0 failed**（独立复跑一致）；既有 UI / Search 测试无退化；ruff 全绿；品牌词全仓 0 命中（缓存目录除外）。

**B. GSAS-II 高级拟合接口（择优取向 + 晶粒尺寸/微应变，全委托后端）**

**交付**：
- `xinmatch/core/refine/gsas2_adapter.py`：`RefineOptions` 新增 `refine_size_strain: bool = False`。
- `xinmatch/core/refine/gsas2_project.py`：manifest `options` 新增 `refine_size_strain` 键；driver 新增 size/strain 阶段（PO 之后、zero-shift 之前，遵循"profile 收敛后才开"原则）：`p.set_HAP_refinements({"Size": {"type":"isotropic","refine":True}, "Mustrain": {"type":"isotropic","refine":True}})`，per-phase try/except 容错。GSAS-II API 经本机实测确认（`Size[2][0]` / `Mustrain[2][0]` 为各向同性精修标志，GSASIIscriptable.py 5070–5163 行）。
- `xinmatch/ui/refinement_wizard.py`：参数页新增「择优取向（March-Dollase）」「晶粒尺寸 / 微应变」勾选，映射 `refine_po` / `refine_size_strain`；说明标签：**以上高级参数全部委托 GSAS-II 后端执行，本地不做拟合算法**；第 1 页多相提示完善（可多选多相，每相 scale/晶胞/原子由后端独立处理）。

**实测**（真实 GSAS-II，3 相 Al2O3/ZnO/CaF2 + cpd-1c.gss，max_iter=25，size_strain=on，PO=off）：**Rwp = 11.85%**、Rp = 9.26%、约 18 s；产物 .gpx/.lst/.prf/.gss/.prm/driver/manifest/result.json 齐全。探针：U/V/W 收敛后 Rwp 21.44% → 开启 size+mustrain 后 20.66%。manifest 传播（run=False）：`refine_size_strain=True → manifest["options"]["refine_size_strain"] is True` ✓。

**验收**：adapter 13 passed + 1 skipped；gsas2_project 15 passed（非真实）+ 真实精修测试 1 passed（18.02 s，GSAS2_AVAILABLE 守卫）；向导 12 passed；`tests/refine` + 向导独立复跑全绿；ruff 全绿；品牌词 0 命中。

**已知局限（非本次引入）**：PO 阶段 [0,0,1] March-Dollase 轴面向层状/纤锌矿结构（如 ZnO、Mg(OH)2），在立方/三方相上勾选 PO 可能使 MD 积分发散（Rwp→100%）——现有 PO 逻辑未改，仅新增界面暴露；size/strain 与 U/V/W 高度相关，依赖分阶段收敛顺序，极端数据下需人工校验参数物理性。

## 版本 1.2.0 + 二进制打包（2026-10-11）✅

**版本升级 1.0.0 → 1.2.0**：`pyproject.toml` version、`xinmatch.spec`（APP_VERSION/VERSION_TUPLE/COLLECT 名）、`tools/build_exe.ps1` 默认 `-Version 1.2.0`；`xinmatch.__version__` 走 `importlib.metadata`（重装 editable 后解析为 1.2.0）；About 对话框显示 **版本 1.2.0** + 联系方式 `sshztx@outlook.com` + logo（独立「关于」菜单，帮助→关于XinMatch...）。

**打包**：`tools/build_exe.ps1`（PyInstaller 6.22.3 onedir）产物 `dist/xinmatch-1.2.0/`（约 1186 MB）：XinMatch.exe（7.2 MB，图标/版本资源 1.2.0）+ `data/cod_inorganics.db`（71,203 entries，512 MB，已重定位到 exe 旁）+ `_internal/`（Qt/PySide6 6.11.2/pyqtgraph 0.14.0/scipy/lmfit 等）+ assets（logo/splash/ico）+ 3Dmol.js。入口 `tools/pyi_entry.py` 单 exe 调度（CLI 子命令/GUI）。

**打包产物自测（真窗口）**：启动 ✓（窗口标题/200 MB 稳定）→ About 版本 1.2.0/联系方式/logo ✓ → 打开 synth_06.txt（4000 点，谱图曲线正常）✓ → Search-Match 检索（候选列表填充，真相相 96-210-0858 rank5 FoM 0.719）✓ → CLI `search --help`/synth_06 检索（146 峰/5 候选）✓ → **3 次启动/关闭循环全成功**（PID 9152/13412/14104）✓。品牌词 0 命中。

**说明**：截图中 "77604 entries COD-Inorg 2025.12.01"/Shimadzu 版权行来自桌面并排运行的参考软件窗口（OCR 混入），非 XinMatch 内容；XinMatch 加载的是打包的 71,203 库。pyqtgraph.examples/OpenGL hidden-import ERROR 与 scipy.special._cdflib WARNING 为无害构建告警（v1.0.0 同）。

## 版本 1.2.1 / 1.3.0 / 1.3.1（2026-10-12）✅

**v1.2.1 — mypy 全包零豁免 + 品牌自指修复**：`pyproject.toml` 移除 mypy `exclude`（search/refine）与 `[[tool.mypy.overrides]]` 段，18 处注解层修复（`dict[str, str | float]` / `cast` / `Any` / 返回类型包装）；`python -m mypy` → **Success 0 errors / 103 files**；`tests/search+refine+cli+ui` 全量后台验证通过（exit 0）。`docs/mypy_baseline.md` 更新为全包无豁免。HANDOVER 品牌自检命令改为模式串拼接书写（消除文档自指误报）。

**v1.3.0 — FPFM Kα1/Kα2 双线旋钮 + 图标库重绘**：
- FPFM 旋钮三处收口：Options→Search-Match 页（`fpfm_kalpha2_enabled` / `fpfm_kalpha1_angstrom` / `fpfm_kalpha2_angstrom`，落盘 `config/xinmatch.yaml`）、CLI `search --mode fpfm [--single-kalpha] [--kalpha1] [--kalpha2]`、GUI 检索模式 combo 提示当前 Kα 配置；`fpfm_kalpha_wavelengths()` 读 YAML（Kα1≤0 时跟随样品波长）。synth_13 单线谱回归锁定（`tests/ui/test_fpfm_kalpha2.py`）。
- 图标库：修复 `_build_actions` 把模块 id 当图标名传入导致 14 个动作全部回退通用立方体的 bug（`icons.icon()` 内置 `resolve_icon_name`）；29+ 图标重绘为填充主体 + accent 点缀（数据特征类保留粗描边）；新增多尺寸预渲染 `(16,20,24,32,48)`；主题切换时图标重着色（`_icon_actions` + `_refresh_icons`）。

**v1.3.1 — 五项 GUI 体验迭代 + 忙碌窗口 + 打包**：
1. **图标视觉归一化**（`ui/icons.py`）：`_normalized_pixmap` 高清 8× 渲染 → `_alpha_bbox` alpha 包围盒 → 长边等比缩放到 `_CONTENT_RATIO=0.74` → 居中；38 图标占比统一 0.75（±容差验证）。
2. **工具栏图标+文字+悬停详细说明**：`ToolButtonTextBesideIcon` + `_MODULE_TIPS` 15 条 tooltip（是什么+怎么用）。
3. **元素周期表改弹窗式**（`ui/periodic_table.py::PeriodicTablePanel`）：摘要行+启用开关+「选择元素…」+「清除」；弹窗复用持久 `PeriodicTableWidget` 实例；states/set_states/set_enabled/is_enabled/reset drop-in API。
4. **谱图轴切换**（`ui/pattern_view.py`）：X 2θ↔d（布拉格 λ/2sinθ），Y 计数↔√↔log₁₀；crosshair 读数恒显物理量；`fit_data_range()` 打开/删除数据/切轴后自适应。
5. **耗时操作忙碌窗口**（`ui/busy.py`）：`run_with_busy` QThread + `BusyDialog`（走马灯+模态遮罩+重入保护）；检索全链路 busy 化（`_do_search`/`_apply_search_results`/`_show_search_error` 三件套，异常经 on_error 回 GUI 线程提示）。修复两个生产级线程 bug：DirectConnection 跨线程调 QWidget 挂死（信号 receiver 改 BusyDialog 排队槽）、sqlite 主建连 worker 用（`check_same_thread=False`）。

**版本与打包**：pyproject/spec(APP_VERSION+TUPLE+COLLECT name)/build_exe.ps1/PACKAGING.md 五处同步 **1.3.1** + `pip install -e . --no-deps`；产物 `dist/xinmatch-1.3.1/`（exe FileVersion 1.3.1 实测，CLI FoM+FPFM 单线冒烟通过）。

**验收**：ruff 全绿；mypy 104 files 0 错误；`tests/ui` 轻量 461 passed（新增 `tests/ui/test_v131_ux.py` 15 用例）；heavy 真库冒烟 1m46s 全过；品牌词全仓 0 命中。

**历史大文件治理（推送 GitHub 前）**：`.gitignore` 加 `data/*.db`；`git rm --cached` 三个 512–942 MB 库；`git filter-repo` 重写 86 commits 移除大 blob，.git 1.1GB→8.9MB。**注意**：filter-repo 内部 `reset --hard` 会摧毁未提交工作树改动——跑之前必须 commit/stash（本次事故已凭编辑记录逐文件重建恢复）。

## v1.4.0 无机库构建逻辑排查专项（2026-10-12）✅

**问题**：教科书物相（岩盐 Halite / 钾盐 Sylvite / 方镁石 Periclase / 黑铜矿 CuO）在检索中系统性找不到。诊断出**三层缺陷**（峰表污染 → 库数据缺陷 → 召回饱和），逐层定位并全部修复：

**A. 峰表污染（代码缺陷，两处修复）**

合成 NaCl 谱 5 条真峰变 43 峰，密集 junk 卡片凭 `P_npeaks` 霸榜：

1. **Kα2 剥离自激振荡**（`core/preprocess/alpha2.py`）：Rachinger 因果递归对无 Kα2 卫星的谱（单波长合成谱/单色器/已剥离谱）模型失配，后沿过减、负偏移前馈，振荡幅度达峰高 50%（±24000 计数）。修复：递归后负偏移超峰值 1% 判定「与 Kα1+Kα2 模型不一致」，跳过剥离返回输入副本（`_NEGATIVE_EXCURSION_TOL = 0.01`）。效果：Kα2 步骤峰数 43→5。
2. **MAD 噪声估计崩塌**（`core/peak/peak_search.py`）：`_noise_estimate` 对一阶差分取 MAD，背底相减后平坦区精确为 0 → MAD≈0.0075 → SNR/突出度阈值≈0.02，SNIP 残留 ±16 计数全部成"峰"。修复：`noise <= max(1e-9, 1e-3*signal)` 时回退 `signal*0.01`。效果：SNIP 残留阶段峰数 13→5。
3. **突出度语义缺陷 + 尾毯伪峰**（`core/peak/peak_search.py`，Kα2 护栏上线后暴露）：单线谱上剥离被正确跳过（输出=输入）后，合成谱的宽 Lorentz 尾（8×FWHM 截断，峰间 40–160 计数"尾毯"）上的噪声凸点越过 3×MAD≈30 阈值——synth_06 峰数 146→182，BaTiO₃ 跌出 Top-10。修复：① 突出度改「钥匙鞍点」语义（scipy 同款：高于两侧通往更高峰路径上的最低点的较高者），尾毯凸点的上坡鞍点贴近峰高 → 突出度塌缩到噪声级；② 候选生成时吸附到局部极大（导数过零点会落在峰侧翼一格，不吸附会重复接受强峰的侧翼候选——实测 121 伪峰）；③ 突出度搜索半窗宽度自适应（max(5, 峰自身 FWHM/2) 点，上限 50 点）——宽弱峰（FWHM 0.3°）要走到自己的谷底才有突出度，尖噪声凸峰保持窄窗。效果：synth_06 峰数 182→122，BaTiO₃ rank 5；13 组合成谱 Top-20/Top-5 全达；新增回归测试 `test_peak_search_rejects_tail_carpet_bumps`（旧代码 15 峰泄漏 → 新代码 ≤8）。

**B. 数据库数据缺陷（幂等迁移工具修复）**

- 上游 dump（`COD_inorganics.sqlite` 71,199 条）中 `Cl Na`/`Cl K`/`Mg O` 纯二元条目数为 **0**——补卡无源，只能从 CIF 现算；
- 库内 4 张教科书相卡片实为 COD **非环境条件变体**（CIF 自带证据：9006388 是 100K 高压 NaCl，a=5.8447 vs 环境岩盐 5.6402），与教科书线位偏差大；
- 10 张卡片强度未归一化（6.4e5–9.5e8）；52,366 个幻影峰（`intensity < 1e-6`，库内强度分布二模分离：1e-20 以下 52,366 个，1e-6~0.01 之间 0 个）。

修复：新增 `tools/patch_cod_inorganics.py`（幂等数据迁移）：插入 3 张环境条件卡片 `96-900-3308`（Halite, a=5.6401）/`96-900-3112`（Sylvite, a=6.2879）/`96-900-0501`（Periclase, a=4.212），峰表由 `compute_peaks_from_cif(dmin=1.0, max_peaks=100)` 计算、归一化 max=1000、过滤 `I>=0.01`（去 F 心禁峰）；归一化 10 张未归一化卡片；删 52,366 幻影峰；`build_element_index` + `ANALYZE`；`--dry-run`/`--no-backup` 支持；写前自动备份（`cod_inorganics.bak-20261012-153759`）。已验证幂等（二次运行 0 修改）。

**C. 召回饱和缺陷（默认值翻转修复）**

稀疏谱（5 峰）下数百张密集卡片全部匹配所有窗口，`recall_max_candidates=800` 按 entry_id 字典序截断，`96-900-xxxx` 系列恒被挤出——GUI 峰列表模式实测仅 8/13 命中。修复：`search_match(recall_strongest_peak=True)` 默认翻转（Hanawalt 式召回：只保留最强参考峰落在实验强峰窗内的条目），docstring 补充饱和缺陷说明。实测 13 组合成谱 plain 8/13 → Hanawalt 13/13（12 个 rank 1）。FPFM 路径本就传 True，文档（`docs/fpfm_mechanism.md`）早已按 True 描述，翻转后峰列表模式与文档一致。

**回归测试（新增）**

- `tests/peak/test_peak_search.py::test_peak_search_noise_floor_rejects_smooth_ripple`：5 高斯峰 + 慢速波纹 → 恰好 5 峰；
- `tests/peak/test_peak_search.py::test_peak_search_rejects_tail_carpet_bumps`：宽尾伪峰 + 弱宽真峰 → 真峰全在、总数 ≤8（旧代码 15 峰泄漏）；
- `tests/preprocess/test_alpha2.py`：3 个护栏测试（Kα1-only 谱跳过剥离 / 真双线仍剥离 / 修复既有 recovering 测试的逐点 δ 构造）；
- `tests/search/test_search_match.py::test_recall_hanawalt_default_survives_dense_card_saturation`：900 张 `96-200-xxxx` 密集诱饵 + 真相 `96-900-9999`，legacy plain+800 截断丢失真相、Hanawalt 默认 top-1 FoM=1.0；
- `tests/search/test_textbook_phases.py`（新文件）：教科书晶胞常数现场合成三相谱 → 峰数==线条数 + 环境条件卡片 Top-20 + Halite Top-5，库缺卡片时提示运行迁移工具。

**验收**：`.scratch/probe_ambient.py` → Halite rank 1（FoM 0.928）/ Sylvite rank 5 / Periclase rank 2（榜首 `96-900-5516 Fe0.01Mg0.99O` 为掺 Fe 近缘卡片，合理）；`tests/search` + `tests/preprocess` + `tests/peak` 套件通过；ruff/mypy 改动文件全绿（`alpha2.py` 护栏行为 mypy 零错误）。

**遗留（归入后续任务）**：Sylvite rank 5 的差距源于卡片 a=6.2879 vs 教科书 6.2931 的 0.08% 单元格差 + CIF 强度惯例（→ T0.8 FoM P 值深挖）；`recall_strongest_peak=True` 在 71k 全库上单次检索 ~9s（plain ~2.5s 但结果错误），Hanawalt 模式下 `recall_max_candidates` 被忽略，超大规模库的性能旋钮留待 T6.0 索引落地。

---

## v1.4.0 FPFM 剩余扩展（2026-10-13）✅

**背景**：`docs/fpfm_mechanism.md` §8 列了四项局限（择优取向与晶胞微调 / FWHM 全局单值 / 多相解叠 / 峰形不对称）。本次先做**数据可行性核查**再定范围，落地两项、推迟两项（其中一项被数据阻塞）。

**选型结论（先查数据，后选模型）**

| 项 | 结论 | 依据 |
|---|---|---|
| Caglioti U/V/W 角度依赖宽化 | ✅ 实现并默认开 | 不依赖 hkl；合成谱生成器同款模型，可直接验证参数回收 |
| 晶胞微调 `cell_delta` | ✅ 实现并默认开 | `entries.a/b/c` 仅 15/71206 缺失；2θ 位移 ∝ tanθ，与常数 shift 可区分 |
| March-Dollase 择优取向 | ⛔ **被数据阻塞** | `peaks.h/k/l` **6,214,072 行全 NULL**（`Entry.hkl` 恒 None）；真 MD 需逐反射 hkl 算面法向夹角，须先做 CIF→hkl 回填迁移 |
| 峰形不对称 | ⏸ 明确推迟 | η 自 v1.2 起就在拟合向量内（`eta_bounds=(0.05,0.95)`），已吸收一阶不对称；显式校正（Finger–Cox–Jephcoat 类）对"先找到相"排序增益有限 |
| 多相解叠 | ⏸ 明确推迟 | FPFM 定位是"先找到相"，精修交 GSAS-II；混合谱真相相仍可排到 Top-1，仅 Rwp 偏高 |

附带发现：生成器的 `_march_factor` **不是**真 March-Dollase——它乘的是**峰内形状**（窗内 |2θ−2θ₀| ≤ 8×FWHM ≈ 0.028 rad，cos≈1 ⇒ 近似常数 1.52），被 `scale` 完全吸收，对排序无影响。

**实现**（`xinmatch/core/search/fpfm.py`）

1. `_caglioti_fwhm(tanθ, u, v, w, fwhm_bounds)`：`H²=U·tan²θ+V·tanθ+W`，H² 先夹 0 再开方（U/V/W 的 box 边界不保证 H²>0，否则 NaN），H 再夹进 `fwhm_bounds`。
2. `cell_delta`：全局相对晶胞缩放，2θ 位移 `−Δ·(360/π)·tanθ_i`（Bragg 一阶；Δ=0.005 时二阶误差 <0.001°，远小于 0.02° 网格）。开启时按 `cell_bound·(360/π)·tanθ_i` **逐反射加宽评估窗**，避免峰被推出窗而截断。
3. 参数向量 7→11 按 `cfg.caglioti` / `cfg.cell_refine` 动态组装；关闭时严格回退 v1.2 行为，`CandidateFit`/score_dict 写入恒等编码（U=V=0、W=fwhm²、Δ=0），新增键 `caglioti_u/v/w`、`cell_delta` 恒存在。
4. **剖面向量化**：逐反射切片循环 → 统一宽度索引矩阵 + `np.bincount` 累加。

**性能（本次最反直觉的一点）**：参数 7→11 后首版精排慢 2.8×（refine 12.5→34.7s，照此外推 5-2b 会破 120s 护栏）。插桩定位 = nfev 7→8.9（1.27×）+ 单次残差 4.4→6.8ms（1.55×），后者源于**逐反射循环里 8 次小数组 numpy 调用的固定开销**。向量化后单次残差 0.42→0.18 ms，**端到端反比 v1.3 更快**——6 谱 A/B 全部下降：

| 谱 | v1.3 | v1.4 | 变化 |
|---|---:|---:|---|
| synth_01 | 44.8s | 43.4s | −1.4s |
| synth_06 | 57.2s | 51.1s | −6.1s |
| synth_12 | 40.2s | 36.1s | −4.1s |
| synth_13 | 68.3s | 61.5s | −6.8s |
| 2-1（真实） | 89.9s | 80.1s | −9.8s |
| 5-2b（真实） | 108.3s | 90.3s | −18.0s |

真相相 6/6 保持 Top-1；真实谱 Rwp 微降（2-1 0.4439→0.4421、5-2b 0.4176→0.4170）。合成谱 Rwp 基本不变（生成器 Caglioti 全程被 0.15° 下限压制 ⇒ 实际常数宽度，两种模型不可区分）。

**回归测试**（`tests/search/test_fpfm.py` 新增 8 项）：`test_caglioti_fwhm_formula_and_clamps`、`test_theory_profile_caglioti_widens_high_angle`（细网格高低角 FWHM 比 >1.5）、`test_fit_recovers_caglioti_uvw`、`test_caglioti_beats_global_fwhm_on_angle_dependent_width`（Rwp < 0.5×）、`test_fit_recovers_cell_delta`（+0.003 → +0.00299）、`test_switches_off_identity_encoding`、`test_reflection_windows_extra_margin_widens_high_angle`、`test_score_dict_carries_v14_keys`。

**等价性验证**：改前把旧文件 `cp` 到 `.scratch/fpfm_pre_vectorize.py`，以独立模块名加载，48 组配置（Kα 双线 × 晶胞偏移 × 窗口加宽 × 0.01/0.02 网格）对比 `max|Δ|/max < 1e-12`。

**验收**（2026-10-13）

- `tests/search` junit 结论：**275 用例 0 失败 0 错误**（2 跳过，166.5s），含新增 8 项、`test_deterministic_single_pattern` 与 `test_single_pattern_under_120s`（43.4s，护栏 120s）；
- 两个慢验收类（`TestSyntheticFpfmAcceptance` 13 组合成谱 Top-20/Top-5、`TestRealFpfmRecord` 13 组真实谱 record）在 `tests/peak + tests/preprocess + tests/search` 全量跑（47 分钟）中同样到达 100%、进度行无 F/E；
- 2 处 skip 为 `tests/search/test_textbook_phases.py` 对 Sylvite/Periclase 的「仅 Halite 断言 Top-5」预期跳过（v1.4.0 无机库专项既有行为，与本改动无关）；
- `tests/ui` junit 结论：**205 用例 0 失败 0 错误**（350s，offscreen）；
- ruff 改动文件全绿；mypy `fpfm.py` **0 错误**（其余 9 处为 `entry.py`/`background.py`/`smoothing.py`/`fom_criteria.py` 存量）；
- 提交 `d6a543c`（5 文件 +538/−47）。
- 已知环境现象：本环境 pytest 收尾会被沙盒钩子拦截临时目录清理（286 文件 > 50 阈值），汇总行不落盘、退出码非 0——**判定以 junit XML 与进度行的 F/E 为准**。

**关联**：v1.4.0 无机库专项遗留的「Sylvite 卡片 a=6.2879 vs 6.2931 的 0.08% 晶胞差」现由 `cell_delta`（边界 ±0.5%）在拟合层面吸收，剩余差距（CIF 强度惯例）仍归 T0.8。

---

## T0.8 / #16 FoM P 值深挖（2026-10-13）🟡→结论沉淀

**任务**：从 `fom_criteria.py` 五分量入手，量化「密集 junk 卡片凭 `P_npeaks` 霸榜」的实际影响面并决定权重，同步处理 CIF 强度惯例 vs 实测强度差异。

**方法**：`.scratch/` 一组只读探针（`probe_pnpeaks.py` / `probe_sylvite_intensity.py` / `probe_lp_intensity.py` / `probe_l3_weights.py` / `probe_minor_phase.py` / `probe_recall_topk.py`），真实无机库 71,203 条 + 教科书三相（真相 eid 已知）+ 13 组真实谱 + 组合成谱，检索后本地重算 P 值/权重，不重跑检索。

> **可复核链说明（2026-11-06 补）**：上述六个原始探针与当时的结果 JSON 已从
> `.scratch/` 清理，本地不再可直接复跑。结论以本节正文 + `docs/基准报告-物相检索-v3.md`
> §26 为准；后续相关的实测 P 值可查 `docs/检索基准-v3-诊断-20261104.md`、
> `docs/检索基准-31-次相诊断-20261105.md` 与 `.scratch/probe_31_fom.json`。

### 结论 1：权重**保持发布值不动**（三条独立证据）

1. **密集卡霸榜的现状形态**：候选集已无 n_ref≥200 的「超密集 junk 卡」（幻影峰清理 + Hanawalt 过滤生效），竞争来自 **n_ref=100 的中等密集卡**。典型个案：
   - **Sylvite**（5 峰稀疏谱）：榜首 `96-200-1971 Cs N O3` / 次席 `96-153-5097 Ge I2 La2` 等 n_ref=100 无关卡凭「峰位密度撞线 + n=1.000/corr=1.000 满分」压过真相卡 `96-900-3112`（rank 3，FoM 差仅 0.0024）。
   - **synth_06**（BaTiO₃，122 峰含伪峰）：真相卡 pairs=16/n=0.131（pos=0.989 几乎完美）被密集卡 pairs=42/n=0.344 反超，真相 rank 5（Top-5 边界）。
2. **单变量权重敏感性是双刃剑**（本地重排）：`w_npeaks` 0.2306→0.15 改善 synth_06（5→2）但恶化 Sylvite（3→7）与 Halite（1→2 风险）；0.05 全面恶化。
3. **L3 真实谱 13 组最终判据**（71k 库，formula 兼容口径）：`w_npeaks ∈ {0.20, 0.15, 0.10, 0.30}` 的 Top-1 命中均为 **10/13、Top-10 全中恒 4/13 且缺失样本完全相同**（2-1 CaCO₃ / 3-1 Al₂O₃·CaF₂ / 4-1 Al₂O₃）——**权重对多相次相缺失零影响**；`w=0.05` 使 Top-1 降至 9/13。叠加 #14 已证纯权重 sweep 不可复现 ⇒ 权重路线关闭。

### 结论 2：CIF 强度惯例差异真实存在，但**不做全局 LP 修正**（破坏性证据）

- **量化**：Sylvite 卡 `96-900-3112` 归一化后 (220)/(200)=0.34 vs 教科书 0.55（差 38%），低角→高角系统性衰减更快，符合 COD I_calc（结构因子²，缺洛伦兹-偏振因子）惯例特征。
- **LP 校正模拟**（卡片强度 ×LP(2θ)=(1+cos²2θ)/(sin²θ·cosθ) 再归一化，本地重算）：**全面破坏**——真实谱 2-1 Top-1 ZnO→Ba₃Er₄O₉、5-2b Fe₂O₃→O₄TaTi；Sylvite 真相 3→20；合成谱真相 rank synth_01 1→4、synth_06 5→40、synth_13 1→9。
- **根因耦合**：合成谱生成器 `_card_peaks_by_formula()` 直接抄库卡片强度 ⇒ 合成谱 =「库强度」的理想再现（自洽闭环），且人工参考软件验收基线（ref20261011）绑定旧谱。全局改惯例 = 破坏合成谱验收 + 真实谱 Top-1 双损。**库强度与实验谱现状已兼容**（L3 Top-1 10/13 优于 LP 后）。
- 残余差距归因个案：Sylvite 卡强度表本身偏差 + 0.08% 晶胞差（后者已由 FPFM `cell_delta` 吸收）。

### 结论 3（新增归因）：多相谱次相 Top-10 缺失在 **recall 层**，不在 FoM 层

- 3-1 的 50 张 Al₂O₃ 卡、4-1 的 Al₂O₃/Brucite 卡、2-1 的 CaCO₃ 卡 **0 张进入候选集**——`strongest_peak_only`（Hanawalt）只保留「最强参考峰落在实验 **Top-20 强峰**窗口」的条目；次相最强峰（如 Al₂O₃ 1.602 Å→57.5°）不在强峰窗口 ⇒ 整体淘汰。
- **recall_top_k 20→40→80→200 全部无效**（次相恒 MISS）——不是强峰数量问题，是「单最强峰」判定的结构性盲区。
- 该层与 FoM 权重无关 ⇒ 解释了结论 1 中「权重调不动缺失面」。修复方向属 T6.0 预筛策略（如「卡片前 K 强峰任一命中」+ 候选规模护栏），单独立项，不在本次改。

### 代码变更

- `xinmatch/core/search/fom_criteria.py`：docstring 与默认值对齐——`sigma_pos` 描述 0.1°→0.15°（L3 追平时实参已改 0.15，文档未同步；行为零变化）。
- 探针留存 `.scratch/`（gitignore）。**FoM 权重、强度惯例、correlate、peak_search 均未改动**——本次为证据驱动的不动决策，防未来误改。

---

## T0.8 / #17 定量精度：主相 wt% 追 <3%（2026-10-13）🟢达成

**任务**（handover 行动清单第 2 项）：COD 标准 CIF + 实测仪器参数 + 优选取向建模，把主相 wt% 追到 <3%。基线（COD CIF + MD-PO，20-120° 窗口）：4-1 的 ZnO +0.39 / Al₂O₃ +2.78 / CaF₂ +1.14 / **Brucite −4.31 wt%**（唯一超标）。

### 探针结论（证据链）

1. **实测仪器 .prm 无改善（归因证伪）**：MAUD 实测仪器块（Cu Kα1=1.5405982/Kα2=1.5445065、I(Kα2)/I(Kα1)=0.4898、θ-θ、石墨单色器 26.228°、闪烁探测器）经 `tools/maud_to_prm.py` 转 GSAS-II `.prm` 后 4-1 复跑：Rwp 17.54→17.57%，Brucite −4.31→−4.84 wt%——**波长级仪器参数对层状相偏差无贡献**。
2. **SH 球谐纹理在此工作流不可行**：P-3m1（Laue 3m1）4 阶圆柱 SH 仅 3 系数（C(2,0,0)/C(4,0,0)/C(4,0,3)），且（a）hist 级 `Pref.Ori.[0]='SH'` 触发 SHPOcal，其系数名用 IfLMN=False（缺 C(2,0)）与 phase 级 `General['SH Texture']` 的 IfLMN=True 名不一致 → RefineCore 报 `0:0:C(2,0)` 缺失直接崩；（b）改 phase 级 SH Texture 后 LS 引擎 SVD 奇异（`ouch #2` giving up）。**放弃 SH，聚焦 MD 初始值与窗口**。
3. **根因 1——窗口切掉 Brucite 最强峰**：默认 20-120° 窗口把 Brucite (001)（2θ≈18.6°，相对强度 100）排除 ⇒ Brucite scale 失去最强峰约束、MD r 不可辨识（收敛 1.0）。
4. **根因 2——MD r=1.0 是陷阱极小**：层状相（Brucite/ZnO 板状织构）r 必须 <1 增强 (001)；r0=1.0 时 LS 停在各向同性，r0=0.7 时精修收敛 r*≈0.672（4-1 Brucite）且 Rwp 显著改善。

### 结果（r0=0.7 + 窗口 10°）

| 样本 | Rwp | ZnO | Al₂O₃ | CaF₂ | Brucite |
|---|---|---|---|---|---|
| 4-1（真值 19.94/21.27/22.53/36.26） | 15.69% | −0.83 | +0.78 | −0.05 | **+0.09** |
| 3-1（真值 ZnO 93.59%） | 14.26% | −1.80 | +0.70 | +1.11 | — |
| CPD-1C（真值 ZnO 93.59%） | 14.26% | −1.73 | +0.69 | +1.05 | — |

**全部相 <3 wt%（实际 <2 wt%）**；4-1 Brucite 从 −4.31 改善到 +0.09。全谱（None，5° 起）反而不如 10° 窗口（Brucite +8.67，低角背景/样品效应干扰），故默认窗口定为 (10, 120)。

### 代码变更

- `tools/maud_to_prm.py`（新）：MAUD `.par` 实测仪器块 → GSAS-II `.prm`（ICONS 固定列经 GSASIIfiles.py 规则验证）。
- `tests/fixtures/gsas2_project/XRD7000_Cu.prm`（新）：实测 XRD-7000 仪器参数 fixture。
- `xinmatch/core/quant/rietveld_quant.py`：`rietveld_quantify` 新增 `instrument_file=` 参数透传。
- `xinmatch/core/refine/gsas2_adapter.py`：`RefineOptions` 新增 `po_model`（"md"/"sh"，sh 实验性）与**默认 `two_theta_range=(10,120)`**（10° 下限保留 <20° 强峰；None 仍表示全谱）。
- `xinmatch/core/refine/gsas2_project.py`：manifest 透传 `po_model`；驱动脚本 MD 阶段 **r0=0.7**（板状织构初始，绕开 r=1.0 陷阱）；SH 分支按 phase 级 `SH Texture` 设置（实验性，P-3m1 下 SVD 不稳）。
- `tests/quant/test_maud_to_prm.py`（新，4 用例）+ `test_rietveld_quant.py`：三个 cod_po 真实数据测试窗口 20°→10°、4-1 **Brucite 断言 <6%→<3%**、docstring 沉淀 #17 修复逻辑。

**回归**：`tests/quant/test_maud_to_prm.py` 4/4；`test_rietveld_quant.py` 非 slow 7/7；slow cod_po 三用例 3/3（junit `.scratch/v17_slow.xml`）；ruff 改动文件全绿；mypy 无新增错误（存量 9 处为 entry/background/smoothing/fom_criteria）。

---

## #18 v1.4.0 小项打包（2026-10-13）✅

**任务**：版本号五处同步 + 全量验证 + PyInstaller 打包 + 推送 GitHub。

**版本号同步**（v1.3.1 → v1.4.0）：
- `pyproject.toml` `version`、`xinmatch.spec` `APP_VERSION`/`VERSION_TUPLE`/**`COLLECT name`**（首次构建曾漏改 COLLECT name，产物误落到 `dist/xinmatch-1.3.1`，修正后重建并清理残留）、`tools/build_exe.ps1` `$Version`/输出路径/注释、`pip install -e . --no-deps` 刷新 metadata（`xinmatch.__version__ == "1.4.0"` 实测）、`README.md` 状态行。
- `docs/STATUS.md` / `HANDOVER-20261013.md` 中 v1.3.1 历史记录保留（历史文档不改写）。

**全量验证**：
- 核心套件（`tests` 除 UI，含 slow）：**1013 用例 3 失败 0 错误 46 跳过**——3 个失败全部为 venv 缺 `pyyaml`（pyproject 正式依赖未装），`pip install pyyaml` 后 `tests/test_batch_runner.py` 4/4 全过（非代码回归）。
- UI 套件（python310）：**205 用例 0 失败 0 错误**（358.6s）。

**打包产物**：`dist/xinmatch-1.4.0/`（**1186 MB**）——`XinMatch.exe` 7.2 MB（FileVersion/ProductVersion = 1.4.0 实测）、`data/cod_inorganics.db` 512.3 MB 外置、`_internal/`。CLI 冒烟：`search --help`/`import --help` usage OK；`run` 5-1 真实样本 → top_candidate 96-901-3321（SiO₂）+ report.html（13,982 B）+ JSON 输出正常。

**推送**：6 个提交（`62909cd`→`a1a3040`）已推送 GitHub `PolyXRD/XinMatch` master，本地与远端 0/0 同步。

---

## 5.2 hkl 回填迁移（2026-10-13）✅

**任务**（HANDOVER §5.2 新立项，FPFM 择优取向前置）：`peaks.h/k/l` 全 NULL（6,214,072 行 / 71,206 卡），真 March-Dollase 无法落地——逐峰 Miller 指数缺失。

**探查**：
- `peaks` 表已有 h/k/l INTEGER 列（全 NULL）；`entries.entry_id` 全为 `96-` 前缀可反推 COD id（`ref_id_to_cod_id`）；CIF 存档缺失 43 条（0.06%）。
- **库峰表来源**：抽样 4 矿物（Halite/Periclase/Sylvite/Tenorite）库峰 d 与本地 CIF gemmi 重算**全对齐**（d 相对差 < 5e-5）——同管线输出；但全库 dry-run 显示 **26.9% 峰未匹配**：59.8% 是 **d < 1.0 Å**（库 dump 的 dmin 深于本地重算的 1.0 Å），其余 d ≥ 1.0 未匹配系 **PolyXRD dump 与本地 COD CIF 的晶胞/管线差异**（相对 d 漂移 p50 = 0.45%，非浮点噪声；CIF 无 `_refln` 表可对照）。
- **匹配策略安全边界**：1e-4 相对容差 → 只给「d 完全一致」的峰写 hkl，绝不猜测错配邻近反射；未匹配峰留 NULL。

**实现**：
- `tools/build_cod_full_xinmatch.py`：`compute_peaks_from_cif` 新增 `return_hkl=True`（返回 (d, i, hkl) 三元组，默认 False 保持双元组契约）。
- `tools/backfill_hkl.py`（新）：幂等回填——逐卡重算（dmin=1.0、Cu Kα、非偏振 LP、top-100）+ d 对齐（searchsorted + 同 d 多解按强度消歧）+ 分批 UPDATE（2000 行/事务）+ `--dry-run` / `--no-backup` / `--limit`；备份 `cod_inorganics.db.bak-hkl-*`。

**结果**（正式回填，backup `data/cod_inorganics.db.bak-hkl-20261013-084416`）：

| 指标 | 值 |
|---|---|
| 回填行 | **4,526,901 / 6,194,488（73.1%）** |
| 覆盖卡 | 70,956 / 71,206（**99.6%**，至少 1 峰回填） |
| 未匹配 | 1,667,587：d<1.0 Å 910,706（超出重算 dmin 范围）+ d≥1.0 756,881（晶胞/管线差异，留 NULL） |
| CIF 缺失 | 216 条（含重算失败，0.3%） |

**核验**：Sylvite 实卡最强峰 d=3.2110 Å ↔ hkl=(0,2,0) ↔ 晶胞 a=6.422 Å（d=a/2 自洽）；`tests/test_backfill_hkl.py` 8 用例（return_hkl 契约、d 匹配、同 d 强度消歧、空重算、dry-run 零写入、apply 幂等）全过；ruff 全绿。

**关联**：下一步 FPFM 择优取向（March-Dollase 真逐峰 hkl 建模）可在 hkl 填充的库上落地；逐晶胞参数（a/b/c）精修的晶胞数据本就完备（entries.a/b/c 缺失仅 15/71,206）。

### 5.2b 逐晶胞参数（a/b/c/α/β/γ/volume）精修（2026-10-13）✅

**任务**（HANDOVER §5.2「同批可做」）：`entries` 晶胞与 COD CIF 权威值对齐 + 补全缺失 + 校正 volume。

**探查**：抽样 500 卡——a/b/c 相对差 p50 = 0.000%、max ~0.15%（dump 与 CIF 基本一致）；**volume 大面积失真**（与 CIF 差 >1% 的卡 1,890/71,206 按存储值口径）；15 条六参数全缺（均为无 CIF 卡，属 43 条 CIF 缺失）。

**实现**：`tools/backfill_cells.py`（新）——逐卡读 CIF（gemmi `SmallStructure.cell`）重写 `entries` 的 a/b/c/α/β/γ/volume（CIF 权威），幂等、`--dry-run`/`--no-backup`/`--limit`、备份在首次写入前。

**结果**（正式应用，backup `data/cod_inorganics.db.bak-cells-20261013-112431`，含 hkl 回填结果）：

| 指标 | 值 |
|---|---|
| 更新 | 71,163 / 71,206（43 条无 CIF 保留 dump 值并报告） |
| 实质变动 | 1,890 卡（a/b/c 或 volume 相对差 >0.1% / >1%） |
| 缺失 | 六参数缺失清零至 15 条（均为无 CIF 卡，无法补） |

**核验**：抽样 10 卡 a/b/c/volume 与 CIF 相对差 < 1e-6 全一致；`tests/test_backfill_cells.py` 5 用例（dry-run 零写入/apply 幂等/NULL 补全/无 CIF 报告）全过；回归 81 用例 0 失败（backfill 两工具 + db 套件）。dist 打包产物 DB 已同步。

### 6.1 FPFM 真 March-Dollase 逐峰择优取向建模（2026-10-13）✅

**任务**（用户选定候选）：在 hkl 已回填的库上落地 FPFM **真** March-Dollase（MD）逐峰择优取向建模——此前 `peaks.h/k/l` 全 NULL 无法逐峰解析 PO 轴反射（#15 被数据阻塞），5.2 回填后 73.1% 峰含 hkl、99.6% 卡可解析。

**生成器升级（"验收集能证伪≠证实"根除）**：`tools/generate_synthetic_patterns.py` 的 `_march_factor` 原是**假 MD**——乘的是**峰内形状**（窗内 |2θ−2θ₀|≤0.028 rad、cos≈1 ⇒ 近似常数 1.52，被 `scale` 吸收，对排序零影响）。现替换为**真 MD**：逐峰按该峰 hkl 与 PO 轴（倒格矢 metric 夹角）乘积分强度权重 `(r²cos²α + sin²α/r)^(-3/2)`，r = MD_R = 0.75（板状织构，轴上增强 ~r⁻³≈2.4×）。库卡 hkl + 晶胞（5.2 回填）驱动几何；无 hkl 峰权重 1。

**FPFM 拟合侧**（`xinmatch/core/search/fpfm.py`）：
- `march_dollase_cos(entry, po_axis)`：逐峰 cos α（倒格矢 metric：a*/b*/c*/cosα*/β*/γ* 由 `CellParams` 计算；`Entry.hkl` 缺行 → nan，nan 峰权重 1——部分标注卡只在标注反射上织构）。
- `expand_reflections_po`：cos 数组随 Kα1/Kα2 双线 + 2θ 范围过滤同步展开。
- `generate_theory_profile(..., march_cos, march_r)`：amps ×= `(r²cos²α + sin²α/r)^(-3/2)`。
- `fit_candidate`：`FpfmConfig.march_po`（默认 **False** 保持旧行为；`po_axis` 默认 (0,0,1)、`march_r_init=1.0`、边界 (0.3,3.0)）开启时参数向量尾部加 `march_r`；`CandidateFit.march_r` + score_dict `march_r` 键。

**验收（真 MD 可辨识性闭环）**：
- 单元：MD 权重公式（r=1 恒等 / r<1 轴上 r⁻³ 增强、垂直 r^{3/2} 削弱 / nan→1）、六方几何（002/004 cos=1、100 cos=0）、Kα2 cos 复制、profile 轴上峰增强 >3×；`tests/search/test_fpfm.py` +7 项。
- 恢复性：构造六方织构谱（r=0.6）→ `fit_candidate(march_po=True)` 恢复 **r≈0.6**、Rwp 优于无织构模型；无织构谱不误报（r≈1）。
- **端到端**（`test_march_po_recovers_textured_zirconia`，slow）：生成器真 MD 织构 Zirconia 谱 → `search_match_fpfm(march_po=True)` 真相回 **Top-1**、Rwp < 无织构模型、拟合 r<1。
- **合成谱验收**：13 组谱用真 MD 生成器**重新生成**（seed 42），peak-list Top-20/Top-5 与 FPFM Top-20/Top-5 全部保持（**注**：单相 Zirconia 的 (-1,1,1) 织构在 r=0.75 下已使 peak-list 掉出——peak-list 强度失配是真实物理；该样本去织构，6 组多相织构样本保留，MD 端到端由专项测试覆盖）。
- 全量核心回归（无 UI/无 pdf2_source_config）：**全部通过**；ruff 本轮文件全绿；mypy 本轮文件 0 错误（其余 8 处为 preprocess/model/fom_criteria 存量噪音）。

**提交**：`(本提交)`。

---

## T14.4 串口仪器控制（2026-10-14）✅

**任务**（路线图 Phase 14 最后一项）：串口配置、数据采集、实时图谱（对应参考软件 Qt5SerialPort，P2 可选）。

**交付**：
- `xinmatch/core/instrument/serial_port.py`：`list_serial_ports()`（无串口栈时返回空列表 + warning，不抛异常）；`open_serial()`（pyserial 懒加载；用 `serial_for_url` 支持 `loop://` 等 URL 协议，普通 COMx 照常）。
- `xinmatch/core/instrument/collector.py`：`parse_point`（逗号/空格/TAB/全角逗号/分号/科学计数；注释行/空行/单数/纯文本跳过）；`iter_lines`（EOF / stop_event / max_lines 三停止条件）；`SerialCollector`（流式解析 + `on_point` 逐点回调——GUI 实时绘制的标准接入点；`n_raw_lines/n_parsed/n_skipped` 计数；两列 ASCII 落盘可被 `load_pattern` 直接导入）。
- CLI：`xinmatch instrument scan`（枚举串口 JSON/文本）；`xinmatch instrument collect --port … [--baud/--bytesize/--parity/--stopbits/--timeout/--seconds/--max-points/--out/--verbose/--live-plot]`（流式采集；`--live-plot` matplotlib 懒加载实时绘制，缺失自动降级不中断采集）。
- pyproject 正式依赖 + `pyserial>=3.5`（venv 实测 3.5）。

**验收**（详见 `docs/ACCEPTANCE-T14.4-20261014.md`）：`tests/instrument` 37 + `tests/test_batch_core.py` + `tests/cli/test_cli.py` = 65 passed；`tests/test_batch_runner.py` 4/4（batch.py 改动回归）；ruff 本轮文件全绿；mypy 本轮零新增（全仓剩 12 处已登记存量）；CLI 实跑 scan（空列表 exit 0）/ collect --help 正常。顺带清偿 T14.3 欠账：`batch.py` 3 处 mypy 错误（`pattern_path` 窄化断言、`peaks: list[Any]` 注解、`_resolve` 误用 `config_dir`→`base_dir`）。

**边界**：GUI 串口采集面板留后续（core 的 `on_point` 回调即接入点；本机无真实仪器可验收）；真实硬件联调与二进制/专有协议报文需用户仪器实测样本（core 解析为单函数 `parse_point`，扩展点单一）。

---

## v1.6.0 版本发布（2026-10-15）✅

**版本**：1.5.0 → 1.6.0（增量 = 1.5.0 后全部开发：T6.0 检索预筛 + T14.3 批处理 + T14.4 串口 + T2.4 Bruker RAW + T0.2 版本 diff + T0.5 术语表 + T0.3/T0.4 TiO₂ 定量验证）。

**验证**：核心套件 **1089 passed / 0 failed / 46 skipped**（5668s，含全部 slow）；UI（python310）**209 passed / 0 failed**；ruff 全量 All checks passed；mypy **109 files 0 errors**（本轮清偿 24 处存量：ruff 6 + mypy 18——14 处 Qt/numpy `no-any-return` 标注、fom_criteria 3 处 `arr.max()`→`np.max()`、le_bail np.trapz→getattr 双备、cli matplotlib/DataPoint、backfill_cells numpy、fpfm ternary、test_fpfm import 排序）。

**产物**：`dist/xinmatch-1.6.0/`（onedir，DB 不内置）+ `dist/xinmatch-cod-db-1.6.0.zip`（210.2 MB，zip 内 `data/cod_inorganics.db`）+ `dist/XinMatch-Setup-1.6.0.exe`（Inno Setup 单文件安装版，DB 单独挂载）+ `dist/XinMatch-Portable-1.6.0.zip`（便携，本地保留）。

**Release**：GitHub `v1.6.0` 上传 Setup exe + DB zip（便携包本地）；验收 `docs/ACCEPTANCE-v1.6.0-20261015.md`。

---

## v1.6.1 版本发布（2026-10-16）✅

**版本**：1.6.0 → 1.6.1（小幅版本升级：SMPF 更名为 **FPFM（Full Pattern Fitting Match）**，无功能变更；含 2026-10-15/16 并行会话合并的 March-Dollase 择优取向修正 `33a7f45`）。

**更名范围**（commit `cc12b9c`，30 文件）：模块 `core/search/smpf.py` → `fpfm.py`，全部类/函数/常量更名（`FpfmConfig`、`search_match_fpfm`、`SEARCH_MODE_FPFM_FULL` 等）；UI 文案、术语表（`docs/TERMINOLOGY.md` 词条 50）、README 状态行同步更新；5 处版本号同步（pyproject / spec / build_exe.ps1 / iss / README），`xinmatch.__version__ == 1.6.1` 实测通过。

**向后兼容**（三层，附 3 个回归测试）：
1. CLI `--mode smpf` 保留为别名，静默归一化为 `fpfm`（帮助文本注明 legacy）；
2. 批处理 `mode: smpf` 在 `_validate_config` 原位归一化为 `fpfm`；
3. 持久化配置键 `smpf_kalpha*` 在 `load_config` 合并前迁移为 `fpfm_*`（先迁移再合并，旧用户设置仍优先于新默认值）；`SEARCH_MODE_SMPF_FULL` 值仅运行时使用、不落盘，无需迁移。

**验证**：ruff 全量 All checks passed；mypy 109 files 0 errors；核心套件 + UI/CLI 套件（python310 offscreen）全绿（详见验收文档）。

**产物**：`dist/xinmatch-1.6.1/`（onedir）+ `dist/xinmatch-cod-db-1.6.1.zip` + `dist/XinMatch-Setup-1.6.1.exe` + `dist/XinMatch-Portable-1.6.1.zip`（便携，本地保留）。

**Release**：GitHub `v1.6.1` 上传 Setup exe + DB zip；验收 `docs/ACCEPTANCE-v1.6.1-20261016.md`。

---

## v1.7.0 版本发布（2026-10-16）✅

**版本**：1.6.1 → **1.7.0**（增量 = 注册机制 + 双二进制构建变体）。

**注册机制**（commit `98b086b`，复用 `D:\Project\XRD\PolyXRD-Reg`）：
- `xinmatch/utils/registration.py`：PolyXRD 家族注册模块**逐字副本**（490 行，零三方依赖，PySide6 延迟导入）。注册码 `PXRD1-XXXX-…` = Base32(`UTF8(单位部门名称)` + `0x00` + `HMAC-SHA256(密钥, 单位名)[:8]`)，软件端重算校验并还原单位名；无需联网/机器码，同单位可多台电脑使用。与家族注册机出码**逐字节一致**（交叉验证通过）。
- 行为：未注册每次启动弹出「本软件未注册，版权所有，禁止用于商业用途。如需注册请联系 sshztx@outlook.com」→「确定」关闭并继续使用／「输入注册码」完成注册；帮助菜单固定「输入注册码 (&R)…」；状态栏最右端显示「已注册：\<单位部门名称\>」/「未注册」。状态文件 `%APPDATA%/XinMatch/XinMatch/registration.json`，每次启动重校验，**手改 JSON 伪造已注册无效**。
- 出码工具：`tools/make_reg_code.py`（脚本化，与家族 `PolyXRD-RegTool.exe` 互通）。

**双二进制构建变体**：
- **正式版 release**：`XinMatch-Setup-1.7.0.exe`（Inno Setup，安装时可选安装位置；DB 仍单独挂载）→ 含注册机制；
- **内部评估版 internal**：`XinMatch-Internal-1.7.0.zip`（免安装，自用）→ 不接入注册机制，状态栏最右端固定「内部评估版本」。
- 变体由随包 `variant.txt` 标记固化（`xinmatch/utils/build_variant.py`）；环境变量 `XINMATCH_VARIANT` **仅在源码运行时**生效（冻结二进制忽略，防止绕过注册提示）；标记缺失按 release 处理（fail-safe）。构建脚本 `tools/build_exe.ps1 -Variant release|internal` 并校验标记内容。

**验证**：ruff 全量 All checks passed；mypy **112 files 0 errors**；UI+CLI 套件 **247 passed / 0 failed**（含新增 10 项注册 UI 测试）；核心套件 **1112 passed / 0 failed / 5 skipped**（5406s，含全部 slow）。新增 `tests/utils/test_registration.py`（21 项：出码/校验/容错/篡改防护/变体解析）。

**冻结二进制冒烟**（`XINMATCH_SELFTEST_REG=1`）：release → `{"variant":"release","registration_enabled":true,"status_text":"未注册"}`；写入注册码后 → `"已注册：内部冒烟测试单位"`；internal → `{"variant":"internal","registration_enabled":false,"status_text":"内部评估版本"}`。

**Release**：GitHub `v1.7.0`（仓库为内部库，内部版 zip 一并上传）；验收 `docs/ACCEPTANCE-v1.7.0-20261016.md`。

---

## v1.7.1 版本发布（2026-10-18）✅

**范围**：全量代码评审结论落地（评审与逐条方案见 [`CODE_REVIEW-20261018.md`](CODE_REVIEW-20261018.md) §7）。

**缺陷修复（P0）**：GUI 检索连接泄漏（每次检索 `close()`，`run_with_busy` 返回 `bool` 供重入路径补关）；
`search_by_d` 在 `d ≤ λ/2` 时的 `math.asin` 越界（跳过并记录）；`recall_max_candidates` 覆盖 restraints
模式（宽限制由 7 万条降到 ≤ 上限）；wheel 补 `schema.sql` + 3dmol 资源声明（实测 wheel 124 条目）；
`__version__` 无 dist-info 时回退；`PatternView.clear()` 被 pyqtgraph 实例属性遮蔽的真实 bug。

**性能（P1）**：`fetch_entries_by_ids` 由 N 次查询改两趟分块（N → ⌈N/500⌉）；
Hanawalt top-K 缓存加 DB 指纹（mtime/size）+ 锁 + LRU(2)，修掉「重建库后仍用旧排名」；
新增 `fpfm.to_candidates()` 统一 GUI/批处理/CLI 的结果组装。

**体验**：打开数据文件走忙碌窗口（大 raw/brml 不冻结）；FPFM 等长任务支持**协作式取消**
（`core/cancel.py`，不强杀线程）；5 个占位工具栏菜单接线为可用功能（背景扣除/平滑/Kα2 剥离/
重置原始数据/峰检测）。

**工程化**：新增 GitHub Actions（ubuntu+windows × py3.10/3.12；ruff + mypy + 默认测试 + wheel 资源断言）
与本地 `tools/ci.ps1`；`slow` 标记补齐并默认排除（`pytest` 现在可直接运行，`pytest -m slow` 跑全量）；
去掉硬编码 `D:\Project\...` 默认库路径；SQLite URI 与 LIKE 通配符转义；`docs/README.md` 索引 +
`tools/clean_data_backups.ps1`。

**验证**：ruff **All checks passed**；mypy **113 files 0 errors**；默认套件 **1297 项 / 0 失败 / 7 跳过**
（794.9 s，排除 slow）；冻结 `XinMatch.exe import --help` exit 0、internal 变体注册自检 JSON 正确。

**产物**：`dist/XinMatch-Setup-1.7.1.exe`（180,895,295 B）+ `dist/XinMatch-Internal-1.7.1.zip`
（265,449,143 B）+ `dist/xinmatch-cod-db-1.7.1.zip`（204,614,250 B）+ 两套 onedir。

**Release**：GitHub `v1.7.1`；验收 `docs/ACCEPTANCE-v1.7.1-20261018.md`。

**推迟**：`core/pipeline.py` 三入口统一（UI 与 CLI 预处理语义不同，需配真实库回归）、
`main_window.py` 拆分（1112 行）、注册机制升级为 Ed25519（会作废已发注册码）、
`data/*.bak-*` 清理（仅提供脚本，待确认）、`slow` 套件补跑。



---

## v2.0.0 版本发布（2026-10-20）✅

**版本**：1.7.1 → **2.0.0**（大版本，因为数据库使用方式变了）。

**主特性（`c0b1a56`）：PolyXRD `.sqlite` 直接挂载**

外部参考库不再需要拷进安装目录：`设置 → 参考数据库 → 添加外部库`（或
`xinmatch libraries --add <path>`）即可挂载任意位置的 `*.sqlite` / `*.db`。
新增 `core/db/polyxrd.py` 做 schema 判别（`xinmatch` / PolyXRD `phases` / PolyXRD `cod_entries` 结构库 /
未知），PolyXRD `phases` 库一次性转成原生 schema 的 sidecar（`<用户数据>/indexes/external/`，
源文件只读、按 `mtime+size` 指纹失效、可取消）；`libraries.json` 记录挂载项；
结构型 dump（`cod_index.sqlite`）明确拒绝并说明原因。

配合 PolyXRD 侧全面改用 `.sqlite` 扩展名，XinMatch 在预期路径处等价接受 `.sqlite` / `.db`。

**验收中修掉的 3 个发布缺陷（只在冻结+打包阶段暴露）**：

1. **冻结版 `libraries` 不走 CLI**：`tools/pyi_entry.py` 硬编码子命令集漏了 `libraries`
   （还有 `batch`、`instrument`），`XinMatch.exe libraries --add …` 会当成未知子命令**直接开 GUI**，
   功能形同虚设。改为从 `build_parser()` 运行时推导 + 新增 `tests/tools/test_pyi_entry.py`（12 项）。
2. **变体传递不可靠会删掉另一个变体**：`-File` 嵌套调用时环境变量没到子进程，internal 构建
   算出 release 的 `BUNDLE_NAME`，PyInstaller 的 COLLECT 先删 `dist\xinmatch-2.0.0\` 再写。
   改为**文件传递**（`build/variant.request` 优先于环境变量）+ 构建前校验。
3. **`.ps1` 无 BOM + 中文注释**：PS 5.1 按 ANSI 解码，字节落在行尾反斜杠时把下一行并进注释
   （表现为 `$LASTEXITCODE` 为空、`Join-Path` 收到 `$null`）。改为 UTF-8 带 BOM。

**配套**：`run_dev.bat`（免打包运行工作树）；3COD 库验收（`docs/ACCEPTANCE-3COD-20261020.md`）
与按来源分库 `tools/split_3cod.py`（COD 7.9 万 / PCOD 106 万 / TCOD 4.7 万，
PolyXRD 只挂实验 COD，PCOD/TCOD 只给 XinMatch）。

**验证**：ruff **All checks passed**；mypy **114 files 0 errors**；
默认套件 **1351 项 / 0 失败 / 7 跳过**（742.7 s，排除 `slow`）。
两个变体的冻结二进制全部通过：`import --help`、`libraries --json`、
`libraries --add`（78,747 条、`needs_index=false`）、`search`（Al₂O₃ FoM 0.802，真值第 2）、
注册自检（release `未注册` / internal `内部评估版本`）。本轮 release 变体的 GUI 自检**首次跑通**
（v1.7.1 那次被注册弹窗阻塞）。

**产物**：`dist/XinMatch-Setup-2.0.0.exe`（180,974,864 B）+ `dist/XinMatch-Internal-2.0.0.zip`
（265,471,156 B）+ `dist/xinmatch-cod-db-2.0.0.zip`（204,614,240 B）+ 两套 onedir（681 MB/套）。

**Release**：GitHub `v2.0.0`；验收 `docs/ACCEPTANCE-v2.0.0-20261020.md`。

**推迟**：`slow` 套件补跑、实机静默安装、`max_peaks=64` 保真对照、
`core/pipeline.py` 三入口统一、`main_window.py` 拆分、Ed25519 注册升级。

## v3.0.0 版本发布（2026-10-23）✅

**版本**：2.0.0 → **3.0.0**（参考库格式收口为单一 `.xinDB`，默认库随包内置）。

**主特性（`7605e06`）**

- **`.xinDB` v3 列存单一格式**：单文件 SQLite，`meta` / `entries` / `peak_chunks`
  （每 4096 相一块的 CSR + 预筛矩阵）/ `element_inv` 四张表；只读打开、
  `journal_mode=DELETE`、无 `-wal/-shm` 侧车，可直接放 NAS 只读共享。
- **三个无机物库按来源分库**：`COD-Inorg` 78,036 相 / `PCOD-Inorg` 1,061,953 相 /
  `TCOD-Inorg` 46,846 相，`entry_id` 号段 0 / +2e7 / +1e8 互不遮蔽
  （库本体在 `XinMatch-DataBase` 仓库发布，不入本仓）。
- **默认库内置**：便携包 `<exe>/data/COD-Inorg-<快照>.xinDB`，安装即能检索；
  运行期库目录解析 `XINMATCH_XINDB_DIR` → `<exe>/data` → `<exe>/_internal/data` →
  `../XinMatch-DataBase/data`（源码态）。外部 `.xinDB` 可从任意目录挂载。
- **旧格式运行期代码删除**：v2 行表读取、PolyXRD dump、PDF-2 转换层删除；
  `search_match` 按对象类型分派到 `search_match_v3`（评分/排序仍是原 v2 代码）。
- **内部评估版**：状态栏右侧红色加粗「内部评估版本」；正式版保留注册机制。

**发布时记录**：`pytest tests` 1570 passed / 4 skipped / 1 xfail（12m14s）。
> 该数字复现不出来：同一份 v3.0.0 源码 2026-10-24 复验为
> **1347 passed / 6 skipped / 51 deselected / 1 xfailed**（16m47s，`QT_QPA_PLATFORM=offscreen`，
> 含 `slow` 之外的 1354 项）。发布记录里 tests/ui 实际未跑（v3.0.0-验收报告 §5 自述），
> 所以「全量 1570 passed」应按本次复验更正。详见 `docs/CODE-REVIEW-v3.0.0-20261024.md`。

**产物**：`XinMatch-Setup-3.0.0.exe`（256,400,880 B）+ `XinMatch-Internal-3.0.0.zip`
（356,466,971 B）+ `XinMatch-Databases-COD-Inorg-3.0.0.zip`（91,175,782 B）+ `SHA256SUMS.txt`；
三个附件的 SHA-256 与 `SHA256SUMS.txt` 逐位一致（2026-10-24 复核），
分发包内的 `.xinDB` 与已验收库逐字节相同。

**Release**：GitHub `v3.0.0`；验收 `docs/ACCEPTANCE-v3.0.0-20261023.md`、
`docs/v3.0.0-验收报告.md`、`docs/ACCEPTANCE-3COD-20261024.md`。

## v3.0.0 全面复验与修复（2026-10-24）✅

**范围**：代码审查 + 静态分析 + 真实缺陷修复 + 检索性能优化 + 三库独立验收 + 文档一致性。
完整报告 `docs/CODE-REVIEW-v3.0.0-20261024.md`。

- **静态门恢复 green**：`ruff check xinmatch tools tests` **0 error**（复验前 218）、
  `mypy` **119 files 0 error**（复验前 6）。此前 v3.0.0 未跑质量门，CI 实际是红的。
- **修真实缺陷**：峰引擎 180° 边界假峰（COD 5 + PCOD 7 个相只剩 d=0.7703 假峰）、
  gemmi 默认晶胞假峰（3 相，含晶胞恢复）、`batch --json` stdout 被进度行污染、
  `report --input-report` 崩溃/静默空报告、GUI 配置非原子写 + 损坏即崩、
  参考库异常逃逸 Qt 槽、坏 `XINMATCH_XINDB_DIR` 覆盖导致内置库静默不可用、
  冻结包漏收 `atomic_scattering_params.json`、`reader_v3` 路径含 `#` 的 URI 转义。
- **性能优化**：`reader_v3` prescreen 行块化 + `fetch_peaks` 按 chunk 定位/仅解码命中块 +
  mmap；候选集/排序逐位等价（3 库 parity）。
- **三库验收**：`validate_xindb` COD 0F/1W、PCOD 0F/0W、TCOD 0F/0W；
  全量独立复核（118 万条 id、全部 chunk）0 违规；自召回 COD 38/40、PCOD 40/40、TCOD 40/40。
  已知坏相（COD 8、PCOD 7）登记在 `docs/ACCEPTANCE-3COD-20261024.md`，
  峰引擎已修、重建 COD/PCOD 即可清除。
- **参考库构建/验收工具链重建（2026-10-24，姊妹仓库 `XinMatch-DataBase`）**：
  六库统一构建入口（`COD/PCOD/TCOD × Inorg/Full`）、单 CIF 单次解析
  （`build_pipeline.compute_phase`）、结构因子分块按原子数自适应（构建吞吐 ~+10–15%）、
  `validate_xindb` 新增 E5/E6 坏相检查、新增 6 库通用 `accept_xindb`、仓库内合成夹具测试
  （152 项）。**约定**：库统一在 `XinMatch-DataBase` 构建（默认 `<repo>/data/`），
  CIF 源统一在 `../sync-COD`（`XRD_DATA_ROOT` 可覆盖）；详见该仓库
  `docs/构建与验收手册.md`。本机 `--workers` 实测 8 最优（8C/16T）。




## 参考库重建与 Full 库构建（2026-11-01/04）✅

**范围**：用修复后的峰引擎（2θ=180° 边界 + 占位晶胞）重建 3 个 Inorg 库，并新建 2 个 Full 库；
PCOD-Full 因 PCOD 全为无机（manifest 1,061,962/1,061,962 is_inorg=1）与 PCOD-Inorg 实质等价，按决定跳过。

| 库 | 相数 | 反射数 | 体积 | 构建 | 验收 |
|---|---:|---:|---:|---|---|
| COD-Inorg | 78,035 | 9,395,681 | 113.1 MiB | 61.6 min | validate 0F/1W；accept 0F/1W |
| TCOD-Inorg | 46,846 | 5,874,790 | 68.0 MiB | 15.2 min | validate 0F/1W；accept 0F/1W；与旧库峰载荷逐字节相同 |
| PCOD-Inorg | 1,061,953 | 159,275,318 | 1694.1 MiB | 13.3 h | validate 0F/1W；accept 0F/1W；7 条坏相全恢复 |
| TCOD-Full | 361,701 | 53,099,238 | 594.3 MiB | 12.1 h | validate 0F/2W；accept 0F/1W |
| COD-Full | 532,038 | 77,458,154 | 879.4 MiB | 36.4 h | validate 0F/2W；accept 0F/2W（bad_phase_ids=0） |

- **坏相清零**：COD 8 条（7 恢复 + 96-210-4629 无晶胞剔除）、PCOD 7 条全部恢复；三 Inorg 库 
_peaks<=1 均为 0。
- **等价性**：COD/TCOD/PCOD-Inorg 与旧库逐条目对比，只变化坏相（COD 7 条、PCOD 17 条），其余逐字节相同；
  Full 库与对应 Inorg 库的公共相**逐字节相同**（COD 78,035/78,035、TCOD 46,846/46,846，0 差异）。
- **产物位置**：D:\Project\XRD\XinMatch-DataBase\data\
  COD-Inorg-20261020.xinDB、TCOD-Inorg-20261020.xinDB、PCOD-Inorg-20261020.xinDB、
  TCOD-Full-20261020.xinDB、COD-Full-20261020.xinDB；旧库与旧 `20261020` Release 已于 2026-11-04 删除，重建版发布为 GitHub Release `20261020-rebuild`。
- **应用侧自检**：清空 XINMATCH_XINDB_DIR 后 libraries --json → 5 个库全部 available=true，
  entries 分别为 78,035 / 46,846 / 1,061,953 / 361,701 / 532,038。
- **工具链修正**：真实全库构建 --workers 14 更优（TCOD 14w 15.2 min vs 旧实现 16.9 min；
  COD 8w 61.6 min 反而略慢于历史 14w 58 min），此前“8 最优”结论仅适用于小切片基准。
- **验收记录**：姊妹仓库 XinMatch-DataBase 的
  docs/ACCEPTANCE-20261101-rebuild.md（提交 8679bf0/1bb9c63/4b36f0/13e85b9）。
- **已知提示**：TCOD-Full 48,732 相 / COD-Full 81,284 相的元素超出 63 位 lem_mask
  （ntries.elements 与 lement_inv 完整，按元素检索不受影响）；半塌缩边界 WARN 属峰口径边缘现象，不阻塞。

## Materials Project 外部库 MP-20261031（2026-11-04）✅

**范围**：把 `D:\Project\MP-summary` 的 Materials Project summary CIF（155,204 个）按 `.xinDB` v3 外部库格式构建为
`MP-20261031.xinDB`，并完成结构/产品/端到端验收。源数据与产物：

| 项 | 值 |
|---|---|
| CIF 源 | 155,204（平铺，文件名为化学式；3 个无 `# mp-id:` 头跳过） |
| 相数 / 反射数 | **155,201 / 20,900,193**（38 chunk） |
| 体积 / SHA-256 | **251,633,664 B** / `26D7A9BE…5289EE20`（zip 197,925,329 B） |
| 构建 | **9.0 min**，17,318 相/分钟（14 workers），errors=0 |
| 验收 | validate --all-chunks **0F/1W/29**；accept **0F/1W/19**（id 集合与归档 155,201 个 mp-id 完全一致，bad_phase_ids=0）；自重召回 Top-1/Top-5 20/20（中位 0.52 s） |

- **id 约定**：`mp-<number>`（MP 原生 id，如 `mp-862690`），号段 `[0, 20,000,000)`；不套 COD 的 `96-` 前缀。
- **空间群**：pymatgen 把结构写成 P1，真实空间群只在注释 `# mp-id: ... | spacegroup: ...`；
  构建器用注释覆盖 `entries.space_group` 并推导晶系（225 个符号 / 7 个晶系，全量核对与归档一致）。
- **tier = 2**（DFT 计算结构）；journal/author = Materials Project、quality = DFT。
- **挂载**：`python -m xinmatch.cli.main libraries --add D:\Project\XRD\XinMatch-DataBase\data\MP-20261031.xinDB --label "Materials Project"`；
  已实测挂载为外部库 `ext_567de5034377`，available=true，entries=155201。
- **代码**（姊妹仓库 `XinMatch-DataBase` 提交 `19a01b3`）：`mp_scan.py`、`build_mp_xindb.py`、
  `build_cod_xindb.build(id_mode="mp")`、`accept_xindb --mp-root` 全集归属、`tests/test_mp_scan.py`。
- **已知 WARN**：5,660 条半塌缩边界相（真实反射 + LP 在 180° 发散，非假峰），不阻塞。
- **记录**：`XinMatch-DataBase/docs/MP-库构建与验收.md`、`docs/release-notes-20261031-mp.md`；
  Release [`20261031-mp`](https://github.com/PolyXRD/XinMatch-DataBase/releases/tag/20261031-mp)
  （MP-20261031.xinDB.zip 197,925,329 B，SHA-256 `d20c4a61…` + SHA256SUMS.txt）。

## v3.2.0 发布（2026-11-04）✅

**范围**：相位级身份（同相异卡识别 + 候选列表折叠）、两套检索基准（13 组合成谱 + 13 组真实谱）、
预筛名额双路分配（默认 1000 / 20%）、新 logo 与启动图。详见 `docs/RELEASE-NOTES-v3.2.0.md`。

| 附件 | 字节 | SHA-256（前 16 位） |
|---|---:|---|
| `XinMatch-Setup-3.2.0.exe` | 254,143,458 | `350b24cfe0ffb669…` |
| `XinMatch-Internal-3.2.0.zip` | 353,721,811 | `96e818ee29cbe545…` |
| `SHA256SUMS.txt` | 185 | — |

- **二进制稳健性 5 轮全通过**（可复跑 `tools/verify_binary.py`，报告 `.scratch/binary_verify_320.json`）：
  哈希清单回读一致；便携解包 3556 文件 / 785 MiB、随包 logo 与源码逐字节一致、冻结 CLI 识别内置库 78,035 相；
  冻结 GUI 三钩子（REG / LIBS / ABOUT）+ 3 次冷启动 exit 0；`/VERYSILENT /CURRENTUSER` 静默安装成功；
  安装后真实谱检索 118 峰 → 5 候选、榜首 `96-210-0189`，安装包与主程序 `ProductVersion=3.2.0`。
- **全量回归**：1477 项 1472 passed / 4 skipped / 1 xfailed / 0 failed（13m27s）；ruff 全通过、mypy 121 文件 Success。
- **基准终态**：合成谱相位级 Top-1 11/13、Top-5 12/13、序贯 10/13、相召回 19/24；
  真实谱 Top-1 10/12、Top-5 12/12、卡级 24/43、族级 27/43、序贯 5/12。
- **外挂数据库**：两个二进制均内置 `COD-Inorg-20261020.xinDB`；更大的 PCOD / TCOD / Full / MP 库在
  [`XinMatch-DataBase` Releases](https://github.com/PolyXRD/XinMatch-DataBase/releases) 分发，
  下载解压后经「设置 → 参考数据库…」或 `XinMatch.exe libraries --add <path>` 挂载，可多库并存。

## v3.3.0 发布（2026-11-05）✅

**范围**：少线相**强线锚定标记**（`AnchorPolicy` + `ResidualSearchResult.anchored_ids` + 候选表 ★），
排序默认不变。详见 `docs/RELEASE-NOTES-v3.3.0.md`、基准报告 §11.5。

| 附件 | 字节 | SHA-256（前 16 位） |
|---|---:|---|
| `XinMatch-Setup-3.3.0.exe` | 254,071,430 | `6e93c548dbd09ad8…` |
| `XinMatch-Internal-3.3.0.zip` | 353,728,377 | `71f410fbef7eedad…` |
| `SHA256SUMS.txt` | 190 | — |

- **二进制稳健性 5 轮全通过**（`tools/verify_binary.py`，报告 `.scratch/binary_verify_330.json`）：
  哈希清单回读一致；便携解包 variant=internal、内置库 118,640,640 B / 78,035 相、随包 logo 逐字节一致；
  冻结 GUI 三钩子（REG=内部评估版本 / LIBS=10 条库 / ABOUT PNG 9,117 B）+ 3 次冷启动 exit 0；
  `/VERYSILENT /CURRENTUSER` 静默安装 variant=release 成功；安装后真实谱检索 118 峰 → 5 候选、
  榜首 `96-210-0189`，GUI 钩子 `variant=release, registration_enabled=true, 未注册`。
- **验收工具修复**：`verify_binary` 的 `--workdir` 传相对路径会让轮 3/4 把相对路径交给子进程
  （cwd 即 work 目录）→ 冻结 GUI 写文件抛 `FileNotFoundError` 被 Qt 吞掉、表现为自测超时 +
  静默安装 rc=1。`main()` 现在先 `resolve()` 所有输入路径。
- **全量回归**：1488 项 1483 passed / 4 skipped / 1 xfailed / 0 failed（15m27s）；ruff 全通过、
  mypy 121 文件 Success。
- **基准终态（默认口径与 v3.2.0 逐项相同）**：合成谱相位级 T1 11/13、T5 12/13、序贯 10/13、
  相召回 19/24；真实谱 T1 10/12、T5 12/12、卡级 24/43、族级 27/43、序贯 5/12。
  开启 `promote_anchored=True`：合成 11/13 · 21/24，真实 4/12（故默认关闭）。

## v3.4.0 发布产物（2026-11-05，二进制已验收；GitHub Release 待批准）

**范围**：与 **XinRefinement 1.1.0** 打通「检索 → 精修」家族链路。新增
`文件 → 导出物相分析（.xinm）…`：谱图（CSV `%.10g`）+ 已选物相 COD CIF + 峰表
装进自包含 zip；CIF 回取靠 `core/refine/cif_store.resolve_entry_cif` 的多根探测链
（`XINMATCH_COD_ROOT` → 当前档案根 → 历史根）。参考库格式、FoM 权重、排序、命令行
**全部不变**。详见 `docs/RELEASE-NOTES-v3.4.0.md`、格式契约 `docs/JOINT_PLAN_xinm_xinr.md` §8。

| 附件 | 字节 | SHA-256（前 16 位） |
|---|---:|---|
| `XinMatch-Setup-3.4.0.exe` | 254,139,154 | `4962defa7d0e4cf7…` |
| `XinMatch-Internal-3.4.0.zip` | 368,486,794 | `fb82ce897bf4227a…` |
| `SHA256SUMS.txt` | — | — |

- **二进制稳健性 5 轮全通过**（`tools/verify_binary.py`，报告 `.scratch/binary_verify_340.json`，
  `all_pass=true`）：哈希清单回读一致；便携解包 variant=internal、内置库 118,640,640 B / 78,035 相、
  随包 logo 逐字节一致；冻结 GUI 三钩子（REG / LIBS=10 / ABOUT）+ 冷启动 exit 0；
  `/VERYSILENT /CURRENTUSER` 静默安装 variant=release；安装后真实谱 `5-1.txt` 118 峰 → 5 候选、
  榜首 `96-210-0189`（与 v3.3.0 逐位一致）。
- **顺带修掉的版本号缺陷**：冻结包无 `pyproject.toml`，`site-packages` 残留
  `xinmatch-1.7.1.dist-info` 会让 `importlib.metadata` 报 1.7.1，污染 About 与 `.xinm`
  的 `app.version`。现在冻结态取 `__init__._FALLBACK_VERSION`，`xinmatch.spec` 构建时断言
  它等于 `APP_VERSION`（不同步直接失败）；CLI 补 `--version` / `-V`（此前会误开 GUI）。
- **环境修正**：`XINMATCH_XINDB_DIR` 由已不存在的 `PolyXRD-DataBase\xindb` 改为
  `XinMatch-DataBase\data`（库实际位置），消除启动时"目录下没有 .xinDB"告警。

## PDF-2 参考库迁到 `.xinDB`（2026-11-05）

**背景**：v3.0.0 删掉了全部旧格式读取路径（含 PDF2 dump + 侧车索引），此后 ICDD PDF-2
在 XinMatch 里没有可挂载的形态。本次按 `.xinDB` v3 外挂库规范重新打包，读取侧零改动。

| 项 | 值 |
|---|---|
| 源 | `C:\pdf2\pdf2.dat`（587,999,120 B，80 字符定宽流，7,349,989 行） |
| 产物 | `D:\Project\XRD\XinMatch-DataBase\data\PDF2-20040317.xinDB`（172,302,336 B / 164.3 MiB） |
| 规模 | **163,834 相 / 10,445,852 反射 / 40 chunk**，建库 **41 s** |
| 对比旧格式 | `PDF2_2004.sqlite` 214,454,272 B → **小 19.7%** |
| meta | `library_kind=PDF2`、`data_date=20040317`、`tier_default=0`、**`peak_origin=observed`** |
| 验收 | `validate_xindb` **30 项 0 FAIL / 2 WARN**；自召回 120 相 **119 top-1 + 1 top-5 + 0 漏** |

**关键设计决定：PDF-2 不是计算库。** 峰是几十年文献实测的相对强度，不是由 CIF 算的。
照抄 `peak_convention` 的冻结串就是对文件撒谎，所以新增 `meta.peak_origin`
（`computed` 缺省 / `observed`）；实测库自报 `observed-ICDD-PDF2-2004-norm1000`，
强度仍归一 1000（两类库共用一把尺子，否则打分权重不可比）。验收器据此切换三条判据
（口径、NULL 晶胞、峰数上限），缺省 `computed` 让三个既有库的结论一字不变。

**兼容格式清理**（本仓）：

- `ui/icons.py`：删掉 `"pdf2"` 图标 —— 全仓无引用，是 v2 时代的残留。
- `core/io/xinm.py`：`source` 现在把 `PDF2-<卡片号>` 判为 **`pdf2`** 而非 `unresolved`。
  两者对精修端含义不同（「本来就没结构」vs「本该有结构却没找到」），混用会让缺结构原因写错。
  分类收拢到一个 `_classify_entry()`，三处调用点不再各写一遍。
- `core/db/multi_db.py` / `ui/dialogs/library_dialog.py`：错误提示与 tooltip 补一句
  「PDF-2 请用 `tools.build_pdf2_xindb` 打成 `PDF2-<日期>.xinDB` 再挂载」。

**版权边界**：产物不入 git、不进 Release。`PolyXRD/.gitignore` 补 `**/PDF2*.xinDB` 与
`cod_data/*.xinDB`（此前 165 MB 的 ICDD 派生文件在 `git status` 里是未跟踪状态，`git add -A`
会收进去）；`XinMatch-DataBase/tools/package_release.py` 的默认 glob 现在主动跳过 `PDF2*`。
构建/验收细节见 XinMatch-DataBase `docs/PDF2-库构建与验收.md`。

## 下一步计划（2026-11-05 排定）

v3.4.0 发布 + PDF-2 接入本仓后，按「先自洽基准、再动引擎」的原则排定如下顺序。每项标注依据与阻塞，避免用非同源尺子校准算法。

| 优先级 | 事项 | 依据 / 为什么是下一步 | 阻塞 / 依赖 |
|---|---|---|---|
| **P0** | **PDF2 真实链路验收（联合计划 S2）** | `source="pdf2"` 此前只由合成 manifest 覆盖，没有真实条目走通 `.xinm` 导出（`structural=false`、不打包 ICDD 文件）→ 导入端「仅参照」分支。本仓现已挂载 `PDF2-20040317.xinDB`（163,834 相），可补真实验收 | 需一条真实 PDF2 条目 + 配套谱 |
| **P1** | **按 v3 库强度口径重建 13 组合成谱基准** | `docs/检索基准-v3-诊断-20261104.md`：合成谱用 v2 卡强度生成、v3 重建库强度口径已改（含 LP/结构因子），两者不同源 → synth_12 误判失败。诊断 §5 顺序：先重建自洽基准 → 重测 → 再决定是否动引擎 | 无 |
| ~~P1~~ | ~~候选近重复聚簇 / 相位族去重后分配预筛名额~~ **已实测否决（2026-11-05）** | 基准报告 §14：族配额在 1000 席下救不回 `3-1`，且端到端把合成 T1 从 11/13 打到 6/13；池内霸榜是弥散稀释（~550 族/1000 席），不是单族洪水 | 已关闭 |
| ~~P1~~ | ~~预筛排序函数改造（连续量取代「主峰是否命中」）~~ **已量到结论（2026-11-06）** | 基准报告 §16.2/§16.3：连续量口径（`2·main_hit+命中率` 50/67、`+0.3·whits` 49/67）**都不如**纯二值门控 + 命中数（51/67），§14.5 的方向被证伪；真正有效的是把 `whits` 与 `hits` 换位，但两把尺子结论相反（合成 T1 −3 / 真实相召回 +4）→ 落成开关 `prescreen_order`，默认不变 | 待用户裁定是否切默认 |
| ~~P1~~ | ~~少线相召回收尾 + 样品侧元素合理性挡假卡~~ **已完成（2026-11-06）** | 基准报告 §16.1：`ElementState.EXCLUDE` 从死代码接通到预筛（`element_exclude_filter` + `prescreen(elements_excluded)` + 兼容层 + GUI 面板），真实谱 Top-1 10/12→12/12、21 升/4 降 | 已关闭 |
| ~~P1~~ | ~~空白式卡补式（416 条，`elements_from_sites`）~~ **已完成（2026-11-06）** | 基准报告 §15：`formula_from_sites` 对称展开位点计数 → `parse_meta` 兜底 → 原地补丁 417 行；四步等价性证明全过 | 已关闭 |
| ~~P1~~ | ~~COD-Full 436 条空式卡补式~~ **已完成（2026-11-06）** | §15.6：同工具 + `--cif-root DEFAULT_COD_ROOT`，写入 440 行，四步等价性证明全过 | 已关闭 |
| ~~P0~~ | ~~真实谱真值口径加「矿物名级」补充列~~ **已完成（2026-11-06）** | 基准报告 §17：`mineral_species_key` 归一化 + 四层判定（家族/名/组成兜底/多晶型 split），分母 43→50；细口径 21/50 对粗口径 19/43，粗口径逐字段零变化 | 已关闭 |
| ~~P1~~ | ~~检索加速：峰位精修换优化器~~ **已完成（2026-11-06）** | 基准报告 §18：`curve_fit` 每峰跑满 `maxfev=5000` 仍抛错且静默返回未精修位置（12% 的峰中招）；换 LM + 解析雅可比后 预处理 35.2 s → 0.35 s、真实谱基准 10 min → 26 s、CLI 端到端 36 s → 2.3 s，合成谱逐项相同、真实谱卡级 19→20/43 | 已关闭 |
| ~~P1~~ | ~~`.xinDB` schema v3.1（d 值倒排 + chunk 边界表）~~ **已评估：不做（2026-11-06）** | 基准报告 §19：四库实测，默认库端到端 2.31 s 里导入 1.32 s、打分 0.37 s，检索本体 0.18 s；1.06M 库 5.68 s，三项全做也只到 ~3.8 s。且 chunk 边界表经分析无效（候选散满 260 chunk），真要动是调 chunk 粒度 → 需重建库 | 已关闭 |
| ~~P1~~ | ~~`3-1` 类次相召回收尾~~ **已完成（2026-11-06）** | 基准报告 §20：名额假说（8000 席下 Al₂O₃ #581/CaF₂ #425）与残差排序假说（垃圾卡同为 3/3 命中）双双被否定；答案是**元素约束** —— 3-1 由 1/3 变 3/3、全量相召回 20/43 → 30/43、族级 → 33/43，无一样品变差。新增 `--oracle-elements` 上界口径 | 已关闭 |
| **P2** | **COD 全库检索质量上游修复（峰抽取标定）** | 峰抽取口径标定，属上游数据质量 | 非引擎层 |
| ~~P2~~ | ~~T0.8 FoM P 值深挖收尾~~ **已完成（2026-11-06）** | 基准报告 §26：三条结论进基准体系、`FOM_MODEL.md` / `fom_criteria.py` 时态统一、LP 语义与 v2→v3 时间线澄清、代码注释里的 `I_scale` 结论搬进文档、Phase 0 状态 🟡→✅。精确 P 定义反推列为外部依赖 | 已关闭 |
| ~~P2~~ | ~~CLI 大库引导一致性~~ **已完成（2026-11-07）** | 基准报告 §27：阈值/判据下沉 `core/db/library_scale.py`（零 PySide6），GUI re-export、CLI `search`/`run` 打开库后走 stderr 非阻塞提示（相数 O(1) 读 meta）；已有元素约束 / FPFM / `--no-library-hint` 三种情况不打扰；`--json` stdout 保持纯 JSON。30 项新单测 | 已关闭 |
| **P3** | **Bruker RAW v1 / v4** | v1 无格式文档需真实样本逆向；v4 需 RAW4.00 样本真实验收 | 依赖真实样本 |
| **P3** | **T14.4 GUI 串口采集面板** | 本机无真实仪器可验收 | 需硬件联调 |
| **规划** | **3.5.0：反向 XinRefinement→XinMatch 回写精修结果** | 联合计划 §0「范围外，留到 3.5/1.2 评估」 | 等 3.4.0/1.1.0 配对稳定 |

**执行纪律**：P1 的引擎改动必须等基准自洽——11-04 诊断已证 synth_12 失败是「尺子与库不同源」，不是引擎缺陷；在重建自洽基准前调参即用错尺子。

## PDF-2 真实链路验收 S2（2026-11-05）✅

联合计划 §8 项 4 的 S2「PDF2 混合来源相」真实链路补验（此前 `source="pdf2"` 只由合成 manifest 覆盖）。用已挂载的真实库跑一次端到端：真实谱 `test_xrd/txt/5-1.txt`（5751 点 / 102 峰）+ 真实 COD 方解石 `96-210-0189`（CIF 回取命中 `cifs/2100189.cif`）+ 真实 PDF2 卡片 `PDF2-010837`（ICDD 01-0837）。

| 检查 | 结果 |
|---|---|
| 真实 PDF2 库 entry_id 形态 | **163,834 条全部 `PDF2-XXXXXX`**，`_classify_entry` 判为 `pdf2`（无格式错配） |
| PDF2 相 source / structural / cif | `pdf2` / `false` / `null`，reason「ICDD PDF-2 卡片无 CIF，仅提供参考峰表」 |
| COD 相 source / structural / cif | `cod` / `true` / `cifs/2100189.cif` |
| `.xinm` 成员 | `pattern/pattern.csv` + `cifs/2100189.cif` + `manifest.json`，**无任何 ICDD 衍生文件** |
| PDF2 参考峰表是否外泄 | 否（manifest 只带 id/formula/cell 元数据，不导出 d-I 参考峰表） |

**顺带修掉一个真 bug**：`build_manifest` 的 `candidates_summary` 复用了 `for ph` 循环泄漏的 `eid`（恒为最后选中相），导致所有候选都指向同一个相 —— 真实 S2 才暴露（合成测试当时只断言了数量）。已改为 `e.entry_id`，并给 `test_export_roundtrip_manifest_and_csv` 补了「候选 entry_id 各自对应」的断言。`tests/io/test_xinm.py` 7 项全绿。

复现：`python -m tools._probe_pdf2_xinm --pdf2-db <PDF2.xinDB> --cod-db <COD.xinDB> --spectrum <谱> --out <输出.xinm>`，退出码 0 = 11/11 全过。

## P1 基准回归复核（2026-11-05）✅

合成谱基准 `test_xrd/synthetic_v3` 已于 2026-11-04 按 v3 库强度重建（生成器 `--peak-source v3`）。本次确认两点：① 用当前生成器同 seed 重生成，**13 组逐字节 SHA-256 一致**（可复现，非一次性产物）；② 在 3.4.0 代码上重跑两套基准，与 `docs/基准报告-物相检索-v3.md` §2/§9.2 **逐项相同**：合成 相位级 T1 11/13 · T5 12/13 · 序贯 10/13 · 相召回 19/24；真实 整谱 T1 10/12 · T5 12/12 · 卡级 24/43 · 族级 27/43 · 序贯 5/12。

**结论：3.4.0 检索行为 = v3.2.0 终态，发布无需改引擎。** §9.4/§10.5 的 FoM 层（`3-1` 次相排不上去）与相位族预筛配额是下一批工作。原始数据 `.scratch/bench_v3set_340.json`、`.scratch/bench_real_340.json`。

## 3-1 次相失败诊断（2026-11-05，只读）

`tools/_probe_31_fom.py` 诊断（报告 `docs/检索基准-31-次相诊断-20261105.md`），**修正 §9.3 的定性**：
- **主因是预筛召回**：默认名额（1000）下 Al₂O₃/CaF₂ **不在池内**；8000 深名额下才进池（族 420/303）。
- FoM 层非 bug：距 Top-20 族仅差 0.06~0.08 fom，罚分弥散在 intensity/ncorr/peakpos（次相稀释形态）；
  单判据反事实都能拉进 Top-20 族（18/6），但 §11.2 已证单一覆盖指标会同时抬高假密集卡 —— 不动冻结权重。
- **附带发现**：库里 416/78,035 条 formula 为 NULL/空，`same_phase` 的组成回退把它们当「不反对」→
  可假匹配任何真值/折入任何族（潜在基准虚高风险，本次未影响数字）。修复需批准，方向：
  `same_phase` 对「一侧有式、一侧解析为空」返回 False，或建库侧拒绝 NULL 式条目。
- 复现口径更正：§10.1 的名额实验要用 `search_match_v3(candidate_limit=...)`；
  `search_match` 的 `recall_max_candidates` 不转发 v3。

## 3.4.1 `same_phase` 修复：空白式卡不再「万能匹配」（2026-11-05）✅

`_composition_agrees` 曾在「任一侧组成不可解析」时返回 `True`（`no evidence, not a mismatch`）。
该函数只在至少一侧缺晶胞时被调用 —— 那时组成是**唯一**证据，返回 `True` 等于「不知道 ⇒ 同相」，
后果是真值匹配虚高（一张空白卡同时命中所有真值）与折叠错族（空白卡当上族代表）。

| 项 | 内容 |
|---|---|
| 改动 | `_composition_agrees` 改「两侧都非空才可能为真」；晶胞路径不变（晶胞本身是正向证据） |
| 测试 | `tests/search/test_phase_key.py` +4 组用例（空式双向 False / 两侧皆空 False / 空式但晶胞吻合 True / 折叠独立成族）；全量 pytest 0 失败（15m18s） |
| 合成基准 | **逐字节不变**（`diff` 全空）：11/13 · 12/13 · 10/13 · 19/24 |
| 真实基准 | 卡级 **24→19**、族级 **27→19**、序贯完整 **5→4**；仅 `5-3` 与 `7-1` 两行变化，其余 10 行逐行相同 |

**归因（逐条查证）**：`7-1` Top-20 第 14 位 `96-720-0134` 式为空 → 旧实现一张卡命中 7 个真值
（7/7 → 2/7）；`5-3` Top-80 折叠出 58 族、其中 2 个族代表是空白卡（5/5 → 2/5），序贯轮 3
确认的 `96-230-0274`（矿物名 Hydroxyapatite）也是空白卡（5/5 → 0/5）。
**§9.3 结论 1 已更正**：`5-3` 折叠增益是 +1（Kaolinite），不是 +4。

**下界说明**：19/43 低于引擎真实能力 —— 落到 Top-N 的空白卡无法计入任何真值。库里 **416/78,035**
`formula` 为空，但**全部带晶胞、全部有峰**（20~150 条），是真结构缺 `_chemical_formula_sum`
（`elements` 有值、`formula` 空）。补式路线已登记为 P1。

全文：`docs/基准报告-物相检索-v3.md` §13；复现探针 `.scratch/_probe_blank_cards.py`（只读）。

## §10.5 相位族预筛配额：实测否决（2026-11-05）✅

§10.5 建议「每族先给 1 席，剩余按分数回填」。已实现为 `XinDBReader.family_slots`（默认 `None`，
族 = 三强线指纹 `_family_keys`，不回表），并做了「上界 → 端到端」两级实测。

| 阶段 | 结果 |
|---|---|
| 池内召回（1000 席 / 25 样品 / 67 真值相，上界） | off 45/67；≤1 席 **48/67**；≤2/4/8/16 无变化或 −1 |
| `3-1` 次相 | **完全不动**：Al₂O₃ 首个同相卡在池内第 2071 位、CaF₂ 第 4262 位 |
| 端到端（合成） | 相位级 T1 **11/13 → 6/13**（≤1、≤2 均如此）、序贯 10→7、召回 19→15 |
| 端到端（真实） | 卡级 19→19/18、族级 19→18、T1 10→9/10、T5 12→12/11 |

**根因**：族内保留的是 legacy 顺序第一张，不是 FoM 分最高的那张；族定义只看三强线，化学上
不同的相也会同指纹 → 砍掉的是高分卡，留下的是近邻卡。

**否决，默认关闭**；机制与 6 项测试（`tests/db/test_prescreen_family_cap.py`）保留，避免重做实验。
**§10.5 的前提被证伪**：结果层「同族 30+ 变体霸榜」与预筛池层的「弥散稀释」（前 1000 席已有
~550 个族、最大族仅 44–67 张）不是同一个问题。真正待改的是**预筛排序函数**（「主峰是否命中」
这类二值判据在多相谱里信息量不足），或按需放大 `candidate_limit`（4000 席可覆盖 Al₂O₃）。

全文：`docs/基准报告-物相检索-v3.md` §14。

## P1 空白式卡补式（2026-11-06）✅

把 COD-Inorg 里 416 张「有晶胞、有峰、但无化学式」的卡补齐组成证据，并让**整库重建不再回退**。

| 项 | 结果 |
|---|---|
| 解析层 | `cif_meta.formula_from_sites()`：对称展开位点 + 占位度累加，D/T→H、剥离氧化态；`parse_meta` 三种公式标签全失败时兜底 |
| 测试 | `tests/test_cif_meta_elements.py` 18 项全绿（新增 3 项 + 更新 1 项既有断言）；ruff / mypy 全通 |
| 补丁 | `tools/_patch_meta_blank_formula.py --scan/--apply`；备份 `.xinDB.bak-20261106-055803`；写入 **417 行**（416 空式 + 1 垃圾式 `96-770-6030`），空式归零 |
| 等价性 | 全量重解析 79,198 CIF × 18 列：**仅 formula 417 行不同，其余 17 列 0**；写后再 diff **全 0**（补丁 = 新代码重建的元数据） |
| 峰 | `validate_xindb` 0 fail/27 检查；`_compare_xindb_peaks` 20 chunk 哈希全等；抽样重建 24 受影响 + 24 对照 **48/48 逐字节一致**（float32 精度）；`build_time` 保持原值 |
| 基准 | 合成 + 真实两套**逐字节不变**（11/13·12/13·10/13·19/24；10/12·12/12·19/43·19/43·4/12） |

**口径修正（重要）**：§13.6 曾推断「19/43 被缺式卡压低」——实测**未兑现**。真实谱 Top-80 里
只有 4 张补式卡（全是 `C16 H28 N4 O12` 等有机/金属有机相），命中真值 0。旧口径的虚高是
**假阳性**，不是真命中被错杀。19/43 应作为当前口径的实测值引用，不再写成「下界」。

**PDF-2 另案处理**：36 条空式是 ICDD 源数据本就没有化学式字段，不编造；同批发现并修复
57 张「X7 多行导致化学式只剩尾巴」的解析缺陷（见下节）。COD-Full 436 条已于同日补齐。
全文：`docs/基准报告-物相检索-v3.md` §15。

## P1 COD-Full 空式卡补式（2026-11-06）✅

把 532,038 相的 COD-Full 库里 436 张「有峰、有晶胞、无化学式」的卡补齐并证明与重建等价。

| 项 | 结果 |
|---|---|
| 范围 | `COD-Full-20261020.xinDB`（879.4 MiB / 532,038 相 / 130 chunk），CIF 根 `D:\Project\XRD\sync-COD\COD`（**必须显式 `--cif-root`**，工具默认是无机子集） |
| 写前 diff | 535,166 源 CIF 全量重解析 0 失败；532,038 行 × 18 列 → **仅 `formula` 440 行不同**，其余 17 列 0；436 空式 + 4 垃圾式，拒写 0 |
| 补丁 | `tools/_patch_meta_blank_formula.py --apply`；备份 `.xinDB.bak-20261106-065523`；写入 **440 行**，空式归零；`build_time` 保持 `2026-11-02T14:09:12+08:00` |
| 等价性 | 写后全量 diff **18 列全 0**；全表逐列（备份 vs 新库）仅 `formula` 440 行，`meta` / `element_inv` 全等 |
| 峰 | `validate_xindb` **0 fail / 0 warn / 27 checks**；`_compare_xindb_peaks` **130 chunk 哈希全等**；抽样重建 **48/48 逐字节一致** |
| 基准 | 合成 + 真实两套 JSON **逐字段全等**（11/13·12/13·10/13·19/24；10/12·12/12·19/43·19/43·4/12） |

四张垃圾式：`'?'` ×2、`'Ph as e kn n ow un'`（与 Inorg 同一张）、`'h8 k8 o40 si12 zr4'`
（全小写不可解析且元素集与库内 `elements` 矛盾）。

**口径**：双基准用 COD-Inorg，与本次改动的 COD-Full 无交集；数字不变是回归保护，
不代表 Full 库检索质量变化。PDF-2 的组成缺陷已于同日另案修复（下节）。
全文：`docs/基准报告-物相检索-v3.md` §15.6。

## PDF-2 组成缺陷修复（2026-11-06）✅

用户要求「修正 36 条空式」。查证后发现：那 36 张卡的 ICDD 原始记录里 **X7 行存在但数据区全空、
也没有 X8**，是源数据固有缺失，**不能编造化学式**；但同一轮全量重解析揪出了一个更严重的真 bug。

| 项 | 结果 |
|---|---|
| 真因 | `pdf2_scan.parse_record` 对 X7 用**覆盖赋值**，长化学式跨行时只留下 `)2` / `)0.43 ]n` 这类尾巴；`display_formula` 又优先返回它 → 这些卡在 `elements` / `element_inv` 里完全不可见 |
| 验收证据 | 补丁前 `validate_xindb` 的 E2 WARN = **93 条无元素**，其中仅 36 条是空式，另 **57 条是「有式但抽不出元素」** |
| 解析层修复 | `Pdf2Card.formula_lines` 收集全部 X7 行；`display_formula` **只在旧写法抽不出元素时**才退回 X8 规范经验式（或第一行）。单行与「旧式可解析」的多行卡逐位不变 |
| 收窄护栏 | 初版曾把全部多行卡换成 X8，导致 **16,170 行 formula / 578 行 elements 变化**（`020087` 的 X8 还漏 Er），会改 `same_phase` 组成比值 → 当场否决并收窄，最终只动 57 行 |
| 原地补丁 | `XinMatch-DataBase/tools/_patch_pdf2_formula.py --scan/--apply`；备份 `.xinDB.bak-20261106-112616`；写入 57 行 `formula`/`elements`/`elem_mask`，从 `entries` 重建 `element_inv`（96 键不变、37 个 bucket 补 eid） |
| 等价性 | 全表逐列仅这 57 行 × 3 列变化；`meta` 28 行、`peak_chunks` 40 行全等；`_compare_xindb_peaks` **40 chunk 哈希全等**；`validate_xindb` **0 fail / 1 warn / 28 checks**，E2 WARN **93 → 36** |
| 36 条空式 | 保持 NULL 与空 `elements`；3.4.1 的 `same_phase` 本就拒绝「无组成证据」的匹配，这 36 张不参与组成级判定是**正确行为**。E2 剩余 WARN 是数据事实，不是缺陷 |
| 版权边界 | `pdf2.dat` 与 `.xinDB` 全程本地，未入 Git / Release；入仓的只有解析代码、补丁工具、测试与文档 |

**结论**：36 条空式不可补，已定性关闭；顺带修复的 57 张截断式让元素筛选与组成判定重新可见。
全文：`docs/基准报告-物相检索-v3.md` §15.7。

## P1 元素「必须不含」约束落地（2026-11-06）✅

`ElementState.EXCLUDE`（周期表红色）此前是**死代码**：面板能标红、摘要显示「排除：Bi」，
但 `main_window._do_search` 调 `search_match` 时不传 `restraints`，预筛也没有这条通路，
全仓对 `EXCLUDE` 的引用数为 0。于是「样品里没有 Bi」（XRF/EDS 已确认）进不了召回。

| 层 | 改动 |
|---|---|
| 预筛 | `XinDBReader.element_exclude_filter()`（`element_inv` 倒排，与 63 位 `elem_mask` 无关）+ `prescreen(elements_excluded=)` |
| 检索 | `search_match_v3(elements_excluded=)` 转发 |
| 兼容层 | `search_match(restraints=)` 的 `EXCLUDE → elements_excluded`（此前静默丢弃） |
| GUI | `MainWindow._current_restraints()`（GUI 线程读面板）+ `_do_search(restraints=)`；FPFM 模式给出「不参与」的状态栏提示 |
| 测试 | `tests/db/test_prescreen_element_exclude.py`（12）+ `tests/ui/test_element_restraints.py`（6） |

语义细节：**未知元素在排除方向上什么都不排除**（返回全 `True`）—— 与「必须含」相反，
拼错符号不该把结果清空。

真实谱量化（理想 XRF 设定，`top_n=60`）：Top-1（任一真值相口径）10/12 → **12/12**；
逐相名次 21 升 / 17 平 / 4 降 / 1 挤出榜单。**非单调**要记住：过滤腾出名额后新进来的卡
可能把某张真值卡挤出固定 Top-N（`5-2` Muscovite 46 → 掉出前 60）。详见基准报告 §16.1。

## P1 预筛排序：连续化被证伪，换键做成开关（2026-11-06）⚠️ 待裁定

§14.5 曾判断「二值主峰判据信息量不足，应改强度加权覆盖率」，实测**反了**：

| 排序（800 席池内召回 / 67 真相位） | 召回 |
|---|---:|
| `main_hit → whits → hits`（3.4.x 默认） | 39/67 |
| `main_hit → hits → whits` | **51/67** |
| 去掉主峰门控（`hits → whits`） | 41/67 |
| `2·main_hit + 命中率` / `+0.3·whits` | 50 / 49 |

主峰门控是**载荷**（去掉掉 10 个真值相），连续化加权项一律不如二值门控 + 命中数。

但把后两键换位的端到端结果是**两把尺子相反**（2×2 分离实验，见 §16.3）：

| 口径 | 合成 T1/T5/序贯 | 真实 T1/T5 | 真实卡级/族级相召回 |
|---|---|---|---|
| 旧排序 + div0.2（现默认） | 11/13·12/13·10/13 | 10/12·12/12 | 19/43·19/43 |
| 新排序 + div0 | 8/13·10/13·5/13 | **11/12·12/12** | **23/43·25/43** |

根因是尺子：合成谱用库内同一批参考强度反演，强度形判据天然占优；真实谱没有这个关系。

**处置**：机制落成 `XinDBReader(prescreen_order="intensity"|"hits")`，默认 `"intensity"`
（3.4.x 逐项不变，合成基准复核 11/13·12/13·10/13·19/24）。切默认需要接受
「合成 T1 −3 换真实相召回 +4」，属产品裁定 —— 未获裁定前不改默认。

## 版本号落点统一（2026-11-06）✅

同一版本号曾在四处各写一遍并漂移：`pyproject.toml` 3.4.1、`__init__._FALLBACK_VERSION`
3.4.0、`xinmatch.spec` `APP_VERSION` 3.4.0、`xinmatch_setup.iss` 10 处 3.4.0。后果是
冻结 exe 的 About 报 3.4.0、源码报 3.4.1，安装包名固定 3.4.0，与 tag 对不上。

| 落点 | 处置 |
|---|---|
| `pyproject.toml` | **唯一真相源**，本轮 → 3.5.0 |
| `xinmatch/__init__.py` | `_FALLBACK_VERSION = "3.5.0"`（冻结态返回值） |
| `xinmatch.spec` | 改为从 pyproject 推导 `APP_VERSION` / `VERSION_TUPLE`，不再写字面量；原有 guard（spec ↔ `_FALLBACK_VERSION`）继续生效 |
| `tools/xinmatch_setup.iss` | 只剩一处 `#ifndef AppVersion` 默认值，其余全部 `{#AppVersion}`；构建脚本用 `ISCC /DAppVersion=` 覆盖 |
| `tools/build_exe.ps1` | `-Version` 默认空 → 从 `import xinmatch` 读；构建后校验 exe 的 FileVersion；新增 `-Installer` 走 ISCC |
| `tests/test_version_consistency.py` | 5 项检查：pyproject 三段式、`_FALLBACK_VERSION`、iss 默认值、iss 无其他字面量、spec 不得写死 |

同样的问题在 XinRefinement 侧更严重：`__version__` 1.4.0 而 iss 仍写 1.1.0，导致
`build_installer()` 打完包按 1.4.0 找产物、必然报「安装包未生成」。已修（iss 默认值 1.4.0 +
`ISCC /DAppVersion=` + `tests/test_version_consistency.py`）。

## v3.5.0 二进制构建与稳健性验收（2026-11-06）✅

三种形态全部产出并逐一验过，`dist/` 下旧版 3.3.0/3.4.0 产物未动。

| 产物 | 体积 | 说明 |
|---|---|---|
| `XinMatch-Setup-3.5.0.exe` | 242.3 MiB | Inno Setup 安装包，唯一对外发布物 |
| `XinMatch-Internal-3.5.0.zip` | 337.4 MiB | 便携包，根层直接是 `XinMatch.exe` / `_internal/` / `data/` |
| `dist/xinmatch-3.5.0`、`dist/xinmatch-internal-3.5.0` | 各 791 MB | onedir 树，本地调试用，不发布 |

SHA-256 已写入 `dist/SHA256SUMS.txt` 并用 `sha256sum -c` 回验通过（Setup
`e81ab39f…9ba7`、zip `41ac3005…b40b`）。

### 验收 5 轮

| 轮次 | 动作 | 结果 |
|---|---|---|
| 1 版本一致性 | 三个形态 `--version` + exe `FileVersion` 资源 | 全部 `3.5.0` |
| 2 库注册 | `libraries --json` | `xindb_cod_inorg` / `available:true` / `entries:78035`；把 `XINMATCH_XINDB_DIR` 指到 `XinMatch-DataBase\data` 后 7 个库全部识别（COD-Inorg 78,035 / COD-Full 532,038 / PCOD-Inorg 1,061,953 / TCOD-Inorg 46,846 / TCOD-Full 361,701 / MP 155,201 / PDF2 163,834），仅 PCOD-Full 按决定跳过（与 PCOD-Inorg 等同，非遗漏） |
| 3 冻结检索 | 真实样本 `3-1.txt`（207 峰）对 78k 相库 | 36 s 出榜，榜首 `zincite`(ZnO) 正确 |
| 4 新功能穿透 | `--restraints '{"elements":{"Zn":"red"}}'` | ZnO 全数消失、榜首跌到 `Mo Ni`（FoM 0.773→0.685）—— 约束在冻结产物上真的生效，不是只在源码里 |
| 5 安装 / 启动 / 便携 | `/VERYSILENT` 安装 → GUI offscreen 启动 → 卸载；zip `7z t` | 安装退出 0、3562 文件、`variant.txt=release`、GUI 存活 12 s 无崩溃；卸载退出 0；zip CRC 全过 |

### 两处构建修复（都进了本轮提交）

1. **PyInstaller 不能直接打到 `dist\`。** COLLECT 会先**删**目标目录，而 `dist\xinmatch-3.5.0`
   有 3577 个文件，撞上本机批量删除保护后 exit 1，前两分钟打包白跑。改为先进
   `build\stage\<variant>-<ver>-<hhmmss>`（每次唯一，永不需先删）再 `Copy-Item -Force`
   覆盖镜像。`build_exe.ps1` 里已注明原因，避免后来者改回去。
2. **便携 zip 必须排除 `*.xinDB-shm` / `*.xinDB-wal`。** 只要跑过一次 GUI 或 CLI，
   `data\` 下就会长出这两个运行态文件；第一版 zip 里带了它们（`-shm` 32 KB 全零、
   `-wal` 0 B），打包命令改加 `-x!*.xinDB-shm -x!*.xinDB-wal` 后重打，条目数 3562→3560。

### 尚未做

- **推送**：`0534fc0`（XinMatch/master）、`ff1f3e4`（XinRefinement）、XinMatch-DataBase
  的 `.gitignore`（`.scratch/`）三项仍只在本地，等显式批准。
- **GitHub Release**：按惯例只上传 Setup，便携 zip 不上传。
- **`prescreen_order` 默认值**：仍是 `"intensity"`，等产品裁定（见上一节）。
- XinRefinement 工作树有上一会话遗留的 EWIMV 织构试验改动（`tools/bench_v14.py`、
  `core/refine/recipe.py` 把 micro 步提到 B 步之前），**未提交**，与本轮无关。


## 真实谱真值口径加「矿物名级」补充列（2026-11-06）✅

转交记录 §7.2 的 P0：真实谱的组成级真值有三个结构性盲区（多晶型被合并、掺杂固溶体整条被
排除、掺杂卡组成不完全相等即判 miss）。新增一把**并列**的细口径，不改动任何候选生成或打分代码。

| 层 | 改动 |
|---|---|
| 新模块 | `xinmatch/core/search/mineral_name.py`：`mineral_species_key()` 把 `Quartz high` / `Muscovite-2M1` / `Brucite (deuterated)` 归一到物种键，`Nitrocalcite` / `Magnesium calcite` / `Anatase↔Rutile` **不**互认；`has_species_name()` 把 `hexagonal` 这类晶系词判为「无名」 |
| 基准 | `tools/bench_real_samples.py` 新增 `FineTruth` / `TRUTH_FINE`（13 组 / 50 相）与四层判定：固溶体家族 → 卡有名按名 → 卡无名回落组成比（多晶型成对时不计）→ 只有名的真值不接受无名卡 |
| 输出 | 旧 JSON 字段一字不改，新增 `totals_fine` 与每行 `fine_*` 字段；终端多打一张细口径表 |

**数字**（COD-Inorg，`top_n=20`，序贯 3 轮）：

| 口径 | 整谱 T1 | T5 | 卡级相召回 | 族级 | 序贯完整 |
|---|---|---|---|---|---|
| 粗（组成级，43 相） | 10/12 | 12/12 | 19/43（44.2%），峰位精修修复后 **20/43** | 19/43 → 20/43 | 4/12 |
| 细（矿物名级，50 相） | **12/13** | **13/13** | **21/50（42.0%）** | 20/50（40.0%） | 4/13 |

**细口径没有让引擎变好**（42.0% 对 44.2%，略低），价值在信息量：2-2 从「1/1」拆成「1/2」，
第一次看清只找到锐钛矿没找到金红石；5-3 的 Top-1 由 miss 变 hit（`Co0.03Fe0.97HO2` 按名
判为 Goethite）；7-2 的 Hornblende 在族层被找到（粗口径里它不在分母）；1-2 的 NCM811
首次进分母（家族规则命中 `Li1.01Mn0.1Ni0.89O2`，缺 Co）。

**无侵入证明**：`totals` 与默认配置基线 `ab_real_old_ord_div0.2.json` 完全相同，
逐行逐字段 12 行 × 14 列 **差异 0 处**；新增样本仅 `1-2`（粗口径不计，细口径计入）。

**两个踩坑**：

1. `mineral_name` 字段里有 24 张（0.12%）是晶系词/占位符。第一版把「字段非空」当「有名字」，
   2-1 的榜首 `96-157-7381`（`mineral_name="hexagonal"`，`formula="O Zn"`）因此被自己的
   尺子判成 miss。修法是 `has_species_name()` —— 判据必须是「有物种键」，不是「字符串非空」。
2. `.scratch/bench_syn_350.json` / `bench_real_350.json` 文件名像「3.5.0 基线」，其实是
   「新排序 + div0」的 A/B 产物（8/13 与 11/12·23/43）。若拿它当基线比对，会得出
   「粗口径变了」的错误结论。已重命名为 `bench_*_neworder_div0.json`。

**测试**：`tests/search/test_mineral_name.py`（33 项，含 10 例「形似但不该命中」反例）、
`tests/cli/test_module_entry.py`（2 项，见下）。ruff/mypy 干净。
全量 pytest **1570 passed / 4 skipped / 1 xfailed / 0 failed**（21m10s）。
注意：退出码是 1，因为会话结束时的安全钩子拒绝删除 pytest 临时垃圾目录
（`SAFE_DELETE_BULK_CONFIRM_REQUIRED`，119 个文件 > 阈值 50），与测试结果无关 ——
判绿要看进度行的 `.`/`s`/`x` 统计，不要只看 `$?`。

**墙钟阈值测试的环境要求**：`tests/search/test_hanawalt_fink.py::test_pre_filter_hanawalt_perf_10k_under_half_second`
断言 <0.5 s。并发跑基准时实测 0.567 s 会**假失败**，单跑即过。跑全量前先停掉重任务，
否则会误判为回归。

**顺带修掉文档与事实不符**：转交记录 §6.6/§8.2 写着源码 CLI 入口是 `python -m xinmatch`，
但包内没有 `__main__.py`，该命令实际报 `No module named xinmatch.__main__`
（只有 `python -m xinmatch.cli.main` 可用）。已补 `xinmatch/__main__.py` 并加测试，
使文档描述的形式真的可用。

## 峰位精修换优化器：36 s → 2.3 s（2026-11-06）✅

v3.5.0 二进制验收里「`3-1.txt` 打 78k 相库 36 s」一直被当成库检索慢。这次按分段计时查，
发现 **93% 的时间在预处理里的逐峰高斯拟合**，数据库检索本体只有 0.9 s。

| 阶段 | 修复前 | 修复后 |
|---|---:|---:|
| `refine_peak_position` × 208 峰 | 35.2 s（156 ms/峰） | **0.35 s**（1.5 ms/峰） |
| `prescreen(1000)` / `fetch_peaks` / `rank_candidates` | 79 / 72 / 311 ms | 不变 |
| 真实谱基准 13 组（含序贯 3 轮） | 10 min 03 s | **26 s** |
| CLI `search` 端到端（subprocess 墙钟 3 次中位） | 约 36 s | **2.31 s** |

**根因（两层）**：

1. `curve_fit`（trf + 边界）拟合 11 点 4 参数模型时**每个峰都跑满 `maxfev=5000` 仍不收敛**，
   直接抛 `RuntimeError`；异常分支 `return float(two_theta[idx])` 把「未精修」的位置
   静默当成结果返回 —— 208 个峰里 26 个（12%）中招。所以这不只是慢，是**静默的质量缺陷**。
2. 顺带发现抛物线法同类 bug：近似线性片段使 a≈0，顶点 `-b/(2a)` 可达 **1.6e12°**。
   现在抛物线结果也必须落在窗口内，否则退回网格点。

**修法**：模型/初值/窗口/最小二乘目标不变，只换 `least_squares(method="lm")` + 解析雅可比，
模型求值次数 5000 → 中位 15；LM 无界，所以加护栏（`fwhm>0`、`amplitude≥0`、中心在窗口内），
不合格退抛物线、再不合格退网格点。

**一致性**：208 峰里 LM 与旧 curve_fit 的位置差中位 **5.6e-08°**；差异 >1e-4° 的 26 个峰
正是旧实现失败的那些（旧值恰好等于 `x[idx]`），新值与独立的抛物线法差 <0.006°。

**检索质量**（无劣化，还有 +1）：

| 口径 | 修复前 | 修复后 |
|---|---|---|
| 合成谱（相位级） | 11/13·12/13·10/13·19/24 | **逐项相同** |
| 真实谱粗口径 | 10/12·12/12·19/43·19/43·4/12 | 10/12·12/12·**20**/43·**20**/43·4/12 |
| 真实谱细口径 | 12/13·13/13·21/50·20/50·4/13 | **逐项相同** |

唯一命中判定变化：**5-2 的 SiO₂ 由 miss 变 hit**。逐行逐字段 13 行 × 22 列有 28 处差异，
全部落在 `sequential_found` / `n_families` / `coverage` 这类对峰位敏感的字段。

**测试**：`tests/peak/test_peak_refine.py` +3 项（迭代上界 5 s 的宽松性能护栏、无峰斜坡
必须落在窗口内、全等强度必须有限）；`tests/peak` 35 项全绿；ruff/mypy 干净。
**全量回归 1573 passed / 4 skipped / 1 xfailed / 0 failed，16 min 23 s，exit=0**——
比上一轮的 21 min 少了近 5 min，正是峰位拟合不再空转的直接体现。
（这次 `-q` 的收尾 counts 行整行没落盘，只剩进度点，统计是按进度行字符数数的 ——
所以 §4.1 那条「判绿看进度行统计」不是洁癖。）

**教训**：端到端计时只说"慢"，分段计时才说"慢在哪"。若按原计划做 `schema v3.1` 索引，
会为一个 0.9 s 的检索优化 0.47 s，而 35 s 的真正来源完全没碰到。
全文：`docs/基准报告-物相检索-v3.md` §18。

## 检索成本结实测 + `schema v3.1` 决策：不做（2026-11-06）✅

峰位拟合修好之后，转交记录 §7.2 的 P1「`schema v3.1`：d 值倒排 + chunk 边界表」失去前提，
于是把四个库在同一谱（`3-1.txt`，208 峰 / 40 窗）上量了一遍，用数字决定做不做。

| 库 | 相数 | 预筛(40 窗) | 取峰(1000 相) | FoM 打分 | 进程内合计 | CLI 墙钟 |
|---|---:|---:|---:|---:|---:|---:|
| TCOD-Inorg | 46,846 | 57 ms | 73 ms | 416 ms | 0.92 s | 2.51 s |
| COD-Inorg | 78,035 | 101 ms | 77 ms | 372 ms | 0.92 s | 2.31 s |
| COD-Full | 532,038 | 560 ms | 352 ms | 382 ms | 1.66 s | 3.65 s |
| PCOD-Inorg | 1,061,953 | 1,358 ms | 896 ms | 480 ms | 3.10 s | 5.68 s |

**三个发现**：

1. **只有预筛和取峰随库规模涨**。打分稳定在 0.37~0.48 s，因为它只跟候选数（1000）有关，
   与库里几百万相无关；预处理 0.35 s 同样与库无关。
2. **默认库上最大的单项是导入，不是检索**。COD-Inorg 端到端 2.31 s = 导入启动 1.32 s（57%）
   + 打分 0.37 s + 预筛 0.10 s + 取峰 0.08 s + 预处理 0.35 s。`-X importtime` 显示
   `scipy`（经 `peak_refine` 的 `scipy.optimize` 和 `smoothing` 的 `scipy.signal`→`scipy.stats`）
   独占 0.73 s。
3. **取峰有约 800 倍读放大**。1000 个候选散落在 196/260 个 chunk 里，读出约 955 MB，
   只为取 1.2 MB（0.09%）。这是 chunk=4096 相/块的必然结果，不是实现缺陷。

**决策：`schema v3.1` 不做。** 三项优化全做，1M 库 5.68 s → 约 3.8 s，默认库一分不省，
代价是百万相 136 MB 附加索引 + 全部已发布库迁移 + schema 双向兼容。真要动手，
第一刀是 **chunk 粒度 4096 → 256**（读放大 800× → 50×，但要重建库），不是 d 倒排。
`chunk 边界表`这一项经分析是**无效的**：候选散布满 260 个 chunk，边界表省不掉解码。

**遗留（不在计划内，记录备查）**：CLI 启动 1.32 s 中 0.73 s 是 scipy 导入。
把它挪进函数体内只能帮到 `libraries`/`--version` 这类命令 —— `search` 必然用得上 scipy，
挪了也是等价交换。要真降只能自己写 4 参数 LM（已有解析雅可比）或绕开 `scipy.signal`，
属"碰数值"的改动，不做。

全文：`docs/基准报告-物相检索-v3.md` §19（含复现脚本表）。

## `3-1` 类次相召回：名额与排序都被否定，答案是元素约束（2026-11-06）✅

转交记录 §7.2 的 P1「`3-1` 类次相召回收尾」，原判断是「根因是预筛名额，方向是按样本复杂度
自适应名额」。这次把三个假说一起量了，**前两个都不成立**：

| 假说 | 做法 | 结果 |
|---|---|---|
| 一：预筛名额不够 | `candidate_limit` 1000 → 8000 | Al₂O₃ 从 MISS 到 **#581**、CaF₂ **#425**；第 20 名 fom 0.653，二者差 −0.06~−0.07，仍在 Top-20 外；代价 0.82 s → **4.61 s** |
| 二：残差阶段排序键不对 | 换成「解释残差峰数」/「三强线命中数」 | 解释峰数更差（#1922 / #4717，密集卡刷满 10/11）；三强线命中在 11 峰残差上被垃圾卡同分压制（`As Ca Cu H O5` fom 0.692 > Al₂O₃ 0.684），放到第 1 轮 33 峰残差上直接把真 ZnO 换成 `Fe4.93 H O8` → **实现已回退，不入代码** |
| 三：给化学信息 | 除 Zn/Al/Ca/O/F 外全部「必须不含」 | 池 1000 → **386**，CaF₂ **#11**、Al₂O₃ **#13**，检索还快 3 倍 |

**新证据说明「相一定在样品里」**：ZnO 之后的 11 个残差峰，位置与 Al₂O₃ 五条最强线中的 4 条
（57.48/43.33/35.12/68.21°）、CaF₂ 的两条（46.98/28.24°）逐一对应，局部信噪比 **5.3~31.8σ**，
是真峰；但强度全挤在 187~236（≈最大峰的 1.1%），强度形不可用 —— 这才是「单谱检索找不回
次相」的物理原因。

**全量 12 组真实谱，元素已知（上界）口径**：

| 口径 | Top-1 | 相召回（卡级） | 相召回（族级） | 序贯完整 |
|---|---:|---:|---:|---:|
| 无约束（现状默认） | 10/12 | 20/43 | 20/43 | 4/12 |
| 元素已知（上界） | **12/12** | **30/43** | **33/43** | 5/12 |

净增 10 相，**没有一样品变差**（3-1 +2、4-1 +2、5-1 +2、5-3 +3、7-1 +1）。

**新增能力**：`tools/bench_real_samples.py --oracle-elements` —— 用真值化学式推出样品元素，
把其余元素全部标为必须不含，单列一套「元素上界」口径（默认关闭，不影响既有数字；JSON 增
`totals_oracle`）。这是**上界**：现实中元素来自 XRF/EDS 或配方，可能缺轻元素。

**产品含义**：界面上「样品元素」该提到显眼位置；报告里的 20/43 应标注为「无化学约束」时的值。
**不要**据此改 FoM 权重 —— 这次证明的是信息不足，不是打分不对。

**踩到的 API 陷阱**：`prescreen(elements_allowed=…)` 是「必须**全部**含有」，不是「允许集合」。
按字面传 Zn/Al/Ca/O/F 会把池缩到 76 张卡、连 ZnO 都 MISS；「只允许」必须用
`elements_excluded = 全元素表 − 允许集合`。已写进 HANDOVER §6.3⑦。

全文：`docs/基准报告-物相检索-v3.md` §20；复现探针 `_probe_31_deep_rank.py`、`_probe_31_sequential.py`。

## 元素约束产品化：一行输入框替代 113 次点击（2026-11-06）✅

§20 的结论是「多相次相缺的是化学信息」。落地时发现真正的障碍不是位置而是**表达成本**：
「只允许 Zn/Al/Ca/O/F」在预筛层只能写成「其余 113 个元素全部标红」，原来要在 118 个
周期表按钮上逐个点，没人会这么做。

| 位置 | 改动 |
|---|---|
| `xinmatch/ui/periodic_table.py` | 新增纯函数 `parse_element_symbols()`（大小写不敏感、去重、拒绝非元素符号、返回 `(known, unknown)`）+ `ELEMENT_SYMBOLS`（118，与按钮同源）；`PeriodicTablePanel` 顶部加「样品元素」输入框 + 「其余元素排除」按钮；补集模式下摘要改显示「仅允许：…（其余 113 个元素标为排除）」；手工改任一按钮或点「清除」即退出补集模式 |
| `xinmatch/ui/main_window.py` | 主工具栏 Search-Match 旁新增常显状态按钮「样品元素：未设置 / 仅 … / 自定义 N 项 / 已关闭」；点击 raise 右侧坞、翻到「限制条件」页、聚焦输入框；`_MODULE_TIPS["restraints"]` 补实测数字 |
| 提示文案 | 明写 `20/43 → 30/43` 并标注「上界（元素由真值反推）」；提醒「轻元素 O/F/C/N 漏填会误杀氧化物/氟化物」 |

**语义护栏**：检出元素一律保持 `OPTIONAL`，绝不标 `REQUIRED` —— 次相未必含主相的每个元素，
且 `elements_allowed` 是「必须全部含有」。生成的 `Restraints.elements` 全为 `EXCLUDE`，
共 `118 − len(detected)` 项，可直接进 `_current_restraints()` → `search_match` → 预筛倒排。

**验收**：`tests/ui/test_sample_elements.py` 14 项 + 既有 `test_periodic_table.py` /
`test_element_restraints.py` 共 **27 项全绿**；`ruff check .` 干净、
`mypy xinmatch/core` 97 文件 Success；离屏截图确认面板无重叠/截断。
全仓回归 **1587 passed / 4 skipped / 1 xfailed / 0 failed，15 min 22 s，exit=0**
（比上一轮 1573 多出的 14 项正是本批新增单测；收尾 counts 行照例未落盘，按进度行字符统计）。
全文 `docs/基准报告-物相检索-v3.md` §20.7。

## `prescreen_order` 默认值裁定：保持 `intensity`（2026-11-06）✅

§16.3 留下的悬置（两把尺子结论相反）用当前代码 + §17 的矿物名级细口径重测 2×2 后结案。

**先解决复现问题**：历史 2×2 靠「临时改写源码、跑完还原」，产物文件名与配置只能靠记忆认
（§6.3⑤ 的坑）。给 `tools/bench_pattern_set.py` / `tools/bench_real_samples.py` 补
`--prescreen-order {intensity,hits}`（默认 `intensity`），把 `config` 写进结果 JSON、
终端首行打印配置。`intensity` 一组与发布基线逐项一致（合成 11/13·12/13·10/13·19/24；
真实粗 10/12·20/43、细 12/13·21/50），证明参数化零行为变更。

| 指标 | `intensity` | `hits` |
|---|---:|---:|
| 合成 T1 / T5 / 序贯 / 相召回 | 11/13 · 12/13 · 10/13 · 19/24 | 8/13 · 10/13 · 4/13 · 13/24 |
| 真实粗 T1 / 卡级 / 序贯完整 | 10/12 · 20/43 · 4/12 | 11/12 · 23/43 · 3/12 |
| 真实细 T1 / 卡级 / 族级 / 序贯完整 | 12/13 · 21/50 · 20/50 · 4/13 | 13/13 · 25/50 · 28/50 · 4/13 |

**裁定：默认保持 `"intensity"`，不切 `"hits"`。**

- 合成谱 13 组里 `hits` 让 4 组 T1、2 组 T5、6 组序贯退化，**零组变好**；
  「Top-1/Top-5 不退化」是硬验收口径，单方面改默认等于绕过验收。
- 真实谱收益集中在 Top-20 广度（粗卡 +3、细卡 +4、细族 +8），代价落在榜首 / 序贯头部；
  粗序贯完整还退化 1 个样品（`3-2` 由 3→2）。细口径总量持平是退化与改善抵消的结果，
  不是「零代价」。
- 合成尺子确实用库内参考强度反演、系统性高估强度形判据，但这只说明该换更中立的
  合成尺子，不能单独给真实谱收益开绿灯。多相次相更划算的是 §20 元素约束（20/43→30/43）。

**`hits` 保留为一等选项**：`XinDBReader(prescreen_order="hits")` 与两个基准脚本参数可用。
重开条件（满足其一）：合成谱换独立强度模型 / 真实谱扩到 ≥30 组且头部不退化 /
产品侧显式签核。全文 `docs/基准报告-物相检索-v3.md` §21；复现产物
`.scratch/order_{syn,real}_{intensity,hits}.json`。

**验收**：`ruff check .` 全通过、`mypy xinmatch/core` 97 文件 Success、两个基准脚本
`--help` 与 `--prescreen-order` 实跑均正常。全仓回归
**1587 passed / 4 skipped / 1 xfailed / 0 failed，16 min 26 s**；本轮 `exit=1`
来自会话结束安全钩子拦截 pytest 临时目录清理（`SAFE_DELETE_BULK_CONFIRM_REQUIRED`，
175 项 > 50 阈值），**不是测试失败** —— 按 HANDOVER §4.1 的既定判据看进度行判绿。
本批没改任何检索代码，只给基准脚本加了可选参数，故两套尺子的发布基线逐项不变。

## COD 全库「峰抽取标定」P0：只读调研结案，症结已消失（2026-11-06）✅

转交记录 §7.2 的 P0 来自 2026-10-10 的旧行式库 `cod_full.db`：ZnO 卡只有 21 峰
（无机库 30–38 峰）、全库 Top-1 1/13，结论指向上游 CIF→峰抽取窗口 / 强度标定。
本轮**不动库、不改代码**，只做只读核查与一次基准复测。

- 两个 v3 `.xinDB` 的 `meta` 逐字一致：`build_tool=tools.build_cod_xindb`、
  `peak_convention=CuKa1-1.5406-d0.7703-30.0-merge-mult-DW-norm1000`、
  `top_k=32`、`schema_version=3`、`data_date=20261020`。
- `entries.n_peaks` 中位数都是 150（`DEFAULT_MAX_PEAKS`）；ZnO 卡 `96-210-7059`
  两库都是 **29 峰**；`n_peaks<30` 绝对数 7,385 / 7,303 几乎相同（COD-Inorg ⊂ COD-Full，
  共享同一套峰数据），占比差异只来自分母（532k vs 78k）。「全库峰稀疏」已不存在。
- 当前 COD-Full 合成谱相位级 T1 7/13、T5 11/13、序贯 8/13、相召回 17/24
  （COD-Inorg 11/13·12/13·10/13·19/24），已从历史 1/13 大幅提升。
- 4 个退化样品里 3 个的榜首是有机卡（`C13 H9 Br2 N O`、`C6 H4 S4`、`C14 H9 N O6`），
  1 个是全库多出的同组成异卡；COD-Full **93.3%** 相含 C/H（Inorg 54.0%）
  → 残余缺口是**候选池稀释**，不是峰抽取。

**裁定：不做，不启动重建。** 峰抽取属「碰峰」类，改了必须整库重建
（532,038 相 / 约 36 h / 880 MB），而两库口径本就一致、没有可标定的差异。
默认检索保持 COD-Inorg 的决定依然正确，全库仅作覆盖性挂载。若将来要追平，方向是
元素约束（§20 已产品化）/ 有机相过滤 / `tier` 分层，都不碰峰数据。
全文 `docs/基准报告-物相检索-v3.md` §22。

## COD 全库候选池稀释验证：元素约束让两个库收敛（2026-11-06）✅

§22 结案后，全库合成谱 T1 仍 7/13 vs 无机库 11/13。验证「93.3% 有机卡稀释候选池」：

- **诊断**（`.scratch/_probe_codfull_pool.py`，4 个退化样品）：真值相**全部在池内**
  （#2/#2/#3/#7），不是名额挤出；放大到 8000 席只 2/4 有效，`synth_09` 反而
  7→23。元素补集约束 4/4 抬到 #1，池 1000→56–943，单次检索快 2–3 倍。
- **全量 13 组**：给 `tools/bench_pattern_set.py` 补 `--oracle-elements`
  （与真实谱脚本对称，默认输出逐项不变，已与 §21/§22 基线逐项比对为 `True`）。

| 库 | 无约束 T1 / T5 / 序贯 / 相召回 | 元素上界 |
|---|---|---|
| COD-Inorg（默认） | 11/13 · 12/13 · 10/13 · 19/24 | **12/13 · 13/13 · 12/13 · 23/24** |
| COD-Full | 7/13 · 11/13 · 8/13 · 17/24 | **12/13 · 13/13 · 12/13 · 23/24** |

**决定性结论**：给足化学信息后两个库收敛到完全相同的四个数字，全库的全部差距
（T1 −4、序贯 −2、相召回 −2）**100% 来自多出来的有机 / 无关卡**，不是峰数据、
不是引擎、不是库规模本身。默认库选 COD-Inorg 本质是**一次隐式化学过滤**。

- **反例（如实记录）**：`synth_04` 在元素上界下 Top-1 与序贯完整都变差，两个库一致；
  真值相仍在池内（#1→#3），属排序变化而非被排除。净账 Full 6 好 1 差、
  Inorg 2 好 1 差，不写「零代价」。
- **上界口径**：元素由真值相在库内反推，现实中来自 XRF/EDS 或配方；走
  `element_inv` 倒排硬过滤、不依赖强度形，故不受合成尺子偏差影响。
- **产品含义**：§20.7 的「样品元素」输入框已覆盖此场景，挂载 COD-Full 时更该填。
  不改默认值、不动峰数据、不重建库。全文 `docs/基准报告-物相检索-v3.md` §23。

**验收**：`ruff check .` 全通过、`mypy xinmatch/core` 97 文件 Success；两组基准的
默认输出与 §21/§22 基线逐项一致（`True`）。全仓回归 1587 通过 / 4 skipped /
1 xfailed，唯一 `FAILED` 是 `test_pre_filter_hanawalt_perf_10k_under_half_second`
墙钟抖动（0.531 s > 0.5 s，起因是回归启动后并发跑了静态检查），单独无并发复跑
3 次全绿，判定环境性假失败，未改测试阈值。

## 大库元素约束引导落地 GUI（2026-11-06）✅

§23 说「挂覆盖性大库时元素约束是前提」，把它变成不打断操作的一行提示：

- `xinmatch/ui/main_window.py` 新增纯函数 `is_large_library()` 与阈值
  `LARGE_LIBRARY_PHASE_THRESHOLD=200_000`（按 `entry_count`；COD-Full 532k /
  PCOD 1.06M 触发，COD-Inorg 78k 不触发，读不到时保守不提示）。
- 工具栏在「大库 + 未设约束」时常显「样品元素：大库建议填写」；已有约束就
  让位回原状态文案。选库确认后给**非模态**状态栏提示（库名 / 相数 / 原因 /
  `7/13 → 12/13`），已设约束的用户不重复打扰。
- 两个同步时机：选库对话框确认后、`open_search_library()` 打开库后（覆盖
  「配置直接写了大库」）；注册表损坏静默降级。启动时刻意不读用户配置。
- 不弹模态框、不强制填写、不改默认值、不改 FoM、不重建库。

**验收**：`tests/ui/test_large_library_hint.py` 8 项 + 既有 3 个 UI 测试文件共
**37 项全绿**；`ruff check .` 与 `mypy xinmatch/core` 干净；全仓回归
**1595 passed / 4 skipped / 1 xfailed / 0 failed，15 min 54 s**（+8 项即本批新增单测）。
`exit=1` 是安全钩子拦截 pytest 临时目录清理（879 项 > 50 阈值），按 §4.1 判绿；
本轮启动后未并发重任务，墙钟阈值测试未再假失败。全文 `docs/基准报告-物相检索-v3.md` §24。

## 元素约束补到 CLI：`--sample-elements`（2026-11-06）✅

GUI 的「样品元素」一行输入（§20.7 / §24）在 CLI 侧还停留在手写 113 个
`EXCLUDE` 键值的 `--restraints` JSON。本轮把语义搬到命令行，并让两边共用实现：

- 新增 `xinmatch/core/model/element_symbols.py`：118 元素表 + 解析 + 补集，
  **零 PySide6 依赖**；`xinmatch/ui/periodic_table.py` 删掉本地重复实现改为
  re-export，`apply_detected_elements()` 直接调 `complement_restraints()`。
  GUI / CLI 的「检出元素保持 OPTIONAL、其余 EXCLUDE」只有一个来源。
- `search` / `run` 新增 `--sample-elements "Zn Al Ca O F"`，与 `--restraints`
  **互斥**（argparse exit 2）；FPFM 模式下明确报错而不是静默忽略；未知符号 /
  化学式 / 空输入给中文可操作错误；结果 JSON 只在显式给出时回显
  `sample_elements`，默认输出逐项不变。
- **元素表口径核过**：`cif_meta.IUPAC_ELEMENTS`（权威位表，原子序数序）、
  core 共享表、GUI 按钮网格三者都是 118 项且集合完全相同，只是排列约定不同；
  `element_exclude_filter` 对库里不存在的元素天然安全，118 项补集不会误杀。
  基准脚本的 `ALL_ELEMENTS`（91 项）是另一套上界口径，不参与 CLI。
- **真实大库冒烟**（`3-1` / COD-Full 532k 相 / `--top-n 20`）：Top-20 含禁元素
  的卡 **11/20 → 0/20**，真值 Zincite 仍 #1 且 FoM 0.773 不变，CLI 墙钟
  **3.06 s → 2.53 s（0.83×）**。证明约束进了预筛，不是只加了个回显字段。

**验收**：新增 29 项单测（core 18 + CLI 11），`tests/model` + `tests/cli` +
`tests/ui` 子目录全绿，既有 14 项 GUI 元素测试与 8 项大库提示测试仍全绿；
`ruff check .` 与 `mypy xinmatch/core` 干净；全仓回归
**1624 passed / 4 skipped / 1 xfailed / 0 failed，21 min 25 s**（+29 项即本批新增
单测，1595 → 1624）。counts 行未落盘，按 §4.1 进度行统计 `F`/`E` 均为 0；
`exit=1` 是安全钩子拦截 879 个临时项。启动前后未并发重任务，墙钟测试未假失败。
不改默认值、不改 FoM、不重建库。全文 `docs/基准报告-物相检索-v3.md` §25。

## T0.8 FoM P 值深挖：文档收尾结案（2026-11-06）✅

这是 §7.2 里最后一个不依赖外部数据/硬件的 P2。结论自 2026-10-13 就沉淀在
本文 §T0.8，但没进检索基准报告，`FOM_MODEL.md` 与 `fom_criteria.py` 还停在
「尚未解决 / 待 T0.8 反推」的时态。本轮只做文档与状态同步：

- **基准报告 §26** 收进三条结论与关键数字、五分量/发布权重表、唯一的
  lab6 ground truth、以及原本只在 `fom_criteria.py` 注释里的 `I_scale`
  归一化结论。明确区分「**决策已结案**」与「**精确 P 定义反推未完成**」
  —— 后者需要参考软件多组候选 CSV，是外部依赖，不是当前阻塞。
- **澄清 LP 语义**：LP = Lorentz-Polarization（洛伦兹-偏振因子），不是线性规划；
  权重标定用的是 NNLS + 网格坐标上升。并写清 v2 卡片库（T0.8 当时）→
  v3 建库期改强度口径 → 11-04 发现合成谱仍按 v2 强度生成、补
  `--peak-source v3` 的时间线，避免把「不做运行时全局 LP」读成与现状矛盾。
- **状态统一**：本文 Phase 0 的 T0.8 🟡→✅、收尾待办表标已关闭；
  `HANDOVER-20261106.md` §7.2 标完成并补齐原先漏写的结论 ③（次相缺失在
  recall 层）；`FOM_MODEL.md` §4 加结案交叉引用；`fom_criteria.py` 的模块
  docstring 与 `.. todo::` → `.. note::` 改为已结案措辞（纯文字）。
- **索引与溯源**：`docs/README.md` 补 §26；`ROADMAP_v3.md` Phase 0 加一条注
  （T0.8 是 STATUS.md 追加项，路线图原本止于 T0.7）。
- **可复核链如实标注**：§T0.8 引用的六个 `.scratch` 原始探针已清理，不再声称
  可直接复跑，改指向正文与后续诊断报告。

**验收**：`ruff check .` 全通过、`mypy xinmatch/core` 98 文件 Success；
`DEFAULT_WEIGHTS` 实测仍是 `0.2275 / 0.1112 / 0.2306 / 0.1152 / 0.0454`；
全仓回归 **1624 passed / 4 skipped / 1 xfailed / 0 failed，16 min 15 s**
（测试数与上轮相同，本批无新增用例）。counts 行未落盘，按 §4.1 进度行统计
`.`1624 / `s`4 / `x`1 / `F`0 / `E`0；无 `FAILED` / `ERROR` 行；`exit=1` 是
安全钩子拦截 pytest 临时目录清理（196 项 > 50 阈值）。启动前后未并发重任务。
不改权重、不改 P 定义、不改强度惯例、不重建库。
全文 `docs/基准报告-物相检索-v3.md` §26。

## CLI 大库引导一致性（2026-11-07）✅

§24 的「挂大库建议填样品元素」原本只在 GUI；CLI 是自动化链路，最容易
`--db` 直接指向 880 MB 的 COD-Full，却没有任何提示。本轮补齐：

- 阈值与判据下沉 `xinmatch/core/db/library_scale.py`（**零 PySide6**，
  脏值保守 `False`）；`main_window.py` 改为显式 re-export，UI 测试固定
  GUI 与 core 是**同一个对象**，两处魔数不会漂移。
- `search` / `run` 打开库后调 `_emit_large_library_hint()`：相数走
  `XinDBReader.entry_count()`（读 `meta`，**O(1)**，非 `COUNT(*)` 全表扫描）；
  提示**只写 stderr**，`--json` 的 stdout 仍是一个完整 JSON。
- 三种情况不打扰：已有元素约束（判据是 `restraints.elements` 非空，不是
  「有没有 `--restraints` 参数」—— 只设晶系时仍提示）、FPFM 模式（不接
  元素约束，建议会误导）、`--no-library-hint` 新开关（文案里写明出路）。
  读不到相数静默降级，绝不影响检索。

**验收**：新增 30 项单测（core 5 + CLI 24 + UI 1；三文件合跑 38 项含 UI 原有 8 项）；`tests/db` + `tests/cli` +
`tests/ui` 子目录全绿；`ruff check .` 与 `mypy xinmatch/core`（99 文件）干净；
全仓回归 **1654 passed / 4 skipped / 1 xfailed / 0 failed，16 min 8 s，exit=0**
（= 上轮 1624 + 30；counts 行未落盘按 §4.1 进度行判绿，本轮连安全钩子都未触发）。
不改检索默认值、不改 FoM、不重建库。
全文 `docs/基准报告-物相检索-v3.md` §27。

## IUCr CPD 标准谱接入基准（2026-11-07）✅

前两把尺子各有一个已记录的盲区：合成谱的强度形一致性是人为成立的；13 组实验室谱
的三组混合样本**没有定量含量**，所以「次相小到多少还能找到」答不了。IUCr CPD 标准
样品补这一格 —— 真实扫描 + 官方 weighed wt%，`CPD-1A`…`1H` 是同一三相体系
（刚玉/锌白/萤石）的八个配比，从 **1.15 wt% 到 94.81 wt%**。

- 新增 `tools/bench_iucr.py`：19 个评分样本 / 48 个真值相；9 个样本逐条排除
  （`SILICA` 非晶、药物 5 相库内不可达、`PHARM1GR/2GR` 真值不完整、
  `GRANODIO` 无真值）。`_raw` 优先 / `_mdi` 次之 / 裸名兜底（`CPD-1F/1G/1H`
  只有裸名）。
- **主口径改为矿物名级**（与 §17 相反）：本数据集的天然多相样品真值相都落在同组成
  多晶型族里（BAUXITE 的 Gibbsite/Bayerite、Kaolinite/Dickite、Anatase/Rutile、
  Quartz 309 张）。但实测**否掉了「组成级会系统性高估」的预判** —— 两口径总数相同
  （39/48 卡级、44/48 族级），偏差双向：组成级误判 BAUXITE 的 Boehmite（同组成异名
  卡占位）、漏判 CPD-2 的 Brucite（库内 Brucite 多为氘代，元素集含 D）。`--coarse`
  保留对照，默认关闭。
  > **口径修订（同日晚，见下一节）**：族级判定修好后 fine 族级 **44/48 → 45/48**、
  > wt **0.987 → 0.995**；上面那句「偏差双向」里的 Boehmite 一半是族级实现缺陷
  > 造成的假差异，修完只剩组成级单向漏判 Brucite。
- **主结果**（COD-Inorg 78k / COD-Full 532k）：plain（只给谱）族级 27/48 与 25/48、
  wt 加权 0.778 / 0.762；elements（给样品元素）两库**都是 44/48、wt 0.987**。
  **库扩大 6.8 倍，给元素时相召回一格未动**；不给元素时掉 2 个相。
- **含量—召回曲线**（12 个多相样本 41 个相）：<5 % 桶由 1/7 → **5/7**、5–20 % 由
  4/11 → **9/11**、20–50 % 由 8/15 → **15/15**。`CPD-1A` 的 **1.15 wt% 刚玉**
  plain 漏、elements 找回（族级 3/3、wt 1.000）。
- **三个诊断**：① `CPD-1F/1G/1H` 的萤石丢失是预筛 `rank_limit=1000` 截断
  （`n_prescreened=1000, truncated=True`；给元素后 366 张、不截断，萤石回到 Top-5
  第 3 位），不是评分失败；② `BRUCITE` 单相 001 峰强度是第二强峰的 **5.1 倍**
  （择优取向），plain 排 100 名外、elements 第 8 名；③ 药物 5 相在 COD-Full 里
  同组成卡全是异构体（山梨醇/乳糖/正缬氨酸/糖酐），Nizatidine 化学式 0 张 ——
  **库覆盖缺口，不是引擎问题**。
- `tools/bench_real_samples.py`：`truth_entry` / `fine_hit_entry` 由私有改公开，
  两个基准共用同一个「命中」定义（零行为变化）。

**验收**：`ruff check .` 全通过、`mypy xinmatch/core` 99 文件 Success；全仓回归
**1654 passed / 4 skipped / 1 xfailed / 0 failed，13 min 51 s**（本轮只动 `tools/`，
无新增用例，故与上轮同数；按 §4.1 进度行统计 `.`1654 / `s`4 / `x`1 / `F`0 / `E`0，
无 `FAILED` / `ERROR` 行；启动前后未并发重任务）。基准实测两库各一次（Inorg 64 s /
Full 2 min 24 s），元素约束上界与 `--coarse` 对照均已跑通。

全文 `docs/基准报告-物相检索-v3.md` §28。不改检索默认值、不改 FoM、不重建库。

## 族级口径修复：从「族代表卡」到「族内任一成员」（2026-11-07）✅

由「BAUXITE 七相只召回 3 个」的只读诊断引出。诊断三条结论里两条归引擎/数据（只记录），
一条是**基准自己的 bug**：

- **缺陷**：族级指标语义是「同一物相的多张卡只占一个位置」，实现却是每族只取族首卡
  （`candidates[g[0]]`），等于偷偷换成「族首卡是不是真值相」。COD 里拼写变体/不同设置/
  掺杂卡会同族并存，而族首名次与拼写对错无关 —— BAUXITE 的 Boehmite（14.93 wt%）
  族 6 里 **rank 10 是错拼 `Bohmite`（族首）、rank 15 才是 `Boehmite`**，主相被判漏检。
  先排除的假线索：折叠深度（`deep_n` 100/200/400 三档全同）、候选顺序（deep 100 与 1000
  前 30 张 ID+FoM 逐张一致）。
- **修法**：`tools/bench_real_samples.py` 新增 `family_members(cards, top_n)`（返回前
  top_n 族、每族带全部成员卡），`bench_iucr._score` 与 `bench_real_samples` 三处族级判定
  （粗 / 细 / 元素上界）一律改用它。族的**排名**不变，只改「这一族算不算命中」。
- **重跑**（只改判据，卡级 / Top-1 / Top-5 / 序贯 / 预筛必须不动，实测吻合）：
  IUCr 族级 **44 → 45/48**、wt **0.987 → 0.995**（Inorg 与 Full 同）；含量梯度 5–20 % 桶
  **9/11 → 10/11**；13 组实验室谱粗族级 **20 → 21/43**、细族级 **20 → 22/50**
  （`5-2/5-2b` 的方解石）；元素上界族级 33/43 与 `prescreen_order=hits` 细族级 28/50
  **逐项不变**（§21 裁定依据不受影响）。逐相对照脚本报 IUCr「变化条目 1」＝ BAUXITE
  Boehmite 一处。
- **连带纠正**：§28.2 的「两口径偏差双向」有一半是假差异 —— Boehmite 那条不是组成级
  误判，是族级实现缺陷。修完只剩组成级单向漏判 CPD-2 的 Brucite（fine 45 vs coarse 44）。
  `COARSE_NOTES`、`bench_iucr` 模块文档、HANDOVER §6.6、工作记忆均已按实测改写。
- **只记录不动引擎的两条**：① Kaolinite 择优取向（`peakpos` 0.800 而 `intensity` 0.000，
  001 线实测 137 / 全谱最强 5000，与 BRUCITE 001 被放大 5.1 倍是同一效应的两个方向）；
  ② 序贯被单质卡吃轮次（#5 `Silicon`、#6 `Hydrogen` 都在允许元素集内 →
  **元素约束只能排除「元素不可能」，不能排除「物相不合理」**）。
- 顺带修 `bench_iucr` 收尾行的 `wt_hit / wt_sum` 零除崩溃（全部样本被跳过时 traceback）。

**验收**：`ruff check .` 全通过、`mypy xinmatch/core` 99 文件 Success；全仓回归
**1654 passed / 4 skipped / 1 xfailed / 0 failed，17 min 58 s**（进度行 `.`1654 / `s`4 /
`x`1 / `F`0 / `E`0；`exit=1` 仍是安全钩子拦 pytest 临时目录清理，`count=942`）。
首轮曾出现 **1 例偶发失败**（进度行 65 % 处一个 `F`，`-q` 摘要行未落盘故无法指名），
`pytest --lf` 单跑即通过，重跑全绿；两轮墙钟 21 min 38 s / 17 min 58 s 均慢于上一轮
13 min 51 s，按「偶发 + 环境偏慢」记录，不作为代码问题。

全文 `docs/基准报告-物相检索-v3.md` §29。不改引擎、不改 FoM、不改预筛默认值、不重建库。

## 序贯单质卡：证据驱动的「不动」决策（2026-11-07）✅ 已评估，不做

§29.6 记下「BAUXITE 序贯第 5/6 轮被 `单质:Si`、`单质:H2` 占掉」，当时推论「需要单质/
气相相过滤」。本节把它拿到数据上验：

- **规模**：单质卡（元素集只有 1 个元素）COD-Inorg **1,413 张（1.81 %）**、COD-Full
  同一批 1,413 张（0.27 %）。Top-20 里出现频率：IUCr 27/760（3.55 %）、真实谱 13/520（2.50 %）。
- **三档 A/B**（32 组样本 × 8 轮，只改「每轮选哪张卡」）：现状 143、只跳双原子/气相
  单质 **143（零增益）**、跳所有单质 **145**。有物理依据的窄规则没有用 —— BAUXITE 的
  `H2` 在第 6 轮，跳过它不改变前 5 轮。增益来自跳**金属单质**：BAUXITE 多找回
  **Anatase（2.00 wt%）**、`5-3` 上界多找回 **Fluorapatite**。
- **反事实**：库内没有单质谱，用单质卡峰位/强度合成理想粉体谱（Gauss 0.12°/背景 20/
  0.02° 步长），Si / Al / Fe / Zn / Cu / Mg **6/6 现状第 1 位命中，跳过单质后 6/6 失效**
  （第 1 轮就丢真值，残差被污染后 7 轮救不回来）。
- **裁定**：**不改默认值**（取榜首）。理由：① 增益 +2 相属噪声量级（单相缺失就能让一个
  桶跳 14 个百分点）；② 有物理依据的窄规则零增益；③ 代价是确定的 6/6；④ 序贯真正的
  瓶颈是择优取向与最低含量相，不是单质卡 —— `all` 变体也没救回 Kaolinite。
- **重开条件**：有真实单质标样谱可复现对照 + 只在用户显式声明「不含单质相」时启用 +
  三把尺子同时不劣化。

三个探针只读（`.scratch/_probe_elemental_cards.py` / `_variants.py` / `_standard.py`），
**未改动任何产品代码与基准判定口径**，故本轮无代码变更、无回归数字变化。

全文 `docs/基准报告-物相检索-v3.md` §30。

## 择优取向 / 强度形失配：证据驱动的「不动」决策（2026-11-07）✅ 已评估，不做

§29.6 ① 与 §30.4 ④ 都把 Kaolinite 的漏检归给「择优取向」。本轮把它拿到数据上验，
**归因被推翻**：

- **分类**（98 真值相，候选池最佳卡的 `p_values`）：命中 65、**强度形失配 29**、
  候选池无卡 4、**峰位失配 0**（最低 `peakpos` 0.663，还是通过的 BRUCITE）。
  **没有任何失败相是「位置对不上」。**
- **逐对拆解**：Kaolinite `mean(Δ²)=805`，最大单对 7,433（占均值 923 %）是 001 被压
  （I_ref 100 → I_exp 13.8）；但紧随其后的**四个大偏离全是正向**（26.64°/35.65°/28.17°/
  64.00° 处参考强度 18.3/4.5/4.2/0.8，实测 996/75/67/53）—— 是**别的相强峰误配到它的
  弱线上**。删掉 001 那一对，P 也只从 0.00032 到 0.00127。反面证据：Gibbsite 通过，最大
  偏离同样是别人的峰（33.19° 参考 0.6 → 实测 25.4）；Brucite 001 被放大 5.1 倍，
  **没进它自己的偏离前六**。
- **结构性缺陷**：`mean(Δ²)` 惩罚「配对得多」的卡（real/3-1 萤石 11/17 对 → P=0.000，
  排不过 4/17 对的卡）。换估计量的实验（只动强度分量，其余四个不变）：

  | 变体 | 命中/98 | Δ | 涨/跌 | Top-1/32 |
  |---|---:|---:|---:|---:|
  | `base` | 70 | +0 | — | 31 |
  | `trim10` | 73 | +3 | +7/−4 | **31** |
  | `trim25` | 74 | +4 | +7/−3 | 30 |
  | `trim40` | 73 | +3 | +7/−4 | 31 |
  | `q75` | 72 | +2 | +7/−5 | 29 |
  | `median` | 74 | +4 | +8/−4 | 30 |

  **所有变体涨的是同一批 7 个相**（现状名次 25–52），跌的一直是那 4 个（现状名次 15–18）
  —— 是**零和交换，不是修好**。
- **那处 Top-1 退化是命名口径**：`real/2-1` 的 `median` 新榜首 `96-702-2027 C Ca O3` 是
  **R-3c、a=4.9915、c=17.0880**，就是方解石；两个变体的榜首**都是真值相**。判它不中的
  唯一原因是卡名写 `"Calcium Carbonate"` 而真值别名只有 `"Calcite"`。别名缺口审计 11 行，
  **不改变任何已发布的命中数**（「该补」五行里四行真值本来已命中、一行两侧都在榜外），
  所以不需要第三次重跑历史数字。
- **裁定**：**不改默认值**。① 净增益是零和交换；② 真实病因在上游（参考弱线误配），改
  残差统计量治不了，要动得动 `correlate`（碰物理量）；③ 强度分量只占 **15.2 %** 权重却能
  翻转 11 个相，说明 Top-20 是软边界，按 +3 调参等于按噪声调参；④ 缺精度侧指标，任何
  「提召回」的重排都无法被证伪。
- **重开条件**：有精度侧指标 + 上游先解决弱线误配 + 三把尺子同向为正且 Top-1（补齐别名后）
  不退化 + 长度偏置显式归一。

八个探针只读（`.scratch/_probe_po_shape.py` / `_pairs.py` / `_variants.py` / `_trim.py` /
`_sparse.py` / `_boundary.py` / `_top1_check.py` / `_alias_gap.py`），**未改动任何产品代码
与基准判定口径**，故本轮无代码变更、无回归数字变化。

全文 `docs/基准报告-物相检索-v3.md` §31。

## 上游配对与 FoM 分量消融：证据驱动的「不动」决策（2026-11-07）✅ 已评估，不做

接着 §31 的结论往下查两件事：**能不能在上游修配对**、**五个 FoM 分量各占多少分量**。

- **配对已经是一对一**。`_greedy_correlate` 维护 `matched_ref`，实测 5,721 张候选卡里
  exp / ref 索引**重复各 0 次**。所以 §31.7 写的「例如一对一强制分配」是**假选项**，
  已在该节加注更正。另一个上游选项 `ref_cut`（只用 I_ref_norm ≥ 10 的对）只有 **+1**。
- **弱线是多数配对，却是少数偏差**（5,721 张卡聚合）：

  | 组 | 卡数 | 弱线占配对数 | 弱线贡献 `ΣΔ²` | 弱线均 `Δ²` | 强线均 `Δ²` |
  |---|---:|---:|---:|---:|---:|
  | 强度形通过 | 1,172 | 71.6 % | 34.4 % | 14.1 | 67.9 |
  | 强度形失败 | 4,549 | 78.3 % | **47.8 %** | 317.7 | **1,250.0** |

  失败卡的偏差质量一半以上来自**强线**对 —— 即「该相的强线在实测里本来就弱」（次相 /
  择优取向 / 被压制）。**§31.2 的「弱线劫持」只能解释 Kaolinite 那类具体病例，不是 29 个
  失败相的普遍机制**，该节结论段落已按此改写。这也解释了 `ref_cut` 为何只有 +1：它只拿掉
  了 34–48 % 的偏差质量。
- **五分量消融**（只改 `compute_fom` 权重，按尺子分开）：

  | 变体 | Δ | IUCr/48 | real/50 | 涨/跌 | Top-1/32 |
  |---|---:|---:|---:|---|---:|
  | `base` | +0 | 39 | 31 | 0/0 | 31 |
  | `drop_peakpos` | −3 | 39 | 28 | 0/3 | 28 |
  | `drop_intensity` | +3 | **42** | **31** | 7/4 | 30 |
  | `drop_npeaks` | −3 | 39 | 28 | 1/4 | 29 |
  | `drop_ncorr` | −1 | 39 | 30 | 0/1 | 30 |
  | **`drop_i_scale`** | **+2** | 40 | **32** | **2/0** | **31** |
  | `intensity × 3` | −1 | 40 | 29 | 2/3 | **27** |
  | `drop_int+i_sc` | +4 | 43 | 31 | 11/7 | 29 |

  `peakpos` / `npeaks` 是承重墙；`intensity` 的 +3 **全部来自 IUCr、真实谱 +0**（跨不过
  尺子），加倍则 Top-1 掉 4 格；`i_scale` 是**唯一双尺子同向（+1/+1）、零损失、Top-1 不动**
  的候选，但只有 +2 相、且缺精度侧指标。
- **裁定**：配对与权重**都不动**。① 配对层没有可修缺陷；② 权重是参考软件发布值，§26 已
  裁定保持，改它就是改产品语义；③ `intensity` 在两把尺子上符号相反，说明它在这批数据上
  没有稳定判别力；④ `i_scale` 登记为唯一候选，但需先补合成尺子 + 精度侧指标 + 与 §26 对账。

两个探针只读（`.scratch/_probe_pair_weak.py` / `_probe_fom_ablation.py`），`compute_fom`
只被传入不同权重字典，**产品代码一行未动**，本轮无回归数字变化。

全文 `docs/基准报告-物相检索-v3.md` §32。

## `i_scale` 三把尺子 A/B：证据驱动的「不动」决策（2026-11-07）✅ 已评估，不做

§32.5 给 `i_scale`（唯一双尺子同向候选）定了三条重开条件，本轮把 ①② 做掉，并加了
「截断尾巴」这个更保守的对照。

- **无界尾巴是假警报**：`|ln s|` p50 0.181（扣 0.008）、p99 2.238（扣 0.102）、
  **max 6.734（扣 0.306）**，`> 1` 占 9.9 %。但 `clamp1.0` 在**三把尺子上每一格都与
  base 相同**（召回 / Top-1 / Top-5 / `fp_above` 全等）—— 被重罚的那 9.9 % 的卡本来就
  远在 Top-20 之外。**「惩罚项无界」不等于「需要截断」，得先测它影响的样本是否落在边界上。**
- **四变体 × 三把尺子**（召回 / Top-1 / Top-5 相 / `fp_above` 均值）：

  | 尺子 | base | `i_scale=0` |
  |---|---|---|
  | 合成 24 相 | 16 · 8/13 · 13 · 9.83 | 16 · 8/13 · 13 · **10.00（差）** |
  | IUCr 48 相 | 39 · 9/19 · 24 · 7.74 | **40** · **10/19** · 24 · **6.58（好）** |
  | 真实谱 50 相 | 31 · 9/13 · 17 · 9.31 | **32** · 9/13 · 17 · **10.08（差）** |

  `clamp1.0` / `clamp0.5` 召回一格未动。
- **裁定**：默认值不动。条件 ① 通过（合成尺子三格全等）、**条件 ② 不通过**（`fp_above`
  两把变差 +0.77 / +0.17、一把变好 −1.16）。机制上它也不是修 bug —— 唯一像 bug 的东西
  （无界尾巴）不影响排名，剩下的是 6.2 % 权重的重新分配。`i_scale` 由「唯一候选」降为
  **不推荐**；重开只在出现**序贯口径**正向证据时考虑。
- **横向结论**：§31/§32/§33 三项连测下来，所有单点排序改动都在 ±3 相（±3 %）量级且
  伴生反方向变化。**Top-20 是软边界，按这个量级调参等于选噪声**；真杠杆在化学信息
  （§20 元素约束 +10 相）与候选池（§23 预筛截断），不在权重。

探针只读（`.scratch/_probe_iscale_three_rulers.py`），`clamp*` 在探针内重算，
**产品代码一行未动**，本轮无回归数字变化。

全文 `docs/基准报告-物相检索-v3.md` §33。

## 候选池上界：量到顶了，唯一量级够的旋钮是 Top-N（2026-11-07）✅ 只读量化

§31–§33 证明排序权重没便宜可捡，本轮量另一半：**真值相进没进候选池**。

- **池外只剩 1 相**（`candidate_limit = top_n = 2000`）：Top-20 69、21–100 20、
  101–500 7、501–1000 1、**1001–2000 = 0**、池里根本没有 1（1.0 %）。那 1 相是
  `real/7-2` 的 Hornblende，库里**有** `'Hornblende'` 卡 → **预筛漏捞**，不是覆盖缺口。
- **放大候选池是负收益**：`candidate_limit` 1000 → 2000，Top-20 命中 **70 → 69**。
  多出的 1000 张卡没捞回任何一相，只挤掉 1 个真值相。与 §23「收益在给元素约束那一步、
  不在加名额」一致。
- **28 相是排序问题**：20 名外的名次区间 22–796，**中位 52**。
- **唯一量级够的旋钮是 Top-N**：

  | Top-N | 20 | 30 | 50 | 100 | 200 |
  |---|---:|---:|---:|---:|---:|
  | 命中 | 69 | 75 | **83** | 89 | 93 |

  Top-20 → Top-50 多覆盖 **14 相（+14.3 pt）**；§31/§32/§33 所有排序改动最好成绩是 **+3 相**，
  差一个数量级。**Top-20 的 70.4 % 与 Top-50 的 84.7 % 差的不是引擎能力，是展示预算。**
  这是产品决策（界面显示多少行），本项不下结论，只把数字摆出来。
- **预筛截断只在 4/32 样本**（`5-2` / `5-2b` / `5-3` / `7-2`，全是峰最多的谱），
  其余 28 个样本池 34–2000 不等、根本没被截断；而这 4 个加名额也捞不回相。

探针只读（`.scratch/_probe_pool_ceiling.py`），只把 `candidate_limit` / `top_n` 调大，
**产品代码一行未动**，本轮无回归数字变化。

全文 `docs/基准报告-物相检索-v3.md` §34。

## Top-N 上调可行性：族级口径修正 + 方案 B（2026-11-07）✅ 调研完成，待排期

§34.5 摆出的「Top-20 → Top-50 多覆盖 14 相」是**卡级**数字；GUI 候选表按**族合并**显示，
本节按族口径重算并做完落地调研。

- **口径修正**：族级（一行 = 一个相族）现状 20 行 = **81/98（82.7 %）**，不是卡级 70.4 %
  —— 族合并本身是一层「免费召回」。提到 50 行 = **89/98（90.8 %）**，收益 **+8 相**，
  不是 +14。引用 §34 必须改读 §35.1。
- **Top-N 的全部调用点**：core 六处默认 20、CLI 两处 `--top-n`（默认 20，用户可调）、
  GUI 三处（整谱检索不传、序贯显式 20、FPFM 不传）。**计算成本为零** —— 打分对整个池
  完整算完，`top_n` 只是切片。
- **映射陷阱**：族合并只减行数，「显示 50 个族」需要返回多于 50 张卡。
- **测试坑**：`tests/ui/test_fpfm_kalpha2.py`、`test_search_mode.py` 用
  `kwargs.setdefault("top_n", 10)` 钳 GUI 调用提速；GUI 若**显式传** `top_n=200`，钳位失效、
  测试变慢 → **必须走设置项**。其余测试显式传参，无「默认 20 行」断言；CLI 默认不动即无兼容问题。
- **建议方案 B**：加第 4 个设置项「候选列表族数上限」（默认 50，QSettings，与现有三个
  FPFM 旋钮同一模式），GUI 三处调用取 200 张卡、表格按族合并后截到上限；报告/打印与表格
  同源。CLI 不动。
- 判定：**值得做**（+8 相、零计算成本、实现面小），作为独立小项排期；默认值 50 属产品决策。

探针只读（`.scratch/_probe_pool_ceiling.py`），**产品代码一行未动**。

全文 `docs/基准报告-物相检索-v3.md` §35。

## 方案 B 落地：候选列表行数上限 max_display_rows（2026-11-07）✅ 实现完成

§35.5 建议的方案 B 已实现并验收通过。**CLI 与检索引擎零改动**，全部落在 GUI 层。

- **设置项**：设置 → 选项 → 候选列表 → 「候选列表行数上限（折叠时按族计）」，
  默认 **50**，YAML 持久化（`candidate_list.max_display_rows`）。
- **换算 helper**：`main_window._candidate_row_budget()` → `(fetch, max_rows)`，
  `fetch = min(1000, max(200, 4 × max_rows))`；脏值（非正数/非整数/None）回退默认。
- **三处检索入口显式传 `top_n=fetch`**：整谱 `search_match`、序贯 `search_residual`
  （原显式 20）、FPFM `search_match_fpfm`（prescreen 名额不动，只放大切片）。
  `top_n` 只影响切片，打分成本与它无关（§34），成本增量≈0。
- **表格模型层截断**：`_CandidateListModel.set_max_rows()`，`_rebuild_rows` 末尾
  `visible[:N]`——折叠时前 N 行 = 前 N 个族，展开时前 N 张卡；0/负数归一不截断；
  跨 `set_candidates` 保持。
- **报告同源**：`_run_report_preview` 改用 `candidate_table.visible_results()`，
  报告候选行数与用户看到的完全一致（折叠模式只列族代表）。
- **存档不受影响**：`win._candidates` 仍持全量，`.xinm` 的 `candidates=[...]` 不截断。
- **测试钳位的坑（§35.4）落地核实**：`setdefault("top_n", 10)` 钳位确实失效，
  但夹具库极小、top_n 只影响切片，实测两个测试文件 17 用例耗时无可见变化，
  无需改造。
- **验收**：新单测 `tests/ui/test_candidate_max_rows.py` 19 用例全绿；受影响 UI 子集
  （tables/main_window/sequential_ui/v131_ux 64 + search_mode/fpfm_kalpha2 17）全绿；
  `ruff check .` 通过、`mypy xinmatch/core` 99 文件 Success；全量 pytest 回归判绿。
- **行为变化**：候选表默认最多 50 行（合并后 ≤50 族），整谱检索返回卡数 20 → 200。
  三把尺子基准数字不受影响（基准直连引擎，不经 GUI）。

全文 `docs/基准报告-物相检索-v3.md` §36。

## 真值别名表补齐 + §31.5 分类更正（2026-11-07）✅ 已完成

§31.5 登记的小项落地。**只改基准判据的真值侧**（TRUTH_FINE / IUCR BAUXITE），
引擎与产品代码一行未动；`mineral_name.py` 归一化语义不变。

- **补 4 个别名**（逐卡核过晶胞）：`Calcite` ← `"Calcium Carbonate"`（96-702-2027，
  R-3c）与 `"CaCO3"`（96-702-0139，R-3c）；`Boehmite` ← `"Bohmite"`（96-901-2273/74/75
  错拼，Cmcm）；`Feldspar` ← `"Orthoclase"`（正长石 = K-长石种名）。
- **刻意不收 1 个，并更正 §31.5**：`Corundum ← "eta- Al-oxid_fit2gnn"`（96-110-1168）
  空间群 **Fd-3m** = 尖晶石型 η-Al₂O₃，不是刚玉 R-3c —— 与 Rutile←Anatase 同类的
  **正确拒绝**。原表误列「该补」；移走后原「不改变已发布命中数」的记账矛盾同时解开
  （该行 12/52 两侧都不在 Top-20，若补进会让细卡级凭空 +1）。
- **验收：两把尺子逐项零变化** —— 真实谱粗 10/12·12/12·20/43·21/43·4/12、细
  12/13·13/13·21/50·22/50·4/13；IUCr plain 26/48·27/48·0.778、elements
  39/48·45/48·45/48·0.995；含量梯度 5/7·10/11·15/15。全部与文档已发布值一致。
- 新单测 `tests/tools/test_truth_aliases.py` 9 用例；ruff 通过。
- 坑：bench_iucr 必须以 `python -m tools.bench_iucr` 跑，直接脚本方式调用会因
  `tools.bench_real_samples` 导入报 ModuleNotFoundError。

全文 `docs/基准报告-物相检索-v3.md` §37（§31.5 加更正注）。

## GUI 批次 1 接线：5 个占位模块动作接到既有能力（2026-11-07）✅ 已完成

P2「GUI 剩余向导 / 主题」拆解后的第一批。盘点结论先行：T13.0–T13.8 其实全部 ✅
（主题/精修向导早已落地），「剩余」的真实含义是 15 个功能模块里有 11 个
菜单/工具栏动作仍是 `_placeholder` 占位。本批把其中 5 个接到既有能力，
**零新逻辑、零 core 改动**：

- `data_import` → `_open_data_file`（与工具栏「打开数据…」Ctrl+O 同槽）；
- `raw_processing` → 聚合子菜单（背景扣除 / 平滑 / Kα2 剥离 / 重置，同一批
  QAction 对象，工具栏与菜单永远同步；子菜单在四个动作创建之后挂载）；
- `peak_list` → `_detect_peaks`（与工具栏「峰检测」同槽）；
- `restraints` → 新增 `_focus_restraints`：右侧坞限制条件页翻到最前
  （与 `focus_sample_elements` 的样品元素引导区分开，状态栏提示不同）；
- `rietveld` → `_open_refinement_wizard`（与精修向导 Ctrl+Shift+W 同槽）。

仍占位（批次 2+，各有 core 能力待封装）：`data_export`（导出聚合菜单）、
`profile_fitting`（`core.peak.profile_fit`）、`quant_analysis`（`core.quant`
RIR/内标）、`microstructure`（`core.micro` 晶粒尺寸/微应变）、`indexing`
（`core.index` DicVol/Treor）、`user_db`（无 core 能力，需求待定）。

- **测试**：新 `tests/ui/test_module_wiring.py` 7 用例（同槽断言 / 子菜单聚合 /
  dock 翻页 / 占位模块仍播报）；同步更新 `test_main_window.py` 与
  `test_shortcuts.py` 里两处以 `raw_processing` 为占位示例的旧断言。
  `tests/ui` 全套 170 用例通过；ruff / mypy(99) 通过。
- **实现注意**：模块动作循环先于四个预处理动作创建执行，子菜单必须挂到循环
  外（`_build_actions` 末尾），否则 `AttributeError: background_action`。

## GUI 批次 2 接线：数据导出聚合菜单 + 三张表 CSV 导出（2026-11-07）✅ 已完成

「数据导出」模块动作从占位接成**聚合菜单**（7 项），并把三张数据表悬空的
`export_requested` 右键信号接上——此前右键「导出 (CSV)...」点了没有任何反应。

- **聚合菜单**（`data_export` 动作，图谱能力全部既有）：
  1. 导出谱图 (ASCII profile)… — `core.io.exporters.export_ascii_profile`
     （start/step/end 头 + 强度，可被 `read_ascii_profile_3col` 原样读回）；
  2. 导出谱图 (两列 2θ–I)… — `export_ascii_2col`；
  3. 导出峰列表 (CSV)… — 新方法 `_export_peak_list_csv`
     （2θ/d/I/I-I₀/FWHM/hkl）；
  4. 导出候选列表 (CSV)… — `_export_candidates_csv`（与界面显示同源：
     `visible_results()` 截断口径）；
  5. 导出匹配列表 (CSV)… — `_export_matches_csv`
     （entry/化学式/scale/weight_pct）；
  6. 导出物相分析（.xinm）… / 7. 导出所选相 CIF… — 复用既有动作（同对象）。
- **信号接线**：`peak_table` / `candidate_table` / `match_table` 三处
  `export_requested`（右键「导出 (CSV)...」）此前均无 handler，统一接到
  对应导出方法。
- **CSV 编码**：utf-8-sig（Excel 双击打开不乱码）+ LF；表头用英文列名。
- **数据访问器**：`PeakListTable.peaks()` 与 `MatchListTable.phases()` 新增
  （模型 `_peaks` / `_phases` 的公开转发）。
- **守卫**：无谱图/无峰/无候选/无匹配时 information 提示，不抛异常；写文件
  异常走 critical 提示（GUI 动作边界）。
- **测试**：新 `tests/ui/test_export_menu.py` 14 用例（聚合菜单结构 + 谱图两种
  格式 round-trip + 三表 CSV 内容 + 四个空守卫 + 信号接线）；同步更新
  `test_main_window.py` / `test_module_wiring.py` 里以 data_export 为占位示例
  的两处旧断言。tests/ui 全套通过；ruff / mypy(99) 通过。
- **实现注意**：聚合菜单必须在 `_build_menus` 末尾挂载——它引用同方法上方才
  创建的 `export_xinm_action` / `export_cifs_action`（`_build_actions` 循环阶段
  尚不存在）。

## GUI 批次 3：Profile Fitting 对话框（2026-11-07）✅ 已完成

`profile_fitting` 模块动作（F5 快捷键同一入口）从占位接成真实对话框
`xinmatch/ui/profile_fit_dialog.py`。**计算全委托
`core.peak.profile_fit.fit_profile`（多峰最小二乘，scipy TRF），不重写算法。**

- **输入**：当前谱图 + 峰列表初始猜测（`peak_table.peaks()`）；无谱图 / 峰列表
  为空时 information 提示，不打开对话框。
- **选项**：谱形四选一（pseudo-Voigt 默认 / Gaussian / Lorentzian / Pearson VII）。
- **运行**：`run_with_busy` 工作线程执行，异常走 critical 提示。
- **输出**：
  * 结果表——每峰精修 2θ / FWHM / 面积 / 相对强度 I-I₀（按最强峰归一）；
  * Rwp（加权剖面 R 因子）标签；
  * 拟合曲线叠加到谱图区（再拟合替换上一条；对话框关闭时移除）；
  * 「应用到峰列表」→ `fit_applied` 信号 → 主窗口 `peak_table.set_peaks`
    写回精修峰（此后可重新 Search-Match）。
- **测试**：新 `tests/ui/test_profile_fit_dialog.py` 9 用例（构造默认值 /
  双高斯合成谱拟合出表 + 叠加 +1 / apply 信号 / 关闭移除曲线 / 再拟合替换 /
  两级守卫 / 模块动作打开对话框且不再占位播报）；同步更新
  `test_shortcuts.py` 的 profile_fit 断言（无谱图走 information 守卫）。
  tests/ui 全套通过；ruff / mypy(99) 通过。
- **坑**：对话框不自动把实验谱加进谱图区（测试要先 `set_pattern`）；
  隐藏对话框里的子控件 `isVisible()` 恒 False，要用 `isHidden()` 取反断言。

## GUI 批次 4：RIR 定量分析对话框（2026-11-07）✅ 已完成（全量回归待机器空闲后补跑）

`quant_analysis` 模块动作从占位接成真实对话框 `xinmatch/ui/quant_dialog.py`。
**计算全委托 `core.quant.rir.rir_quantify`（Hill–Howard 绝热法，wt% 归一到
1.0），不重写算法。**

- **输入**：已确认物相（`match_table.phases()`）+ 当前峰列表
  （`peak_table.peaks()`）；无已确认物相时 information 提示，不打开对话框。
- **主峰强度**：每相取 `phase.correlations` 指向的实验峰的最大积分强度
  （重叠分解由上游 Search-Match 的相关记录承担，本对话框不做分解；
  越界索引保护，缺省 0.0）。强度为 0 的相不参与计算，wt% 列显示「—」。
- **RIR 列**：默认 1.0、逐相可编辑（参考软件同样由用户按 PDF 卡片填 I/Ic）；
  相名 / 强度 / wt% 三列只读。
- **输出**：「计算 wt%」回填 wt% 列（百分数两位小数）；「应用到匹配列表」→
  `quant_applied` 信号 → 主窗口把 wt% 写回 `Phase.weight_fraction` 并
  `match_table.set_phases` 刷新（之后可用「数据导出 → 导出匹配列表 (CSV)…」
  带走 weight_pct 列）。
- **守卫**：RIR 非数字 → warning 逐行提示；全部相无可匹配峰 → information；
  `rir_quantify` ValueError → warning。
- **测试**：新 `tests/ui/test_quant_dialog.py` 8 用例（correlations 强度取 max /
  RIR 2:1 强度 → 各 50.00 / 无效 RIR 警告 / 全零强度提示 / apply 写回
  `weight_fraction` / 主窗口「无已确认物相」守卫 / 模块动作打开对话框 /
  不再占位播报）。
- **验证状态**：`test_quant_dialog.py` 8/8 通过；ruff / mypy(99) 全绿。
  提交时（`3bb5d8f`）因外部重任务并发，tests/ui 全套与全量回归未跑；
  **已于 2026-11-08 补跑全量回归判绿**（1736 用例 = 1731 passed / 4 skip /
  1 xfail / 0 F / 0 E），并借批次 5 修掉了 `test_module_wiring.py` 里
  仍把 `quant_analysis` 当占位的陈旧断言。

## GUI 批次 5：微结构分析对话框（2026-11-07）✅ 已完成

`microstructure` 模块动作从占位接成真实对话框
`xinmatch/ui/microstructure_dialog.py`。**计算全委托 `core.micro`，不重写算法。**

- **输入**：当前谱图（提供 λ 默认值，可改）+ 峰列表的 FWHM。FWHM 只能来自
  Profile Fitting 精修（峰检测本身不给宽度），无 FWHM 的峰逐条跳过。
- **参数**：波长 λ（Å，默认取 `pattern.wavelength`）、Scherrer 常数 K
  （默认 0.9）。两页共用同一组参数。
- **Scherrer 页**：`scherrer_from_peaks` 逐峰给 D = Kλ/(βcosθ)（2θ / FWHM /
  D 三列）+ 算术平均（标注「单峰值随 hkl 各向异性会分散」）。
- **Williamson-Hall 页**：`williamson_hall_from_peaks` 对
  βcosθ/λ = K/D + ε·4sinθ/λ 做最小二乘，报 D、ε、R²、参与峰数；回归用的
  (2θ, x, y) 逐峰列出便于复核。截距非正时 D 显示「—（截距非正）」。
- **不互相阻断**：一页数据条件不足（如 W-H 需 ≥2 峰）只把该页提示写回，
  另一页照常出结果；两页都不弹模态框。
- **仪器宽化**：本版**不做** β_sample² = β_obs² − β_inst²（需 LaB₆ / Si 标样
  表，后续版本），对话框内常显提示「算出的 D 会偏小」，避免误读。
- **不回写**：结果是报告性数值，不写峰列表（与参考软件一致）。
- **测试**：新 `tests/ui/test_microstructure_dialog.py` 13 用例（构造默认 /
  Scherrer 手算对齐 / 跳过无 FWHM 峰 / 算术平均 / 纯尺寸合成峰复原 D=50 nm /
  纯应变合成峰复原 ε=2e-3 / 回归表与峰序对齐 / 单峰时 W-H 提示但 Scherrer
  照常 / 全无 FWHM 提示 / 两个主窗口守卫 / 模块动作打开且不再占位）。
- **连带修正**：`tests/ui/test_module_wiring.py` 的「仍占位模块」清单把
  `quant_analysis`（批次 4 已接）与 `microstructure` 移出——批次 4 因外部
  重任务并发未跑 tests/ui 全套，这条陈旧断言当时没被发现。
- **验证**：受影响 UI 子集 93 用例全绿；**全量回归判绿**（1736 用例 =
  1731 passed / 4 skip / 1 xfail / 0 F / 0 E，19m55s，同时补上批次 4 的
  回归缺口）；ruff / mypy(99) 全绿。
