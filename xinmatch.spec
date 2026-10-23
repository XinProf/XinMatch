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
    - ``COD-Inorg-<snapshot>.xinDB`` -- v3.0.0 **default reference library**,
      collected into ``data/`` so the portable build searches out of the box.
      ``multi_db.xindb_default_dir()`` resolves ``<exe-dir>/data`` first (the
      folder is moved out of ``_internal/`` by ``tools/build_exe.ps1``) and
      ``<exe-dir>/_internal/data`` as a fallback.
* GSAS-II (``C:\\gsas2main``, conda Python 3.13) is NOT bundled; the code
  degrades gracefully via ``GSAS2_AVAILABLE`` when it is absent.

Build with::

    powershell -File tools/build_exe.ps1
"""

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.win32 import versioninfo as vi

# ---- Version (read-only mirror of pyproject [project] version = 3.0.0) ----
APP_NAME = "XinMatch"
APP_VERSION = "3.0.0"
VERSION_TUPLE = (3, 0, 0, 0)

# ---- Build variant (v1.7.0): release = 正式版（含注册机制） / internal = 内部评估版 ----
# 由环境变量 XINMATCH_BUILD_VARIANT 指定（tools/build_exe.ps1 -Variant）。
# 变体以随包分发的 variant.txt 标记固化，运行时由
# xinmatch.utils.build_variant 读取；缺失标记按 release 处理（fail-safe）。
#
# v2.0.0 起：build/variant.request **优先于**环境变量。
# 原因：BUNDLE_NAME 决定 COLLECT 的输出目录，变体若在这个进程里读错，
# internal 构建会算出 release 的名字，PyInstaller 的 COLLECT 会先删掉
# dist/xinmatch-<Version>/（也就是另一个已建好的变体）再写新内容。
# 环境变量在部分调用链上不保证传到子进程（实测过 -File 嵌套时丢失），
# 文件是确定性的，所以让它说话。
_SPEC_DIR = Path(globals().get("SPECPATH") or os.getcwd())
_VARIANT_REQUEST = _SPEC_DIR / "build" / "variant.request"


def _resolve_variant() -> str:
    if _VARIANT_REQUEST.is_file():
        v = _VARIANT_REQUEST.read_text(encoding="utf-8").strip().lower()
        if v in ("release", "internal"):
            return v
    v = os.environ.get("XINMATCH_BUILD_VARIANT", "release").strip().lower()
    return v if v in ("release", "internal") else "release"


BUILD_VARIANT = _resolve_variant()

VARIANT_MARKER = _SPEC_DIR / "build" / "variant.txt"
VARIANT_MARKER.parent.mkdir(parents=True, exist_ok=True)
VARIANT_MARKER.write_text(BUILD_VARIANT, encoding="utf-8")

BUNDLE_NAME = (
    f"xinmatch-{APP_VERSION}" if BUILD_VARIANT == "release"
    else f"xinmatch-internal-{APP_VERSION}"
)

# ---- Collect non-.py assets for packages that ship them at runtime ----
datas = []
binaries = []
hiddenimports = []

# pyqtgraph ships .ui files, icons and dynamically imported submodules.
_pg_d, _pg_b, _pg_h = collect_all("pyqtgraph")
datas += _pg_d
binaries += _pg_b
hiddenimports += _pg_h

# v1.7.0 注册机制模块：显式登记，避免只经延迟导入时被裁剪。
hiddenimports += [
    "xinmatch.utils",
    "xinmatch.utils.registration",
    "xinmatch.utils.build_variant",
]


# ---- Bundled default reference library (v3.0.0) ---------------------------
# 便携版必须"解压即可检索"，所以把默认库 COD-Inorg-<snapshot>.xinDB 打进
# data/。旧版（v2.x）打的是 data/cod_inorganics.db（712 MB 的 v2 SQLite），
# 该格式随 v3.0.0 一起删除了。
#
# 源文件解析顺序：
#   1. 环境变量 XINMATCH_BUNDLE_XINDB（显式指定文件，CI 用）；
#   2. <仓库>/data/*.xinDB；
#   3. <仓库>/../XinMatch-DataBase/data/*.xinDB（构库仓库，开发布局）。
# 同一目录有多个快照时取日期最新的一个。
def _find_bundled_xindb() -> "Path | None":
    explicit = os.environ.get("XINMATCH_BUNDLE_XINDB", "").strip()
    if explicit:
        p = Path(explicit)
        if p.is_file():
            return p
        print(f"WARNING: XINMATCH_BUNDLE_XINDB is not a file: {p}")
    candidates: list[Path] = []
    for root in (
        _SPEC_DIR / "data",
        _SPEC_DIR.parent / "XinMatch-DataBase" / "data",
    ):
        if root.is_dir():
            candidates.extend(root.glob("COD-Inorg*.xinDB"))
    if not candidates:
        return None
    return sorted(candidates)[-1]  # 文件名带 YYYYMMDD，字典序即时间序


_BUNDLED_XINDB = _find_bundled_xindb()
if _BUNDLED_XINDB is not None:
    print(
        "==> Bundling default reference library: "
        f"{_BUNDLED_XINDB.name} ({_BUNDLED_XINDB.stat().st_size / 2**20:.0f} MiB)"
    )
else:
    print(
        "==> WARNING: no COD-Inorg-*.xinDB found — the portable build will not "
        "search out of the box (mount one via 设置→参考数据库…)."
    )

# Project data files (see module docstring for why these exact destinations).
datas += [
    ("xinmatch/core/db/schema.sql", "xinmatch/core/db"),
    # Brand assets (logo / splash / icons).  Read at runtime through
    # ``_asset_path`` (``Path(__file__).resolve().parents[2] / "assets"``),
    # which in the onedir bundle resolves to ``_internal/assets`` — so the
    # whole folder must be collected at that destination.
    ("assets", "assets"),
    # Locally bundled 3Dmol.js + HTML template (``structure_view.py``
    # ``ASSETS_DIR`` = ``ui/assets/3dmol``).  Required for the 3D viewer to
    # work inside the bundle (no CDN at runtime).
    ("xinmatch/ui/assets", "xinmatch/ui/assets"),
    # v1.7.0 构建变体标记（内容 release / internal），运行时读取。
    (str(VARIANT_MARKER), "."),
]

# 默认参考库（COD-Inorg）→ 便携包内的 data/，解压即可检索。
if _BUNDLED_XINDB is not None:
    datas.append((str(_BUNDLED_XINDB), "data"))

# ---- Windows version resource (FileVersion / ProductVersion = 3.0.0) ----
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
    name=BUNDLE_NAME,
)
