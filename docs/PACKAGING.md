# Packaging XinMatch for Windows (PyInstaller)

Phase 15 builds a **onedir** Windows distribution of XinMatch with PyInstaller.
This document describes how to build it, where the output lands, how to smoke-test
it, and the known limitations / common pitfalls.

## Prerequisites

* Python 3.10.11 at `D:\Project\XRD\python310\python.exe`
  (override with the `XINMATCH_PYTHON` env var).
* Installed into that interpreter: `PySide6`, `pyqtgraph`, `gemmi`, `numpy`,
  `scipy`, `lmfit`, `pyyaml`, `Pillow`, and **`pyinstaller`**.

  Install PyInstaller if missing:

  ```powershell
  & D:\Project\XRD\python310\python.exe -m pip install pyinstaller
  ```

* `data/cod_inorganics.db` (~512 MB, 71,199 COD entries) present in the repo.

## Build

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_exe.ps1
```

The script:

1. Converts `assets/logo.png` -> `build/xinmatch.ico` (exe icon).
2. Runs `pyinstaller --noconfirm --clean xinmatch.spec`.
3. Relocates the bundled DB from `_internal/data/` to `data/` next to the exe.

Output: **`dist/xinmatch-1.3.1/`**

```
dist/xinmatch-1.3.1/
  XinMatch.exe                 single dispatcher executable (console subsystem)
  data/cod_inorganics.db       reference DB (point Open-DB / --db at this)
  _internal/                   Python runtime, Qt, PySide6, pyqtgraph, gems, ...
    xinmatch/core/db/schema.sql   (required; read at import time)
```

### How the single executable works

PyInstaller selects **one** boot script per executable; splitting two Analysis
scripts across two `EXE()` targets does **not** produce independent entry points
(the bootloader always runs the first script).  We therefore ship one exe whose
entry (`tools/pyi_entry.py`) dispatches on `sys.argv`:

* `XinMatch.exe <cli-subcommand> ...`  -> runs `xinmatch.cli.main`
* `XinMatch.exe` (double-click, no recognized subcommand) -> runs the GUI

Subcommands recognized for the CLI branch: `import`, `process`, `search`,
`quantify`, `report`, `run`.

## Smoke testing

CLI (pure-compute, no DB needed):

```powershell
cd dist\xinmatch-1.3.1
.\XinMatch.exe quantify --phases "{\"Al2O3\":100.0}"
# expect: weight_fractions: 1 entry(ies)   (exit 0)
```

GUI (offscreen; does not require a display session):

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
$p = Start-Process .\XinMatch.exe -PassThru
Start-Sleep 8
$p.HasExited          # False == MainWindow built and event loop running
Stop-Process -Id $p.Id -Force
```

Verify the bundled DB is intact:

```powershell
.\XinMatch.exe search <pattern-file> --db .\data\cod_inorganics.db
```

## Known limitations

* **GSAS-II is not bundled.**  It lives at `C:\gsas2main` and runs under a
  separate conda Python 3.13, so it cannot go into this distribution.  The
  app detects it via `GSAS2_AVAILABLE` and degrades gracefully; Rietveld /
  quantitative refinement against GSAS-II only activates on machines where
  GSAS-II is installed externally.
* **Large DB.**  `cod_inorganics.db` is ~512 MB; the full bundle is ~1.1–1.2 GB.
  This is why we use **onedir** (onefile would re-extract ~700 MB to `%TEMP%`
  on every launch).
* **QtWebEngine / QML bloat.**  The PySide6 hook pulls in QtWebEngine, QtQml,
  QtQuick etc. transitively; XinMatch itself only needs QtWidgets/QtGui/QtCore.
  This is left as-is for Phase 15 (config is reusable); a production slim build
  can add `PySide6.QtWebEngine*`, `PySide6.QtQml`, `PySide6.QtQuick*` to the
  `excludes` list in `xinmatch.spec`.
* **`console=True`.**  The exe uses the console subsystem so CLI stdout/stderr
  and offscreen-GUI crash output are visible.  Flip `console=False` in the spec
  for a windowed production build (note: CLI output then disappears).

## Common pitfalls

* **`schema.sql` must be bundled.**  `xinmatch/core/db/schema.py` reads
  `schema.sql` at **import time** (`Path(__file__).with_name("schema.sql")`).
  The spec collects it to `xinmatch/core/db/schema.sql` inside `_internal/`.
  If it is missing, the whole package fails to import on startup.
* **The DB path is not auto-resolved.**  Neither the GUI nor the CLI guesses the
  DB location; users point the Open-DB dialog / `--db` flag at
  `data/cod_inorganics.db`.
* **JSON arguments need escaped quotes** when passed through a shell / .NET
  `ProcessStartInfo` (`"{\"Al2O3\":100.0}"`); unescaped quotes vanish and you
  get a `json` parse error.
* **`.gitignore` already covers `build/`, `dist/`, `*.spec`** — no extra ignore
  rules needed.

## Files

| File | Purpose |
|------|---------|
| `xinmatch.spec` | PyInstaller build description (onedir, data files, icon, version resource 1.3.1) |
| `tools/build_exe.ps1` | One-shot build driver (icon -> pyinstaller -> relocate DB) |
| `tools/pyi_entry.py` | Dispatcher entry point (CLI vs GUI by argv) |
