"""Tests for peak correlation (T6.1)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from xinmatch.core.model import Peak
from xinmatch.core.search.correlate import (
    correlate,
    correlate_peaks,
    d_to_two_theta,
)

# Cu Kα wavelength used throughout the synthetic tests.
WL = 1.5406


def _d_from_two_theta(two_theta: float, wavelength: float = WL) -> float:
    """Inverse of :func:`d_to_two_theta` for synthesising reference peaks."""
    return wavelength / (2.0 * math.sin(math.radians(two_theta / 2.0)))


# --------------------------------------------------------------------- #
# d_to_two_theta
# --------------------------------------------------------------------- #


def test_d_to_two_theta_lab6_first_peak():
    """LaB6 (100): d = 4.156 Å, λ = 1.5406 → 2θ ≈ 21.36°."""
    expected = math.degrees(2.0 * math.asin(1.5406 / (2.0 * 4.156)))
    assert abs(d_to_two_theta(4.156, 1.5406) - expected) < 1e-9


def test_d_to_two_theta_known_value():
    """d = λ/2 → sin θ = 1 → 2θ = 180° (the boundary, not unreachable)."""
    assert abs(d_to_two_theta(WL / 2.0, WL) - 180.0) < 1e-9


def test_d_to_two_theta_invalid_d_raises():
    with pytest.raises(ValueError, match="d-spacing must be positive"):
        d_to_two_theta(0.0, WL)
    with pytest.raises(ValueError, match="d-spacing must be positive"):
        d_to_two_theta(-1.0, WL)


def test_d_to_two_theta_invalid_wavelength_raises():
    with pytest.raises(ValueError, match="wavelength must be positive"):
        d_to_two_theta(3.0, 0.0)


def test_d_to_two_theta_unreachable_returns_inf():
    """d < λ/2 has no real solution — must return +inf, not raise."""
    assert math.isinf(d_to_two_theta(0.5, WL))


# --------------------------------------------------------------------- #
# correlate (with (2θ, intensity) reference peaks)
# --------------------------------------------------------------------- #


def test_correlate_perfect_match():
    """Synthetic data with exact 2θ correspondence → 100% correct pairing."""
    exp_two_theta = [10.0, 20.0, 30.0, 40.0]
    exp_intensities = [100.0, 50.0, 25.0, 10.0]
    exp_peaks = [
        Peak(two_theta=tt, intensity=intensity)
        for tt, intensity in zip(exp_two_theta, exp_intensities, strict=True)
    ]
    ref_peaks_2theta_intensity = list(
        zip(exp_two_theta, exp_intensities, strict=True)
    )

    pairs = correlate(exp_peaks, ref_peaks_2theta_intensity, window_deg=0.3)
    assert pairs == [(0, 0), (1, 1), (2, 2), (3, 3)]


def test_correlate_one_to_one_constraint():
    """Even with two ref peaks in the window, only one exp gets paired."""
    exp_peaks = [Peak(two_theta=20.0, intensity=100.0)]
    # Two ref peaks at 20.0 and 20.1, both within ±0.15° of exp.
    # Greedy rule: pick the strongest (intensity 200 > 100).
    ref_peaks_2theta_intensity = [(20.0, 200.0), (20.1, 100.0)]
    pairs = correlate(exp_peaks, ref_peaks_2theta_intensity, window_deg=0.3)
    assert pairs == [(0, 0)]


def test_correlate_strongest_in_window_wins():
    """When several ref peaks fall in the window, the strongest is chosen."""
    exp_peaks = [Peak(two_theta=25.0, intensity=100.0)]
    # 3 candidates within ±0.15° of 25.0; the middle one is strongest.
    ref_peaks_2theta_intensity = [
        (24.9, 50.0),
        (25.05, 800.0),  # strongest → should win
        (25.1, 200.0),
    ]
    pairs = correlate(exp_peaks, ref_peaks_2theta_intensity, window_deg=0.3)
    assert pairs == [(0, 1)]


def test_correlate_no_match_when_ref_outside_window():
    exp_peaks = [Peak(two_theta=10.0, intensity=100.0)]
    ref_peaks_2theta_intensity = [(50.0, 100.0)]  # 40° away — way outside 0.3° window
    pairs = correlate(exp_peaks, ref_peaks_2theta_intensity, window_deg=0.3)
    assert pairs == []


def test_correlate_empty_inputs():
    assert correlate([], [], window_deg=0.3) == []
    assert correlate([], [(20.0, 100.0)], window_deg=0.3) == []
    assert correlate([Peak(20.0, 100.0)], [], window_deg=0.3) == []


def test_correlate_window_lower_boundary_inclusive():
    """Ref exactly at exp − window/2 is accepted."""
    exp_peaks = [Peak(two_theta=20.0, intensity=100.0)]
    ref_peaks_2theta_intensity = [(19.85, 50.0)]  # Δ = 0.15 = window/2
    pairs = correlate(exp_peaks, ref_peaks_2theta_intensity, window_deg=0.3)
    assert pairs == [(0, 0)]


def test_correlate_window_upper_boundary_inclusive():
    """Ref exactly at exp + window/2 is accepted."""
    exp_peaks = [Peak(two_theta=20.0, intensity=100.0)]
    ref_peaks_2theta_intensity = [(20.15, 50.0)]  # Δ = 0.15 = window/2
    pairs = correlate(exp_peaks, ref_peaks_2theta_intensity, window_deg=0.3)
    assert pairs == [(0, 0)]


def test_correlate_just_outside_window():
    """Ref at exp + window/2 + ε is rejected."""
    exp_peaks = [Peak(two_theta=20.0, intensity=100.0)]
    ref_peaks_2theta_intensity = [(20.16, 50.0)]  # Δ = 0.16 > window/2 = 0.15
    pairs = correlate(exp_peaks, ref_peaks_2theta_intensity, window_deg=0.3)
    assert pairs == []


def test_correlate_noisy_perturbation():
    """2θ perturbed by σ = 0.05° — all peaks still within window."""
    rng = np.random.default_rng(42)
    true_2th = np.array([12.0, 22.0, 32.0, 42.0, 52.0])
    exp_peaks = [
        Peak(two_theta=float(t + rng.normal(0.0, 0.05)), intensity=100.0)
        for t in true_2th
    ]
    ref_peaks_2theta_intensity = [(float(t), 100.0) for t in true_2th]

    pairs = correlate(exp_peaks, ref_peaks_2theta_intensity, window_deg=0.3)
    # Acceptance criterion: at least 4 of 5 peaks still matched, and
    # every matched pair is correct (since both lists are sorted and
    # unique).
    assert len(pairs) >= 4
    for ei, ri in pairs:
        assert ei == ri


def test_correlate_more_exp_than_ref_peaks():
    """Extra exp peaks get no pair; the rest match correctly."""
    exp_peaks = [
        Peak(two_theta=10.0, intensity=100.0),
        Peak(two_theta=20.0, intensity=50.0),
        Peak(two_theta=30.0, intensity=25.0),
    ]
    ref_peaks_2theta_intensity = [(10.0, 100.0), (30.0, 25.0)]  # no peak for 20.0
    pairs = correlate(exp_peaks, ref_peaks_2theta_intensity, window_deg=0.3)
    # Pair (1, ?) should be missing — peak at 20.0 has no ref counterpart.
    assert (0, 0) in pairs
    assert (2, 1) in pairs
    assert all(ei != 1 for ei, _ in pairs)


def test_correlate_more_ref_than_exp_peaks():
    """Extra ref peaks get no pair; exp peaks match strongest ref."""
    exp_peaks = [Peak(two_theta=20.0, intensity=100.0)]
    # Two ref peaks within window of 20.0; the strongest (200) should win.
    # A third ref at 60.0 — outside window — should never pair.
    ref_peaks_2theta_intensity = [
        (19.9, 100.0),
        (20.1, 200.0),  # strongest in window → wins
        (60.0, 999.0),
    ]
    pairs = correlate(exp_peaks, ref_peaks_2theta_intensity, window_deg=0.3)
    assert pairs == [(0, 1)]


def test_correlate_preserves_input_list():
    """The function must not mutate its input."""
    exp_peaks = [Peak(two_theta=20.0, intensity=100.0)]
    ref_peaks_2theta_intensity = [(20.0, 50.0)]
    _ = correlate(exp_peaks, ref_peaks_2theta_intensity, window_deg=0.3)
    assert exp_peaks[0].two_theta == 20.0
    assert ref_peaks_2theta_intensity == [(20.0, 50.0)]


def test_correlate_unknown_method_raises():
    exp_peaks = [Peak(two_theta=20.0, intensity=100.0)]
    ref_peaks_2theta_intensity = [(20.0, 50.0)]
    with pytest.raises(ValueError, match="unknown method"):
        correlate(
            exp_peaks, ref_peaks_2theta_intensity, window_deg=0.3, method="bogus"
        )


# --------------------------------------------------------------------- #
# correlate_peaks (with (d, intensity) reference peaks)
# --------------------------------------------------------------------- #


def test_correlate_peaks_perfect_match():
    """d→2θ conversion via Bragg's law + correlation = perfect pairing."""
    exp_two_theta = [15.0, 25.0, 35.0]
    exp_intensities = [100.0, 80.0, 40.0]
    exp_peaks = [
        Peak(two_theta=tt, intensity=intensity)
        for tt, intensity in zip(exp_two_theta, exp_intensities, strict=True)
    ]
    ref_ds = [_d_from_two_theta(tt) for tt in exp_two_theta]
    ref_peaks_d_intensity = list(zip(ref_ds, exp_intensities, strict=True))

    pairs = correlate_peaks(
        exp_peaks, ref_peaks_d_intensity, wavelength=WL, window_deg=0.3
    )
    assert pairs == [(0, 0), (1, 1), (2, 2)]


def test_correlate_peaks_unreachable_d_skipped():
    """A reference peak with d < λ/2 must never match."""
    exp_peaks = [Peak(two_theta=20.0, intensity=100.0)]
    # First ref peak is unreachable (d = 0.5 < λ/2 = 0.77).
    # Second ref peak is real and matches.
    ref_peaks_d_intensity = [
        (0.5, 9999.0),  # unreachable → +inf 2θ → never matches
        (_d_from_two_theta(20.0), 100.0),
    ]
    pairs = correlate_peaks(
        exp_peaks, ref_peaks_d_intensity, wavelength=WL, window_deg=0.3
    )
    assert pairs == [(0, 1)]


def test_correlate_peaks_empty():
    assert correlate_peaks([], [], wavelength=WL, window_deg=0.3) == []


# --------------------------------------------------------------------- #
# Hungarian method
# --------------------------------------------------------------------- #


def test_correlate_hungarian_perfect_match():
    """Hungarian method produces the same pairing as greedy when unambiguous."""
    exp_peaks = [
        Peak(two_theta=10.0, intensity=100.0),
        Peak(two_theta=20.0, intensity=50.0),
    ]
    ref_peaks_2theta_intensity = [(10.0, 100.0), (20.0, 50.0)]
    pairs = correlate(
        exp_peaks, ref_peaks_2theta_intensity, window_deg=0.3, method="hungarian"
    )
    assert sorted(pairs) == [(0, 0), (1, 1)]


def test_correlate_hungarian_handles_overlapping_window():
    """Two exp peaks both close to two ref peaks; Hungarian picks globally optimal."""
    exp_peaks = [
        Peak(two_theta=20.0, intensity=100.0),
        Peak(two_theta=20.1, intensity=100.0),
    ]
    # Ref peaks at 20.05 and 20.15 — each exp peak is within 0.15° of
    # *both* ref peaks.  Greedy would give exp[0]→ref[0] (stronger),
    # exp[1]→ref[1].  Hungarian should also give the same one-to-one.
    ref_peaks_2theta_intensity = [(20.05, 200.0), (20.15, 100.0)]
    pairs_greedy = correlate(
        exp_peaks, ref_peaks_2theta_intensity, window_deg=0.3, method="greedy"
    )
    pairs_hung = correlate(
        exp_peaks, ref_peaks_2theta_intensity, window_deg=0.3, method="hungarian"
    )
    # Both must produce exactly 2 one-to-one pairs.
    assert len(pairs_greedy) == 2
    assert len(pairs_hung) == 2
    # Both must be valid one-to-one matchings.
    assert {p[0] for p in pairs_greedy} == {0, 1}
    assert {p[1] for p in pairs_greedy} == {0, 1}
    assert {p[0] for p in pairs_hung} == {0, 1}
    assert {p[1] for p in pairs_hung} == {0, 1}


def test_correlate_hungarian_empty():
    assert correlate([], [], window_deg=0.3, method="hungarian") == []
    assert correlate(
        [], [(20.0, 100.0)], window_deg=0.3, method="hungarian"
    ) == []
    assert correlate(
        [Peak(20.0, 100.0)], [], window_deg=0.3, method="hungarian"
    ) == []


def test_correlate_hungarian_no_match_outside_window():
    exp_peaks = [Peak(two_theta=10.0, intensity=100.0)]
    ref_peaks_2theta_intensity = [(60.0, 100.0)]  # 50° away
    pairs = correlate(
        exp_peaks, ref_peaks_2theta_intensity, window_deg=0.3, method="hungarian"
    )
    assert pairs == []
