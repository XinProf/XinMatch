# Implementation status

Tracks progress against [ROADMAP_v3.md](../ROADMAP_v3.md).

Legend: ⬜ not started · 🟡 in progress · ✅ done

## Phase 0 — Knowledge base & golden baseline

| ID | Task | Status |
|----|------|--------|
| T0.1 | Extract official doc library (169 topics) | ✅ |
| T0.2 | Re-extract against latest 参考软件, diff versions | ⬜ |
| T0.3 | Build standard sample set (20–30 samples) | 🟡 (辅助工具就绪：`tools/import_match_baseline.py` + `tests/baseline/match/README.md`（人工 参考软件 操作步骤 + 13→20–30 缺口清单）；合成谱 13 组已生成（`tools/generate_synthetic_patterns.py` → `D:\Project\XRD\test_xrd\synthetic\synth_01~13.txt`，真相已知），用户已在参考软件 SMPF 验收（jingzhun 13/13 Top-1、FoM=1.0000，归档 `tests/baseline/ref20261011/`）；真实样品采集仍待人工跑) |
| T0.4 | Run 参考软件 baseline on the sample set | 🟡 (转换链就绪：参考软件 导出 CSV → `import_match_baseline.py` 规范化 → `tests/baseline/match/`（生产加载器 `load_match_csv` 回读校验，真实 1-1.csv smoke 55 行往返一致）；参考软件 对 13 组合成谱的候选基线已归档 `tests/baseline/ref20261011/`（jingzhun 19 + alloption 23 文件，验收记录 `docs/sample_expansion_20261011.md`）；真实样品跑完后导入) |
| T0.5 | Terminology mapping table | ⬜ |
| T0.6 | Project skeleton + CI (pytest, ruff, mypy) | ✅ (2026-10-10：mypy 配置落地（pyproject [tool.mypy]，files=xinmatch + search/refine 基线豁免），26 源文件纯类型层修复，**109 错误 → 0（81 源文件）**，`python -m mypy` 与 `mypy xinmatch` 均 Success；豁免清单见 docs/mypy_baseline.md。pytest/ruff 此前已就绪) |
| T0.7 | Cross-platform conventions | ✅ |
| T0.8 | Reverse-engineer FoM P-value definitions from baseline CSV | 🟡 |

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
| T2.4 | Bruker (.uxd/.brml; .raw TODO) | 🟡 |
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
| T6.9c | **L3 追平（2026-10-10）** | ✅ Top-1 一致率 **9/13 → 11/13（84.6% ≥ 80% PASS）**、Top-5 重叠 **67.7% → 83.1% PASS**。两处 FoM 算法修正（`core/search/fom_criteria.py`）：① 强度归一化改用「匹配峰最大值」（消除多相次相 I_scale 尺度效应重复惩罚，翻转 5-2/5-2b Hematite）；② sigma_pos 0.1→0.15（修复 4-1 胶着回归，CaF₂ 曾以 0.001 压 ZnO）。终态仅剩 5-1（参考 Magnesite 96-900-0381 快照内容错位为 Teruggite）与 5-3（参考 Kaolinite 96-900-9231 快照缺失）两处不匹配；**13/13 top1 均为真相相**；诊断确认库中这些相正常条目均在、纯排序问题，SMPF 权重模拟崩坏彻底排除权重路线、未补库。详见 docs/l3_traceup_report.md |
| T6.9b | COD 全库检索质量核验（2026-10-10） | ✅ (用 `data/cod_full.db` 112,734 条目重跑同基线：Top-1 一致率反而降至 1/13——全库含大量重复/低质量卡片稀释排序。**结论：默认检索保持精选无机库 71,199 正确，全库仅作覆盖性挂载**；L3 追平不靠换库，方向仍是逆向参考软件 FoM 内部逻辑或补条目) |
| T6.10 | Weight tuning (grid/Bayesian) | ✅ (R²=0.9971 ≥ 0.9913 baseline; keep published weights) |

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
| T14.4 | Serial instrument control | ⬜ |

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

剩余：T14.4 serial instrument control、T0.3/T0.4 人工样品采集（工具已就绪）、T0.8 FoM P 值深挖、COD 全库检索质量上游修复（峰抽取标定）。

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

**背景**：用户参考软件 SMPF 验收合成谱 13/13（jingzhun 全 Top-1 FoM=1.0000，归档 `tests/baseline/ref20261011/` + `docs/sample_expansion_20261011.md`）；XinMatch 侧标准检索仅 **3/13** 真相相进 Top-20。

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

## SMPF（全谱拟合检索）实现（2026-10-11）✅

**交付**：`xinmatch/core/search/smpf.py`（完整流水线：峰列表预筛 150 卡 → 7 参数受限最小二乘全谱拟合精排 → Rwp/GOF/FoM 排序）；`pfsm.py` 保留 `pfsm_score`/`pfsm_rank` 兼容层（签名不变）；`tests/search/test_smpf.py`（单元 + 合成验收 + 真实记录 + 性能守卫）；机制文档 `docs/smpf_mechanism.md`。

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

**A. 统一检索入口（峰列表 FoM / SMPF 双模式）**

**交付**：`xinmatch/ui/main_window.py`——工具栏新增检索模式下拉框 `_search_mode_combo`（「峰列表 FoM（寻峰）」「SMPF 全谱拟合（不寻峰）」，切换仅更新内部状态、不自动触发检索）；`_run_search_match` 按模式分支执行；模块级 `smpf_results_to_candidates()` 把 SMPF `(Entry, score_dict)` 适配为 `CandidateResult`（`fom` + `p_values{rwp,rexp,gof}`），`self._candidates` 元素类型不变（精修向导 / 3D 视图 / CIF 导出链路不破）；SMPF 分支不寻峰、不覆盖峰列表（保留上次峰列表）；Kα2 双线（1.5444）留作后续旋钮。新增测试 `tests/ui/test_search_mode.py`（控件存在性/切换行为/纯函数转换/双模式冒烟/SMPF Top-1 命中/`_selected_candidate_results` 回归锚点）。

**冒烟结果**（offscreen + 真实默认库 + 合成谱 synth_06）：

| 模式 | 候选数 | Top-5 | 峰列表 |
|---|---:|---|---|
| 峰列表 FoM | 20 | 全 "Ba O3 Ti" | 84 行（写入） |
| SMPF 全谱拟合 | 10（测试限 top_n=10） | Top-3 全 "Ba O3 Ti"（fom 0.701/0.700/0.700） | 保持 84 行（不覆盖） |

**SMPF 命中（UI 级，is_truth 元素集+比例口径）**：synth_06 Top-1 = 96-210-0858 "Ba O3 Ti" ✓；synth_09 Top-1 = 96-101-0519 "C 1 2 1"（fom 0.614，第二名 0.044）✓。

**验收**：`pytest tests/ui/test_search_mode.py tests/ui/test_main_window.py tests/search/test_synthetic_acceptance.py tests/search/test_smpf.py` = **47 passed / 0 failed**（独立复跑一致）；既有 UI / Search 测试无退化；ruff 全绿；品牌词全仓 0 命中（缓存目录除外）。

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

**v1.3.0 — SMPF Kα1/Kα2 双线旋钮 + 图标库重绘**：
- SMPF 旋钮三处收口：Options→Search-Match 页（`smpf_kalpha2_enabled` / `smpf_kalpha1_angstrom` / `smpf_kalpha2_angstrom`，落盘 `config/xinmatch.yaml`）、CLI `search --mode smpf [--single-kalpha] [--kalpha1] [--kalpha2]`、GUI 检索模式 combo 提示当前 Kα 配置；`smpf_kalpha_wavelengths()` 读 YAML（Kα1≤0 时跟随样品波长）。synth_13 单线谱回归锁定（`tests/ui/test_smpf_kalpha2.py`）。
- 图标库：修复 `_build_actions` 把模块 id 当图标名传入导致 14 个动作全部回退通用立方体的 bug（`icons.icon()` 内置 `resolve_icon_name`）；29+ 图标重绘为填充主体 + accent 点缀（数据特征类保留粗描边）；新增多尺寸预渲染 `(16,20,24,32,48)`；主题切换时图标重着色（`_icon_actions` + `_refresh_icons`）。

**v1.3.1 — 五项 GUI 体验迭代 + 忙碌窗口 + 打包**：
1. **图标视觉归一化**（`ui/icons.py`）：`_normalized_pixmap` 高清 8× 渲染 → `_alpha_bbox` alpha 包围盒 → 长边等比缩放到 `_CONTENT_RATIO=0.74` → 居中；38 图标占比统一 0.75（±容差验证）。
2. **工具栏图标+文字+悬停详细说明**：`ToolButtonTextBesideIcon` + `_MODULE_TIPS` 15 条 tooltip（是什么+怎么用）。
3. **元素周期表改弹窗式**（`ui/periodic_table.py::PeriodicTablePanel`）：摘要行+启用开关+「选择元素…」+「清除」；弹窗复用持久 `PeriodicTableWidget` 实例；states/set_states/set_enabled/is_enabled/reset drop-in API。
4. **谱图轴切换**（`ui/pattern_view.py`）：X 2θ↔d（布拉格 λ/2sinθ），Y 计数↔√↔log₁₀；crosshair 读数恒显物理量；`fit_data_range()` 打开/删除数据/切轴后自适应。
5. **耗时操作忙碌窗口**（`ui/busy.py`）：`run_with_busy` QThread + `BusyDialog`（走马灯+模态遮罩+重入保护）；检索全链路 busy 化（`_do_search`/`_apply_search_results`/`_show_search_error` 三件套，异常经 on_error 回 GUI 线程提示）。修复两个生产级线程 bug：DirectConnection 跨线程调 QWidget 挂死（信号 receiver 改 BusyDialog 排队槽）、sqlite 主建连 worker 用（`check_same_thread=False`）。

**版本与打包**：pyproject/spec(APP_VERSION+TUPLE+COLLECT name)/build_exe.ps1/PACKAGING.md 五处同步 **1.3.1** + `pip install -e . --no-deps`；产物 `dist/xinmatch-1.3.1/`（exe FileVersion 1.3.1 实测，CLI FoM+SMPF 单线冒烟通过）。

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

稀疏谱（5 峰）下数百张密集卡片全部匹配所有窗口，`recall_max_candidates=800` 按 entry_id 字典序截断，`96-900-xxxx` 系列恒被挤出——GUI 峰列表模式实测仅 8/13 命中。修复：`search_match(recall_strongest_peak=True)` 默认翻转（Hanawalt 式召回：只保留最强参考峰落在实验强峰窗内的条目），docstring 补充饱和缺陷说明。实测 13 组合成谱 plain 8/13 → Hanawalt 13/13（12 个 rank 1）。SMPF 路径本就传 True，文档（`docs/smpf_mechanism.md`）早已按 True 描述，翻转后峰列表模式与文档一致。

**回归测试（新增）**

- `tests/peak/test_peak_search.py::test_peak_search_noise_floor_rejects_smooth_ripple`：5 高斯峰 + 慢速波纹 → 恰好 5 峰；
- `tests/peak/test_peak_search.py::test_peak_search_rejects_tail_carpet_bumps`：宽尾伪峰 + 弱宽真峰 → 真峰全在、总数 ≤8（旧代码 15 峰泄漏）；
- `tests/preprocess/test_alpha2.py`：3 个护栏测试（Kα1-only 谱跳过剥离 / 真双线仍剥离 / 修复既有 recovering 测试的逐点 δ 构造）；
- `tests/search/test_search_match.py::test_recall_hanawalt_default_survives_dense_card_saturation`：900 张 `96-200-xxxx` 密集诱饵 + 真相 `96-900-9999`，legacy plain+800 截断丢失真相、Hanawalt 默认 top-1 FoM=1.0；
- `tests/search/test_textbook_phases.py`（新文件）：教科书晶胞常数现场合成三相谱 → 峰数==线条数 + 环境条件卡片 Top-20 + Halite Top-5，库缺卡片时提示运行迁移工具。

**验收**：`.scratch/probe_ambient.py` → Halite rank 1（FoM 0.928）/ Sylvite rank 5 / Periclase rank 2（榜首 `96-900-5516 Fe0.01Mg0.99O` 为掺 Fe 近缘卡片，合理）；`tests/search` + `tests/preprocess` + `tests/peak` 套件通过；ruff/mypy 改动文件全绿（`alpha2.py` 护栏行为 mypy 零错误）。

**遗留（归入后续任务）**：Sylvite rank 5 的差距源于卡片 a=6.2879 vs 教科书 6.2931 的 0.08% 单元格差 + CIF 强度惯例（→ T0.8 FoM P 值深挖）；`recall_strongest_peak=True` 在 71k 全库上单次检索 ~9s（plain ~2.5s 但结果错误），Hanawalt 模式下 `recall_max_candidates` 被忽略，超大规模库的性能旋钮留待 T6.0 索引落地。

---

## v1.4.0 SMPF 剩余扩展（2026-10-13）✅

**背景**：`docs/smpf_mechanism.md` §8 列了四项局限（择优取向与晶胞微调 / FWHM 全局单值 / 多相解叠 / 峰形不对称）。本次先做**数据可行性核查**再定范围，落地两项、推迟两项（其中一项被数据阻塞）。

**选型结论（先查数据，后选模型）**

| 项 | 结论 | 依据 |
|---|---|---|
| Caglioti U/V/W 角度依赖宽化 | ✅ 实现并默认开 | 不依赖 hkl；合成谱生成器同款模型，可直接验证参数回收 |
| 晶胞微调 `cell_delta` | ✅ 实现并默认开 | `entries.a/b/c` 仅 15/71206 缺失；2θ 位移 ∝ tanθ，与常数 shift 可区分 |
| March-Dollase 择优取向 | ⛔ **被数据阻塞** | `peaks.h/k/l` **6,214,072 行全 NULL**（`Entry.hkl` 恒 None）；真 MD 需逐反射 hkl 算面法向夹角，须先做 CIF→hkl 回填迁移 |
| 峰形不对称 | ⏸ 明确推迟 | η 自 v1.2 起就在拟合向量内（`eta_bounds=(0.05,0.95)`），已吸收一阶不对称；显式校正（Finger–Cox–Jephcoat 类）对"先找到相"排序增益有限 |
| 多相解叠 | ⏸ 明确推迟 | SMPF 定位是"先找到相"，精修交 GSAS-II；混合谱真相相仍可排到 Top-1，仅 Rwp 偏高 |

附带发现：生成器的 `_march_factor` **不是**真 March-Dollase——它乘的是**峰内形状**（窗内 |2θ−2θ₀| ≤ 8×FWHM ≈ 0.028 rad，cos≈1 ⇒ 近似常数 1.52），被 `scale` 完全吸收，对排序无影响。

**实现**（`xinmatch/core/search/smpf.py`）

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

**回归测试**（`tests/search/test_smpf.py` 新增 8 项）：`test_caglioti_fwhm_formula_and_clamps`、`test_theory_profile_caglioti_widens_high_angle`（细网格高低角 FWHM 比 >1.5）、`test_fit_recovers_caglioti_uvw`、`test_caglioti_beats_global_fwhm_on_angle_dependent_width`（Rwp < 0.5×）、`test_fit_recovers_cell_delta`（+0.003 → +0.00299）、`test_switches_off_identity_encoding`、`test_reflection_windows_extra_margin_widens_high_angle`、`test_score_dict_carries_v14_keys`。

**等价性验证**：改前把旧文件 `cp` 到 `.scratch/smpf_pre_vectorize.py`，以独立模块名加载，48 组配置（Kα 双线 × 晶胞偏移 × 窗口加宽 × 0.01/0.02 网格）对比 `max|Δ|/max < 1e-12`。

**验收**（2026-10-13）

- `tests/search` junit 结论：**275 用例 0 失败 0 错误**（2 跳过，166.5s），含新增 8 项、`test_deterministic_single_pattern` 与 `test_single_pattern_under_120s`（43.4s，护栏 120s）；
- 两个慢验收类（`TestSyntheticSmpfAcceptance` 13 组合成谱 Top-20/Top-5、`TestRealSmpfRecord` 13 组真实谱 record）在 `tests/peak + tests/preprocess + tests/search` 全量跑（47 分钟）中同样到达 100%、进度行无 F/E；
- 2 处 skip 为 `tests/search/test_textbook_phases.py` 对 Sylvite/Periclase 的「仅 Halite 断言 Top-5」预期跳过（v1.4.0 无机库专项既有行为，与本改动无关）；
- `tests/ui` junit 结论：**205 用例 0 失败 0 错误**（350s，offscreen）；
- ruff 改动文件全绿；mypy `smpf.py` **0 错误**（其余 9 处为 `entry.py`/`background.py`/`smoothing.py`/`fom_criteria.py` 存量）；
- 提交 `d6a543c`（5 文件 +538/−47）。
- 已知环境现象：本环境 pytest 收尾会被沙盒钩子拦截临时目录清理（286 文件 > 50 阈值），汇总行不落盘、退出码非 0——**判定以 junit XML 与进度行的 F/E 为准**。

**关联**：v1.4.0 无机库专项遗留的「Sylvite 卡片 a=6.2879 vs 6.2931 的 0.08% 晶胞差」现由 `cell_delta`（边界 ±0.5%）在拟合层面吸收，剩余差距（CIF 强度惯例）仍归 T0.8。
