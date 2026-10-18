"""Reference-database registry / multi-library mounting (core layer).

This module is the *core* of the multi-database feature: it knows how to find
and open every reference database XinMatch can search against, regardless of
the on-disk format.  The GUI layer (``xinmatch/ui``) is a separate subtask and
only consumes the public API below.

Four source formats are supported
---------------------------------
``xinmatch``
    A native XinMatch-schema SQLite (``entries`` / ``peaks`` / ``elements`` /
    ``element_combo``).  This is the default bundled library
    ``data/cod_inorganics.db`` and any database built by
    ``tools/build_cod_full_xinmatch.py``.
``pdf2``
    The PolyXRD dump of the ICDD PDF-2 2004 database
    (``PDF2_2004.sqlite``).  Its ``phases`` table already carries parsed
    ``peaks_d`` / ``peaks_i`` strings, but the layout is *not* the XinMatch
    schema.  We therefore never search it in place: a **sidecar index** in
    XinMatch schema is built once (``pdf2_index.build_pdf2_index``) under the
    user data directory, and that sidecar is what we open for search.  The
    source ``.sqlite`` (and its ``-wal`` / ``-shm`` sidecars) is only ever
    opened read-only.
``cod_full``
    The full 113 k-entry COD database (``cod_index.sqlite``).  It has no peak
    table; peaks are computed from CIFs with gemmi.  The XinMatch-schema
    product is built by ``tools/build_cod_full_xinmatch.py`` (default output
    ``data/cod_full.db``).  Until that build has been run the library is
    reported as unavailable with a friendly reason.
``polyxrd`` (external, any location)
    A PolyXRD ``.sqlite`` database with a ``phases`` table (``peaks_d`` /
    ``peaks_i`` CSV columns).  It does **not** have to live in the install
    directory: :func:`add_external_library` registers any path the user picks,
    persists it in ``<user-data>/libraries.json`` and the GUI/CLI can mount it
    at runtime.  The first open converts it once into a XinMatch-schema sidecar
    under ``<user-data>/indexes/external/`` (:mod:`xinmatch.core.db.polyxrd`),
    keyed by the source's mtime/size so a rebuilt source is re-converted
    automatically.

Default-library path resolution
-------------------------------
* **Development** — ``Path(__file__).resolve().parents[3]/"data"/"cod_inorganics.db"``
  (this file lives at ``xinmatch/core/db/multi_db.py``; ``parents[3]`` is the
  project root that contains the ``data/`` directory).
* **PyInstaller frozen** — ``Path(sys.executable).parent/"data"/"cod_inorganics.db"``,
  because the onedir bundle ships the DB at ``<exe-dir>/data/`` (verified on
  ``dist/xinmatch-1.0.0/``).

The reference software packaged libraries (``D:\\Project\\XRD\\Match-COD\\*.mti`` ...) are
**not** mounted: they are proprietary binary indexes with no CIFs and no
SQLite, and the clean-room constraint forbids reverse-engineering them.  They
are intentionally absent from the registry.

Public API for the GUI subtask
------------------------------
* :func:`list_libraries` — all known libraries with availability + reasons.
* :func:`library_by_id` — lookup by stable id.
* :func:`open_library` — return a read-only :class:`sqlite3.Connection` that
  is fully compatible with
  :func:`~xinmatch.core.search.search_match.fetch_entries_by_ids` /
  :func:`~xinmatch.core.search.search_match.search_match` (raises
  :class:`LibraryNotAvailableError` when a library is missing / unbuilt).
* :func:`resolve_default` — the default bundled library record.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import polyxrd
from .schema import table_exists

logger = logging.getLogger(__name__)

#: library kinds
KIND_XINMATCH = "xinmatch"
KIND_PDF2 = "pdf2"
KIND_COD_FULL = "cod_full"
#: external PolyXRD ``.sqlite`` database mounted from an arbitrary path
KIND_POLYXRD = "polyxrd"

#: Optional built-in fallback directory for the external PolyXRD dumps
#: (read-only inputs).  ``None`` = not configured: the library is reported as
#: unavailable with an actionable reason and the user picks the directory in
#: the GUI (设置→参考数据库…) or sets ``XINMATCH_POLYXRD_DIR``.  A hard-coded
#: ``D:\Project\XRD\PolyXRD\cod_data`` default used to leak one developer's
#: machine layout into every install.
DEFAULT_POLYXRD_DIR: Path | None = None

#: Runtime PDF-2 source override set by the GUI (config ``pdf2_source_dir``).
#: When not ``None`` it takes precedence over the ``XINMATCH_POLYXRD_DIR`` env
#: var / :data:`DEFAULT_POLYXRD_DIR`.  ``None`` = not configured (fall back).
_pdf2_source_override: Path | None = None


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
    """Directory holding the bundled reference databases."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "data"
    return project_root() / "data"


def _with_sqlite_fallback(base: Path) -> Path:
    """Return *base*, or its ``.sqlite`` sibling when only that exists.

    v2.0.0: PolyXRD now packages its databases with a ``.sqlite`` extension, and
    XinMatch's own bundles are moving the same way.  Both spellings are
    accepted so users can drop either file into ``data/`` (or mount either one
    from an arbitrary folder) without renaming.
    """
    if base.exists():
        return base
    alt = base.with_suffix(".sqlite")
    if alt.exists():
        return alt
    return base


def default_db_path() -> Path:
    """Resolve the default bundled reference DB (``cod_inorganics.db``).

    Development layout: ``<project-root>/data/cod_inorganics.db``.
    Frozen (PyInstaller onedir) layout: ``<exe-dir>/data/cod_inorganics.db``.
    A ``cod_inorganics.sqlite`` file is accepted as an alternative spelling.
    """
    return _with_sqlite_fallback(_data_dir() / "cod_inorganics.db")


def cod_full_db_path() -> Path:
    """Where :mod:`tools.build_cod_full_xinmatch.py` writes its product.

    Same resolution rules as :func:`default_db_path` (``data/`` next to the
    package in dev, next to the exe when frozen); ``.sqlite`` accepted.
    """
    return _with_sqlite_fallback(_data_dir() / "cod_full.db")


def cod_full_curated_db_path() -> Path:
    """Where :mod:`tools.build_cod_full_curated.py` writes its product.

    The curated de-duplicated copy keeps one card per
    (``formula``, ``space_group``) cluster of the full COD DB so the FoM
    ranking is no longer diluted by near-duplicate cards.  Same resolution
    rules as :func:`default_db_path`; ``.sqlite`` accepted.
    """
    return _with_sqlite_fallback(_data_dir() / "cod_full_curated.db")


def user_data_dir() -> Path:
    """Writable per-user data directory.

    Defaults to ``%USERPROFILE%\\.xinmatch`` (i.e. ``~/.xinmatch``); override
    with ``XINMATCH_USER_DATA``.  Sidecar search indexes live under
    ``<user_data_dir>/indexes/`` so that the read-only source directories
    (PolyXRD dumps, the install dir) are never written to.
    """
    override = os.environ.get("XINMATCH_USER_DATA")
    if override:
        return Path(override)
    return Path.home() / ".xinmatch"


def set_pdf2_source_dir(path: str | Path | None) -> None:
    """Set / clear the GUI-level PDF-2 source override.

    Precedence inside :func:`pdf2_source_path` is:

    1. this override (GUI / YAML config);
    2. the ``XINMATCH_POLYXRD_DIR`` environment variable;
    3. the built-in :data:`DEFAULT_POLYXRD_DIR`.

    Parameters
    ----------
    path:
        Either a directory that contains ``PDF2_2004.sqlite`` (the resolved
        path becomes ``<dir>/PDF2_2004.sqlite``), or the ``.sqlite`` file
        itself (used directly).  Pass ``None`` to clear the override and
        fall back to the env var / default directory.
    """
    global _pdf2_source_override
    _pdf2_source_override = Path(path) if path is not None else None


def polyxrd_dir() -> Path | None:
    """Return the configured PolyXRD dump directory, or ``None``.

    Resolution order: GUI/config override (its parent when the override is a
    ``.sqlite`` file) → ``XINMATCH_POLYXRD_DIR`` → :data:`DEFAULT_POLYXRD_DIR`.
    ``None`` means "not configured", which callers surface as a friendly
    reason instead of guessing a machine-specific path.
    """
    override = _pdf2_source_override
    if override is not None:
        if override.suffix.lower() == ".sqlite":
            return override.parent
        return override
    env = os.environ.get("XINMATCH_POLYXRD_DIR")
    if env:
        return Path(env)
    return DEFAULT_POLYXRD_DIR


def pdf2_source_path() -> Path:
    """Source PolyXRD PDF-2 2004 dump (read-only input).

    A GUI/config override (see :func:`set_pdf2_source_dir`) wins over the
    ``XINMATCH_POLYXRD_DIR`` env var / :data:`DEFAULT_POLYXRD_DIR`.  When
    nothing is configured this returns the conventional
    ``~/PolyXRD/cod_data/PDF2_2004.sqlite`` so error messages name a plausible
    location; callers must check :func:`polyxrd_dir` to tell "unconfigured"
    from "configured but missing".
    """
    override = _pdf2_source_override
    if override is not None:
        if override.is_dir():
            return override / "PDF2_2004.sqlite"
        if override.is_file():
            return override
        # Path does not (yet) exist: decide by extension so a directory-style
        # config still resolves to the conventional file name.
        if override.suffix.lower() == ".sqlite":
            return override
        return override / "PDF2_2004.sqlite"
    base = polyxrd_dir()
    if base is None:
        return Path.home() / "PolyXRD" / "cod_data" / "PDF2_2004.sqlite"
    return base / "PDF2_2004.sqlite"


def pdf2_sidecar_path() -> Path:
    """XinMatch-schema sidecar index built on top of the PDF-2 dump."""
    return user_data_dir() / "indexes" / "pdf2_2004_xinmatch.db"


# ---------------------------------------------------------------------------
# External library registry (v2.0.0)
# ---------------------------------------------------------------------------
#: JSON registry of user-mounted databases (any folder, any ``.db``/``.sqlite``).
#: Kept out of the GUI YAML on purpose: it is *data*, not a look preference, and
#: the CLI must be able to add/list libraries without importing Qt.
_REGISTRY_VERSION = 1


@dataclass(frozen=True)
class ExternalLibrary:
    """A user-mounted reference database (path + label + stable id).

    Attributes
    ----------
    id:
        Stable ``ext_<hash>`` identifier derived from the resolved absolute
        path, so re-adding the same file is idempotent and the config keeps
        pointing at a valid id after a restart.
    path:
        Absolute path to the ``.db`` / ``.sqlite`` file (any folder).
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
            out.append(
                ExternalLibrary(
                    id=str(item["id"]),
                    path=Path(str(item["path"])),
                    label=str(item.get("label") or ""),
                )
            )
        except (KeyError, TypeError):  # pragma: no cover - hand-edited file
            logger.warning("skipping malformed registry entry: %r", item)
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


def add_external_library(
    path: str | Path, label: str | None = None
) -> ExternalLibrary:
    """Register an external database located anywhere on disk.

    The file is validated first: it must be a searchable XinMatch-schema OR
    PolyXRD ``phases`` database.  PolyXRD *structure-only* dumps
    (``cod_index.sqlite``) are rejected with an actionable message instead of
    being mounted as an empty library.

    Re-adding the same path updates the label and keeps the same id, so the
    config's ``selected_library_id`` never dangles.

    Raises
    ------
    FileNotFoundError
        The path does not exist.
    ValueError
        The file is not a supported reference database.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"database file not found: {p}")
    schema = polyxrd.detect_source(p)
    if not schema.searchable:
        raise ValueError(schema.reason or f"unsupported database format: {p}")

    lib_id = _external_id(p)
    entry = ExternalLibrary(
        id=lib_id,
        path=p.resolve(),
        label=(label or "").strip(),
    )
    existing = [lib for lib in load_external_libraries() if lib.id != lib_id]
    existing.append(entry)
    _save_external_libraries(existing)
    logger.info("mounted external library %s -> %s", lib_id, entry.path)
    return entry


def remove_external_library(library_id: str) -> bool:
    """Unregister *library_id*; returns ``True`` when it existed.

    Only the registry entry is removed — the sidecar cache and, of course, the
    source database are left untouched.
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
    """A single mountable reference database.

    Attributes
    ----------
    id:
        Stable short identifier (used by the GUI as a key, never displayed as
       -is).
    display_name:
        Human-readable name for the library picker.
    kind:
        One of :data:`KIND_XINMATCH`, :data:`KIND_PDF2`,
        :data:`KIND_COD_FULL`, :data:`KIND_POLYXRD`.
    path:
        For ``xinmatch`` / ``cod_full``: the XinMatch-schema SQLite file that
        :func:`open_library` opens directly.  For ``pdf2``: the *source*
        PolyXRD dump (read-only); the opened file is the sidecar returned by
        :func:`pdf2_sidecar_path`.  For ``polyxrd``: the mounted ``.sqlite``
        source at whatever path the user chose.
    entry_count:
        Number of entries in the opened database, or ``None`` when it has not
        been queried yet (lazy).
    available:
        Whether :func:`open_library` will succeed.
    unavailable_reason:
        Human-readable reason when ``available`` is ``False`` (GUI shows this
        and falls back to the default library).
    note:
        Optional extra context (e.g. where the sidecar lives, how to build a
        missing database).
    needs_index:
        ``True`` when the library is searchable but its converted index has not
        been built yet (:class:`LibraryNeedsIndexError` on open).
    sidecar:
        Path of the converted XinMatch-schema index (``polyxrd`` kind only).
    external:
        ``True`` for user-mounted libraries (shown with their own path in the
        picker, removable from the dialog).
    """

    id: str
    display_name: str
    kind: str
    path: Path
    entry_count: int | None = None
    available: bool = True
    unavailable_reason: str | None = None
    note: str | None = None
    needs_index: bool = False
    sidecar: Path | None = None
    external: bool = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _readonly_uri(path: Path) -> str:
    """Return a ``file:`` URI for *path* that is safe for special characters.

    ``#`` starts a URI fragment and ``?`` starts the query we append, so a
    database living in e.g. ``C:/data #2/lib.db`` would previously be silently
    truncated (or fail to open).  :meth:`Path.as_uri` percent-encodes ``#``,
    ``?``, spaces and non-ASCII characters, which SQLite decodes again.
    """
    try:
        return path.resolve().as_uri() + "?mode=ro"
    except ValueError:  # pragma: no cover - relative path, defensive
        return "file:" + path.as_posix() + "?mode=ro"


def _count_entries(db_path: Path) -> int | None:
    """Return ``COUNT(*) FROM entries`` for *db_path*, or ``None`` on error."""
    try:
        conn = sqlite3.connect(_readonly_uri(db_path), uri=True)
        try:
            if not table_exists(conn, "entries"):
                return None
            cur = conn.execute("SELECT COUNT(*) FROM entries")
            return int(cur.fetchone()[0])
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        return None


def _xinmatch_record(
    lib_id: str,
    display_name: str,
    kind: str,
    path: Path,
    note: str | None = None,
) -> LibraryRecord:
    """Build a LibraryRecord for a native XinMatch-schema database."""
    if not path.exists():
        return LibraryRecord(
            id=lib_id,
            display_name=display_name,
            kind=kind,
            path=path,
            available=False,
            unavailable_reason=f"database file not found: {path}",
            note=note,
        )
    n = _count_entries(path)
    if n is None:
        return LibraryRecord(
            id=lib_id,
            display_name=display_name,
            kind=kind,
            path=path,
            available=False,
            unavailable_reason=f"not a XinMatch-schema database (no entries table): {path}",
            note=note,
        )
    return LibraryRecord(
        id=lib_id,
        display_name=display_name,
        kind=kind,
        path=path,
        entry_count=n,
        available=True,
        note=note,
    )


def _pdf2_record() -> LibraryRecord:
    """Build the PDF-2 (``pdf2``) registry entry.

    The source dump itself is not searchable in XinMatch schema; we check both
    that the source exists (read-only) and that the sidecar index has been
    built.  Missing sidecar → unavailable with a reason pointing at the build
    entry point.
    """
    src = pdf2_source_path()
    sidecar = pdf2_sidecar_path()
    if not src.exists():
        unconfigured = (
            _pdf2_source_override is None
            and not os.environ.get("XINMATCH_POLYXRD_DIR")
            and DEFAULT_POLYXRD_DIR is None
        )
        return LibraryRecord(
            id="pdf2_2004",
            display_name="ICDD PDF-2 2004 (via PolyXRD dump)",
            kind=KIND_PDF2,
            path=src,
            available=False,
            unavailable_reason=(
                "PDF-2 source directory not configured; pick it in "
                "设置→参考数据库… or set XINMATCH_POLYXRD_DIR"
                if unconfigured
                else f"source dump not found: {src}"
            ),
            note="Expected in the PolyXRD cod_data directory (PDF2_2004.sqlite).",
        )
    if not sidecar.exists():
        return LibraryRecord(
            id="pdf2_2004",
            display_name="ICDD PDF-2 2004 (via PolyXRD dump)",
            kind=KIND_PDF2,
            path=src,
            available=False,
            unavailable_reason=(
                "sidecar search index not built yet; run "
                "`python -m xinmatch.core.db.pdf2_index` (one-off, ~minutes)."
            ),
            note=f"source is read-only at {src}; sidecar would be built at {sidecar}",
        )
    n = _count_entries(sidecar)
    if n is None:
        return LibraryRecord(
            id="pdf2_2004",
            display_name="ICDD PDF-2 2004 (via PolyXRD dump)",
            kind=KIND_PDF2,
            path=src,
            available=False,
            unavailable_reason=f"sidecar is corrupt (no entries table): {sidecar}",
        )
    return LibraryRecord(
        id="pdf2_2004",
        display_name="ICDD PDF-2 2004 (via PolyXRD dump)",
        kind=KIND_PDF2,
        path=src,
        entry_count=n,
        available=True,
        note=f"searchable sidecar: {sidecar} (source opened read-only)",
    )


def _external_record(ext: ExternalLibrary) -> LibraryRecord:
    """Build the registry record for a user-mounted database at an arbitrary path.

    XinMatch-schema files are opened directly; PolyXRD ``phases`` databases get
    a converted sidecar (built lazily, so the record first reports
    ``needs_index=True`` with the source row count as an estimate).
    """
    schema = polyxrd.detect_source(ext.path)
    name = ext.display_name

    if schema.kind == polyxrd.SCHEMA_XINMATCH:
        rec = _xinmatch_record(
            ext.id,
            name,
            KIND_XINMATCH,
            ext.path,
            note="外部挂载（XinMatch 格式）：直接从该路径读取",
        )
        return LibraryRecord(
            id=rec.id,
            display_name=rec.display_name,
            kind=rec.kind,
            path=rec.path,
            entry_count=rec.entry_count,
            available=rec.available,
            unavailable_reason=rec.unavailable_reason,
            note=rec.note,
            external=True,
        )

    if schema.kind == polyxrd.SCHEMA_POLYXRD:
        sidecar = polyxrd.sidecar_path_for(ext.path)
        fresh = polyxrd.sidecar_is_fresh(ext.path, sidecar)
        count = _count_entries(sidecar) if fresh else schema.row_count
        return LibraryRecord(
            id=ext.id,
            display_name=name,
            kind=KIND_POLYXRD,
            path=ext.path.resolve(),
            entry_count=count,
            available=True,
            needs_index=not fresh,
            sidecar=sidecar,
            external=True,
            note=(
                f"PolyXRD 数据库：源文件 {ext.path.resolve()}（只读）；"
                + (
                    f"已建立检索索引 {sidecar.name}"
                    if fresh
                    else "首次检索前需建立索引（约 1–2 分钟，可取消）"
                )
            ),
        )

    return LibraryRecord(
        id=ext.id,
        display_name=name,
        kind=KIND_POLYXRD,
        path=ext.path,
        available=False,
        unavailable_reason=schema.reason or f"unsupported database format: {ext.path}",
        external=True,
        note="外部挂载：仅支持 XinMatch 格式或 PolyXRD phases 表（含 peaks_d/peaks_i）",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def list_libraries() -> list[LibraryRecord]:
    """Return all known reference libraries, with live availability status.

    The list order is the suggested picker order: the bundled default first,
    then the optional built-ins, then every user-mounted external database
    (``external=True``).  Each record carries ``available`` and
    ``unavailable_reason`` so the GUI can show friendly labels and grey out
    (and fall back to the default library for) missing ones.
    """
    out: list[LibraryRecord] = [
        _xinmatch_record(
            "cod_inorganics",
            "COD Inorganics (default, bundled)",
            KIND_XINMATCH,
            default_db_path(),
            note="Shipped with XinMatch; 71,199 inorganic COD phases.",
        ),
        _pdf2_record(),
        _xinmatch_record(
            "cod_full",
            "COD full database (113k phases, CIF-computed peaks)",
            KIND_COD_FULL,
            cod_full_db_path(),
            note=(
                "Built from the 522k-CIF archive by "
                "`python -m tools.build_cod_full_xinmatch`; not built by default."
            ),
        ),
        _xinmatch_record(
            "cod_full_curated",
            "COD full curated (one card per formula+space_group cluster)",
            KIND_XINMATCH,
            cod_full_curated_db_path(),
            note=(
                "De-duplicated copy of cod_full.db: keeps the highest-quality "
                "card per (formula, space_group) cluster so FoM ranking is not "
                "diluted by near-duplicates.  Build with "
                "`python -m tools.build_cod_full_curated`."
            ),
        ),
    ]
    for ext in load_external_libraries():
        out.append(_external_record(ext))
    return out


def library_by_id(library_id: str) -> LibraryRecord | None:
    """Return the :class:`LibraryRecord` with *library_id*, or ``None``."""
    for rec in list_libraries():
        if rec.id == library_id:
            return rec
    return None


def resolve_default() -> LibraryRecord:
    """Return the default library record (``cod_inorganics``).

    This always returns a record (never raises); callers must check
    ``available`` themselves.  If the bundled DB is missing the record reports
    ``available=False`` with the path that was expected.
    """
    return _xinmatch_record(
        "cod_inorganics",
        "COD Inorganics (default, bundled)",
        KIND_XINMATCH,
        default_db_path(),
    )


class LibraryNotAvailableError(RuntimeError):
    """Raised by :func:`open_library` when the requested library cannot be opened.

    The exception message carries the same friendly reason as
    ``LibraryRecord.unavailable_reason`` so CLI / GUI callers can surface it
    directly without re-querying the registry.
    """


class LibraryNeedsIndexError(LibraryNotAvailableError):
    """The library is mounted but its converted index has not been built yet.

    Callers should run :func:`ensure_library_index` (progress + cancellation
    supported) and then retry :func:`open_library`.  The GUI does this inside
    its busy dialog; the CLI does it synchronously.
    """

    def __init__(self, library_id: str, source: Path, sidecar: Path) -> None:
        self.library_id = library_id
        self.source = source
        self.sidecar = sidecar
        super().__init__(
            f"参考数据库「{library_id}」已挂载但尚未建立检索索引"
            f"（源文件：{source}）。首次检索前需要转换一次。"
        )


def _open_ro(path: Path) -> sqlite3.Connection:
    """Open *path* read-only via the ``file:`` URI interface.

    SQLite opens WAL-mode databases cleanly in read-only mode as long as the
    directory is writable; for the source dumps we additionally never create
    or modify ``-wal`` / ``-shm`` sidecars.

    ``check_same_thread=False``：GUI 检索在忙碌窗口的工作线程里使用主线程
    创建的连接（v1.3.1 ``run_with_busy``），只读访问配合忙碌窗口的重入保护
    保证串行使用，不会并发读写同一连接。
    """
    conn = sqlite3.connect(
        _readonly_uri(path), uri=True, check_same_thread=False
    )
    conn.execute("PRAGMA query_only = ON")
    return conn


def open_library(library_id: str) -> sqlite3.Connection:
    """Open a search-ready, read-only connection to library *library_id*.

    The returned connection targets a **XinMatch-schema** database, so it can
    be handed straight to
    :func:`~xinmatch.core.search.search_match.search_match` and
    :func:`~xinmatch.core.search.search_match.fetch_entries_by_ids`.

    Parameters
    ----------
    library_id:
        Registry id (see :func:`list_libraries`).

    Raises
    ------
    LibraryNotAvailableError
        If the library is missing, not yet built, or corrupt.  The message is
        GUI-friendly.
    """
    rec = library_by_id(library_id)
    if rec is None:
        raise LibraryNotAvailableError(f"unknown library id: {library_id!r}")
    if not rec.available:
        raise LibraryNotAvailableError(
            f"library {rec.id!r} is not available: {rec.unavailable_reason}"
        )
    if rec.kind == KIND_PDF2:
        # The source dump is never opened for search; open the XinMatch-schema
        # sidecar instead.
        return _open_ro(pdf2_sidecar_path())
    if rec.kind == KIND_POLYXRD:
        sidecar = rec.sidecar or polyxrd.sidecar_path_for(rec.path)
        if not polyxrd.sidecar_is_fresh(rec.path, sidecar):
            raise LibraryNeedsIndexError(rec.id, rec.path, sidecar)
        return _open_ro(sidecar)
    return _open_ro(rec.path)


def ensure_library_index(
    library_id: str,
    *,
    force: bool = False,
    max_peaks: int = polyxrd.DEFAULT_MAX_PEAKS,
    progress: Callable[[int], None] | None = None,
) -> dict[str, Any] | None:
    """Build (or rebuild) the converted index for a mounted PolyXRD database.

    Parameters
    ----------
    library_id:
        Registry id (built-in or external).
    force:
        Rebuild even when the cached sidecar still matches the source.
    max_peaks:
        Strongest reflections kept per phase.
    progress:
        Called with the number of entries written so far.

    Returns
    -------
    dict | None
        Build summary, or ``None`` when nothing had to be built (fresh cache)
        or the library does not need conversion at all.
    """
    rec = library_by_id(library_id)
    if rec is None:
        raise LibraryNotAvailableError(f"unknown library id: {library_id!r}")
    if rec.kind != KIND_POLYXRD:
        return None
    _sidecar, summary = polyxrd.ensure_sidecar(
        rec.path, force=force, max_peaks=max_peaks, progress=progress
    )
    return summary


def open_search_database(
    db_path: str | Path,
    *,
    build_index: bool = True,
    progress: Callable[[int], None] | None = None,
) -> sqlite3.Connection:
    """Open *any* supported database file for search (CLI / batch convenience).

    Accepts a native XinMatch database (opened directly) or a PolyXRD
    ``.sqlite`` file at any path (converted once into the cached sidecar, then
    opened).  Unlike :func:`open_library` this does **not** require the file to
    be registered first — handy for ``xinmatch search --db <path>``.

    Raises
    ------
    FileNotFoundError
        The path does not exist.
    LibraryNotAvailableError
        Unsupported schema, or the index is missing and *build_index* is False.
    """
    p = Path(db_path)
    if not p.is_file():
        raise FileNotFoundError(f"database file not found: {p}")
    schema = polyxrd.detect_source(p)
    if schema.kind == polyxrd.SCHEMA_XINMATCH:
        return _open_ro(p)
    if schema.kind == polyxrd.SCHEMA_POLYXRD:
        sidecar = polyxrd.sidecar_path_for(p)
        if not build_index and not polyxrd.sidecar_is_fresh(p, sidecar):
            raise LibraryNeedsIndexError(
                _external_id(p), p, sidecar
            )
        sidecar, summary = polyxrd.ensure_sidecar(p, progress=progress)
        if summary is not None:
            logger.info(
                "converted PolyXRD database %s -> %s (%s entries, %.1fs)",
                p,
                sidecar,
                summary.get("entries_indexed"),
                float(summary.get("seconds") or 0.0),
            )
        return _open_ro(sidecar)
    raise LibraryNotAvailableError(
        schema.reason or f"unsupported database format: {p}"
    )


__all__ = [
    "KIND_XINMATCH",
    "KIND_PDF2",
    "KIND_COD_FULL",
    "KIND_POLYXRD",
    "ExternalLibrary",
    "LibraryNeedsIndexError",
    "LibraryNotAvailableError",
    "LibraryRecord",
    "add_external_library",
    "cod_full_curated_db_path",
    "cod_full_db_path",
    "default_db_path",
    "ensure_library_index",
    "library_by_id",
    "library_registry_path",
    "list_libraries",
    "load_external_libraries",
    "open_library",
    "open_search_database",
    "pdf2_sidecar_path",
    "pdf2_source_path",
    "project_root",
    "remove_external_library",
    "resolve_default",
    "set_pdf2_source_dir",
    "user_data_dir",
]
