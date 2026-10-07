"""Tests for the automatic raw-data processing pipeline (T3.8)."""

import numpy as np

from xinmatch.core.model import Pattern
from xinmatch.core.peak.shapes import gaussian
from xinmatch.core.preprocess.auto_pipeline import auto_process


def _lab6_like_pattern():
    """Synthetic LaB6-like pattern with several known peaks."""
    two_theta = np.arange(15.0, 100.0, 0.02)
    centers = [21.4, 30.4, 37.5, 43.6, 49.0, 54.0, 58.6, 63.0, 71.0, 79.0]
    fwhms = [0.18] * len(centers)
    heights = [1000, 800, 600, 500, 400, 350, 300, 250, 200, 150]
    spec = np.zeros_like(two_theta)
    for c, f, h in zip(centers, fwhms, heights, strict=False):
        sigma = f / (2 * np.sqrt(2 * np.log(2)))
        area = h * sigma * np.sqrt(2 * np.pi)
        spec = spec + gaussian(two_theta, c, f, area)
    # Flat background.
    spec = spec + 50.0
    return two_theta, spec, centers


def test_pipeline_recovers_peak_positions():
    """LaB6-like pattern through full pipeline: peak positions within 0.01°."""
    two_theta, intensity, centers = _lab6_like_pattern()
    pattern = Pattern(two_theta=two_theta, intensity=intensity, wavelength=1.5406)

    # The synthetic spectrum is pure Kα1 (no Kα2), so we disable Kα2
    # stripping to avoid Rachinger over-subtraction distorting the peaks.
    config = {"strip_alpha2": False}
    processed, peaks = auto_process(pattern, config=config)

    found = np.array([p.two_theta for p in peaks])
    # Match each true center to nearest found peak.
    matched = []
    for c in centers:
        if found.size == 0:
            continue
        d = np.abs(found - c)
        idx = int(np.argmin(d))
        if d[idx] < 0.05:
            matched.append(d[idx])

    # At least 80% of true peaks found within 0.01°.
    assert len(matched) >= 0.8 * len(centers)
    assert max(matched) < 0.01, f"worst peak match {max(matched)} >= 0.01°"


def test_pipeline_can_disable_steps():
    two_theta, intensity, _ = _lab6_like_pattern()
    pattern = Pattern(two_theta=two_theta, intensity=intensity)
    cfg = {"smooth": False, "background": False, "strip_alpha2": False}
    processed, peaks = auto_process(pattern, config=cfg)
    # Peaks still found on the raw (background-removed? no, background left)
    # data.  Just check it runs and returns a pattern + peaks.
    assert processed.intensity.shape == intensity.shape
    assert isinstance(peaks, list)


def test_pipeline_output_is_pattern():
    two_theta, intensity, _ = _lab6_like_pattern()
    pattern = Pattern(two_theta=two_theta, intensity=intensity)
    processed, peaks = auto_process(pattern)
    assert isinstance(processed, Pattern)
    assert processed.two_theta.shape == two_theta.shape
