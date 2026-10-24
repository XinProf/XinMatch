"""Reference-database registry (v3.0.0: ``.xinDB`` only).

XinMatch v3.0.0 drops every legacy on-disk format.  The **only** searchable
reference library is a v3 columnar ``.xinDB`` file
(:mod:`xinmatch.core.db.reader_v3`), and the **default** one is the bundled
inorganic COD library ``COD-Inorg-<snapshot>.xinDB``.

Why the legacy formats are gone
-------------------------------
``xinmatch`` (v2 SQLite with ``entries`` / ``peaks`` / ``elements``),
``pdf2`` (PolyXRD dump + converted sidecar), ``cod_full`` (CIF-computed peaks)
and ``polyxrd`` (arbitrary ``phases`` table) all needed their own reader, their
own conversion cache and their own failure modes.  v3 replaced the lot: one
columnar layout, one reader, one search path
(:func:`~xinmatch.core.db.search_v3.search_match_v3`).  Keeping the old
readers alive only meant two code paths to test for every query, so they were
deleted rather than deprecated.

Library discovery
-----------------
Built-in rows are resolved from :func:`xindb_default_dir`, searched for
``<Prefix>-<YYYYMMDD>.xinDB`` (newest snapshot wins):

===============  ==============================================
id               file
===============  ==============================================
``xindb_cod_inorg``  ``COD-Inorg-*.xinDB``   ← **默认库**
``xindb_cod_full``   ``COD-Full-*.xinDB``
``xindb_pcod_inorg`` ``PCOD-Inorg-*.xinDB``
``xindb_tcod_inorg`` ``TCOD-Inorg-*.xinDB``
===============  ==============================================

Any other ``.xinDB`` anywhere on disk can be mounted with
:func:`add_external_library` (persisted in ``<user-data>/libraries.json``).

Public API
----------
* :func:`list_libraries` — all known libraries with availability + reasons.
* :func:`library_by_id` — lookup by stable id.
* :func:`resolve_default` — the COD-Inorg record (falls back to any available
  library so a machine without the default build still works).
* :func:`open_library` / :func:`open_search_database` — return a
  :class:`~xinmatch.core.db.reader_v3.XinDBReader`; close it when done (or use
  it as a context manager).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

from .schema_v3 import XINDB_SUFFIX, XINDB_SUFFIX_LC

logger = logging.getLogger(__name__)

#: The only library kind left in v3.0.0.
KIND_XINDB = "xindb"

#: Id of the default (bundled) library.
DEFAULT_LIBRARY_ID = "xindb_cod_inorg"

#: ``<Prefix>`` of every built-in row, in picker order.
_BUILTIN_PREFIXES: tuple[tuple[str, str], ...] = (
    (DEFAULT_LIBRARY_ID, "COD-Inorg"),
    ("xindb_cod_full", "COD-Full"),
    ("xindb_pcod_inorg", "PCOD-Inorg"),
    ("xindb_tcod_inorg", "TCOD-Inorg"),
)

#: Snapshot date embedded in the file names (``COD-Inorg-20261020.xinDB``).
_SNAPSHOT_RE = re.compile(r"\d{8}")


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------
def project_root() -> Path:
    """Return the XinMatch project root (development layout).

    This module lives at ``<root>/xinmatch/core/db/multi_db.py``, so
    ``parents[3]`` is the directory that contains ``xinmatch/`` and ``data/``.
    """
    return Path(__file__).resolve().parents[3]


def _data_dir() -> Path:
    """Directory holding the bundled reference databases.

    Development: ``<project-root>/data``.  Frozen (PyInstaller onedir): the
    portable package puts the ``.xinDB`` at ``<exe-dir>/data`` so the user can
    swap libraries without touching the bundle.  PyInstaller 6 also collects
    ``datas`` into ``_internal/``, so that location is checked as a fallback
    (a build made by running ``pyinstaller xinmatch.spec`` directly, without
    :file:`tools/build_exe.ps1` moving the folder out).
    """
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        for candidate in (exe_dir / "data", exe_dir / "_internal" / "data"):
            if candidate.is_dir():
                return candidate
        return exe_dir / "data"
    return project_root() / "data"


def user_data_dir() -> Path:
    """Writable per-user data directory (``~/.xinmatch``).

    Override with ``XINMATCH_USER_DATA``.  Only the external-library registry
    lives here now — v3 libraries are self-contained files, nothing is cached.
    """
    override = os.environ.get("XINMATCH_USER_DATA")
    if override:
        return Path(override)
    return Path.home() / ".xinmatch"


def _has_xindb(directory: Path) -> bool:
    """True when *directory* actually holds at least one ``.xinDB`` library."""
    try:
        return directory.is_dir() and any(directory.glob(f"*{XINDB_SUFFIX}"))
    except OSError:  # pragma: no cover - unreadable directory
        return False


#: ``XINMATCH_XINDB_DIR`` values already reported as stale.  ``xindb_default_dir``
#: is called several times per registry refresh (once per built-in library), so
#: the warning must not be re-emitted for every call.
_WARNED_ENV_DIRS: set[str] = set()


def xindb_default_dir() -> Path:
    """Directory searched for the built-in v3 libraries.

    Resolution order:

    1. ``XINMATCH_XINDB_DIR`` (deployment scripts / tests) — **only when it
       actually contains a ``.xinDB``**.  A stale variable pointing at an
       empty or removed folder used to win unconditionally, which silently
       hid the bundled library (``available=False`` for a machine that has
       ``data/COD-Inorg-*.xinDB``): the user sees "library not found" instead
       of "the environment variable is wrong".  Such an override is now
       ignored with a warning and the next candidate is used.
    2. ``<data>/`` — ``<exe-dir>/data`` when frozen, ``<repo>/data`` in dev;
    3. the sibling build repo ``<repo>/../XinMatch-DataBase/data`` (dev only).

    Step 3 exists so a source checkout finds the libraries built by the
    data repo without copying 1.8 GiB around; it is skipped when frozen.
    """
    override = os.environ.get("XINMATCH_XINDB_DIR")
    candidates: list[Path] = []
    if override:
        env_dir = Path(override)
        candidates.append(env_dir)
        if _has_xindb(env_dir):
            return env_dir
        if override not in _WARNED_ENV_DIRS:
            _WARNED_ENV_DIRS.add(override)
            logger.warning(
                "XINMATCH_XINDB_DIR=%s 下没有找到任何 .xinDB 库；忽略该环境变量，"
                "回退到内置库目录。",
                override,
            )
    candidates.append(_data_dir())
    if not getattr(sys, "frozen", False):
        candidates.append(project_root().parent / "XinMatch-DataBase" / "data")
    # 取"真的放着 .xinDB"的那个: 源码树的 data/ 里常年只躺着日志与旧格式库,
    # 而库本体在构库仓库 —— 只看目录存在与否会把默认库定位到空目录上。
    for root in candidates:
        if _has_xindb(root):
            return root
    # 没有任何候选目录真的放着库: 返回内置数据目录(而不是过期/为空的 env
    # 覆盖目录), 让"未找到库"的报错指向正确位置。
    return candidates[1] if override else candidates[0]


def _latest_snapshot(prefix: str, directory: Path | None = None) -> Path:
    """Newest ``<prefix>-<YYYYMMDD>.xinDB`` in *directory*.

    Libraries carry their COD snapshot date in the file name, so several
    builds of the same kind can coexist and the newest one is what the picker
    offers.  The undated ``<prefix>.xinDB`` remains the fallback.
    """
    base = Path(directory) if directory is not None else xindb_default_dir()
    if base.is_file() and _is_xindb(base):
        return base
    dated = [
        p
        for p in base.glob(f"{prefix}-*{XINDB_SUFFIX}")
        if _SNAPSHOT_RE.fullmatch(p.stem.rsplit("-", 1)[-1])
    ]
    if dated:
        return sorted(dated)[-1]
    return base / f"{prefix}{XINDB_SUFFIX}"


def xindb_cod_inorg_path() -> Path:
    """Default location of the v3 inorganic-COD library (**默认库**)."""
    return _latest_snapshot("COD-Inorg")


def xindb_cod_full_path() -> Path:
    """Default location of the v3 full-COD library (newest snapshot)."""
    return _latest_snapshot("COD-Full")


def xindb_pcod_inorg_path() -> Path:
    """Default location of the v3 PCOD inorganic library."""
    return _latest_snapshot("PCOD-Inorg")


def xindb_tcod_inorg_path() -> Path:
    """Default location of the v3 TCOD inorganic library."""
    return _latest_snapshot("TCOD-Inorg")


def default_db_path() -> Path:
    """The default library file (``COD-Inorg-*.xinDB``).

    Kept as a name because batch configs, docs and the CLI all refer to "the
    default database"; in v3.0.0 it resolves to the bundled ``.xinDB``.
    """
    return xindb_cod_inorg_path()


def _is_xindb(path: Path) -> bool:
    """True when *path* looks like a v3 ``.xinDB`` library (by extension).

    The content is verified separately by :func:`xinmatch.core.db.reader_v3.probe`
    when the library is actually opened.
    """
    return path.suffix.lower() == XINDB_SUFFIX_LC


# ---------------------------------------------------------------------------
# External library registry
# ---------------------------------------------------------------------------
#: JSON registry of user-mounted ``.xinDB`` files (any folder).
#: Kept out of the GUI YAML on purpose: it is *data*, not a look preference, and
#: the CLI must be able to add/list libraries without importing Qt.
_REGISTRY_VERSION = 2


@dataclass(frozen=True)
class ExternalLibrary:
    """A user-mounted reference library (path + label + stable id).

    Attributes
    ----------
    id:
        Stable ``ext_<hash>`` identifier derived from the resolved absolute
        path, so re-adding the same file is idempotent and the config keeps
        pointing at a valid id after a restart.
    path:
        Absolute path to the ``.xinDB`` file.
    label:
        Optional display label (defaults to the file stem).
    """

    id: str
    path: Path
    label: str = ""

    @property
    def display_name(self) -> str:
        return self.label or self.path.stem


def library_registry_path() -> Path:
    """Path of the external-library registry JSON.

    Override with ``XINMATCH_LIBRARIES_JSON`` (used by tests and by portable
    installs that keep everything on a USB stick).
    """
    override = os.environ.get("XINMATCH_LIBRARIES_JSON")
    if override:
        return Path(override)
    return user_data_dir() / "libraries.json"


def _external_id(path: Path) -> str:
    try:
        key = str(path.resolve()).lower()
    except OSError:  # pragma: no cover - defensive
        key = str(path).lower()
    return "ext_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def load_external_libraries() -> list[ExternalLibrary]:
    """Read the registry (never raises; a corrupt file yields an empty list)."""
    file = library_registry_path()
    if not file.exists():
        return []
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("ignoring unreadable library registry: %s", file)
        return []
    out: list[ExternalLibrary] = []
    for item in data.get("libraries", []) if isinstance(data, dict) else []:
        try:
            entry = ExternalLibrary(
                id=str(item["id"]),
                path=Path(str(item["path"])),
                label=str(item.get("label") or ""),
            )
        except (KeyError, TypeError):  # pragma: no cover - hand-edited file
            logger.warning("skipping malformed registry entry: %r", item)
            continue
        if not _is_xindb(entry.path):
            # v2 时代的注册表里还留着 .sqlite / .db 条目: 格式已不支持,
            # 静默忽略比让它们以"不可用"行混进选择列表干净 (磁盘上多半还在,
            # 但 v3 读不了; 用户真要那几个库得重新构建成 .xinDB)。
            logger.info("ignoring legacy library entry (not .xinDB): %s", entry.path)
            continue
        out.append(entry)
    return out


def _save_external_libraries(libs: list[ExternalLibrary]) -> None:
    file = library_registry_path()
    file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": _REGISTRY_VERSION,
        "libraries": [
            {"id": lib.id, "path": str(lib.path), "label": lib.label} for lib in libs
        ],
    }
    tmp = file.with_name(file.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    tmp.replace(file)


def add_external_library(path: str | Path, label: str | None = None) -> ExternalLibrary:
    """Register an external ``.xinDB`` library located anywhere on disk.

    Re-adding the same path updates the label and keeps the same id, so the
    config's ``selected_library_id`` never dangles.

    Raises
    ------
    FileNotFoundError
        The path does not exist.
    ValueError
        The file is not a usable ``.xinDB`` library.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"library file not found: {p}")
    if not _is_xindb(p):
        raise ValueError(
            f"仅支持 .xinDB 库（v3 列存格式）：{p}。"
            "旧格式（cod_inorganics.db / PDF2 dump / COD sqlite）已在 v3.0.0 移除。"
        )
    ok, reason = _probe_xindb(p)
    if not ok:
        raise ValueError(f"不是可用的 .xinDB 库（{reason}）：{p}")

    lib_id = _external_id(p)
    entry = ExternalLibrary(id=lib_id, path=p.resolve(), label=(label or "").strip())
    existing = [lib for lib in load_external_libraries() if lib.id != lib_id]
    existing.append(entry)
    _save_external_libraries(existing)
    logger.info("mounted external library %s -> %s", lib_id, entry.path)
    return entry


def remove_external_library(library_id: str) -> bool:
    """Unregister *library_id*; returns ``True`` when it existed.

    Only the registry entry is removed — the library file is left untouched.
    """
    libs = load_external_libraries()
    kept = [lib for lib in libs if lib.id != library_id]
    if len(kept) == len(libs):
        return False
    _save_external_libraries(kept)
    return True


# ---------------------------------------------------------------------------
# Registry record
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LibraryRecord:
    """A single mountable reference library.

    Attributes
    ----------
    id:
        Stable short identifier (used by the GUI as a key, never displayed as-is).
    display_name:
        Human-readable name for the library picker.
    kind:
        Always :data:`KIND_XINDB` in v3.0.0 (kept as a field so the GUI table
        does not need a special case).
    path:
        The ``.xinDB`` file that :func:`open_library` opens.
    entry_count:
        Number of phases in the library, or ``None`` when it could not be read.
    available:
        Whether :func:`open_library` will succeed.
    unavailable_reason:
        Human-readable reason when ``available`` is ``False``.
    note:
        Optional extra context (where the file is, how to build a missing one).
    external:
        ``True`` for user-mounted libraries (shown with their own path in the
        picker, removable from the dialog).
    default:
        ``True`` for the default library (COD-Inorg).
    """

    id: str
    display_name: str
    kind: str = KIND_XINDB
    path: Path = Path()
    entry_count: int | None = None
    available: bool = True
    unavailable_reason: str | None = None
    note: str | None = None
    external: bool = False
    default: bool = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _readonly_uri(path: Path) -> str:
    """Return a ``file:`` URI for *path* that is safe for special characters."""
    try:
        return path.resolve().as_uri() + "?mode=ro"
    except ValueError:  # pragma: no cover - relative path, defensive
        return "file:" + path.as_posix() + "?mode=ro"


def _probe_xindb(path: Path) -> tuple[bool, str]:
    """Probe a v3 library without importing the heavy reader eagerly."""
    from .reader_v3 import probe as _probe

    return _probe(path)


def _count_xindb_entries(path: Path) -> int | None:
    """Return the number of phases in a v3 library."""
    try:
        conn = sqlite3.connect(_readonly_uri(path), uri=True)
        try:
            cur = conn.execute("SELECT COUNT(*) FROM entries")
            return int(cur.fetchone()[0])
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        return None


def _xindb_record(
    lib_id: str,
    display_name: str,
    path: Path,
    *,
    is_default: bool = False,
    external: bool = False,
) -> LibraryRecord:
    """Build a registry record for a v3 ``.xinDB`` library.

    A v3 library is a self-contained columnar file: it is opened directly,
    read-only, and can live in any folder.
    """
    if not path.exists():
        return LibraryRecord(
            id=lib_id,
            display_name=display_name,
            path=path,
            available=False,
            unavailable_reason=f"未找到库文件：{path}",
            note=(
                "尚未构建该库 —— 在 XinMatch-DataBase 仓库里跑 "
                "`python -m tools.build_cod_inorg_xindb`（或对应 build 脚本）。"
            ),
            default=is_default,
            external=external,
        )
    ok, reason = _probe_xindb(path)
    if not ok:
        return LibraryRecord(
            id=lib_id,
            display_name=display_name,
            path=path,
            available=False,
            unavailable_reason=f"不是可用的 .xinDB 库（{reason}）：{path}",
            default=is_default,
            external=external,
        )
    return LibraryRecord(
        id=lib_id,
        display_name=display_name,
        path=path,
        entry_count=_count_xindb_entries(path),
        available=True,
        note=f"v3 列存库（只读）：{path}",
        default=is_default,
        external=external,
    )


def _external_record(ext: ExternalLibrary) -> LibraryRecord:
    """Build the registry record for a user-mounted library at an arbitrary path."""
    return _xindb_record(
        ext.id, ext.display_name, ext.path, external=True
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
#: Display names of the built-in rows (all English-free so the GUI can show
#: them next to Chinese UI text without a translation layer).
_BUILTIN_NAMES: dict[str, str] = {
    DEFAULT_LIBRARY_ID: "COD Inorganics（默认）",
    "xindb_cod_full": "COD Full",
    "xindb_pcod_inorg": "PCOD Inorganics",
    "xindb_tcod_inorg": "TCOD Inorganics",
}


def list_libraries() -> list[LibraryRecord]:
    """Return all known libraries, with live availability status.

    Order is the suggested picker order: the default COD-Inorg library first,
    then the other built-ins (only when present on disk), then every
    user-mounted library.  Each record carries ``available`` and
    ``unavailable_reason`` so the GUI can grey out missing rows.
    """
    out: list[LibraryRecord] = []
    builtin_paths: set[Path] = set()
    for lib_id, prefix in _BUILTIN_PREFIXES:
        rec = _xindb_record(
            lib_id,
            _BUILTIN_NAMES[lib_id],
            _latest_snapshot(prefix),
            is_default=lib_id == DEFAULT_LIBRARY_ID,
        )
        out.append(rec)
        if rec.available:
            try:
                builtin_paths.add(rec.path.resolve())
            except OSError:  # pragma: no cover - defensive
                builtin_paths.add(rec.path)
    for ext in load_external_libraries():
        # 用户早年把内置库那份也挂过一次 → 同一文件不要在列表里出现两遍
        try:
            if ext.path.resolve() in builtin_paths:
                continue
        except OSError:  # pragma: no cover - defensive
            pass
        out.append(_external_record(ext))
    return out


def library_by_id(library_id: str) -> LibraryRecord | None:
    """Return the :class:`LibraryRecord` with *library_id*, or ``None``."""
    for rec in list_libraries():
        if rec.id == library_id:
            return rec
    return None


def resolve_default() -> LibraryRecord:
    """Return the default library record (COD-Inorg).

    Never raises.  When the default build is missing it falls back to the first
    *available* library so a machine with only a mounted ``.xinDB`` still
    searches something instead of failing on startup; if nothing is available
    the record for the default is returned with ``available=False`` and a
    reason the GUI can show.
    """
    default = _xindb_record(
        DEFAULT_LIBRARY_ID,
        _BUILTIN_NAMES[DEFAULT_LIBRARY_ID],
        _latest_snapshot("COD-Inorg"),
        is_default=True,
    )
    if default.available:
        return default
    for rec in list_libraries():
        if rec.available:
            return rec
    return default


class LibraryNotAvailableError(RuntimeError):
    """Raised by :func:`open_library` when the requested library cannot be opened.

    The exception message carries the same friendly reason as
    ``LibraryRecord.unavailable_reason`` so CLI / GUI callers can surface it
    directly without re-querying the registry.
    """


def open_library(library_id: str):
    """Open a search-ready :class:`XinDBReader` for library *library_id*.

    The returned reader works with
    :func:`~xinmatch.core.db.search_v3.search_match_v3` and
    ``reader.fetch_peaks`` / ``reader.fetch_entry``.  **The caller owns it**:
    call :meth:`XinDBReader.close` when done (or use ``with``).

    Raises
    ------
    LibraryNotAvailableError
        If the library is missing or corrupt.  The message is GUI-friendly.
    """
    from .reader_v3 import XinDBReader

    rec = library_by_id(library_id)
    if rec is None:
        raise LibraryNotAvailableError(f"unknown library id: {library_id!r}")
    if not rec.available:
        raise LibraryNotAvailableError(
            f"library {rec.id!r} is not available: {rec.unavailable_reason}"
        )
    return XinDBReader(rec.path)


def open_search_database(db_path: str | Path):
    """Open *any* ``.xinDB`` file for search (CLI / batch convenience).

    Unlike :func:`open_library` this does not require the file to be
    registered first — handy for ``xinmatch search --db <path>.xinDB``.

    Raises
    ------
    FileNotFoundError
        The path does not exist.
    LibraryNotAvailableError
        Not a ``.xinDB`` file, or the file is not a usable v3 library.
    """
    from .reader_v3 import XinDBReader

    p = Path(db_path)
    if not p.is_file():
        raise FileNotFoundError(f"database file not found: {p}")
    if not _is_xindb(p):
        raise LibraryNotAvailableError(
            f"{p} 不是 .xinDB 库 —— v3.0.0 只支持 .xinDB（旧格式已移除）"
        )
    ok, reason = _probe_xindb(p)
    if not ok:
        raise LibraryNotAvailableError(f"{p} 不是可用的 .xinDB 库（{reason}）")
    return XinDBReader(p)


__all__ = [
    "DEFAULT_LIBRARY_ID",
    "KIND_XINDB",
    "ExternalLibrary",
    "LibraryNotAvailableError",
    "LibraryRecord",
    "add_external_library",
    "default_db_path",
    "library_by_id",
    "library_registry_path",
    "list_libraries",
    "load_external_libraries",
    "open_library",
    "open_search_database",
    "project_root",
    "remove_external_library",
    "resolve_default",
    "user_data_dir",
    "xindb_cod_full_path",
    "xindb_cod_inorg_path",
    "xindb_default_dir",
    "xindb_pcod_inorg_path",
    "xindb_tcod_inorg_path",
]
