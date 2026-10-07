"""Tests for the Le Bail pattern decomposition (T10.3)."""

import math

import numpy as np

from xinmatch.core.index.lattice import compute_d
from xinmatch.core.model.entry import CellParams
from xinmatch.core.model.pattern import Pattern
from xinmatch.core.refine.le_bail import le_bail
from xinmatch.core.refine.peak_model import PeakModel
from xinmatch.core.refine.structure_factor import multiplicity

_WAVELENGTH = 1.5406  # Cu Kα1


def _two_theta(d: float) -> float:
    sin_theta = min(max(_WAVELENGTH / (2.0 * d), -1.0), 1.0)
    return math.degrees(2.0 * math.asin(sin_theta))


def _crystal_system(cell: CellParams) -> str:
    a, b, c = cell.a, cell.b, cell.c
    alpha, beta, gamma = cell.alpha, cell.beta, cell.gamma
    tol = 1e-3
    if abs(a - b) < tol and abs(b - c) < tol and abs(alpha - 90) < tol and abs(beta - 90) < tol and abs(gamma - 90) < tol:
        return "cubic"
    if abs(a - b) < tol and abs(alpha - 90) < tol and abs(beta - 90) < tol and abs(gamma - 90) < tol:
        return "tetragonal"
    if abs(a - b) >= tol and abs(b - c) >= tol and abs(alpha - 90) < tol and abs(beta - 90) < tol and abs(gamma - 90) < tol:
        return "orthorhombic"
    return "triclinic"


def _synthetic_pattern(
    cell: CellParams,
    hkl_intensities: dict[tuple[int, int, int], float],
    peak_model: PeakModel,
    tth_range: tuple[float, float] = (10.0, 100.0),
    step: float = 0.02,
) -> Pattern:
    """Build a noiseless powder pattern from known per-reflection intensities.

    The peak area for ``(hkl)`` is ``I(hkl) * m(hkl)`` where ``m`` is the
    multiplicity, matching the convention used inside :func:`le_bail`.
    """
    cs = _crystal_system(cell)
    tth = np.arange(tth_range[0], tth_range[1] + step, step)
    y = np.zeros_like(tth)
    for hkl, intensity in hkl_intensities.items():
        d = compute_d(hkl, cell)
        pos = _two_theta(d)
        fwhm = peak_model.fwhm(pos)
        m = multiplicity(hkl, cs)
        y += intensity * m * peak_model.shape_function(tth, pos, fwhm, 1.0)
    return Pattern(two_theta=tth, intensity=y, wavelength=_WAVELENGTH, step=step)


def test_le_bail_simple_cubic_rwp_below_10():
    """Le Bail on a clean cubic pattern recovers the intensities (Rwp < 10%)."""
    cell = CellParams(4.0, 4.0, 4.0)
    pm = PeakModel(eta=0.5, asymmetry=0.0, caglioti_uvw=(0.0, 0.0, 0.01))
    # A few well-separated reflections with arbitrary intensities.
    hkl_i = {
        (1, 1, 1): 1000.0,
        (2, 0, 0): 600.0,
        (2, 2, 0): 400.0,
        (3, 1, 1): 300.0,
        (2, 2, 2): 200.0,
    }
    pattern = _synthetic_pattern(cell, hkl_i, pm, tth_range=(20.0, 90.0))

    result = le_bail(
        pattern, cell, pm,
        wavelength=_WAVELENGTH,
        n_iter=20,
        two_theta_range=(20.0, 90.0),
    )

    assert result["rwp"] < 0.10, f"Rwp = {result['rwp']:.4f} (expected < 0.10)"
    assert result["converged"] is True
    # Each input reflection should be recovered with reasonable intensity.
    # Le Bail stores Friedel-unique keys (the smaller of (h,k,l)/(-h,-k,-l)).
    recovered = result["intensities"]
    for hkl, true_i in hkl_i.items():
        key = hkl if hkl in recovered else (-hkl[0], -hkl[1], -hkl[2])
        assert key in recovered, f"hkl={hkl} not found in recovered intensities"
        ratio = recovered[key] / true_i
        assert 0.5 < ratio < 2.0, f"hkl={hkl} ratio={ratio:.3f}"


def test_le_bail_overlapping_peaks():
    """Overlapping peaks (small cell, many hkl) should still converge."""
    cell = CellParams(3.0, 3.0, 3.0)
    pm = PeakModel(eta=0.4, asymmetry=0.0, caglioti_uvw=(0.0, 0.0, 0.02))
    rng = np.random.default_rng(42)
    hkl_i: dict[tuple[int, int, int], float] = {}
    for h in range(1, 5):
        for k in range(0, h + 1):
            for ll in range(0, k + 1):
                if h == 0 and k == 0 and ll == 0:
                    continue
                hkl_i[(h, k, ll)] = float(rng.uniform(100, 1000))

    pattern = _synthetic_pattern(cell, hkl_i, pm, tth_range=(10.0, 120.0))
    result = le_bail(
        pattern, cell, pm,
        wavelength=_WAVELENGTH,
        n_iter=30,
        two_theta_range=(10.0, 120.0),
    )
    assert result["rwp"] < 0.10, f"Rwp = {result['rwp']:.4f}"


def test_le_bail_empty_range_returns_empty():
    cell = CellParams(4.0, 4.0, 4.0)
    pm = PeakModel(caglioti_uvw=(0.0, 0.0, 0.01))
    pattern = Pattern(
        two_theta=np.array([10.0, 10.02]),
        intensity=np.array([1.0, 1.0]),
        wavelength=_WAVELENGTH,
    )
    result = le_bail(pattern, cell, pm, wavelength=_WAVELENGTH, two_theta_range=(50.0, 60.0))
    assert result["intensities"] == {}
    assert result["converged"] is False


def test_le_bail_intensities_are_non_negative():
    cell = CellParams(4.0, 4.0, 4.0)
    pm = PeakModel(caglioti_uvw=(0.0, 0.0, 0.01))
    hkl_i = {(1, 1, 1): 500.0, (2, 0, 0): 500.0}
    pattern = _synthetic_pattern(cell, hkl_i, pm, tth_range=(20.0, 60.0))
    result = le_bail(
        pattern, cell, pm,
        wavelength=_WAVELENGTH,
        n_iter=10,
        two_theta_range=(20.0, 60.0),
    )
    for val in result["intensities"].values():
        assert val >= 0.0
