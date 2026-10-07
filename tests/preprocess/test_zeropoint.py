"""Tests for zero-point correction (T3.5)."""

import numpy as np

from xinmatch.core.preprocess.zeropoint import correct_zero_point, find_shift


def test_correct_zero_point_shifts_axis():
    t = np.array([10.0, 20.0, 30.0])
    out = correct_zero_point(t, shift=0.05)
    np.testing.assert_allclose(out, [9.95, 19.95, 29.95])


def test_find_shift_recovers_known_offset():
    """Synthetic spectrum shifted by 0.05° → recovered error < 0.01°."""
    standard = np.array([20.0, 35.0, 50.0, 65.0, 80.0])
    shift_true = 0.05
    experimental = standard + shift_true

    shift = find_shift(experimental, standard)
    assert abs(shift - shift_true) < 0.01, f"shift={shift}, expected {shift_true}"


def test_find_shift_empty():
    assert find_shift(np.array([]), np.array([1.0, 2.0])) == 0.0
    assert find_shift(np.array([1.0]), np.array([])) == 0.0


def test_correct_plus_find_roundtrip():
    standard = np.array([15.0, 30.0, 45.0, 60.0])
    experimental = standard + 0.03
    shift = find_shift(experimental, standard)
    corrected = correct_zero_point(experimental, shift)
    np.testing.assert_allclose(corrected, standard, atol=0.01)
