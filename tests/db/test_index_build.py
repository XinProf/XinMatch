"""Tests for inverted-index building (Phase 5 / T5.3)."""

from __future__ import annotations

import sqlite3
import time

from xinmatch.core.db.index_build import (
    build_d_index,
    build_element_index,
    build_rtree_d_index,
)
from xinmatch.core.db.query_filter import search_by_elements
from xinmatch.core.db.query_peaks import search_by_d


def test_build_element_index_creates_combos(populated_conn: sqlite3.Connection):
    n = build_element_index(populated_conn)
    assert n > 0
    cur = populated_conn.execute("SELECT COUNT(*) FROM element_combo")
    assert cur.fetchone()[0] == n


def test_build_element_index_is_idempotent(populated_conn: sqlite3.Connection):
    n1 = build_element_index(populated_conn)
    n2 = build_element_index(populated_conn)
    assert n1 == n2


def test_d_index_query_is_fast(populated_conn: sqlite3.Connection):
    build_d_index(populated_conn)
    # Use the LaB6 d-spacings as a query.
    cur = populated_conn.execute(
        "SELECT d FROM peaks WHERE entry_id = 'LAB6-0001' ORDER BY intensity DESC LIMIT 10",
    )
    peak_ds = [r[0] for r in cur.fetchall()]

    t0 = time.perf_counter()
    results = search_by_d(populated_conn, peak_ds, tolerance=0.02)
    elapsed = time.perf_counter() - t0
    assert results, "expected at least one match"
    # Acceptance: < 100 ms on 100+ entries.
    assert elapsed < 0.1, f"d-search took {elapsed * 1000:.1f} ms (>100 ms)"


def test_element_index_query_is_fast(populated_conn: sqlite3.Connection):
    build_element_index(populated_conn)
    t0 = time.perf_counter()
    ids = search_by_elements(populated_conn, required={"La", "B"})
    elapsed = time.perf_counter() - t0
    assert "LAB6-0001" in ids
    assert elapsed < 0.1, f"element search took {elapsed * 1000:.1f} ms (>100 ms)"


def test_build_rtree_d_index_returns_bool(populated_conn: sqlite3.Connection):
    ok = build_rtree_d_index(populated_conn)
    assert isinstance(ok, bool)
    # Either it succeeds (rtree available) or falls back gracefully.
