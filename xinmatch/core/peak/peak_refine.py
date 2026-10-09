"""Peak position refinement.

Implements the sub-point peak-position refinement used by the reference software's peak
search and profile fitting.  Three methods are provided:

* ``'centroid'`` — intensity-weighted centre of gravity over a window.
* ``'parabola'`` — fit a quadratic to the top three (or five) points and
  take its vertex.
* ``'gaussian'`` — fit a Gaussian (with a constant baseline) over a window
  using :func:`scipy.optimize.curve_fit`.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import curve_fit

from xinmatch.core.peak.shapes import gaussian


def refine_peak_position(
    two_theta: np.ndarray,
    intensity: np.ndarray,
    idx: int,
    method: str = "gaussian",
    window: int = 5,
) -> float:
    """Refine a peak position to sub-step accuracy.

    The reference software feature: sub-point peak position determination during peak
    search / profile fitting.

    Parameters
    ----------
    two_theta:
        1-D array of scattering angles (degrees 2θ).
    intensity:
        1-D array of intensities.
    idx:
        Index of the (approximate) peak apex in the arrays.
    method:
        ``'centroid'``, ``'parabola'``, or ``'gaussian'`` (default).
    window:
        Half-window (in points) used around *idx*.  Total width is
        ``2 * window + 1``.

    Returns
    -------
    float
        Refined peak position in degrees 2θ.

    Raises
    ------
    ValueError
        If *idx* is out of range or *method* is unknown.
    """
    two_theta = np.asarray(two_theta, dtype=np.float64)
    intensity = np.asarray(intensity, dtype=np.float64)
    n = two_theta.size
    if not 0 <= idx < n:
        raise ValueError(f"idx {idx} out of range [0, {n})")

    lo = max(0, idx - window)
    hi = min(n, idx + window + 1)
    x = two_theta[lo:hi]
    y = intensity[lo:hi]

    if method == "centroid":
        total = y.sum()
        if total <= 0.0:
            return float(two_theta[idx])
        return float(np.sum(x * y) / total)

    if method == "parabola":
        if y.size < 3:
            return float(two_theta[idx])
        # Fit y = a*x^2 + b*x + c.
        coeffs = np.polyfit(x, y, 2)
        a, b = coeffs[0], coeffs[1]
        if a >= 0.0:
            # Not a maximum; fall back to the input position.
            return float(two_theta[idx])
        return float(-b / (2.0 * a))

    if method == "gaussian":
        if y.size < 4:
            return float(two_theta[idx])
        # Model: y = baseline + gaussian(x, center, fwhm, amplitude).
        baseline = float(y.min())
        height = float(y.max() - baseline)
        center0 = float(two_theta[idx])
        step = float(np.median(np.diff(x))) if x.size > 1 else 0.05
        fwhm0 = max(3.0 * step, 0.1)
        amp0 = height * fwhm0 * np.sqrt(2.0 * np.pi) / (
            2.0 * np.sqrt(2.0 * np.log(2.0))
        )

        def model(x_, center, fwhm, amplitude, bg):
            return bg + gaussian(x_, center, fwhm, amplitude)

        try:
            popt, _ = curve_fit(
                model,
                x,
                y,
                p0=[center0, fwhm0, amp0, baseline],
                bounds=(
                    [x[0], 1e-6, 0.0, -np.inf],
                    [x[-1], np.inf, np.inf, np.inf],
                ),
                maxfev=5000,
            )
            return float(popt[0])
        except (RuntimeError, ValueError):
            return float(two_theta[idx])

    raise ValueError(f"unknown refinement method: {method!r}")
