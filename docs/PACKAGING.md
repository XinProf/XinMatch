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

Subcommands are read from `xinmatch.cli.main:build_parser()` at runtime, so the
dispatcher and the CLI cannot drift apart (`libraries`, `batch`, `instrument`
were missing from an earlier hard-coded list, which made
`XinMatch.exe libraries --json` open the GUI instead of mounting a database).
`-h` / `--help` also go to the CLI; everything else opens the GUI.

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

## External reference databases (v2.0.0)

Databases no longer have to be copied into `data/`.  The user mounts any
`*.sqlite` / `*.db` file from any folder:

```powershell
.\XinMatch.exe libraries --add "D:\XRD-Data\PolyXRD\COD_inorganics.sqlite"
.\XinMatch.exe libraries --list          # or --json for scripting
.\XinMatch.exe libraries --build <id> --force   # rebuild after the source changes
```

In the GUI: 设置 → 参考数据库… → 添加外部库… (the picker and the *建立/重建索引*
button live in the same dialog).

Behaviour worth knowing for support:

* the mount is recorded in `<user-data>/libraries.json`
  (`%USERPROFILE%\.xinmatch\` by default, override with `XINMATCH_USER_DATA`);
  the selected library still lives in the GUI YAML under
  `reference_db.selected_library_id`;
* a PolyXRD dump (`phases` table with `peaks_d`/`peaks_i`) is converted **once**
  into a XinMatch-schema sidecar at
  `<user-data>/indexes/external/<name>_<hash>.db` (~3–4 min and ~650 MB for the
  163 k-row PDF-2 file; the 1.2 GB COD dump is similar).  The conversion is
  cancellable and the source file is only ever opened read-only;
* the sidecar records the source `mtime`/`size`, so replacing or rebuilding the
  PolyXRD database automatically triggers a rebuild on the next search (or
  immediately with *建立/重建索引*);
* `*.sqlite` is accepted wherever a `*.db` path is expected
  (`data/cod_inorganics.sqlite`, `cod_full.sqlite`, …), matching PolyXRD's
  switch to the `.sqlite` extension;
* PolyXRD structure-only dumps (`cod_index.sqlite` / `cod_entries`, no peak
  table) are rejected with an explanation instead of being mounted empty —
  use `COD_inorganics.sqlite`, `PDF2_2004.sqlite`, or export a `phases`-style
  database.

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
  `schema.sql` at **import time** via
  `importlib.resources.files("xinmatch.core.db").joinpath("schema.sql")`.
  The spec collects it to `xinmatch/core/db/schema.sql` inside `_internal/`;
  the wheel declares it (plus `xinmatch/ui/assets/3dmol/*`) through
  `[tool.setuptools.package-data]`, and CI asserts both are present in the
  built wheel.  If it is missing, the whole package fails to import on startup.
* **The DB path is not auto-resolved.**  Neither the GUI nor the CLI guesses the
  DB location; users point the Open-DB dialog / `--db` flag at
  `data/cod_inorganics.db`.
* **JSON arguments need escaped quotes** when passed through a shell / .NET
  `ProcessStartInfo` (`"{\"Al2O3\":100.0}"`); unescaped quotes vanish and you
  get a `json` parse error.
* **`.gitignore` already covers `build/`, `dist/`, `*.spec`** — no extra ignore
  rules needed.

## 注册机制的安全边界（v1.7.x 说明）

`xinmatch/utils/registration.py` 是 PolyXRD 家族的**逐字副本**，注册码 =
Base32(单位名 + `0x00` + HMAC-SHA256(内置密钥, 单位名)[:8])。密钥随二进制分发，
属于**混淆级**防护（源码注释已写明「可被逆向提取」）：

* 能防的是「随便填个码」和「手改 `registration.json`」（每次启动重新校验）；
* 防不住的是「从 exe 里提取密钥后自行出码」；
* 因此**不要**把它当作强授权/防破解方案；如需提高门槛，需改非对称签名
  （Ed25519：私钥只留在 `tools/make_reg_code.py`，软件端只内置公钥），
  代价是已发出的注册码作废（格式变更）。

当前决策：保持与家族互通的码格式不变，安全边界按上述如实告知。

## Files

| File | Purpose |
|------|---------|
| `xinmatch.spec` | PyInstaller build description (onedir, data files, icon, version resource 1.3.1) |
| `tools/build_exe.ps1` | One-shot build driver (icon -> pyinstaller -> relocate DB) |
| `tools/pyi_entry.py` | Dispatcher entry point (CLI vs GUI by argv) |
