# Implementation status

Tracks progress against [ROADMAP_v3.md](../ROADMAP_v3.md).

Legend: ⬜ not started · 🟡 in progress · ✅ done

## Phase 0 — Knowledge base & golden baseline

| ID | Task | Status |
|----|------|--------|
| T0.1 | Extract official doc library (169 topics) | ✅ |
| T0.2 | Re-extract against latest Match!, diff versions | ⬜ |
| T0.3 | Build standard sample set (20–30 samples) | ⬜ |
| T0.4 | Run Match! baseline on the sample set | ⬜ |
| T0.5 | Terminology mapping table | ⬜ |
| T0.6 | Project skeleton + CI (pytest, ruff, mypy) | 🟡 |
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
| T6.9 | L3 acceptance (Top-10 vs match4 baseline) | ✅ (real COD db 71,199 entries: **13/13 samples top1 = ground-truth phase**; vs Match! CSV: Top-5 overlap 67.7% ≥ 60% PASS, Top-1 agreement 69.2% (9/13) < 80% FAIL — 4 mismatches are multi-phase 5-x samples where both sides pick a true phase; FoM weight sweep (4 combos) all stop at 9/13, not reproducible by linear weights; see docs/l3_golden_acceptance_cod.html) |
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
| T8.3 | Rietveld quantitative (depends on Phase 10) | ✅ (`core/quant/rietveld_quant.py` 委托 GSAS-II 闭环：build→run→parse→wt%，误差表见模块 docstring。CPD-1c 与 test_xrd 3-1 端到端 Rwp≈14–15%、GoF≈2.3；微量相 CaF₂ 误差 +2.3 wt%（<3 wt% 达标）；主相 ZnO/Al₂O₃ 误差 ~9–12 wt% 未达 Phase 8 <3 wt%——归因：ZnO 择优取向未有效建模（CPD 轮测文献已知难点，T8.2 内标法同标 xfail）+ 手写 CIF 原子坐标 + 通用仪器参数文件与实际衍射仪不匹配；降至 <3 wt% 需 COD 标准 CIF + 实测仪器参数文件) |
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
> （Match! 集成 FullProf，XinMatch 选择 GSAS-II，因为它是 Python 编写可嵌入式集成。）

| ID | Task | Status | 说明 |
|----|------|--------|------|
| T10.1 | Peak model (pseudo-Voigt + asymmetry + Caglioti U/V/W) | ✅ (reference only) | 自研，仅用于交叉验证，**非生产路径** |
| T10.2 | Structure factor (scattering factors, DW, LP, multiplicity) | ✅ (reference only) | 同上 |
| T10.3 | Le Bail decomposition | ✅ (reference only) | 同上 |
| T10.4 | Rietveld refinement (scale + cell + peak_width + zero) | ✅ (reference only) | 同上 |
| T10.5 | Residuals (Rp/Rwp/R_exp/χ²/GoF) | ✅ (reference only) | 同上；生产上由 GSAS-II 输出 |
| T10.6 | FullProf adapter | ❌ not doing | Match! 用 FullProf，XinMatch 选 GSAS-II |
| T10.6b | **GSAS-II adapter (production path)** | ✅ | `gsas2_adapter.py`：Protocol + Local fallback + `.gss` 解析 + lazy import |
| T10.7 | Strategy turn-on (Parameter Turn-On) | ✅ (reference only) | 自研策略化；生产上由 GSAS-II 的 refine controls 承担 |
| T10.8 | GSAS-II 项目构造器（CIF + Pattern → GSAS-II .gpx 项目） | ✅ | `gsas2_project.py`：driver+清单自包含，Gsas2NotAvailableError 优雅降级；cpd-1c 三相机实测 Rwp≈59% |
| T10.9 | GSAS-II 结果解析（Rwp / 精修后 CIF / prf 残差谱） | ✅ | `gsas2_parse.py`：.lst/.prf/精修CIF/.gpx 解析回填 Phase/Pattern/RFactorSection；真实 fixture 验证 |

## Phase 14 — CLI & scripting (`cli/`)

| ID | Task | Status |
|----|------|--------|
| T14.1 | CLI pipeline (import → process → search → quantify → report) | ✅ |
| T14.2 | Python API (`xinmatch/__init__.py`) | ✅ |
| T14.3 | Batch scripting (JSON/YAML config) | ⬜ |
| T14.4 | Serial instrument control | ⬜ |

## Phase 13 — GUI (`ui/` · PySide6)

> **精修 GUI 特别说明**：精修面板采用 **MAUD 风格向导式交互**（分步引导：选相 → 选背景 → 选精修参数组 → 运行 → 查看 R 因子与残差），
> 但所有实际计算委托给 GSAS-II（T10.6b）。XinMatch 不重写精修算法，只重写交互体验。
> 参考软件：`C:\MAUD3`（MAUD 界面）、`C:\Program Files\Match4`（Match! 工作流）。

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
| **T13.8** | **Refinement wizard GUI (MAUD-style, delegates to GSAS-II)** | ✅ (`ui/refinement_wizard.py`：四步向导——选已鉴定相→背景处理→勾选 Scale/Cell/Profile/Atoms→运行→R 因子+残差谱+精修后晶胞；无 GSAS-II 时友好降级提示；计算全委托 T10.6b/T10.8/T10.9 不重写算法；结果信号 refinement_finished) |

## Phases 14–16

See [ROADMAP_v3.md](../ROADMAP_v3.md). Remaining: T14 CLI batch/serial,
T15 packaging, T16 3D structure viz.
