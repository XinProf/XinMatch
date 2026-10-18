"""Database schema for the XinMatch reference database (Phase 5).

Implements the SQLite table layout that covers the reference software's 28 search fields
(elements, cell parameters, d-spacings, formula, mineral name, author,
journal, year, space group, crystal system, color, density, ...).

The DDL lives in :data:`SCHEMA_SQL` (mirrored in ``schema.sql`` next to this
module) and is applied by :func:`create_tables`.
"""

from __future__ import annotations

import sqlite3
from importlib import resources

# Load the canonical DDL from the sibling ``schema.sql`` so there is a single
# source of truth (kept in sync by convention).
#
# Read through :mod:`importlib.resources` rather than ``Path(__file__)`` so the
# module also works from a wheel / zip import, where ``schema.sql`` is a package
# resource instead of a loose file (declared in ``[tool.setuptools.package-data]``).
SCHEMA_SQL: str = (
    resources.files("xinmatch.core.db").joinpath("schema.sql").read_text(encoding="utf-8")
)


def create_tables(conn: sqlite3.Connection) -> None:
    """Create all reference-database tables and indexes on *conn*.

    Implements the reference software's reference-database storage (Phase 5 / T5.2).
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
