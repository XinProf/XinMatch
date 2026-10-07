"""Tests for entry insertion (Phase 5 / T5.1, T5.6)."""

from __future__ import annotations

import sqlite3

import numpy as np

from xinmatch.core.db.build_cod import insert_entries, insert_entry
from xinmatch.core.model import CellParams, Entry


def _lab6_entry(entry_id: str = "LAB6") -> Entry:
    return Entry(
        entry_id=entry_id,
        formula="B6 La",
        mineral_name="Lanthanum hexaboride",
        cell=CellParams(4.156, 4.156, 4.156),
        space_group="Pm-3m",
        d_spacings=np.array([4.156, 2.939, 2.400, 2.078, 1.859]),
        intensities=np.array([1000.0, 800.0, 600.0, 400.0, 200.0]),
        hkl=[(1, 0, 0), (1, 1, 0), (1, 1, 1), (2, 0, 0), (2, 1, 0)],
        literature={"author": "Tanaka", "journal": "JAC", "year": 1971},
        quality="A",
    )


def test_insert_entry_creates_rows(empty_conn: sqlite3.Connection):
    entry = _lab6_entry()
    insert_entry(empty_conn, entry)

    cur = empty_conn.execute("SELECT formula, space_group, quality FROM entries WHERE entry_id = ?", ("LAB6",))
    row = cur.fetchone()
    assert row is not None
    assert row[0] == "B6 La"
    assert row[1] == "Pm-3m"
    assert row[2] == "A"


def test_insert_entry_writes_peaks(empty_conn: sqlite3.Connection):
    entry = _lab6_entry()
    insert_entry(empty_conn, entry)
    cur = empty_conn.execute("SELECT COUNT(*) FROM peaks WHERE entry_id = ?", ("LAB6",))
    assert cur.fetchone()[0] == 5

    cur = empty_conn.execute(
        "SELECT d, h, k, l FROM peaks WHERE entry_id = ? ORDER BY d DESC",
        ("LAB6",),
    )
    ds = [r[0] for r in cur.fetchall()]
    np.testing.assert_allclose(ds, [4.156, 2.939, 2.400, 2.078, 1.859], atol=1e-6)


def test_insert_entry_writes_elements(empty_conn: sqlite3.Connection):
    entry = _lab6_entry()
    insert_entry(empty_conn, entry)
    cur = empty_conn.execute("SELECT element FROM elements WHERE entry_id = ? ORDER BY element", ("LAB6",))
    elems = [r[0] for r in cur.fetchall()]
    assert elems == ["B", "La"]


def test_insert_entry_stores_crystal_system(empty_conn: sqlite3.Connection):
    entry = _lab6_entry()
    insert_entry(empty_conn, entry)
    cur = empty_conn.execute("SELECT crystal_system FROM entries WHERE entry_id = ?", ("LAB6",))
    assert cur.fetchone()[0] == "cubic"


def test_insert_entry_stores_cell_and_year(empty_conn: sqlite3.Connection):
    entry = _lab6_entry()
    insert_entry(empty_conn, entry)
    cur = empty_conn.execute(
        "SELECT a, b, c, year, author, journal FROM entries WHERE entry_id = ?",
        ("LAB6",),
    )
    a, b, c, year, author, journal = cur.fetchone()
    assert a == 4.156
    assert b == 4.156
    assert c == 4.156
    assert year == 1971
    assert author == "Tanaka"
    assert journal == "JAC"


def test_insert_entry_replaces_existing(empty_conn: sqlite3.Connection):
    e1 = _lab6_entry("E1")
    insert_entry(empty_conn, e1)
    e1_updated = Entry(
        entry_id="E1",
        formula="B6 La",
        cell=CellParams(4.156, 4.156, 4.156),
        space_group="Pm-3m",
        d_spacings=np.array([4.0]),
        intensities=np.array([1000.0]),
    )
    insert_entry(empty_conn, e1_updated)
    cur = empty_conn.execute("SELECT COUNT(*) FROM entries WHERE entry_id = ?", ("E1",))
    assert cur.fetchone()[0] == 1
    cur = empty_conn.execute("SELECT COUNT(*) FROM peaks WHERE entry_id = ?", ("E1",))
    assert cur.fetchone()[0] == 1  # replaced, not appended


def test_insert_entries_batch(populated_conn: sqlite3.Connection, random_entries):
    cur = populated_conn.execute("SELECT COUNT(*) FROM entries")
    assert cur.fetchone()[0] == len(random_entries)
    cur = populated_conn.execute("SELECT COUNT(*) FROM peaks")
    assert cur.fetchone()[0] > 0


def test_insert_entries_peak_count_matches(empty_conn: sqlite3.Connection, random_entries):
    insert_entries(empty_conn, random_entries)
    total_peaks = sum(e.n_peaks for e in random_entries)
    cur = empty_conn.execute("SELECT COUNT(*) FROM peaks")
    assert cur.fetchone()[0] == total_peaks
