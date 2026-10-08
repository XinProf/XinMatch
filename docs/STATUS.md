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
| T6.9 | L3 acceptance (Top-10 vs match4 baseline) | ✅ |
| T6.10 | Weight tuning (grid/Bayesian) | ✅ |

## Phase 7 — Restraints application (`core/search/`)

| ID | Task | Status |
|----|------|--------|
| T7 | Apply restraints to DB search + candidate pruning + scoring | ✅ |

## Phase 8 — Quantitative analysis (`core/quant/`)

| ID | Task | Status |
|----|------|--------|
| T8.1 | RIR quantitative (adiabatic + reference-ratio) | ✅ |

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

## Phase 12 — Report & export (`core/report/`)

| ID | Task | Status |
|----|------|--------|
| T12.1 | Report data model (SampleInfo / CandidateEntry / Report) | ✅ |
| T12.2 | Renderers: HTML / text / markdown / PDF (weasyprint lazy) | ✅ |
| T12.3 | Figure export: PNG / SVG (matplotlib Agg) | ✅ |

## Phase 10 — Refinement (`core/refine/`)

| ID | Task | Status |
|----|------|--------|
| T10.1 | Peak model (pseudo-Voigt + asymmetry + Caglioti U/V/W) | ✅ |
| T10.2 | Structure factor (scattering factors, DW, LP, multiplicity) | ✅ |
| T10.3 | Le Bail decomposition | ✅ |
| T10.4 | Rietveld refinement (scale + cell + peak_width + zero) | ✅ |
| T10.5 | Residuals | ✅ |
| T10.6 | FullProf / GSAS-II adapter | ✅ |
| T10.7 | Strategy turn-on | ✅ |

## Phase 14 — CLI & scripting (`cli/`)

| ID | Task | Status |
|----|------|--------|
| T14.1 | CLI pipeline (import → process → search → quantify → report) | ✅ |
| T14.2 | Python API (`xinmatch/__init__.py`) | ✅ |
| T14.3 | Batch scripting (JSON/YAML config) | ⬜ |
| T14.4 | Serial instrument control | ⬜ |

## Phases 13, 15–16

See [ROADMAP_v3.md](../ROADMAP_v3.md). Remaining: T13 GUI (PySide6),
T15 packaging, T16 3D structure viz.
