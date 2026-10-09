"""Convert a list of peaks back to a diffraction profile.

Implements the reference software's *Calculate profile from peak data* concept (used for
displaying the calculated profile and for residual-peak analysis).  Each
peak is rendered with its shape function and integrated intensity (area),
and the contributions are summed.
"""

from __future__ import annotations

import numpy as np

from xinmatch.core.model import Peak
from xinmatch.core.peak.shapes import SHAPE_FUNCTIONS


def peaks_to_profile(
    two_theta: np.ndarray,
    peaks: list[Peak],
    shape: str = "pseudo_voigt",
    eta: float = 0.5,
) -> np.ndarray:
    """Sum peak shapes into a calculated diffraction profile.

    The reference software feature: profile calculation from the peak list (displayed as
    the *calculated profile* curve).

    Parameters
    ----------
    two_theta:
        1-D array of scattering angles (degrees 2θ) at which to evaluate
        the profile.
    peaks:
        List of :class:`Peak` objects.  ``intensity`` is treated as the
        integrated intensity (peak area); ``fwhm`` must be set.
    shape:
        Peak shape name (see :data:`SHAPE_FUNCTIONS`).
    eta:
        Lorentzian fraction for ``pseudo_voigt`` (ignored otherwise).

    Returns
    -------
    np.ndarray
        Calculated intensity profile, same length as *two_theta*.

    Raises
    ------
    ValueError
        If *shape* is unknown or a peak has no ``fwhm``.
    """
    two_theta = np.asarray(two_theta, dtype=np.float64)
    if shape not in SHAPE_FUNCTIONS:
        raise ValueError(f"unknown shape: {shape!r}")
    shape_fn = SHAPE_FUNCTIONS[shape]
    has_eta = shape in ("pseudo_voigt",)

    profile = np.zeros_like(two_theta)
    for p in peaks:
        if p.fwhm is None:
            raise ValueError(
                f"peak at 2θ={p.two_theta} has no fwhm; cannot render profile"
            )
        if has_eta:
            profile = profile + shape_fn(
                two_theta, p.two_theta, p.fwhm, p.intensity, eta
            )
        else:
            profile = profile + shape_fn(
                two_theta, p.two_theta, p.fwhm, p.intensity
            )
    return profile
