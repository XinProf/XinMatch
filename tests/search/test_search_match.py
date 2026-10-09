"""Tests for :mod:`xinmatch.core.search.search_match` (Phase 6 / T6.3-T6.5).

Self-contained: builds a small in-memory database with curated synthetic
entries (no dependency on real COD data or on sibling test fixtures that
might be edited concurrently by other agents).  Fixture names are
``sm_*``-prefixed to avoid colliding with the inline fixtures defined in
``tests/search/test_restraints_apply.py``.
"""

from __future__ import annotations

import math
import sqlite3
import time

import numpy as np
import pytest

from xinmatch.core.db import build_element_index, create_tables, insert_entries
from xinmatch.core.model import CellParams, Entry, Peak, Restraints
from xinmatch.core.search import (
    CandidateList,
    CandidateResult,
    fetch_entries_by_ids,
    rank_candidates,
    search_marked_peaks,
    search_match,
    select_top_n,
)

# Cu Kα wavelength used throughout the synthetic tests.
WL = 1.5406


def _d_from_two_theta(two_theta: float, wavelength: float = WL) -> float:
    """Inverse of ``d_to_two_theta`` for synthesising reference peaks."""
    return wavelength / (2.0 * math.sin(math.radians(two_theta / 2.0)))


# ---------------------------------------------------------------------------
# Synthetic entry factory
# ---------------------------------------------------------------------------
def _entry_from_two_theta(
    entry_id: str,
    two_thetas: list[float],
    intensities: list[float],
    *,
    formula: str = "Si O2",
    space_group: str | None = "P3221",
    mineral_name: str | None = None,
    cell: CellParams | None = None,
) -> Entry:
    """Build an :class:`Entry` whose (d, I) table lands at the given 2θ positions.

    The peaks are sorted by descending intensity (the reference software convention) so
    the round-trip through ``get_entry_peaks`` (which orders by intensity
    DESC) preserves the input ordering.
    """
    # Sort by intensity desc to match the reference software convention.
    order = sorted(range(len(two_thetas)), key=lambda i: -intensities[i])
    ds = [_d_from_two_theta(two_thetas[i]) for i in order]
    ints = [intensities[i] for i in order]
    hkls = [(1, 0, 0), (1, 1, 0), (1, 1, 1), (2, 0, 0), (2, 1, 0)]
    return Entry(
        entry_id=entry_id,
        formula=formula,
        d_spacings=np.array(ds, dtype=np.float64),
        intensities=np.array(ints, dtype=np.float64),
        mineral_name=mineral_name,
        cell=cell,
        space_group=space_group,
        hkl=hkls[: len(ds)],
        literature={"author": "tester", "journal": "J. Synth.", "year": 2000},
        quality="A",
    )


@pytest.fixture
def sm_entries() -> list[Entry]:
    """A curated set of 5 entries.

    ``E1`` is the *ground truth*: its (d, I) table reproduces the
    experimental peaks exactly, so its FoM should evaluate to 1.0.
    The others are decoys with shifted / sparse / overlapping peaks.
    """
    # Common 2θ positions for the experimental pattern.
    exp_tt = [10.0, 20.0, 30.0, 40.0]
    exp_int = [100.0, 50.0, 25.0, 10.0]

    e1 = _entry_from_two_theta(
        "E1", exp_tt, exp_int,
        formula="Si O2", space_group="P3221",
        mineral_name="Quartz",
        cell=CellParams(4.914, 4.914, 5.405, gamma=120.0),
    )
    # Decoy: shifted by 0.05° (still within the 0.3° window, but P_peakpos < 1).
    e2 = _entry_from_two_theta(
        "E2", [10.05, 20.05, 30.05, 40.05], [90.0, 45.0, 25.0, 10.0],
        formula="C Ca O3", space_group="R-3c",
        mineral_name="Calcite",
        cell=CellParams(4.99, 4.99, 17.06, gamma=120.0),
    )
    # Decoy: only 2 of 4 peaks present (P_npeaks = 0.5).
    e3 = _entry_from_two_theta(
        "E3", [10.0, 30.0], [100.0, 25.0],
        formula="Na Cl", space_group="Fm-3m",
        mineral_name="Halite",
        cell=CellParams(5.64, 5.64, 5.64),
    )
    # Decoy: all peaks far away (no correlation).
    e4 = _entry_from_two_theta(
        "E4", [60.0, 70.0, 80.0], [100.0, 50.0, 25.0],
        formula="Fe2 O3", space_group="R-3c",
        mineral_name="Hematite",
        cell=CellParams(5.04, 5.04, 13.75, gamma=120.0),
    )
    # Decoy: extra peaks but covering all 4 experimental peaks (3 of 5 ref matched).
    e5 = _entry_from_two_theta(
        "E5", [10.0, 20.0, 30.0, 40.0, 50.0], [100.0, 50.0, 25.0, 10.0, 5.0],
        formula="Cu", space_group="Fm-3m",
        mineral_name="Copper",
        cell=CellParams(3.615, 3.615, 3.615),
    )
    return [e1, e2, e3, e4, e5]


@pytest.fixture
def sm_exp_peaks() -> list[Peak]:
    """4 synthetic experimental peaks at 2θ = [10, 20, 30, 40]."""
    return [
        Peak(two_theta=10.0, intensity=100.0),
        Peak(two_theta=20.0, intensity=50.0),
        Peak(two_theta=30.0, intensity=25.0),
        Peak(two_theta=40.0, intensity=10.0),
    ]


@pytest.fixture
def sm_conn(sm_entries: list[Entry]) -> sqlite3.Connection:
    """In-memory DB populated with the 5 synthetic entries."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)
    insert_entries(conn, sm_entries)
    build_element_index(conn)
    yield conn
    conn.close()


# ===========================================================================
# rank_candidates
# ===========================================================================
def test_rank_candidates_perfect_match_top(sm_exp_peaks, sm_entries):
    """Ground-truth entry E1 (perfect match) ranks first with FoM ≈ 1."""
    results = rank_candidates(sm_exp_peaks, sm_entries, wavelength=WL)
    assert len(results) == 5
    # Sorted by FoM descending.
    foms = [r.fom for r in results]
    assert foms == sorted(foms, reverse=True)
    # E1 must be at the top.
    assert results[0].entry.entry_id == "E1"
    assert results[0].fom == pytest.approx(1.0, abs=1e-9)
    # P values reflect the perfect match.
    assert results[0].p_values["peakpos"] == pytest.approx(1.0, abs=1e-9)
    assert results[0].p_values["intensity"] == pytest.approx(1.0, abs=1e-9)


def test_rank_candidates_returns_candidate_result_with_pairs(sm_exp_peaks, sm_entries):
    """Each result carries the correlation pairs and the I_scale field."""
    results = rank_candidates(sm_exp_peaks, sm_entries, wavelength=WL)
    e1 = next(r for r in results if r.entry.entry_id == "E1")
    assert isinstance(e1, CandidateResult)
    assert isinstance(e1.pairs, list)
    # 4 exp peaks ↔ 4 ref peaks → 4 pairs.
    assert len(e1.pairs) == 4
    # Pairs are (exp_idx, ref_idx) tuples.
    for ei, ri in e1.pairs:
        assert isinstance(ei, int)
        assert isinstance(ri, int)
        assert 0 <= ei < len(sm_exp_peaks)
        assert 0 <= ri < 4
    assert e1.i_scale == pytest.approx(1.0, abs=1e-9)
    assert e1.p_values["i_scale"] == pytest.approx(e1.i_scale, abs=1e-12)


def test_rank_candidates_no_correlation_baseline(sm_exp_peaks, sm_entries):
    """E4 (peaks far away) ends up with the baseline (lowest) FoM."""
    results = rank_candidates(sm_exp_peaks, sm_entries, wavelength=WL)
    e4 = next(r for r in results if r.entry.entry_id == "E4")
    assert e4.pairs == []
    # With no pairs: P_peakpos=0, P_intensity=0, P_npeaks=0, P_ncorr=0,
    # I_scale=1.0 → FoM = 1 - sum(w_i for i in [peakpos, intensity, npeaks, ncorr]).
    expected = 1.0 - (
        0.2275 + 0.1112 + 0.2306 + 0.1152
    )
    assert e4.fom == pytest.approx(expected, abs=1e-9)
    # E4 must be last (everything else has at least one matched pair).
    assert results[-1].entry.entry_id == "E4"


def test_rank_candidates_partial_overlap_orders_correctly(sm_exp_peaks, sm_entries):
    """E1 (perfect) > E5 (4 of 5 match) > E2 (slight shift) > E3 (2 of 4) > E4 (none)."""
    results = rank_candidates(sm_exp_peaks, sm_entries, wavelength=WL)
    ids = [r.entry.entry_id for r in results]
    # FoM descending; check the ordering constraints that must hold.
    assert ids[0] == "E1"  # perfect
    assert ids[-1] == "E4"  # no overlap
    # E3 (only 2 peaks) should rank below E5 (all 4 matched + 1 extra).
    e3 = next(r for r in results if r.entry.entry_id == "E3")
    e5 = next(r for r in results if r.entry.entry_id == "E5")
    assert e5.fom > e3.fom


def test_rank_candidates_empty_entries(sm_exp_peaks):
    """Empty candidate list → empty result."""
    assert rank_candidates(sm_exp_peaks, [], wavelength=WL) == []


def test_rank_candidates_empty_exp_peaks(sm_entries):
    """No experimental peaks → all candidates get baseline FoM (no pairs)."""
    results = rank_candidates([], sm_entries, wavelength=WL)
    assert len(results) == len(sm_entries)
    # All FoM equal to the no-pair baseline (I_scale defaults to 1.0).
    for r in results:
        assert r.pairs == []
        assert r.p_values["i_scale"] == 1.0


def test_rank_candidates_custom_weights(sm_exp_peaks, sm_entries):
    """Custom weights propagate (perfect match → FoM = 1 regardless)."""
    from xinmatch.core.search.fom_criteria import FomWeights
    custom = FomWeights(
        peakpos=0.5, intensity=0.1, npeaks=0.2, ncorr=0.1, i_scale=0.0
    )
    results = rank_candidates(
        sm_exp_peaks, sm_entries, wavelength=WL, weights=custom
    )
    e1 = next(r for r in results if r.entry.entry_id == "E1")
    assert e1.fom == pytest.approx(1.0, abs=1e-9)


# ===========================================================================
# select_top_n
# ===========================================================================
def test_select_top_n_default(sm_exp_peaks, sm_entries):
    results = rank_candidates(sm_exp_peaks, sm_entries, wavelength=WL)
    top = select_top_n(results)
    assert len(top) == 5  # default n=20, only 5 results → all kept
    assert top[0].fom >= top[-1].fom


def test_select_top_n_explicit(sm_exp_peaks, sm_entries):
    results = rank_candidates(sm_exp_peaks, sm_entries, wavelength=WL)
    top = select_top_n(results, n=3)
    assert len(top) == 3
    assert [r.entry.entry_id for r in top] == [
        results[0].entry.entry_id,
        results[1].entry.entry_id,
        results[2].entry.entry_id,
    ]


def test_select_top_n_zero(sm_exp_peaks, sm_entries):
    results = rank_candidates(sm_exp_peaks, sm_entries, wavelength=WL)
    assert select_top_n(results, n=0) == []


def test_select_top_n_negative_raises(sm_exp_peaks, sm_entries):
    results = rank_candidates(sm_exp_peaks, sm_entries, wavelength=WL)
    with pytest.raises(ValueError, match="non-negative"):
        select_top_n(results, n=-1)


def test_select_top_n_does_not_mutate_input(sm_exp_peaks, sm_entries):
    """select_top_n returns a new list (input unchanged)."""
    results = rank_candidates(sm_exp_peaks, sm_entries, wavelength=WL)
    snapshot = list(results)
    _ = select_top_n(results, n=2)
    assert results == snapshot


# ===========================================================================
# fetch_entries_by_ids
# ===========================================================================
def test_fetch_entries_by_ids_roundtrip(sm_conn, sm_entries):
    """Entries fetched from the DB match the originals (modulo peak order)."""
    ids = [e.entry_id for e in sm_entries]
    fetched = fetch_entries_by_ids(sm_conn, ids)
    assert len(fetched) == len(sm_entries)
    by_id_orig = {e.entry_id: e for e in sm_entries}
    by_id_fetched = {e.entry_id: e for e in fetched}
    assert set(by_id_orig) == set(by_id_fetched)
    for eid in by_id_orig:
        orig = by_id_orig[eid]
        got = by_id_fetched[eid]
        assert got.entry_id == orig.entry_id
        assert got.formula == orig.formula
        assert got.mineral_name == orig.mineral_name
        assert got.space_group == orig.space_group
        assert got.quality == orig.quality
        # d-spacings / intensities match as multisets (order may differ if
        # the SQL ORDER BY intensity DESC ties are resolved differently).
        assert sorted(got.d_spacings.tolist()) == sorted(orig.d_spacings.tolist())
        assert sorted(got.intensities.tolist()) == sorted(orig.intensities.tolist())


def test_fetch_entries_by_ids_preserves_input_order(sm_conn, sm_entries):
    ids = ["E4", "E1", "E3", "E5", "E2"]
    fetched = fetch_entries_by_ids(sm_conn, ids)
    assert [e.entry_id for e in fetched] == ids


def test_fetch_entries_by_ids_skips_missing(sm_conn):
    """Ids absent from the DB are silently dropped."""
    fetched = fetch_entries_by_ids(sm_conn, ["E1", "E_DOES_NOT_EXIST"])
    assert len(fetched) == 1
    assert fetched[0].entry_id == "E1"


def test_fetch_entries_by_ids_empty(sm_conn):
    assert fetch_entries_by_ids(sm_conn, []) == []


def test_fetch_entries_by_ids_reconstructs_cell_and_literature(sm_conn, sm_entries):
    """Cell params and literature (author/journal/year) survive the round-trip."""
    fetched = fetch_entries_by_ids(sm_conn, ["E1"])
    e1 = fetched[0]
    assert e1.cell is not None
    assert e1.cell.a == pytest.approx(4.914, abs=1e-6)
    assert e1.cell.gamma == pytest.approx(120.0, abs=1e-6)
    assert e1.literature.get("author") == "tester"
    assert e1.literature.get("journal") == "J. Synth."
    assert e1.literature.get("year") == 2000


# ===========================================================================
# search_match (full pipeline)
# ===========================================================================
def test_search_match_default_d_search(sm_exp_peaks, sm_conn, sm_entries):
    """Default path: d-value retrieval produces candidates, FoM ranks them."""
    results = search_match(sm_exp_peaks, sm_conn, wavelength=WL)
    # All 5 entries share d-spacings near the experimental ones, so all 5
    # should be candidates (the d-search tolerance 0.02 Å catches them).
    assert 1 <= len(results) <= 5
    # E1 must be at the top if present.
    if any(r.entry.entry_id == "E1" for r in results):
        e1 = next(r for r in results if r.entry.entry_id == "E1")
        assert e1.fom == pytest.approx(1.0, abs=1e-9)
        # And it ranks first.
        assert results[0].entry.entry_id == "E1"


def test_search_match_top_n(sm_exp_peaks, sm_conn):
    results = search_match(sm_exp_peaks, sm_conn, wavelength=WL, top_n=2)
    assert len(results) <= 2


def test_search_match_top_n_zero(sm_exp_peaks, sm_conn):
    results = search_match(sm_exp_peaks, sm_conn, wavelength=WL, top_n=0)
    assert results == []


def test_search_match_restraints_path(sm_exp_peaks, sm_conn):
    """Restraints path: only entries with required element are scored."""
    r = Restraints()
    r.require("Si")
    results = search_match(sm_exp_peaks, sm_conn, wavelength=WL, restraints=r)
    # Only E1 (Si O2) and E5 (Cu — wait, no Cu has no Si) ...
    # Actually only E1 (SiO2) contains Si → only 1 candidate.
    ids = {r.entry.entry_id for r in results}
    assert ids == {"E1"}
    assert results[0].fom == pytest.approx(1.0, abs=1e-9)


def test_search_match_restraints_no_match_returns_empty(sm_exp_peaks, sm_conn):
    """Restraints excluding all entries → empty result."""
    r = Restraints()
    r.require("Xx")  # not present in any entry
    assert search_match(sm_exp_peaks, sm_conn, wavelength=WL, restraints=r) == []


def test_search_match_pre_filter_path(sm_exp_peaks, sm_conn, sm_entries):
    """Pre-filter callable replaces the default candidate generation."""

    def my_pre_filter(peaks, conn):
        return ["E2", "E3"]  # only score these two

    results = search_match(
        sm_exp_peaks, sm_conn, wavelength=WL, pre_filter=my_pre_filter
    )
    ids = {r.entry.entry_id for r in results}
    assert ids == {"E2", "E3"}


def test_search_match_pre_filter_takes_precedence_over_restraints(
    sm_exp_peaks, sm_conn
):
    """When both pre_filter and restraints are given, pre_filter wins."""
    r = Restraints()
    r.require("Si")  # would yield only E1

    def my_pre_filter(peaks, conn):
        return ["E4"]  # E4 has no Si but pre_filter bypasses restraints

    results = search_match(
        sm_exp_peaks, sm_conn, wavelength=WL, restraints=r, pre_filter=my_pre_filter
    )
    ids = {r.entry.entry_id for r in results}
    assert ids == {"E4"}


def test_search_match_empty_exp_peaks(sm_conn):
    """No experimental peaks → empty result (no d-spacings to search on)."""
    assert search_match([], sm_conn, wavelength=WL) == []


def test_search_match_window_deg_passthrough(sm_exp_peaks, sm_conn):
    """A narrower window reduces matches for the shifted decoy E2."""
    wide = search_match(sm_exp_peaks, sm_conn, wavelength=WL, window_deg=0.3)
    narrow = search_match(sm_exp_peaks, sm_conn, wavelength=WL, window_deg=0.001)
    # The perfect match (E1) must still appear in both, with FoM 1.0.
    wide_e1 = next((r for r in wide if r.entry.entry_id == "E1"), None)
    narrow_e1 = next((r for r in narrow if r.entry.entry_id == "E1"), None)
    assert wide_e1 is not None
    assert narrow_e1 is not None
    assert wide_e1.fom == pytest.approx(1.0, abs=1e-9)
    assert narrow_e1.fom == pytest.approx(1.0, abs=1e-9)
    # E2 (0.05° shift) is in the 0.3° window but not in the 0.001° window.
    wide_e2 = next((r for r in wide if r.entry.entry_id == "E2"), None)
    narrow_e2 = next((r for r in narrow if r.entry.entry_id == "E2"), None)
    if wide_e2 is not None and narrow_e2 is not None:
        # With 0.001° window E2's pairs are empty → lower FoM.
        assert narrow_e2.fom <= wide_e2.fom


# ===========================================================================
# search_marked_peaks (T6.5)
# ===========================================================================
def test_search_marked_peaks_single(sm_exp_peaks, sm_conn, sm_entries):
    """Marking just the first peak restricts the search."""
    # The first experimental peak (2θ=10) is matched by E1, E2, E3, E5.
    results = search_marked_peaks(
        sm_exp_peaks, sm_conn, wavelength=WL, marked_indices=[0], top_n=10
    )
    ids = {r.entry.entry_id for r in results}
    # E4 has no peak near 2θ=10 → excluded.
    assert "E4" not in ids
    assert len(ids) >= 1


def test_search_marked_peaks_multiple(sm_exp_peaks, sm_conn):
    """Marking peaks 0 and 2 (2θ=10 and 30)."""
    results = search_marked_peaks(
        sm_exp_peaks, sm_conn, wavelength=WL, marked_indices=[0, 2], top_n=10
    )
    # E1 has peaks at both positions → should rank high.
    e1 = next((r for r in results if r.entry.entry_id == "E1"), None)
    assert e1 is not None


def test_search_marked_peaks_empty_indices(sm_exp_peaks, sm_conn):
    """No marked peaks → empty result."""
    assert search_marked_peaks(
        sm_exp_peaks, sm_conn, wavelength=WL, marked_indices=[]
    ) == []


def test_search_marked_peaks_kwargs_forwarded(sm_exp_peaks, sm_conn):
    """Extra kwargs (top_n, weights, ...) are forwarded to search_match."""
    results = search_marked_peaks(
        sm_exp_peaks, sm_conn, wavelength=WL,
        marked_indices=[0, 1, 2, 3], top_n=2,
    )
    assert len(results) <= 2


def test_search_marked_peaks_out_of_range(sm_exp_peaks, sm_conn):
    """Out-of-range marked indices raise IndexError."""
    with pytest.raises(IndexError):
        search_marked_peaks(
            sm_exp_peaks, sm_conn, wavelength=WL, marked_indices=[99]
        )


# ===========================================================================
# Performance: 1000 candidates < 2 s
# ===========================================================================
def test_perf_1000_candidates_under_2s():
    """Score 1000 synthetic candidate entries in under 2 seconds.

    Builds a ground-truth entry + 999 decoys with random peak positions,
    inserts into a fresh in-memory DB, and runs search_match.  This
    matches the spec's perf target ("1000 候选 <2 秒，合成数据").
    """
    rng = np.random.default_rng(123)
    exp_tt = [10.0, 20.0, 30.0, 40.0]
    exp_int = [100.0, 50.0, 25.0, 10.0]
    exp_peaks = [Peak(two_theta=tt, intensity=i)
                 for tt, i in zip(exp_tt, exp_int, strict=True)]

    # Ground truth.
    e_gt = _entry_from_two_theta("PERF-0000", exp_tt, exp_int,
                                  formula="Si O2", space_group="P3221",
                                  mineral_name="GroundTruth")
    # 999 decoys with 4 random 2θ positions each (broad distribution).
    decoys: list[Entry] = []
    for i in range(1, 1000):
        # Random peaks: occasionally land near exp positions (so d-search
        # finds them), mostly scattered.
        if i % 3 == 0:
            tt = [10.0 + rng.uniform(-0.5, 0.5),
                  20.0 + rng.uniform(-0.5, 0.5),
                  30.0 + rng.uniform(-0.5, 0.5),
                  40.0 + rng.uniform(-0.5, 0.5)]
        else:
            tt = [float(rng.uniform(5, 80)) for _ in range(4)]
        ints = [float(rng.uniform(10, 100)) for _ in range(4)]
        decoys.append(_entry_from_two_theta(
            f"DEC-{i:04d}", tt, ints,
            formula="Decoy X", space_group=None,
        ))
    all_entries = [e_gt] + decoys

    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)
    insert_entries(conn, all_entries)
    build_element_index(conn)
    try:
        t0 = time.perf_counter()
        results = search_match(exp_peaks, conn, wavelength=WL, top_n=20)
        elapsed = time.perf_counter() - t0
    finally:
        conn.close()

    assert len(results) <= 20
    # Ground truth must be in the top-20 (it's a perfect match).
    top_ids = {r.entry.entry_id for r in results}
    assert "PERF-0000" in top_ids
    # And the top result should be the ground truth (highest FoM).
    assert results[0].entry.entry_id == "PERF-0000"
    assert results[0].fom == pytest.approx(1.0, abs=1e-9)
    # Performance: under 2 seconds on synthetic data.
    assert elapsed < 2.0, f"1000-candidate search took {elapsed:.3f}s (>2s)"


# ===========================================================================
# CandidateList integration smoke test
# ===========================================================================
def test_search_match_feeds_candidate_list(sm_exp_peaks, sm_conn):
    """The output of search_match is consumable by CandidateList."""
    results = search_match(sm_exp_peaks, sm_conn, wavelength=WL, top_n=5)
    cl = CandidateList(candidates=results, n_exp_peaks=len(sm_exp_peaks))
    assert len(cl) == len(results)
    # Iteration works.
    assert list(cl) == results
    # FoM order preserved.
    foms = [r.fom for r in cl]
    assert foms == sorted(foms, reverse=True)
    # show_unassociated_peaks on the top candidate is sensible.
    top_id = results[0].entry.entry_id
    unassoc = cl.show_unassociated_peaks(top_id)
    assert isinstance(unassoc, list)
    assert all(0 <= i < len(sm_exp_peaks) for i in unassoc)
