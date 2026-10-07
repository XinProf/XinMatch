"""Tests for FoM criteria (T6.2)."""

from __future__ import annotations

import math

import pytest

from xinmatch.core.model import Peak
from xinmatch.core.search.correlate import correlate_peaks
from xinmatch.core.search.fom_criteria import (
    DEFAULT_WEIGHTS,
    FomWeights,
    compute_fom,
    compute_p_values,
    score_candidate,
)

# Cu Kα wavelength used throughout.
WL = 1.5406


def _d_from_two_theta(two_theta: float, wavelength: float = WL) -> float:
    return wavelength / (2.0 * math.sin(math.radians(two_theta / 2.0)))


def _make_perfect_data(
    exp_two_theta: list[float] | None = None,
    exp_intensities: list[float] | None = None,
) -> tuple[list[Peak], list[tuple[float, float]]]:
    """Synthesise an experimental peak list and a matching (d, intensity) reference.

    By default the two peak lists are *identical* (after d→2θ conversion)
    so the FoM should evaluate to 1.0.
    """
    if exp_two_theta is None:
        exp_two_theta = [10.0, 20.0, 30.0, 40.0]
    if exp_intensities is None:
        exp_intensities = [100.0, 50.0, 25.0, 10.0]
    exp_peaks = [
        Peak(two_theta=tt, intensity=intensity)
        for tt, intensity in zip(exp_two_theta, exp_intensities, strict=True)
    ]
    ref_ds = [_d_from_two_theta(tt) for tt in exp_two_theta]
    ref_peaks_d_intensity = list(zip(ref_ds, exp_intensities, strict=True))
    return exp_peaks, ref_peaks_d_intensity


# --------------------------------------------------------------------- #
# FomWeights
# --------------------------------------------------------------------- #


def test_default_weights_match_fom_model():
    """Defaults must equal the table in FOM_MODEL.md §2 (R² = 0.9913)."""
    assert DEFAULT_WEIGHTS.peakpos == pytest.approx(0.2275)
    assert DEFAULT_WEIGHTS.intensity == pytest.approx(0.1112)
    assert DEFAULT_WEIGHTS.npeaks == pytest.approx(0.2306)
    assert DEFAULT_WEIGHTS.ncorr == pytest.approx(0.1152)
    assert DEFAULT_WEIGHTS.i_scale == pytest.approx(0.0454)


def test_fom_weights_frozen():
    """FomWeights is frozen — cannot be mutated in place."""
    # FrozenInstanceError subclasses AttributeError in Python 3.10+.
    with pytest.raises(AttributeError):
        DEFAULT_WEIGHTS.peakpos = 0.5  # type: ignore[misc]


def test_fom_weights_custom_overrides():
    custom = FomWeights(
        peakpos=1.0, intensity=0.0, npeaks=0.0, ncorr=0.0, i_scale=0.0
    )
    assert custom.peakpos == 1.0
    assert custom.intensity == 0.0


def test_fom_weights_as_dict_roundtrip():
    d = DEFAULT_WEIGHTS.as_dict()
    assert set(d.keys()) == {
        "peakpos",
        "intensity",
        "npeaks",
        "ncorr",
        "i_scale",
    }


# --------------------------------------------------------------------- #
# compute_p_values
# --------------------------------------------------------------------- #


def test_compute_p_values_perfect_match():
    """Identical exp and ref → all P = 1, I_scale = 1."""
    exp_peaks, ref_peaks_d_intensity = _make_perfect_data()
    pairs = correlate_peaks(
        exp_peaks, ref_peaks_d_intensity, wavelength=WL, window_deg=0.3
    )
    p = compute_p_values(exp_peaks, ref_peaks_d_intensity, pairs, wavelength=WL)

    assert set(p.keys()) == {"peakpos", "intensity", "npeaks", "ncorr", "i_scale"}
    assert p["peakpos"] == pytest.approx(1.0, abs=1e-9)
    assert p["intensity"] == pytest.approx(1.0, abs=1e-9)
    assert p["npeaks"] == pytest.approx(1.0, abs=1e-9)
    assert p["ncorr"] == pytest.approx(1.0, abs=1e-9)
    assert p["i_scale"] == pytest.approx(1.0, abs=1e-9)


def test_compute_p_values_no_pairs():
    """Empty pairs → all P = 0 except i_scale defaults to 1.0."""
    exp_peaks = [Peak(two_theta=10.0, intensity=100.0)]
    ref_peaks_d_intensity = [(_d_from_two_theta(50.0), 100.0)]  # far away
    # No correlation will pair them.
    p = compute_p_values(exp_peaks, ref_peaks_d_intensity, [], wavelength=WL)
    assert p == {
        "peakpos": 0.0,
        "intensity": 0.0,
        "npeaks": 0.0,
        "ncorr": 0.0,
        "i_scale": 1.0,
    }


def test_compute_p_values_empty_inputs():
    p = compute_p_values([], [], [], wavelength=WL)
    assert p == {
        "peakpos": 0.0,
        "intensity": 0.0,
        "npeaks": 0.0,
        "ncorr": 0.0,
        "i_scale": 1.0,
    }


def test_compute_p_values_positional_mismatch_lowers_p_peakpos():
    """Shifting one reference peak by 0.2° lowers P_peakpos below 1."""
    exp_peaks, ref_peaks_d_intensity = _make_perfect_data()
    # Manually craft a pair where the reference d → 2θ is shifted.
    shifted_d = _d_from_two_theta(10.2)  # 0.2° offset from exp 10.0
    ref_shifted = [(shifted_d, 100.0)] + ref_peaks_d_intensity[1:]
    pairs = [(0, 0), (1, 1), (2, 2), (3, 3)]
    p = compute_p_values(exp_peaks, ref_shifted, pairs, wavelength=WL)
    assert p["peakpos"] < 1.0
    # Sanity bound: 0.2° offset on one of 4 peaks, σ_pos = 0.1°.
    # mean(Δ²) = 0.04/4 = 0.01; exp(-0.01/0.01) = exp(-1) ≈ 0.368
    assert p["peakpos"] == pytest.approx(math.exp(-1.0), abs=1e-3)


def test_compute_p_values_intensity_mismatch_lowers_p_intensity():
    """Altering one reference intensity lowers P_intensity below 1."""
    exp_intensities = [100.0, 50.0, 25.0, 10.0]
    exp_peaks, _ = _make_perfect_data(exp_intensities=exp_intensities)
    # Reference: same d's but flip the second intensity to 5 instead of 50.
    ref_ds = [_d_from_two_theta(tt) for tt in [10.0, 20.0, 30.0, 40.0]]
    ref_intensities = [100.0, 5.0, 25.0, 10.0]
    ref_peaks_d_intensity = list(zip(ref_ds, ref_intensities, strict=True))
    pairs = [(0, 0), (1, 1), (2, 2), (3, 3)]

    p = compute_p_values(exp_peaks, ref_peaks_d_intensity, pairs, wavelength=WL)
    assert p["intensity"] < 1.0
    # exp normalised: [100, 50, 25, 10]
    # ref normalised to max=100: [100, 5, 25, 10]
    # ΔI = [0, 45, 0, 0], mean(Δ²) = 45²/4 = 506.25
    # P_intensity = exp(-506.25 / 100) = exp(-5.0625) ≈ 0.0063
    assert p["intensity"] == pytest.approx(math.exp(-5.0625), abs=1e-3)


def test_compute_p_values_npeaks_partial_coverage():
    """3 of 4 exp peaks matched → P_npeaks = 0.75."""
    exp_peaks = [
        Peak(two_theta=10.0, intensity=100.0),
        Peak(two_theta=20.0, intensity=50.0),
        Peak(two_theta=30.0, intensity=25.0),
        Peak(two_theta=80.0, intensity=10.0),  # no ref counterpart
    ]
    ref_ds = [
        _d_from_two_theta(10.0),
        _d_from_two_theta(20.0),
        _d_from_two_theta(30.0),
    ]
    ref_peaks_d_intensity = list(
        zip(ref_ds, [100.0, 50.0, 25.0], strict=True)
    )
    pairs = correlate_peaks(
        exp_peaks, ref_peaks_d_intensity, wavelength=WL, window_deg=0.3
    )

    p = compute_p_values(exp_peaks, ref_peaks_d_intensity, pairs, wavelength=WL)
    assert p["npeaks"] == pytest.approx(0.75, abs=1e-9)
    # All 3 ref peaks matched out of min(4, 3) = 3 → P_ncorr = 1.0.
    assert p["ncorr"] == pytest.approx(1.0, abs=1e-9)


def test_compute_p_values_ncorr_partial_when_ref_has_extras():
    """If only 2 of 3 ref peaks pair (out of min(4, 3)=3) → P_ncorr = 2/3."""
    exp_peaks = [
        Peak(two_theta=10.0, intensity=100.0),
        Peak(two_theta=20.0, intensity=50.0),
        Peak(two_theta=80.0, intensity=25.0),  # not close to ref peak #3 (at 30.0)
    ]
    ref_ds = [
        _d_from_two_theta(10.0),
        _d_from_two_theta(20.0),
        _d_from_two_theta(30.0),  # no exp counterpart
    ]
    ref_peaks_d_intensity = list(
        zip(ref_ds, [100.0, 50.0, 25.0], strict=True)
    )
    pairs = correlate_peaks(
        exp_peaks, ref_peaks_d_intensity, wavelength=WL, window_deg=0.3
    )

    p = compute_p_values(exp_peaks, ref_peaks_d_intensity, pairs, wavelength=WL)
    # min(n_exp=3, n_ref=3) = 3, matched_ref = 2 → P_ncorr = 2/3.
    assert p["ncorr"] == pytest.approx(2.0 / 3.0, abs=1e-9)


def test_compute_p_values_i_scale_doubled():
    """If exp intensities are 2x ref (same shape, different scale) →
    after per-side normalisation I_scale stays near 1; the *raw* ratio
    would be 2, but the LSQ on normalised values enforces shape match.
    Here we keep shapes identical → I_scale == 1.
    """
    exp_intensities = [200.0, 100.0, 50.0, 20.0]  # 2x the reference
    exp_peaks, ref_peaks_d_intensity = _make_perfect_data(
        exp_intensities=exp_intensities
    )
    pairs = correlate_peaks(
        exp_peaks, ref_peaks_d_intensity, wavelength=WL, window_deg=0.3
    )
    p = compute_p_values(exp_peaks, ref_peaks_d_intensity, pairs, wavelength=WL)
    # Both sides normalised to max=100 → identical shapes → scale = 1.
    assert p["i_scale"] == pytest.approx(1.0, abs=1e-9)


def test_compute_p_values_i_scale_shape_mismatch():
    """Different shape → I_scale ≠ 1."""
    exp_intensities = [100.0, 50.0, 25.0, 10.0]
    exp_peaks, _ = _make_perfect_data(exp_intensities=exp_intensities)
    ref_ds = [_d_from_two_theta(tt) for tt in [10.0, 20.0, 30.0, 40.0]]
    # Reference: half of exp on the second peak (50 → 25 after normalisation 50)
    ref_intensities = [100.0, 25.0, 25.0, 10.0]
    ref_peaks_d_intensity = list(zip(ref_ds, ref_intensities, strict=True))
    pairs = [(0, 0), (1, 1), (2, 2), (3, 3)]

    p = compute_p_values(exp_peaks, ref_peaks_d_intensity, pairs, wavelength=WL)
    # exp_norm = [100, 50, 25, 10], ref_norm = [100, 50, 50, 20]
    # (after ref_max = 100 → 25/100*100 = 25; wait, max is 100 → 25 stays 25,
    # 25 normalised = 25, 50 normalised = 50 — recompute:
    # Actually: max(ref_intensities=[100,25,25,10]) = 100 → norm factors:
    # ref_norm = [100, 25, 25, 10]
    # exp_max = 100 → exp_norm = [100, 50, 25, 10]
    # I_scale LSQ = sum(exp*ref)/sum(ref^2)
    #  = (100*100 + 50*25 + 25*25 + 10*10) / (100^2 + 25^2 + 25^2 + 10^2)
    #  = (10000 + 1250 + 625 + 100) / (10000 + 625 + 625 + 100)
    #  = 11975 / 11350 ≈ 1.0551
    expected_scale = (10000.0 + 1250.0 + 625.0 + 100.0) / (
        10000.0 + 625.0 + 625.0 + 100.0
    )
    assert p["i_scale"] == pytest.approx(expected_scale, abs=1e-9)
    assert p["i_scale"] > 1.0


def test_compute_p_values_invalid_sigma_raises():
    exp_peaks, ref_peaks_d_intensity = _make_perfect_data()
    with pytest.raises(ValueError, match="sigma_pos"):
        compute_p_values(
            exp_peaks, ref_peaks_d_intensity, [], wavelength=WL, sigma_pos=0.0
        )
    with pytest.raises(ValueError, match="sigma_intensity"):
        compute_p_values(
            exp_peaks,
            ref_peaks_d_intensity,
            [],
            wavelength=WL,
            sigma_intensity=0.0,
        )


# --------------------------------------------------------------------- #
# compute_fom
# --------------------------------------------------------------------- #


def test_compute_fom_perfect_match_is_one():
    p = {
        "peakpos": 1.0,
        "intensity": 1.0,
        "npeaks": 1.0,
        "ncorr": 1.0,
        "i_scale": 1.0,
    }
    fom = compute_fom(p)
    assert fom == pytest.approx(1.0, abs=1e-12)


def test_compute_fom_zero_match_baseline():
    """All P = 0, I_scale = 1 → FoM = 1 − sum(w_i) for i = 1..4."""
    p = {
        "peakpos": 0.0,
        "intensity": 0.0,
        "npeaks": 0.0,
        "ncorr": 0.0,
        "i_scale": 1.0,
    }
    fom = compute_fom(p)
    expected = 1.0 - (
        DEFAULT_WEIGHTS.peakpos
        + DEFAULT_WEIGHTS.intensity
        + DEFAULT_WEIGHTS.npeaks
        + DEFAULT_WEIGHTS.ncorr
    )
    assert fom == pytest.approx(expected, abs=1e-12)
    # Sanity: this should be roughly 0.3155 (no I_scale penalty).
    assert 0.30 < fom < 0.33


def test_compute_fom_i_scale_penalty():
    """|ln(I_scale)| contributes w5 * |ln| to the penalty."""
    p = {
        "peakpos": 1.0,
        "intensity": 1.0,
        "npeaks": 1.0,
        "ncorr": 1.0,
        "i_scale": 2.0,
    }
    fom = compute_fom(p)
    expected = 1.0 - DEFAULT_WEIGHTS.i_scale * abs(math.log(2.0))
    assert fom == pytest.approx(expected, abs=1e-12)


def test_compute_fom_i_scale_below_one_same_penalty_as_inverse():
    """|ln(2)| == |ln(0.5)| — multiplicative symmetry."""
    p_high = {
        "peakpos": 1.0,
        "intensity": 1.0,
        "npeaks": 1.0,
        "ncorr": 1.0,
        "i_scale": 2.0,
    }
    p_low = {
        "peakpos": 1.0,
        "intensity": 1.0,
        "npeaks": 1.0,
        "ncorr": 1.0,
        "i_scale": 0.5,
    }
    assert compute_fom(p_high) == pytest.approx(compute_fom(p_low), abs=1e-12)


def test_compute_fom_custom_weights_dataclass():
    """FomWeights instance overrides defaults."""
    p = {
        "peakpos": 0.5,
        "intensity": 1.0,
        "npeaks": 1.0,
        "ncorr": 1.0,
        "i_scale": 1.0,
    }
    custom = FomWeights(
        peakpos=1.0,
        intensity=0.0,
        npeaks=0.0,
        ncorr=0.0,
        i_scale=0.0,
    )
    fom = compute_fom(p, custom)
    # FoM = 1 − 1.0 · (1 − 0.5) = 0.5
    assert fom == pytest.approx(0.5, abs=1e-12)


def test_compute_fom_custom_weights_dict_partial():
    """Partial dict fills missing keys with defaults."""
    p = {
        "peakpos": 0.5,
        "intensity": 1.0,
        "npeaks": 1.0,
        "ncorr": 1.0,
        "i_scale": 1.0,
    }
    fom = compute_fom(p, {"peakpos": 1.0})
    # peakpos weight overridden to 1.0; others stay at defaults.
    expected = (
        1.0
        - 1.0 * (1.0 - 0.5)
        - DEFAULT_WEIGHTS.intensity * (1.0 - 1.0)
        - DEFAULT_WEIGHTS.npeaks * (1.0 - 1.0)
        - DEFAULT_WEIGHTS.ncorr * (1.0 - 1.0)
        - DEFAULT_WEIGHTS.i_scale * abs(math.log(1.0))
    )
    assert fom == pytest.approx(expected, abs=1e-12)


def test_compute_fom_default_weights_arg_none():
    """Passing weights=None uses DEFAULT_WEIGHTS."""
    p = {
        "peakpos": 1.0,
        "intensity": 1.0,
        "npeaks": 1.0,
        "ncorr": 1.0,
        "i_scale": 1.0,
    }
    assert compute_fom(p, None) == pytest.approx(1.0, abs=1e-12)


def test_compute_fom_monotone_in_peakpos():
    """FoM is monotone non-decreasing in P_peakpos (others equal)."""
    base = {
        "peakpos": 0.5,
        "intensity": 0.7,
        "npeaks": 0.9,
        "ncorr": 0.8,
        "i_scale": 1.0,
    }
    fom_low = compute_fom(base)
    base_high = dict(base)
    base_high["peakpos"] = 0.9
    fom_high = compute_fom(base_high)
    assert fom_high > fom_low


# --------------------------------------------------------------------- #
# score_candidate (integration: correlate → P → FoM)
# --------------------------------------------------------------------- #


def test_score_candidate_perfect_match():
    exp_peaks, ref_peaks_d_intensity = _make_perfect_data()
    fom, p = score_candidate(exp_peaks, ref_peaks_d_intensity, wavelength=WL)
    assert fom == pytest.approx(1.0, abs=1e-9)
    assert p["peakpos"] == pytest.approx(1.0, abs=1e-9)
    assert p["intensity"] == pytest.approx(1.0, abs=1e-9)
    assert p["npeaks"] == pytest.approx(1.0, abs=1e-9)
    assert p["ncorr"] == pytest.approx(1.0, abs=1e-9)
    assert p["i_scale"] == pytest.approx(1.0, abs=1e-9)


def test_score_candidate_no_overlap_low_fom():
    """No reference peaks near experimental peaks → FoM drops to baseline."""
    exp_peaks = [
        Peak(two_theta=10.0, intensity=100.0),
        Peak(two_theta=20.0, intensity=50.0),
    ]
    ref_peaks_d_intensity = [
        (_d_from_two_theta(60.0), 100.0),
        (_d_from_two_theta(70.0), 50.0),
    ]
    fom, _ = score_candidate(exp_peaks, ref_peaks_d_intensity, wavelength=WL)
    expected = 1.0 - (
        DEFAULT_WEIGHTS.peakpos
        + DEFAULT_WEIGHTS.intensity
        + DEFAULT_WEIGHTS.npeaks
        + DEFAULT_WEIGHTS.ncorr
    )
    assert fom == pytest.approx(expected, abs=1e-9)


def test_score_candidate_partial_match_high_fom_below_one():
    """Most peaks match → FoM close to 1 but strictly less."""
    exp_peaks = [
        Peak(two_theta=10.0, intensity=100.0),
        Peak(two_theta=20.0, intensity=50.0),
        Peak(two_theta=30.0, intensity=25.0),
        Peak(two_theta=80.0, intensity=10.0),  # no ref counterpart
    ]
    ref_ds = [
        _d_from_two_theta(10.0),
        _d_from_two_theta(20.0),
        _d_from_two_theta(30.0),
    ]
    ref_peaks_d_intensity = list(
        zip(ref_ds, [100.0, 50.0, 25.0], strict=True)
    )
    fom, p = score_candidate(exp_peaks, ref_peaks_d_intensity, wavelength=WL)
    assert 0.8 < fom < 1.0
    assert p["npeaks"] == pytest.approx(0.75, abs=1e-9)
    assert p["ncorr"] == pytest.approx(1.0, abs=1e-9)


def test_score_candidate_custom_weights():
    """Custom weights propagate through score_candidate."""
    exp_peaks, ref_peaks_d_intensity = _make_perfect_data()
    custom = FomWeights(
        peakpos=1.0,
        intensity=0.0,
        npeaks=0.0,
        ncorr=0.0,
        i_scale=0.0,
    )
    fom, _ = score_candidate(
        exp_peaks, ref_peaks_d_intensity, wavelength=WL, weights=custom
    )
    # Perfect match → all P = 1, I_scale = 1 → FoM = 1 regardless of weights.
    assert fom == pytest.approx(1.0, abs=1e-9)


def test_score_candidate_dict_weights():
    exp_peaks, ref_peaks_d_intensity = _make_perfect_data()
    fom, _ = score_candidate(
        exp_peaks, ref_peaks_d_intensity, wavelength=WL, weights={"peakpos": 0.5}
    )
    # Perfect match → FoM = 1 (all P = 1, ln(1) = 0).
    assert fom == pytest.approx(1.0, abs=1e-9)


def test_score_candidate_hungarian_method():
    """Hungarian method path works in the integrated scorer."""
    exp_peaks, ref_peaks_d_intensity = _make_perfect_data()
    fom, p = score_candidate(
        exp_peaks, ref_peaks_d_intensity, wavelength=WL, method="hungarian"
    )
    assert fom == pytest.approx(1.0, abs=1e-9)
    assert p["peakpos"] == pytest.approx(1.0, abs=1e-9)


def test_score_candidate_perfect_match_outranks_partial():
    """Sanity: FoM ordering reflects match quality."""
    exp_peaks, ref_perfect = _make_perfect_data()
    fom_perfect, _ = score_candidate(exp_peaks, ref_perfect, wavelength=WL)

    # Build a worse reference: same 2θ but scrambled intensities.
    ref_ds = [_d_from_two_theta(tt) for tt in [10.0, 20.0, 30.0, 40.0]]
    ref_bad = list(zip(ref_ds, [10.0, 25.0, 50.0, 100.0], strict=True))  # reversed
    fom_bad, _ = score_candidate(exp_peaks, ref_bad, wavelength=WL)

    assert fom_perfect > fom_bad


def test_score_candidate_returns_dict_with_all_keys():
    exp_peaks, ref_peaks_d_intensity = _make_perfect_data()
    _, p = score_candidate(exp_peaks, ref_peaks_d_intensity, wavelength=WL)
    assert set(p.keys()) == {"peakpos", "intensity", "npeaks", "ncorr", "i_scale"}
