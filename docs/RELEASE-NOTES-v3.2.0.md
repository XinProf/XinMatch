## XinMatch v3.2.0 — Phase-level identity: the candidate list folds same-phase variants + dual-criterion benchmarking

> Baseline `v3.1.0`. This is a **minor** release (new capability plus two default-behaviour
> changes): reference-library format, FoM weights, command line and configuration are all
> unchanged, and old projects and libraries keep working. The search engine changed in exactly
> one place — pre-filter slot allocation (§3.5) — and the candidate cap went 800 → 1000.

### 1. Problem to solve

The reference library holds **dozens of cards for the same phase**. In COD, BaTiO₃ has
`96-210-0858` / `96-210-0859` and TiO₂ anatase has `96-500-0223` / `96-900-8214`. In a
`top_n=40` run, `synth_01`'s Top-40 contained 18 entries from the Al₂O₃ family and `synth_02`
had 12 from the beryl family (18 before the pre-filter allocation change). That creates two
independent problems:

1. **The candidate list is flooded by near-duplicate cards.** Scrolling 40 rows shows the user
   effectively one phase. In `synth_02` calcite's FoM was only 0.0017 below the top entry, yet
   beryl cards occupied the slots and kept it out of the Top-40 for a while (it is now first
   place, see `docs/基准报告-物相检索-v3.md` §3, §10).
2. **The benchmark recorded "found the right phase" as a failure.** Scoring hits strictly by
   `entry_id`, landing on a sibling card counts as a miss — same library, same engine: entry
   level Top-1 is 7/13, phase level is 11/13.

### 2. Core capabilities

| Capability | Description |
|---|---|
| Phase-level identity `same_phase(a, b)` | Same element set + cell axes within ±1 % / angles within ±1.5° + identical space group; **only when the cell is missing** does it fall back to stoichiometry comparison (tolerance 0.25) |
| Candidate folding | `group_same_phase()` cuts the ranked candidates into phase families (family representative = the highest-ranked member); the table shows one row per family by default |
| "Variants" column | Folded state shows `N entries`; hovering lists every card's `entry_id` + six cell parameters, with `▶` marking the representative |
| Expand / merge | Right-click "Expand same-phase variants (N entries)" → one row per card and the column becomes `rank within family / family size` (`1/3`, `2/3`…); right-click "Merge same-phase variants" folds it back |
| Dual-criterion benchmark | `tools/bench_pattern_set.py` reports both entry level (strict id) and phase level (a sibling card counts as a hit) |
| Synthetic ruler re-based | `tools/generate_synthetic_patterns.py --peak-source v3 --library <xinDB>`: d/I come from the same in-library entry, eliminating the intensity mismatch of "pattern generated from v2 cards, searched against a v3 library" |
| Dual pre-filter slots | `prescreen()` keeps the original "main-peak hit → intensity-weighted hits → hit count" ordering for 80 % of the slots and allocates 20 % by "intensity-weighted hits → hit count", letting minor phases enter on reflection count; default candidate cap 800 → 1000 |

### 3. Key design decisions (and why)

1. **The cell takes precedence over stoichiometry**
   Occupancy-refined variants (`Al1.499 Be3 Si6 O18` vs `Al2 Be3 Si6 O18`) have nearly identical
   cells but different formulas; polymorphs (anatase / rutile) share a formula but differ in
   cell. Using stoichiometry as the main criterion would split the former into two phases and
   merge the latter into one — wrong in both directions. So **when a cell exists it decides**,
   and stoichiometry only applies when the cell is missing (the only evidence available).

2. **Greedy grouping, order preserved**
   Candidates are walked in rank order and each is merged into the representative of the first
   family it matches. The representative is therefore always the strongest card in its family
   and family order is unchanged — the first folded row is still the phase that ranked first, so
   the user need not re-learn the ordering. The cost is theoretical non-transitivity (A≈B and
   B≈C need not imply A≈C), which is not a practical issue under the one-dimensional
   approximation of "same phase, different card".

3. **Folding changes display only, not scoring**
   Folding happens in the rendering layer and never touches `rank_candidates`. The fact that 15
   spinel cards push metallic Fe out of Top-1 in `synth_10` is unchanged (see
   `docs/基准报告-物相检索-v3.md` §5, §6) — folding only makes it *display* as one row, so "the
   folded list looks better" must not be mistaken for "recall is fixed". Calcite in `synth_02`
   genuinely returns to first place thanks to the pre-filter change in §3.5, not to folding.

4. **Row indices are no longer candidate indices**
   In the folded state row 2 may correspond to candidate 4. Everything that maps from the UI
   back to data must go through the mapping: `CandidateListTable.selected_results()` /
   `result_at(row)` / `family_results_at(row)` all pass through the folding table, and
   `MainWindow._selected_candidate_results()` (the entry point for the refinement wizard and
   batch operations) has switched to the first of these. Exports and reports must use
   `visible_results()`, or the row count will not match the UI.

5. **Two tenths of the pre-filter slots are cut out for "reflection count"**
   `prescreen` used to take the top N by `(main-peak hit, intensity-weighted hits, hit count)`.
   That criterion implicitly assumes "the true phase's strongest line is also strong in the
   measured pattern" — which fails for minor phases: Al₂O₃ retains only weaker lines in the
   measured `3-1` pattern, `main_hit` scores nothing, and it is pushed beyond rank 800 by the
   main phase and its own family (it appears at rank 197 only with `candidate_limit=8000`).
   The change keeps the original criterion for 80 % of slots and takes 20 % purely by reflection
   count, so a phase with corresponding measured peaks at many d positions can enter on
   coverage. **No FoM was changed and nothing outside the candidate pool was touched** — only
   the slot allocation went from a single criterion to two complementary ones.

### 4. UI and branding

* The candidate list gains an 11th column, "Variants"; the context menu gains a folding toggle
  (shown greyed as "no same-phase variants" when there are none).
* Signal `family_mode_changed(bool)`: emitted when the folding state changes, for the status bar
  and export hints to follow.
* **New logo from v3.2.0**: window icon / application icon / installer icon / splash all unified
  on `assets/icons/logo*.png` / `logo.ico`; the splash is recomposed
  (`tools/compose_brand_assets.py`, using `assets/splash_backdrop.png` as the backdrop plus a
  logo plate bottom-right, a vignette bottom-left and the version number), with the version read
  from `xinmatch.__version__` at runtime.

### 5. Compatibility

* No new dependencies, no schema change; `.xinDB` libraries work as-is.
* `CandidateListTable.set_candidates()` gains the keyword argument `merge` (default `None` =
  keep the current folding state, folded on first use). Positional signatures unchanged.
* **Default behaviour changed**: the candidate table folds same-phase variants by default, so
  the visible row count is the number of phase families rather than the number of candidates.
  External scripts relying on `rowCount() == len(candidates)` must switch to `visible_results()`.
* **Default parameters changed**: `DEFAULT_RANK_LIMIT` / `DEFAULT_CANDIDATE_LIMIT` go from 800 to
  1000, and the pre-filter gains the keyword argument `diversify_slots` (default `None` = 20 % of
  `limit`; pass 0 to restore the old behaviour exactly). The cost is search time: COD-Inorg
  (78k phases) 0.37 → 0.41 s (+11 %), PCOD-Inorg (1.06M phases) 1.50 → 1.89 s (+26 %).
* `xinmatch.__version__` now prefers `pyproject.toml` in the source tree (it used to be masked by
  a stale version in the repository's leftover `xinmatch.egg-info/PKG-INFO`).

### 6. Reference database: bundled default library + mountable external libraries

**Works out of the box**: both binaries bundle `COD-Inorg-20261020.xinDB` (rebuilt, 78,035
phases / 113.1 MiB) at `<install-dir>\data\`. After installing or unzipping, **search works with
no configuration at all**; the library in that folder can be replaced directly, and further
libraries can be mounted.

**Extended libraries ship in the sister repository**:
[PolyXRD/XinMatch-DataBase](https://github.com/PolyXRD/XinMatch-DataBase) Releases provide
`.xinDB` libraries split by provenance; this Release **does not duplicate them** (PCOD alone is
1.7 GB — bundling it in the installer would be pointless):

| Release | Libraries provided | Purpose |
|---|---|---|
| [`20261020-rebuild`](https://github.com/PolyXRD/XinMatch-DataBase/releases/tag/20261020-rebuild) | `COD-Inorg` (same as above), `TCOD-Inorg` 47k phases, `PCOD-Inorg` 1.06M phases, `TCOD-Full` 360k phases, `COD-Full` 530k phases | Fall back to predicted/theoretical libraries when the experimental one has no entry; the Full libraries contain the entire archive |
| [`20261031-mp`](https://github.com/PolyXRD/XinMatch-DataBase/releases/tag/20261031-mp) | `MP-20261031.xinDB` (Materials Project) | Supplementary first-principles structures |

**Three steps to mount**:

1. Download `*.xinDB.zip` from the Release above → unzip to a single `*.xinDB`. **Keep the
   filename as `<kind>-<YYYYMMDD>.xinDB`** (the validator reconciles filename against the `meta`
   inside the library; renaming fails it). The Release's `SHA256SUMS.txt` verifies the archive.
2. Put it in any directory (local disk or a read-only NAS share both work; the library uses
   `journal_mode=DELETE`, so there are no `-wal/-shm` sidecars).
3. GUI: **"Settings → Reference Database…"**, add and select it; or on the command line:

   ```bat
   XinMatch.exe libraries --add "D:\XRD-DB\PCOD-Inorg-20261020.xinDB" --label "PCOD predicted"
   XinMatch.exe libraries --json
   ```

   `--add` only registers the path and **neither modifies nor copies the library file**; remove
   with `libraries --remove <id>`. The registry lives in the user directory at
   `~/.xinmatch/libraries.json`, so upgrading the program does not lose it.

**Coexistence and its cost**: several libraries can be mounted at once and the active one is
chosen at search time. Bigger is slower — measured in this release on the same 208-peak pattern:
COD-Inorg (78k phases) 0.41 s versus PCOD-Inorg (1.06M phases) 1.89 s, because the pre-filter
runs boolean operations over the whole `top_d` matrix and candidate location has to decode more
chunks. **Day to day, use COD-Inorg and mount PCOD/TCOD only when an entry is missing.** The v2
`.db` / `.sqlite` reference libraries were removed in v3.0.0 and mounting one is rejected
explicitly.

### 7. Verification

* Static gates: `ruff check xinmatch tests tools` all pass; `mypy` 121 files
  `Success: no issues found`.
* Regression: full `pytest` (`addopts` excludes `slow` by default) **1477 items: 1472 passed /
  4 skipped / 1 xfailed / 0 failed** (13m27s; `tests/ui` 258 + `tests/search` 310 + `tests/db`
  139 cover most of this change).
* New tests: `tests/search/test_phase_key.py` (14 items: formula parsing, same phase on a
  different card, occupancy variants, polymorphs not merged, different elements, space-group
  conflict, a missing cell is not negative evidence, missing cells compare ratios not counts,
  family order and representative), `tests/ui/test_tables.py` +6 (folding, expand/merge,
  selection mapping, menu toggle), `tests/db/test_prescreen_diversity.py` (4 items: default
  share, out-of-range clamping, a minor phase entering from the hit-count half,
  `diversify_slots=0` reproducing the old behaviour), `tests/db/test_reader_v3_fetch.py` (2
  items: batching under the parameter ceiling, connection proxy above it). The reference oracle
  in `tests/db/test_reader_v3_perf.py` is updated to the new slot policy.
* Benchmark (COD-Inorg 78,035 phases, 13 synthetic patterns, new patterns = v3 library
  intensities):

  | Criterion | Top-1 | Top-5 | Sequential full recovery | Phase recall |
  |---|---:|---:|---:|---:|
  | Entry level (strict id) | 7/13 | 11/13 | 2/13 | 9/24 |
  | **Phase level (sibling card counts as a hit)** | **11/13** | **12/13** | **10/13** | **19/24** |
  | Old patterns / phase level | 9/13 | 10/13 | 7/13 | 15/24 |

  Only two genuine misses remain: `synth_07` (a sparse pattern lacking discrimination; full-
  pattern T1/T5 both fail) and `synth_10` (metallic Fe shares a family with spinel-type oxides,
  first place is taken by `96-900-6921`, T5 hits). `synth_02` is fixed in this release (2/2
  sequential full recovery despite the beryl flood).

* Benchmark (second set, 13 measured real patterns, full `auto_process` chain, 12 evaluable):
  full-pattern Top-1 **10/12**, Top-5 **12/12**; phase recall at Top-20 card-level **24/43** /
  family-level after folding **27/43**; sequential full recovery **5/12**. Sample `5-3` shows
  the substance of folding best: card level 1/5 → family level 5/5.

Details and data in `docs/基准报告-物相检索-v3.md`; the failure-localization process in
`docs/检索基准-v3-诊断-20261104.md`.

### 8. Binary robustness acceptance (5 rounds, all measured and passed)

Five rounds were run against the **actually shipped artefacts** (not the source tree) with the
re-runnable `tools/verify_binary.py`
(`python -m tools.verify_binary --setup … --zip … --workdir …`); raw results in
`.scratch/binary_verify_320.json`:

| # | Check | Method and measured result |
|---|---|---|
| 1 | SHA-256 consistency | hash each artefact → write `SHA256SUMS.txt` → read it back and **re-hash** to compare: matches ✅ |
| 2 | Portable startup | 7-Zip extract (3556 files / 785 MiB) → `variant.txt=internal`, bundled `COD-Inorg-20261020.xinDB` 118,640,640 B, bundled `logo_256.png` **byte-identical** to source; frozen CLI `libraries --json` and `import --help` both exit 0, registry default library `entries=78035 / available=true` ✅ |
| 3 | Frozen GUI smoke | three offscreen self-test hooks: `REG` → `variant=internal, registration_enabled=false, internal evaluation build`; `LIBS` → 10 library records; `ABOUT` → About dialog rendered to PNG (9,117 B, new logo visible). Plus 3 consecutive cold starts exit 0 with no leftover locks ✅ (Chinese renders as boxes offscreen because the session lacks CJK fonts — not an artefact problem) |
| 4 | Silent install | `XinMatch-Setup-3.2.0.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CURRENTUSER /DIR=… /LOG=…` → exit 0, log says `Installation process succeeded`, 3558 files installed, `XinMatch.exe` + `data\COD-Inorg-20261020.xinDB`, `variant.txt=release` ✅ |
| 5 | Post-install startup | frozen CLI in the install dir: `libraries --json` exit 0; **real-pattern end-to-end search** `search 5-1.txt --db <installed bundled library> --top-n 5 --json` → 118 peaks / 5 candidates / top `96-210-0189` (calcite, matching the benchmark); release GUI hook `variant=release, registration_enabled=true, unregistered`; installer and main program version resource `ProductVersion=3.2.0` ✅ |

> In earlier versions `/SILENT` hung in non-interactive sessions and the release variant was
> blocked by the registration dialog; adding `/CURRENTUSER` made both work this round. A manual
> double-click acceptance by the user before release is still recommended (automation covers
> only the offscreen path).

### 9. Release artefacts

| Attachment | Bytes | SHA-256 |
|---|---:|---|
| `XinMatch-Setup-3.2.0.exe` | 254,143,458 | `350b24cfe0ffb669a1792216a5246a20ecd6c1d9461dd18843e6ead525a93590` |
| `XinMatch-Internal-3.2.0.zip` | 353,721,811 | `96e818ee29cbe5453178b7d6d793f1d408e97fc1dedcca7062a4d73016d47756` |
| `SHA256SUMS.txt` | 185 | manifest of the two hashes above |

Both binaries bundle `COD-Inorg-20261020.xinDB` (rebuilt, 78,035 phases); **mount extended
libraries from the `XinMatch-DataBase` repository per §6** — this Release does not carry
gigabyte-scale libraries.
