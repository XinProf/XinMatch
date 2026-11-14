# Changelog

What changed in each released version of XinMatch. Only **user-visible** changes are listed
here; implementation detail, verification data and the traps hit along the way live in
`docs/RELEASE-NOTES-<version>.md` and in the index at the end of this file.

## Maintenance rules (applied on every release)

1. Accumulate work under `## [Unreleased]` while developing, and rename it to
   `## [x.y.z] — YYYY-MM-DD` when tagging.
2. **A release updates three places together**: this file, the version line and download link in
   `README.md` + `README-CN.md`, and `docs/RELEASE-NOTES-<version>.md`. All three version numbers
   must match the tag verbatim.
3. The version still has a single source of truth, `pyproject.toml` (`xinmatch.spec` derives from
   it; the iss default is overridden by the build script). The version in this file's headings
   must never run ahead of it.
4. Categories: Added / Changed / Fixed / Data / Release. Do not repeat explanations across
   versions — point back to the release that introduced them.

## [Unreleased]

(Nothing yet.)

## [3.8.0] — 2026-11-14

**Added**
- **Fourth benchmark ruler** `tools/bench_shijk.py`: seven measured MAUD refinement patterns,
  33 crystalline phases, 13 metrics covering entry-level / phase-level Top-K, six-round
  sequential identification and sample-level Top-1. Ground-truth entry IDs are derived from
  the exported CIF numbering (seven digits minus one) and verified 33/33 with
  `--verify-truth`. Amorphous phases in four samples are excluded from the denominator.
  Baselines: `docs/bench/shijk-20261113.json` and `shijk-20261113-pool20000.json`.
- **Configurable v3 prescreen pool cap**: `search_match(..., candidate_limit=...)`. `None`
  keeps the built-in 1000 and is bit-identical to previous releases. An explicit 20000 pool
  lifts ShiJK phase-level Top-20 from 9/33 to 15/33 at roughly 10x per-search latency; the
  GUI does not expose the knob.
- **Default-off adaptive pool switch** `adaptive_pool`: re-runs with a wider pool only when the
  FoM head is flat. A/B ruled it out as a default (7 up / 2 down / 18 flat on the three
  rulers; ShiJK sequential 16/33 → 14/33; 5–10x latency), so it stays an opt-in switch.
- **`--oracle-elements` upper bound**: complement element restraints built from ground-truth
  CIF element sets. This is the first one-directional gain across all four rulers —
  10 up / 0 down / 3 flat, phase-level Top-20 9 → 15, sequential 16 → 25, sample Top-1
  6/7 → 7/7, with no extra runtime. It is an upper bound, not a shipped metric: input
  sensitivity probes show that under-reporting light elements is worse than applying no
  restraints at all.
- Independent `--seq-candidate-limit` knob keeps the historical benchmark baselines
  reproducible, and `_compare()` now reports all 13 metrics with up / down / flat totals.

**Changed**
- All four rulers accept `--adaptive-pool`; `tools/bench_three_rulers.py` forwards it and
  records it in the summary config.
- External documentation is now English by default: README, README-CN, this changelog and
  all `docs/RELEASE-NOTES-*.md` files. Internal notes (`docs/STATUS.md`, the benchmark
  report, work logs) stay in Chinese.

**Fixed**
- `userdb` was missing from the frozen CLI fallback dispatcher (`tools/pyi_entry.py`), so a
  frozen build could route `XinMatch.exe userdb ...` to the GUI when parser import failed.
  A dedicated regression test now pins the subcommand list.

**Data**
- Diagnostics documented and ruled out without production changes: prescreen `hits`
  ordering (§42), adaptive pool (§43), four alternative `p_npeaks` estimators (§44),
  wide pool in sequential search (§45). The element upper bound is §46.

**Release**
- Default search behaviour is unchanged: the default ruler run is 13/13 flat against the
  historical baseline. `.xinDB`, `.xinm` and `config.yaml` formats are unchanged.
- `XinMatch-Setup-3.8.0.exe`; the portable zip is built for acceptance but not published.

## [3.7.0] — 2026-11-12

**Added**
- `tools/bench_three_rulers.py`: runs all three benchmark rulers (synthetic / real-sample / IUCr)
  in one command and reports 26 unified metrics; `--baseline` gives per-metric deltas split into
  up / down / flat, and `--fail-on-down` turns a regression into a release gate.
- CLI `xinmatch userdb list / add / remove / rebuild`, sharing the same `core/db/user_db`
  implementation as the GUI.

**Changed**
- Synthetic ruler rebuilt: 13 groups / 24 phases, regenerated with `--peak-source v3` so the
  intensities come from the same library the search uses.

**Fixed**
- The synthetic generator's `CARD_DB` was hard-coded to a pre-migration absolute path that no
  longer existed; it now resolves relative to the repository, and the three card-lookup helpers
  return early when the library is missing instead of aborting generation.
- `core/refine/cif_store` never descended into the `cif/` subdirectory when probing the COD root,
  so card-source generation crashed on `900-` series entries (only 4 of 13 groups produced); both
  layouts now resolve.
- `compute_rwp` in FPFM / PFSM gains a `RWP_MIN_REL_INTENSITY = 1e-9` floor: subnormal intensity
  points overflowed `w = 1/ym`. Arithmetic is unchanged and 237/237 normal patterns stay
  bit-identical.
- `tools/verify_binary.py` unpacks the portable archive with the standard-library `zipfile`
  instead of hard-depending on a local 7-Zip.

**Data**
- Restored the real-pattern ruler (13 groups, `docs/bench/real-20261112.json`) and a unified
  baseline (`docs/bench/all-20261112.json`); PDF-2 (163,834 phases) is mounted in the local
  registry only and never enters the repository.

**Release**
- `XinMatch-Setup-3.7.0.exe` 243.4 MiB, SHA-256 `ea3b9225…a6565`; the portable zip is built but
  not published.
- All 5 rounds of binary robustness acceptance passed (hash read-back / portable extract / frozen
  GUI three hooks / silent install / post-install search).

## [3.6.4] — 2026-11-11

**Added**
- `user_db` wired into the v3 search chain; restoring the `[report]` extra brought back 42 tests
  that had been parked.

**Changed**
- Startup to main window **1.81 s → 0.82 s** (lazy scipy / QtWebEngine loading plus C-level icon
  scanning).
- Splash screen changed to 800×600 without a version number; iss / `verify_binary` synchronized on
  release-variant detection.

**Fixed**
- Crash on empty cells in the RIR quantification dialog; missing type annotations on the pattern
  reference-line row list.

## [3.6.3] — 2026-11-09

**Added**
- Element constraints in four states (must-have P / contains H / possible M / absent E) plus a
  **closed-loop switch** "restrict to the selected elements", semantics aligned clause by clause
  with the sister project PolyXRD; the pre-filter gains an `elements_any` channel.
- A "fill light elements" button that marks O/C/H/N/S as "contains" in one click.

**Changed**
- Phase identification now defaults to FPFM full-profile fitting (no peak search); the dropdown
  switches back to peak-list FoM in one click. The FPFM chain does not accept element
  constraints, and under that combination the toolbar permanently shows "not effective under
  FPFM".
- Old archives and old workflows behave bit-for-bit as before (closed loop off by default);
  benchmark numbers do not move.

## [3.6.2] — 2026-11-09

**Added**
- A **reference-line lane** below the pattern: one row per phase, formula on the left, x-axis
  aligned with the main plot; a checkbox toggles "angular positions only / with intensities".
- A row of **quick icons** above the pattern (reset / horizontal box select / vertical box select
  / region zoom / pan / step zoom / crosshair).

**Changed**
- The top "X axis / Y axis / fit to data" bar is hidden but keeps its functions, which move to
  **clicking the axis** (left-click cycles, right-click menu).

## [3.6.1] — 2026-11-08

**Fixed** (pure defect-fix release, no interface or data-format change)
- Duplicate legend: pyqtgraph's `PlotItem.addItem()` already adds a legend entry and the code
  added another one; there was always only 1 curve and the extra row was the legend. Also fixed
  "remove legend rows by name" deleting a same-named sibling curve.
- Refinement wizard froze and went white: the GSAS-II subprocess ran synchronously on the GUI
  thread; it now goes through `run_with_busy()` on a background thread, and "Start refinement"
  moved inside page 4 to eliminate misfires from the button sliding into place.
- The list's "crystal system" labelled hexagonal phases as monoclinic: the criterion only counted
  non-90° angles; `H` / `R` criteria added.

## [3.6.0] — 2026-11-08

**Added**
- Profile Fitting dialog (F5): four profile shapes + Rwp + fitted-curve overlay + write-back to
  the peak list.
- RIR quantitative analysis dialog: Hill–Howard adiabatic method, wt% written back to the match
  list.
- Microstructure analysis: Scherrer and Williamson-Hall pages (no instrumental broadening
  correction in this release).
- Indexing wizard (Treor90 / DicVol06): 7 crystal systems selectable, result table with
  `deduplicate` + ranking.
- Aggregated data-export menu: pattern ASCII / peak-list CSV / candidate-list CSV / match-list
  CSV / `.xinm` / CIF.

**Changed**
- Every menu action is now wired — 11 of 15 modules previously only posted a status-bar
  placeholder; only `user_db` remains a placeholder.
- Candidate-list row cap `candidate_list.max_display_rows` (default 50, counted per family):
  family coverage 81/98 → **89/98** at zero compute cost; reports and the table share one source.
- Peak-position refinement switched to LM: preprocessing **35.2 s → 0.35 s**, 207-peak CLI
  end-to-end **36 s → 2.3 s**.
- Periodic table redesigned (sizing driven by font metrics; three states encoded by colour + line
  style + font weight, red-green colour-blind friendly).
- One-line sample-element entry: real-pattern phase recall **20/43 → 30/43**.

## [3.5.0] — 2026-11-06

**Added**
- The element "must not contain" constraint really participates in search (the pre-filter removes
  such phases via the `element_inv` inverted index); GUI / `search_match(restraints=…)` /
  `search_match_v3(elements_excluded=…)` all take the same path.
- Five version-consistency tests; the build script self-checks the exe's `FileVersion` after
  building.

**Changed**
- The version number collapsed into a single source of truth: `pyproject.toml` only, the spec
  derives from it, and iss keeps just a default overridden by `ISCC /DAppVersion=`.
- A misspelled element symbol empties the result in the "must contain" direction and excludes
  nothing in the "must not contain" direction.

## [3.4.0] — 2026-11-05

**Added**
- **Export phase analysis (.xinm)**: the anchor pattern + selected phases' CIFs + peak table +
  metadata packed into a zip that XinRefinement loads in one click via "Import XinMatch phase
  analysis".
- A CIF retrieval bridge probing roots in the order "environment variable → current archive root
  → legacy root".

**Changed**
- When a phase's CIF cannot be retrieved it degrades to "reference only" and does not block the
  export.
- Copyright boundary: no ICDD/PDF-2 derived data file is packed; `source="pdf2"` writes only the
  id and peak-table metadata.

## [3.3.0] — 2026-11-04

**Added**
- Sparse-phase **strong-line anchoring** mark `AnchorPolicy`: strongest reference line hits
  ≥0.30× the strongest residual peak, `P(2θ)`≥0.98, matched pairs ≥2, `P(ncorr)`≥0.50, reference
  reflections ≤20 → the candidate table marks it `★`.
- Optional re-ranking `search_residual(..., promote_anchored=True)` (off by default).

**Changed**
- The mark is informational and does not change ranking: the same rule also mislabels a wrong
  phase on real patterns (benchmark report §11.5).
- Line-count guard: candidates with more than 20 reference reflections are never marked — they
  are the dominating mechanism itself.

## [3.2.0] — 2026-11-04

**Added**
- Phase-level identity `same_phase(a, b)` and candidate folding: same element set + cell within
  ±1 % / angles within ±1.5° + identical space group; falls back to stoichiometry when the cell is
  missing. The candidate table shows one row per family by default, the "Variants" column shows
  `N entries`, and families can be expanded / merged.
- Dual-criterion benchmark (entry level / phase level); synthetic patterns support
  `--peak-source v3` to stay same-source with the search library.

**Changed**
- Dual pre-filter slots (80 % original ordering + 20 % by intensity-weighted hits so minor phases
  can enter), candidate cap 800 → 1000.
- Phase-level Top-1 in the same library 7/13 → **10/13** ("hitting a same-phase sibling card" is
  no longer counted as a miss).
- New logo / icon set and a recomposed splash screen.

## [3.1.0] — 2026-10-31

**Added**
- **Sequential phase identification**: confirm a phase → subtract its contribution → run the same
  FoM engine on the remaining peaks → confirm the next phase.
- Three-state peak status: explained (residual ≤ 5 % of that peak) / unexplained / low intensity
  not counted (< 1 % of the strongest peak).
- Rollback (undo the last phase / remove a specific phase / clear the list); the pattern area
  overlays reference sticks per phase for visual checking.

## [3.0.0] — 2026-10-23

**Changed** (breaking)
- `.xinDB` single-format consolidation: the v2 SQLite (`cod_inorganics.db`), PolyXRD dump and
  PDF-2 readers are **deleted** rather than deprecated; one reader, one search path
  (`search_match_v3`).
- Default library switched to COD-Inorg and bundled into the portable package, so it works out of
  the box with no separate download.

**Added**
- The internal evaluation build is marked "internal evaluation build" in bold red in the status
  bar.

## Earlier versions

`v1.0.0` (2026-10-09) → `v2.0.0` (2026-10-20) was the project's formation period: the T1–T14
kernel and GUI skeleton, multi-library mounting, the GSAS-II refinement chain, the PDF-2 sidecar
index, and PolyXRD `.sqlite` compatibility with external library mounting. No per-version release
notes were written then; the history is in the corresponding git tags and the archived chapters of
`docs/STATUS.md`.

---

## Detailed release notes

| Version | Notes | GitHub Release |
|---|---|---|
| v3.8.0 | [docs/RELEASE-NOTES-v3.8.0.md](docs/RELEASE-NOTES-v3.8.0.md) | [v3.8.0](https://github.com/XinProf/XinMatch/releases/tag/v3.8.0) |
| v3.7.0 | [docs/RELEASE-NOTES-v3.7.0.md](docs/RELEASE-NOTES-v3.7.0.md) | [v3.7.0](https://github.com/XinProf/XinMatch/releases/tag/v3.7.0) |
| v3.6.4 | — (tag only, no separate notes) | no binary released |
| v3.6.3 | [docs/RELEASE-NOTES-v3.6.3.md](docs/RELEASE-NOTES-v3.6.3.md) | — |
| v3.6.2 | [docs/RELEASE-NOTES-v3.6.2.md](docs/RELEASE-NOTES-v3.6.2.md) | — |
| v3.6.1 | [docs/RELEASE-NOTES-v3.6.1.md](docs/RELEASE-NOTES-v3.6.1.md) | — |
| v3.6.0 | [docs/RELEASE-NOTES-v3.6.0.md](docs/RELEASE-NOTES-v3.6.0.md) | — |
| v3.5.0 | [docs/RELEASE-NOTES-v3.5.0.md](docs/RELEASE-NOTES-v3.5.0.md) | — |
| v3.4.0 | [docs/RELEASE-NOTES-v3.4.0.md](docs/RELEASE-NOTES-v3.4.0.md) | — |
| v3.3.0 | [docs/RELEASE-NOTES-v3.3.0.md](docs/RELEASE-NOTES-v3.3.0.md) | — |
| v3.2.0 | [docs/RELEASE-NOTES-v3.2.0.md](docs/RELEASE-NOTES-v3.2.0.md) | — |
| v3.1.0 | [docs/RELEASE-NOTES-v3.1.0.md](docs/RELEASE-NOTES-v3.1.0.md) | — |
| v3.0.0 | [docs/RELEASE-NOTES-v3.0.0.md](docs/RELEASE-NOTES-v3.0.0.md) | — |

> "—" means the binary and notes for that version were published in the previous repository
> (`PolyXRD/XinMatch`) or that no asset was published separately; after the move, v3.7.0 and
> v3.8.0 have corresponding GitHub Release records.
