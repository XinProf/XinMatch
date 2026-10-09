"""Residual analysis and R-factor computation (T10.5).

Computes the standard crystallographic R-factors (Rp, Rwp, R_exp, chi^2, GoF)
and detects *unfitted peaks* on the residual spectrum
``I_obs - I_calc``.  The residual spectrum is the difference between the
observed and the calculated powder patterns; peaks in it indicate
reflections that were not accounted for by the model (extra phases, missing
Bragg reflections, or wrong peak-shape parameters).

Corresponds to the reference software's *Peak residuals* view (``docs/Rietveld.md``):
the lower difference plot shown during a Rietveld refinement and the
``Tools → Peak residuals`` analysis command.

References
----------
* R.J. Hill, I.D. Brown, *A Clarendon Press, 1987 (Rietveld method).*
* R.A. Young (ed.), "The Rietveld Method", IUCr/OUP 1993, ch. 1 & 3.
* B.H. Toby, "R factors in Rietveld analysis: How good is good enough?",
  Powder Diffraction 21 (1) (2006) 67-70.
* International Tables for Crystallography Vol. C (2019), ch. 8.5
  (Rietveld refinement).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from xinmatch.core.model import Pattern, Peak
from xinmatch.core.peak.peak_search import find_peaks


@dataclass
class RFactorTable:
    """Standard Rietveld R-factors.

    All factors are reported as **fractions** (multiply by 100 for the
    usual percentage form).  ``GoF`` is the goodness-of-fit
    ``Rwp / R_exp = sqrt(chi^2)``.

    Attributes
    ----------
    rp:
        Profile R-factor ``Rp = Σ|y_obs - y_calc| / Σ|y_obs|``.
    rwp:
        Weighted profile R-factor
        ``Rwp = sqrt(Σ w_i (y_obs - y_calc)² / Σ w_i y_obs²)``.
    r_exp:
        Expected Rwp ``R_exp = sqrt((N - P) / Σ w_i y_obs²)``.
    chi2:
        Reduced chi-squared ``χ² = Σ w_i (y_obs - y_calc)² / (N - P)``.
    gof:
        Goodness of fit ``GoF = sqrt(χ²) = Rwp / R_exp``.
    n_points:
        Number of data points ``N``.
    n_params:
        Number of refined parameters ``P`` used in the degrees of freedom.
    """

    rp: float
    rwp: float
    r_exp: float
    chi2: float
    gof: float
    n_points: int
    n_params: int


@dataclass
class ResidualReport:
    """Outcome of a residual analysis.

    Attributes
    ----------
    rfactors:
        :class:`RFactorTable` with Rp / Rwp / R_exp / chi^2 / GoF.
    residual_pattern:
        Pattern holding ``I_obs - I_calc`` on the same 2θ grid as the
        observed pattern.
    unfitted_peaks:
        Peaks detected on the residual spectrum (i.e. Bragg reflections
        that the model did not account for).
    """

    rfactors: RFactorTable
    residual_pattern: Pattern
    unfitted_peaks: list[Peak] = field(default_factory=list)


def _estimate_variance(y_obs: np.ndarray, sigma: np.ndarray | None) -> np.ndarray:
    """Return the per-point variance ``σ_i²`` to use for weighting.

    If *sigma* (ESD per point) is provided, the variance is ``sigma²``.
    Otherwise a Poisson-like variance is estimated from the data: each
    point's variance is the larger of the observed intensity and the
    median-absolute-deviation noise floor.  The estimator is the same
    one used by
    :class:`xinmatch.core.refine.rietveld.RietveldRefinement` so that
    the Rwp reported here matches the refinement's self-reported Rwp.
    """
    y = np.asarray(y_obs, dtype=np.float64)
    if sigma is not None:
        sigma_arr = np.asarray(sigma, dtype=np.float64)
        return np.maximum(sigma_arr * sigma_arr, 1e-12)
    if y.size <= 1:
        return np.full_like(y, 1.0)
    # Match RietveldRefinement._compute_rwp exactly so the residual Rwp
    # equals the refinement's self-reported Rwp.
    noise = float(np.median(np.abs(np.diff(y)))) / 1.4826
    noise = max(noise, 1e-6)
    return np.maximum(y, noise * noise)


def compute_r_factors(
    y_obs: np.ndarray,
    y_calc: np.ndarray,
    *,
    sigma: np.ndarray | None = None,
    n_params: int = 0,
) -> RFactorTable:
    """Compute Rp / Rwp / R_exp / chi^2 / GoF.

    Parameters
    ----------
    y_obs, y_calc:
        Observed and calculated intensities on the same 2θ grid.
    sigma:
        Optional per-point standard deviations (``σ_i``).  When ``None``
        the Poisson-like / MAD-based estimator is used so that the
        returned Rwp is consistent with the value reported by
        :class:`RietveldRefinement`.
    n_params:
        Number of refined parameters ``P`` for the degrees of freedom
        ``N - P``.  Defaults to ``0`` (no parameters).

    Returns
    -------
    RFactorTable
    """
    y_obs = np.asarray(y_obs, dtype=np.float64)
    y_calc = np.asarray(y_calc, dtype=np.float64)
    if y_obs.shape != y_calc.shape:
        raise ValueError(
            f"y_obs and y_calc must have the same shape, "
            f"got {y_obs.shape} and {y_calc.shape}"
        )
    n_points = int(y_obs.size)
    n_params = max(int(n_params), 0)

    variance = _estimate_variance(y_obs, sigma)
    weight = 1.0 / variance  # w_i = 1/σ_i²

    diff = y_obs - y_calc
    num_wres = float(np.sum(weight * diff * diff))
    denom_wobs_sq = float(np.sum(weight * y_obs * y_obs))

    if denom_wobs_sq <= 0.0:
        rwp = 1.0
        r_exp = 1.0
    else:
        rwp = float(np.sqrt(num_wres / denom_wobs_sq))
        dof = max(n_points - n_params, 1)
        r_exp = float(np.sqrt(dof / denom_wobs_sq))

    sum_abs_obs = float(np.sum(np.abs(y_obs)))
    sum_abs_diff = float(np.sum(np.abs(diff)))
    rp = float(sum_abs_diff / sum_abs_obs) if sum_abs_obs > 0.0 else 1.0

    dof = max(n_points - n_params, 1)
    chi2 = float(num_wres / dof)
    gof = float(np.sqrt(chi2)) if chi2 > 0.0 else 0.0

    return RFactorTable(
        rp=rp,
        rwp=rwp,
        r_exp=r_exp,
        chi2=chi2,
        gof=gof,
        n_points=n_points,
        n_params=n_params,
    )


def residual_analysis(
    observed: Pattern,
    calculated: Pattern,
    *,
    sigma: np.ndarray | None = None,
    n_params: int = 0,
    sensitivity: str = "medium",
    min_intensity_factor: float = 5.0,
) -> ResidualReport:
    """Run a full residual analysis on (observed - calculated).

    Parameters
    ----------
    observed:
        Experimental pattern (background-subtracted).
    calculated:
        Calculated pattern from a Le Bail / Rietveld refinement.  Must be
        on the same 2θ grid as *observed* (no resampling is done here).
    sigma:
        Optional per-point ESDs.  ``None`` ⇒ Poisson/MAD estimate.
    n_params:
        Number of refined parameters used in the degrees of freedom.
    sensitivity:
        Sensitivity preset forwarded to
        :func:`xinmatch.core.peak.peak_search.find_peaks`.
    min_intensity_factor:
        Threshold (in noise σ units) above which a residual peak is
        considered an *unfitted* Bragg reflection.  Defaults to 5σ,
        matching the convention used by the reference software's *Peak residuals* dialog.

    Returns
    -------
    ResidualReport
    """
    if observed.two_theta.shape != calculated.two_theta.shape:
        raise ValueError(
            "observed and calculated patterns must share the same 2θ grid; "
            f"got {observed.two_theta.shape} and {calculated.two_theta.shape}"
        )
    if not np.allclose(observed.two_theta, calculated.two_theta):
        raise ValueError("observed and calculated 2θ grids must match pointwise")

    residual_intensity = observed.intensity - calculated.intensity
    residual_pattern = Pattern(
        two_theta=observed.two_theta.copy(),
        intensity=residual_intensity,
        wavelength=observed.wavelength,
        step=observed.step,
        metadata=dict(observed.metadata),
    )

    rfactors = compute_r_factors(
        observed.intensity,
        calculated.intensity,
        sigma=sigma,
        n_params=n_params,
    )

    variance = _estimate_variance(observed.intensity, sigma)
    noise = float(np.sqrt(np.median(variance)))
    threshold = noise * float(min_intensity_factor)
    peaks = find_peaks(
        observed.two_theta,
        residual_intensity,
        sensitivity=sensitivity,
    )
    unfitted: list[Peak] = [
        p for p in peaks if p.intensity >= threshold
    ]

    return ResidualReport(
        rfactors=rfactors,
        residual_pattern=residual_pattern,
        unfitted_peaks=unfitted,
    )
