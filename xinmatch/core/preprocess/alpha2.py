"""Kα2 stripping (Rachinger method).

Implements the reference software's *Strip K-alpha2* command (Pattern menu).

The measured intensity is the sum of the Kα1 and Kα2 contributions:

.. math::

    I(2\\theta) = I_{\\alpha1}(2\\theta) + I_{\\alpha2}(2\\theta)

with :math:`I_{\\alpha2} = r \\, I_{\\alpha1}` where *r* is the Kα2/Kα1
intensity ratio (0.5 for Cu radiation).  Because the Kα2 wavelength is
longer, each Kα2 companion sits at a *higher* 2θ than its Kα1 parent.

We use the classic Rachinger stripping (W. A. Rachinger, *J. Sci. Instrum.*
**25**, 254 (1948)): iterating from low to high 2θ, the Kα1 intensity at
each point is recovered by subtracting the (already known) Kα1 intensity
at the lower companion angle, scaled by *r*:

.. math::

    I_{\\alpha1}(2\\theta_i) = I(2\\theta_i) - r \\, I_{\\alpha1}(2\\theta_i - \\delta_i)

where :math:`\\delta_i` is the angular separation at :math:`2\\theta_i`,
derived from Bragg's law:

.. math::

    \\delta = 2\\left[\\arcsin\\!\\left(\\frac{\\lambda_{\\alpha2}}{\\lambda_{\\alpha1}}
              \\sin\\theta\\right) - \\theta\\right].
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

#: Negative-excursion tolerance for the Rachinger recursion, as a fraction
#: of the pattern maximum.  On true Kα1+Kα2 data the recursion is exact and
#: only produces noise-level negatives.  On Kα1-only data (monochromated or
#: already-stripped patterns, single-wavelength synthetic patterns) the
#: assumed satellite does not exist: the subtraction over-shoots on every
#: falling edge, the negatives feed forward through the companion lookup,
#: and the output self-excites into oscillations reaching tens of percent
#: of the peak height.  Such patterns are inconsistent with the Kα1+Kα2
#: model, so stripping is skipped for them (the correct answer is "nothing
#: to strip").
_NEGATIVE_EXCURSION_TOL = 0.01


def angular_separation(
    two_theta: float | np.ndarray,
    wavelength_kalpha1: float = 1.5406,
    wavelength_kalpha2: float = 1.5444,
) -> float | np.ndarray:
    """Kα1--Kα2 angular separation in degrees 2θ.

    Parameters
    ----------
    two_theta:
        Scattering angle(s) in degrees 2θ.
    wavelength_kalpha1, wavelength_kalpha2:
        Kα1 and Kα2 wavelengths in Å (Cu defaults).

    Returns
    -------
    float or np.ndarray
        Separation :math:`2\\theta_{\\alpha2} - 2\\theta_{\\alpha1}` in
        degrees (always non-negative for valid input).
    """
    theta = np.radians(np.asarray(two_theta, dtype=np.float64) / 2.0)
    ratio = wavelength_kalpha2 / wavelength_kalpha1
    sin_theta2 = np.clip(ratio * np.sin(theta), -1.0, 1.0)
    theta2 = np.arcsin(sin_theta2)
    delta = 2.0 * np.degrees(theta2 - theta)
    return np.asarray(delta, dtype=np.float64)


def strip_alpha2(
    two_theta: np.ndarray,
    intensity: np.ndarray,
    wavelength_kalpha1: float = 1.5406,
    wavelength_kalpha2: float = 1.5444,
    ratio: float = 0.5,
) -> np.ndarray:
    """Strip the Kα2 contribution from a powder diffraction pattern.

    The reference software feature: *Strip K-alpha2* (Pattern menu).  the reference software uses the
    Ladell--Zagofsky--Pearlman algorithm; here we implement the classical
    Rachinger iterative stripping.

    Parameters
    ----------
    two_theta:
        1-D array of scattering angles (degrees 2θ), monotonically
        increasing.
    intensity:
        1-D array of measured (Kα1 + Kα2) intensities.
    wavelength_kalpha1, wavelength_kalpha2:
        Kα1 and Kα2 wavelengths in Å.
    ratio:
        Kα2/Kα1 intensity ratio (0.5 for Cu).

    Returns
    -------
    np.ndarray
        Kα1-only intensities, same shape as *intensity*.
    """
    two_theta = np.asarray(two_theta, dtype=np.float64)
    intensity = np.asarray(intensity, dtype=np.float64)
    if two_theta.shape != intensity.shape:
        raise ValueError("two_theta and intensity must have the same shape")
    if two_theta.ndim != 1:
        raise ValueError("two_theta must be a 1-D array")

    n = two_theta.size
    alpha1 = np.empty(n, dtype=np.float64)
    if n == 0:
        return alpha1

    delta = np.asarray(
        angular_separation(two_theta, wavelength_kalpha1, wavelength_kalpha2),
        dtype=np.float64,
    )

    # Iterate from low to high 2θ: the Kα2 companion seen at 2θ_i was
    # produced by the Kα1 at (2θ_i - δ_i), which has already been computed.
    alpha1[0] = intensity[0]
    for i in range(1, n):
        target = two_theta[i] - delta[i]
        if target <= two_theta[0]:
            alpha1[i] = intensity[i]
        else:
            # Interpolate the already-recovered α1 intensity at the
            # companion angle using points 0..i.
            alpha1_companion = float(
                np.interp(target, two_theta[: i + 1], alpha1[: i + 1])
            )
            alpha1[i] = intensity[i] - ratio * alpha1_companion

    # Stability guard: reject stripping when the recursion produced
    # unphysical negative excursions beyond the tolerance (Kα1-only data,
    # see _NEGATIVE_EXCURSION_TOL).  Return the input unchanged instead of
    # a ringing-corrupted profile.
    if n > 0:
        peak_scale = float(np.max(intensity))
        if peak_scale > 0.0 and float(np.min(alpha1)) < -_NEGATIVE_EXCURSION_TOL * peak_scale:
            logger.debug(
                "strip_alpha2: negative excursion %.3g exceeds %.1f%% of the "
                "pattern maximum — pattern is inconsistent with the "
                "Kα1+Kα2 model; stripping skipped",
                float(np.min(alpha1)),
                _NEGATIVE_EXCURSION_TOL * 100.0,
            )
            return np.array(intensity, dtype=np.float64, copy=True)

    return alpha1
