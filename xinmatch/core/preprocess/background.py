"""Background determination and subtraction.

Implements the reference software's background determination (*Recalculate background*,
*Set background to zero*, *Two points*) and *Subtract background* commands.

Three automatic methods are provided:

* ``'snip'`` — the Statistics-sensitive Non-linear Iterative Peak-clipping
  (SNIP) algorithm (C. G. Ryan et al., *Nucl. Instrum. Methods Phys. Res.,
  Sect. B* **34**, 396 (1988)).  A robust, window-decreasing peak-clipping
  filter that converges to the background.
* ``'polynomial'`` — iterative polynomial fitting with an asymmetric
  (Asymmetric Least Squares style) penalty that pushes the curve below the
  peaks (E. P. Boelens et al., and the asymmetric-least-squares idea of
  P. H. C. Eilers and H. F. M. Boelens, 2005).
* ``'two_points'`` — a straight line connecting the left- and right-most
  data points (the reference software's *Two points* option).

Manual background control points can be interpolated with
:func:`interpolate_background`.  Subtraction (with clipping to zero) is
provided by :func:`subtract_background`.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


def _snip(
    intensity: np.ndarray,
    window: int = 20,
    niter: int = 8,
    log_transform: bool = False,
) -> np.ndarray:
    """Core SNIP peak-clipping background estimator.

    Parameters
    ----------
    intensity:
        1-D intensity array (counts, non-negative recommended).
    window:
        Maximum half-window width in points (the largest clip window).
    niter:
        Number of decreasing-window passes per window size.
    log_transform:
        If ``True``, work in log space (classic SNIP for XRF with Poisson
        statistics).  For XRD with arbitrary background shapes leave this
        ``False``.
    """
    y = intensity.astype(np.float64).copy()
    if log_transform:
        # Avoid log of zero / negatives.
        offset = y.min()
        y = np.log(y - offset + 1.0)

    n = y.size
    bg = y.copy()
    for w in range(window, 0, -1):
        for _ in range(niter):
            left = np.roll(bg, w)
            right = np.roll(bg, -w)
            # Edge handling: set invalid neighbours to the current value so
            # that min picks bg (no clipping at the borders).
            left[:w] = bg[:w]
            right[n - w :] = bg[n - w :]
            avg = 0.5 * (left + right)
            bg = np.minimum(bg, avg)

    if log_transform:
        bg = np.exp(bg) + offset - 1.0
    return bg  # type: ignore[no-any-return]


def _asymmetric_polynomial(
    intensity: np.ndarray,
    x: np.ndarray,
    degree: int = 4,
    niter: int = 20,
    asym_penalty: float = 0.01,
) -> np.ndarray:
    """Iterative asymmetric polynomial background fit.

    A polynomial is fitted by weighted least squares.  After each fit,
    points above the fit are down-weighted (peaks are penalised so the
    curve tends to lie beneath them).  This is the asymmetric-least-squares
    idea adapted to a polynomial basis.

    Parameters
    ----------
    intensity:
        1-D intensity array.
    x:
        Independent variable (2θ), same length as *intensity*.
    degree:
        Polynomial degree.
    niter:
        Number of re-weighting iterations.
    asym_penalty:
        Weight assigned to points above the current fit (in ``(0, 1)``).
        Smaller values push the background further below the peaks.
    """
    y = intensity.astype(np.float64)
    weights = np.ones_like(y)
    # Centre and scale x for numerical stability.
    xm = x.mean()
    xs = x.std() if x.std() > 0 else 1.0
    xs = np.where(xs == 0, 1.0, xs)
    xs = float(xs) if not isinstance(xs, float) else xs
    xs = float(xs)
    xn = (x - xm) / xs

    bg = np.zeros_like(y)
    for _ in range(niter):
        # Weighted polynomial fit.
        coeffs = np.polyfit(xn, y, degree, w=weights)
        bg = np.polyval(coeffs, xn)
        residual = y - bg
        # Points above the fit (peaks) get a low weight; points below keep
        # full weight.  A small floor keeps the system non-singular.
        above = residual > 0
        weights = np.where(above, asym_penalty, 1.0)
        weights = np.maximum(weights, 1e-6)
    return bg


def estimate_background(
    two_theta: np.ndarray,
    intensity: np.ndarray,
    method: str = "snip",
    window: int = 20,
    degree: int = 4,
    control_points: np.ndarray | None = None,
) -> np.ndarray:
    """Estimate the diffraction-pattern background.

    The reference software feature: *Background determination* (Pattern → Background menu,
    automatic during import).  the reference software uses the Sonneveld--Visser method by
    default; here we provide SNIP and iterative asymmetric-polynomial
    estimators which are widely used and robust.

    Parameters
    ----------
    two_theta:
        1-D array of scattering angles (degrees 2θ).  Only used for the
        polynomial and manual-control-point methods; ignored for SNIP.
    intensity:
        1-D array of diffraction intensities (counts).
    method:
        ``'snip'`` (default), ``'polynomial'``, ``'two_points'``, or
        ``'manual'`` (requires *control_points*).
    window:
        SNIP maximum half-window in points (only for ``'snip'``).
    degree:
        Polynomial degree (only for ``'polynomial'``).
    control_points:
        For ``'manual'``: an ``(N, 2)`` array of ``(two_theta, intensity)``
        control points.  Cubic-spline interpolation is used.

    Returns
    -------
    np.ndarray
        Estimated background, same length as *intensity*.

    Raises
    ------
    ValueError
        For an unknown *method* or missing control points.
    """
    two_theta = np.asarray(two_theta, dtype=np.float64)
    if two_theta.ndim != 1:
        raise ValueError("two_theta must be a 1-D array")

    if method == "manual":
        if control_points is None:
            raise ValueError("control_points must be provided for method='manual'")
        return interpolate_background(two_theta, control_points)

    intensity = np.asarray(intensity, dtype=np.float64)
    if intensity.ndim != 1:
        raise ValueError("intensity must be a 1-D array")
    if two_theta.shape != intensity.shape:
        raise ValueError("two_theta and intensity must have the same shape")

    if method == "snip":
        return _snip(intensity, window=window)

    if method == "polynomial":
        return _asymmetric_polynomial(intensity, two_theta, degree=degree)

    if method == "two_points":
        # Straight line between the first and last data points.
        if intensity.size < 2:
            return intensity.copy()  # type: ignore[no-any-return]
        t0, t1 = two_theta[0], two_theta[-1]
        i0, i1 = intensity[0], intensity[-1]
        if t1 == t0:
            return np.full_like(intensity, i0)
        return np.asarray(
            i0 + (i1 - i0) * (two_theta - t0) / (t1 - t0), dtype=np.float64
        )

    raise ValueError(f"unknown background method: {method!r}")


def interpolate_background(
    two_theta: np.ndarray,
    control_points: np.ndarray,
    kind: str = "cubic",
) -> np.ndarray:
    """Interpolate a background curve from user-defined control points.

    The reference software feature: manual adjustment of background control points with
    cubic-spline interpolation.

    Parameters
    ----------
    two_theta:
        1-D array of scattering angles at which to evaluate the background.
    control_points:
        ``(N, 2)`` array of ``(two_theta, intensity)`` control points.
    kind:
        Interpolation kind passed to :func:`scipy.interpolate.interp1d`.
        Defaults to ``'cubic'`` (the reference software uses cubic splines).

    Returns
    -------
    np.ndarray
        Interpolated background at *two_theta*.
    """
    # 延迟导入：本模块在 GUI 启动链上（auto_pipeline），而 interp1d 会把
    # scipy.interpolate 整条链（含 spline/linalg）带进内存；只有手动背景
    # 控制点这条冷路径真的需要它。
    from scipy.interpolate import interp1d

    control_points = np.asarray(control_points, dtype=np.float64)
    if control_points.ndim != 2 or control_points.shape[1] != 2:
        raise ValueError("control_points must have shape (N, 2)")
    # Sort control points by 2θ.
    order = np.argsort(control_points[:, 0])
    cp = control_points[order]
    xp = cp[:, 0]
    yp = cp[:, 1]
    if xp.size < 2:
        return np.full_like(two_theta, yp[0] if yp.size else 0.0, dtype=np.float64)
    # scipy's cubic spline needs at least 4 points; fall back to quadratic
    # or linear for smaller control-point sets.
    actual_kind = kind
    if xp.size < 4 and kind == "cubic":
        actual_kind = "quadratic" if xp.size >= 3 else "linear"
    f = interp1d(
        xp,
        yp,
        kind=actual_kind,
        bounds_error=False,
        fill_value=(yp[0], yp[-1]),
    )
    return np.asarray(f(np.asarray(two_theta, dtype=np.float64)), dtype=np.float64)


def subtract_background(
    intensity: np.ndarray,
    background: np.ndarray,
) -> np.ndarray:
    """Subtract the background, clipping negative results to zero.

    The reference software feature: *Subtract background* (Pattern menu).  Net intensity =
    raw − background; physically non-negative values are enforced.

    Parameters
    ----------
    intensity:
        Raw diffraction intensities.
    background:
        Estimated background, same shape as *intensity*.

    Returns
    -------
    np.ndarray
        Background-subtracted (net) intensities, clipped to ``>= 0``.
    """
    intensity = np.asarray(intensity, dtype=np.float64)
    background = np.asarray(background, dtype=np.float64)
    if intensity.shape != background.shape:
        raise ValueError(
            f"intensity and background must have the same shape, "
            f"got {intensity.shape} and {background.shape}"
        )
    net = intensity - background
    np.clip(net, 0.0, None, out=net)
    return np.asarray(net, dtype=np.float64)
