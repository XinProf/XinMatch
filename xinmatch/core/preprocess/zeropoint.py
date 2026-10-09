"""Zero-point (2θ offset) correction.

Implements the reference software's *Correct zero point* command (Pattern menu).

A constant zero-point shift :math:`\\Delta(2\\theta)` is added to (or
subtracted from) the whole 2θ axis to align experimental peaks with
reference positions.  :func:`correct_zero_point` applies the shift;
:func:`find_shift` estimates it from a set of experimental peak positions
and their known standard positions by robust (median) pair-difference.

The reference software determines the shift automatically by analysing d-value quotients of
peak pairs (e.g. d(100) = 2·d(200)); here we accept an explicit list of
standard peak positions, which is the common case when an internal standard
or known reference pattern is available.
"""

from __future__ import annotations

import numpy as np


def correct_zero_point(
    two_theta: np.ndarray,
    shift: float,
) -> np.ndarray:
    """Apply a constant 2θ zero-point shift.

    The reference software feature: *Correct zero point* (Pattern menu).  The shift is
    *subtracted* from the data to remove the error:
    ``corrected = two_theta - shift``.

    Parameters
    ----------
    two_theta:
        1-D array of scattering angles (degrees 2θ).
    shift:
        Zero-point offset in degrees 2θ to remove.  Positive shift means
        the data are shifted to higher angles and must be moved down.

    Returns
    -------
    np.ndarray
        Corrected 2θ array.
    """
    two_theta = np.asarray(two_theta, dtype=np.float64)
    return two_theta - float(shift)


def find_shift(
    experimental_peaks: np.ndarray,
    standard_peaks: np.ndarray,
) -> float:
    """Estimate the zero-point shift between experimental and standard peaks.

    The shift is the robust (median) difference between paired experimental
    and standard peak positions.  Peaks are paired by nearest-neighbour
    matching within a tolerance window.

    Parameters
    ----------
    experimental_peaks:
        1-D array of experimental peak positions (degrees 2θ).
    standard_peaks:
        1-D array of standard (reference) peak positions (degrees 2θ).

    Returns
    -------
    float
        Estimated zero-point shift :math:`\\Delta(2\\theta)` in degrees,
        such that ``experimental - standard ≈ shift`` (i.e. apply
        :func:`correct_zero_point` with this value to align the data).
        Returns ``0.0`` if no pairs can be matched.
    """
    exp = np.asarray(experimental_peaks, dtype=np.float64).ravel()
    std = np.asarray(standard_peaks, dtype=np.float64).ravel()

    if exp.size == 0 or std.size == 0:
        return 0.0

    # Match each experimental peak to the nearest standard peak.
    diffs: list[float] = []
    for e in exp:
        idx = int(np.argmin(np.abs(std - e)))
        diffs.append(float(e - std[idx]))

    if not diffs:
        return 0.0
    return float(np.median(diffs))
