"""Tests for :class:`xinmatch.core.model.Peak` and :func:`sort_peaks`."""

import pytest

from xinmatch.core.model import Peak, sort_peaks


def test_peak_defaults():
    p = Peak(two_theta=25.0, intensity=100.0)
    assert p.fwhm is None
    assert p.hkl is None
    assert not p.correlated
    assert not p.marked


def test_peak_serialization_roundtrip():
    p = Peak(
        two_theta=25.123,
        intensity=456.7,
        fwhm=0.12,
        d=3.54,
        hkl=(1, 1, 1),
        correlated=True,
        marked=True,
    )
    restored = Peak.from_dict(p.to_dict())
    assert restored.two_theta == pytest.approx(25.123)
    assert restored.intensity == pytest.approx(456.7)
    assert restored.fwhm == pytest.approx(0.12)
    assert restored.d == pytest.approx(3.54)
    assert restored.hkl == (1, 1, 1)
    assert restored.correlated is True
    assert restored.marked is True


def test_sort_peaks_by_two_theta():
    peaks = [Peak(30.0, 1.0), Peak(10.0, 2.0), Peak(20.0, 3.0)]
    sorted_peaks = sort_peaks(peaks, "two_theta")
    assert [p.two_theta for p in sorted_peaks] == [10.0, 20.0, 30.0]


def test_sort_peaks_returns_new_list():
    peaks = [Peak(30.0, 1.0), Peak(10.0, 2.0)]
    sorted_peaks = sort_peaks(peaks)
    assert peaks is not sorted_peaks
    # original order unchanged
    assert peaks[0].two_theta == 30.0
