"""Tests for user-database workflows (Phase 5 / T5.6)."""

from __future__ import annotations

import sqlite3

import numpy as np

from xinmatch.core.db.user_db import (
    add_entry,
    count_entries,
    create_user_database,
    list_entries,
    remove_entry,
)
from xinmatch.core.model import CellParams, Entry


def _make_entry(entry_id: str) -> Entry:
    return Entry(
        entry_id=entry_id,
        formula="B6 La",
        cell=CellParams(4.156, 4.156, 4.156),
        space_group="Pm-3m",
        d_spacings=np.array([4.156, 2.939, 2.400]),
        intensities=np.array([1000.0, 800.0, 600.0]),
    )


def test_create_user_database(tmp_path):
    from pathlib import Path

    p = Path(tmp_path) / "udb.db"
    conn = create_user_database(p)
    try:
        assert p.exists()
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='entries'")
        assert cur.fetchone() is not None
    finally:
        conn.close()


def test_add_and_list_entries(empty_conn: sqlite3.Connection):
    add_entry(empty_conn, _make_entry("U1"))
    add_entry(empty_conn, _make_entry("U2"))
    rows = list_entries(empty_conn)
    ids = [r[0] for r in rows]
    assert ids == ["U1", "U2"]


def test_count_entries(empty_conn: sqlite3.Connection):
    assert count_entries(empty_conn) == 0
    add_entry(empty_conn, _make_entry("U1"))
    assert count_entries(empty_conn) == 1


def test_remove_entry(empty_conn: sqlite3.Connection):
    add_entry(empty_conn, _make_entry("U1"))
    add_entry(empty_conn, _make_entry("U2"))
    assert remove_entry(empty_conn, "U1") is True
    assert count_entries(empty_conn) == 1
    # Peaks and elements for U1 should also be gone.
    cur = empty_conn.execute("SELECT COUNT(*) FROM peaks WHERE entry_id = 'U1'")
    assert cur.fetchone()[0] == 0
    cur = empty_conn.execute("SELECT COUNT(*) FROM elements WHERE entry_id = 'U1'")
    assert cur.fetchone()[0] == 0


def test_remove_nonexistent_returns_false(empty_conn: sqlite3.Connection):
    assert remove_entry(empty_conn, "NOPE") is False
