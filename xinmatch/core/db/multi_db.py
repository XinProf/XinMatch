"""Reference-database registry / multi-library mounting (core layer).

This module is the *core* of the multi-database feature: it knows how to find
and open every reference database XinMatch can search against, regardless of
the on-disk format.  The GUI layer (``xinmatch/ui``) is a separate subtask and
only consumes the public API below.

Three source formats are supported
----------------------------------
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

Default-library path resolution
-------------------------------
* **Development** — ``Path(__file__).resolve().parents[3]/"data"/"cod_inorganics.db"``
  (this file lives at ``xinmatch/core/db/multi_db.py``; ``parents[3]`` is the
  project root that contains the ``data/`` directory).
* **PyInstaller frozen** — ``Path(sys.executable).parent/"data"/"cod_inorganics.db"``,
  because the onedir bundle ships the DB at ``<exe-dir>/data/`` (verified on
  ``dist/xinmatch-1.0.0/``).

Match! packaged libraries (``D:\\Project\\XRD\\Match-COD\\*.mti`` ...) are
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

import logging
import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

from .schema import table_exists

logger = logging.getLogger(__name__)

#: library kinds
KIND_XINMATCH = "xinmatch"
KIND_PDF2 = "pdf2"
KIND_COD_FULL = "cod_full"

#: Directory of the external PolyXRD dumps (read-only inputs).  Override with
#: the ``XINMATCH_POLYXRD_DIR`` environment variable for other checkouts.
DEFAULT_POLYXRD_DIR = Path(
    os.environ.get(
        "XINMATCH_POLYXRD_DIR", r"D:\Project\XRD\PolyXRD\cod_data"
    )
)


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------
def project_root() -> Path:
    """Return the XinMatch project root (development layout).

    This module lives at ``<root>/xinmatch/core/db/multi_db.py``, so
    ``parents[3]`` is the directory that contains ``xinmatch/`` and ``data/``.
    """
    return Path(__file__).resolve().parents[3]


def default_db_path() -> Path:
    """Resolve the default bundled reference DB (``cod_inorganics.db``).

    Development layout: ``<project-root>/data/cod_inorganics.db``.
    Frozen (PyInstaller onedir) layout: ``<exe-dir>/data/cod_inorganics.db``.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "data" / "cod_inorganics.db"
    return project_root() / "data" / "cod_inorganics.db"


def cod_full_db_path() -> Path:
    """Where :mod:`tools.build_cod_full_xinmatch.py` writes its product.

    Same resolution rules as :func:`default_db_path` (``data/`` next to the
    package in dev, next to the exe when frozen).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "data" / "cod_full.db"
    return project_root() / "data" / "cod_full.db"


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


def pdf2_source_path() -> Path:
    """Source PolyXRD PDF-2 2004 dump (read-only input)."""
    return DEFAULT_POLYXRD_DIR / "PDF2_2004.sqlite"


def pdf2_sidecar_path() -> Path:
    """XinMatch-schema sidecar index built on top of the PDF-2 dump."""
    return user_data_dir() / "indexes" / "pdf2_2004_xinmatch.db"


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
        One of :data:`KIND_XINMATCH`, :data:`KIND_PDF2`, :data:`KIND_COD_FULL`.
    path:
        For ``xinmatch`` / ``cod_full``: the XinMatch-schema SQLite file that
        :func:`open_library` opens directly.  For ``pdf2``: the *source*
        PolyXRD dump (read-only); the opened file is the sidecar returned by
        :func:`pdf2_sidecar_path`.
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
    """

    id: str
    display_name: str
    kind: str
    path: Path
    entry_count: int | None = None
    available: bool = True
    unavailable_reason: str | None = None
    note: str | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _count_entries(db_path: Path) -> int | None:
    """Return ``COUNT(*) FROM entries`` for *db_path*, or ``None`` on error."""
    try:
        uri = "file:" + db_path.as_posix() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
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
        return LibraryRecord(
            id="pdf2_2004",
            display_name="ICDD PDF-2 2004 (via PolyXRD dump)",
            kind=KIND_PDF2,
            path=src,
            available=False,
            unavailable_reason=f"source dump not found: {src}",
            note="Expected at the PolyXRD cod_data directory; set XINMATCH_POLYXRD_DIR to override.",
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def list_libraries() -> list[LibraryRecord]:
    """Return all known reference libraries, with live availability status.

    The list order is the suggested picker order: the bundled default first,
    then optional external libraries.  Each record carries ``available`` and
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
    ]
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


def _open_ro(path: Path) -> sqlite3.Connection:
    """Open *path* read-only via the ``file:`` URI interface.

    SQLite opens WAL-mode databases cleanly in read-only mode as long as the
    directory is writable; for the source dumps we additionally never create
    or modify ``-wal`` / ``-shm`` sidecars.
    """
    uri = "file:" + path.as_posix() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
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
    return _open_ro(rec.path)


__all__ = [
    "KIND_XINMATCH",
    "KIND_PDF2",
    "KIND_COD_FULL",
    "LibraryNotAvailableError",
    "LibraryRecord",
    "cod_full_db_path",
    "default_db_path",
    "list_libraries",
    "library_by_id",
    "open_library",
    "pdf2_sidecar_path",
    "pdf2_source_path",
    "project_root",
    "resolve_default",
    "user_data_dir",
]
