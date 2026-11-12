"""Tests for PFSM (Profile-fitting search-match) FoM (T6.6)."""

from __future__ import annotations

import numpy as np
import pytest

from xinmatch.core.model import Entry, Pattern
from xinmatch.core.search.pfsm import (
    compute_reference_pattern,
    compute_rwp,
    fit_scale_shift,
    pfsm_rank,
    pfsm_score,
)

WL = 1.5406  # Cu Kα


def _make_entry(ds: list[float], ints: list[float]) -> Entry:
    return Entry(
        entry_id="ref",
        formula="Si O2",
        d_spacings=np.array(ds, dtype=np.float64),
        intensities=np.array(ints, dtype=np.float64),
    )


# A simple d–I table with well-separated lines.
_DS = [4.257, 3.343, 2.457, 2.282, 2.128, 1.980, 1.818]
_INTS = [100.0, 100.0, 12.0, 12.0, 4.0, 14.0, 4.0]


# --------------------------------------------------------------------------- #
# compute_reference_pattern
# --------------------------------------------------------------------------- #


def test_reference_pattern_shapes_and_length():
    entry = _make_entry(_DS, _INTS)
    tt, intensity = compute_reference_pattern(entry, WL, (5.0, 90.0), step=0.02)
    expected = int((90.0 - 5.0) / 0.02) + 1
    assert tt.size == expected
    assert intensity.size == expected
    assert np.all(intensity >= 0.0)


def test_reference_pattern_peaks_at_correct_positions():
    entry = _make_entry(_DS, _INTS)
    tt, intensity = compute_reference_pattern(entry, WL, (5.0, 90.0), step=0.01)
    # Every d should produce a peak at 2θ = 2 arcsin(λ/2d).
    for d in _DS:
        center = 2.0 * np.degrees(np.arcsin(WL / (2.0 * d)))
        if 5.0 <= center <= 90.0:
            idx = int(np.argmin(np.abs(tt - center)))
            # The peak must be a local maximum near the expected position.
            assert intensity[idx] > intensity[max(0, idx - 5)]
            assert intensity[idx] > intensity[min(tt.size - 1, idx + 5)]


def test_reference_pattern_empty_entry():
    entry = _make_entry([], [])
    tt, intensity = compute_reference_pattern(entry, WL)
    assert np.all(intensity == 0.0)


# --------------------------------------------------------------------------- #
# fit_scale_shift
# --------------------------------------------------------------------------- #


def test_fit_scale_shift_recovers_scale():
    two_theta = np.arange(5.0, 90.0, 0.02)
    ref = np.zeros_like(two_theta)
    for c in [20.0, 35.0, 50.0, 70.0]:
        ref += 100.0 * np.exp(-0.5 * ((two_theta - c) / 0.1) ** 2)
    scale_true = 0.37
    pattern = scale_true * ref
    scale, shift = fit_scale_shift(two_theta, pattern, ref)
    assert scale == pytest.approx(scale_true, rel=1e-3)
    assert shift == pytest.approx(0.0, abs=1e-2)


def test_fit_scale_shift_recovers_shift():
    two_theta = np.arange(5.0, 90.0, 0.02)
    ref = np.zeros_like(two_theta)
    for c in [20.0, 35.0, 50.0, 70.0]:
        ref += 100.0 * np.exp(-0.5 * ((two_theta - c) / 0.1) ** 2)
    shift_true = 0.15
    # Build the "observed" pattern by shifting the reference.
    pattern = np.interp(two_theta - shift_true, two_theta, ref, left=0.0, right=0.0)
    scale, shift = fit_scale_shift(two_theta, pattern, ref)
    assert scale == pytest.approx(1.0, abs=1e-2)
    assert shift == pytest.approx(shift_true, abs=1e-2)


def test_fit_scale_shift_scale_is_nonnegative():
    two_theta = np.arange(5.0, 90.0, 0.02)
    ref = np.exp(-0.5 * ((two_theta - 30.0) / 0.1) ** 2)
    pattern = -5.0 * ref  # try to force negative scale
    scale, shift = fit_scale_shift(two_theta, pattern, ref)
    assert scale >= 0.0


# --------------------------------------------------------------------------- #
# compute_rwp
# --------------------------------------------------------------------------- #


def test_rwp_perfect_fit_is_zero():
    y = np.array([100.0, 50.0, 25.0, 10.0])
    assert compute_rwp(y, y.copy()) == pytest.approx(0.0, abs=1e-12)


def test_rwp_bad_fit_is_large():
    y = np.array([100.0, 50.0, 25.0, 10.0])
    yc = np.zeros_like(y)
    rwp = compute_rwp(y, yc)
    assert rwp == pytest.approx(1.0)  # sqrt(sum(w y^2)/sum(w y^2)) = 1


def test_rwp_no_positive_points_returns_inf():
    y = np.array([0.0, -1.0, 0.0])
    assert compute_rwp(y, np.zeros_like(y)) == float("inf")


def test_rwp_subnormal_intensity_points_are_ignored():
    """Same guard as fpfm.compute_rwp: 1/y must not overflow (see fpfm tests)."""
    rng = np.random.default_rng(7)
    fitted = np.abs(rng.normal(100.0, 20.0, 1000)) + 1.0
    observed = fitted.copy()
    observed[::10] = np.nextafter(0.0, 1.0)
    rwp = compute_rwp(observed, fitted)
    assert np.isfinite(rwp)
    assert rwp < 1e-6


# --------------------------------------------------------------------------- #
# pfsm_score
# --------------------------------------------------------------------------- #


def _pattern_from_entry(entry: Entry, scale: float = 1.0, shift: float = 0.0) -> Pattern:
    """Build an experimental pattern by scaling/shifting the entry's reference."""
    tt, intensity = compute_reference_pattern(entry, WL, (5.0, 90.0), step=0.02)
    shifted = np.interp(tt - shift, tt, intensity, left=0.0, right=0.0)
    return Pattern(two_theta=tt, intensity=scale * shifted, wavelength=WL, step=0.02)


def test_pfsm_score_keys():
    entry = _make_entry(_DS, _INTS)
    pat = _pattern_from_entry(entry)
    score = pfsm_score(pat, entry)
    assert set(score.keys()) == {"rwp", "scale", "shift_deg", "fom"}


def test_pfsm_score_perfect_match_low_rwp():
    entry = _make_entry(_DS, _INTS)
    pat = _pattern_from_entry(entry, scale=2.0, shift=0.0)
    score = pfsm_score(pat, entry)
    assert score["rwp"] < 0.05
    assert score["scale"] == pytest.approx(2.0, rel=0.1)
    assert score["shift_deg"] == pytest.approx(0.0, abs=0.02)
    assert score["fom"] > 0.99


def test_pfsm_score_recovers_shift():
    entry = _make_entry(_DS, _INTS)
    pat = _pattern_from_entry(entry, scale=1.0, shift=0.1)
    score = pfsm_score(pat, entry)
    assert score["shift_deg"] == pytest.approx(0.1, abs=0.02)
    assert score["rwp"] < 0.1


def test_pfsm_score_wrong_entry_has_lower_fom():
    entry = _make_entry(_DS, _INTS)
    pat = _pattern_from_entry(entry)
    wrong = _make_entry(
        [6.0, 5.0, 4.5, 3.8, 3.1, 2.7, 2.3],
        [100.0, 80.0, 60.0, 40.0, 30.0, 20.0, 10.0],
    )
    good_score = pfsm_score(pat, entry)
    bad_score = pfsm_score(pat, wrong)
    assert good_score["fom"] > bad_score["fom"]


def test_pfsm_score_returns_fom_in_range():
    entry = _make_entry(_DS, _INTS)
    pat = _pattern_from_entry(entry)
    score = pfsm_score(pat, entry)
    assert 0.0 <= score["fom"] <= 1.0


# --------------------------------------------------------------------------- #
# pfsm_rank
# --------------------------------------------------------------------------- #


def test_pfsm_rank_sorted_and_truncated():
    target = _make_entry(_DS, _INTS)
    others = [
        _make_entry(
            [6.0 - i * 0.2, 5.0, 4.0, 3.0, 2.5, 2.0, 1.5],
            [100.0, 80.0, 60.0, 40.0, 30.0, 20.0, 10.0],
        )
        for i in range(10)
    ]
    entries = others + [target]
    pat = _pattern_from_entry(target)
    ranked = pfsm_rank(pat, entries, top_n=5)
    assert len(ranked) == 5
    foms = [s["fom"] for _, s in ranked]
    assert foms == sorted(foms, reverse=True)
    # The true phase should be at the top.
    assert ranked[0][0].entry_id == target.entry_id


def test_pfsm_rank_empty_entries():
    entry = _make_entry(_DS, _INTS)
    pat = _pattern_from_entry(entry)
    assert pfsm_rank(pat, []) == []
