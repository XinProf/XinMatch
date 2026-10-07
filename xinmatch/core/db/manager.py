"""Database library management (Phase 5 / T5.7).

Implements Match!'s *Reference Database* manager: list, create, and delete
reference-database files (COD library + user databases).  Multiple databases
coexist as separate ``.db`` files under a single directory.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from .schema import create_tables, enable_wal

logger = logging.getLogger(__name__)

DB_SUFFIX = ".db"


def list_databases(db_dir: str | Path) -> list[Path]:
    """List all reference-database files in *db_dir*.

    Implements Match!'s *Reference Database → Open* library listing.

    Parameters
    ----------
    db_dir:
        Directory containing ``.db`` files.

    Returns
    -------
    list[Path]
        Paths to ``.db`` files, sorted by name.  Returns an empty list if the
        directory does not exist.
    """
    p = Path(db_dir)
    if not p.is_dir():
        return []
    return sorted(p.glob(f"*{DB_SUFFIX}"))


def create_database(path: str | Path) -> sqlite3.Connection:
    """Create a new reference database at *path*.

    Implements Match!'s *Reference Database → Create*.  The file is created
    with the full schema and WAL mode enabled.  If a file already exists it is
    opened (tables are created with ``IF NOT EXISTS``).

    Parameters
    ----------
    path:
        Filesystem path for the ``.db`` file.

    Returns
    -------
    sqlite3.Connection
        Open connection to the new database.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    enable_wal(conn)
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)
    logger.info("created database at %s", p)
    return conn


def delete_database(path: str | Path) -> bool:
    """Delete a reference-database file.

    Implements Match!'s *Reference Database → Delete*.

    Parameters
    ----------
    path:
        Path to the ``.db`` file to delete.

    Returns
    -------
    bool
        ``True`` if the file was deleted, ``False`` if it did not exist.
    """
    p = Path(path)
    if not p.exists():
        return False
    p.unlink()
    # Also remove WAL / SHM sidecar files if present.
    for sidecar in (p.with_suffix(".db-wal"), p.with_suffix(".db-shm")):
        if sidecar.exists():
            sidecar.unlink()
    logger.info("deleted database at %s", p)
    return True


def database_entry_count(path: str | Path) -> int:
    """Return the number of entries stored in *path* without opening long-term.

    Parameters
    ----------
    path:
        Path to a ``.db`` file.
    """
    p = Path(path)
    if not p.exists():
        return 0
    conn = sqlite3.connect(str(p))
    try:
        cur = conn.execute("SELECT COUNT(*) FROM entries")
        return int(cur.fetchone()[0])
    finally:
        conn.close()
