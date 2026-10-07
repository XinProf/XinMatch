"""Tests for structure-factor physics (T10.2)."""

import pytest

from xinmatch.core.model.entry import CellParams
from xinmatch.core.refine.structure_factor import (
    Atom,
    atomic_scattering_factor,
    debye_waller_factor,
    lorentz_polarization,
    multiplicity,
    structure_factor,
)


# ---------------------------------------------------------------------------
# Atomic scattering factor
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("element", "z"),
    [("H", 1), ("C", 6), ("N", 7), ("O", 8), ("Na", 11), ("Si", 14),
     ("Fe", 26), ("Cu", 29), ("Pb", 82), ("U", 92)],
)
def test_scattering_factor_at_theta_zero_equals_z(element, z):
    """f(s=0) = number of electrons = Z (within tabulated coefficient precision)."""
    assert abs(atomic_scattering_factor(element, 0.0) - z) < 0.1


def test_scattering_factor_decreases_with_s():
    """f(s) is monotonically decreasing (forward scattering strongest)."""
    f0 = atomic_scattering_factor("Si", 0.0)
    f1 = atomic_scattering_factor("Si", 0.3)
    f2 = atomic_scattering_factor("Si", 0.6)
    assert f0 > f1 > f2 > 0


def test_scattering_factor_unknown_element_raises():
    with pytest.raises(ValueError):
        atomic_scattering_factor("Xx", 0.0)


# ---------------------------------------------------------------------------
# Debye-Waller
# ---------------------------------------------------------------------------
def test_debye_waller_at_s_zero_is_one():
    assert debye_waller_factor(1.0, 0.0) == pytest.approx(1.0)


def test_debye_waller_decreases_with_b_and_s():
    assert debye_waller_factor(2.0, 0.5) < debye_waller_factor(1.0, 0.5)
    assert debye_waller_factor(1.0, 0.5) < debye_waller_factor(1.0, 0.2)


# ---------------------------------------------------------------------------
# Lorentz-polarisation
# ---------------------------------------------------------------------------
def test_lp_at_90_deg():
    """At 2θ = 90°, LP = (1 + P·0) / (sin45·cos45) = 1 / 0.5 = 2 (P=0)."""
    assert lorentz_polarization(90.0, wavelength=1.54, polarization=0.0) == pytest.approx(2.0)


def test_lp_zero_or_negative_denominator_returns_zero():
    assert lorentz_polarization(0.0, wavelength=1.54) == 0.0


# ---------------------------------------------------------------------------
# Multiplicity
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("hkl", "expected"),
    [((1, 1, 1), 8), ((2, 0, 0), 6), ((2, 2, 0), 12), ((3, 1, 1), 24),
     ((2, 2, 2), 8), ((4, 0, 0), 6), ((3, 3, 1), 24), ((4, 2, 0), 24)],
)
def test_multiplicity_cubic(hkl, expected):
    assert multiplicity(hkl, "cubic") == expected


def test_multiplicity_cubic_general_is_48():
    assert multiplicity((3, 2, 1), "cubic") == 48


def test_multiplicity_orthorhombic():
    assert multiplicity((1, 1, 1), "orthorhombic") == 8
    assert multiplicity((1, 0, 0), "orthorhombic") == 2
    assert multiplicity((1, 1, 0), "orthorhombic") == 4


def test_multiplicity_tetragonal():
    assert multiplicity((1, 0, 0), "tetragonal") == 4
    assert multiplicity((1, 1, 0), "tetragonal") == 4
    # (h,k,l) general with h≠k and l≠0 → 16; (h,k,0) with h≠k → 8.
    assert multiplicity((2, 1, 1), "tetragonal") == 16
    assert multiplicity((2, 1, 0), "tetragonal") == 8


def test_multiplicity_monoclinic():
    assert multiplicity((1, 1, 1), "monoclinic") == 4
    assert multiplicity((1, 0, 1), "monoclinic") == 2


def test_multiplicity_triclinic():
    assert multiplicity((1, 2, 3), "triclinic") == 2


def test_multiplicity_zero_hkl():
    assert multiplicity((0, 0, 0), "cubic") == 1


# ---------------------------------------------------------------------------
# Structure factor
# ---------------------------------------------------------------------------
def test_structure_factor_empty_atoms_is_zero():
    cell = CellParams(5.0, 5.0, 5.0)
    assert structure_factor((1, 0, 0), [], cell, wavelength=1.54) == 0j


def test_structure_factor_si_diamond_extinctions():
    """Si diamond cubic: F(200) = 0 (forbidden by the glide plane)."""
    cell = CellParams(5.431, 5.431, 5.431)
    atoms = [Atom("Si", 0, 0, 0), Atom("Si", 0.25, 0.25, 0.25)]
    f200 = structure_factor((2, 0, 0), atoms, cell, wavelength=1.5406)
    assert abs(f200) < 1e-6


def test_structure_factor_si_allowed_reflection():
    """Si (111) is allowed and |F| > 0."""
    cell = CellParams(5.431, 5.431, 5.431)
    atoms = [Atom("Si", 0, 0, 0), Atom("Si", 0.25, 0.25, 0.25)]
    f111 = structure_factor((1, 1, 1), atoms, cell, wavelength=1.5406)
    assert abs(f111) > 1.0


def test_structure_factor_bcc_na_extinction():
    """BCC Na: (100) forbidden (h+k+l odd), (200) allowed."""
    cell = CellParams(4.29, 4.29, 4.29)
    atoms = [Atom("Na", 0, 0, 0), Atom("Na", 0.5, 0.5, 0.5)]
    f100 = structure_factor((1, 0, 0), atoms, cell, wavelength=1.5406)
    f200 = structure_factor((2, 0, 0), atoms, cell, wavelength=1.5406)
    assert abs(f100) < 1e-6
    assert abs(f200) > 1.0
