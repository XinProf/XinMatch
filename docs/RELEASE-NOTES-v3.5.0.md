## XinMatch v3.5.0 — "Must not contain" element constraint made effective; single source of truth for the version

> Baseline `v3.4.0` (commit `c39e3b0`). This is a **defect-closure + engineering-governance**
> release. Reference-library format, FoM weights, P-value definitions and the command-line
> interface are all unchanged; **default search behaviour is unchanged item by item**
> (synthetic baseline 11/13 · 12/13 · 10/13 · 19/24 re-verified).

### 1. Problem to solve

Three items: the first two are "the UI says it exists but it doesn't", the third is "one
number written four times".

1. **The red branch of the three-state element constraint never took effect.** The periodic
   table could mark an element red and the summary showed "exclude: Bi", yet from 1.x through
   3.4 `ElementState.EXCLUDE` had **zero references across the whole repository**: the search
   entry point `main_window._do_search` did not pass `restraints` to `search_match`, and the
   pre-filter had no such channel. Users believed "no Bi in the sample" was in effect when
   nothing happened — the `3-2` `Bi-Y-O` false card in benchmark report §11.5 (pos 0.984,
   more accurate than the real CaF₂ at 0.928) could only be removed by eye.
2. **The version number was written in four places and drifted.** `pyproject.toml` said 3.4.1,
   `__init__._FALLBACK_VERSION` said 3.4.0 (**this is what a frozen exe reports**),
   `xinmatch.spec` said 3.4.0, and `xinmatch_setup.iss` had 10 occurrences of 3.4.0. The
   consequence is not cosmetic: the exe's About says 3.4.0, running from source says 3.4.1,
   and the installer filename is fixed as `XinMatch-Setup-3.4.0.exe`, so version numbers in bug
   reports do not match the tag. Every release relied on a manual checklist ("change all 11
   places together") written out item by item in `docs/ACCEPTANCE-*.md`.
3. **P1 "continuous pre-filter ranking" needed a verdict.** §14.5 judged that "the binary
   main-peak criterion carries too little information; switch to intensity-weighted coverage",
   and that direction had never been verified.

### 2. Core capabilities

| Capability | Description |
|---|---|
| **Element "must not contain" constraint** | Red elements in the periodic table now really participate in search: the pre-filter removes phases containing them via the `element_inv` inverted index, intersected with "must contain" (green) |
| Three entry points agree | GUI (Restraints panel), `search_match(restraints=...)` and `search_match_v3(elements_excluded=...)` share one path |
| Opposite semantics for unknown elements | A misspelled symbol empties the result in the "must contain" direction (the constraint cannot be satisfied) but **excludes nothing** in the "must not contain" direction (cannot possibly contain ≠ cannot possibly satisfy) |
| FPFM mode stated explicitly | The full-profile chain has no `restraints` parameter; with elements selected and FPFM active the status bar says so instead of failing silently |
| **Single source of truth for the version** | `pyproject.toml` only; the spec derives from it, and iss keeps one default overridden by the build script's `ISCC /DAppVersion=` |
| Version consistency tests | 5 checks (pyproject / `_FALLBACK_VERSION` / iss default / no other literals in iss / spec must not hard-code); any drift fails the test |
| Build self-check | `tools/build_exe.ps1` reads the exe's `FileVersion` after building and compares it with the target; new `-Installer` produces the installer in one command |

### 3. Key design decisions (and why)

1. **Exclusion goes through the `element_inv` inverted index, not `entries.elem_mask`**
   The mask is a single signed 64-bit integer **truncated to 63 bits at build time**
   (`_MAX_STORABLE_MASK`). Phases containing W, Pb, Bi, U, Ta, Au, Pt, Gd and friends — 27 % of
   the library — fall outside bit 63, so filtering by mask silently misses them.
   `element_index()` already switched to the inverted index for this reason; exclusion follows
   the same route.

2. **Unknown elements return all-`True` in the exclusion direction**
   Deliberately the opposite of "must contain". "Must contain La" with no La in the library →
   the result must be empty (the constraint cannot be satisfied); "must not contain Zz" with no
   Zz in the library → nothing should be excluded. Treating both the same way turns a typo into
   "search returns nothing", the hardest failure to diagnose.

3. **The GUI must read panel state on the GUI thread**
   `_do_search` runs on a worker thread, and calling `PeriodicTablePanel.states()` from the
   worker is cross-thread QWidget access that crashes randomly on Windows. So
   `_current_restraints()` takes a snapshot inside `_run_search_match` (GUI thread) and passes
   the immutable `Restraints` into the thread.

4. **Pre-filter ordering made a switch, default unchanged**
   Measured with the last two keys swapped (hit count promoted): real patterns Top-1 10/12 →
   **11/12**, card-level phase recall 19/43 → **23/43** (family-level 25/43), but synthetic
   Top-1 11/13 → 8/13 and sequential 10/13 → 5/13. The root cause is that the rulers are not
   same-source: the synthetic patterns are inverted from the same in-library reference
   intensities, so intensity-shape criteria win by construction. "Top-1/Top-5 must not
   regress" is a hard acceptance rule, and two rulers disagreeing is a product decision, so it
   became `XinDBReader(prescreen_order="intensity"|"hits")` with **`"intensity"` still the
   default**. See benchmark report §16.

5. **Falsified an old recommendation along the way**
   §14.5 recommended continuous quantities such as "intensity-weighted coverage". Measured
   in-pool recall (800 slots / 67 truth phases): `2·main_hit+hit-rate` 50/67, `+0.3·whits`
   49/67, dropping the main-peak gate 41/67 — all below "binary gate + hit count" at 51/67.
   **The gate is payload, not a defect**: "is my strongest line a strong peak of the sample?"
   is precisely the single strongest discriminating feature in multi-phase patterns.

6. **The version no longer relies on a checklist but on mechanism**
   The spec derives from `pyproject.toml` (the existing guard comparing `_FALLBACK_VERSION`
   still applies), iss keeps a single `#ifndef AppVersion` default with everything else using
   `{#AppVersion}`, the build script injects `/DAppVersion=`, and
   `tests/test_version_consistency.py` turns "the three places must match verbatim" into a
   test. The next bump therefore touches 2 files (pyproject + `_FALLBACK_VERSION`) instead of
   11 checklist entries.

### 4. Data-side corrections shipped with this release

These changed library content, not code behaviour, and were already live in the 3.4.1 library
files; recorded here with 3.5.0:

| Item | Content | Verification |
|---|---|---|
| 417 empty-formula cards in COD-Inorg | Symmetry-expanded sites → formula derived with `formula_from_sites`; in-place patch touching metadata only | Four-step equivalence proof: full re-parse diff / guarded write / `validate_xindb` + per-chunk hashes + sampled rebuild / post-write diff zero |
| 440 empty-formula cards in COD-Full | Same (including 4 junk formulas); empty formulas down to zero | 130 chunk hashes all equal, 48/48 sampled rebuilds byte-identical, both benchmark JSONs identical field by field |
| 57 truncated cards in PDF-2 | `X7` continuation lines no longer overwritten (`formula_lines` + narrowed `display_formula`); 57 mangled `)2` / `]n` tails fixed | E2 no-element WARN 93 → 36 (the remaining 36 are inherent to the source data — **nothing invented**); 40 chunk hashes all equal |

The 3.4.1 `same_phase` fix (empty-formula cards no longer match everything) is also inside this
release: it makes the real-pattern composition-level recall numbers **go down** and become more
truthful — the old numbers were inflated by false matches, so this is a correction of the
metric, not a loss of capability.

### 5. Verification

| Item | Result |
|---|---|
| `pytest` (full) | see §6, 0 failures |
| `ruff` | All checks passed |
| `mypy` (changed modules) | Success: no issues found |
| Synthetic benchmark (default config) | phase-level Top-1 11/13, Top-5 12/13, sequential 10/13, phase recall 19/24 — identical to 3.4.x item by item |
| Element constraint (13 real groups, ideal XRF setting) | Top-1 10/12 → 12/12; per-phase rank 21 up / 17 flat / 4 down / 1 pushed out |
| Version consistency | all 5 tests pass; both XinMatch and XinRefinement gained the same gate |
| Binary · version | all three artefacts report `3.5.0` from `--version`; the exe's `FileVersion` resource = 3.5.0 |
| Binary · bundled library | `libraries --json` lists `xindb_cod_inorg`, `available:true`, `entries:78035` |
| Binary · search | frozen exe on the real sample `3-1.txt` (207 peaks / 78k-phase library) returns a ranking in 36 s, top hit zincite (ZnO) correct |
| Binary · new feature | after `--restraints '{"elements":{"Zn":"red"}}'` all ZnO entries disappear — the constraint really works in the frozen build |
| Binary · GUI | release / internal / installed forms all survive 12 s of offscreen startup without crashing (stderr holds only offscreen-platform font and `titleBarShown` warnings) |
| Installer | `/VERYSILENT` exit code 0, 3562 files installed, `variant.txt=release`, bundled library in place; uninstall exit code 0 |
| Portable zip | `7z t` full CRC passes (3560 files / 822,198,605 → 353,751,503 B), no `-shm`/`-wal` runtime files among the entries |

Release artefacts (`dist/`):

| File | Size | SHA-256 |
|---|---|---|
| `XinMatch-Setup-3.5.0.exe` | 254,107,247 B (242.3 MiB) | `e81ab39f97ec9322db8bf68de18831bb02ce14b3f77e6b8eb23d460d159f9ba7` |
| `XinMatch-Internal-3.5.0.zip` | 353,751,503 B (337.4 MiB) | `41ac3005ea17af5f4af2538ea285a5bbc69932ae9c456985cd5e63cce295b40b` |

> Inside the portable zip, `XinMatch.exe` / `_internal/` / `data/` sit at the root (no wrapper
> directory), consistent with 3.3/3.4. Packaging explicitly excludes `*.xinDB-shm` /
> `*.xinDB-wal` — those are SQLite runtime temporaries, and shipping them makes the first
> launch show meaningless "library in use" warnings.

### 6. Upgrade notes

* **Default behaviour unchanged**: users who never touch the Restraints panel get
  bit-identical search results to 3.4.x.
* To make red elements effective, tick elements on the Restraints tab, set their state to red,
  then run Search-Match (peak-list FoM mode only; FPFM says it is not involved).
* The installer filename becomes `XinMatch-Setup-3.5.0.exe`; existing `data\*.xinDB` reference
  libraries carry over directly.
* To try the new ranking: `XinDBReader(path, prescreen_order="hits")`, or write a script to
  compare — note that it moves synthetic and real patterns in opposite directions (report §16.3).

### 7. Reproduction

```bash
# synthetic / real benchmarks (default config)
python -m tools.bench_pattern_set  --patterns D:\Project\XRD\test_xrd\synthetic_v3 \
    --library <COD-Inorg.xinDB> --out .scratch/bench_syn.json
python -m tools.bench_real_samples --patterns D:\Project\XRD\test_xrd\txt \
    --library <COD-Inorg.xinDB> --out .scratch/bench_real.json

# ranking 2×2 (temporarily rewrites source, restores it afterwards)
python .scratch/_probe_ab_prescreen.py --which syn
python .scratch/_probe_ab_prescreen.py --which real

# rank changes from the "must not contain" constraint on real patterns
python .scratch/_probe_exclude_bench.py
```
