## XinMatch v3.3.0 — Sparse-phase marking: `★` strong-line anchoring in the candidate list

> Baseline `v3.2.0`. This is a **minor** release (one new criterion plus a UI mark).
> Reference-library format, FoM weights, P-value definitions, command line and configuration
> are **all unchanged**; ranking is identical to v3.2.0 item by item. The engine gains only a
> re-ranking switch that defaults to off and a read-only marking channel.

### 1. Problem to solve

`P(npeaks)` inside the FoM counts **lines** — how many observed peaks a candidate explains and
what fraction of all peaks that is. On the residual pattern of a multi-phase sample this
criterion inherently favours cards with many lines: an intermetallic with 40–150 reflections
can "collide" with many weak residual peaks, while the **sparse phases** that genuinely should
be identified (metallic Fe with 6 lines, NaCl with 17, KCl around 9) explain only two or three
peaks, score a low `P(npeaks)` and therefore always sit at the back.

Measured (`docs/基准报告-物相检索-v3.md` §11.3):

* the true KCl of `synth_07` **does not exist at all** in a candidate pool of depth 1000;
* metallic Fe in `synth_10` ranks **#94/1000** in round 1, with `P(2θ)` 0.998, `P(I/I₀)` 0.99
  and its strongest line landing exactly on the strongest residual peak at **1.00×**;
* NaCl in `synth_07` ranks 10 with `P(2θ)` 0.991, its strongest line likewise hitting the
  residual main peak.

In other words: these phases are entirely correct in **position** and **strongest line**; they
simply do not have enough "votes".

### 2. Core capabilities

| Capability | Description |
|---|---|
| Strong-line anchoring criterion `AnchorPolicy` | Strongest reference line hits ≥0.30× the strongest residual peak + `P(2θ)`≥0.98 + matched pairs ≥2 + `P(ncorr)`≥0.50 + reference reflections ≤20 |
| Candidate marking | `ResidualSearchResult.anchored_ids` lists the entries that pass; the first column of the candidate table shows `★` in its colour band, hovering explains the criterion, and the status bar reports "★ N entries whose strongest line hits a strong residual peak" |
| Optional re-ranking (off by default) | `search_residual(..., promote_anchored=True)` moves those candidates to the front (still FoM-descending), for offline experiments |
| Line-count guard | Candidates with more than 20 reference reflections are **never** marked — they are the dominating mechanism itself |

### 3. Key design decisions (and why)

1. **Tried scoring first, then ranking, and finally settled for marking**
   It started with changing `P(npeaks)` as the task text said: swap in observed-side intensity
   coverage, blend with the FoM, add a position gate, re-rank near-ties with ε, exclude sibling
   cards of a family, replace `ncorr` with intensity coverage too — **all eight variants scored
   ≤ the baseline 10/13** (§11.2). Conclusion: the scoring layer cannot fix this, because the
   "many and messy" false card and the "few and precise" truth are mirror images on the same
   metric. So the approach became an anchoring criterion that **does not change the score, only
   takes an extra look**.

2. **Why a line-count guard rather than "an even stronger strongest line"**
   On synthetic patterns anchoring rescues `synth_07` from 0/2 all the way to 2/2 (sequential
   10/13 → **11/13**, phase recall 19/24 → **21/24**). But without the guard, the falsely dense
   card in `synth_02` also satisfies "strongest line hits" and knocks 2/2 down to 1/2. The
   guard is set at 20 lines: Fe 6, KCl 9, NaCl 17 and CaF₂ 17 are all inside; the 40–150-line
   cards are all outside.

3. **Why no re-ranking by default (the most important decision in this release)**
   On the 12 real patterns, re-ranking lost `3-2`: round 2's top 6 were all genuine Al₂O₃, and
   anchoring lifted the 7th, `Bi1.284O2.988Y0.684`, to first place — its `P(2θ)` is **0.984**,
   **more accurate** than the real CaF₂ at 0.928, `P(ncorr)` 0.588 is sufficient, and 17
   reflections is enough too. Once mis-confirmed, the residual is polluted and CaF₂ cannot be
   recovered even after 5 rounds (it is not "one extra round"). Sequential full recovery goes
   5/12 → 4/12.
   Three variants — single-line / double-line (Hanawalt-style, both strongest lines hit) /
   double-line plus intensity ratio — give **identical** values on all eight metrics, showing
   this is not a matter of threshold tuning but of the rule lacking discriminating power on
   real patterns.

   Root cause: synthetic patterns are rebuilt from the same reference intensities, so
   "reference relative intensity ↔ observed relative intensity" holds exactly; real patterns
   have no such relation, a sparse phase's `P(I/I₀)` naturally approaches 0, and anchoring can
   rely only on position and line count — where the false `3-2` card is "good" on both.
   **The synthetic ruler systematically overestimates this rule.**

   So this release demotes it to a **mark**: engine ranking is identical to v3.2.0 item by item
   (real patterns Top-1 10/12, Top-5 12/12, sequential 5/12, card recall 24/43, family-level
   27/43), and the user decides whether to look at that ★ at rank 7 — the engine does not
   decide for them.

4. **The mark takes no new column**
   `★` is drawn in the existing first column (the colour band): `DisplayRole` returns `★`,
   `ToolTipRole` explains the criterion, and the sort key becomes 1/0, so clicking the header
   groups all ★ candidates together. Column count, column order and existing shortcuts are all
   unchanged.

### 4. UI

* Candidate list: rows that pass strong-line anchoring show `★` in the first column's colour
  band (coexisting with the confirmed-phase colour); the tooltip reads "the strongest reference
  line lands on a strong residual peak, position accuracy is high and its own reflections
  explain more than half… worth a look even when ranked low — check the reference lines before
  confirming".
* Status bar: the residual-search completion message gains "★ N entries whose strongest line
  hits a strong residual peak (sparse phases — worth checking even when ranked low)".
* Full-pattern search (non-sequential) produces no marks; behaviour is exactly v3.2.0.

### 5. Compatibility

* No new dependencies, no schema change; `.xinDB` libraries work as-is.
* `search_residual()` gains keyword arguments `promote_anchored` (default `False`) and
  `anchor_policy` (default `None` = `DEFAULT_ANCHOR_POLICY`); neither is **ever** forwarded to
  `search_match`, so the `kwargs` seen by a custom `search_fn` are byte-identical to before.
* `ResidualSearchResult` gains the field `anchored_ids` (empty list by default); old construction
  patterns are unaffected.
* `CandidateListTable.set_candidates()` / `MainWindow.set_candidates()` gain the keyword
  argument `anchored_ids` (default `None` = no marking). Positional signatures unchanged.
* `xinmatch.core.search.sequential` now also exports: `AnchorPolicy`, `DEFAULT_ANCHOR_POLICY`,
  `DEFAULT_ANCHOR_ALPHA` / `_PEAKPOS` / `_MIN_PAIRS` / `_MIN_NCORR` / `_MAX_REFLECTIONS`.

### 6. Verification

* Static gates: `ruff check xinmatch tests` all pass; `mypy xinmatch` 121 files
  `Success: no issues found`.
* Full `pytest` (`addopts` excludes `slow` by default): **1488 items / 1483 passed / 4 skipped /
  1 xfailed / 0 failed** (15m27s).
* Benchmarks (COD-Inorg, 78,035 phases) — **default configuration identical to v3.2.0 item by
  item**:

  | Criterion | v3.2.0 | v3.3.0 default | v3.3.0 `promote_anchored=True` |
  |---|---:|---:|---:|
  | Synthetic `synthetic_v3` sequential full recovery (phase level) | 10/13 | 10/13 | **11/13** |
  | Synthetic `synthetic_v3` sequential phase recall | 19/24 | 19/24 | **21/24** |
  | Real 12 groups full-pattern Top-1 / Top-5 | 10/12 · 12/12 | 10/12 · 12/12 | 10/12 · 12/12 |
  | Real 12 groups card recall / family-level recall | 24/43 · 27/43 | 24/43 · 27/43 | 24/43 · 27/43 |
  | Real 12 groups sequential full recovery (3 rounds) | 5/12 | 5/12 | 4/12 |
  | Real 12 groups sequential full recovery (5 rounds) | 6/12 | 6/12 | 5/12 |
  | Real 12 groups in-sequential phase recall | 23/43 | 23/43 | 22/43 |

  The synthetic gain is 100 % from `synth_07` (NaCl lifted from rank 10 to first, `0/2 → 2/2`);
  the real loss is 100 % from `3-2` (the false Bi-Y-O card takes the slot, CaF₂ is lost). That
  is the entire reason it is off by default; data and diagnosis in
  `docs/基准报告-物相检索-v3.md` §11.5.

* New tests: `tests/search/test_sequential.py` +9 (no re-ranking by default but still marked,
  the re-ranking switch, dense cards not marked, each of the `ncorr` / position / anchor-intensity
  criteria able to veto, a single pair is not evidence, `pairs=[]` / `p_values={}` do not crash,
  `pairs` still map back to the original peak indices after re-ranking);
  `tests/ui/test_tables.py` +2 (★ mark and tooltip, the mark restored when a folded variant
  expands); `tests/ui/test_sequential_ui.py` +1 (residual results carrying `anchored_ids` →
  candidate-table mark + status-bar hint).

### 7. Release artefacts

| Attachment | Bytes | SHA-256 |
|---|---:|---|
| `XinMatch-Setup-3.3.0.exe` | 254,071,430 | `6e93c548dbd09ad82dcb3a3e59c8b41218d3a9a11515e45acc62b519f9770791` |
| `XinMatch-Internal-3.3.0.zip` | 353,728,377 | `71f410fbef7eedad7dab785f0703d24af3fc7d10d0bc29d696fe7ba947c144c4` |
| `SHA256SUMS.txt` | 190 | manifest of the two hashes above |

Both binaries bundle `COD-Inorg-20261020.xinDB` (113 MiB / 78,035 phases), so search works
right after unzipping or installing; larger extended libraries are still mounted from
[`XinMatch-DataBase`](https://github.com/PolyXRD/XinMatch-DataBase).

### 8. Binary robustness acceptance (5 rounds, all passed)

`tools/verify_binary.py` was run against the **actually shipped artefacts**
(`python -m tools.verify_binary --setup … --zip … --workdir …`); raw results in
`.scratch/binary_verify_330.json`:

| # | Check | Measured result |
|---|---|---|
| 1 | SHA-256 consistency | hash → write `SHA256SUMS.txt` → parse back and re-hash to compare: matches ✅ |
| 2 | Portable startup | extract exit 0 → `variant.txt=internal`, bundled `COD-Inorg-20261020.xinDB` 118,640,640 B, bundled `logo_256.png` byte-identical to source; frozen CLI `libraries --json` (default library `entries=78035 / available=true`) and `import --help` both exit 0 ✅ |
| 3 | Frozen GUI smoke | `REG` → `variant=internal, registration_enabled=false, internal evaluation build`; `LIBS` → 10 library records; `ABOUT` → About dialog rendered to PNG (9,117 B); 3 consecutive cold starts all exit 0 ✅ |
| 4 | Silent install | `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CURRENTUSER /DIR=…` → exit 0, `XinMatch.exe` + `data\COD-Inorg-20261020.xinDB` installed, `variant.txt=release` ✅ |
| 5 | Post-install startup | frozen CLI in the install dir `libraries --json` exit 0; **real-pattern end-to-end search** `search 5-1.txt --db <installed bundled library> --top-n 5 --json` → 118 peaks / 5 candidates / top `96-210-0189` (calcite, matching the benchmark); release GUI hook `variant=release, registration_enabled=true, unregistered` ✅ |

> This round hit a **trap in the acceptance tool itself**, now fixed: when `--workdir` was given
> a relative path, rounds 3/4 passed that relative path to child processes as an environment
> variable / `/LOG=` argument (the child's cwd is the work directory), which resolved to a
> non-existent path → file writes inside the frozen GUI raised `FileNotFoundError`, Qt swallowed
> it and the event loop kept running, showing up as "self-test timeout at 120 s" plus "silent
> install rc=1" — easily misread as a broken artefact. `verify_binary.main()` now `resolve()`s
> all input paths first.

A manual double-click acceptance by the user is still recommended (automation covers only the
offscreen path).
