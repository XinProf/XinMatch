"""Tests for d-spacing search-match (Phase 5 / T5.4) ⭐ core."""

from __future__ import annotations

import sqlite3

import numpy as np

from xinmatch.core.db.query_peaks import get_entry_peaks, search_by_d
from xinmatch.core.model import CellParams, Entry


def _lab6_entry() -> Entry:
    cell = CellParams(4.156, 4.156, 4.156)
    # Real-ish LaB6 d-spacings (cubic Pm-3m).
    ds = np.array([4.156, 2.939, 2.400, 2.078, 1.859, 1.697, 1.572, 1.469])
    intensities = np.array([1000.0, 850.0, 700.0, 550.0, 400.0, 300.0, 200.0, 100.0])
    return Entry(
        entry_id="LAB6-0001",
        formula="B6 La",
        mineral_name="Lanthanum hexaboride",
        cell=cell,
        space_group="Pm-3m",
        d_spacings=ds,
        intensities=intensities,
    )


def test_search_by_d_returns_lab6_in_top3(populated_conn: sqlite3.Connection):
    """Acceptance: LaB6 must rank in the top 3 when searched with its own peaks."""
    cur = populated_conn.execute(
        "SELECT d FROM peaks WHERE entry_id = 'LAB6-0001' ORDER BY intensity DESC",
    )
    lab6_ds = [r[0] for r in cur.fetchall()]

    results = search_by_d(populated_conn, lab6_ds, tolerance=0.02)
    assert results, "expected search results"
    top_ids = [eid for eid, _ in results[:3]]
    assert "LAB6-0001" in top_ids, f"LaB6 not in top 3: {top_ids}"


def test_search_by_d_empty_peaks_returns_empty(populated_conn: sqlite3.Connection):
    assert search_by_d(populated_conn, []) == []


def test_search_by_d_sorted_by_match_count_desc(populated_conn: sqlite3.Connection):
    cur = populated_conn.execute(
        "SELECT d FROM peaks WHERE entry_id = 'LAB6-0001' ORDER BY intensity DESC",
    )
    lab6_ds = [r[0] for r in cur.fetchall()]
    results = search_by_d(populated_conn, lab6_ds, tolerance=0.02)
    counts = [cnt for _, cnt in results]
    assert counts == sorted(counts, reverse=True)


def test_search_by_d_within_tolerance(empty_conn: sqlite3.Connection):
    entry = _lab6_entry()
    from xinmatch.core.db.build_cod import insert_entry

    insert_entry(empty_conn, entry)
    # Query with slightly shifted d-values within tolerance.
    query_ds = (entry.d_spacings + 0.005).tolist()
    results = search_by_d(empty_conn, query_ds, tolerance=0.02)
    assert results[0][0] == "LAB6-0001"
    assert results[0][1] == float(len(query_ds))


def test_search_by_d_outside_tolerance_no_match(empty_conn: sqlite3.Connection):
    entry = _lab6_entry()
    from xinmatch.core.db.build_cod import insert_entry

    insert_entry(empty_conn, entry)
    # Query far away — no entry should match all peaks.
    query_ds = [100.0, 200.0, 300.0]
    results = search_by_d(empty_conn, query_ds, tolerance=0.02)
    assert results == []


def test_search_by_d_below_half_wavelength_does_not_raise(
    populated_conn: sqlite3.Connection,
):
    """`d < λ/2` is unphysical (sin θ > 1) and must be skipped, not crash.

    Real trigger: a Mo/Ag-tube pattern imported without wavelength metadata
    falls back to the Cu Kα default, leaving high-angle peaks with
    d ≈ 0.35 Å; ``asin`` would raise ``ValueError: math domain error``.
    """
    results = search_by_d(populated_conn, [0.35], wavelength=1.5406, window_deg=0.3)
    assert results == []


def test_search_by_d_at_backscattering_limit_does_not_overflow(
    populated_conn: sqlite3.Connection,
):
    """``d == λ/2`` (2θ = 180°) is the boundary of ``asin``: float round-off
    must not push the argument above 1.0."""
    results = search_by_d(
        populated_conn, [1.5406 / 2.0], wavelength=1.5406, window_deg=0.3
    )
    assert isinstance(results, list)


def test_get_entry_peaks(empty_conn: sqlite3.Connection):
    entry = _lab6_entry()
    from xinmatch.core.db.build_cod import insert_entry

    insert_entry(empty_conn, entry)
    peaks = get_entry_peaks(empty_conn, "LAB6-0001")
    assert len(peaks) == entry.n_peaks
    # Ordered by descending intensity.
    intensities = [p[1] for p in peaks]
    assert intensities == sorted(intensities, reverse=True)
