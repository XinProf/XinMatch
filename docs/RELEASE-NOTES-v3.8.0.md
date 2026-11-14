# XinMatch v3.8.0 — Release Notes

**Release date**: 2026-11-14
**Type**: search-match benchmarking and diagnostics (**no change to default search results,
no change to the library or project file formats**)

## Changes

### A fourth benchmark ruler on measured multi-phase patterns

`tools/bench_shijk.py` adds a fourth, independent ruler built from seven MAUD refinement
projects — real measured patterns, not synthetic ones. The ground truth is **33 crystalline
phases across 7 samples** (5/4/5/5/5/4/5). Four samples also contain amorphous material;
amorphous phases have no reference card and are therefore excluded from the denominator
rather than counted as misses.

- Entry-level truth is derived from the numbering in the exported CIF files (the seven-digit
  number minus one, then reassembled as the local `96-XXX-XXXX` id). `--verify-truth`
  matches **33/33** phases against the bundled library. Using the file-number directly
  silently resolves to a different phase, so the conversion is pinned by a unit test.
- Phase-level equality uses **element set + unit cell (1.2% / 1.5 deg)** and deliberately
  ignores space group: the library carries quartz cards in both `P 32 2 1` and `P 31 2 1`,
  and comparing space groups would report a correct hit as a miss.
- 13 metrics are reported together: entry / phase Top-1/3/5/10/20, six-round sequential
  identification, and sample-level Top-1. `--baseline` prints per-metric up / down / flat
  deltas. Baselines `docs/bench/shijk-20261113.json` (default pool) and
  `shijk-20261113-pool20000.json` are committed; the ruler is **not** merged into the
  existing three-ruler 26-metric summary because the denominators differ.

Default-path results: entry Top-1 0/33, Top-20 8/33; phase Top-1 6/33, Top-20 9/33;
sequential 16/33; sample Top-1 (phase level) 6/7.

### Prescreen pool cap and a default-off adaptive pool

- `search_match(..., candidate_limit=...)` exposes the v3 prescreen pool cap. `None` keeps
  the built-in 1000 and is **bit-identical** to previous releases. On the ShiJK ruler an
  explicit 20000 pool lifts phase-level Top-20 from 9/33 to 15/33, at a cost of roughly
  0.5 s → 5.3 s per search. The GUI does not expose the knob: it is an explicit
  recall / latency trade-off.
- `adaptive_pool` re-runs with the wider pool only when the FoM head is flat
  (Top-1 minus Top-10 below 0.04). A/B ruled it out as a default: the three rulers gave
  **7 up / 2 down / 18 flat**, ShiJK gave **9 up / 1 down / 3 flat** with the single drop
  in sequential identification (16/33 → 14/33), and latency rose 5–10x. The synthetic
  pattern whose gap overlaps the ShiJK range makes the threshold structurally
  non-separable. The switch stays available but is off by default.
- `--seq-candidate-limit` is a separate knob so the historical baselines remain
  reproducible: pushing `--candidate-limit` into sequential search was measured to drop
  sequential hits from 16/33 to 14/33, so the two paths stay independent.

### Element restraints: the first one-directional gain

`--oracle-elements` runs the ruler in an "element set known" upper-bound mode. The allowed
set is the union of the CIF element sets of all ground-truth phases for that sample; every
other element is marked EXCLUDE through the same complement-restraint path used by the IUCr
ruler. Restraints are applied to both whole-pattern and sequential search.

| Run | Elements | Whole pool | Seq pool | 13 metrics | Phase Top-20 | Seq | Sample Top-1 | Time |
|---|---|---|---|---|---|---|---|---|
| Control | none | 1000 | 1000 | 0 up / 0 down / 13 flat | 9/33 | 16/33 | 6/7 | 20 s |
| **Upper bound** | oracle | 1000 | 1000 | **10 up / 0 down / 3 flat** | **15/33** | **25/33** | **7/7** | **17 s** |
| Upper bound + wide pool | oracle | 20000 | 1000 | identical, metric by metric | 15/33 | 25/33 | 7/7 | 19 s |
| + wide sequential pool | oracle | 20000 | 20000 | only `seq −1` | 15/33 | 24/33 | 7/7 | 27 s |

This is the **first one-directional, zero-drop improvement across all four rulers**, with
no extra runtime. The mechanism is not a smaller candidate pool: direct measurement shows
**6/7 samples still fill all 1000 prescreen slots and still report `truncated=True`**.
The complement restraints keep chemically impossible dense cards out, so the same 1000
slots go to chemically plausible cards and the true phases can reach scoring. Widening the
pool and purging it are redundant — the third run is identical to the second.

Input sensitivity (monkeypatched allowed sets, same 13 metrics):

| Element input | Phase Top-20 | Sequential |
|---|---:|---:|
| No restraints (baseline) | 9 | 16 |
| Exact upper bound | 15 | 25 |
| Missing H | 14 | 21 |
| Missing H, C | 10 | 15 |
| Missing H, C, F | 9 | **13 (worse than no restraints)** |
| Extra Na, Cl, S, Ba, Zn | 14 | **26** |

Over-reporting elements is almost harmless; **under-reporting light elements destroys the
gain quickly and can end up worse than applying no restraints at all**. Any product UI for
element entry must therefore be over-inclusive by default: H/C/N/F/Li (hard or impossible
for XRF) should default to MAYBE or be allowed outright, never to a closed-world
"unchecked = absent" hard exclusion. A loose / strict pair of modes with an explicit
warning about missing light elements is the intended shape.

**15/33 and 25/33 are upper bounds, not shipped metrics** — real element sets come from
XRF/EDS or a known formulation, never from the answer. Quantifying that realistic input is
the next step.

### Ruled-out directions (documented, no production change)

Prescreen ordering by normalised hit count (§42), the adaptive pool (§43), four alternative
`p_npeaks` estimators scored by offline re-ranking of the entire pool (§44), and a wide
pool in sequential search (§45) were all measured and rejected. The `p_npeaks` diagnostic
confirmed the systematic penalty on minor phases (true cards 0.261 vs false cards 0.289,
lower in 6/6 samples) but the weighted contribution differs by only ~0.006 — not enough to
flip the ranking. **Single-point tuning of the retrieval and scoring layers is now closed**;
chemical information is the only lever with a measured one-directional gain.

### Other fixes

- `userdb` was missing from the static CLI fallback set in `tools/pyi_entry.py`. A frozen
  build whose parser import fails could route `XinMatch.exe userdb ...` to the GUI instead
  of the CLI. A dedicated regression test now pins the full subcommand list.
- Release documentation is now English by default (README, README-CN, CHANGELOG, all
  `RELEASE-NOTES-*.md`, GitHub Release text and commit messages). Internal documents
  (`docs/STATUS.md`, the benchmark report, work logs) stay in Chinese.

## Compatibility

- `.xinDB`, `.xinm` and `config.yaml` formats are **unchanged**; existing libraries and
  project archives keep working as-is.
- **Default search behaviour is unchanged**: with `candidate_limit=None` and
  `adaptive_pool=None` the default ruler run is **13/13 flat** against the historical
  baseline, and the three-ruler control group is 27/27 flat. All new search knobs are
  opt-in or default-off.
- Production search code and the GUI are unchanged by the element upper bound work; the
  upper bound lives entirely in the benchmark tool.

## Assets

| File | Size | SHA-256 |
|---|---:|---|
| `XinMatch-Setup-3.8.0.exe` | 255,173,587 B (243.4 MiB) | `80b13060c4fca434d577dd00793eda13f856024d05e7bbe8ad0bcf3d12a5d58a` |

> The portable zip (`XinMatch-Portable-3.8.0.zip`, 371,703,257 B / 354.5 MiB,
> SHA-256 `e97dd289fe4a2307eba964eb0b87f551c7f88cbbeff2e8c3b18123ce2dd8825a`)
> is **built but not published** with the Release, per project convention.

## Acceptance

All 5 automated rounds passed (`tools/verify_binary.py`; report
`.scratch/binary_verify_380.json`, a process artefact that is not committed):

- **Round 1**: SHA-256 manifest read-back matches for both Setup and Portable.
- **Round 2**: portable archive extracts cleanly; the frozen CLI recognises the bundled
  library — **78,035 phases** (118,640,640 B) — with `variant=release`, and the bundled
  logo is byte-identical to the source tree.
- **Round 3**: frozen GUI three hooks (REG = release / `registration_enabled`, LIBS 7
  entries, ABOUT PNG 9,117 B) plus 3 cold starts all exiting 0.
- **Round 4**: `/VERYSILENT /CURRENTUSER` silent install succeeds with `variant=release`
  and the bundled library installed alongside.
- **Round 5**: search on a real pattern after installation (5-1, 118 peaks) returns 5
  candidates, top hit `96-210-0189`.

The build itself was run in the foreground through the whole PyInstaller + Inno Setup
chain, so the installer is complete (243.4 MiB, not the truncated intermediate that a
background build can leave behind). Per project red line #6, the installer must also pass
a **manual double-click acceptance** before the Release is promoted from draft.

## Data sources (not in Git)

The four ruler datasets live in local directories:

- Synthetic patterns: `D:\test_XRD\synthetic_v3`
- Real patterns: `D:\test_XRD\temp\smz xrd analysis`
- IUCr: `D:\test_XRD\IUCr\txt`
- ShiJK-Refinement: `D:\test_XRD\ShiJK-Refinement`

PDF-2 (ICDD copyrighted data) is **not** part of this repository or this Release.
