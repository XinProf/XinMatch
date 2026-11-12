## XinMatch v3.6.2 — Pattern-area interaction rework (reference-line lane / quick icons / axis-click switching)

> Baseline `v3.6.1` (source `272539d`). This is an **interaction** release: no `core.*`
> interface change, no `.xinDB` / `.xinm` / `config.yaml` format change, FoM weights and
> default search behaviour unchanged item by item, benchmark numbers identical to v3.6.1.
>
> The v3.6.1 installer was **built but never manually accepted, tagged or published**; this
> release changes the pattern area on top of it, and the two binaries do not overlap: the
> 3.6.1 artefacts in `dist/` **do not** contain this release's features.

### 1. Problem to solve

Four points raised during real use (verbatim in STATUS §v3.6.2):

1. "Below the pattern, when a phase is selected in the candidate list, show its corresponding
   positions and intensities… so the user can compare the phase match, with a checkbox in
   that area to show only angular positions or both angles and intensities"
2. "The matched phases on the right should all be shown in that area too… so you can spot
   peaks that are not yet matched"
3. "That area of the pattern can be removed (hidden, but keep the function), move the function
   into the horizontal and vertical axes, left-click to cycle the display, right-click to
   switch as well"
4. "This spot could show some quick icons to process the pattern, like XinRefinement does"

### 2. What was done

#### ① A "reference-line lane" below the pattern (`xinmatch/ui/stick_lane.py`)

One row per phase: a label on the left (chemical formula by default, e.g. `MgCO3`), vertical
lines growing from the row baseline, **sharing the x-axis with the main pattern**
(`ViewBox.setXLink`) — so a stick sits directly above its peak in the pattern.

| Item | Content |
|---|---|
| Two modes | "Also show peak intensity" checked (default): stick height = row-normalized relative intensity; unchecked: all equal height, angles only |
| Row label | Hugs the left edge of the viewport with a translucent themed backing (readable even over sticks); follows pan/zoom |
| Row separator | A faint `InfiniteLine` at each row boundary (`theme.THEMES[current]["chart_grid"]`) |
| Empty state | With no rows the whole lane calls `setVisible(False)` and the pattern takes back that height |

**X-axis alignment** is the easiest thing to get wrong here: the lane hides below the main
pattern, so if the two `ViewBox` left margins (left-axis widths) differ by 1 px the sticks
shift as a whole. Two things make it work —

1. `sync_geometry()` sets the lane's left-axis `fixedWidth` to the main plot's **current
   pixel width** (not a guessed constant); called on window resize, data change, row change
   and theme switch;
2. after the sync, pyqtgraph's `linkedViewChanged` compensates by **on-screen geometric
   overlap** (`ViewBox.py:1075-1100`), aligning the overlapping pixel columns of both views.

The regression test compares "the pixel x of the same 2θ in both views" via
`mapViewToScene()`, with a 1.5 px tolerance.

#### ② Candidate preview row + all confirmed phases enter the lane

| Trigger | Behaviour |
|---|---|
| Candidate list row **highlighted** | A **dashed** preview row (orange, labelled "candidate ⟨formula⟩") appears at the top of the lane |
| Double-click / Enter / "Confirm this phase" | The phase moves into the confirmed list; the preview row disappears and a regular row (solid) appears |
| Undo / clear the match list | Rows disappear / the lane empties accordingly |
| New data / new candidate batch | Preview cleared (`set_candidates()` explicitly emits an empty `candidate_highlighted`) |

- New signal `CandidateListTable.candidate_highlighted(str)` (entry id, empty string when
  nothing is selected); driven by `currentRowChanged`, plus one explicit clear inside
  `set_candidates()` — a model reset clears the current row but **not necessarily** emits
  `currentRowChanged`.
- Colour is identity: lane rows and the reference sticks overlaid on the main pattern
  (`_rebuild_reference_sticks`) index into `PATTERN_COLORS` by the **same index**, so a phase
  has the same colour in both places (pinned by a regression test).
- Intensity is **normalized per row**: the main-pattern sticks are "scale factor × relative
  intensity" (the counts it *claims* to contribute, comparable against observed peaks), while
  the lane's height is "the strongest line fills the row" (it only answers "which lines are
  strong"). The two semantics differ, so the numbers are deliberately not shared.

#### ③ The top axis control bar is hidden; switching moves to clicking the axes

- `PatternPanel._axis_bar` (X dropdown / Y dropdown / fit-to-data) is **hidden**, but the
  three attributes `x_combo` / `y_combo` / `fit_button` are **kept and still functional** —
  the dropdowns remain the single source of truth for axis mode (axis clicks ultimately set
  their `currentIndex` too), and "fit to data range" is taken over by the "original pattern"
  button in the icon row.
- `ClickableAxisItem` (subclass of `pg.AxisItem`): explicitly calls
  `setAcceptedMouseButtons(Left|Right)` — pyqtgraph's `AxisItem` receives no mouse buttons by
  default, so without this, clicking does nothing.
  - **Left click**: cycle to the next mode (X: 2θ ↔ d-spacing; Y: counts → sqrt → log → counts)
  - **Right click**: popup mode menu (current item checked), jump to any mode directly
  - Both axes carry a tooltip describing the current mode and the interaction

#### ④ Pattern quick-icon row (`xinmatch/ui/plot_toolbar.py` + `plot_icons.py`)

Ported from the sister project `D:\Project\XinRefinement` (`gui/plot_tools.py` /
`button_icons.py`):

| Button | Action | Implementation note |
|---|---|---|
| Original pattern | Restore the default view | `reset_view()`: set the range from the **data bounding box** (see "traps") |
| Horizontal box select | Change x only, y auto-fits that interval | `RectMode` + lock Y (stretch the rect in `showAxRect`) |
| Vertical box select | Change y only | `RectMode` + lock X |
| Region zoom | Change both | pyqtgraph's default `RectMode` |
| Pan left / right | Shift the view by 25% | `pan_x(±0.25)` |
| Zoom in / out | Step zoom about the view centre (0.8×/1.25×), y refits | `zoom_scale()` |
| Crosshair | Crosshair + readout (also mirrored in the top-right of the plot) | Selected by default, preserving the pre-rework experience |

Mode buttons are mutually exclusive but **clicking again cancels** — hence no
`QButtonGroup` exclusive mode (an exclusive group cannot be unchecked); momentary buttons
return to unselected immediately.

### 3. Traps hit (all of them recur; recorded in HANDOVER §6)

1. **`RectMode` does not look at `mouseEnabled`.** The intuitive approach is
   `setMouseEnabled(y=False)` so box-select affects x only, but `ViewBox.mouseDragEvent`
   (`ViewBox.py:1332`) goes straight to `showAxRect` under `RectMode` and never reads that
   switch (it only affects panning). → Restore the non-scaled axis to the current range inside
   `showAxRect`, and **the locking branch must use `padding=0`** (the default 2% margin
   stretches the locked axis too, defeating the lock).
2. **`clipToView=True` makes `autoRange()` consider only visible points.** With
   `clipToView` on a curve, `ViewBox.autoRange()` counts only data inside the current window —
   so after a single zoom, "fit to data range / reset" can **never return to the full view**
   (measured: after setting 20–30°, autoRange leaves it untouched). → `reset_view()` now sets
   the range from `data_bounds()` (bounding box of every curve's display coordinates) directly,
   without relying on autorange.
3. **An `AxisItem` width has two sources of truth.** `setWidth(w)` sets `fixedWidth` (the
   layout constraint), while `width()` returns the **current geometric width**; before layout
   runs the two disagree, so using it as an idempotence check resets the width repeatedly.
   → Compare `fixedWidth`.
4. **A model reset may not emit `currentRowChanged`.** After `set_candidates()` swaps data the
   highlighted row is already invalid, but Qt does not guarantee a signal; the preview row then
   stays on screen pointing at a phase that no longer exists. → Emit an explicit empty signal
   at the end of `set_candidates()`.
5. **Refreshing only the view on theme switch leaves a pale lane.** The main window used to
   call `apply_theme_colors()` directly on `pattern_view`; this release routes it through
   `pattern_panel` (view + lane recoloured together).

### 4. Verification

| Item | Result |
|---|---|
| New regression tests | **38**: `test_plot_toolbar` +20 (icon set / exclusive-but-cancellable / reset, pan, step zoom / per-axis box select / crosshair visibility / control bar hidden yet still driving / axis left-click cycle and right-click menu), `test_stick_lane` +13 (one stick per peak / intensity mode / equal-height mode / empty-state hidden / candidate row on top / pixel-level alignment / d-spacing conversion / left-axis width / entry-to-row data), `test_sequential_ui` +5 (confirmed phases enter the lane / colour consistency / candidate preview / cancel clears only the preview / new candidates clear the preview) |
| Full regression | **1809 = 1804 passed / 4 skipped / 1 xfailed / 0 F / 0 E** (18m 43s) |
| Reconciliation | `pytest --collect-only -q` sums to **1809** per file, exactly matching the progress-line character count (baseline 1771 + 38 new) |
| Static checks | `ruff check .` all passed; `mypy xinmatch/core` 99 files, no issues |
| Version consistency | `tests/test_version_consistency.py` 5/5 (pyproject / `_FALLBACK_VERSION` / spec derivation / iss default / package metadata) |

> **`exit code` is not the green criterion**: on this machine pytest deletes its own
> `pytest-of-<user>` temp directory at exit; the sandbox safe-delete hook refuses the bulk
> delete because the file count exceeds the threshold (57 > 50), so a line
> `[safe-delete] ... {"count":57,...}` appears at the end of the log and pushes the process
> exit code to 1. Judge green by project convention: **progress-line character counts**
> (`.`/`s`/`x`/`F`/`E`) plus `--collect-only` reconciliation — both give 1809, and **F/E are 0**.

### 5. Key design decisions

1. **The reference-line lane is its own widget; the "negative-Y region inside the main plot"
   approach was rejected.** The latter gets x-alignment for free, but row height would scale
   with the intensity axis — zoom into the weak-peak region and the whole lane leaves the view.
2. **Row labels are drawn inside the plot area, not as left-axis ticks.** Ticks would require
   widening the left axis enough for formulas like `CaMg(CO3)2`, while that axis must be
   **equal** in width to the main plot's for alignment — the two requirements conflict directly.
   A backed `TextItem` never clips however long the name is and consumes no axis space.
3. **The existing reference sticks in the main pattern (height = claimed counts) stay.** They
   answer a different question: the sticks say "how many counts this phase can explain", the
   lane says "where this phase's lines are and which are strong". The user said "show them in
   that area **too**", not "remove the original lines".
4. **No new shortcuts for the button row.** The v1.3.1 shortcut table (`shortcuts.py`) is
   already full; adding another set with similar semantics (zoom/pan) would inevitably
   conflict, and icons are cheaper to discover than key combinations.

### 6. Upgrade notes

- **No data migration**: `.xinDB` libraries, `.xinm` archives and `config.yaml` all stay compatible.
- **No API change**: `core.*` public signatures untouched; existing `PatternView` /
  `PatternPanel` methods (`add_pattern` / `patterns` / `fit_data_range` / `add_stick_pattern` …)
  are all kept. Only view-operation methods are new (`reset_view` / `pan_x` / `zoom_scale` /
  `fit_y_range` / `set_plot_tool` / `x_display_of` / `left_axis_width`) plus the new modules.
- **UI change**: the top axis control bar is no longer shown. Axis mode moves to "click the
  axis" (left-click cycles / right-click menu), and "fit to data range" is the first
  "original pattern" button in the icon row.
- **Binary**: the v3.6.2 installer / portable package is **not built yet**; run
  `tools/build_exe.ps1` once the manual acceptance plan is settled (steps in HANDOVER §8.3).
