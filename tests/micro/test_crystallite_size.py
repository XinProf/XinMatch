"""Tests for crystallite size estimation (T11.1)."""

import math

import pytest

from xinmatch.core.micro.crystallite_size import (
    scherrer,
    scherrer_from_peaks,
    scherrer_williamson_hall,
)
from xinmatch.core.model import Peak

# ---------------------------------------------------------------------------
# scherrer (single peak)
# ---------------------------------------------------------------------------


def test_scherrer_single_peak_basic():
    """FWHM=0.1°, 2θ=30°, λ=1.5406, K=0.9 → D ≈ 82.24 nm.

    Hand-derivation:
        β = 0.1° × π/180 = 1.7453e-3 rad
        θ = 15° → cos θ = 0.96593
        D_Å = (0.9 × 1.5406) / (β × cos θ) ≈ 822.43 Å → 82.24 nm
    """
    d_nm = scherrer(0.1, 30.0, 1.5406, k=0.9)
    expected_angstrom = (0.9 * 1.5406) / (
        0.1 * math.pi / 180 * math.cos(math.radians(15.0))
    )
    expected_nm = expected_angstrom / 10.0
    assert abs(d_nm - expected_nm) < 1e-9
    # Sanity bounds — value should land in the 80–85 nm range.
    assert 80.0 < d_nm < 85.0


def test_scherrer_with_k_094_match_default():
    """K=0.94 (Match! default per docs) → D scales linearly with K."""
    d1 = scherrer(0.1, 30.0, 1.5406, k=0.9)
    d2 = scherrer(0.1, 30.0, 1.5406, k=0.94)
    assert abs(d2 / d1 - 0.94 / 0.9) < 1e-9


def test_scherrer_with_k_1():
    """K=1.0 → D scales linearly with K."""
    d1 = scherrer(0.1, 30.0, 1.5406, k=0.9)
    d2 = scherrer(0.1, 30.0, 1.5406, k=1.0)
    assert abs(d2 / d1 - 1.0 / 0.9) < 1e-9


def test_scherrer_smaller_fwhm_larger_d():
    """Doubled FWHM → halved D (inverse relationship)."""
    d_small = scherrer(0.1, 30.0, 1.5406)
    d_large = scherrer(0.2, 30.0, 1.5406)
    assert abs(d_large - d_small / 2) < 1e-9


def test_scherrer_higher_two_theta_larger_d():
    """At higher 2θ (smaller cos θ), the same FWHM gives larger D."""
    d_low = scherrer(0.1, 30.0, 1.5406)
    d_high = scherrer(0.1, 60.0, 1.5406)
    assert d_high > d_low


def test_scherrer_cu_kalpha_default_lambda_handled():
    """Common Cu Kα1 wavelength produces a finite positive result."""
    d = scherrer(0.15, 28.0, 1.5406)
    assert d > 0


def test_scherrer_invalid_fwhm_raises():
    with pytest.raises(ValueError, match="fwhm_deg must be positive"):
        scherrer(0.0, 30.0, 1.5406)
    with pytest.raises(ValueError, match="fwhm_deg must be positive"):
        scherrer(-0.1, 30.0, 1.5406)


def test_scherrer_invalid_two_theta_raises():
    with pytest.raises(ValueError, match="two_theta_deg"):
        scherrer(0.1, 0.0, 1.5406)
    with pytest.raises(ValueError, match="two_theta_deg"):
        scherrer(0.1, 180.0, 1.5406)
    with pytest.raises(ValueError, match="two_theta_deg"):
        scherrer(0.1, -5.0, 1.5406)


def test_scherrer_invalid_wavelength_raises():
    with pytest.raises(ValueError, match="wavelength"):
        scherrer(0.1, 30.0, 0.0)
    with pytest.raises(ValueError, match="wavelength"):
        scherrer(0.1, 30.0, -1.0)


def test_scherrer_invalid_k_raises():
    with pytest.raises(ValueError, match="Scherrer"):
        scherrer(0.1, 30.0, 1.5406, k=0.0)
    with pytest.raises(ValueError, match="Scherrer"):
        scherrer(0.1, 30.0, 1.5406, k=-0.5)


# ---------------------------------------------------------------------------
# scherrer_from_peaks (batch)
# ---------------------------------------------------------------------------


def test_scherrer_from_peaks_basic():
    peaks = [
        Peak(two_theta=28.0, intensity=100.0, fwhm=0.2),
        Peak(two_theta=40.0, intensity=80.0, fwhm=0.15),
        Peak(two_theta=55.0, intensity=60.0, fwhm=0.18),
    ]
    results = scherrer_from_peaks(peaks, 1.5406, k=0.9)
    assert len(results) == 3
    for peak, d in results:
        assert d > 0
        expected = scherrer(peak.fwhm, peak.two_theta, 1.5406, k=0.9)
        assert abs(d - expected) < 1e-12


def test_scherrer_from_peaks_skips_missing_fwhm():
    """Peaks with fwhm=None or fwhm <= 0 are silently skipped."""
    peaks = [
        Peak(two_theta=28.0, intensity=100.0, fwhm=None),
        Peak(two_theta=40.0, intensity=80.0, fwhm=0.15),
        Peak(two_theta=55.0, intensity=60.0, fwhm=0.0),  # invalid
        Peak(two_theta=70.0, intensity=50.0, fwhm=-0.1),  # invalid
    ]
    results = scherrer_from_peaks(peaks, 1.5406)
    assert len(results) == 1
    assert results[0][0].two_theta == 40.0


def test_scherrer_from_peaks_empty_input():
    assert scherrer_from_peaks([], 1.5406) == []


def test_scherrer_from_peaks_all_skipped():
    """If every peak is invalid, the result is an empty list."""
    peaks = [
        Peak(two_theta=28.0, intensity=100.0, fwhm=None),
        Peak(two_theta=40.0, intensity=80.0, fwhm=0.0),
    ]
    assert scherrer_from_peaks(peaks, 1.5406) == []


def test_scherrer_from_peaks_preserves_input_order():
    peaks = [
        Peak(two_theta=70.0, intensity=50.0, fwhm=0.1),
        Peak(two_theta=28.0, intensity=100.0, fwhm=0.2),
        Peak(two_theta=40.0, intensity=80.0, fwhm=0.15),
    ]
    results = scherrer_from_peaks(peaks, 1.5406)
    assert [r[0].two_theta for r in results] == [70.0, 28.0, 40.0]


# ---------------------------------------------------------------------------
# scherrer_williamson_hall
# ---------------------------------------------------------------------------


def _wh_synthetic_dataset(d_angstrom: float, eps: float, k: float, lam: float):
    """Build a perfectly linear Williamson-Hall dataset for given D, ε."""
    two_theta_list = [20.0, 35.0, 50.0, 65.0, 80.0]
    fwhm_list = []
    for two_theta in two_theta_list:
        theta = math.radians(two_theta / 2.0)
        beta_cos_theta = (k * lam) / d_angstrom + 4 * eps * math.sin(theta)
        cos_theta = math.cos(theta)
        beta_rad = beta_cos_theta / cos_theta
        beta_deg = beta_rad * 180.0 / math.pi
        fwhm_list.append(beta_deg)
    return fwhm_list, two_theta_list


def test_williamson_hall_synthetic_recovers_d_and_strain():
    """Synthetic data with known D=100 nm and ε=0.001 → recover within 5%."""
    k = 0.9
    lam = 1.5406
    d_true_angstrom = 1000.0  # 100 nm
    eps_true = 0.001

    fwhm_list, two_theta_list = _wh_synthetic_dataset(
        d_true_angstrom, eps_true, k, lam
    )

    d_nm, eps = scherrer_williamson_hall(
        fwhm_list, two_theta_list, lam, k=k
    )
    assert abs(d_nm - 100.0) / 100.0 < 0.05
    assert abs(eps - 0.001) / 0.001 < 0.05


def test_williamson_hall_zero_strain_recovers_d():
    """Pure size broadening (ε=0) → slope ≈ 0, D recovered exactly."""
    k = 0.9
    lam = 1.5406
    d_true_angstrom = 500.0  # 50 nm
    fwhm_list, two_theta_list = _wh_synthetic_dataset(
        d_true_angstrom, 0.0, k, lam
    )
    d_nm, eps = scherrer_williamson_hall(
        fwhm_list, two_theta_list, lam, k=k
    )
    assert abs(d_nm - 50.0) < 0.5  # 1 nm tolerance
    assert abs(eps) < 1e-9


def test_williamson_hall_large_strain_recovers():
    """Larger ε (0.005) is recovered reliably."""
    k = 0.9
    lam = 1.5406
    d_true_angstrom = 800.0  # 80 nm
    eps_true = 0.005
    fwhm_list, two_theta_list = _wh_synthetic_dataset(
        d_true_angstrom, eps_true, k, lam
    )
    d_nm, eps = scherrer_williamson_hall(
        fwhm_list, two_theta_list, lam, k=k
    )
    assert abs(d_nm - 80.0) / 80.0 < 0.05
    assert abs(eps - 0.005) / 0.005 < 0.05


def test_williamson_hall_mismatched_lengths_raises():
    with pytest.raises(ValueError, match="same length"):
        scherrer_williamson_hall([0.1, 0.2], [30.0], 1.5406)


def test_williamson_hall_too_few_points_raises():
    with pytest.raises(ValueError, match="at least 2"):
        scherrer_williamson_hall([0.1], [30.0], 1.5406)
    with pytest.raises(ValueError, match="at least 2"):
        scherrer_williamson_hall([], [], 1.5406)


def test_williamson_hall_invalid_fwhm_raises():
    with pytest.raises(ValueError, match="positive"):
        scherrer_williamson_hall([0.1, 0.0], [30.0, 50.0], 1.5406)
    with pytest.raises(ValueError, match="positive"):
        scherrer_williamson_hall([0.1, -0.2], [30.0, 50.0], 1.5406)


def test_williamson_hall_invalid_two_theta_raises():
    with pytest.raises(ValueError, match="2θ"):
        scherrer_williamson_hall([0.1, 0.2], [0.0, 50.0], 1.5406)
    with pytest.raises(ValueError, match="2θ"):
        scherrer_williamson_hall([0.1, 0.2], [180.0, 50.0], 1.5406)


def test_williamson_hall_invalid_wavelength_raises():
    with pytest.raises(ValueError, match="wavelength"):
        scherrer_williamson_hall([0.1, 0.2], [30.0, 50.0], 0.0)


def test_williamson_hall_invalid_k_raises():
    with pytest.raises(ValueError, match="Scherrer"):
        scherrer_williamson_hall([0.1, 0.2], [30.0, 50.0], 1.5406, k=0.0)
