"""RIR (Reference Intensity Ratio) quantitative phase analysis.

Implements the algebraic core of the RIR method presented by de Wolff and
Visser [1], as used by Match!'s (semi-)quantitative analysis when at least
two entries are selected as matching (see ``docs/quant_analysis_RIR.md``).

The functions here take already-decomposed per-phase main-peak intensities
and compute weight fractions.  The least-squares intensity scale-factor
refinement that Match! uses to *obtain* those per-phase intensities from
overlapping peaks in the mixed pattern is part of profile fitting /
Rietveld refinement and is out of scope for this module.

Two formulations are supported:

* **Adiabatic** (Hill-Howard, ``reference_phase=None``): assumes *all*
  crystalline phases are accounted for (no amorphous, no missing phase):

  .. math::
      W_i = (I_i / \\mathrm{RIR}_i) /
            \\sum_j (I_j / \\mathrm{RIR}_j)

* **Reference-relative** (``reference_phase`` set): the named phase is
  treated as the corundum-like standard; its main-peak intensity is
  :math:`I_c`.  Expressing the same Hill-Howard equation with explicit
  reference to the standard:

  .. math::
      W_i = (I_i / (I_c\\, \\mathrm{RIR}_i)) /
            \\sum_j (I_j / (I_c\\, \\mathrm{RIR}_j))

  The :math:`I_c` factors cancel, so the result is numerically identical
  to the adiabatic form when the reference phase is one of the mixture
  phases (i.e. when no external standard weight is supplied).  The
  parameter is retained for API symmetry with Match!'s reference-method
  option and to validate that the declared reference phase is present
  in the input.

References
----------
[1] P.M. de Wolff, J.W. Visser, "Absolute intensities",
    Rep. 641.109 Technische Physische Dienst, Delft 1964.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from xinmatch.core.model import Peak


def rir_quantify(
    pattern_intensity_by_phase: dict[str, float],
    rir_values: dict[str, float],
    *,
    reference_phase: str | None = None,
) -> dict[str, float]:
    """Compute weight fractions (wt fraction, sums to 1.0) via the RIR method.

    Parameters
    ----------
    pattern_intensity_by_phase:
        Mapping ``{phase_name: main-peak intensity}`` for each phase present
        in the mixture.  Intensities must already be decomposed
        (overlap-resolved) — this function does *not* perform peak
        decomposition.
    rir_values:
        Mapping ``{phase_name: RIR (I/Ic) value}`` for each phase.  Must
        contain at least every key in ``pattern_intensity_by_phase``.
    reference_phase:
        Optional name of the reference phase (e.g. ``"corundum"``).
        ``None`` (default) selects the adiabatic method; otherwise the
        reference-relative method is used.  If set, the value must be a
        key in both input mappings.

    Returns
    -------
    dict[str, float]
        Mapping ``{phase_name: weight fraction}`` with values in ``[0, 1]``
        summing to 1.0.

    Raises
    ------
    ValueError
        If inputs are empty, an RIR value is missing for a phase, the
        reference phase is unknown, an RIR value is non-positive, or the
        total intensity is zero (degenerate input).
    """
    if not pattern_intensity_by_phase:
        raise ValueError("pattern_intensity_by_phase must not be empty")
    if not rir_values:
        raise ValueError("rir_values must not be empty")

    missing = [p for p in pattern_intensity_by_phase if p not in rir_values]
    if missing:
        raise ValueError(
            f"RIR value missing for phase(s): {', '.join(missing)}"
        )

    if reference_phase is not None:
        if reference_phase not in pattern_intensity_by_phase:
            raise ValueError(
                f"reference phase {reference_phase!r} not in "
                f"pattern_intensity_by_phase"
            )
        if reference_phase not in rir_values:
            raise ValueError(
                f"reference phase {reference_phase!r} not in rir_values"
            )

    bad_rir = [p for p, v in rir_values.items() if v <= 0]
    if bad_rir:
        raise ValueError(
            f"RIR values must be positive; got non-positive for: "
            f"{', '.join(bad_rir)}"
        )

    # Hill-Howard ratios: I_i / RIR_i.  In the reference-relative form the
    # extra I_c factor cancels between numerator and denominator, so the
    # numeric result is identical; we therefore use a single computation.
    ratios = {
        p: pattern_intensity_by_phase[p] / rir_values[p]
        for p in pattern_intensity_by_phase
    }

    total = sum(ratios.values())
    if total <= 0:
        raise ValueError(
            "total intensity is zero — cannot normalize "
            "(all main-peak intensities are zero)"
        )

    return {p: r / total for p, r in ratios.items()}


def compute_rir_from_pure_pattern(
    pure_pattern_peaks: Sequence[Peak],
    phase_name: str,
    wavelength_angstrom: float,
    *,
    reference: str = "corundum",
    reference_intensity: float = 100.0,
) -> float:
    """Estimate the RIR (I/Ic) value from a pure-phase diffraction pattern.

    Implements the simplified *experimental* RIR determination: with the
    corundum main peak normalized to ``I_c = 100`` (a common convention),
    the RIR of phase *i* equals the intensity of its strongest peak in
    counts measured under identical conditions.

    Parameters
    ----------
    pure_pattern_peaks:
        Peak list of the pure-phase standard (e.g. from profile fitting of
        the pure-phase diffraction pattern).
    phase_name:
        Name of the phase — used for error messages only.
    wavelength_angstrom:
        Wavelength (Å) used to measure the pattern.  Reserved for a future
        implementation that computes RIR from crystal-structure (CIF) data;
        currently unused.
    reference:
        Reference label (default ``"corundum"``).  Reserved for future use;
        currently only the corundum convention is implemented.
    reference_intensity:
        Main-peak intensity of the reference (corundum) standard measured
        under the same conditions.  Defaults to ``100.0``.

    Returns
    -------
    float
        The RIR value (``I_i / I_c``), i.e. the ratio of the phase's
        strongest peak intensity to the corundum main-peak intensity.

    Raises
    ------
    ValueError
        If the peak list is empty, the strongest intensity is non-positive,
        or the reference intensity is non-positive.

    Notes
    -----
    This is the *simplified* RIR determination described in the Match!
    documentation.  The full method (computing I/Ic from crystal-structure
    data imported from a CIF file) is not implemented here.
    """
    if not pure_pattern_peaks:
        raise ValueError(
            f"pure_pattern_peaks is empty for phase {phase_name!r}"
        )
    if reference_intensity <= 0:
        raise ValueError(
            f"reference_intensity must be positive, got {reference_intensity}"
        )

    i_strongest = max(p.intensity for p in pure_pattern_peaks)
    if i_strongest <= 0:
        raise ValueError(
            f"strongest peak intensity for phase {phase_name!r} is "
            f"non-positive ({i_strongest}); cannot compute RIR"
        )

    return i_strongest / reference_intensity


@dataclass
class RirResult:
    """Detailed RIR quantitative result for a single phase.

    Parameters
    ----------
    phase:
        Phase name.
    weight_fraction:
        Computed weight fraction in ``[0, 1]``.
    rir:
        The phase's RIR (I/Ic) value used in the calculation.
    peak_intensity:
        The phase's main-peak intensity in the mixed pattern.
    """

    phase: str
    weight_fraction: float
    rir: float
    peak_intensity: float


def rir_quantify_detailed(
    pattern_intensity_by_phase: dict[str, float],
    rir_values: dict[str, float],
    *,
    reference_phase: str | None = None,
) -> list[RirResult]:
    """Like :func:`rir_quantify` but returns a detailed :class:`RirResult` list.

    Parameters
    ----------
    As for :func:`rir_quantify`.

    Returns
    -------
    list[RirResult]
        One :class:`RirResult` per phase, in input-dict insertion order.
    """
    weights = rir_quantify(
        pattern_intensity_by_phase,
        rir_values,
        reference_phase=reference_phase,
    )
    return [
        RirResult(
            phase=p,
            weight_fraction=weights[p],
            rir=rir_values[p],
            peak_intensity=pattern_intensity_by_phase[p],
        )
        for p in pattern_intensity_by_phase
    ]
