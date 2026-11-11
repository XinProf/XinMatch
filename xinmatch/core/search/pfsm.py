"""Profile-fitting search-match (PFSM) FoM (Phase 6 / T6.6).

PFSM is the reference software's full-spectrum alternative to peak-based search-match
(available since the reference software).  Instead of correlating individual peaks,
PFSM calculates a full diffraction profile for each candidate entry,
fits an intensity scale factor and a global 2θ shift against the
experimental profile, and ranks candidates by the resulting goodness of
fit (Rwp reduction).

The background is **not** refined (the reference software requires it to be set
correctly beforehand), and no structural parameters are touched — this
is profile fitting, not Rietveld refinement.

The reference software feature: *Search → Profile-fitting search-match*.  See
``docs/fpfm_mechanism.md`` for the full FPFM design (this module is the
lightweight scale+shift reference used as a compatibility layer; the full
candidate pre-screen + profile-fitting pipeline lives in
:mod:`xinmatch.core.search.fpfm`).

Algorithm source: the reference software PFSM documentation (profile fitting of each
candidate's calculated pattern to the experimental profile, ranking by
Rwp reduction).  The Rwp goodness-of-fit metric is the standard
Rietveld / full-pattern fit criterion (Young, ``The Rietveld Method``,
Chap. 4).
"""

from __future__ import annotations

import numpy as np

from xinmatch.core.model import Entry, Pattern
from xinmatch.core.peak.shapes import pseudo_voigt

__all__ = [
    "compute_reference_pattern",
    "fit_scale_shift",
    "compute_rwp",
    "pfsm_score",
    "pfsm_rank",
]


# --------------------------------------------------------------------------- #
# Reference pattern generation
# --------------------------------------------------------------------------- #
def compute_reference_pattern(
    entry: Entry,
    wavelength: float,
    two_theta_range: tuple[float, float] = (5.0, 90.0),
    *,
    step: float = 0.02,
    fwhm: float = 0.1,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate a reference powder pattern from an entry's d–I table.

    Each ``(d, I)`` reflection is converted to 2θ via Bragg's law and
    rendered as a pseudo-Voigt peak (FWHM fixed at *fwhm* degrees,
    ``η = 0.5``) on a uniform 2θ grid.  The peak area is set to the
    entry's relative intensity, so the integrated intensity of each
    reflection is preserved.

    The reference software feature: the "profile calculated from reference database
    entries" used by PFSM.  the reference software uses the IL (Intermediate
    Lorentzian) profile internally; pseudo-Voigt is used here as the
    standard analytical approximation available in
    :mod:`xinmatch.core.peak.shapes`.

    Parameters
    ----------
    entry:
        Reference database entry carrying a d–I table.
    wavelength:
        Radiation wavelength in Å.
    two_theta_range:
        ``(low, high)`` 2θ range in degrees.
    step:
        2θ grid step in degrees.
    fwhm:
        Peak full width at half maximum in degrees 2θ (default 0.1°).

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        ``(two_theta, intensity)`` arrays on the requested grid.
    """
    lo, hi = two_theta_range
    two_theta = np.arange(lo, hi + step * 0.5, step, dtype=np.float64)
    intensity = np.zeros_like(two_theta)
    if entry.n_peaks == 0:
        return two_theta, intensity
    sin_theta = wavelength / (2.0 * entry.d_spacings)
    # d-spacings outside the Bragg range give |sin| > 1 → skip.
    valid = (sin_theta >= -1.0) & (sin_theta <= 1.0)
    ds = entry.d_spacings[valid]
    ints = entry.intensities[valid]
    if ds.size == 0:
        return two_theta, intensity
    tt = 2.0 * np.degrees(np.arcsin(sin_theta[valid]))
    in_range = (tt >= lo) & (tt <= hi)
    tt = tt[in_range]
    ints = ints[in_range]
    for center, amp in zip(tt, ints, strict=True):
        intensity += pseudo_voigt(two_theta, float(center), fwhm, float(amp))
    return two_theta, intensity


# --------------------------------------------------------------------------- #
# Scale + 2θ shift fitting
# --------------------------------------------------------------------------- #
def fit_scale_shift(
    two_theta: np.ndarray,
    pattern_intensity: np.ndarray,
    reference_intensity: np.ndarray,
    *,
    initial_scale: float = 1.0,
    initial_shift: float = 0.0,
    shift_bound: float = 1.0,
) -> tuple[float, float]:
    """Fit an intensity scale factor and a global 2θ shift.

    Minimises the weighted least-squares residual between
    ``pattern_intensity`` and ``scale · reference(2θ − shift)`` using
    :func:`scipy.optimize.minimize` (Nelder–Mead, derivative-free).

    The 2θ shift is applied by linearly interpolating the reference
    profile onto the shifted grid; points outside the reference support
    are filled with zero.

    The reference software feature: PFSM refines "the intensity scale factor as well as
    the 2theta shift" for each candidate (see ``docs/fpfm_mechanism.md``).

    Parameters
    ----------
    two_theta:
        2θ grid (degrees) shared by *pattern_intensity* and
        *reference_intensity*.
    pattern_intensity:
        Experimental (or target) intensity array.
    reference_intensity:
        Reference intensity array on the same grid.
    initial_scale:
        Starting value for the intensity scale factor.
    initial_shift:
        Starting value for the 2θ shift in degrees.
    shift_bound:
        Symmetric bound ``[−shift_bound, +shift_bound]`` on the fitted
        2θ shift in degrees.

    Returns
    -------
    tuple[float, float]
        ``(scale, shift_deg)``.
    """
    two_theta = np.asarray(two_theta, dtype=np.float64)
    y = np.asarray(pattern_intensity, dtype=np.float64)
    ref = np.asarray(reference_intensity, dtype=np.float64)

    def shifted_reference(shift: float) -> np.ndarray:
        return np.interp(
            two_theta - shift,
            two_theta,
            ref,
            left=0.0,
            right=0.0,
        )

    def objective(params: np.ndarray) -> float:
        scale, shift = params
        fitted = scale * shifted_reference(float(shift))
        return float(np.sum((y - fitted) ** 2))

    # 延迟导入：只在真的做 Nelder-Mead 拟合时才拉 scipy.optimize。
    from scipy.optimize import minimize

    res = minimize(
        objective,
        np.array([initial_scale, initial_shift], dtype=np.float64),
        method="Nelder-Mead",
        options={"xatol": 1e-4, "fatol": 1e-6, "maxiter": 2000},
    )
    scale, shift = float(res.x[0]), float(res.x[1])
    # Clamp to physical bounds after the unconstrained NM run.
    scale = max(scale, 0.0)
    shift = float(np.clip(shift, -shift_bound, shift_bound))
    return scale, shift


# --------------------------------------------------------------------------- #
# Goodness of fit
# --------------------------------------------------------------------------- #
def compute_rwp(
    pattern_intensity: np.ndarray,
    fitted_intensity: np.ndarray,
) -> float:
    """Compute the profile R-factor Rwp.

    .. math::

        R_{wp} = \\sqrt{\\frac{\\sum w_i\\,(y_i - y_{\\text{calc},i})^2}
                              {\\sum w_i\\, y_i^2}},
        \\qquad w_i = 1 / y_i

    Points with non-positive observed intensity are excluded (their
    weight would be infinite and they carry no signal).  If no positive
    points remain, ``inf`` is returned.

    The reference software feature: the Rwp value whose *reduction* drives PFSM ranking.

    Parameters
    ----------
    pattern_intensity:
        Observed (experimental) intensity array.
    fitted_intensity:
        Calculated (fitted) intensity array on the same grid.

    Returns
    -------
    float
        Rwp (≥ 0; ``inf`` if no valid points).
    """
    y = np.asarray(pattern_intensity, dtype=np.float64)
    yc = np.asarray(fitted_intensity, dtype=np.float64)
    mask = y > 0.0
    if not np.any(mask):
        return float("inf")
    ym = y[mask]
    ycm = yc[mask]
    w = 1.0 / ym
    numer = float(np.sum(w * (ym - ycm) ** 2))
    denom = float(np.sum(w * ym ** 2))
    if denom <= 0.0:
        return float("inf")
    return float(np.sqrt(numer / denom))


# --------------------------------------------------------------------------- #
# Per-candidate PFSM score
# --------------------------------------------------------------------------- #
def pfsm_score(
    exp_pattern: Pattern,
    entry: Entry,
    *,
    window_deg: float = 0.3,
) -> dict[str, float]:
    """Run the full PFSM pipeline for one candidate entry.

    1. Generate the reference profile on the experimental 2θ grid.
    2. Fit ``(scale, 2θ_shift)`` so that
       ``scale · reference(2θ − shift)`` best matches the experiment.
    3. Compute Rwp between the experiment and the fitted reference.
    4. Map Rwp → FoM (lower Rwp ⇒ higher FoM).

    The reference software feature: PFSM per-candidate calculation.  Note that the reference software
    ranks by *Rwp reduction* taking already-selected phases into
    account; here we score each entry independently (single-phase
    PFSM).  The ``window_deg`` parameter bounds the allowed 2θ shift.

    Parameters
    ----------
    exp_pattern:
        Experimental diffraction pattern.
    entry:
        Candidate reference entry.
    window_deg:
        Maximum allowed 2θ shift in degrees (also used as the shift
        bound during fitting).  Default 0.3°, the reference software peak-
        correlation window.

    Returns
    -------
    dict[str, float]
        ``{"rwp", "scale", "shift_deg", "fom"}``.
    """
    lo = float(exp_pattern.two_theta.min()) if len(exp_pattern) else 5.0
    hi = float(exp_pattern.two_theta.max()) if len(exp_pattern) else 90.0
    step = float(exp_pattern.step) if exp_pattern.step is not None else 0.02

    ref_tt, ref_int = compute_reference_pattern(
        entry,
        exp_pattern.wavelength,
        (lo, hi),
        step=step,
    )
    # Resample the reference onto the experimental grid so the shift
    # interpolation is exact.
    ref_on_exp = np.interp(
        exp_pattern.two_theta, ref_tt, ref_int, left=0.0, right=0.0
    )

    scale, shift = fit_scale_shift(
        exp_pattern.two_theta,
        exp_pattern.intensity,
        ref_on_exp,
        shift_bound=window_deg,
    )
    fitted = scale * np.interp(
        exp_pattern.two_theta - shift,
        exp_pattern.two_theta,
        ref_on_exp,
        left=0.0,
        right=0.0,
    )
    rwp = compute_rwp(exp_pattern.intensity, fitted)
    # FoM mapping: lower Rwp → higher FoM.  exp(−Rwp/10) keeps FoM in a
    # gentle range (Rwp=0 → 1.0, Rwp=10 → ~0.37) and is well-behaved for
    # large Rwp.
    fom = float(np.exp(-rwp / 10.0)) if np.isfinite(rwp) else 0.0
    return {
        "rwp": float(rwp),
        "scale": float(scale),
        "shift_deg": float(shift),
        "fom": fom,
    }


# --------------------------------------------------------------------------- #
# Batch PFSM ranking
# --------------------------------------------------------------------------- #
def pfsm_rank(
    exp_pattern: Pattern,
    entries: list[Entry],
    *,
    window_deg: float = 0.3,
    top_n: int = 20,
) -> list[tuple[Entry, dict[str, float]]]:
    """Run PFSM over *entries* and return the top-N by FoM.

    The reference software feature: ranked PFSM candidate list.

    Parameters
    ----------
    exp_pattern:
        Experimental diffraction pattern.
    entries:
        Candidate reference entries.
    window_deg:
        Maximum 2θ shift allowed per candidate.
    top_n:
        Number of top candidates to return.

    Returns
    -------
    list[tuple[Entry, dict[str, float]]]
        ``(entry, score_dict)`` pairs sorted by descending FoM.
    """
    scored = [(entry, pfsm_score(exp_pattern, entry, window_deg=window_deg)) for entry in entries]
    scored.sort(key=lambda kv: kv[1]["fom"], reverse=True)
    return scored[:top_n]
