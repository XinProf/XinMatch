# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for XinMatch (Phase 15 packaging).

Layout decisions
----------------
* **onedir** (not onefile).  The COD reference DB is ~537 MB; onefile would
  re-extract ~700 MB to %TEMP% on every launch and fight antivirus scans.
  onedir keeps the DB as a loose file next to the executable.
* **Single executable** (``XinMatch.exe``) with a dispatcher entry
  (``tools/pyi_entry.py``): it runs the CLI when the first argument is a known
  subcommand, otherwise launches the GUI.  PyInstaller selects one boot script
  per exe, so splitting two Analysis scripts across two EXEs does *not* yield
  independent entry points.
* ``console=True``: keeps CLI stdout/stderr visible and lets offscreen GUI
  smoke capture crashes.  Flip to ``console=False`` for a windowed production
  build (note: CLI output then disappears).
* Data files collected:
    - ``xinmatch/core/db/schema.sql`` -- read at *import time* next to
      ``schema.py``; MUST land at ``xinmatch/core/db/schema.sql`` inside the
      bundle or the whole package fails to import.
    - ``data/cod_inorganics.db`` -- bundled at ``data/``; the GUI/CLI never
      auto-resolve it, users point the Open-DB dialog / ``--db`` at it.
* GSAS-II (``C:\\gsas2main``, conda Python 3.13) is NOT bundled; the code
  degrades gracefully via ``GSAS2_AVAILABLE`` when it is absent.

Build with::

    powershell -File tools/build_exe.ps1
"""

from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.win32 import versioninfo as vi

# ---- Version (read-only mirror of pyproject [project] version = 1.6.1) ----
APP_NAME = "XinMatch"
APP_VERSION = "1.6.1"
VERSION_TUPLE = (1, 6, 1, 0)

# ---- Collect non-.py assets for packages that ship them at runtime ----
datas = []
binaries = []
hiddenimports = []

# pyqtgraph ships .ui files, icons and dynamically imported submodules.
_pg_d, _pg_b, _pg_h = collect_all("pyqtgraph")
datas += _pg_d
binaries += _pg_b
hiddenimports += _pg_h

# Project data files (see module docstring for why these exact destinations).
datas += [
    ("xinmatch/core/db/schema.sql", "xinmatch/core/db"),
    # NOTE (v1.6.0): data/cod_inorganics.db is intentionally NOT collected.
    # The reference DB (~512 MB) ships as a separate downloadable archive
    # (data is mountable next to the exe: <exe-dir>/data/cod_inorganics.db,
    # auto-resolved by multi_db.default_db_path when frozen).
    # Brand assets (logo / splash / icons).  Read at runtime through
    # ``_asset_path`` (``Path(__file__).resolve().parents[2] / "assets"``),
    # which in the onedir bundle resolves to ``_internal/assets`` — so the
    # whole folder must be collected at that destination.
    ("assets", "assets"),
    # Locally bundled 3Dmol.js + HTML template (``structure_view.py``
    # ``ASSETS_DIR`` = ``ui/assets/3dmol``).  Required for the 3D viewer to
    # work inside the bundle (no CDN at runtime).
    ("xinmatch/ui/assets", "xinmatch/ui/assets"),
]

# ---- Windows version resource (FileVersion / ProductVersion = 1.6.1) ----
version_info = vi.VSVersionInfo(
    ffi=vi.FixedFileInfo(
        filevers=VERSION_TUPLE,
        prodvers=VERSION_TUPLE,
        mask=0x3F,
        flags=0x0,
        OS=0x40004,      # VOS_NT_WINDOWS32
        fileType=0x1,    # VFT_APP
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        vi.StringFileInfo([
            vi.StringTable(
                "040904B0",
                [
                    vi.StringStruct("CompanyName", "XinMatch Contributors"),
                    vi.StringStruct("FileDescription", "XinMatch - powder XRD phase analysis"),
                    vi.StringStruct("FileVersion", APP_VERSION),
                    vi.StringStruct("InternalName", APP_NAME),
                    vi.StringStruct("OriginalFilename", "XinMatch.exe"),
                    vi.StringStruct("ProductName", APP_NAME),
                    vi.StringStruct("ProductVersion", APP_VERSION),
                    # v1.0.0 品牌要求：联系方式（用户指定 sshztx@outlook.com）
                    # 写入可执行文件版本资源。
                    vi.StringStruct("LegalCopyright", "Copyright 2026 XinMatch Contributors <sshztx@outlook.com>"),
                    vi.StringStruct("Contact", "sshztx@outlook.com"),
                    vi.StringStruct("联系方式", "sshztx@outlook.com"),
                ],
            )
        ]),
        vi.VarFileInfo([vi.VarStruct("Translation", [0x0409, 0x04B0])]),
    ],
)

# ---- Analysis: single dispatcher entry point ----
a = Analysis(
    ["tools/pyi_entry.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Optional/heavy deps not used by XinMatch (pulled in transitively).
        "matplotlib",
        "pytest",
        "_pytest",
        "pyqtgraph.examples",
        "OpenGL",
        "tkinter",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    icon="assets/icons/logo.ico",
    version=version_info,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="xinmatch-1.6.1",
)
