"""Tests for raw-data smoothing (T3.1)."""

import numpy as np
import pytest

from xinmatch.core.preprocess.smoothing import smooth


def _gaussian_peak(two_theta, center, fwhm, height):
    sigma = fwhm / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    return height * np.exp(-0.5 * ((two_theta - center) / sigma) ** 2)


def test_savgol_preserves_peak_position():
    """Synthetic Gaussian peak (2θ=25°, FWHM=0.2°) + 5% noise: peak shift <0.005°."""
    rng = np.random.default_rng(42)
    two_theta = np.arange(10.0, 60.0, 0.02)
    pure = _gaussian_peak(two_theta, 25.0, 0.2, 1000.0)
    noise = rng.normal(0.0, 0.05 * 1000.0, two_theta.shape)
    noisy = pure + noise

    smoothed = smooth(noisy, method="savgol", window=11, polyorder=3)

    # Peak position = argmax of smoothed.
    idx = int(np.argmax(smoothed))
    pos = two_theta[idx]
    assert abs(pos - 25.0) < 0.005, f"peak shifted to {pos}, diff={abs(pos - 25.0)}"


def test_moving_average_preserves_peak_position():
    rng = np.random.default_rng(0)
    two_theta = np.arange(10.0, 60.0, 0.02)
    pure = _gaussian_peak(two_theta, 30.0, 0.2, 800.0)
    noisy = pure + rng.normal(0.0, 0.05 * 800.0, two_theta.shape)

    smoothed = smooth(noisy, method="moving_average", window=11)
    idx = int(np.argmax(smoothed))
    assert abs(two_theta[idx] - 30.0) < 0.01


def test_smooth_reduces_noise():
    rng = np.random.default_rng(1)
    two_theta = np.arange(10.0, 60.0, 0.02)
    pure = _gaussian_peak(two_theta, 25.0, 0.3, 1000.0)
    noisy = pure + rng.normal(0.0, 50.0, two_theta.shape)

    smoothed = smooth(noisy, method="savgol", window=15, polyorder=3)
    # Smoothed should be closer to the pure signal than the noisy input.
    assert np.mean((smoothed - pure) ** 2) < np.mean((noisy - pure) ** 2)


def test_smooth_output_same_shape():
    y = np.linspace(0, 100, 200)
    out = smooth(y, method="savgol", window=11, polyorder=3)
    assert out.shape == y.shape
    out = smooth(y, method="moving_average", window=7)
    assert out.shape == y.shape


def test_smooth_invalid_method():
    with pytest.raises(ValueError):
        smooth(np.zeros(50), method="bogus")


def test_smooth_empty():
    out = smooth(np.array([]), method="savgol")
    assert out.size == 0
