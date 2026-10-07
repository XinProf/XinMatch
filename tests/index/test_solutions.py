"""Tests for solutions.py — ranking, dedup, FOMs (T9.4)."""

from __future__ import annotations

import math

import pytest

from xinmatch.core.index.lattice import LatticeSolution
from xinmatch.core.index.solutions import (
    deduplicate,
    rank_solutions,
    smith_snyder_fom,
    wolff_fom,
)
from xinmatch.core.index.treor import index_treor
from xinmatch.core.model.entry import CellParams

# LaB6 cubic, a = 4.157 Å.
_LAB6_A = 4.157
_LAB6_PEAKS = [
    _LAB6_A / math.sqrt(n2)
    for n2 in [1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20]
]


# --------------------------------------------------------------------- #
# rank_solutions
# --------------------------------------------------------------------- #


def _make_sol(a: float, fom: float, n_indexed: int = 5) -> LatticeSolution:
    return LatticeSolution(
        cell=CellParams(a=a, b=a, c=a),
        crystal_system="cubic",
        fom=fom,
        hkl_assignments=[(1, 0, 0)] * n_indexed,
        n_indexed=n_indexed,
        program="treor",
    )


def test_rank_solutions_orders_by_fom_desc():
    sols = [_make_sol(4.0, fom=10.0), _make_sol(4.1, fom=42.0), _make_sol(4.2, fom=1.0)]
    ranked = rank_solutions(sols)
    assert [s.fom for s in ranked] == [42.0, 10.0, 1.0]


def test_rank_solutions_tiebreak_n_indexed_desc():
    sols = [_make_sol(4.0, fom=5.0, n_indexed=3), _make_sol(4.1, fom=5.0, n_indexed=5)]
    ranked = rank_solutions(sols)
    assert ranked[0].n_indexed == 5


def test_rank_solutions_tiebreak_smaller_volume():
    """Same FOM and n_indexed → smaller volume first."""
    sol_a = LatticeSolution(
        cell=CellParams(a=5.0, b=5.0, c=5.0),
        crystal_system="cubic",
        fom=10.0,
        hkl_assignments=[(1, 0, 0)],
        n_indexed=1,
    )
    sol_b = LatticeSolution(
        cell=CellParams(a=4.0, b=4.0, c=4.0),
        crystal_system="cubic",
        fom=10.0,
        hkl_assignments=[(1, 0, 0)],
        n_indexed=1,
    )
    ranked = rank_solutions([sol_a, sol_b])
    assert ranked[0].cell.a == 4.0


def test_rank_solutions_empty():
    assert rank_solutions([]) == []


# --------------------------------------------------------------------- #
# deduplicate
# --------------------------------------------------------------------- #


def test_deduplicate_keeps_best_on_tie():
    """Two near-identical cells → only the higher-FOM one kept."""
    sol_a = _make_sol(4.157, fom=42.0)
    sol_b = _make_sol(4.1575, fom=10.0)
    kept = deduplicate([sol_a, sol_b], tol_cell=0.01)
    assert len(kept) == 1
    assert kept[0].fom == 42.0


def test_deduplicate_distinct_cells_all_kept():
    sol_a = _make_sol(4.0, fom=10.0)
    sol_b = _make_sol(5.0, fom=8.0)
    sol_c = _make_sol(6.0, fom=5.0)
    kept = deduplicate([sol_a, sol_b, sol_c], tol_cell=0.01)
    assert len(kept) == 3


def test_deduplicate_default_tolerance():
    """Default tol_cell=0.01 — 0.005 difference is a dup, 0.02 is not."""
    sol_a = _make_sol(4.0, fom=10.0)
    sol_b = _make_sol(4.005, fom=5.0)
    sol_c = _make_sol(4.05, fom=3.0)
    kept = deduplicate([sol_a, sol_b, sol_c])
    assert len(kept) == 2


def test_deduplicate_empty():
    assert deduplicate([]) == []


# --------------------------------------------------------------------- #
# wolff_fom
# --------------------------------------------------------------------- #


def test_wolff_fom_zero_when_no_indexed_peaks():
    sol = LatticeSolution(
        cell=CellParams(a=4.0, b=4.0, c=4.0),
        crystal_system="cubic",
        fom=0.0,
        hkl_assignments=[None, None],
        n_indexed=0,
    )
    assert wolff_fom(sol, [4.0, 3.0]) == 0.0


def test_wolff_fom_perfect_fit_returns_large_value():
    """When calculated d's match observed d's exactly, FOM should be
    very large."""
    a = 4.157
    hkl = [(1, 0, 0), (1, 1, 0), (2, 0, 0)]
    peaks = [a / math.sqrt(1), a / math.sqrt(2), a / 2]
    sol = LatticeSolution(
        cell=CellParams(a=a, b=a, c=a),
        crystal_system="cubic",
        fom=10.0,
        hkl_assignments=hkl,
        n_indexed=3,
    )
    f = wolff_fom(sol, peaks)
    assert f > 1e3


def test_wolff_fom_decreases_with_error():
    """As calculated d's deviate more from observed, FOM drops."""
    a_true = 4.157
    hkl = [(1, 0, 0), (1, 1, 0), (2, 0, 0)]
    peaks = [a_true / math.sqrt(n2) for n2 in [1, 2, 4]]
    # Cell is exactly right
    sol_perfect = LatticeSolution(
        cell=CellParams(a=a_true, b=a_true, c=a_true),
        crystal_system="cubic",
        fom=10.0,
        hkl_assignments=hkl,
        n_indexed=3,
    )
    # Cell is slightly off
    sol_off = LatticeSolution(
        cell=CellParams(a=a_true + 0.1, b=a_true + 0.1, c=a_true + 0.1),
        crystal_system="cubic",
        fom=10.0,
        hkl_assignments=hkl,
        n_indexed=3,
    )
    f_perfect = wolff_fom(sol_perfect, peaks)
    f_off = wolff_fom(sol_off, peaks)
    assert f_perfect > f_off


def test_wolff_fom_on_treor_solution():
    """Treor finds LaB6 a → wolff_fom should be > 10 (Treor rule)."""
    sols = index_treor(_LAB6_PEAKS, crystal_systems=["cubic"], tolerance=0.05)
    best = sols[0]
    # Compute wolff_fom on the indexed solution (use the same 20-peak
    # set passed to treor — assignments list aligns).
    fom = wolff_fom(best, sorted(_LAB6_PEAKS, reverse=True))
    # The Treor rule: M(20) > 10 → "solved". For our noise-free LaB6
    # synthetic we expect well above 10.
    assert fom > 10.0


# --------------------------------------------------------------------- #
# smith_snyder_fom
# --------------------------------------------------------------------- #


def test_smith_snyder_fom_zero_when_no_indexed_peaks():
    sol = LatticeSolution(
        cell=CellParams(a=4.0, b=4.0, c=4.0),
        crystal_system="cubic",
        fom=0.0,
        hkl_assignments=[None, None],
        n_indexed=0,
    )
    assert smith_snyder_fom(sol, [4.0, 3.0]) == 0.0


def test_smith_snyder_fom_perfect_fit_returns_large_value():
    a = 4.157
    hkl = [(1, 0, 0), (1, 1, 0), (2, 0, 0)]
    peaks = [a / math.sqrt(1), a / math.sqrt(2), a / 2]
    sol = LatticeSolution(
        cell=CellParams(a=a, b=a, c=a),
        crystal_system="cubic",
        fom=10.0,
        hkl_assignments=hkl,
        n_indexed=3,
    )
    f = smith_snyder_fom(sol, peaks)
    assert f > 1.0


def test_smith_snyder_fom_decreases_with_error():
    a_true = 4.157
    hkl = [(1, 0, 0), (1, 1, 0), (2, 0, 0)]
    peaks = [a_true / math.sqrt(n2) for n2 in [1, 2, 4]]
    sol_perfect = LatticeSolution(
        cell=CellParams(a=a_true, b=a_true, c=a_true),
        crystal_system="cubic",
        fom=10.0,
        hkl_assignments=hkl,
        n_indexed=3,
    )
    sol_off = LatticeSolution(
        cell=CellParams(a=a_true + 0.1, b=a_true + 0.1, c=a_true + 0.1),
        crystal_system="cubic",
        fom=10.0,
        hkl_assignments=hkl,
        n_indexed=3,
    )
    f_perfect = smith_snyder_fom(sol_perfect, peaks)
    f_off = smith_snyder_fom(sol_off, peaks)
    assert f_perfect > f_off


def test_smith_snyder_fom_on_treor_solution_positive():
    sols = index_treor(_LAB6_PEAKS, crystal_systems=["cubic"], tolerance=0.05)
    best = sols[0]
    f = smith_snyder_fom(best, sorted(_LAB6_PEAKS, reverse=True))
    assert f > 0
    assert math.isfinite(f)


# --------------------------------------------------------------------- #
# End-to-end: Treor → rank → dedup → FOM
# --------------------------------------------------------------------- #


def test_end_to_end_treor_rank_dedup_lab6():
    """Run Treor, rank, dedup; final list should contain one good cubic
    solution with a within 0.01 Å of LaB6."""
    raw = index_treor(_LAB6_PEAKS, crystal_systems=["cubic"], tolerance=0.05)
    ranked = rank_solutions(raw)
    deduped = deduplicate(ranked, tol_cell=0.01)
    assert deduped, "expected at least one deduplicated solution"
    best = deduped[0]
    assert best.cell.a == pytest.approx(_LAB6_A, abs=0.01)
    assert best.crystal_system == "cubic"
    # Re-evaluate FOM with wolff_fom.
    refined_fom = wolff_fom(best, sorted(_LAB6_PEAKS, reverse=True))
    assert refined_fom > 10.0
