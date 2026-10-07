"""Tests for background determination and subtraction (T3.2 + T3.3)."""

import numpy as np
import pytest

from xinmatch.core.preprocess.background import (
    estimate_background,
    interpolate_background,
    subtract_background,
)


def _gaussian(t, c, fwhm, h):
    s = fwhm / (2 * np.sqrt(2 * np.log(2)))
    return h * np.exp(-0.5 * ((t - c) / s) ** 2)


def _synthetic_pattern():
    rng = np.random.default_rng(7)
    t = np.arange(5.0, 90.0, 0.02)
    # Three Gaussian peaks.
    peaks = (
        _gaussian(t, 20.0, 0.2, 900.0)
        + _gaussian(t, 40.0, 0.25, 1200.0)
        + _gaussian(t, 65.0, 0.3, 700.0)
    )
    # Polynomial background (cubic) — kept small so that at the peak
    # positions the background is < 10% of each peak height.
    bg_true = 20.0 + 0.1 * t - 0.002 * t ** 2 + 0.00002 * t ** 3
    noise = rng.normal(0.0, 8.0, t.shape)
    intensity = peaks + bg_true + noise
    return t, intensity, bg_true, peaks


def test_snip_does_not_cut_peaks():
    """Estimated background at peak positions < 10% of peak height."""
    t, intensity, _, peaks = _synthetic_pattern()
    bg = estimate_background(t, intensity, method="snip", window=30)

    for center, height in [(20.0, 900.0), (40.0, 1200.0), (65.0, 700.0)]:
        idx = int(np.argmin(np.abs(t - center)))
        assert bg[idx] < 0.10 * height, (
            f"background at {center}° ({bg[idx]}) >= 10% of peak height {height}"
        )


def test_polynomial_does_not_cut_peaks():
    t, intensity, _, _ = _synthetic_pattern()
    bg = estimate_background(t, intensity, method="polynomial", degree=4)
    for center, height in [(20.0, 900.0), (40.0, 1200.0), (65.0, 700.0)]:
        idx = int(np.argmin(np.abs(t - center)))
        assert bg[idx] < 0.10 * height


def test_subtract_background_non_negative():
    t, intensity, _, _ = _synthetic_pattern()
    bg = estimate_background(t, intensity, method="snip", window=30)
    net = subtract_background(intensity, bg)
    assert np.all(net >= 0.0)


def test_subtract_background_shape_mismatch():
    with pytest.raises(ValueError):
        subtract_background(np.zeros(10), np.zeros(5))


def test_two_points_background():
    t = np.linspace(0.0, 100.0, 50)
    intensity = 10.0 + 0.5 * t  # linear
    bg = estimate_background(t, intensity, method="two_points")
    # Should match the straight line through endpoints.
    expected = intensity[0] + (intensity[-1] - intensity[0]) * (t - t[0]) / (t[-1] - t[0])
    np.testing.assert_allclose(bg, expected, atol=1e-9)


def test_manual_background():
    t = np.linspace(0.0, 100.0, 101)  # includes exactly 50.0 at index 50
    control = np.array([[0.0, 10.0], [50.0, 30.0], [100.0, 20.0]])
    bg = estimate_background(t, None, method="manual", control_points=control)
    # Endpoints match control points.
    assert abs(bg[0] - 10.0) < 1e-6
    assert abs(bg[-1] - 20.0) < 1e-6
    # Control point at 50° is reproduced exactly by the spline.
    mid = int(np.argmin(np.abs(t - 50.0)))
    assert abs(bg[mid] - 30.0) < 1e-6


def test_manual_background_via_interpolate():
    t = np.linspace(0.0, 10.0, 50)
    cp = np.array([[0.0, 1.0], [5.0, 3.0], [10.0, 2.0]])
    bg = interpolate_background(t, cp, kind="linear")
    np.testing.assert_allclose(bg[[0, -1]], [1.0, 2.0], atol=1e-9)
