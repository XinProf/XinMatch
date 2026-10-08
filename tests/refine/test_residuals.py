"""Tests for the residual analysis module (T10.5)."""

import math

import numpy as np
import pytest

from xinmatch.core.model.entry import CellParams, Entry
from xinmatch.core.model.pattern import Pattern
from xinmatch.core.model.peak import Peak
from xinmatch.core.peak.shapes import pseudo_voigt
from xinmatch.core.refine.peak_model import PeakModel
from xinmatch.core.refine.residuals import (
    ResidualReport,
    RFactorTable,
    compute_r_factors,
    residual_analysis,
)
from xinmatch.core.refine.rietveld import RietveldRefinement
from xinmatch.core.refine.structure_factor import Atom

_WAVELENGTH = 1.5406


def _two_theta(d: float) -> float:
    sin_theta = min(max(_WAVELENGTH / (2.0 * d), -1.0), 1.0)
    return math.degrees(2.0 * math.asin(sin_theta))


def test_compute_r_factors_perfect_fit():
    """A perfect fit gives Rp = Rwp = 0; chi^2 = 0; GoF = 0."""
    y = np.linspace(1, 100, 100)
    r = compute_r_factors(y, y, n_params=2)
    assert isinstance(r, RFactorTable)
    assert r.rp < 1e-12
    assert r.rwp < 1e-12
    assert r.chi2 < 1e-12
    assert r.gof < 1e-12
    assert r.n_points == 100
    assert r.n_params == 2


def test_compute_r_factors_zero_calc():
    """With y_calc = 0, Rwp = 1 (worst possible)."""
    y = np.full(50, 100.0)
    r = compute_r_factors(y, np.zeros_like(y))
    assert abs(r.rwp - 1.0) < 1e-9
    assert r.rp == 1.0
    assert r.chi2 > 0.0
    assert r.gof > 0.0


def test_compute_r_factors_with_explicit_sigma():
    """When σ is given, the variance is σ² (no Poisson fallback)."""
    y_obs = np.array([10.0, 20.0, 30.0])
    y_calc = np.array([9.0, 21.0, 29.0])
    sigma = np.array([1.0, 2.0, 3.0])
    r = compute_r_factors(y_obs, y_calc, sigma=sigma, n_params=0)
    # Manual: w_i = 1/σ_i²
    w = 1.0 / (sigma * sigma)
    num = np.sum(w * (y_obs - y_calc) ** 2)
    den = np.sum(w * y_obs * y_obs)
    expected_rwp = math.sqrt(num / den)
    assert abs(r.rwp - expected_rwp) < 1e-12
    expected_chi2 = num / max(y_obs.size - 0, 1)
    assert abs(r.chi2 - expected_chi2) < 1e-12
    expected_gof = math.sqrt(expected_chi2)
    assert abs(r.gof - expected_gof) < 1e-12


def test_compute_r_factors_mismatched_shapes_raise():
    with pytest.raises(ValueError):
        compute_r_factors(np.zeros(5), np.zeros(6))


def test_residual_analysis_basic_report():
    tth = np.arange(20.0, 80.0 + 0.02, 0.02)
    rng = np.random.default_rng(0)
    y_obs = rng.uniform(50, 100, size=tth.size)
    y_calc = y_obs + rng.normal(0, 1, size=tth.size)
    obs = Pattern(two_theta=tth, intensity=y_obs, wavelength=_WAVELENGTH, step=0.02)
    calc = Pattern(two_theta=tth, intensity=y_calc, wavelength=_WAVELENGTH, step=0.02)
    report = residual_analysis(obs, calc, n_params=5)
    assert isinstance(report, ResidualReport)
    assert isinstance(report.rfactors, RFactorTable)
    assert report.rfactors.n_points == tth.size
    assert report.rfactors.n_params == 5
    np.testing.assert_allclose(report.residual_pattern.two_theta, tth)
    np.testing.assert_allclose(
        report.residual_pattern.intensity, y_obs - y_calc, atol=1e-9
    )
    # No real residual peaks in pure noise.
    assert isinstance(report.unfitted_peaks, list)


def test_residual_analysis_mismatched_grid_raises():
    tth_a = np.arange(20.0, 30.0, 0.02)
    tth_b = np.arange(20.0, 30.0, 0.05)
    obs = Pattern(two_theta=tth_a, intensity=np.zeros_like(tth_a),
                  wavelength=_WAVELENGTH)
    calc = Pattern(two_theta=tth_b, intensity=np.zeros_like(tth_b),
                  wavelength=_WAVELENGTH)
    with pytest.raises(ValueError):
        residual_analysis(obs, calc)


def test_residual_peak_detection_synthetic_100_percent():
    """A strong unmodelled peak in the residual is detected 100% of the time."""
    tth = np.arange(20.0, 80.0 + 0.02, 0.02)
    # Background-only observed pattern + one extra strong peak.
    baseline = np.full_like(tth, 5.0)
    extra_peak = pseudo_voigt(tth, center=45.0, fwhm=0.2, amplitude=2000.0, eta=0.5)
    y_obs = baseline + extra_peak
    # The model misses the peak (calc = baseline only).
    y_calc = baseline.copy()
    obs = Pattern(two_theta=tth, intensity=y_obs, wavelength=_WAVELENGTH, step=0.02)
    calc = Pattern(two_theta=tth, intensity=y_calc, wavelength=_WAVELENGTH, step=0.02)
    report = residual_analysis(obs, calc, sensitivity="high")
    assert len(report.unfitted_peaks) >= 1
    detected = any(abs(p.two_theta - 45.0) < 0.2 for p in report.unfitted_peaks)
    assert detected, "the extra peak at 45° was not detected"


def test_residual_analysis_multiple_known_peaks():
    """Several extra peaks are all detected."""
    tth = np.arange(20.0, 90.0 + 0.02, 0.02)
    baseline = np.full_like(tth, 2.0)
    centers = (28.0, 40.5, 55.0, 70.0)
    y_obs = baseline.copy()
    for c in centers:
        y_obs = y_obs + pseudo_voigt(tth, center=c, fwhm=0.15, amplitude=1500.0,
                                      eta=0.5)
    y_calc = baseline.copy()
    obs = Pattern(two_theta=tth, intensity=y_obs, wavelength=_WAVELENGTH, step=0.02)
    calc = Pattern(two_theta=tth, intensity=y_calc, wavelength=_WAVELENGTH, step=0.02)
    report = residual_analysis(obs, calc, sensitivity="high", min_intensity_factor=3.0)
    found_centers = [p.two_theta for p in report.unfitted_peaks]
    matched = sum(
        any(abs(fc - c) < 0.3 for fc in found_centers) for c in centers
    )
    # All four inserted peaks must be recovered (100% recall).
    assert matched == len(centers), (
        f"only {matched}/{len(centers)} peaks detected: {found_centers}"
    )


def test_rwp_matches_rietveld_self_reported():
    """The Rwp reported by RietveldRefinement matches the Rwp computed by
    residual_analysis on the same (observed, fitted) pair.

    Both use the same Poisson/MAD noise-floor estimator, so the result
    must agree to floating-point tolerance.
    """
    cell = CellParams(5.431, 5.431, 5.431)
    atoms = [Atom("Si", 0, 0, 0), Atom("Si", 0.25, 0.25, 0.25)]
    pm = PeakModel(caglioti_uvw=(0.0, 0.0, 0.01))

    tth = np.arange(20.0, 90.0 + 0.02, 0.02)
    from xinmatch.core.index.lattice import compute_d
    from xinmatch.core.refine.structure_factor import multiplicity, structure_factor

    y = np.zeros_like(tth)
    hkls = []
    for h in range(-5, 6):
        for k in range(-5, 6):
            for ll in range(-5, 6):
                if h == 0 and k == 0 and ll == 0:
                    continue
                if (h, k, ll) > (-h, -k, -ll):
                    continue
                try:
                    d = compute_d((h, k, ll), cell)
                except ValueError:
                    continue
                pos = _two_theta(d)
                if pos < 20.0 or pos > 90.0:
                    continue
                f = structure_factor((h, k, ll), atoms, cell, wavelength=_WAVELENGTH)
                f_sq = float((f * f.conjugate()).real)
                lp = (1.0 + math.cos(math.radians(2.0 * pos)) ** 2) / (
                    math.sin(math.radians(pos / 2.0))
                    * math.cos(math.radians(pos / 2.0)) + 1e-12
                )
                m = multiplicity((h, k, ll), "cubic")
                intensity = 100.0 * f_sq * m * lp
                if intensity <= 0:
                    continue
                fwhm = pm.fwhm(pos)
                y += intensity * pm.shape_function(tth, pos, fwhm, 1.0)
                hkls.append((h, k, ll))

    pattern = Pattern(two_theta=tth, intensity=y, wavelength=_WAVELENGTH, step=0.02)
    entry = Entry(
        entry_id="Si-res",
        formula="Si",
        d_spacings=np.array([1.0]),
        intensities=np.array([1.0]),
        cell=cell,
    )
    entry.atoms = atoms  # type: ignore[attr-defined]
    refiner = RietveldRefinement(pattern, entry, pm, wavelength=_WAVELENGTH)
    result = refiner.fit(n_iter=20)
    report = residual_analysis(pattern, result.fitted_pattern, n_params=11)
    assert abs(report.rfactors.rwp - result.rwp) < 1e-6, (
        f"residual rwp={report.rfactors.rwp:.6f} vs rietveld rwp={result.rwp:.6f}"
    )


def test_residual_report_unfitted_peaks_are_peak_objects():
    """Unfitted peaks are :class:`Peak` instances."""
    tth = np.arange(20.0, 60.0 + 0.02, 0.02)
    baseline = np.full_like(tth, 1.0)
    extra = pseudo_voigt(tth, center=35.0, fwhm=0.2, amplitude=2000.0, eta=0.5)
    obs = Pattern(two_theta=tth, intensity=baseline + extra,
                  wavelength=_WAVELENGTH, step=0.02)
    calc = Pattern(two_theta=tth, intensity=baseline.copy(),
                   wavelength=_WAVELENGTH, step=0.02)
    report = residual_analysis(obs, calc, sensitivity="high")
    for p in report.unfitted_peaks:
        assert isinstance(p, Peak)
