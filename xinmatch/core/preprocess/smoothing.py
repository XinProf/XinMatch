"""Raw data smoothing.

Implements the reference software's *Smooth raw data* command (Pattern menu / Ctrl+F4).

Two algorithms are provided:

* ``'moving_average'`` — a simple box-car (uniform) moving average.
* ``'savgol'`` — Savitzky--Golay smoothing, the algorithm used by the reference software
  (A. Savitzky and M.J.E. Golay, *Analyt. Chem.* **36**, 1627 (1964);
  corrected by Steinier, Termonia and Deltour, *Analyt. Chem.* **44**, 1906
  (1972)).  the reference software defaults to a polynomial order of 2 and an
  automatically-determined window width (roughly the number of points in
  the FWHM of the peaks).

The functions operate on plain ``numpy.ndarray`` intensity vectors and return
an ``np.ndarray`` of the same length — no GUI involvement.
"""

from __future__ import annotations

import numpy as np


def smooth(
    intensity: np.ndarray,
    method: str = "savgol",
    window: int = 11,
    polyorder: int = 3,
) -> np.ndarray:
    """Smooth a 1-D diffraction intensity vector.

    The reference software feature: *Smooth raw data* (Pattern menu, Ctrl+F4).
    Algorithm: Savitzky--Golay (default) or moving average.

    Parameters
    ----------
    intensity:
        1-D array of diffraction intensities (counts).
    method:
        Smoothing algorithm.  One of ``'savgol'`` (default) or
        ``'moving_average'``.
    window:
        Window width in data points.  Must be a positive odd integer for
        Savitzky--Golay.  the reference software uses a window roughly equal to the number
        of points in the FWHM of the peaks (or up to 20 % larger).
    polyorder:
        Polynomial order for the Savitzky--Golay filter (ignored for the
        moving-average method).  the reference software defaults to 2.

    Returns
    -------
    np.ndarray
        Smoothed intensities, same shape and dtype as the input.

    Raises
    ------
    ValueError
        If *method* is unknown or the window is invalid.
    """
    # 延迟导入：scipy.signal 单独就要 ~0.2 s，而本模块在 GUI 启动链上
    # （main_window → auto_pipeline → smoothing）。首次调用后 import 命中
    # sys.modules，重复调用只是一次字典查找。
    from scipy.signal import savgol_filter

    intensity = np.asarray(intensity, dtype=np.float64)
    if intensity.ndim != 1:
        raise ValueError("intensity must be a 1-D array")

    n = intensity.size
    if n == 0:
        return intensity.copy()  # type: ignore[no-any-return]

    if window < 1:
        raise ValueError(f"window must be >= 1, got {window}")
    if window > n:
        window = n if n % 2 == 1 else n - 1
        if window < 1:
            return intensity.copy()  # type: ignore[no-any-return]

    if method == "savgol":
        if window % 2 == 0:
            window += 1
        if polyorder >= window:
            polyorder = window - 1
        return np.asarray(
            savgol_filter(intensity, window_length=window, polyorder=polyorder),
            dtype=np.float64,
        )

    if method == "moving_average":
        kernel = np.ones(window, dtype=np.float64) / window
        # 'same' convolution keeps the output length; edges use zero padding.
        return np.convolve(intensity, kernel, mode="same")

    raise ValueError(f"unknown smoothing method: {method!r}")
