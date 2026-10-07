"""Tests for peak position refinement (T4.2)."""

import numpy as np

from xinmatch.core.peak.peak_refine import refine_peak_position
from xinmatch.core.peak.shapes import gaussian


def _peak_dataset(center, fwhm=0.2, height=1000.0, step=0.02):
    two_theta = np.arange(center - 1.0, center + 1.0 + step, step)
    sigma = fwhm / (2 * np.sqrt(2 * np.log(2)))
    area = height * sigma * np.sqrt(2 * np.pi)
    intensity = gaussian(two_theta, center, fwhm, area)
    return two_theta, intensity


def test_gaussian_refine_accuracy():
    """Peak position accuracy < 0.002° for a clean Gaussian."""
    center = 30.123
    two_theta, intensity = _peak_dataset(center)
    idx = int(np.argmax(intensity))
    refined = refine_peak_position(two_theta, intensity, idx, method="gaussian")
    assert abs(refined - center) < 0.002, f"refined={refined}, true={center}"


def test_parabola_refine_accuracy():
    center = 45.678
    two_theta, intensity = _peak_dataset(center)
    idx = int(np.argmax(intensity))
    refined = refine_peak_position(two_theta, intensity, idx, method="parabola")
    assert abs(refined - center) < 0.002


def test_centroid_refine_accuracy():
    center = 22.345
    two_theta, intensity = _peak_dataset(center)
    idx = int(np.argmax(intensity))
    refined = refine_peak_position(two_theta, intensity, idx, method="centroid")
    # Centroid is less accurate but should be within ~half a step.
    assert abs(refined - center) < 0.01


def test_refine_noisy_peak():
    rng = np.random.default_rng(5)
    center = 50.0
    two_theta, intensity = _peak_dataset(center, height=500.0)
    intensity = intensity + rng.normal(0.0, 2.0, intensity.shape)
    idx = int(np.argmax(intensity))
    refined = refine_peak_position(two_theta, intensity, idx, method="gaussian")
    assert abs(refined - center) < 0.005


def test_refine_invalid_idx():
    import pytest

    t = np.array([1.0, 2.0, 3.0])
    y = np.array([1.0, 2.0, 1.0])
    with pytest.raises(ValueError):
        refine_peak_position(t, y, 99, method="gaussian")
