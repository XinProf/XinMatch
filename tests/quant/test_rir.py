"""Tests for RIR quantitative phase analysis (T8.1)."""

import pytest

from xinmatch.core.model import Peak
from xinmatch.core.quant.rir import (
    RirResult,
    compute_rir_from_pure_pattern,
    rir_quantify,
    rir_quantify_detailed,
)

# ---------------------------------------------------------------------------
# rir_quantify — adiabatic method
# ---------------------------------------------------------------------------


def test_50_50_equal_rir_adiabatic():
    """50/50 mix, both RIR=1.0 → 50/50 weight split (error < 3 wt%)."""
    intensities = {"A": 100.0, "B": 100.0}
    rirs = {"A": 1.0, "B": 1.0}
    weights = rir_quantify(intensities, rirs)
    assert abs(weights["A"] - 0.5) < 0.03
    assert abs(weights["B"] - 0.5) < 0.03
    assert abs(sum(weights.values()) - 1.0) < 1e-12


def test_30_70_unequal_rir_adiabatic():
    """30/70 mix, RIR_A=1.2, RIR_B=0.8 → recover weight fractions (<5 wt%)."""
    # Target W_A=0.3, W_B=0.7.  In adiabatic: W_i ∝ I_i/RIR_i.
    # Pick I_A = 0.36 (so I_A/RIR_A = 0.3), I_B = 0.56 (so I_B/RIR_B = 0.7).
    intensities = {"A": 0.36, "B": 0.56}
    rirs = {"A": 1.2, "B": 0.8}
    weights = rir_quantify(intensities, rirs)
    assert abs(weights["A"] - 0.3) < 0.05
    assert abs(weights["B"] - 0.7) < 0.05
    assert abs(sum(weights.values()) - 1.0) < 1e-12


def test_three_phase_adiabatic_normalizes_to_one():
    """3-phase mix → weights sum to 1.0, each within 5 wt% of target."""
    # Target: W_A=0.5, W_B=0.3, W_C=0.2; RIRs A=1.0, B=1.5, C=0.8.
    # Choose I_i so that I_i/RIR_i = W_i (i.e. ratios already normalised).
    intensities = {"A": 0.5, "B": 0.45, "C": 0.16}
    rirs = {"A": 1.0, "B": 1.5, "C": 0.8}
    weights = rir_quantify(intensities, rirs)
    assert abs(weights["A"] - 0.5) < 0.05
    assert abs(weights["B"] - 0.3) < 0.05
    assert abs(weights["C"] - 0.2) < 0.05
    assert abs(sum(weights.values()) - 1.0) < 1e-12


# ---------------------------------------------------------------------------
# rir_quantify — reference-relative method
# ---------------------------------------------------------------------------


def test_reference_phase_equals_adiabatic():
    """Reference-relative method equals adiabatic (math equivalent)."""
    intensities = {"A": 100.0, "B": 80.0, "corundum": 90.0}
    rirs = {"A": 1.5, "B": 1.2, "corundum": 1.0}
    adiabatic = rir_quantify(intensities, rirs)
    reference = rir_quantify(intensities, rirs, reference_phase="corundum")
    for p in adiabatic:
        assert abs(adiabatic[p] - reference[p]) < 1e-12
    assert abs(sum(reference.values()) - 1.0) < 1e-12


def test_reference_phase_weights_reasonable():
    """Reference method returns sensible weight fractions."""
    # Corundum as one of three mixture phases.
    intensities = {"quartz": 200.0, "corundum": 100.0, "calcite": 150.0}
    rirs = {"quartz": 3.0, "corundum": 1.0, "calcite": 2.0}
    weights = rir_quantify(intensities, rirs, reference_phase="corundum")
    assert abs(sum(weights.values()) - 1.0) < 1e-12
    # I/RIR: quartz=66.7, corundum=100, calcite=75 → total 241.7
    assert abs(weights["quartz"] - 66.7 / 241.7) < 0.02
    assert abs(weights["corundum"] - 100.0 / 241.7) < 0.02
    assert abs(weights["calcite"] - 75.0 / 241.7) < 0.02


# ---------------------------------------------------------------------------
# rir_quantify — error handling
# ---------------------------------------------------------------------------


def test_empty_intensities_raises():
    with pytest.raises(ValueError, match="empty"):
        rir_quantify({}, {"A": 1.0})


def test_empty_rir_raises():
    with pytest.raises(ValueError, match="empty"):
        rir_quantify({"A": 100.0}, {})


def test_missing_rir_raises():
    with pytest.raises(ValueError, match="RIR value missing"):
        rir_quantify({"A": 100.0, "B": 50.0}, {"A": 1.0})


def test_non_positive_rir_raises():
    with pytest.raises(ValueError, match="positive"):
        rir_quantify({"A": 100.0, "B": 50.0}, {"A": 1.0, "B": 0.0})
    with pytest.raises(ValueError, match="positive"):
        rir_quantify({"A": 100.0}, {"A": -1.0})


def test_zero_total_intensity_raises():
    with pytest.raises(ValueError, match="zero"):
        rir_quantify({"A": 0.0, "B": 0.0}, {"A": 1.0, "B": 1.0})


def test_unknown_reference_phase_raises():
    with pytest.raises(ValueError, match="reference phase"):
        rir_quantify({"A": 100.0}, {"A": 1.0}, reference_phase="corundum")


def test_reference_phase_not_in_rir_raises():
    intensities = {"A": 100.0, "B": 50.0}
    rirs = {"A": 1.0, "B": 1.0}
    with pytest.raises(ValueError, match="reference phase"):
        rir_quantify(intensities, rirs, reference_phase="corundum")


# ---------------------------------------------------------------------------
# compute_rir_from_pure_pattern
# ---------------------------------------------------------------------------


def test_compute_rir_from_pure_pattern_basic():
    """Strongest peak intensity / corundum intensity = RIR."""
    peaks = [
        Peak(two_theta=20.0, intensity=80.0),
        Peak(two_theta=25.0, intensity=240.0),
        Peak(two_theta=35.0, intensity=50.0),
    ]
    rir = compute_rir_from_pure_pattern(peaks, "A", 1.5406)
    # Corundum main peak = 100 (default), strongest A peak = 240 → RIR=2.4.
    assert abs(rir - 2.4) < 1e-12


def test_compute_rir_custom_reference_intensity():
    peaks = [Peak(two_theta=25.0, intensity=200.0)]
    rir = compute_rir_from_pure_pattern(
        peaks, "A", 1.5406, reference_intensity=100.0
    )
    assert abs(rir - 2.0) < 1e-12


def test_compute_rir_uses_strongest_not_first():
    """Strongest peak is picked, even if it is not the first."""
    peaks = [
        Peak(two_theta=20.0, intensity=10.0),
        Peak(two_theta=30.0, intensity=500.0),
        Peak(two_theta=40.0, intensity=200.0),
    ]
    rir = compute_rir_from_pure_pattern(peaks, "A", 1.5406)
    assert abs(rir - 5.0) < 1e-12


def test_compute_rir_empty_peaks_raises():
    with pytest.raises(ValueError, match="empty"):
        compute_rir_from_pure_pattern([], "A", 1.5406)


def test_compute_rir_zero_intensity_raises():
    peaks = [Peak(two_theta=25.0, intensity=0.0)]
    with pytest.raises(ValueError, match="non-positive"):
        compute_rir_from_pure_pattern(peaks, "A", 1.5406)


def test_compute_rir_negative_intensity_raises():
    peaks = [Peak(two_theta=25.0, intensity=-50.0)]
    with pytest.raises(ValueError, match="non-positive"):
        compute_rir_from_pure_pattern(peaks, "A", 1.5406)


def test_compute_rir_zero_reference_intensity_raises():
    peaks = [Peak(two_theta=25.0, intensity=100.0)]
    with pytest.raises(ValueError, match="positive"):
        compute_rir_from_pure_pattern(
            peaks, "A", 1.5406, reference_intensity=0.0
        )


# ---------------------------------------------------------------------------
# rir_quantify_detailed
# ---------------------------------------------------------------------------


def test_rir_quantify_detailed_basic():
    """Detailed result preserves weight fractions and metadata."""
    intensities = {"A": 0.5, "B": 0.45}
    rirs = {"A": 1.0, "B": 1.5}
    results = rir_quantify_detailed(intensities, rirs)

    assert len(results) == 2
    assert all(isinstance(r, RirResult) for r in results)

    by_phase = {r.phase: r for r in results}
    assert by_phase["A"].rir == 1.0
    assert by_phase["A"].peak_intensity == 0.5
    assert by_phase["B"].rir == 1.5
    assert by_phase["B"].peak_intensity == 0.45
    # I/RIR: A=0.5, B=0.3 → W_A=0.625, W_B=0.375.
    assert abs(by_phase["A"].weight_fraction - 0.625) < 1e-9
    assert abs(by_phase["B"].weight_fraction - 0.375) < 1e-9
    assert abs(sum(r.weight_fraction for r in results) - 1.0) < 1e-12


def test_rir_quantify_detailed_with_reference_phase():
    """Detailed result honours the reference_phase kwarg."""
    intensities = {"A": 100.0, "B": 80.0, "corundum": 90.0}
    rirs = {"A": 1.5, "B": 1.2, "corundum": 1.0}
    results = rir_quantify_detailed(
        intensities, rirs, reference_phase="corundum"
    )
    assert len(results) == 3
    phases = {r.phase for r in results}
    assert phases == {"A", "B", "corundum"}
    assert abs(sum(r.weight_fraction for r in results) - 1.0) < 1e-12


def test_rir_quantify_detailed_preserves_input_order():
    """Result list follows insertion order of the input dict."""
    intensities = {"alpha": 1.0, "beta": 2.0, "gamma": 3.0}
    rirs = {"alpha": 1.0, "beta": 1.0, "gamma": 1.0}
    results = rir_quantify_detailed(intensities, rirs)
    assert [r.phase for r in results] == ["alpha", "beta", "gamma"]
