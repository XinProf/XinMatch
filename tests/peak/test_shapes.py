"""Tests for peak shape functions (T4.3)."""

import numpy as np
import pytest

from xinmatch.core.peak.shapes import (
    fwhm_to_sigma,
    gaussian,
    lorentzian,
    pearson_vii,
    pseudo_voigt,
    sigma_to_fwhm,
)


def test_fwhm_sigma_roundtrip():
    fwhm = 0.25
    assert abs(sigma_to_fwhm(fwhm_to_sigma(fwhm)) - fwhm) < 1e-12


def test_gaussian_peak_at_center():
    x = np.linspace(-1, 1, 1001)
    y = gaussian(x, 0.0, 0.2, 1.0)
    assert abs(x[int(np.argmax(y))]) < 0.002


def test_gaussian_fwhm_matches():
    x = np.linspace(-2, 2, 20001)
    fwhm = 0.3
    y = gaussian(x, 0.0, fwhm, 1.0)
    half = y.max() / 2.0
    above = x[y >= half]
    measured = above[-1] - above[0]
    assert abs(measured - fwhm) < 1e-3


def test_gaussian_area_conservation():
    """Integral of normalised Gaussian equals amplitude."""
    x = np.linspace(-10, 10, 200001)
    amp = 5.0
    y = gaussian(x, 0.0, 0.5, amp)
    area = np.trapz(y, x)
    assert abs(area - amp) < 1e-4


def test_lorentzian_area_conservation():
    x = np.linspace(-1000, 1000, 400001)
    amp = 3.0
    y = lorentzian(x, 0.0, 1.0, amp)
    area = np.trapz(y, x)
    assert abs(area - amp) < 1e-3


def test_pseudo_voigt_limits():
    x = np.linspace(-5, 5, 10001)
    fwhm, amp = 0.5, 2.0
    g = gaussian(x, 0.0, fwhm, amp)
    lor = lorentzian(x, 0.0, fwhm, amp)
    pv0 = pseudo_voigt(x, 0.0, fwhm, amp, eta=0.0)
    pv1 = pseudo_voigt(x, 0.0, fwhm, amp, eta=1.0)
    np.testing.assert_allclose(pv0, g, atol=1e-12)
    np.testing.assert_allclose(pv1, lor, atol=1e-12)


def test_pseudo_voigt_fwhm_eta_consistency():
    """pseudo-Voigt with shared FWHM: measured FWHM equals input FWHM."""
    x = np.linspace(-2, 2, 40001)
    fwhm = 0.4
    for eta in [0.0, 0.3, 0.5, 0.7, 1.0]:
        y = pseudo_voigt(x, 0.0, fwhm, 1.0, eta=eta)
        half = y.max() / 2.0
        above = x[y >= half]
        measured = above[-1] - above[0]
        assert abs(measured - fwhm) < 1e-3, f"eta={eta}, measured={measured}"


def test_pseudo_voigt_area():
    x = np.linspace(-1000, 1000, 400001)
    amp = 1.0
    for eta in [0.0, 0.5, 1.0]:
        y = pseudo_voigt(x, 0.0, 0.5, amp, eta=eta)
        area = np.trapz(y, x)
        assert abs(area - amp) < 1e-3


def test_pearson_vii_lorentzian_limit():
    """Pearson VII with m=1 equals a Lorentzian."""
    x = np.linspace(-5, 5, 10001)
    pvii = pearson_vii(x, 0.0, 1.0, 1.0, shape=1.0)
    lor = lorentzian(x, 0.0, 1.0, 1.0)
    np.testing.assert_allclose(pvii, lor, atol=1e-6)


def test_pearson_vii_gaussian_limit():
    """Pearson VII with large m approaches a Gaussian."""
    x = np.linspace(-5, 5, 10001)
    pvii = pearson_vii(x, 0.0, 1.0, 1.0, shape=100.0)
    g = gaussian(x, 0.0, 1.0, 1.0)
    np.testing.assert_allclose(pvii, g, atol=1e-2)


def test_pearson_vii_invalid_shape():
    with pytest.raises(ValueError):
        pearson_vii(np.linspace(-1, 1, 10), 0.0, 1.0, 1.0, shape=0.1)


def test_analytical_gaussian_height():
    """Gaussian amplitude = area => check peak height formula analytically."""
    fwhm = 0.2
    amp = 1.0
    sigma = fwhm_to_sigma(fwhm)
    expected_height = amp / (sigma * np.sqrt(2 * np.pi))
    x = np.array([0.0])
    y = gaussian(x, 0.0, fwhm, amp)
    assert abs(y[0] - expected_height) < 1e-12
