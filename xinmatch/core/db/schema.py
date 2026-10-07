"""Database schema for the XinMatch reference database (Phase 5).

Implements the SQLite table layout that covers Match!'s 28 search fields
(elements, cell parameters, d-spacings, formula, mineral name, author,
journal, year, space group, crystal system, color, density, ...).

The DDL lives in :data:`SCHEMA_SQL` (mirrored in ``schema.sql`` next to this
module) and is applied by :func:`create_tables`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# Load the canonical DDL from the sibling ``schema.sql`` so there is a single
# source of truth (kept in sync by convention).
_SCHEMA_PATH = Path(__file__).with_name("schema.sql")
SCHEMA_SQL: str = _SCHEMA_PATH.read_text(encoding="utf-8")


def create_tables(conn: sqlite3.Connection) -> None:
    """Create all reference-database tables and indexes on *conn*.

    Implements Match!'s reference-database storage (Phase 5 / T5.2).
    Idempotent: every statement uses ``IF NOT EXISTS``.

    Parameters
    ----------
    conn:
        Open SQLite connection.  Caller is responsible for
        ``PRAGMA journal_mode=WAL`` and committing if desired.
    """
    conn.executescript(SCHEMA_SQL)


def enable_wal(conn: sqlite3.Connection) -> None:
    """Enable WAL journal mode for better concurrent-read performance.

    Parameters
    ----------
    conn:
        Open SQLite connection.
    """
    conn.execute("PRAGMA journal_mode=WAL")


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    """Return ``True`` if a table (or index) named *name* exists in *conn*.

    Parameters
    ----------
    conn:
        Open SQLite connection.
    name:
        Table / index name to check.
    """
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE name = ?",
        (name,),
    )
    return cur.fetchone() is not None
