"""Tests for the peak-shape model (T10.1)."""

import numpy as np
import pytest

from xinmatch.core.refine.peak_model import (
    PeakModel,
    asymmetric_pseudo_voigt,
    caglioti_fwhm,
)


def test_caglioti_pure_w():
    """With U = V = 0, H = sqrt(W) at all 2θ."""
    w = 0.01
    for tth in (10.0, 30.0, 60.0, 120.0):
        assert abs(caglioti_fwhm(tth, 0.0, 0.0, w) - np.sqrt(w)) < 1e-12


def test_caglioti_positive_uvw():
    """H² should be non-negative for physical parameter sets."""
    h = caglioti_fwhm(45.0, 0.005, -0.001, 0.02)
    assert h >= 0.0


def test_caglioti_negative_radicand_returns_zero():
    """A strongly negative W gives H = 0 (no crash)."""
    assert caglioti_fwhm(10.0, 0.0, 0.0, -1.0) == 0.0


def test_asymmetric_pv_unit_area():
    """Asymmetric pseudo-Voigt integrates to 1 (unit-area normalisation)."""
    x = np.linspace(-50, 50, 200001)
    for asymmetry in (-0.5, 0.0, 0.3):
        y = asymmetric_pseudo_voigt(x, 0.0, 1.0, 0.5, asymmetry=asymmetry)
        area = np.trapz(y, x)
        assert abs(area - 1.0) < 1e-2, f"asymmetry={asymmetry}, area={area}"


def test_asymmetric_pv_symmetry_recovers_standard():
    """asymmetry = 0 equals the plain pseudo-Voigt."""
    from xinmatch.core.peak.shapes import pseudo_voigt

    x = np.linspace(-5, 5, 1001)
    y_asym = asymmetric_pseudo_voigt(x, 0.0, 0.5, 0.4, asymmetry=0.0)
    y_std = pseudo_voigt(x, 0.0, 0.5, 1.0, eta=0.4)
    np.testing.assert_allclose(y_asym, y_std, atol=1e-10)


def test_asymmetric_pv_positive_broadens_left():
    """Positive asymmetry makes the low-angle side broader."""
    x = np.linspace(-3, 3, 6001)
    y = asymmetric_pseudo_voigt(x, 0.0, 0.5, 0.5, asymmetry=0.5)
    half = y.max() / 2.0
    left = x[x < 0][y[x < 0] >= half]
    right = x[x >= 0][y[x >= 0] >= half]
    left_width = 0.0 - left[0] if left.size else 0.0
    right_width = right[-1] - 0.0 if right.size else 0.0
    assert left_width > right_width


def test_peak_model_fwhm_uses_caglioti():
    pm = PeakModel(eta=0.5, asymmetry=0.0, caglioti_uvw=(0.0, 0.0, 0.04))
    assert abs(pm.fwhm(30.0) - 0.2) < 1e-9


def test_peak_model_shape_function_scales_intensity():
    pm = PeakModel(eta=0.5, asymmetry=0.0, caglioti_uvw=(0.0, 0.0, 0.01))
    x = np.linspace(-10, 10, 4001)
    y = pm.shape_function(x, 0.0, 0.1, 42.0)
    assert abs(np.trapz(y, x) - 42.0) < 1e-1


def test_peak_model_eta_clamped():
    pm = PeakModel(eta=2.0)
    assert pm.eta == 1.0


def test_peak_model_unsupported_shape_raises():
    with pytest.raises(NotImplementedError):
        PeakModel(shape="gaussian")


def test_peak_model_bad_uvw_length_raises():
    with pytest.raises(ValueError):
        PeakModel(caglioti_uvw=(0.0, 0.0))  # type: ignore[arg-type]
