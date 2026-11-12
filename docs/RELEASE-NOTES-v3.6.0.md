## XinMatch v3.6.0 — GUI goes from skeleton to usable; peak-position refinement two orders of magnitude faster

> Baseline `v3.5.0` (tag `fe4ccfe`). This is a **feature completion + performance + benchmark
> infrastructure** release. `.xinDB` format, FoM weights, P-value definitions and default
> search behaviour are **unchanged item by item** — every A/B this round concluded "leave it
> alone" (see the last two rows of §4), so the published numbers on all three rulers remain
> valid.

### 1. Problem to solve

Three items: the first two are "you can click it but nothing happens", the third is "the
computation finishes in no time yet we sit waiting on I/O".

1. **11 of 15 feature modules had empty menu actions.** "Quantitative analysis",
   "Microstructure", "Indexing" and "Data export" were all clickable in the toolbar and the
   Analysis menu, but clicking them only posted "module skeleton is in place" in the status
   bar. The `core` capability had long been ✅ (`core.quant` / `core.micro` / `core.index`;
   T8 / T11 / T9 all complete) — nobody had wired the GUI to it.
2. **The candidate list showed only 20 rows, hiding answers that were already computed.**
   Scoring runs over the entire pool and `top_n` is only a slice — 20 rows gives family
   coverage 81/98, 50 rows gives 89/98, at zero compute cost. This was stuck on the undefined
   question "is display budget a product decision or an algorithm parameter".
3. **Preprocessing was an order of magnitude slower than search itself.** Measured against the
   default library, the 2.31 s end-to-end splits into 1.32 s import, 0.37 s scoring and
   **0.18 s actual search**; yet the 207-peak `3-1.txt` spent 35.2 s in preprocessing alone
   (peak-position refinement used Nelder-Mead with a per-peak restart).

### 2. Core capabilities

| Capability | Description |
|---|---|
| **Profile Fitting dialog** | Same F5 entry; four profile shapes (pseudo-Voigt default / Gaussian / Lorentzian / Pearson VII); the result table gives refined 2θ / FWHM / area / I-I₀ + Rwp; the fitted curve is overlaid in the pattern area, and "apply to peak list" writes back so Search-Match can run again |
| **RIR quantitative analysis dialog** | Confirmed phases + peak list → main-peak intensity is the largest integrated intensity among the experimental peaks referenced by `Phase.correlations`; the RIR column is editable (default 1.0); the computation is delegated to `core.quant.rir_quantify` (Hill–Howard adiabatic method); wt% is written back to `Phase.weight_fraction` and the match list refreshed |
| **Microstructure analysis (Scherrer / W-H)** | Two pages sharing λ and K: Scherrer gives per-peak D plus an arithmetic mean; Williamson-Hall reports D / ε / R² / peak count with the regression data listed. The pages do not block each other (with a single peak, W-H only warns). **This release does no instrumental broadening correction**, and the UI says so permanently |
| **Indexing wizard (Treor90 / DicVol06)** | d computed from 2θ + λ, excluded peaks skipped; algorithm / wavelength / tolerance / 7 crystal systems selectable (high-symmetry four by default); a 10-column result table after `deduplicate` + `rank_solutions`; empty solutions only warn without a dialog; the selected row copies its cell |
| **Aggregated data-export menu** | Pattern ASCII profile / two-column 2θ–I, peak-list CSV, candidate-list CSV (same source as the display), match-list CSV, `.xinm`, selected-phase CIF; the three tables' right-click "Export (CSV)…" was dangling before and is now wired |
| **All menu actions connected** | Data import / raw-data processing (background · smoothing · Kα2 · reset submenu) / peak list / restraints / Rietveld refinement / the five above — only `user_db` remains a placeholder (no core capability, requirements undecided) |
| **Candidate-list row cap** | Setting `candidate_list.max_display_rows` (default 50, counted per family); the table truncates to N rows when folded and per card when expanded; `.xinm` archives and `win._candidates` keep everything; reports use `visible_results()` so they match the table |
| **Peak-position refinement switched to LM** | `scipy.optimize.least_squares` replaces per-peak Nelder-Mead restarts: preprocessing **35.2 s → 0.35 s**, 207-peak CLI end-to-end **36 s → 2.3 s** |
| **Periodic table redesigned** | Sizing is now driven by font metrics (no longer clipped by the global QSS `padding` / `min-height`); the three states are encoded three ways — colour + line style + font weight (red-green colour-blind friendly) — with a permanent legend and per-key tooltips; the dialog sizes itself and falls back to scrolling |
| **One-line sample-element entry** | Type `Zn Al Ca O F` on the Restraints page → every other element is marked excluded (through the `element_inv` inverted index); real-pattern phase recall **20/43 → 30/43**, and `3-1` minor phases go 1/3 → 3/3 |

### 3. Key design decisions (and why)

1. **The GUI only wires things up; it does not reimplement algorithms.** All five new dialogs
   delegate computation to `core.*` (`fit_profile` / `rir_quantify` / `scherrer_from_peaks` /
   `williamson_hall_from_peaks` / `index_treor`·`index_dicvol`); the GUI side only collects
   parameters, presents results and guards against empty data. The CLI can reuse the same
   semantics later, so "one set for the GUI, another for the CLI" cannot happen.
2. **Indexing makes no "first row is the answer" implication.** On a synthetic cubic pattern
   with a=4.0 Å, DicVol correctly puts `cubic a=4.0000` first, but **Treor's first row is
   `tetragonal a=2.0 / c=2.3094`** — same FoM (6.00), same 6/6 indexing, and `rank_solutions`'
   rule of "same FoM, smaller volume first" (Werner 1985) places the tetragonal cell V=9.24
   ahead of the cubic V=64. That is a rule from the literature, not a bug, so the UI shows a
   **permanent hint**: "an equivalent lower-symmetry cell may rank above the true symmetry —
   don't read only the first row". The test likewise asserts "a cubic a≈4.0 exists", not
   "the first row is cubic".
3. **Microstructure results are not written back to the peak list.** Consistent with the
   reference software: Scherrer / W-H produce conclusion numbers, not an edit job on peaks;
   writing back would only make users think the peaks were re-fitted.
4. **The RIR column defaults to 1.0 but stays editable.** The reference software likewise has
   the user enter I/Ic from the PDF card — the library has no reliable RIR field, and
   hard-coding a "standard value" is more dangerous than leaving it blank.
5. **Periodic-table size is not hard-coded.** See §5.1: hard-coding 38×30 left only 8 px of
   content area under the themed QSS.
6. **The candidate cap is a setting, not a constant.** The `tests/ui/*` fixture libraries are
   tiny; a hard-coded constant would make the three search paths always fetch 200 cards and
   slow the suite down. As a YAML setting, tests can clamp it and users can change it.

### 4. Verification

| Item | Result |
|---|---|
| Full regression (source, 2026-11-08) | **1753 = 1748 passed / 4 skipped / 1 xfailed / 0 failed / 0 error**, exactly reconciled with `--collect-only` |
| New UI unit tests | periodic table 5 + indexing 12 + microstructure 13 + quantitative 8 + Profile Fit 9 + export menu 14 + module wiring 7 + candidate cap 19 |
| Static checks | `ruff check .` all green; `mypy xinmatch/core` 99 files, no errors |
| Default search behaviour | Every A/B this round concluded "leave it alone": `prescreen_order` stays intensity, `sigma_intensity=10` stays, FoM weights stay at the published values, sequential "skip pure elements" stays off, `i_scale` stays at clamp 1.0; the alias table changed only the truth side (both rulers rerun with zero change item by item) |
| Benchmark infrastructure | New third ruler: IUCr CPD (19 samples / 48 phases); family-level criterion changed to "any member of the family counts as a hit"; real-pattern fine-grained denominator 43 → 50 |

### 5. Binary artefacts

| File | Size | SHA-256 |
|---|---|---|
| `XinMatch-Setup-3.6.0.exe` | 242.4 MiB | `fb5b0c19433213a1fb935a1f83e5611ed092f77d62370cb7aee645e1a586b155` |
| `XinMatch-Internal-3.6.0.zip` (portable, not distributed with the Release) | 337.4 MiB | `2a46f4654094a922a7e2d5d406d0e21c34ff851c49c74c5802455dba25413665` |

The automated gate `python -m tools.verify_binary` passed all 5 rounds (56 s, `all_pass=true`):

| Round | Content | Result |
|---|---|---|
| 1 | SHA-256 of both artefacts + manifest round-trip | matches the table above |
| 2 | Portable extract → frozen CLI `libraries` / `import --help`, bundled library, logo | 78,035 phases; `variant=internal` |
| 3 | Frozen GUI offscreen hooks REG / LIBS / ABOUT | 10 libraries; internal build shows "internal evaluation version" in the status bar |
| 4 | Setup silent install into an isolated directory | `variant=release`; bundled library in place |
| 5 | Installed-state CLI + real search (`5-1.txt`, 118 peaks) | 5 candidates, top `96-210-0189 C Ca O3` |

`FileVersion=3.6.0`, `XinMatch.exe --version` → `xinmatch 3.6.0`, `dist/SHA256SUMS.txt` is LF
and `sha256sum -c` passes both.

> **Status**: binaries produced and past the automated gate; **manual double-click acceptance
> has not happened**, so `v3.6.0` is not tagged and no GitHub Release exists. Per project
> discipline, every EXE must pass manual double-click acceptance before release (see
> `docs/HANDOVER-20261106.md` §8.3 item 6).

### 6. Upgrade notes

1. **The periodic-table styling problem was never "the font is too small".** If you previously
   felt the element symbols were clipped, the root cause was the theme QSS `padding: 5px 14px`
   eating the button's content area plus `min-height: 20px` outranking `setFixedSize()`. Sizing
   now comes from `QFontMetrics`, verified at 9 / 13 / 16 pt with `min == max == actual`.
2. **The candidate list shows 50 rows by default** (was 20). If that feels long, change it back
   under "Settings → Options → Candidate list row cap"; it is display truncation only and does
   not affect search.
3. **`.xinm` archives still hold all candidates** and lose nothing to display truncation.
4. **The `.xinDB` reference format is unchanged**; existing libraries carry over with no rebuild.
5. **One new config key**: `candidate_list.max_display_rows` (treated as 50 when missing, so old
   configs work as-is).
