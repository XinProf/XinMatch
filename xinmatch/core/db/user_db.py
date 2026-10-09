"""User-database (UDB) helpers (Phase 5 / T5.6).

The reference software allows users to maintain their own reference databases ("user
databases") alongside the COD library.  This module wraps the low-level
insert functions in :mod:`build_cod` and provides UDB-specific operations:
creating a fresh UDB file, adding / removing entries, and listing contents.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from xinmatch.core.model import Entry

from .build_cod import insert_entries, insert_entry
from .schema import create_tables, enable_wal

logger = logging.getLogger(__name__)


def create_user_database(path: str | Path) -> sqlite3.Connection:
    """Create (or open) a user-database SQLite file at *path*.

    Implements the reference software's *Reference Database → Create User Database*.

    Parameters
    ----------
    path:
        Filesystem path for the ``.db`` file.

    Returns
    -------
    sqlite3.Connection
        Open connection with schema applied and WAL mode enabled.
    """
    conn = sqlite3.connect(str(path))
    enable_wal(conn)
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)
    logger.info("created user database at %s", path)
    return conn


def add_entry(conn: sqlite3.Connection, entry: Entry) -> None:
    """Add a single entry to the user database.

    Thin wrapper over :func:`build_cod.insert_entry` kept for semantic clarity
    in UDB workflows.

    Parameters
    ----------
    conn:
        Open user-database connection.
    entry:
        Entry to add.
    """
    insert_entry(conn, entry)


def add_entries(conn: sqlite3.Connection, entries: Iterable[Entry]) -> int:
    """Add multiple entries to the user database.

    Parameters
    ----------
    conn:
        Open user-database connection.
    entries:
        Entries to add.

    Returns
    -------
    int
        Number of entries added.
    """
    return insert_entries(conn, entries)


def remove_entry(conn: sqlite3.Connection, entry_id: str) -> bool:
    """Remove an entry (and its peaks / element rows) from the database.

    Implements the reference software's *Reference Database → Delete Entry*.

    Parameters
    ----------
    conn:
        Open database connection.
    entry_id:
        Identifier of the entry to delete.

    Returns
    -------
    bool
        ``True`` if at least one row was deleted.
    """
    with conn:
        cur = conn.execute("DELETE FROM peaks WHERE entry_id = ?", (entry_id,))
        peaks_deleted = cur.rowcount
        cur = conn.execute("DELETE FROM elements WHERE entry_id = ?", (entry_id,))
        elem_deleted = cur.rowcount
        cur = conn.execute("DELETE FROM entries WHERE entry_id = ?", (entry_id,))
        entry_deleted = cur.rowcount
    logger.debug(
        "removed entry %s (entries=%d, peaks=%d, elements=%d)",
        entry_id, entry_deleted, peaks_deleted, elem_deleted,
    )
    return entry_deleted > 0


def list_entries(conn: sqlite3.Connection) -> list[tuple[str, str, str | None]]:
    """List (entry_id, formula, mineral_name) for every entry in the database.

    Parameters
    ----------
    conn:
        Open database connection.

    Returns
    -------
    list[tuple[str, str, str | None]]
        One tuple per entry, ordered by entry_id.
    """
    cur = conn.execute(
        "SELECT entry_id, formula, mineral_name FROM entries ORDER BY entry_id",
    )
    return cur.fetchall()


def count_entries(conn: sqlite3.Connection) -> int:
    """Return the number of entries stored in the database.

    Parameters
    ----------
    conn:
        Open database connection.
    """
    cur = conn.execute("SELECT COUNT(*) FROM entries")
    return int(cur.fetchone()[0])
