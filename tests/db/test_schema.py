"""Tests for the database schema (Phase 5 / T5.2)."""

from __future__ import annotations

import sqlite3

from xinmatch.core.db.schema import SCHEMA_SQL, create_tables, table_exists


def test_create_tables_creates_all_tables(empty_conn: sqlite3.Connection):
    expected_tables = {"entries", "peaks", "elements", "element_combo"}
    for name in expected_tables:
        assert table_exists(empty_conn, name), f"table {name} missing"


def test_create_tables_creates_indexes(empty_conn: sqlite3.Connection):
    expected_indexes = {
        "idx_elements_element_entry",
        "idx_peaks_d",
        "idx_entries_formula",
        "idx_entries_space_group",
        "idx_entries_crystal_system",
        "idx_entries_year",
    }
    for name in expected_indexes:
        assert table_exists(empty_conn, name), f"index {name} missing"


def test_create_tables_is_idempotent(empty_conn: sqlite3.Connection):
    # Running create_tables twice must not raise.
    create_tables(empty_conn)
    create_tables(empty_conn)
    assert table_exists(empty_conn, "entries")


def test_schema_sql_is_nonempty():
    assert isinstance(SCHEMA_SQL, str)
    assert "CREATE TABLE" in SCHEMA_SQL
    assert "entries" in SCHEMA_SQL


def test_entries_table_columns(empty_conn: sqlite3.Connection):
    cur = empty_conn.execute("PRAGMA table_info(entries)")
    columns = {row[1] for row in cur.fetchall()}
    required = {
        "entry_id", "formula", "mineral_name", "space_group", "crystal_system",
        "a", "b", "c", "alpha", "beta", "gamma", "volume", "density",
        "color", "year", "author", "journal", "quality", "elements",
    }
    assert required.issubset(columns), f"missing columns: {required - columns}"


def test_peaks_table_columns(empty_conn: sqlite3.Connection):
    cur = empty_conn.execute("PRAGMA table_info(peaks)")
    columns = {row[1] for row in cur.fetchall()}
    assert {"entry_id", "d", "intensity", "h", "k", "l"}.issubset(columns)


def test_elements_table_has_composite_primary_key(empty_conn: sqlite3.Connection):
    cur = empty_conn.execute("PRAGMA table_info(elements)")
    pk_cols = [row[1] for row in cur.fetchall() if row[5] > 0]
    assert set(pk_cols) == {"entry_id", "element"}
