"""Internal-standard quantitative phase analysis (T8.2).

Implements the *spiking* / *internal-standard* method, in which a known
mass fraction of a reference phase (the internal standard) is added to the
sample and the weight fractions of all other phases are back-calculated
from their main-peak intensities relative to the standard.

The core equation (see e.g. Klug & Alexander [1], eq. 7-16; and the
matrix-flushing formulation of Chung [2]) is:

.. math::

    W_x = \\frac{I_x}{I_s}\\,\\frac{\\mathrm{RIR}_s}{\\mathrm{RIR}_x}\\,W_s

where *I* is the integrated (profile-fitted) intensity of the strongest
non-overlapped peak, *W* is the weight fraction, subscripts *x* and *s*
denote phase *x* and the internal standard, and ``RIR`` is the Reference
Intensity Ratio (I/Ic relative to corundum).  When the standard is corundum
itself, ``RIR_s = 1``.

The method yields *absolute* weight fractions: if the sum of all
crystalline phases is less than 1.0, the missing fraction is attributed to
amorphous / undetected material (``assign_residual_to_amorphous=True``).

This module takes already-decomposed per-phase intensities — it does not
perform profile fitting itself.  The companion :func:`extract_intensities`
helper integrates peak areas around expected positions for end-to-end
validation on real patterns.

References
----------
[1] H.P. Klug, L.E. Alexander, *X-ray Diffraction Procedures for
    Polycrystalline and Amorphous Materials*, 2nd ed., Wiley, 1974.
[2] F.H. Chung, "Quantitative Interpretation of X-ray Diffraction
    Patterns of Mixtures. I. Matrix-Flushing Method",
    J. Appl. Cryst. 7 (1974), 519-525.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from xinmatch.core.model import Pattern


@dataclass
class QuantResult:
    """Internal-standard quantitative result.

    Attributes
    ----------
    weight_fractions:
        Mapping ``{phase_name: weight fraction in [0, 1]}`` for every
        crystalline phase (including the standard).  Values sum to
        ``<= 1.0``; the remainder is the amorphous fraction when
        ``assign_residual_to_amorphous`` was set.
    uncertainties:
        Mapping ``{phase_name: 1-σ uncertainty (weight fraction)}``.
        Zero when no intensity uncertainties were supplied.
    internal_standard:
        Name of the internal standard phase.
    standard_known_wt_fraction:
        Known weight fraction of the standard (user input).
    standard_recovery:
        Fraction of the sample accounted for by crystalline phases,
        i.e. ``sum(weight_fractions)``.  ~1.0 when no amorphous is
        present; < 1.0 signals amorphous content.
    amorphous_fraction:
        Amorphous weight fraction when
        ``assign_residual_to_amorphous=True``; otherwise ``None``.
    amorphous_name:
        Label used for the amorphous phase (``"amorphous"`` by default).
    """

    weight_fractions: dict[str, float]
    uncertainties: dict[str, float]
    internal_standard: str
    standard_known_wt_fraction: float
    standard_recovery: float
    amorphous_fraction: float | None = None
    amorphous_name: str = "amorphous"


def internal_standard_quantify(
    intensity_by_phase: dict[str, float],
    rir_values: dict[str, float],
    standard_phase: str,
    standard_wt_fraction: float,
    *,
    intensity_uncertainties: dict[str, float] | None = None,
    assign_residual_to_amorphous: bool = False,
    amorphous_name: str = "amorphous",
) -> QuantResult:
    """Compute absolute weight fractions via the internal-standard method.

    Parameters
    ----------
    intensity_by_phase:
        Mapping ``{phase_name: integrated main-peak intensity}`` for each
        phase present, including the internal standard.  Intensities must
        already be overlap-decomposed (this function does not profile-fit).
    rir_values:
        Mapping ``{phase_name: RIR (I/Ic)}`` for every phase in
        ``intensity_by_phase``.
    standard_phase:
        Name of the internal standard phase.  Must be a key in both
        input mappings.
    standard_wt_fraction:
        Known weight fraction of the internal standard in ``[0, 1]``.
    intensity_uncertainties:
        Optional mapping ``{phase_name: 1-σ intensity uncertainty}``.
        Used for uncertainty propagation on the weight fractions.  If
        ``None`` (default) the returned uncertainties are zero.
    assign_residual_to_amorphous:
        If ``True``, the residual ``1 - sum(crystalline)`` is assigned to
        an amorphous phase and reported in ``amorphous_fraction``.
        Negative residuals (sum > 1, possible from measurement noise) are
        clamped to zero.
    amorphous_name:
        Label for the amorphous phase (default ``"amorphous"``).

    Returns
    -------
    QuantResult
        Weight fractions (including the standard), uncertainties,
        recovery and (optionally) amorphous fraction.

    Raises
    ------
    ValueError
        If inputs are empty, the standard phase is missing, an RIR value
        is missing or non-positive, the standard weight is out of range,
        or the standard intensity is zero.
    """
    if not intensity_by_phase:
        raise ValueError("intensity_by_phase must not be empty")
    if not rir_values:
        raise ValueError("rir_values must not be empty")
    if standard_phase not in intensity_by_phase:
        raise ValueError(
            f"standard phase {standard_phase!r} not in intensity_by_phase"
        )
    if standard_phase not in rir_values:
        raise ValueError(
            f"standard phase {standard_phase!r} not in rir_values"
        )
    if not 0.0 < standard_wt_fraction <= 1.0:
        raise ValueError(
            f"standard_wt_fraction must be in (0, 1], got {standard_wt_fraction}"
        )

    missing = [p for p in intensity_by_phase if p not in rir_values]
    if missing:
        raise ValueError(
            f"RIR value missing for phase(s): {', '.join(missing)}"
        )

    bad_rir = [p for p, v in rir_values.items() if v <= 0]
    if bad_rir:
        raise ValueError(
            f"RIR values must be positive; got non-positive for: "
            f"{', '.join(bad_rir)}"
        )

    i_std = intensity_by_phase[standard_phase]
    if i_std <= 0:
        raise ValueError(
            f"standard phase intensity must be positive, got {i_std}"
        )

    rir_std = rir_values[standard_phase]

    weight_fractions: dict[str, float] = {}
    uncertainties: dict[str, float] = {}

    for phase, i_x in intensity_by_phase.items():
        if phase == standard_phase:
            w = standard_wt_fraction
        else:
            rir_x = rir_values[phase]
            w = (i_x / i_std) * (rir_std / rir_x) * standard_wt_fraction
        weight_fractions[phase] = w

        # Uncertainty propagation:
        # δw_x = w_x * sqrt((δI_x / I_x)² + (δI_std / I_std)²)
        if intensity_uncertainties and phase in intensity_uncertainties:
            di_x = intensity_uncertainties[phase]
            di_std = intensity_uncertainties.get(standard_phase, 0.0)
            if i_x > 0 and i_std > 0:
                rel = np.sqrt((di_x / i_x) ** 2 + (di_std / i_std) ** 2)
                uncertainties[phase] = w * rel
            else:
                uncertainties[phase] = 0.0
        else:
            uncertainties[phase] = 0.0

    total_crystalline = sum(weight_fractions.values())
    recovery = total_crystalline

    amorphous_fraction: float | None = None
    if assign_residual_to_amorphous:
        amorphous_fraction = max(0.0, 1.0 - recovery)
        weight_fractions[amorphous_name] = amorphous_fraction
        uncertainties[amorphous_name] = 0.0

    return QuantResult(
        weight_fractions=weight_fractions,
        uncertainties=uncertainties,
        internal_standard=standard_phase,
        standard_known_wt_fraction=standard_wt_fraction,
        standard_recovery=recovery,
        amorphous_fraction=amorphous_fraction,
        amorphous_name=amorphous_name,
    )


# ---------------------------------------------------------------------------
# Intensity extraction helper (for end-to-end validation on real patterns)
# ---------------------------------------------------------------------------

def extract_intensities(
    pattern: Pattern,
    phase_peak_positions: dict[str, float],
    *,
    window_deg: float = 1.0,
    background_method: str = "snip",
    background_window: int = 20,
) -> dict[str, float]:
    """Extract integrated main-peak intensities from a pattern.

    A pragmatic alternative to full profile fitting for end-to-end
    validation: for each phase the intensity is integrated (sum × step)
    over a ``±window_deg`` 2θ window around the expected peak position,
    after SNIP background subtraction.

    Parameters
    ----------
    pattern:
        Background-raw diffraction pattern.
    phase_peak_positions:
        Mapping ``{phase_name: expected 2θ of strongest peak}``.
    window_deg:
        Half-width of the integration window in degrees 2θ.
    background_method:
        Background method passed to
        :func:`xinmatch.core.preprocess.background.estimate_background`.
    background_window:
        SNIP window size (points).

    Returns
    -------
    dict[str, float]
        Mapping ``{phase_name: integrated peak intensity}``.
    """
    from xinmatch.core.preprocess.background import (
        estimate_background,
        subtract_background,
    )

    two_theta = pattern.two_theta
    intensity = pattern.intensity
    bg = estimate_background(
        two_theta,
        intensity,
        method=background_method,
        window=background_window,
    )
    net = subtract_background(intensity, bg)

    step = pattern.step or float(np.median(np.diff(two_theta)))
    result: dict[str, float] = {}
    for phase, pos in phase_peak_positions.items():
        mask = (two_theta >= pos - window_deg) & (two_theta <= pos + window_deg)
        result[phase] = float(np.sum(net[mask]) * step)
    return result


def quantify_from_pattern(
    pattern: Pattern,
    phase_peak_positions: dict[str, float],
    rir_values: dict[str, float],
    standard_phase: str,
    standard_wt_fraction: float,
    *,
    window_deg: float = 1.0,
    assign_residual_to_amorphous: bool = False,
) -> QuantResult:
    """End-to-end convenience: extract intensities then quantify.

    Combines :func:`extract_intensities` and
    :func:`internal_standard_quantify` in one call.  See those functions
    for parameter descriptions.
    """
    intensities = extract_intensities(
        pattern, phase_peak_positions, window_deg=window_deg
    )
    return internal_standard_quantify(
        intensities,
        rir_values,
        standard_phase,
        standard_wt_fraction,
        assign_residual_to_amorphous=assign_residual_to_amorphous,
    )
