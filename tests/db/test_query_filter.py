"""Tests for multi-field search filters (Phase 5 / T5.5)."""

from __future__ import annotations

import sqlite3

from xinmatch.core.db.query_filter import (
    search_by_crystal_system,
    search_by_elements,
    search_by_formula,
    search_by_mineral_name,
    search_by_space_group,
    search_by_year,
    search_combined,
)


def test_search_by_elements_required(populated_conn: sqlite3.Connection):
    ids = search_by_elements(populated_conn, required={"La", "B"})
    assert "LAB6-0001" in ids


def test_search_by_elements_excluded(populated_conn: sqlite3.Connection):
    ids = search_by_elements(populated_conn, required={"La", "B"}, excluded={"O"})
    assert "LAB6-0001" in ids  # LaB6 has no O


def test_search_by_elements_excluded_removes(populated_conn: sqlite3.Connection):
    all_with_la_b = set(search_by_elements(populated_conn, required={"La", "B"}))
    without_o = set(search_by_elements(populated_conn, required={"La", "B"}, excluded={"O"}))
    assert without_o.issubset(all_with_la_b)


def test_search_by_crystal_system(populated_conn: sqlite3.Connection):
    ids = search_by_crystal_system(populated_conn, "cubic")
    assert "LAB6-0001" in ids
    # All returned entries should be cubic.
    cur = populated_conn.execute(
        f"SELECT crystal_system FROM entries WHERE entry_id IN ({','.join('?' * len(ids))})",
        ids,
    )
    assert all(row[0] == "cubic" for row in cur.fetchall())


def test_search_by_space_group(populated_conn: sqlite3.Connection):
    ids = search_by_space_group(populated_conn, "Pm-3m")
    assert "LAB6-0001" in ids
    cur = populated_conn.execute(
        f"SELECT space_group FROM entries WHERE entry_id IN ({','.join('?' * len(ids))})",
        ids,
    )
    assert all(row[0] == "Pm-3m" for row in cur.fetchall())


def test_search_by_year_range(populated_conn: sqlite3.Connection):
    ids = search_by_year(populated_conn, year_min=1970, year_max=1972)
    assert "LAB6-0001" in ids  # LaB6 year=1971
    cur = populated_conn.execute(
        f"SELECT year FROM entries WHERE entry_id IN ({','.join('?' * len(ids))})",
        ids,
    )
    for (year,) in cur.fetchall():
        assert 1970 <= year <= 1972


def test_search_by_year_open_ended(populated_conn: sqlite3.Connection):
    ids = search_by_year(populated_conn, year_min=2000)
    cur = populated_conn.execute(
        f"SELECT year FROM entries WHERE entry_id IN ({','.join('?' * len(ids))})",
        ids,
    )
    for (year,) in cur.fetchall():
        assert year >= 2000


def test_search_by_mineral_name(populated_conn: sqlite3.Connection):
    ids = search_by_mineral_name(populated_conn, "hexaboride")
    assert "LAB6-0001" in ids


def test_search_by_formula_exact(populated_conn: sqlite3.Connection):
    ids = search_by_formula(populated_conn, "B6 La")
    assert "LAB6-0001" in ids


def test_search_combined_intersection(populated_conn: sqlite3.Connection):
    """Combined result must equal the intersection of individual conditions."""
    elem_ids = set(search_by_elements(populated_conn, required={"La", "B"}))
    sg_ids = set(search_by_space_group(populated_conn, "Pm-3m"))
    sys_ids = set(search_by_crystal_system(populated_conn, "cubic"))

    expected = elem_ids & sg_ids & sys_ids
    combined = search_combined(
        populated_conn,
        elements={"La", "B"},
        space_group="Pm-3m",
        crystal_system="cubic",
    )
    assert set(combined) == expected


def test_search_combined_with_year(populated_conn: sqlite3.Connection):
    combined = search_combined(
        populated_conn,
        elements={"La", "B"},
        year_min=1970,
        year_max=1972,
    )
    assert "LAB6-0001" in combined


def test_search_combined_no_filters_returns_all(populated_conn: sqlite3.Connection):
    all_ids = search_combined(populated_conn)
    cur = populated_conn.execute("SELECT COUNT(*) FROM entries")
    assert len(all_ids) == cur.fetchone()[0]


def test_search_combined_empty_intersection(populated_conn: sqlite3.Connection):
    # cubic + a year range that LaB6 (1971) is not in -> still may have others,
    # but space_group "Pm-3m" + year 2020+ should be empty for our synthetic set.
    result = search_combined(
        populated_conn,
        space_group="Pm-3m",
        year_min=2020,
        year_max=2024,
    )
    # LaB6 is 1971, so it should NOT be in the result.
    assert "LAB6-0001" not in result
