## XinMatch v3.4.0 — Export phase-analysis state (.xinm): interworking with XinRefinement 1.1.0

> Baseline `v3.3.0`. This is an **interworking** release: one new export entry, one file-format
> contract and one CIF retrieval chain. Reference-library format, FoM weights, ranking
> criterion, P-value definitions and the command line are all unchanged.

### 1. Problem to solve

Once a search is finished, the conclusion lives only inside XinMatch. To run a full-profile
refinement in XinRefinement you had to do three things by hand: re-import the pattern, look up
the CIF of every identified phase, and remember the wavelength.

The second one is the killer. The COD archive is 520 thousand files spread across an id-based
directory hierarchy (`COD/9/00/82/9008220.cif`), while the library stores only the ref_id
`96-900-8220` — no path, no content. Users either dig through directories from experience or
download entry by entry from the website; both ways can attach the wrong phase, and a
refinement with the wrong phase **still converges** — it just reports an inflated Rwp and
produces a meaningless quantification.

### 2. Core capabilities

| Capability | Description |
|---|---|
| **Export phase analysis (.xinm)** | New File-menu entry; packs the anchor pattern + the selected phases' CIFs + the peak table + metadata in one go, for XinRefinement's "Import XinMatch phase analysis" to load in one click |
| Container format | zip: `manifest.json` + `pattern/pattern.csv` + `cifs/*.cif`; `format:"xinm"` / `version:1`, fields are only added, never removed |
| Pattern normalization | Two-column CSV (`two_theta,intensity`) with `%.10g` — float64 round-trips within 1e-9 relative error, ~2 MB for 100k points |
| CIF retrieval bridge | `96-900-8220` → COD id `9008220` → `{id[0]}/{id[1:3]}/{id[3:5]}/{id:07d}.cif`; probed root by root in the order "environment variable → current archive root → legacy root" |
| Degrade without blocking | If one phase's CIF cannot be retrieved, that phase gets `structural=false` plus a `reason` string and the export still completes; the refinement side lists it as "reference only", with CIF attachable manually |
| Copyright boundary | **No ICDD/PDF-2 derived data file is ever packed**; `source="pdf2"` writes only the id and peak-table metadata (the same principle as DB Manager's "please confirm you hold a genuine licence") |
| Candidate summary | The first 20 unselected candidates carry only name / entry_id / source, with no embedded CIF (to control size), so the refinement side can suggest "more phases could be added" |

### 3. Key design decisions (and why)

1. **A zip container rather than a single JSON**
   A 100k-point pattern as a float list in JSON is 4 MB+ and slow to parse; CSV is about 2 MB
   and streams. CIFs are text, so storing them as zip members keyed by name saves 33 % versus
   base64 in JSON and keeps the manifest clean.

2. **No new `xinm_cif_bridge.py`; reuse `core/refine/cif_store.py`**
   The plan listed a separate bridge module. In practice `cif_store` already had the complete
   chain (used by the structure viewer): ref_id → COD id → archive path. Another layer would
   duplicate it and risk two layout conventions drifting apart. All it needed this round was
   **multi-root probing** (see item 5).

3. **`%.10g`, not `%.6g`**
   The draft plan said `%.6g`. Measured: `%.6g` cannot round-trip float64 (relative error around
   1e-7), and pattern round-trips feed baseline subtraction and residual computation, so four
   extra significant digits are worth it. At `%.10g`, 100k points still take < 3 MB and
   round-trip bit-exactly.

4. **Judge only "can the CIF be obtained", not "should it be given"**
   The export side performs no structural sanity checks (atom coordinates present, occupancies
   summing to 1) — that belongs to import on the refinement side. Export answers exactly one
   question: is this entry's CIF present in the local archive? If yes, pack it; if no, flag it.

5. **Probe multiple archive roots instead of hard-coding one path**
   `DEFAULT_COD_ROOT` was hard-coded to `PolyXRD\cod\cif`, which no longer exists after the
   machine migration (the archive now lives at `sync-COD\COD`). Hard-coding made "every CIF
   retrieval failed" look like "the database is broken". Now the first existing directory in
   the order `XINMATCH_COD_ROOT` → current root → legacy root is used, trying each in turn.

6. **Scan range and step normalized on the export side**
   Pattern metadata often lacks `tmin/tmax`, and `step` carries floating-point tails like
   `0.019999999999999574`. Export always backfills the real first/last 2θ (6 decimals) and
   applies `round(step, 6)` — downstream writes these into the canvas and the report header, and
   a field named in the contract should hold a clean value rather than `null` and float noise.

### 4. UI

* Menu: `File → Export Phase Analysis (.xinm)…` (after Export Report, above the separator).
* Pre-checks: no pattern → "no experimental diffraction pattern loaded yet"; no selected
  candidate → "run Search-Match and select phases first".
* Completion message: `Exported N phases (M with structural CIF), pattern P points → analysis.xinm`.
* A failed CIF retrieval raises no error and interrupts nothing — the count is simply smaller
  than the phase count, and the per-phase status is recorded in the manifest.

### 5. Compatibility

| Item | Status |
|---|---|
| Reference-library format (`.xinDB` schema v3) | unchanged; v3.3.0 libraries work directly |
| FoM weights / ranking / P-value definitions | unchanged; search results identical to v3.3.0 item by item |
| Command line / config file | unchanged, no new subcommands |
| Registration mechanism / dual variants | unchanged (release registers, internal shows the red badge) |
| New artefact | `.xinm`, a standalone file that does not affect existing projects or reports |

### 6. Verification

* Unit tests: `tests/io/test_xinm.py`, 6 items — manifest fields, CSV round-trip, no-candidate
  summary, unparsable-id degradation, no-pattern error, and **a real-archive anchor**
  (`96-900-8220` anatase hit).
* Full suite: **1494 items, 1489 passed / 5 skipped / 0 failed**.
* Real-sample interworking (`test_xrd/txt/5-1.txt` calcite with COD `96-210-0189`): export
  5751 points / 1 CIF / 23.3 KB → XinRefinement's `read_xinm` reads back 5751 points, 1 phase
  with structure, CIF 3,580 B, `app.version=3.4.0`.
* Cross-repository: XinRefinement's `tests/test_xinm_import.py` calls this repository's
  exporter directly for a round-trip; the S1 end-to-end "export → import → refine" gives Rwp
  **3.409617019598457**, bit-identical to importing the same pattern/CIF manually, and still
  reproducible after saving `.xinr` and deleting the source pattern and `.xinm`.

### 7. Release artefacts

| Attachment | Bytes | SHA-256 |
|---|---:|---|
| `XinMatch-Setup-3.4.0.exe` | 254,139,154 | `4962defa7d0e4cf702db200c0b3366243b7ea09f95fafe4d7a39fab7ef0c7f19` |
| `XinMatch-Internal-3.4.0.zip` | 368,486,794 | `fb82ce897bf4227aa79420fce3359772001809ee274be64f356ace9aa7ff3a08` |
| `SHA256SUMS.txt` | — | manifest of the two hashes above |

Both binaries bundle `COD-Inorg-20261020.xinDB` (113 MiB / 78,035 phases), so search works
right after unzipping or installing; larger extended libraries are still mounted from
[`XinMatch-DataBase`](https://github.com/PolyXRD/XinMatch-DataBase).
The counterpart that imports `.xinm` is **XinRefinement 1.1.0**; the two versions must be
released as a pair.

### 8. Binary robustness acceptance (5 rounds, all passed)

`tools/verify_binary.py` was run against the **actually shipped artefacts**; raw results in
`.scratch/binary_verify_340.json` (`all_pass=true`):

| # | Check | Measured result |
|---|---|---|
| 1 | SHA-256 consistency | hash → write `SHA256SUMS.txt` → parse back and re-hash to compare: matches ✅ |
| 2 | Portable startup | extract exit 0 → `variant.txt=internal`, bundled `COD-Inorg-20261020.xinDB` 118,640,640 B / 78,035 phases, bundled `logo_256.png` byte-identical to source; `libraries --json` and `import --help` both exit 0 ✅ |
| 3 | Frozen GUI smoke | `REG` → `variant=internal, registration_enabled=false, internal evaluation build`; `LIBS` → 10 library records; `ABOUT` → About dialog rendered to PNG ✅ |
| 4 | Silent install | `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CURRENTUSER` → exit 0, `XinMatch.exe` + `data\COD-Inorg-20261020.xinDB` installed, `variant.txt=release` ✅ |
| 5 | Post-install startup | frozen CLI in the install dir `libraries --json` exit 0; real-pattern end-to-end `5-1.txt` → 118 peaks / 5 candidates / top `96-210-0189` (calcite, same as v3.3.0); release GUI hook `variant=release, registration_enabled=true, unregistered` ✅ |

This round also fixed a **version-display defect** (present since v3.3.0, outside the joint
plan but polluting `.xinm`'s `app.version`): a frozen bundle has no `pyproject.toml`, while the
development machine's `site-packages` retains `xinmatch-1.7.1.dist-info`, so
`importlib.metadata` took that as the real version and both the About dialog and the `.xinm`
manifest said 1.7.1. Frozen builds now return `__init__._FALLBACK_VERSION` directly, and
`xinmatch.spec` asserts at build time that it equals `APP_VERSION` (build fails otherwise);
the CLI also gained `--version` / `-V` (previously `--version` opened the GUI).

A manual double-click acceptance by the user is still recommended (automation covers only the
offscreen path).
