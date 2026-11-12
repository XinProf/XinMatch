## XinMatch v3.0.0 — `.xinDB` single-format consolidation · COD-Inorg bundled default library · internal-build red badge

> Baseline `v2.0.0`. Full regression **1570 passed / 4 skipped / 1 xfail** (`pytest tests`, 12m14s, EXIT=0).

### 1. Default library switched to COD-Inorg (`*.xinDB`) and **bundled into the portable package**

| Item | v2.0.0 | v3.0.0 |
|---|---|---|
| Default library | `data/cod_inorganics.db` (v2 SQLite, 712 MB) | `COD-Inorg-20261020.xinDB` (v3 columnar, 113 MB) |
| Can the portable package search directly? | No (must download a separate 512 MB library and mount it) | **Yes** (already bundled at `<exe>/data/`) |
| Library source resolution | hard-coded | `XINMATCH_XINDB_DIR` → `<exe>/data` → `<exe>/_internal/data` → `../XinMatch-DataBase/data` (source-tree state) |

* The library registry `core/db/multi_db.py` was rewritten as v3-only: `KIND_XINDB` plus four
  built-in ids (`xindb_cod_inorg` default / `xindb_cod_full` / `xindb_pcod_inorg` /
  `xindb_tcod_inorg`), picking the **latest snapshot** by `<Prefix>-<YYYYMMDD>.xinDB`;
  `open_library()` / `open_search_database()` return a read-only `XinDBReader`.
* `xinmatch.spec` gains `_find_bundled_xindb()` to collect the default library into `data/`;
  `tools/build_exe.ps1` moves the library from PyInstaller 6's `_internal/data` to `<exe>/data`
  so users can replace it directly.

### 2. Old-format runtime code **deleted** (not deprecated)

* Removed `core/db/polyxrd.py` (the PolyXRD `phases` dump conversion layer) and
  `core/db/pdf2_index.py` (the PDF-2 conversion layer).
* `ui/dialogs/library_dialog.py` went **720 → about 300 lines**: it only lists / mounts /
  unmounts / refreshes; the build thread and index-building thread are gone, and the
  "PDF-2 source directory" setting is removed.
* CLI `libraries` keeps only `--add` / `--remove` (`--build` / `--force` / `--no-build` removed).
* `core/batch.py` and the top-level API `identify_phase` / `full_analysis` now go through
  `open_search_database()` instead of a bare `sqlite3.connect` — otherwise they would fall into
  the deleted v2 row-table path.
* Ten v2-only test files removed; new `tests/xindb_support.py` (`write_xindb` builds a real
  `.xinDB`).

### 3. Internal evaluation build: **bold red** "internal evaluation build" in the status bar

* `_build_statusbar()` uses a widget-level stylesheet: `color: #d32f2f; font-weight: bold;
  padding: 0 6px;`, `objectName = internalBuildLabel`, `addPermanentWidget(label, 1)` pinned to
  the far right of the status bar.
* Why a widget-level style instead of the global QSS: the status bar is repainted on theme
  change, and widget-level rules take precedence, so the colour does not drop out.

### 4. Attachments

| Attachment | Content |
|---|---|
| `XinMatch-Setup-3.0.0.exe` | Release installer (**with registration**, status bar shows `Registered: <organization>` / `Unregistered`), **bundles the COD-Inorg library** |
| `XinMatch-Internal-3.0.0.zip` | Portable package = **internal evaluation build** (no install, no registration, status bar shows the **red** "internal evaluation build"), **bundles the COD-Inorg library** |
| `XinMatch-Databases-COD-Inorg-3.0.0.zip` | Standalone COD inorganic library package (`*.xinDB`, for replacing or topping up an existing installation) |
| `SHA256SUMS.txt` | SHA-256 of the attachments above |

### 5. Upgrade notes

* Upgrading from v2.0.0: **old `.db` / `.sqlite` reference libraries no longer work** (mounting
  is rejected explicitly with a note that the format was removed). Use `COD-Inorg-*.xinDB`
  instead (bundled in this release; PCOD / TCOD are distributed in
  [XinMatch-DataBase](https://github.com/PolyXRD/XinMatch-DataBase) Releases).
* Other `*.xinDB` libraries remain mountable from any folder: `Settings → Reference Database…` or
  `xinmatch libraries --add <path>`.
