"""Tests for peaks-to-profile conversion (T4.6)."""

import numpy as np

from xinmatch.core.model import Peak
from xinmatch.core.peak.peak_to_profile import peaks_to_profile


def test_area_conservation_single_gaussian():
    """Single Gaussian peak: integrated area error < 1%."""
    two_theta = np.linspace(-5, 5, 20001)
    area = 10.0
    peaks = [Peak(two_theta=0.0, intensity=area, fwhm=0.5)]
    profile = peaks_to_profile(two_theta, peaks, shape="gaussian")
    measured = np.trapz(profile, two_theta)
    assert abs(measured - area) / area < 0.01


def test_area_conservation_pseudo_voigt():
    two_theta = np.linspace(-50, 50, 200001)
    area = 7.5
    peaks = [Peak(two_theta=0.0, intensity=area, fwhm=0.4)]
    profile = peaks_to_profile(two_theta, peaks, shape="pseudo_voigt", eta=0.5)
    measured = np.trapz(profile, two_theta)
    assert abs(measured - area) / area < 0.01


def test_area_conservation_multiple_peaks():
    """Multiple peaks: total area conserved within 1%."""
    two_theta = np.linspace(0, 50, 50001)
    peaks = [
        Peak(two_theta=10.0, intensity=3.0, fwhm=0.3),
        Peak(two_theta=20.0, intensity=5.0, fwhm=0.4),
        Peak(two_theta=35.0, intensity=2.0, fwhm=0.5),
    ]
    total_area = sum(p.intensity for p in peaks)
    profile = peaks_to_profile(two_theta, peaks, shape="gaussian")
    measured = np.trapz(profile, two_theta)
    assert abs(measured - total_area) / total_area < 0.01


def test_output_shape():
    two_theta = np.linspace(0, 10, 100)
    peaks = [Peak(two_theta=5.0, intensity=1.0, fwhm=0.5)]
    profile = peaks_to_profile(two_theta, peaks)
    assert profile.shape == two_theta.shape


def test_peak_without_fwhm_raises():
    import pytest

    two_theta = np.linspace(0, 10, 100)
    peaks = [Peak(two_theta=5.0, intensity=1.0)]
    with pytest.raises(ValueError):
        peaks_to_profile(two_theta, peaks)
