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


# ── 2026-11-06: the gaussian path was rewritten for speed ────────────────
# ``curve_fit`` hit ``maxfev=5000`` on **every** peak: 156 ms per peak, 32 s for
# the 208 peaks of ``test_xrd/txt/3-1.txt`` — 93 % of the automatic-processing
# time, and the reason a "search" appeared to take 36 s.  It also *silently*
# returned the unrefined position when it gave up (26 of those 208 peaks).
# These tests pin the two properties that must not regress: it stays fast, and
# a degenerate input still yields a usable in-window position.


def test_gaussian_refine_is_not_iteration_bound():
    """Refining 200 peaks must take well under a second, not ~30 s.

    The threshold is deliberately loose (5 s → 25 ms/peak): the LM path measures
    ~1.5 ms/peak, while the old ``maxfev=5000`` path measured ~156 ms/peak.  A
    loose bound catches a reintroduced iteration loop without turning this into a
    flaky wall-clock test on a busy machine.
    """
    import time

    two_theta = np.arange(10.0, 60.0, 0.02)
    centers = np.linspace(12.0, 58.0, 200)
    intensity = np.zeros_like(two_theta)
    for c in centers:
        sigma = 0.08 / (2 * np.sqrt(2 * np.log(2)))
        intensity += gaussian(two_theta, c, 0.08, 500.0 * sigma * np.sqrt(2 * np.pi))

    t0 = time.perf_counter()
    refined = [
        refine_peak_position(two_theta, intensity, int(np.argmin(np.abs(two_theta - c))))
        for c in centers
    ]
    dt = time.perf_counter() - t0
    assert dt < 5.0, f"200 peaks took {dt:.2f}s — the iteration-bound fit is back"
    assert all(np.isfinite(refined))


def test_gaussian_refine_returns_in_window_position_for_no_peak():
    """A monotonic ramp has no apex; the result must stay inside the window.

    The LM solve is unbounded, so the guard (`x[0] <= center <= x[-1]`) plus the
    parabola fallback is what keeps a non-peak from returning a wild position.
    """
    two_theta = np.arange(20.0, 21.0, 0.02)
    intensity = 100.0 + 50.0 * (two_theta - 20.0)  # straight ramp, no maximum
    idx = len(two_theta) // 2
    refined = refine_peak_position(two_theta, intensity, idx, method="gaussian")
    assert np.isfinite(refined)
    lo = two_theta[max(0, idx - 5)]
    hi = two_theta[min(len(two_theta) - 1, idx + 5)]
    assert lo <= refined <= hi


def test_gaussian_refine_flat_input_is_finite():
    """All-equal intensities must not produce NaN/inf or an out-of-window value."""
    two_theta = np.arange(30.0, 31.0, 0.02)
    intensity = np.full_like(two_theta, 42.0)
    idx = len(two_theta) // 2
    refined = refine_peak_position(two_theta, intensity, idx, method="gaussian")
    assert np.isfinite(refined)
    assert two_theta[0] <= refined <= two_theta[-1]
