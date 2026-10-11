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

