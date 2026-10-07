"""Tests for Kα2 stripping (T3.4)."""

import numpy as np

from xinmatch.core.peak.shapes import gaussian
from xinmatch.core.preprocess.alpha2 import (
    angular_separation,
    strip_alpha2,
)


def _make_kalpha1_spectrum(two_theta):
    """A pure Kα1 spectrum with several Gaussian peaks."""
    spec = np.zeros_like(two_theta)
    centers = [20.0, 35.0, 50.0, 70.0]
    fwhms = [0.2, 0.22, 0.25, 0.3]
    heights = [1000.0, 800.0, 600.0, 400.0]
    for c, f, h in zip(centers, fwhms, heights, strict=False):
        # Convert height to area for the normalised gaussian.
        sigma = f / (2 * np.sqrt(2 * np.log(2)))
        area = h * sigma * np.sqrt(2 * np.pi)
        spec = spec + gaussian(two_theta, c, f, area)
    return spec


def test_angular_separation_positive():
    delta = angular_separation(30.0)
    assert delta > 0.0
    # For Cu, separation at 30° is ~0.06°.
    assert 0.01 < delta < 0.2


def test_strip_alpha2_recovers_kalpha1():
    """Pure Kα1 → add Kα2 → strip → corr(original, stripped) > 0.98."""
    two_theta = np.arange(10.0, 90.0, 0.02)
    kalpha1 = _make_kalpha1_spectrum(two_theta)

    # Build Kα2 contribution: for each point, the Kα2 comes from Kα1 at
    # (2θ - δ).  Approximate by shifting and scaling.
    delta = angular_separation(two_theta, 1.5406, 1.5444)
    # Shift the Kα1 spectrum to higher angles by the mean delta to create
    # the Kα2 companion.
    mean_delta = float(np.mean(delta))
    kalpha2 = np.interp(
        two_theta - mean_delta, two_theta, kalpha1, left=0.0, right=0.0
    )
    mixed = kalpha1 + 0.5 * kalpha2

    stripped = strip_alpha2(two_theta, mixed)

    corr = np.corrcoef(kalpha1, stripped)[0, 1]
    assert corr > 0.98, f"correlation {corr} <= 0.98"


def test_strip_alpha2_pure_input_reasonable():
    """Stripping a pure Kα1 spectrum should not destroy the peak structure."""
    two_theta = np.arange(10.0, 90.0, 0.02)
    kalpha1 = _make_kalpha1_spectrum(two_theta)
    stripped = strip_alpha2(two_theta, kalpha1)
    # The Rachinger method will over-subtract on pure Kα1 data, but the
    # overall peak structure should remain highly correlated.
    corr = np.corrcoef(kalpha1, stripped)[0, 1]
    assert corr > 0.90, f"pure-Kα1 correlation dropped to {corr}"


def test_strip_alpha2_shape():
    t = np.linspace(10.0, 90.0, 4000)
    y = np.sin(t) ** 2
    out = strip_alpha2(t, y)
    assert out.shape == y.shape
