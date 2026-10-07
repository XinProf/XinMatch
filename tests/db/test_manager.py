"""Tests for database library management (Phase 5 / T5.7)."""

from __future__ import annotations

from pathlib import Path

from xinmatch.core.db.manager import (
    create_database,
    database_entry_count,
    delete_database,
    list_databases,
)


def test_create_database_creates_file(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = create_database(db_path)
    try:
        assert db_path.exists()
        # Schema should be present.
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='entries'")
        assert cur.fetchone() is not None
    finally:
        conn.close()


def test_list_databases(tmp_path: Path):
    create_database(tmp_path / "a.db").close()
    create_database(tmp_path / "b.db").close()
    (tmp_path / "not_a_db.txt").write_text("hello")

    dbs = list_databases(tmp_path)
    names = sorted(p.name for p in dbs)
    assert names == ["a.db", "b.db"]


def test_list_databases_nonexistent_dir():
    assert list_databases("/nonexistent/path/xyz") == []


def test_delete_database(tmp_path: Path):
    db_path = tmp_path / "del.db"
    create_database(db_path).close()
    assert db_path.exists()
    assert delete_database(db_path) is True
    assert not db_path.exists()


def test_delete_database_missing_returns_false(tmp_path: Path):
    assert delete_database(tmp_path / "missing.db") is False


def test_multiple_databases_coexist(tmp_path: Path):
    """Acceptance: multiple databases in one directory do not conflict."""
    p1 = tmp_path / "cod.db"
    p2 = tmp_path / "user.db"
    c1 = create_database(p1)
    c2 = create_database(p2)
    try:
        # Insert into c1 only.
        import numpy as np

        from xinmatch.core.db.build_cod import insert_entry
        from xinmatch.core.model import CellParams, Entry

        insert_entry(c1, Entry(
            entry_id="X1",
            formula="Si O2",
            cell=CellParams(5.0, 5.0, 5.0),
            space_group="P3221",
            d_spacings=np.array([3.0]),
            intensities=np.array([1000.0]),
        ))
        c1.commit()
        assert database_entry_count(p1) == 1
        assert database_entry_count(p2) == 0
    finally:
        c1.close()
        c2.close()
