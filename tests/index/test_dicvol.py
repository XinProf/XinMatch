"""Tests for dicvol.py indexing (T9.3)."""

from __future__ import annotations

import math

import pytest

from xinmatch.core.index.dicvol import index_dicvol
from xinmatch.core.index.lattice import LatticeSolution

# LaB6 — cubic, a = 4.157 Å.  Same synthetic peaks as Treor test.
_LAB6_A = 4.157
_LAB6_PEAKS = [
    _LAB6_A / math.sqrt(n2)
    for n2 in [1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20]
]


# --------------------------------------------------------------------- #
# Basic API & validation
# --------------------------------------------------------------------- #


def test_index_dicvol_empty_input_raises():
    with pytest.raises(ValueError, match="peaks_d must not be empty"):
        index_dicvol([])


def test_index_dicvol_nonpositive_tolerance_raises():
    with pytest.raises(ValueError, match="tolerance must be positive"):
        index_dicvol([4.157], tolerance=0.0)


def test_index_dicvol_unknown_crystal_system_raises():
    with pytest.raises(ValueError, match="unknown crystal system"):
        index_dicvol([4.157], crystal_systems=["weird"])


def test_index_dicvol_nonpositive_wavelength_raises():
    with pytest.raises(ValueError, match="wavelength must be positive"):
        index_dicvol([4.157], wavelength=0.0)


# --------------------------------------------------------------------- #
# Cubic LaB6 — central acceptance test
# --------------------------------------------------------------------- #


def test_index_dicvol_lab6_cubic_finds_a_within_001():
    """Dicvol on LaB6 synthetic peaks → recovers a with |Δa| < 0.01 Å."""
    sols = index_dicvol(_LAB6_PEAKS, crystal_systems=["cubic"], tolerance=0.05)
    assert sols, "expected at least one cubic Dicvol solution for LaB6"
    best = sols[0]
    assert best.crystal_system == "cubic"
    assert best.cell.a == pytest.approx(_LAB6_A, abs=0.01)
    assert best.cell.b == pytest.approx(_LAB6_A, abs=0.01)
    assert best.cell.c == pytest.approx(_LAB6_A, abs=0.01)
    assert best.n_indexed >= len(_LAB6_PEAKS) * 0.7
    assert math.isfinite(best.fom)
    assert best.fom > 0


def test_index_dicvol_returns_lattice_solution_objects():
    sols = index_dicvol(_LAB6_PEAKS[:6], crystal_systems=["cubic"], tolerance=0.05)
    assert all(isinstance(s, LatticeSolution) for s in sols)
    assert all(s.program == "dicvol" for s in sols)


def test_index_dicvol_results_sorted_by_fom_descending():
    sols = index_dicvol(_LAB6_PEAKS, crystal_systems=["cubic"], tolerance=0.05)
    foms = [s.fom for s in sols]
    assert foms == sorted(foms, reverse=True)


def test_index_dicvol_lab6_default_crystal_systems_runs():
    """Default crystal systems list — should produce a cubic result."""
    sols = index_dicvol(_LAB6_PEAKS, tolerance=0.05)
    assert sols
    assert any(s.crystal_system == "cubic" for s in sols)


# --------------------------------------------------------------------- #
# Tetragonal / hexagonal / orthorhombic simplified paths
# --------------------------------------------------------------------- #


def test_index_dicvol_tetragonal_simple_runs():
    """Synthetic tetragonal a=4, c=6 — Treor-style simplified Dicvol."""
    a, c = 4.0, 6.0
    peaks = [a, c, a / math.sqrt(2), c / 2]
    sols = index_dicvol(peaks, crystal_systems=["tetragonal"], tolerance=0.05)
    assert sols
    best = sols[0]
    assert best.crystal_system == "tetragonal"
    assert best.cell.a == pytest.approx(a, abs=0.05)
    assert best.cell.c == pytest.approx(c, abs=0.05)


def test_index_dicvol_orthorhombic_simple_runs():
    """Synthetic orthorhombic a=4, b=5, c=6 — first three peaks give
    the axes directly. The algorithm finds one of the (a, b, c)
    permutations; we accept any of them (axis relabelling is a
    lattice-metric singularity — see Dicvol manual)."""
    a, b, c = 4.0, 5.0, 6.0
    peaks = [a, b, c]
    sols = index_dicvol(peaks, crystal_systems=["orthorhombic"], tolerance=0.05)
    assert sols
    best = sols[0]
    # The cell should be a permutation of (4, 5, 6) — verify as a set.
    cell_set = {best.cell.a, best.cell.b, best.cell.c}
    assert len(cell_set) == 3
    for v in (a, b, c):
        assert any(abs(cv - v) <= 0.05 for cv in cell_set), \
            f"value {v} not present in cell {best.cell}"


def test_index_dicvol_hexagonal_simple_runs():
    """Synthetic hexagonal: a=2 → (1,0,0) d=√3; c=2 → (0,0,1) d=2."""
    a_true = 2.0
    c_true = 2.0
    d_100 = a_true * math.sqrt(3.0) / 2.0
    d_001 = c_true
    peaks = [d_100, d_001, d_100 / math.sqrt(3.0)]
    sols = index_dicvol(peaks, crystal_systems=["hexagonal"], tolerance=0.05)
    assert sols
    best = sols[0]
    assert best.cell.a == pytest.approx(a_true, abs=0.05)
    assert best.cell.c == pytest.approx(c_true, abs=0.05)


def test_index_dicvol_monoclinic_unsupported_skipped_silently():
    sols = index_dicvol(_LAB6_PEAKS, crystal_systems=["monoclinic"], tolerance=0.05)
    assert sols == []


# --------------------------------------------------------------------- #
# Sanity: random peaks should not produce a high-FOM solution
# --------------------------------------------------------------------- #


def test_index_dicvol_random_peaks_cubic_low_or_no_solution():
    peaks = [3.14159, 2.71828, 1.61803, 1.41421, 0.86603]
    sols = index_dicvol(peaks, crystal_systems=["cubic"], tolerance=0.001)
    for sol in sols:
        assert sol.n_indexed < len(peaks)
