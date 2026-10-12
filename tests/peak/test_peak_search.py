"""Tests for peak searching (T4.1)."""

import numpy as np

from xinmatch.core.peak.peak_search import find_peaks
from xinmatch.core.peak.shapes import fwhm_to_sigma, gaussian, pseudo_voigt


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


def test_peak_search_noise_floor_rejects_smooth_ripple():
    """Near-noiseless data: the MAD noise estimate collapses and the
    signal-relative floor must reject numerical residue (v1.4.0 / T14).

    Regression: on background-subtracted synthetic data the flat regions
    are exactly zero, so the MAD-of-differences noise estimate collapses
    to ~1e-2 and *every* residue wiggle (SNIP overshoot, smoothing
    ringing) passed the SNR / prominence tests — a 5-peak pattern came
    back with 43 "peaks" and the search-match FoM ranking collapsed.
    """
    two_theta = np.arange(10.0, 90.0, 0.02)
    spec = np.zeros_like(two_theta)
    for c, h in [(20.0, 5000.0), (35.0, 3000.0), (50.0, 2000.0),
                 (65.0, 1000.0), (80.0, 500.0)]:
        spec = spec + gaussian(two_theta, c, 0.18, h)
    # Slow ripple (amplitude 5) standing in for background-estimation
    # residue: local maxima well above the collapsed MAD threshold
    # (~0.1) but far below the signal-relative floor (1% of std ≈ 13).
    idx = np.arange(two_theta.size)
    spec = spec + 5.0 * np.sin(idx * 0.01) ** 2

    peaks = find_peaks(two_theta, spec, sensitivity="medium")
    found = [round(p.two_theta, 1) for p in peaks]
    assert found == [20.0, 35.0, 50.0, 65.0, 80.0], (
        f"expected exactly the 5 real peaks, got {found}"
    )


def test_peak_search_rejects_tail_carpet_bumps():
    """Broad-tailed peaks: the inter-peak tail carpet must not produce peaks.

    Regression (v1.4.0 / task #14): the synthetic-pattern generator
    truncates pseudo-Voigt peaks at 8×FWHM, leaving a broad "tail carpet"
    of ~0.4–1% of the peak height between reflections.  With a windowed
    -minimum prominence those carpet bumps (heights 50–150 counts) passed
    the 3×MAD threshold (~30 counts) and the single-phase BaTiO3 pattern
    came back with 182 "peaks" instead of ~24 — dense junk reference
    cards then outranked the truth phase on P_npeaks.  Key-col prominence
    collapses the carpet bumps to the noise level while keeping the real
    reflections, including a weak broad one.
    """
    two_theta = np.arange(10.0, 90.0, 0.02)
    y = np.zeros_like(two_theta)

    def _truncated_pv(center, fwhm, height, eta):
        """Pseudo-Voigt truncated at 8×FWHM with a cosine taper (the
        generator's construction — the tails are the point of the test)."""
        area = height * fwhm_to_sigma(fwhm) * np.sqrt(2.0 * np.pi)
        half = 8.0 * fwhm
        near = np.abs(two_theta - center) <= half
        xrel = np.abs(two_theta[near] - center) / fwhm
        taper_start = half / fwhm - 1.5
        taper = np.where(
            xrel <= taper_start,
            1.0,
            0.5 * (1.0 + np.cos(np.pi * (xrel - taper_start) / 1.5)),
        )
        out = np.zeros_like(two_theta)
        out[near] = pseudo_voigt(two_theta[near], center, fwhm, area, eta) * taper
        return out

    # Strong reflections with Lorentzian-heavy tails (eta = 0.6).
    for c, h in [(22.2, 48000.0), (31.7, 20000.0), (45.4, 8000.0),
                 (56.5, 3000.0)]:
        y += _truncated_pv(c, 0.2, h, eta=0.6)
    # A weak broad reflection sitting on the carpet (FWHM 0.3°).
    y += _truncated_pv(75.0, 0.3, 250.0, eta=0.5)
    rng = np.random.default_rng(7)
    y += rng.normal(0.0, 15.0, two_theta.shape)

    peaks = find_peaks(two_theta, y, sensitivity="medium")
    found = [round(p.two_theta, 1) for p in peaks]
    # Every real reflection present (including the weak broad one).
    for c in (22.2, 31.7, 45.4, 56.5, 75.0):
        assert any(abs(f - c) < 0.1 for f in found), (
            f"real peak at {c}° missed; found {found}"
        )
    # No carpet explosion: at most one extra bump per inter-peak gap.
    assert len(found) <= 8, f"tail-carpet bumps leaked into the peak list: {found}"
