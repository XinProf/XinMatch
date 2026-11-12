<div align="center">
  <img src="assets/icons/logo_256.png" alt="XinMatch logo" width="200">
</div>

# XinMatch

> [Chinese (Simplified)](README-CN.md) · English

Open-source **powder X-ray diffraction (XRPD) phase analysis** platform — a
clean-room implementation guided by publicly documented XRD phase-analysis
workflows, published algorithms and open reference data (COD).

> ✅ **v3.6.3.** Core computation kernel + full GUI + dual-mode search-match
> (peak-list FoM / FPFM full-profile fitting (Full Pattern Fitting Match, formerly SMPF)) + **sequential
> multi-phase identification** (confirm a phase → re-search on the remaining
> unexplained peaks → confirm the next) + true March-Dollase preferred
> orientation modeling + GSAS-II refinement pipeline + quantitative Rietveld
> (main-phase wt% < 3 on certified samples) are complete and packaged
> (Windows installer / portable). v3.2.0 adds **phase-level identity**
> (`core/search/phase_key.py`): the candidate list folds cards that describe
> the same phase into one row (expandable, with each card's unit cell one
> hover away), and the benchmark is scored both per entry and per phase —
> same library, phase-level Top-1 goes from 7/13 to **10/13** simply because
> "found the right phase on a sibling card" is no longer counted as a miss.
> It also ships the refreshed logo/icon set and a regenerated splash.
> v3.3.0 adds **sparse-phase marks** in the residual candidate list: a card
> whose strongest reference line sits on a strong leftover peak, that is
> positionally accurate and coherent over its own reflections, is flagged
> with `★` (the FoM counts *how many* peaks a candidate explains, so a
> 6-line metal is always outvoted by a 150-reflection card). The mark is
> informational only — ranking is unchanged, because the same rule also
> flags a wrong phase on real data (see `docs/基准报告-物相检索-v3.md` §11.5).
> v3.4.0 adds **phase-analysis export** (`File → Export Phase Analysis (.xinm)…`):
> the anchor pattern, the selected phases' COD CIFs and their metadata are
> packed into a self-contained zip that the sister project
> [XinRefinement](../XinRefinement) imports in one click to start
> full-profile refinement — no re-importing the pattern, no hunting CIFs in
> the 522 K-file COD archive. Format contract: `docs/JOINT_PLAN_xinm_xinr.md`.
> v3.0.0 replaced the last legacy reference
> formats with the single **v3 columnar `.xinDB`** layout and ships the
> **COD-Inorg** library as the built-in default:
>
> * default library = `COD-Inorg-<snapshot>.xinDB`, bundled at `data/` in the
>   portable build → **works out of the box**, no separate download needed;
> * one reader, one search path (`search_match_v3`); the v2 SQLite
>   (`cod_inorganics.db`), PolyXRD-dump and PDF-2 readers were **deleted**,
>   not deprecated;
> * still mountable from any folder (Settings → Reference Database…, or
>   `xinmatch libraries --add <path>`), `.xinDB` only.
>
> **v3.6.3** reworks element constraints into **four states + a closed loop** (semantics aligned with the sister project PolyXRD; interface changes are additive-only):
> ① Element states expand from "must contain / exclude / unrestricted" to "**Must-have**" (AND), "**Contains**" (OR, at least one),
> "**Possible**" (only widens the allowed pool), "**Absent**" + unrestricted; the click order puts the most restrictive "Must-have" last;
> ② A new **closed-loop switch** "Restrict to selected elements" — elements with no assigned state are all treated as "Absent",
> so "allow only the few elements detected in the sample" no longer takes 113 clicks; ③ pre-filtering gains an `elements_any`
> path (previously only "must contain all" and "reject if any present"); the four-state translation converges into `element_constraint_sets()`
> at a single point; ④ the panel adds a "Fill light elements" one-click button that marks O/C/H/N/S as "Contains". Legacy archives and legacy workflows stay bit-for-bit unchanged
> (closed loop off by default); benchmark numbers stay put.
> ⑤ **Phase identification now defaults to FPFM whole-pattern fitting (no peak search)**; the dropdown still switches back to "peak-list FoM (peak search)" in one click.
> ⚠️ Note: the FPFM search-match chain does not accept element constraints; **to use element constraints, switch back to peak-list FoM**;
> the toolbar "Sample elements" button, when constraints + FPFM are active, permanently shows the "| not effective under FPFM" hint.
> **Download**: [GitHub Release v3.6.3](https://github.com/PolyXRD/XinMatch/releases/tag/v3.6.3)
> (Windows installer, built-in COD-Inorg default library, ready for search-match out of the box); see
> [docs/RELEASE-NOTES-v3.6.3.md](docs/RELEASE-NOTES-v3.6.3.md).
>
> **v3.6.2** changes the pattern-area interaction (no changes to the interface or data format):
> ① A new **reference-line panel** below the pattern — whichever phase is highlighted in the candidate list, its peak positions
> and intensities are drawn directly beneath the pattern (one row per phase, chemical formula on the left, x-axis linked and aligned with the pattern); confirmed phases are all listed too,
> so you can see at a glance "which peaks are not yet matched by any phase"; a checkbox toggles "angle positions only / also show intensities";
> ② The top "X axis / Y axis / Fit to data range" control bar is hidden but its functions remain, moved onto **clicking the axes**
> (left-click cycles, right-click menu); ③ a row of **quick icons** above the pattern (reset / horizontal box select / vertical box select /
> region zoom / pan left-right / step zoom / crosshair), ported from the sister project XinRefinement's implementation.
> See [docs/RELEASE-NOTES-v3.6.2.md](docs/RELEASE-NOTES-v3.6.2.md).
>
> **v3.6.1** is a pure bug-fix release fixing three field-reported issues, with no changes to the interface or data format:
> ① In the pattern legend every curve **appears twice** (pyqtgraph's `PlotItem.addItem()` already adds a legend entry,
> and the code added one manually again — there was always only 1 curve; the duplicate was the legend row);
> ② The Rietveld refinement wizard **went fully white + froze** (refinement ran the GSAS-II subprocess synchronously on the GUI thread,
> causing "(Not responding)", while the "Start refinement" button slid into the "Next" position so repeated clicks misfired),
> now moved to a background thread with the action buttons inside the page; ③ the list's "Crystal system" column **labelled hexagonal phases as monoclinic**
> (it used only the "count of non-90° angles" criterion, while the only non-right angle in a hexagonal cell is γ=120°); added `H`/`R` criteria.
> See [docs/RELEASE-NOTES-v3.6.1.md](docs/RELEASE-NOTES-v3.6.1.md).
>
> **v3.6.0** fixes the "clickable but does nothing" gap: of 15 feature modules, 11 menu actions only
> posted a "module skeleton is in place" line in the status bar, while `core.quant` / `core.micro` / `core.index`
> were already complete. Now all of them are wired to real dialogs — Profile Fitting (F5, one of four
> profile shapes + Rwp + curve overlay), RIR quantification (adiabatic method, wt% written back to the
> match list), Scherrer / Williamson-Hall microstructure (D / ε / R²), Treor90 / DicVol06 indexing
> (candidate cell table), and an aggregated data-export menu (pattern ASCII + three CSV tables + `.xinm` + CIF). Also: the candidate
> list defaults to 50 rows (family coverage 81/98 → **89/98**, at zero compute cost); peak-position refinement
> switches to LM, 207-peak preprocessing **35.2 s → 0.35 s**, CLI end-to-end **36 s → 2.3 s**; the periodic
> table is redone with new sizing and three-state encoding (no longer clipped by the global QSS). Search-match
> default behaviour is unchanged item by item; see [docs/RELEASE-NOTES-v3.6.0.md](docs/RELEASE-NOTES-v3.6.0.md).
>
> See [docs/ROADMAP_v3.md](docs/ROADMAP_v3.md) for the full implementation plan and
> [docs/STATUS.md](docs/STATUS.md) for current progress.

## What XinMatch does

- **Qualitative phase analysis** (search-match): identify crystalline phases
  from an experimental powder diffraction pattern against a reference database.
- **Sequential multi-phase identification** (v3.1.0): confirm the best phase,
  subtract what it explains, and re-search the **remaining unexplained peaks**
  for the next phase — repeat until no significant peak is left.  Each
  confirmation is reversible, and the residual status (peaks explained /
  left over / too weak to use) is shown next to the candidate list.
- **Phase-level candidate list** (v3.2.0): a reference library holds dozens of
  cards per phase, so near-identical entries used to flood the Top-N.  Cards
  now fold into one row per phase (identical unit cell / element set / space
  group, see `core/search/phase_key.py`); the "Variants" column shows how many
  cards were folded, its tooltip lists each card with its cell, and the
  context menu expands them again.
- **Sparse-phase marks** (v3.3.0): the residual search flags candidates whose
  strongest reference line sits on a strong leftover peak (`★` in the first
  column, rule in `core/search/sequential.py`).  The FoM counts *how many*
  peaks a candidate explains, so a correct 6-line metal never outvotes a
  150-reflection card; the mark makes it visible without changing the order.
- **Quantitative phase analysis** (RIR, internal standard, Rietveld).
- **Raw data preprocessing**: smoothing, background subtraction, Kα₂ stripping,
  zero-point / displacement correction.
- **Profile fitting & peak search**.
- **Rietveld / Le Bail refinement** (delegated to GSAS-II).
- **Powder indexing** (Treor / Dicvol).
- **Microstructure**: crystallite size (Scherrer), microstrain, crystallinity.
- **Reports & export**, **GUI** (PySide6), **CLI / batch scripting**.
- **Reference-database mounting**: besides the bundled `COD-Inorg` library, any
  other `.xinDB` library can be mounted from **any folder**
  (Settings → Reference Database…, or `xinmatch libraries --add <path>`). v3 libraries are
  self-contained columnar files, so nothing is copied or converted.
- **3COD libraries are split by provenance** (`tools/split_3cod.py`):
  `COD-Inorg` (experimental, 79 k), `PCOD-Inorg` (predicted, 1.06 M),
  `TCOD-Inorg` (theoretical, 47 k). Mount all three side by side in XinMatch;
  PolyXRD only ever picks up the experimental one, because the other two ship
  without a `phases` table. See
  [docs/ACCEPTANCE-3COD-20261020.md §6](docs/ACCEPTANCE-3COD-20261020.md).
- **Reference libraries are built in the sibling repo, not here.**
  `XinMatch-DataBase` builds all six libraries (`COD` / `PCOD` / `TCOD` ×
  `Inorg` / `Full`); the CIF sources live one level up in
  `../sync-COD` (override with `XRD_DATA_ROOT`), and the built `.xinDB`
  files default to `XinMatch-DataBase/data/`. See that repo's
  [Build and acceptance manual](../XinMatch-DataBase/docs/构建与验收手册.md) for
  the build/validate/acceptance commands.

## Design principles

1. **Clean-room**: no disassembly or decompilation of proprietary software.
   Specifications come from official documentation + published algorithms +
   black-box file-format observation for interoperability.
2. **Kernel / GUI decoupled**: everything in `xinmatch/core/` is pure
   computation (numpy arrays + dataclasses), unit-testable without a display.
   The GUI in `xinmatch/ui/` is a thin layer on top.
3. **Open data first**: the reference database is built from the
   [COD](https://www.crystallography.net/cod/) (CC0) public dump.
4. **Small, verifiable steps**: every task ships with pytest acceptance
   criteria so an AI agent can build, test, and debug independently.

## Project layout

```
xinmatch/
├── core/            # pure computation kernel (no GUI)
│   ├── model/       # Pattern, Peak, Entry, Phase, Restraints, Project
│   ├── io/          # 33 diffraction formats + CIF + exporters
│   ├── preprocess/  # smoothing, background, Kα2, zero point, ...
│   ├── peak/        # peak search, profile fitting, shapes
│   ├── db/          # SQLite reference database (COD) + user DB
│   ├── search/      # FoM search-match, PFSM, restraints
│   ├── index/       # Treor / Dicvol indexing
│   ├── refine/      # Le Bail / Rietveld (delegated to GSAS-II)
│   ├── quant/       # RIR, internal standard, Rietveld quant
│   ├── micro/       # crystallite size, microstrain, DOC
│   └── report/      # report data model + rendering
├── ui/              # PySide6 GUI
├── cli/             # command-line / batch interface
├── utils/           # registration + build variant (stdlib only, no Qt)
tests/               # pytest suite + fixtures + reference baseline
docs/                # analysis docs (reference help retained externally)
tools/               # helper scripts (doc extraction, baseline building)
```

## Getting started

```powershell
# (optional) create a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# install in editable mode with dev + gui extras
pip install -e ".[dev,gui]"

# run the test suite (fast subset; the ``slow`` marker is excluded by default)
pytest

# include the numerically heavy suite (turn-on least squares, GSAS-II
# subprocesses, L3 acceptance curve_fit) — tens of minutes
pytest -m slow

# full local CI (ruff + mypy + tests), mirrors .github/workflows/ci.yml
powershell -File tools/ci.ps1
```

> The reference libraries (`*.xinDB`, ~110 MB–1.7 GB) are not in the repository;
> the source checkout resolves them from `../XinMatch-DataBase/data`
> (`XINMATCH_XINDB_DIR` overrides).  Tests that need them skip themselves.

### Run the working tree without building

`run_dev.bat` starts the code in the working tree in place — no PyInstaller
build and no install step, so what you see is always the latest source.
Without arguments it opens the GUI; any other arguments are forwarded to the
CLI (`python -m xinmatch.cli.main`):

```bat
run_dev.bat                                  :: GUI
run_dev.bat search pat.txt --db ..\XinMatch-DataBase\data\COD-Inorg-20261020.xinDB --top-n 5 --json
run_dev.bat libraries --json                 :: list available .xinDB libraries
```

The interpreter is resolved in this order and echoed on startup:
`%XINMATCH_DEV_PYTHON%` → `.venv\Scripts\python.exe` →
`venv\Scripts\python.exe` → `D:\Project\XRD\python310\python.exe` →
`python` on `PATH`. Because the batch file `cd`s to the repository root,
`python -m` loads the local `xinmatch/` package even when a different
copy is installed in site-packages.

## Builds & registration

Since v1.7.0 two binaries are produced. **Since v3.0.0 both builds bundle the default library** `COD-Inorg-<snapshot>.xinDB`
(unzip/install and you can search-match; located at `<install-dir>\data\`, replaceable, or mount other `.xinDB` libraries):

| Build | Artifact | Registration mechanism | Right end of the status bar |
|---|---|---|---|
| **Release build** (release) | `XinMatch-Setup-<v>.exe` (install location selectable at install time) | **Yes**: registration status checked on every launch | `Registered: <organization/department name>` / `Unregistered` |
| **Internal evaluation build** (internal) | `XinMatch-Internal-<v>.zip` (no installation, for internal use) | **None** | **bold red** `internal evaluation version` |

**v3.4.0 release artifacts**:

| Attachment | Size | SHA-256 (first 16 chars) |
|---|---|---|
| `XinMatch-Setup-3.4.0.exe` (release installer, built-in COD-Inorg library) | 242.4 MiB | `4962defa7d0e4cf7…` |
| `XinMatch-Internal-3.4.0.zip` (portable build = internal evaluation build, marked in red, built-in COD-Inorg library) | 351.4 MiB | `fb82ce897bf4227a…` |
| `SHA256SUMS.txt` | — | — |

The reference database is unchanged in this release; both binaries bundle `COD-Inorg-20261020.xinDB` (rebuilt, 78,035 phases).
`.xinm` export must be paired with **XinRefinement 1.1.0**.
Larger external libraries (`PCOD` / `TCOD` / `Full` / Materials Project) are distributed in the sister repository
[XinMatch-DataBase Releases](https://github.com/PolyXRD/XinMatch-DataBase/releases):
Download `*.xinDB.zip` → unzip → **"Settings → Reference Database…"** or
`XinMatch.exe libraries --add <path>` to mount; multiple libraries can coexist; see
`docs/RELEASE-NOTES-v3.4.0.md` §7.

When the release build is unregistered, a prompt pops up on every launch:

> This software is not registered — all rights reserved, commercial use prohibited.
> For registration, please contact sshztx@outlook.com

Click "**OK**" to dismiss the prompt and keep using the software (the prompt returns at the next launch); click "**Enter registration code**" to paste the code,
and once it validates, registration is complete and the prompt no longer appears. You can also register any time via **Help → Enter registration code (&R)…**.

Registration codes are generated by the developer from the "organization/department name" supplied by the user: `PXRD1-XXXX-XXXX-…` (Base32 payload
`UTF8(org name) + HMAC-SHA256[:8]`); the software re-verifies it and can recover the organization name for display in the status bar;
no network connection or machine code is needed, and the same organization can use it on multiple machines. The algorithm is shared with the PolyXRD family
(reusing `D:\Project\XRD\PolyXRD-Reg`, with a copy in this repo at `xinmatch/utils/registration.py`).

## License

This software is distributed under a **dual license** (Academic + Commercial), consistent with the upstream PolyXRD project.

- **English**: [LICENSE](LICENSE)
- **Chinese (Simplified)**: [LICENSE-CN](LICENSE-CN)

Academic use is free under the Academic License; any commercial use requires a separate written Commercial License from the copyright holder (see license text).
