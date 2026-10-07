"""Tests for lattice.py d-spacing formulas and LatticeSolution (T9.1)."""

from __future__ import annotations

import math

import pytest

from xinmatch.core.index.lattice import (
    CRYSTAL_SYSTEMS,
    LatticeSolution,
    cell_volume,
    compute_d,
    compute_d_cubic,
    compute_d_for_system,
    compute_d_hexagonal,
    compute_d_orthorhombic,
    compute_d_tetragonal,
    d_to_reciprocal_lattice,
    reciprocal_cell,
    solve_reciprocal_lattice,
)
from xinmatch.core.model.entry import CellParams

# --------------------------------------------------------------------- #
# Cubic
# --------------------------------------------------------------------- #


def test_compute_d_cubic_basic():
    """a=4.157, (1,0,0) → d=4.157; (1,1,0) → d=a/√2."""
    a = 4.157
    assert abs(compute_d_cubic((1, 0, 0), a) - a) < 1e-12
    assert abs(compute_d_cubic((1, 1, 0), a) - a / math.sqrt(2)) < 1e-12
    assert abs(compute_d_cubic((1, 1, 1), a) - a / math.sqrt(3)) < 1e-12
    assert abs(compute_d_cubic((2, 0, 0), a) - a / 2) < 1e-12


def test_compute_d_cubic_zero_hkl_raises():
    with pytest.raises(ValueError, match="not a valid reflection"):
        compute_d_cubic((0, 0, 0), 4.0)


def test_compute_d_for_system_dispatch():
    """compute_d_for_system should match the system-specific formulas."""
    cell = CellParams(a=4.157, b=4.157, c=4.157)
    for hkl in [(1, 0, 0), (1, 1, 0), (1, 1, 1), (2, 1, 0), (2, 2, 1)]:
        d_dispatch = compute_d_for_system(hkl, cell, "cubic")
        d_direct = compute_d_cubic(hkl, cell.a)
        assert abs(d_dispatch - d_direct) < 1e-12


def test_compute_d_cubic_lab6_first_peaks():
    """LaB6 cubic, a=4.157 — first few d's match the textbook table."""
    a = 4.157
    # (hkl, expected d)
    table = [
        ((1, 0, 0), 4.157),
        ((1, 1, 0), a / math.sqrt(2)),
        ((1, 1, 1), a / math.sqrt(3)),
        ((2, 0, 0), a / 2),
        ((2, 1, 0), a / math.sqrt(5)),
        ((2, 1, 1), a / math.sqrt(6)),
        ((2, 2, 0), a / math.sqrt(8)),
        ((3, 0, 0), a / 3),
        ((2, 2, 2), a / math.sqrt(12)),
    ]
    for hkl, expected in table:
        got = compute_d_cubic(hkl, a)
        assert abs(got - expected) < 1e-9, f"hkl={hkl} expected={expected} got={got}"


# --------------------------------------------------------------------- #
# Tetragonal / orthorhombic / hexagonal closed forms
# --------------------------------------------------------------------- #


def test_compute_d_tetragonal_a_eq_c_reduces_to_cubic():
    """If a=c, tetragonal formula reduces to cubic."""
    a = 4.157
    hkl = (1, 1, 1)
    d_tetra = compute_d_tetragonal(hkl, a, a)
    d_cubic = compute_d_cubic(hkl, a)
    assert abs(d_tetra - d_cubic) < 1e-12


def test_compute_d_orthorhombic_axis_aligned():
    """For (1,0,0) → d=a; (0,1,0) → d=b; (0,0,1) → d=c."""
    a, b, c = 4.0, 5.0, 6.0
    assert abs(compute_d_orthorhombic((1, 0, 0), a, b, c) - 4.0) < 1e-12
    assert abs(compute_d_orthorhombic((0, 1, 0), a, b, c) - 5.0) < 1e-12
    assert abs(compute_d_orthorhombic((0, 0, 1), a, b, c) - 6.0) < 1e-12


def test_compute_d_hexagonal_a_eq_known():
    """Hexagonal a=2.0, c=√3 ≈ 1.732 — (1,0,0) → d = a·√3/2 = 1.7320."""
    a = 2.0
    c = math.sqrt(3.0)
    d = compute_d_hexagonal((1, 0, 0), a, c)
    assert abs(d - math.sqrt(3.0)) < 1e-12
    # (0,0,1) → d = c
    assert abs(compute_d_hexagonal((0, 0, 1), a, c) - c) < 1e-12


def test_compute_d_general_matches_closed_forms():
    """The general metric-tensor formula matches the closed-form for cubic
    when α=β=γ=90°."""
    cell = CellParams(a=4.157, b=4.157, c=4.157)
    for hkl in [(1, 0, 0), (1, 1, 0), (2, 1, 1), (2, 2, 1)]:
        d_general = compute_d(hkl, cell)
        d_cubic = compute_d_cubic(hkl, cell.a)
        assert abs(d_general - d_cubic) < 1e-9


def test_compute_d_triclinic_matches_hex_setting():
    """Trigonal/hexagonal in hex setting — set up as a "triclinic" cell
    with α=β=90°, γ=120° and verify general formula matches the
    hexagonal closed form."""
    a = 2.0
    c = math.sqrt(3.0)
    cell = CellParams(a=a, b=a, c=c, alpha=90.0, beta=90.0, gamma=120.0)
    for hkl in [(1, 0, 0), (1, 1, 0), (0, 0, 1), (1, 1, 1)]:
        d_general = compute_d(hkl, cell)
        d_hex = compute_d_hexagonal(hkl, a, c)
        assert abs(d_general - d_hex) < 1e-9, f"hkl={hkl}: general={d_general} hex={d_hex}"


# --------------------------------------------------------------------- #
# cell_volume + reciprocal_cell
# --------------------------------------------------------------------- #


def test_cell_volume_cubic():
    cell = CellParams(a=4.157, b=4.157, c=4.157)
    expected = 4.157 ** 3
    assert abs(cell_volume(cell) - expected) < 1e-9


def test_cell_volume_orthorhombic():
    cell = CellParams(a=4.0, b=5.0, c=6.0)
    assert abs(cell_volume(cell) - 120.0) < 1e-9


def test_cell_volume_hexagonal():
    """Hexagonal V = a²·c·sin(120°) = a²·c·√3/2."""
    a = 2.0
    c = 1.5
    cell = CellParams(a=a, b=a, c=c, alpha=90.0, beta=90.0, gamma=120.0)
    expected = a * a * c * math.sin(math.radians(120.0))
    assert abs(cell_volume(cell) - expected) < 1e-9


def test_cell_volume_degenerate_raises():
    """Angles that don't form a valid 3D cell raise ValueError."""
    cell = CellParams(a=1.0, b=1.0, c=1.0, alpha=0.0, beta=0.0, gamma=0.0)
    with pytest.raises(ValueError, match="degenerate"):
        cell_volume(cell)


def test_reciprocal_cell_cubic_orthogonal():
    """For cubic a=4, reciprocal a* = 1/a = 0.25, all angles 90°."""
    cell = CellParams(a=4.0, b=4.0, c=4.0)
    a_s, b_s, c_s, al_s, be_s, ga_s = reciprocal_cell(cell)
    assert abs(a_s - 0.25) < 1e-9
    assert abs(b_s - 0.25) < 1e-9
    assert abs(c_s - 0.25) < 1e-9
    assert abs(al_s - 90.0) < 1e-9
    assert abs(be_s - 90.0) < 1e-9
    assert abs(ga_s - 90.0) < 1e-9


def test_reciprocal_cell_volume_consistency():
    """V_direct · V_recip = 1 (reciprocal volume is 1/V)."""
    cell = CellParams(a=5.0, b=6.0, c=7.0, alpha=80.0, beta=95.0, gamma=105.0)
    a_s, b_s, c_s, al_s, be_s, ga_s = reciprocal_cell(cell)
    # Reciprocal cell volume via the same formula:
    rc = CellParams(a=a_s, b=b_s, c=c_s, alpha=al_s, beta=be_s, gamma=ga_s)
    v_recip = cell_volume(rc)
    v_direct = cell_volume(cell)
    assert abs(v_direct * v_recip - 1.0) < 1e-6


# --------------------------------------------------------------------- #
# d_to_reciprocal_lattice
# --------------------------------------------------------------------- #


def test_d_to_reciprocal_lattice_cubic():
    """Cubic: a* = sqrt(h²+k²+l²)/d."""
    d = 4.157
    hkl = (1, 0, 0)
    (a_star,) = d_to_reciprocal_lattice(d, hkl, "cubic")
    assert abs(a_star - 1.0 / d) < 1e-12
    (a_star_2,) = d_to_reciprocal_lattice(d / math.sqrt(2), (1, 1, 0), "cubic")
    assert abs(a_star_2 - 1.0 / d) < 1e-12


def test_d_to_reciprocal_lattice_tetragonal_axis_aligned():
    """Tetragonal: (1,0,0) → a*; (0,0,1) → c*."""
    (a_star,) = d_to_reciprocal_lattice(4.0, (1, 0, 0), "tetragonal")
    assert abs(a_star - 0.25) < 1e-12
    (c_star,) = d_to_reciprocal_lattice(5.0, (0, 0, 1), "tetragonal")
    assert abs(c_star - 0.2) < 1e-12


def test_d_to_reciprocal_lattice_tetragonal_underdetermined_raises():
    """Tetragonal with both (h,k)≠0 and l≠0 → underdetermined → ValueError."""
    with pytest.raises(ValueError, match="cannot be solved"):
        d_to_reciprocal_lattice(2.0, (1, 1, 1), "tetragonal")


def test_d_to_reciprocal_lattice_hexagonal_axis_aligned():
    """Hexagonal (1,0,0): 1/d² = (4/3)/a² → a = (2/√3)·d → a* = √3/(2·d)."""
    d = 2.0
    (a_star,) = d_to_reciprocal_lattice(d, (1, 0, 0), "hexagonal")
    expected = math.sqrt(3.0) / (2.0 * d)
    assert abs(a_star - expected) < 1e-12


def test_d_to_reciprocal_lattice_orthorhombic_axis_aligned():
    """Orthorhombic: (1,0,0)→a*, (0,1,0)→b*, (0,0,1)→c*."""
    assert abs(d_to_reciprocal_lattice(4.0, (1, 0, 0), "orthorhombic")[0] - 0.25) < 1e-12
    assert abs(d_to_reciprocal_lattice(5.0, (0, 1, 0), "orthorhombic")[0] - 0.20) < 1e-12
    assert abs(d_to_reciprocal_lattice(6.0, (0, 0, 1), "orthorhombic")[0] - 1.0 / 6.0) < 1e-12


def test_d_to_reciprocal_lattice_orthorhombic_mixed_raises():
    """Orthorhombic with (1,1,0) → cannot solve a*, b* separately from
    one peak."""
    with pytest.raises(ValueError, match="axis-aligned"):
        d_to_reciprocal_lattice(2.0, (1, 1, 0), "orthorhombic")


def test_d_to_reciprocal_lattice_unknown_system_raises():
    with pytest.raises(ValueError, match="unknown crystal system"):
        d_to_reciprocal_lattice(2.0, (1, 0, 0), "weird")


def test_d_to_reciprocal_lattice_nonpositive_d_raises():
    with pytest.raises(ValueError, match="d-spacing must be positive"):
        d_to_reciprocal_lattice(0.0, (1, 0, 0), "cubic")
    with pytest.raises(ValueError, match="d-spacing must be positive"):
        d_to_reciprocal_lattice(-1.0, (1, 0, 0), "cubic")


def test_d_to_reciprocal_lattice_zero_hkl_cubic_raises():
    with pytest.raises(ValueError):
        d_to_reciprocal_lattice(2.0, (0, 0, 0), "cubic")


# --------------------------------------------------------------------- #
# solve_reciprocal_lattice
# --------------------------------------------------------------------- #


def test_solve_reciprocal_lattice_cubic_single_peak():
    """Cubic solve with 1 peak: a* = sqrt(N²)/d."""
    d = 4.157
    hkl_list = [(1, 0, 0)]
    (a_star,) = solve_reciprocal_lattice([d], hkl_list, "cubic")
    assert abs(a_star - 1.0 / d) < 1e-12


def test_solve_reciprocal_lattice_cubic_multi_peak_consistency():
    """Cubic LSQ — for synthetic noise-free data, all peaks give the
    same a*."""
    a_true = 4.157
    # (hkl, d)
    pairs = [
        ((1, 0, 0), a_true),
        ((1, 1, 0), a_true / math.sqrt(2)),
        ((2, 0, 0), a_true / 2),
        ((2, 1, 1), a_true / math.sqrt(6)),
        ((2, 2, 0), a_true / math.sqrt(8)),
    ]
    peaks_d = [d for _hkl, d in pairs]
    hkl_list = [hkl for hkl, _d in pairs]
    (a_star,) = solve_reciprocal_lattice(peaks_d, hkl_list, "cubic")
    assert abs(a_star - 1.0 / a_true) < 1e-9


def test_solve_reciprocal_lattice_tetragonal_two_unknowns():
    """Tetragonal with both (1,0,0) (gives a) and (0,0,1) (gives c)."""
    a_true = 4.0
    c_true = 5.0
    peaks_d = [a_true, c_true]
    hkl_list = [(1, 0, 0), (0, 0, 1)]
    (a_star, c_star) = solve_reciprocal_lattice(peaks_d, hkl_list, "tetragonal")
    assert abs(a_star - 1.0 / a_true) < 1e-12
    assert abs(c_star - 1.0 / c_true) < 1e-12


def test_solve_reciprocal_lattice_orthorhombic_three_axes():
    a_true, b_true, c_true = 4.0, 5.0, 6.0
    peaks_d = [a_true, b_true, c_true]
    hkl_list = [(1, 0, 0), (0, 1, 0), (0, 0, 1)]
    a_s, b_s, c_s = solve_reciprocal_lattice(peaks_d, hkl_list, "orthorhombic")
    assert abs(a_s - 1.0 / a_true) < 1e-12
    assert abs(b_s - 1.0 / b_true) < 1e-12
    assert abs(c_s - 1.0 / c_true) < 1e-12


def test_solve_reciprocal_lattice_length_mismatch_raises():
    with pytest.raises(ValueError, match="same length"):
        solve_reciprocal_lattice([1.0], [(1, 0, 0), (0, 0, 1)], "cubic")


def test_solve_reciprocal_lattice_unsupported_system_raises():
    with pytest.raises(NotImplementedError):
        solve_reciprocal_lattice([1.0], [(1, 0, 0)], "monoclinic")


def test_crystal_systems_tuple():
    assert "cubic" in CRYSTAL_SYSTEMS
    assert "triclinic" in CRYSTAL_SYSTEMS
    assert len(CRYSTAL_SYSTEMS) == 7


# --------------------------------------------------------------------- #
# LatticeSolution dataclass
# --------------------------------------------------------------------- #


def test_lattice_solution_construction():
    cell = CellParams(a=4.157, b=4.157, c=4.157)
    sol = LatticeSolution(
        cell=cell,
        crystal_system="cubic",
        fom=42.0,
        hkl_assignments=[(1, 0, 0), None, (1, 1, 0)],
        n_indexed=2,
        program="treor",
    )
    assert sol.crystal_system == "cubic"
    assert sol.n_indexed == 2
    assert sol.program == "treor"
    assert sol.n_total == 3
    assert sol.n_unindexed == 1
    assert abs(sol.volume - 4.157 ** 3) < 1e-9


def test_lattice_solution_derives_n_indexed_from_assignments():
    cell = CellParams(a=4.0, b=4.0, c=4.0)
    sol = LatticeSolution(
        cell=cell,
        crystal_system="cubic",
        fom=1.0,
        hkl_assignments=[(1, 0, 0), (1, 1, 0), None, None],
    )
    assert sol.n_indexed == 2


def test_lattice_solution_invalid_crystal_system_raises():
    cell = CellParams(a=4.0, b=4.0, c=4.0)
    with pytest.raises(ValueError, match="unknown crystal system"):
        LatticeSolution(
            cell=cell,
            crystal_system="weird",
            fom=1.0,
            hkl_assignments=[],
        )
