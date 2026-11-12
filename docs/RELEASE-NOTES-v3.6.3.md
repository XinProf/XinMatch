## XinMatch v3.6.3 — Element constraints in four states + closed loop (semantics aligned with PolyXRD)

> Baseline `v3.6.2` (source `41279d4`). This release touches two things: the **element
> constraint** path and the **default search mode**. `ElementState` grows to four states,
> a closed-loop switch is added, and the pre-filter gains an "at least one of" channel;
> phase identification now defaults to **FPFM full-profile fitting (no peak search)**
> instead of "peak-list FoM (peak search)".
>
> **Legacy behaviour is bit-for-bit unchanged**: `closed_world` defaults to `False`, and the
> new `HAS` / `MAYBE` states are never written by old archives, so "only mark must-have /
> absent" behaves exactly as in v3.6.2. Benchmark numbers (real-pattern phase recall 30/43
> and friends) do not move — the complement constraint produced by quick entry (113
> `EXCLUDE` entries) and the `elements_excluded` set derived from the closed-loop form are
> the same set.
>
> The v3.6.1 / v3.6.2 installers were **never manually accepted, tagged or published**; no
> binary has been built for this release yet.

### 1. Problem to solve

User's words:

> Element constraint logic in the periodic table — implement it with reference to `D:\Project\XRD\PolyXRD`

Before v3.6.2 XinMatch had only three states, with two real gaps:

1. **No "at least one of"**. To express "the sample is MgO or CaO or CaCO3 — that family",
   users had to mark Mg, Ca, C and O **all as "must contain"** — which is AND semantics,
   leaving only CaMg(CO3)2 and shutting out the most common single-component phases.
2. **No closed loop**. "Allow only the few elements detected in the sample" could only be
   written as "mark the other 113 elements as absent" (the v1.4 "exclude the rest" quick
   entry); clicking 118 buttons one by one is unrealistic, and opening the periodic-table
   dialog then shows 113 red frames, which hides what you actually selected.

PolyXRD's four states + `closed_world` fill exactly these two gaps
(`src/polyxrd/utils/formula_parser.py::elements_match_filter` +
`src/polyxrd/views/widgets/element_periodic_table.py`).

### 2. Semantics (aligned with PolyXRD, clause by clause)

Let S = the phase's element set, and P / H / M / E = must-have / contains / possible / absent:

| Class | Predicate | Meaning | Pre-filter implementation |
|---|---|---|---|
| Must-have P | `P ⊆ S` | every one must be present (AND) | `elements_allowed` |
| Contains H | `S ∩ H ≠ ∅` | at least one of them (OR) | `elements_any` (**new**) |
| Possible M | no hard condition | only widens the closed-loop allowed pool | contributes to the pool only |
| Absent E | `S ∩ E = ∅` | any of them eliminates the phase | `elements_excluded` |

Two additional rules, both easy to miss:

* **Once the must-have set is satisfied, "contains" is no longer required.** Otherwise
  single-element phases such as pure metals could never enter the candidate list.
* **Closed loop**: when `P∪H∪M` is non-empty, every unassigned element is treated as
  "absent", i.e. `S ⊆ P∪H∪M`. All three empty = search the whole library; only "absent"
  marked = open world (exclude just those elements).

### 3. What was done

#### ① `core` — model and predicate (`xinmatch/core/model/restraints.py`)

`ElementState` grows from three values to five, **old values unchanged** (`red` / `yellow` /
`green`), adding `HAS = "has"` and `MAYBE = "maybe"`, so old `.xinm` archives, YAML and
`Restraints.from_dict` all load as before.

```python
class ElementState(str, Enum):
    EXCLUDE  = "red"      # absent
    OPTIONAL = "yellow"   # unrestricted (treated as absent once the closed loop is on)
    REQUIRED = "green"    # must-have (AND)
    HAS      = "has"      # contains (OR, at least one)
    MAYBE    = "maybe"    # possible (only widens the closed-loop allowed pool)
```

`Restraints` gains `closed_world: bool = False` (serialized in `to_dict` / `from_dict`;
old archives lacking the key default to `False`); `passes_elements(entry_elements, *,
closed_world=False)` is rewritten as a four-state predicate.

#### ② `core` — the single conversion point `element_constraint_sets()`

```python
required, any_of, excluded = element_constraint_sets(restraints)
# → prescreen(elements_allowed=required, elements_any=any_of,
#             elements_excluded=excluded)
```

The closed loop opens no new channel: it folds "118 elements − allowed pool" directly into
`excluded` (`S ⊆ pool` ⟺ `S ∩ outside-pool = ∅`), reusing the existing `element_inv`
inverted index. Pre-filtering, direct SQL (`query_filter.search_by_elements`) and the
benchmark scripts (`tools/bench_iucr._pools`) **all three call this one function**, so the
semantics cannot drift.

#### ③ `core` — pre-filter gains `elements_any`

`XinDBReader.element_union_filter()`: phases containing **at least one** of *elements* — the
dual of `element_filter` (must contain all). `prescreen(..., elements_any=…)` intersects it
with the other two channels.

#### ④ GUI — four-state periodic table (`xinmatch/ui/periodic_table.py`)

* Click order follows PolyXRD: "unrestricted → contains → possible → absent → **must-have**"
  — must-have is **last** because it filters hardest; a misclick just returns to the start
  instead of emptying the candidate list.
* The four states **do not rely on colour alone**: line style + line width + font weight
  give three-way encoding (red-green colour-blind friendly, still separable when shrunk or
  printed in black and white).

  | State | Background | Border |
  |---|---|---|
  | Unrestricted | `#f7f8f9` | 1 px solid grey |
  | Contains | `#e8f5e9` | 2 px solid green + bold |
  | Possible | `#fff8e1` | 2 px **dotted** amber |
  | Absent | `#fbdede` | 2 px **dashed** red + bold |
  | Must-have | `#d8f0de` | **3 px** solid dark green + bold |

* The legend lists only the four effective states (`LEGEND_ORDER`) and sits permanently
  above the grid.
* New `grouped()` (group by state — shared by the summary row and the tests) and
  `apply_light_elements()` (one click marks O/C/H/N/S as "contains", **filling only
  unassigned cells**; anything the user explicitly set is left alone).

#### ⑤ GUI — two new controls on the panel

| Control | Behaviour |
|---|---|
| Checkbox "Restrict to selected elements" | The closed-loop switch. A permanent line next to it reads `Closed loop on: N elements allowed, the other 118−N treated as absent`; with the loop on but no element marked, it says "equivalent to searching the whole library" so users do not think they are filtering |
| Button "Fill light elements" | O / C / H / N / S → "contains". EDX/EDS routinely misses light elements, while oxides / carbonates / hydroxides are very common in hydrated and weathered samples — omitting them excludes the whole class |

The summary row now colours by the four-state grouping (must-have / contains / possible /
absent, same colour source as the buttons) and truncates beyond 12 elements with an ellipsis.

#### ⑥ Terminology unified

`必含 → 必有` ("must contain" → "must-have"), `排除 → 没有` ("exclude" → "absent") — consistent
with PolyXRD and with "contains / possible" as one vocabulary. Applied to periodic-table
tooltips, the summary row, dialog hints, main-window feature hints and the `main_window`
"restraints" description.

#### ⑦ Phase identification defaults to FPFM full-profile fitting (user request)

`DEFAULT_SEARCH_MODE = SEARCH_MODE_FPFM_FULL`. The dropdown **option order is unchanged**
("peak-list FoM" stays item 0); the default is selected via `findData(DEFAULT_SEARCH_MODE)`,
not via the implicit assumption "item 0 happens to be the default". Users can switch back to
peak search in one click at any time.

There is one **interaction that must be visible**: the FPFM search chain
(`core/search/fpfm.py`) has no `restraints` parameter, so the four element states / closed
loop never reach the pre-filter — setting "sample elements" has no effect there. Once FPFM
becomes the default, that combination becomes routine, so the toolbar "Sample elements"
button gains a permanent suffix `｜not effective under FPFM` when **constraints + FPFM** are
both active (no modal dialog — following "persistent state + non-blocking hint"); the suffix
disappears when switching back to peak-list FoM. The existing 8-second status-bar notice
during search is kept.

> ⚠️ Therefore: **to use element constraints as a chemical prior, switch the toolbar
> dropdown back to "peak-list FoM (peak search)" first**. This is a structural limitation of
> the FPFM chain, not a UI bug; this release does not touch the FPFM kernel.

### 4. Traps hit

1. **`min-width` applies to the content rectangle, while border width differs per state.**
   The old code used a uniform 2 px border, so `min_w = cell_w − 2·2` happened to hold;
   with 1/2/3 px borders the same `min_w` makes the "unrestricted" cell's `minimumSize()`
   4 px smaller than its `setFixedSize()` — as soon as the layout recomputes, the cell
   shrinks and the symbol is clipped. Fix: subtract **this state's** border width
   (`min_w = cell_w − 2·border`), which is what QSS min-* actually means.

2. **"Must-have satisfied ⇒ drop contains" must live at the conversion point**, not only in
   `passes_elements`. The pre-filter intersects `elements_allowed` with `elements_any`;
   relaxing it in a single predicate still gets ANDed end-to-end, and the user sees "I marked
   O as must-have, yet the phase containing only O disappeared". Regression test:
   `test_must_have_suppresses_the_any_of_filter`.

3. **Unknown elements in `elements_any` must be "skipped", not "clear"** — the opposite of
   `elements_allowed`, which must return all-`False` for an element absent from the library
   (it cannot be satisfied). In `elements_any` an unknown symbol simply **has no vote**
   (it cannot be guaranteed). Invert this and a single typo silently empties the result.

4. **`Restraints.elements` is a dict, so the overlap-priority rule is unreachable.**
   PolyXRD's flat-list API needs "must-have > contains > possible > absent" deduplication;
   here an element has exactly one state (`set_element` overwrites), so copying the
   deduplication would only add a dead branch with no test coverage. Documented the
   difference in the docstring instead.

5. **The complement form and the closed-loop form are equivalent, but not bit-identical
   everywhere.** The only difference is a degenerate phase with an **empty element set**: the
   closed-loop form additionally requires at least one allowed-pool hit, the complement form
   does not. No zero-element phase exists in real libraries, so the two are equivalent for
   search purposes (PolyXRD's `test_empty_elements_phase_excluded_when_closed` sides with the
   closed-loop form). The complement form is kept because the CLI `--sample-elements` shares
   it; both paths are pinned by `test_closed_world_equals_the_complement_restraint`.

6. **A stale `lastfailed` cache misleads.** `.pytest_cache/v/cache/lastfailed` still holds
   entries from the old directory layout (`tests/ui/test_smpf_kalpha2.py` and friends no
   longer exist), so `--lf` only selects the ones that still do. Judge green by counting
   progress-line characters plus a `--collect-only` reconciliation, never by that file.

### 5. Verification

| Item | Result |
|---|---|
| `ruff check .` | All checks passed! |
| `mypy xinmatch/core` | Success: no issues found in 99 source files |
| `tests/test_version_consistency.py` | 5 passed |
| Full regression | **1867 = 1862 passed / 4 skipped / 1 xfailed / 0 F / 0 E** (baseline 1809 + 55 four-state + 3 default-mode), `--collect-only` sums to **1867**, reconciled exactly |

`exit code` can still be 1: when pytest cleans up the `pytest-of-Administrator` temp
directory (>50 files) on exit, the sandbox hook refuses the delete and prints a
`[safe-delete]…` JSON line — that is hook output, not a test failure; judge green by counting
progress-line characters. **Note**: that hook truncates pytest's summary section after
`[100%]`, so with `-q` the `=== FAILURES ===` block and the final statistics line may never
reach disk — failures must be located by counting `F` / `E` in the progress line (then
re-run the single file).

58 new test cases:

| File | Count | Content |
|---|---|---|
| `tests/model/test_element_filter_four_state.py` | 25 | PolyXRD's 11 semantic assertions + the conversion point + serialization compatibility + equivalence with the complement form |
| `tests/db/test_prescreen_element_any.py` | 17 | `element_union_filter` semantics, unknown-element direction, pre-filter intersection, `HAS`/`MAYBE`/closed-loop end to end |
| `tests/ui/test_periodic_table.py` | +10 | five-state cycle, tooltip over the whole cycle, four-state visual separability, legend, `grouped`, fill light elements, closed-loop switch and hints |
| `tests/ui/test_element_restraints.py` | +3 | closed-loop switch reaches `Restraints`, quick entry does not accidentally enable the loop |
| `tests/ui/test_search_mode.py` | +3 | FPFM is the default and the dropdown selection agrees, consistent across windows, one-click switch back to FoM, persistent hint under FPFM with constraints (and it disappears on switching back) |

### 6. Key design decisions

* **No new "element constraint engine".** The pre-filter already had `elements_allowed` /
  `elements_excluded`; the four states only need one more channel, `elements_any`, and the
  closed loop reuses `elements_excluded` via the complement. The core change is "one more OR
  channel + one conversion point", not a rewritten search chain.
* **`OPTIONAL` and `MAYBE` are two states, not synonyms.** In the open world neither imposes
  a hard condition (both contribute only a weak +0.1 bonus); once the closed loop is on,
  `MAYBE` joins the allowed pool while `OPTIONAL` is treated as "absent". That is exactly
  PolyXRD's `NONE` / `MAYBE` distinction, and the reason "allow only detected elements" can
  be expressed with a single switch.
* **The closed loop is off by default.** On by default would turn every existing user's
  "mark one must-have" into "allow only that one element", emptying the candidate list. Off by
  default plus a permanent panel hint is the acceptable migration path.
* **Changing the default search mode to FPFM is a UI-default change, not a kernel change.**
  Neither search chain is touched; the default is expressed as an explicit constant selected
  via `findData()` instead of quietly reordering options, so existing tests that switch by
  index and users' existing habits both keep working.
* **"FPFM does not consume element constraints" must be permanently visible.** With FPFM as
  the default, "I set sample elements and nothing happened" goes from edge case to routine;
  a toolbar-button suffix is used rather than a modal dialog or a single 8-second status-bar
  message.
* **The closed-loop switch does not live in a dialog.** It decides the search scope, not the
  state of any element; it sits on the panel at the same level as "enable element filtering".

### 7. Upgrade notes

* Old `.xinm` archives / YAML containing `{"red","yellow","green"}` load as before; new
  archives write one extra `closed_world` key (older versions ignore it, so opening still
  works).
* What the UI used to call "must contain / exclude" is now "must-have / absent" —
  **semantics unchanged**.
* **After Open, clicking Search-Match now runs FPFM full-profile fitting** (no peak search,
  peak list untouched). If your workflow depends on the peak list or on element constraints,
  switch the toolbar dropdown back to "peak-list FoM (peak search)" first — the "Sample
  elements" button will show `｜not effective under FPFM` while constraints are set.
* To reproduce v3.6.2 behaviour: write no `HAS` / `MAYBE` and leave the closed loop off —
  bit-for-bit identical.
