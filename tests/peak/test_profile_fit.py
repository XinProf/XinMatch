"""Tests for multi-peak profile fitting (T4.4)."""

import numpy as np

from xinmatch.core.model import Peak
from xinmatch.core.peak.profile_fit import fit_profile
from xinmatch.core.peak.shapes import gaussian


def _five_peak_spectrum(seed=0):
    """5 overlapping Gaussian peaks with known parameters."""
    rng = np.random.default_rng(seed)
    two_theta = np.arange(20.0, 60.0, 0.02)
    centers = [25.0, 30.0, 35.0, 42.0, 50.0]
    fwhms = [0.2, 0.22, 0.25, 0.2, 0.28]
    heights = [1000.0, 800.0, 1200.0, 600.0, 900.0]
    spec = np.zeros_like(two_theta)
    areas = []
    for c, f, h in zip(centers, fwhms, heights, strict=False):
        sigma = f / (2 * np.sqrt(2 * np.log(2)))
        area = h * sigma * np.sqrt(2 * np.pi)
        areas.append(area)
        spec = spec + gaussian(two_theta, c, f, area)
    spec = spec + rng.normal(0.0, 2.0, two_theta.shape)
    return two_theta, spec, centers, fwhms, areas


def test_five_peak_gaussian_rwp():
    """5-peak Gaussian fit: Rwp < 2%."""
    two_theta, intensity, centers, fwhms, areas = _five_peak_spectrum()
    initial_peaks = [
        Peak(two_theta=c, intensity=h, fwhm=f)
        for c, f, h in zip(centers, fwhms, [800, 700, 1000, 500, 800], strict=False)
    ]
    result = fit_profile(two_theta, intensity, initial_peaks, shape="gaussian")

    assert result.rwp < 0.02, f"Rwp={result.rwp} >= 0.02"
    assert len(result.fitted_peaks) == 5
    assert result.fitted_intensity.shape == intensity.shape


def test_five_peak_pseudo_voigt_rwp():
    """5-peak pseudo-Voigt fit: Rwp < 2%."""
    two_theta, intensity, centers, fwhms, _ = _five_peak_spectrum(seed=1)
    initial_peaks = [
        Peak(two_theta=c, intensity=h, fwhm=f)
        for c, f, h in zip(centers, fwhms, [800, 700, 1000, 500, 800], strict=False)
    ]
    result = fit_profile(two_theta, intensity, initial_peaks, shape="pseudo_voigt")
    assert result.rwp < 0.02, f"Rwp={result.rwp} >= 0.02"


def test_fit_recovers_positions():
    two_theta, intensity, centers, fwhms, _ = _five_peak_spectrum()
    initial_peaks = [
        Peak(two_theta=c, intensity=800, fwhm=0.2) for c in centers
    ]
    result = fit_profile(two_theta, intensity, initial_peaks, shape="gaussian")
    for fp, c in zip(result.fitted_peaks, centers, strict=False):
        assert abs(fp.two_theta - c) < 0.01, f"pos {fp.two_theta} vs {c}"


def test_fit_empty_peaks():
    two_theta = np.linspace(0, 10, 100)
    intensity = np.zeros(100)
    result = fit_profile(two_theta, intensity, [])
    assert result.fitted_peaks == []
    assert result.rwp == 1.0
