"""Tests for treor.py indexing (T9.2)."""

from __future__ import annotations

import math

import pytest

from xinmatch.core.index.lattice import LatticeSolution
from xinmatch.core.index.treor import index_treor

# LaB6 — cubic (Pm-3m), a = 4.15699 Å.  Synthetic noise-free d's:
_LAB6_A = 4.157
_LAB6_PEAKS = [
    _LAB6_A / math.sqrt(n2)
    for n2 in [1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20]
]


# --------------------------------------------------------------------- #
# Basic API & validation
# --------------------------------------------------------------------- #


def test_index_treor_empty_input_raises():
    with pytest.raises(ValueError, match="peaks_d must not be empty"):
        index_treor([])


def test_index_treor_nonpositive_tolerance_raises():
    with pytest.raises(ValueError, match="tolerance must be positive"):
        index_treor([4.157], tolerance=0.0)


def test_index_treor_unknown_crystal_system_raises():
    with pytest.raises(ValueError, match="unknown crystal system"):
        index_treor([4.157], crystal_systems=["weird"])


def test_index_treor_nonpositive_wavelength_raises():
    with pytest.raises(ValueError, match="wavelength must be positive"):
        index_treor([4.157], wavelength=0.0)


# --------------------------------------------------------------------- #
# Cubic LaB6 — the central acceptance test
# --------------------------------------------------------------------- #


def test_index_treor_lab6_cubic_finds_a_within_001():
    """Treor on LaB6 synthetic peaks → recovers a with |Δa| < 0.01 Å."""
    sols = index_treor(_LAB6_PEAKS, crystal_systems=["cubic"], tolerance=0.05)
    assert sols, "expected at least one cubic solution for LaB6"
    best = sols[0]
    assert best.crystal_system == "cubic"
    assert best.cell.a == pytest.approx(_LAB6_A, abs=0.01)
    assert best.cell.b == pytest.approx(_LAB6_A, abs=0.01)
    assert best.cell.c == pytest.approx(_LAB6_A, abs=0.01)
    # Most of the input peaks should be indexed.
    assert best.n_indexed >= len(_LAB6_PEAKS) * 0.7
    # FOM should be > 0 and finite.
    assert math.isfinite(best.fom)
    assert best.fom > 0


def test_index_treor_lab6_cubic_assigns_hkl_to_first_peak():
    """First peak (largest d) should be (1,0,0)."""
    sols = index_treor(_LAB6_PEAKS, crystal_systems=["cubic"], tolerance=0.05)
    best = sols[0]
    # hkl_assignments are in order of *sorted* (d-desc) peaks.
    assert best.hkl_assignments[0] == (1, 0, 0)


def test_index_treor_lab6_cubic_tolerance_too_tight_few_solutions():
    """Tolerance = 1e-10 — Treor finds only solutions with near-exact
    matches (true a and its supercell multiples)."""
    sols = index_treor(_LAB6_PEAKS, crystal_systems=["cubic"], tolerance=1e-10)
    # With super-strict tolerance, only the true a (and supercell multiples)
    # should survive — at most a handful (each supercell multiple is one
    # candidate).
    assert len(sols) <= 15


def test_index_treor_lab6_default_crystal_systems_runs():
    """Default crystal systems list (cubic + tet + hex + ortho) — runs
    without error and produces cubic result."""
    sols = index_treor(_LAB6_PEAKS, tolerance=0.05)
    assert sols
    assert any(s.crystal_system == "cubic" for s in sols)


def test_index_treor_returns_lattice_solution_objects():
    sols = index_treor(_LAB6_PEAKS[:6], crystal_systems=["cubic"], tolerance=0.05)
    assert all(isinstance(s, LatticeSolution) for s in sols)
    assert all(s.program == "treor" for s in sols)


def test_index_treor_results_sorted_by_fom_descending():
    sols = index_treor(_LAB6_PEAKS, crystal_systems=["cubic"], tolerance=0.05)
    foms = [s.fom for s in sols]
    assert foms == sorted(foms, reverse=True)


# --------------------------------------------------------------------- #
# Tetragonal / hexagonal / orthorhombic simplified paths
# --------------------------------------------------------------------- #


def test_index_treor_tetragonal_simple_runs():
    """A synthetic tetragonal: a=4, c=6, peaks (1,0,0),(0,0,1),(1,1,0)."""
    a, c = 4.0, 6.0
    peaks = [a, c, a / math.sqrt(2), c / 2]
    sols = index_treor(peaks, crystal_systems=["tetragonal"], tolerance=0.05)
    assert sols, "expected tetragonal solutions"
    best = sols[0]
    assert best.crystal_system == "tetragonal"
    assert best.cell.a == pytest.approx(a, abs=0.05)
    assert best.cell.c == pytest.approx(c, abs=0.05)


def test_index_treor_orthorhombic_simple_runs():
    """Synthetic orthorhombic a=4, b=5, c=6 — first three peaks give
    the axes directly. The algorithm finds one of the (a, b, c)
    permutations; we accept any of them (axis relabelling is a
    lattice-metric singularity — see Treor manual)."""
    a, b, c = 4.0, 5.0, 6.0
    peaks = [a, b, c]
    sols = index_treor(peaks, crystal_systems=["orthorhombic"], tolerance=0.05)
    assert sols, "expected orthorhombic solutions"
    best = sols[0]
    # The cell should be a permutation of (4, 5, 6) — verify as a set.
    cell_set = {best.cell.a, best.cell.b, best.cell.c}
    assert len(cell_set) == 3
    for v in (a, b, c):
        assert any(abs(cv - v) <= 0.05 for cv in cell_set), \
            f"value {v} not present in cell {best.cell}"


def test_index_treor_hexagonal_simple_runs():
    """Synthetic hexagonal: a=2 (so (1,0,0) → d=√3 ≈ 1.732),
    c=2 → (0,0,1) d=2."""
    a_true = 2.0
    c_true = 2.0
    d_100 = a_true * math.sqrt(3.0) / 2.0  # hex (1,0,0)
    d_001 = c_true
    peaks = [d_100, d_001, d_100 / math.sqrt(3.0)]  # (1,1,0)
    sols = index_treor(peaks, crystal_systems=["hexagonal"], tolerance=0.05)
    assert sols
    best = sols[0]
    assert best.cell.a == pytest.approx(a_true, abs=0.05)
    assert best.cell.c == pytest.approx(c_true, abs=0.05)


def test_index_treor_monoclinic_unsupported_skipped_silently():
    """Monoclinic / triclinic are not implemented — request skipped,
    no solutions returned for that branch (but no exception raised)."""
    sols = index_treor(_LAB6_PEAKS, crystal_systems=["monoclinic"], tolerance=0.05)
    assert sols == []


# --------------------------------------------------------------------- #
# Sanity: synthetic wrong-pattern produces poor / no solution
# --------------------------------------------------------------------- #


def test_index_treor_random_peaks_cubic_low_or_no_solution():
    """Truly random peaks should not produce a high-FOM cubic solution."""
    # 5 random peaks unlikely to fit any cubic cell.
    peaks = [3.14159, 2.71828, 1.61803, 1.41421, 0.86603]
    sols = index_treor(peaks, crystal_systems=["cubic"], tolerance=0.001)
    # Either no solution or all solutions index very few peaks.
    for sol in sols:
        assert sol.n_indexed < len(peaks)
