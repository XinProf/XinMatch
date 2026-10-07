"""Tests for peak searching (T4.1)."""

import numpy as np

from xinmatch.core.peak.peak_search import find_peaks
from xinmatch.core.peak.shapes import gaussian


def _synthetic_spectrum():
    """8 Gaussian peaks, FWHM 0.15-0.3°, intensity 50-1000 counts."""
    two_theta = np.arange(10.0, 90.0, 0.02)
    centers = [15.0, 22.0, 30.0, 38.0, 47.0, 56.0, 68.0, 80.0]
    fwhms = [0.15, 0.18, 0.2, 0.22, 0.25, 0.27, 0.28, 0.3]
    heights = [1000.0, 800.0, 600.0, 500.0, 400.0, 300.0, 200.0, 50.0]
    spec = np.zeros_like(two_theta)
    for c, f, h in zip(centers, fwhms, heights, strict=False):
        sigma = f / (2 * np.sqrt(2 * np.log(2)))
        area = h * sigma * np.sqrt(2 * np.pi)
        spec = spec + gaussian(two_theta, c, f, area)
    rng = np.random.default_rng(123)
    spec = spec + rng.normal(0.0, 5.0, two_theta.shape)
    return two_theta, spec, centers


def test_peak_search_recall():
    """8-peak synthetic spectrum: recall > 95%, false peaks < 5%."""
    two_theta, intensity, centers = _synthetic_spectrum()
    peaks = find_peaks(two_theta, intensity, sensitivity="medium")

    found = np.array([p.two_theta for p in peaks])
    true_positives = 0
    for c in centers:
        if found.size == 0:
            continue
        if np.min(np.abs(found - c)) < 0.1:
            true_positives += 1

    recall = true_positives / len(centers)
    assert recall > 0.95, f"recall {recall} <= 0.95 (found {len(found)} peaks)"

    # False peaks: found peaks not within 0.1° of any true center.
    false_positives = 0
    for f in found:
        if np.min(np.abs(np.array(centers) - f)) >= 0.1:
            false_positives += 1
    fpr = false_positives / max(len(found), 1)
    assert fpr < 0.05, f"false-positive rate {fpr} >= 0.05"


def test_peak_search_sensitivity_high_finds_more():
    two_theta, intensity, centers = _synthetic_spectrum()
    low = find_peaks(two_theta, intensity, sensitivity="low")
    high = find_peaks(two_theta, intensity, sensitivity="high")
    assert len(high) >= len(low)


def test_peak_search_returns_peaks():
    two_theta = np.arange(0.0, 10.0, 0.01)
    y = gaussian(two_theta, 5.0, 0.2, 100.0)
    peaks = find_peaks(two_theta, y, sensitivity="medium")
    assert len(peaks) >= 1
    assert abs(peaks[0].two_theta - 5.0) < 0.05
    assert peaks[0].intensity > 0.0


def test_peak_search_empty():
    peaks = find_peaks(np.array([]), np.array([]))
    assert peaks == []
