## XinMatch v3.6.1 — Three field-reported defects fixed (duplicate legend / frozen refinement / wrong crystal system)

> Baseline `v3.6.0` (source `489e71d`). This is a **pure defect-fix** release: no new
> features, no interface change, no data-format change. `.xinDB` schema, FoM weights, default
> search behaviour and `core.*` public signatures are **unchanged item by item**; benchmark
> numbers are identical to v3.6.0.
>
> The v3.6.0 installer was built but **never manually accepted, tagged or published**; this
> release supersedes it directly, so users need not install 3.6.0 first.

### 1. Problem to solve

All three were hit in real use, with **unrelated root causes** — not three faces of one bug.

1. **"I select one phase and it is drawn twice; confirm two phases and I get four; even the
   sample is drawn twice."** Every curve appeared twice in the legend, so users concluded the
   plot was drawing duplicates or that confirming a phase added it twice.
2. **"The refinement wizard opens empty; I press Next, Next, and it freezes."**
   The window went fully white with "(Not responding)" in the title bar, and only a forced
   kill helped.
3. **"Hexagonal phases show as monoclinic in the match list."** (In the screenshot
   `Anatase` / `Rutile` had crystal-system letter `T`, but other samples in the same column
   showed `M`, while those library entries are hexagonal.)

### 2. What was fixed

#### ① Duplicate legend — there was always only one curve

| Item | Content |
|---|---|
| Measured fingerprint | `plotDataItems = 1` but `legend_rows = 2` (curves right, legend wrong) |
| Root cause | pyqtgraph 0.13.7's `PlotItem.addItem()` already adds a named `PlotDataItem` to the legend at the end (`PlotItem.py:516-552`: `if name is not None and self.legend is not None: self.legend.addItem(item, name=name)`, with `name` taken from `item.name()`); `pattern_view` then called `self._legend.addItem(...)` once more |
| Fix | Remove the manual legend insertion from `add_pattern` / `add_stick_pattern` |
| Related fix | `remove_pattern` / `remove_stick_pattern` no longer remove legend rows **by name**. `PlotItem.removeItem()` already removes **by item identity** (`LegendItem.removeItem` matches `sample.item is item`); removing by name also deletes the row of a same-named sibling curve (redrawing one phase always produces the same name) |

**User-visible effect**: one curve, one legend row. Select 1 phase → 1 experimental + 1
reference curve; confirm 2 phases → 1 + 2.

#### ② Refinement wizard freezes + goes white — one blocking call plus one misfire path

| Item | Content |
|---|---|
| Real cause of the freeze | `_run_refinement()` called `_execute_driver()` (a GSAS-II subprocess, tens of seconds to minutes) **synchronously on the GUI thread**, calling `QApplication.processEvents()` exactly once, after which nothing could repaint → the window entered "(Not responding)" → the DWM discarded its contents → **white screen**. The blank area in the screenshot was the consequence of blocking, not a layout that failed to build |
| Misfire path | The nav bar was `[Back] … [Next][Start refinement][Finish]`. After page 4 hid "Next", "Start refinement" **slid into the same position**; a user double-clicking "Next" on the parameter page had the third click land on the slid-over "Start refinement" → the long task started immediately |
| Fix 1 | Route through `run_with_busy()` (`xinmatch/ui/busy.py`: background `QThread` + modal busy indicator + queued signal back to the GUI thread); all `processEvents()` removed |
| Fix 2 | "▶ Start refinement" moved **inside page 4**; the bottom nav bar keeps only `Back / Next / Finish`, so physical positions no longer overlap |
| Fix 3 | New `_set_running()` / `_on_refine_done()` / `_on_refine_failed()`: locks navigation and duplicate submission while running; failures surface readable text (no longer just `traceback.print_exc()`); retry is possible after an error |
| Fix 4 | Refuses to start with no phase ticked (never feeds an empty phase list to GSAS-II); page 1 shows an explicit empty state when `phases` is empty |
| Cosmetic fixes | The result plot used pyqtgraph's default **black background** (violating "never black in the pattern area under the light theme") → coloured from `theme.THEMES[current]["chart_bg"]`; the unit-cell table was squeezed by `QPlotWidget`'s Expanding policy to **one visible row** (multi-phase refinement looked like a single-phase one) → 3:2 height split plus Stretch on the "Phase" column and ResizeToContents on numeric columns; `cell is None` no longer renders a blank row (fills `—`) |

**Measured verification**: under a real modal `exec()`, letting the driver run 1.2 s while a
100 ms `QTimer` counted ticks — **36 ticks** (the old code managed only 1–2), with results
written back correctly and Rwp displayed after completion.

#### ③ Crystal-system letter — hexagonal labelled monoclinic

| Item | Content |
|---|---|
| Root cause | `tables._crystal_system_letter()` judged low symmetry only by "count of non-90° angles": `n_non90 == 1 → M` (monoclinic), otherwise `A` (triclinic). But hexagonal (a=b, α=β=90°, γ=120°) has **γ as its only non-right angle** → returned `M`. Every hexagonal phase — graphite / ZnO / quartz — showed as monoclinic in both lists; rhombohedral (a=b=c, α=β=γ≠90°) fell into `n_non90 == 3` → `A` (triclinic) |
| Fix | Two geometric criteria added: hexagonal `H` (a=b, α=β=90°, γ=120°) and rhombohedral `R` (a=b=c, α=β=γ≠90°), placed **before** the monoclinic/triclinic tests |
| Alphabet | `C` cubic / `H` hexagonal / `T` tetragonal / `R` rhombohedral (trigonal) / `O` orthorhombic / `M` monoclinic / `A` triclinic; unknown cells stay `X` |

### 3. Verification

| Item | Result |
|---|---|
| New regression tests | **18**: `test_pattern_view` +3 (legend rows ≡ curve count, deleting a same-named curve removes only one row, `clear()` resets to zero), `test_refinement_wizard` +7 (driver runs on a **non-GUI thread**, running state locks navigation, "Start refinement" is not in the nav bar and appears only on page 4, empty selection refused, readable failure with retry, result-plot background follows the theme, controls disabled while running), `test_tables` +8 (seven crystal systems plus `None`, full coverage) |
| Full regression | **1771 = 1766 passed / 4 skipped / 1 xfailed / 0 F / 0 E** (18m 05s, exit=0) |
| Reconciliation | `pytest --collect-only -q` sums to **1771**, exactly matching the progress-line character count (baseline 1753 + 18 new) |
| Static checks | `ruff check .` all passed; `mypy xinmatch/core` 99 files, no issues |
| Version consistency | `tests/test_version_consistency.py` 5/5 (pyproject / `_FALLBACK_VERSION` / spec derivation / iss default / package metadata) |

### 4. Key design decisions

1. **Fixed the freeze with `run_with_busy`, not a hand-rolled `QThread`.** The project already
   has a single entry point (background thread + modal busy indicator + `parent._busy_active`
   re-entrancy guard + cancellation predicate); a hand-rolled thread bypasses the re-entrancy
   guard and cancellation reporting, and every future dialog would grow its own variant.
2. **"Start refinement" does not stay in the nav bar.** It could have been kept visible but
   disabled, yet that only fixes the misfire, not the semantics of "the user thinks this page
   is still a transition page". Inside the page, the nav bar navigates and the page owns its
   own action.
3. **No "start refinement automatically on entering page 4".** Refinement can run for minutes;
   starting automatically binds an expensive action to a single page turn and denies the user
   the chance to inspect parameters or adjust the background order first.
4. **The crystal system is still derived from cell geometry, not read from
   `entries.crystal_system`.** The value does exist in the library (`reader_v3.fetch_meta`
   already returns it), but the `Entry` model has no such field and adding one would ripple
   through the model layer and every construction site; geometric derivation is equivalent and
   free as long as the cell is trustworthy. The real lesson is that **a higher-level derivation
   must enumerate every branch explicitly** instead of waiting for its own fallback.

### 5. Binary artefacts

Built 2026-11-08 (`tools/build_exe.ps1 -Variant release -Installer` + `-Variant internal` + 7-Zip):

| File | Size | SHA-256 |
|---|---|---|
| `XinMatch-Setup-3.6.1.exe` | 242.4 MiB (254,158,820 B) | `55d4f90d8350e7114549e944dbc221119da66155ed457c8575c869e613a9c60f` |
| `XinMatch-Internal-3.6.1.zip` | 351.2 MiB (368,271,127 B) | `f463a1a6217b91d985e5f6373077b96e4f5b6e8bc1dcc3734e79fc02369c86c2` |

- The portable tree is 784 MB; `XinMatch.exe --version` → `xinmatch 3.6.1`, `FileVersion = 3.6.1`;
  the bundled default library `data/COD-Inorg-20261020.xinDB` (118,706,176 B / **78,035 phases**)
  means search works right after unzipping.
- `dist/SHA256SUMS.txt` holds the two 3.6.1 entries (**LF line endings**); `sha256sum -c` passes both.
- **The automated acceptance gate `tools.verify_binary` passed all 5 rounds** (`all_pass=true`):

| Round | Check | Result |
|---|---|---|
| 1 | SHA-256 of both artefacts + manifest round-trip | OK (matches the table above) |
| 2 | Portable extract → frozen CLI (`libraries` / `import --help`) → bundled library → logo bytes | OK (`libraries` rc=0, 78,035 phases, `variant=internal`) |
| 3 | Frozen GUI offscreen hooks: REG / LIBS / ABOUT | OK (10 libraries; ABOUT screenshot 9,117 B) |
| 4 | Silent install into an isolated directory | OK (`variant=release`, bundled library present) |
| 5 | Installed-state frozen CLI + real search | OK (`5-1.txt` **118 peaks → 5 candidates**, top `96-210-0189`) |

> ⚠️ **Manual double-click acceptance has not happened yet.** Per the hard red line, no
> `v3.6.1` tag and no GitHub Release until it passes. The manual checklist is in
> `docs/HANDOVER-20261106.md` §8.3, with **one new item** for this release: open a pattern and
> confirm each curve has exactly one legend row; open the refinement wizard, press "Start
> refinement" and confirm the window does not go white, background progress is visible, and
> Rwp is written back.

### 6. Upgrade notes

- **No data migration**. `.xinDB` libraries, `.xinm` archives and `config.yaml` all stay
  compatible; no need to rebuild reference libraries.
- **No API change**. `core.*` public signatures untouched; `RefinementWizard` constructor
  arguments untouched — only internal button ownership and the running thread changed (the
  signature of injected `driver` test doubles is unchanged).
- **Legend behaviour changed**: if an external script reads `pattern_view._legend.items`
  directly, the row count goes from "2 × curves" to "curves" — that is the fix, not a
  regression.
