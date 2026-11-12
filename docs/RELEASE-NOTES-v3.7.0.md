# XinMatch v3.7.0 — Release Notes

**Release date**: 2026-11-12
**Type**: toolchain fixes + benchmark ruler restoration (**no change to the search algorithm, no change to the library format**)

## Changes

- **Synthetic-pattern ruler restored**: 13 synthetic patterns regenerated from the v3
  reference library (`COD-Inorg-20261020.xinDB`); `load_pattern` loads 13/13. Benchmark
  artefact: `docs/bench/synth-20261112.json`. Phase level: Top-1 **11/13**, Top-5 **12/13**,
  phase recall **19/24**. Entry level (strict `entry_id`): Top-1 7/13, Top-5 12/13.
- **Generator path fix**: `CARD_DB` in `tools/generate_synthetic_patterns.py` was hard-coded
  to a pre-migration absolute path and now resolves relative to the repository
  (`data/cod_inorganics.db`); the three card-lookup helpers return `None` when the library is
  missing instead of aborting the whole generation run. New
  `tests/test_synthetic_generator_paths.py` pins the path so it cannot drift again.
- **Acceptance-tool fix**: `tools/verify_binary.py` now unpacks the portable archive with the
  standard-library `zipfile` module, so it no longer requires a local 7-Zip installation.
- Version synchronized to **3.7.0** in the three places
  (`pyproject.toml` / `xinmatch/__init__.py` / `tools/xinmatch_setup.iss`); `xinmatch.spec`
  still derives it from pyproject and carries no literal.

## Compatibility

- `.xinDB` / `.xinm` / `config.yaml` formats are **unchanged** — existing libraries and
  archives keep working as-is.
- The search algorithm is untouched; candidate ranking behaves exactly as in v3.6.4.

## Assets

| File | Size | SHA-256 |
|---|---:|---|
| `XinMatch-Setup-3.7.0.exe` | 255,257,841 B (243.4 MiB) | `ea3b9225bb0f5b2de0e5b9ebafdb6455b0e8705e8ffa8f84b1d76f48aeea6565` |

> The portable zip (`XinMatch-Portable-3.7.0.zip`, 371,700,155 B / 354.5 MiB,
> SHA-256 `6d09f6707037834be40235af5c66a9b44b422aa0b1f6541e2f84fde5735c0b1b`)
> is **built but not published** with the Release, per project convention.

## Acceptance

All 5 automated acceptance rounds passed (`tools/verify_binary.py`; report
`.scratch/binary_verify_370.json`, a process artefact that is not committed):

- **Round 1**: SHA-256 manifest read-back matches (Setup / Portable).
- **Round 2**: portable archive extracts 3,682 members; the frozen CLI recognises the bundled
  library — **78,035 phases** (118,640,640 B) — with `variant=release` and the bundled logo
  byte-identical to the source tree.
- **Round 3**: frozen GUI three hooks (REG = release / `registration_enabled`, LIBS 7 entries,
  ABOUT PNG 9,117 B) plus 3 cold starts all exiting 0.
- **Round 4**: `/VERYSILENT /CURRENTUSER` silent install succeeds with `variant=release` and
  the bundled library installed alongside.
- **Round 5**: search on a real pattern after installation (5-1, 118 peaks) returns 5
  candidates, top hit `96-210-0189`.

Per project red line #6, the installer must pass a **manual double-click acceptance** before
the Release is promoted from draft.

## Data sources (not in Git)

The inputs for the three benchmark rulers live in a local data directory:

- Synthetic patterns: `D:\test_XRD\synthetic_v3`
- Real patterns: `D:\test_XRD\temp\smz xrd analysis`
- IUCr: `D:\test_XRD\IUCr\txt`

PDF-2 (ICDD copyrighted data) is **not** part of this repository or this Release.
