"""Tests for Hanawalt/Fink coarse pre-filter (T6.0)."""

from __future__ import annotations

import time

import numpy as np
import pytest

from xinmatch.core.model import Entry, Peak
from xinmatch.core.search.hanawalt_fink import (
    build_hanawalt_lookup,
    fink_index,
    hanawalt_index,
    make_hanawalt_key,
    pre_filter,
    pre_filter_fink,
    pre_filter_hanawalt,
)

WL = 1.5406  # Cu Kα


def _d_from_two_theta(two_theta: float, wavelength: float = WL) -> float:
    import math

    return wavelength / (2.0 * math.sin(math.radians(two_theta / 2.0)))


def _make_entry(
    entry_id: str,
    ds: list[float],
    intensities: list[float],
    formula: str = "Si O2",
) -> Entry:
    return Entry(
        entry_id=entry_id,
        formula=formula,
        d_spacings=np.array(ds, dtype=np.float64),
        intensities=np.array(intensities, dtype=np.float64),
    )


# A realistic quartz-like d–I table (d in Å, I/I1 rel).
_QUARTZ_D = [4.257, 3.343, 2.457, 2.282, 2.237, 2.128, 1.980, 1.818, 1.672, 1.600]
_QUARTZ_I = [100.0, 100.0, 12.0, 12.0, 7.0, 4.0, 14.0, 4.0, 2.0, 1.0]


# --------------------------------------------------------------------------- #
# Index extractors
# --------------------------------------------------------------------------- #


def test_hanawalt_index_returns_top3_by_intensity():
    entry = _make_entry("q", _QUARTZ_D, _QUARTZ_I)
    top3 = hanawalt_index(entry)
    # Top 3 intensities are 100, 100, 14 → d = 4.257, 3.343, 1.980
    assert top3[0] == pytest.approx(4.257)
    assert top3[1] == pytest.approx(3.343)
    assert top3[2] == pytest.approx(1.980)
    assert len(top3) == 3


def test_hanawalt_index_pads_short_entry():
    entry = _make_entry("s", [1.0, 2.0], [50.0, 100.0])
    top3 = hanawalt_index(entry)
    assert top3 == (2.0, 1.0, 0.0)


def test_hanawalt_index_empty_entry():
    entry = _make_entry("e", [], [])
    assert hanawalt_index(entry) == (0.0, 0.0, 0.0)


def test_fink_index_returns_up_to_8_sorted_by_d_desc():
    entry = _make_entry("q", _QUARTZ_D, _QUARTZ_I)
    fink = fink_index(entry)
    # 8 strongest intensities: 100,100,14,12,12,7,4,4 → ds =
    # 4.257, 3.343, 1.980, 2.457, 2.282, 2.237, 2.128, 1.818
    # sorted by d desc: 4.257, 3.343, 2.457, 2.282, 2.237, 2.128, 1.980, 1.818
    expected = [4.257, 3.343, 2.457, 2.282, 2.237, 2.128, 1.980, 1.818]
    assert len(fink) == 8
    for got, exp in zip(fink, expected, strict=True):
        assert got == pytest.approx(exp)
    assert all(fink[i] >= fink[i + 1] for i in range(7))


def test_fink_index_pads_to_eight():
    entry = _make_entry("s", [3.0, 2.0, 1.0], [10.0, 20.0, 30.0])
    fink = fink_index(entry)
    assert fink[:3] == (3.0, 2.0, 1.0)
    assert fink[3:] == (0.0, 0.0, 0.0, 0.0, 0.0)


# --------------------------------------------------------------------------- #
# Key construction
# --------------------------------------------------------------------------- #


def test_make_hanawalt_key_quantizes():
    entry = _make_entry("q", _QUARTZ_D, _QUARTZ_I)
    key = make_hanawalt_key(entry, tolerance=0.03)
    assert len(key) == 3
    expected = [str(int(round(d / 0.03))) for d in (4.257, 3.343, 1.980)]
    assert list(key) == expected


def test_make_hanawalt_key_tolerance_changes_bins():
    entry = _make_entry("q", _QUARTZ_D, _QUARTZ_I)
    k1 = make_hanawalt_key(entry, tolerance=0.03)
    k2 = make_hanawalt_key(entry, tolerance=0.1)
    assert k1 != k2


# --------------------------------------------------------------------------- #
# Lookup builders
# --------------------------------------------------------------------------- #


def test_build_hanawalt_lookup_contains_entry():
    entry = _make_entry("q", _QUARTZ_D, _QUARTZ_I)
    lookup = build_hanawalt_lookup([entry])
    # The exact top-3 key must be present.
    key = "_".join(make_hanawalt_key(entry, tolerance=0.03))
    assert key in lookup
    assert entry.entry_id in lookup[key]


def test_build_hanawalt_lookup_indexes_multiple_combos():
    # Entry with 5 distinct peaks → C(5,3) = 10 keys.
    ds = [5.0, 4.0, 3.0, 2.0, 1.0]
    ints = [100.0, 80.0, 60.0, 40.0, 20.0]
    entry = _make_entry("m", ds, ints)
    lookup = build_hanawalt_lookup([entry])
    assert sum(1 for v in lookup.values() if entry.entry_id in v) == 10


# --------------------------------------------------------------------------- #
# Pre-filter: true-phase retention
# --------------------------------------------------------------------------- #


def _exp_peaks_from_entry(entry: Entry, n: int = 5) -> list[Peak]:
    """Build experimental peaks from the entry's top-n lines (perfect match)."""
    order = np.argsort(entry.intensities)[::-1][:n]
    peaks = []
    for i in order:
        d = float(entry.d_spacings[i])
        tt = 2.0 * np.degrees(np.arcsin(WL / (2.0 * d)))
        peaks.append(Peak(two_theta=float(tt), intensity=float(entry.intensities[i]), d=d))
    return peaks


def test_pre_filter_hanawalt_retains_true_phase():
    target = _make_entry("quartz", _QUARTZ_D, _QUARTZ_I)
    distractors = [
        _make_entry(f"d{i}", [3.0 + i * 0.1, 2.0, 1.5], [100.0, 50.0, 30.0])
        for i in range(50)
    ]
    entries = [target] + distractors
    exp = _exp_peaks_from_entry(target)
    cands = pre_filter_hanawalt(exp, entries, wavelength=WL, top_k=2000)
    assert "quartz" in cands


def test_pre_filter_fink_retains_true_phase():
    target = _make_entry("quartz", _QUARTZ_D, _QUARTZ_I)
    distractors = [
        _make_entry(f"d{i}", [3.0 + i * 0.1, 2.0, 1.5], [100.0, 50.0, 30.0])
        for i in range(50)
    ]
    entries = [target] + distractors
    exp = _exp_peaks_from_entry(target)
    cands = pre_filter_fink(exp, entries, wavelength=WL, top_k=2000)
    assert "quartz" in cands


def test_pre_filter_both_is_union():
    target = _make_entry("quartz", _QUARTZ_D, _QUARTZ_I)
    distractors = [
        _make_entry(f"d{i}", [3.0 + i * 0.1, 2.0, 1.5], [100.0, 50.0, 30.0])
        for i in range(20)
    ]
    entries = [target] + distractors
    exp = _exp_peaks_from_entry(target)
    both = set(pre_filter(exp, entries, method="both", wavelength=WL))
    h = set(pre_filter(exp, entries, method="hanawalt", wavelength=WL))
    f = set(pre_filter(exp, entries, method="fink", wavelength=WL))
    assert both == (h | f)
    assert "quartz" in both


def test_pre_filter_invalid_method_raises():
    target = _make_entry("quartz", _QUARTZ_D, _QUARTZ_I)
    exp = _exp_peaks_from_entry(target)
    with pytest.raises(ValueError):
        pre_filter(exp, [target], method="nope", wavelength=WL)


def test_pre_filter_returns_empty_when_no_d_values():
    target = _make_entry("quartz", _QUARTZ_D, _QUARTZ_I)
    # Peaks with two_theta=0 → no usable d.
    exp = [Peak(two_theta=0.0, intensity=100.0)]
    assert pre_filter_hanawalt(exp, [target], wavelength=WL) == []
    assert pre_filter_fink(exp, [target], wavelength=WL) == []


# --------------------------------------------------------------------------- #
# Performance
# --------------------------------------------------------------------------- #


def test_pre_filter_hanawalt_perf_10k_under_half_second():
    rng = np.random.default_rng(42)
    n = 10_000
    entries = []
    for i in range(n):
        ds = rng.uniform(1.0, 5.0, size=8).tolist()
        ints = rng.uniform(1.0, 100.0, size=8).tolist()
        entries.append(_make_entry(f"e{i}", ds, ints))
    target = entries[1234]
    exp = _exp_peaks_from_entry(target)
    t0 = time.perf_counter()
    cands = pre_filter_hanawalt(exp, entries, wavelength=WL, top_k=2000)
    dt = time.perf_counter() - t0
    assert target.entry_id in cands
    assert dt < 0.5, f"hanawalt pre-filter took {dt:.3f}s > 0.5s"
