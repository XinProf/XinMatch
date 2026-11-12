## XinMatch v3.1.0 — Sequential phase identification: confirm one phase → re-search the remaining peaks → confirm again

> Baseline `v3.0.0`. This is a **minor** release (new capability, no breaking change):
> reference-library format, search engine, FoM weights, command line and configuration are all
> unchanged; old projects and libraries keep working.

### 1. Problem to solve

A single search-match run gives one ranking. In a multi-phase sample the main phase's strong
lines keep dominating the FoM: search again after confirming it and the top of the list is still
the main phase's sibling cards, while minor phases stay beyond rank 20. The only workaround was
to manually "exclude the peaks already explained" in the peak list — by feel, and with no way to
tie the exclusions back to candidate cards.

v3.1.0 closes the loop on "confirm phase by phase": **every confirmation re-searches against the
remaining unexplained peaks**, so the ranking answers "what is left".

### 2. Core capabilities

| Capability | Description |
|---|---|
| Confirm and search | Double-click / Enter / right-click "Confirm as matched phase" / the bottom "Confirm this phase" button — all four entries are equivalent |
| Remaining peaks = observed peaks − confirmed-phase contributions | For each phase a least-squares fit of its reference intensity table against observed intensities gives a count-domain scale factor `scale` (counts / unit relative intensity), subtracted peak by peak |
| Three-state peak status | **Explained** (residual ≤ 5 % of that peak), **unexplained** (significant but not yet explained), **low intensity, not counted** (< 1 % of the strongest peak in the pattern; excluded from search) |
| Residual search | `search_residual()` runs **the same** FoM engine over the remaining peaks (not a second scoring implementation) and automatically drops already-confirmed entries |
| Rollback | Undo the last phase / double-click a match-list row / remove a specific phase / clear the match list → the whole residual is recomputed |
| Visual check | The pattern area overlays reference sticks per phase (height = the counts that phase claims to contribute), so agreement or disagreement with observed peaks is visible at a glance; the peak list's "linked" column ticks in step |

### 3. Key design decisions (and why)

1. **Full rebuild rather than incremental update**
   `SequentialIdentifier` recomputes every layer from the **original peak list** on each change:
   correlations → scale factors → residual → mask. The reason: phase B's scale factor was fitted
   after phase A was subtracted, so removing A must be allowed to change B's value. Incremental
   updates accumulate floating-point drift, leave stale correlated peaks behind, and cannot keep
   the undo path clean. The cost is one correlation pass per phase (microseconds), in exchange for
   the invariant "state = f(original peaks, phase sequence)".

2. **The scale factor is fitted in the count domain, not reused from the FoM's `i_scale`**
   `CandidateResult.i_scale` is the LSQ shape factor after both sides are normalized to 100
   (ideal ≈ 1.0) and **cannot** be used to subtract counts from observed peaks. The sequential
   module fits its own in the count domain with `scale = Σ(I_residual·r)/Σ(r²)`
   (`r = I_ref/I_ref,max`), which is what gives the result the dimension "counts / unit relative
   intensity".

3. **Low-intensity peaks get their own state instead of being forced into "explained"**
   A measured lesson (synth_02, see the acceptance document): after confirming both phases,
   32/51 peaks were still "unexplained" while 92 % of the intensity was explained — the rest were
   small noise bumps, and the third round then matched that noise into junk candidates such as
   `Fe0.75V0.25`. Marking peaks below 1 % as "not counted" (neither explained nor remaining) is
   both honest and makes the third round return an empty list.

4. **Partially explained peaks keep their residual intensity**
   For an overlapping peak (main phase + unconfirmed phase), subtracting the main phase's
   contribution leaves a positive residual that stays in the remaining set with its intensity
   lowered accordingly; it is not swallowed by "the position coincided, so it counts as
   explained". This is decisive when a minor phase sits on the main phase's strong lines.

### 4. UI

* The candidate-list panel gains an action row: `Confirm this phase (add to match list)` /
  `Undo the last phase` / `Clear match list` plus residual readouts
  (`N phases confirmed | X/Y peaks remaining | Z% of intensity explained | K low-intensity peaks not counted`).
* The Match List is filled by confirmations; double-clicking rolls that phase back.
* The peak list's "linked" column: peaks positionally related to a confirmed phase get a ✓.
* Pattern area: one set of reference sticks overlaid per phase, colours in the same order as the
  candidate rows' colour chips.
* FPFM mode has no peak list: the first confirmation lazily runs one peak search on the current
  pattern and then enters the sequential flow (with a status-bar note).
* Every full-pattern search (including peak detection and FPFM search) **resets** the sequential
  context — a new search means a new round of analysis.

### 5. Compatibility

* No new dependencies; both `.xinDB` and legacy SQLite libraries work (through the existing
  `search_match` dispatch).
* No numeric criterion of `search_match` / `rank_candidates` / the FoM changes: sequential is
  just "run it again on a different peak set".
* The `CandidateTable` context-menu item "select/deselect" became "Confirm as matched phase (add
  to match list)"; the `toggle_selection` signal is kept (external scripts unaffected).
* `Phase.scale_factor` / `Phase.correlations` are written back with real values during the
  sequential flow, so the downstream fields read by the refinement wizard / reports / CIF export
  are self-consistent.

### 6. Verification

* Full regression (final state on this machine): **1452 passed / 5 skipped / 0 failed**, 849 s
  (14m09s), EXIT=0.
* New tests: `tests/search/test_sequential.py` (18 items, pure synthetic, verifiable by hand),
  `tests/ui/test_sequential_ui.py` (17 items, offscreen UI loop).
* Multi-phase samples against the real library (default COD inorganic library, 71k): two-phase
  samples **3/3 fully recovered** (synth_02 / 04 / 12, both phases pinned within two rounds);
  the three-phase sample synth_01 recovered 2/3 (ZnO not recalled, a limitation of base recall).

Details and data in `docs/序贯物相鉴定-v3.1.0.md`.
