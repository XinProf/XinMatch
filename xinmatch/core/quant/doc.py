"""Degree of Crystallinity (DOC) / amorphous-content analysis (T8.4).

Implements the reference software's *Degree of Crystallinity* (Quantify menu), see
``docs/doc.md``.  The method separates the total scattered intensity into
a crystalline part (sharp Bragg peaks) and an amorphous part (broad halo)
and reports the weight fraction of the amorphous phase.

Algorithm
---------
A SNIP background pass and a morphological opening are combined to
decompose the pattern into three components (see Hermans & Weidinger [1]):

1. **Coarse background** — SNIP with a *large* window (default
   ``len(two_theta) // 4``) captures the slowly-varying true background
   (air scatter, Bremsstrahlung, detector dark).  This is a near-flat
   baseline.
2. **Morphological opening** — A grey-scale morphological opening
   (erosion followed by dilation) with a structuring element of width
   ``2 * fine_window + 1`` points is applied to the baseline-subtracted
   residual.  The opening removes features narrower than the structuring
   element (sharp crystalline peaks, FWHM ≲ 0.5°) while preserving broader
   features (the amorphous halo, FWHM ≳ 5°).

From these two passes:

* ``A_crystalline = Σ (residual − halo) × step`` — area of sharp peaks
* ``A_amorphous   = Σ halo × step``             — area of the halo
* ``DOC = A_crystalline / (A_crystalline + A_amorphous) × 100 %``

The pattern is lightly Savitzky–Golay smoothed before processing to reduce
the impact of counting noise on the morphological opening (noise spikes
would otherwise be retained as spurious "crystalline" area).

If an internal standard with a known weight fraction is provided, the
absolute amorphous weight percent is obtained from the mass balance
instead of the area ratio (which corrects for differences in scattering
power between crystalline and amorphous phases):

    ``W_amorphous = 1 − Σ W_crystalline``

References
----------
[1] P.H. Hermans, A. Weidinger, "Quantitative X-ray investigation of the
    crystallinity and crystallite size in cellulose fibers",
    *J. Appl. Phys.* **19** (1948), 491-506.
[2] C.G. Ryan et al., "SNIP, a statistics-sensitive background treatment",
    *Nucl. Instrum. Methods* **B34** (1988), 396-406.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.ndimage import grey_opening
from scipy.signal import savgol_filter

from xinmatch.core.model import Pattern
from xinmatch.core.preprocess.background import estimate_background


@dataclass
class DOCResult:
    """Degree-of-crystallinity result.

    Attributes
    ----------
    doc_percent:
        Degree of crystallinity in ``[0, 100]`` — crystalline area /
        total area × 100.
    amorphous_wt_percent:
        Amorphous weight percent in ``[0, 100]``.  When no internal
        standard is supplied this is ``100 − DOC``; when an internal
        standard is supplied it is the mass-balance value
        ``100 − Σ(crystalline wt%)``.
    crystalline_wt_fractions:
        Mapping ``{phase_name: weight fraction in [0, 1]}`` for each
        crystalline phase.  Only populated when the internal-standard
        method is used; otherwise empty.
    crystalline_area:
        Integrated area of the crystalline peaks (counts × deg).
    amorphous_area:
        Integrated area of the amorphous halo (counts × deg).
    total_area:
        ``crystalline_area + amorphous_area``.
    """

    doc_percent: float
    amorphous_wt_percent: float
    crystalline_wt_fractions: dict[str, float] = field(default_factory=dict)
    crystalline_area: float = 0.0
    amorphous_area: float = 0.0
    total_area: float = 0.0


def degree_of_crystallinity(
    two_theta: np.ndarray,
    intensity: np.ndarray,
    *,
    coarse_window: int | None = None,
    fine_window: int | None = None,
    smooth_window: int = 11,
    step: float | None = None,
) -> DOCResult:
    """Compute the degree of crystallinity (DOC) from a pattern.

    Uses the SNIP + morphological-opening decomposition described in the
    module docstring.  No internal standard — the amorphous wt% is
    inferred from the area ratio (``100 − DOC``).

    Parameters
    ----------
    two_theta:
        1-D array of scattering angles (degrees 2θ).
    intensity:
        1-D array of diffraction intensities.
    coarse_window:
        SNIP half-window (points) for the coarse (true background)
        pass.  Should be **wider than the amorphous halo** so that the
        halo is captured together with the sharp peaks, leaving only
        the slowly-varying baseline.  If ``None`` (default) it is set
        to ``len(two_theta) // 4`` — one quarter of the pattern,
        typically large enough for broad halos (5–15° FWHM).
    fine_window:
        Half-width of the morphological-opening structuring element
        (points).  Should be wider than the crystalline-peak FWHM but
        narrower than the amorphous-halo FWHM.  If ``None`` (default)
        it is set to ``round(1.5 / step)`` — about 1.5° wide, which
        comfortably brackets typical crystalline peaks (0.1–0.5° FWHM)
        while preserving broad halos (5–15° FWHM).
    smooth_window:
        Savitzky–Golay smoothing window (points, odd).  Set to ``0``
        or ``1`` to disable smoothing.  Default 11.
    step:
        Step width in degrees 2θ.  If ``None`` it is inferred from
        ``two_theta``.

    Returns
    -------
    DOCResult
    """
    two_theta = np.asarray(two_theta, dtype=np.float64)
    intensity = np.asarray(intensity, dtype=np.float64)
    if step is None:
        step = float(np.median(np.diff(two_theta))) if two_theta.size > 1 else 1.0

    if coarse_window is None:
        # Default to one quarter of the pattern — wide enough to bracket
        # broad amorphous halos (5–15° FWHM) so the halo is treated as
        # background + halo, leaving the sharp crystalline peaks above.
        coarse_window = max(two_theta.size // 4, 100)

    if fine_window is None:
        # Structuring element ~1.5° wide: large enough to remove sharp
        # crystalline peaks (FWHM 0.1–0.5°) but small enough to preserve
        # broad amorphous halos (FWHM 5–15°).
        fine_window = max(int(round(1.5 / step)), 20)

    # Light Savitzky–Golay smoothing to reduce the impact of counting
    # noise on the morphological opening (noise spikes would otherwise
    # be retained as spurious "crystalline" area).
    y = intensity
    if smooth_window and smooth_window > 1 and y.size >= 5:
        sw = int(smooth_window)
        if sw % 2 == 0:
            sw += 1
        sw = min(sw, y.size if y.size % 2 == 1 else y.size - 1)
        if sw >= 5:
            y = savgol_filter(y, sw, 3)

    # Coarse background: SNIP with large window → slowly-varying baseline.
    coarse_bg = estimate_background(
        two_theta, y, method="snip", window=coarse_window
    )
    # Residual above baseline = halo + sharp peaks.
    residual = np.maximum(y - coarse_bg, 0.0)

    # Fine: morphological opening of the residual.  Opening = erosion
    # (local minimum) followed by dilation (local maximum) with a flat
    # structuring element of width 2*fine_window+1.  This removes features
    # narrower than the structuring element (sharp crystalline peaks) while
    # preserving broader features (the amorphous halo).
    size = 2 * fine_window + 1
    halo = grey_opening(residual, size=size, mode="nearest")

    # Crystalline area = residual above the halo (sharp peaks).
    crystalline = np.maximum(residual - halo, 0.0)
    a_cryst = float(np.sum(crystalline) * step)

    # Amorphous area = the halo itself.
    amorphous = np.maximum(halo, 0.0)
    a_amorph = float(np.sum(amorphous) * step)

    total = a_cryst + a_amorph
    doc = 100.0 if total <= 0 else a_cryst / total * 100.0

    amorphous_wt = 100.0 - doc

    return DOCResult(
        doc_percent=doc,
        amorphous_wt_percent=amorphous_wt,
        crystalline_area=a_cryst,
        amorphous_area=a_amorph,
        total_area=total,
    )


def doc_with_internal_standard(
    pattern: Pattern,
    phase_peak_positions: dict[str, float],
    rir_values: dict[str, float],
    standard_phase: str,
    standard_wt_fraction: float,
    *,
    window_deg: float = 0.5,
    coarse_window: int | None = None,
    fine_window: int | None = None,
    smooth_window: int = 11,
) -> DOCResult:
    """Compute DOC with an internal standard for absolute amorphous wt%.

    Combines the area-based DOC with the internal-standard quantitative
    method: the crystalline phases' weight fractions are computed via
    :func:`~xinmatch.core.quant.internal_standard.internal_standard_quantify`,
    and the amorphous weight percent is obtained from the mass balance
    ``100% − Σ(crystalline wt%)``.

    Parameters
    ----------
    pattern:
        Raw diffraction pattern.
    phase_peak_positions:
        Mapping ``{phase_name: expected 2θ of main peak}`` for every
        crystalline phase (including the standard).
    rir_values:
        Mapping ``{phase_name: RIR (I/Ic)}``.
    standard_phase:
        Name of the internal standard phase.
    standard_wt_fraction:
        Known weight fraction of the standard.
    window_deg:
        Half-width of the intensity-extraction window (degrees 2θ).
    coarse_window, fine_window, smooth_window:
        Background / opening parameters for the DOC area calculation
        (see :func:`degree_of_crystallinity`).

    Returns
    -------
    DOCResult
        ``doc_percent`` and area values from the area-based method;
        ``amorphous_wt_percent`` and ``crystalline_wt_fractions`` from
        the internal-standard mass balance.
    """
    from xinmatch.core.quant.internal_standard import (
        extract_intensities,
        internal_standard_quantify,
    )

    # Area-based DOC.
    area_result = degree_of_crystallinity(
        pattern.two_theta,
        pattern.intensity,
        coarse_window=coarse_window,
        fine_window=fine_window,
        smooth_window=smooth_window,
        step=pattern.step,
    )

    # Internal-standard quantification for absolute wt%.
    intensities = extract_intensities(
        pattern, phase_peak_positions, window_deg=window_deg
    )
    quant = internal_standard_quantify(
        intensities,
        rir_values,
        standard_phase,
        standard_wt_fraction,
        assign_residual_to_amorphous=True,
    )

    crystalline_wt = {
        p: w for p, w in quant.weight_fractions.items()
        if p != quant.amorphous_name
    }
    amorphous_wt = quant.amorphous_fraction or 0.0

    return DOCResult(
        doc_percent=area_result.doc_percent,
        amorphous_wt_percent=amorphous_wt * 100.0,
        crystalline_wt_fractions=crystalline_wt,
        crystalline_area=area_result.crystalline_area,
        amorphous_area=area_result.amorphous_area,
        total_area=area_result.total_area,
    )
