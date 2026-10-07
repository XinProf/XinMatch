"""Multi-peak profile fitting.

Implements Match!'s *Profile fitting* command (Pattern → Profile fitting,
F5).  Match! optimises 2θ, intensity and FWHM of all peaks by constrained
least squares using the *Intermediate Lorentzian* (IL) profile.  Here we
fit a sum of Gaussian / Lorentzian / pseudo-Voigt / Pearson VII peaks with
:func:`scipy.optimize.least_squares`.

The weighted profile R-factor (``Rwp``) is reported, matching Match!'s
status-bar output:

.. math::

    R_{wp} = \\sqrt{\\frac{\\sum_i w_i (y_i^{obs} - y_i^{calc})^2}
                                {\\sum_i w_i (y_i^{obs})^2}}

with :math:`w_i = 1 / y_i^{obs}` (Poisson weighting).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import least_squares

from xinmatch.core.model import Peak
from xinmatch.core.peak.shapes import SHAPE_FUNCTIONS


@dataclass
class FitResult:
    """Result of a multi-peak profile fit.

    Attributes
    ----------
    fitted_peaks:
        List of :class:`Peak` objects with refined positions, integrated
        intensities (areas) and FWHM.
    fitted_intensity:
        Calculated (fitted) intensity array over the input 2θ grid.
    rwp:
        Weighted profile R-factor (as a fraction, e.g. 0.02 for 2 %).
    """

    fitted_peaks: list[Peak]
    fitted_intensity: np.ndarray
    rwp: float


def _build_model(
    x: np.ndarray,
    params: np.ndarray,
    n_peaks: int,
    shape: str,
    has_eta: bool,
) -> np.ndarray:
    """Evaluate the sum-of-peaks model.

    Parameters layout (per peak): center, fwhm, amplitude[, eta].
    """
    shape_fn = SHAPE_FUNCTIONS[shape]
    y = np.zeros_like(x)
    per_peak = 4 if has_eta else 3
    for i in range(n_peaks):
        base = i * per_peak
        center = params[base]
        fwhm = params[base + 1]
        amplitude = params[base + 2]
        if has_eta:
            eta = params[base + 3]
            y = y + shape_fn(x, center, fwhm, amplitude, eta)
        else:
            y = y + shape_fn(x, center, fwhm, amplitude)
    return y


def fit_profile(
    two_theta: np.ndarray,
    intensity: np.ndarray,
    peaks: list[Peak],
    shape: str = "pseudo_voigt",
) -> FitResult:
    """Fit a multi-peak profile to experimental data.

    Match! feature: *Profile fitting* (F5).  Algorithm: non-linear least
    squares (Levenberg--Marquardt / Trust Region Reflective) over the sum
    of peak-shape functions.

    Parameters
    ----------
    two_theta:
        1-D array of scattering angles (degrees 2θ).
    intensity:
        1-D array of (background-subtracted) experimental intensities.
    peaks:
        Initial peak guesses.  ``two_theta``, ``intensity`` (height —
        internally converted to area) and ``fwhm`` are used as starting
        values.
    shape:
        Peak shape: ``'gaussian'``, ``'lorentzian'``, ``'pseudo_voigt'``
        (default) or ``'pearson_vii'``.

    Returns
    -------
    FitResult
        Fitted peaks, calculated profile and ``Rwp``.
    """
    two_theta = np.asarray(two_theta, dtype=np.float64)
    intensity = np.asarray(intensity, dtype=np.float64)
    if two_theta.shape != intensity.shape:
        raise ValueError("two_theta and intensity must have the same shape")
    if shape not in SHAPE_FUNCTIONS:
        raise ValueError(f"unknown shape: {shape!r}")
    if not peaks:
        return FitResult(
            fitted_peaks=[],
            fitted_intensity=np.zeros_like(intensity),
            rwp=1.0,
        )

    has_eta = shape in ("pseudo_voigt",)
    per_peak = 4 if has_eta else 3
    n_peaks = len(peaks)

    # Convert heights to areas for the normalised shapes.
    # For a normalised Gaussian, amplitude(area) = height * sigma * sqrt(2π)
    # = height * fwhm * sqrt(2π) / (2*sqrt(2 ln2)).
    def height_to_area(height: float, fwhm: float) -> float:
        sigma = fwhm / (2.0 * np.sqrt(2.0 * np.log(2.0)))
        return float(height * sigma * np.sqrt(2.0 * np.pi))

    step = float(np.median(np.diff(two_theta))) if two_theta.size > 1 else 0.05

    x0: list[float] = []
    bounds_lo: list[float] = []
    bounds_hi: list[float] = []
    for p in peaks:
        fwhm = p.fwhm if p.fwhm is not None else max(5.0 * step, 0.1)
        area = height_to_area(p.intensity, fwhm)
        x0.extend([p.two_theta, fwhm, area])
        bounds_lo.extend([two_theta[0], 1e-4, 0.0])
        bounds_hi.extend([two_theta[-1], np.inf, np.inf])
        if has_eta:
            x0.append(0.5)
            bounds_lo.append(0.0)
            bounds_hi.append(1.0)

    # Weights: Poisson-like w_i = 1 / sigma_i^2 with sigma_i^2 = max(y_i, sigma_noise^2).
    # A noise floor keeps low-intensity (noise) points from dominating the
    # fit and the Rwp denominator.
    obs = intensity
    # Robust noise estimate from the first differences (MAD).
    diff = np.diff(obs)
    mad = np.median(np.abs(diff - np.median(diff)))
    sigma_noise = float(1.4826 * mad / np.sqrt(2.0)) if mad > 0 else 1.0
    sigma_noise = max(sigma_noise, 1e-6)
    variance = np.maximum(obs, sigma_noise ** 2)
    weight = 1.0 / np.sqrt(variance)

    def residuals(params: np.ndarray) -> np.ndarray:
        calc = _build_model(two_theta, params, n_peaks, shape, has_eta)
        return weight * (obs - calc)

    result = least_squares(
        residuals,
        x0=np.array(x0, dtype=np.float64),
        bounds=(np.array(bounds_lo), np.array(bounds_hi)),
        method="trf",
        max_nfev=20000,
    )

    calc = _build_model(two_theta, result.x, n_peaks, shape, has_eta)

    # Weighted profile R-factor Rwp.
    # Only points with significant signal (obs > 3 sigma_noise) are included;
    # pure-noise points would otherwise dominate the statistic.
    mask = obs > 3.0 * sigma_noise
    if not np.any(mask):
        mask = np.ones_like(obs, dtype=bool)
    num = np.sum((weight[mask] * (obs[mask] - calc[mask])) ** 2)
    den = np.sum((weight[mask] * obs[mask]) ** 2)
    rwp = float(np.sqrt(num / den)) if den > 0 else 1.0

    fitted_peaks: list[Peak] = []
    for i in range(n_peaks):
        base = i * per_peak
        center = float(result.x[base])
        fwhm = float(result.x[base + 1])
        area = float(result.x[base + 2])
        fitted_peaks.append(
            Peak(
                two_theta=center,
                intensity=area,
                fwhm=fwhm,
            )
        )

    return FitResult(
        fitted_peaks=fitted_peaks,
        fitted_intensity=calc,
        rwp=rwp,
    )
