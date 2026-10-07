"""Tests for :class:`xinmatch.core.model.Pattern`."""

import numpy as np
import pytest

from xinmatch.core.model import Pattern


@pytest.fixture
def pattern() -> Pattern:
    two_theta = np.linspace(10.0, 80.0, 701)
    intensity = np.random.default_rng(0).random(701) * 1000
    return Pattern(two_theta, intensity, wavelength=1.5406, step=0.1)


def test_shape_validation():
    with pytest.raises(ValueError):
        Pattern(np.array([1.0, 2.0]), np.array([1.0]))


def test_1d_validation():
    with pytest.raises(ValueError):
        Pattern(np.array([[1.0, 2.0]]), np.array([[1.0, 2.0]]))


def test_len(pattern: Pattern):
    assert len(pattern) == 701


def test_slice_by_index(pattern: Pattern):
    sub = pattern[10:20]
    assert len(sub) == 10
    np.testing.assert_array_equal(sub.two_theta, pattern.two_theta[10:20])


def test_slice_by_two_theta_range(pattern: Pattern):
    sub = pattern[(20.0, 30.0)]
    assert sub.two_theta.min() >= 20.0
    assert sub.two_theta.max() <= 30.0


def test_bragg_d_spacing_roundtrip(pattern: Pattern):
    """2θ → d → 2θ should recover the original 2θ."""
    d = pattern.d_spacing
    recovered = pattern.d_to_two_theta(d)
    np.testing.assert_allclose(recovered, pattern.two_theta, atol=1e-9)


def test_q_consistency(pattern: Pattern):
    """Q = 2π / d."""
    np.testing.assert_allclose(pattern.q, 2 * np.pi / pattern.d_spacing, atol=1e-9)


def test_resample_on_same_grid(pattern: Pattern):
    """Resampling onto the same grid recovers the original intensities."""
    resampled = pattern.resample(pattern.two_theta)
    np.testing.assert_allclose(resampled.intensity, pattern.intensity, atol=1e-12)


def test_resample_step_inferred():
    p = Pattern(np.array([10.0, 11.0, 12.0]), np.array([1.0, 2.0, 1.0]))
    r = p.resample(np.array([10.0, 10.5, 11.0, 11.5, 12.0]))
    assert r.step == pytest.approx(0.5)


def test_round_trip_serialization(pattern: Pattern):
    d = pattern.to_dict()
    restored = Pattern.from_dict(d)
    np.testing.assert_array_equal(restored.two_theta, pattern.two_theta)
    np.testing.assert_array_equal(restored.intensity, pattern.intensity)
    assert restored.wavelength == pattern.wavelength
