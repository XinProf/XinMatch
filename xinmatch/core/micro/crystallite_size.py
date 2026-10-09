"""Crystallite size estimation via the Scherrer equation.

Implements the reference software's *Crystallite size estimation* command (Quantify menu),
see ``docs/crystallite_size.md``.

The Scherrer equation [1, 2] relates peak width (FWHM) to the average
crystallite size:

.. math::
    D = K\\,\\lambda / (\\beta\\,\\cos\\theta)

where ``K`` is the Scherrer constant (the reference software default = 0.94 for FWHM of
spherical crystals with cubic symmetry; here we default to ``0.9`` to
match the most common textbook convention), ``λ`` is the wavelength, ``β``
is the FWHM (in *radians*), and ``θ`` is the Bragg angle (half the
diffraction angle 2θ).

The Williamson-Hall [3] method additionally separates crystallite-size
broadening from micro-strain broadening by linearising the two effects
against ``sin θ``.

.. note::

   This module does **not** perform instrumental-broadening correction
   (``FWHM_sample² = FWHM_observed² − FWHM_instrumental²``).  The caller
   must supply the sample contribution to the FWHM.  The Caglioti formula
   and instrumental-standard machinery are part of Rietveld refinement
   and will be added in a later phase.

References
----------
[1] P. Scherrer, "Bestimmung der Groesse und der inneren Struktur von
    Kolloidteilchen mittels Roentgenstrahlen", Nachr. Ges. Wiss.
    Goettingen 26 (1918), 98-100.
[2] J.I. Langford, A.J.C. Wilson, "Scherrer after Sixty Years: A Survey
    and Some New Results in the Determination of Crystallite Size",
    J. Appl. Cryst. 11 (1978), 102-113.
[3] G.K. Williamson, W.H. Hall, Acta Metall. 1 (1953), 22-31.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from xinmatch.core.model import Peak

# Radians per degree.
_DEG2RAD = float(np.pi) / 180.0


def scherrer(
    fwhm_deg: float,
    two_theta_deg: float,
    wavelength_angstrom: float,
    *,
    k: float = 0.9,
) -> float:
    """Compute the average crystallite size from a single peak's FWHM.

    Parameters
    ----------
    fwhm_deg:
        Full width at half maximum of the peak, in **degrees 2θ**.
    two_theta_deg:
        Peak position in **degrees 2θ**.
    wavelength_angstrom:
        Wavelength in Å (e.g. Cu Kα1 = 1.5406).
    k:
        Scherrer constant (default 0.9).

    Returns
    -------
    float
        Average crystallite size in **nm**.

    Raises
    ------
    ValueError
        If FWHM, wavelength, or K are non-positive, or if 2θ is outside the
        open interval ``(0°, 180°)``.
    """
    if fwhm_deg <= 0:
        raise ValueError(f"fwhm_deg must be positive, got {fwhm_deg}")
    if two_theta_deg <= 0 or two_theta_deg >= 180:
        raise ValueError(
            f"two_theta_deg must be in (0, 180), got {two_theta_deg}"
        )
    if wavelength_angstrom <= 0:
        raise ValueError(
            f"wavelength_angstrom must be positive, got {wavelength_angstrom}"
        )
    if k <= 0:
        raise ValueError(f"Scherrer constant k must be positive, got {k}")

    fwhm_rad = fwhm_deg * _DEG2RAD
    theta_rad = 0.5 * two_theta_deg * _DEG2RAD
    cos_theta = float(np.cos(theta_rad))
    # For 2θ in (0, 180), θ in (0, 90), cos θ > 0 — guard against FP edge
    # cases very close to 90°.
    if cos_theta <= 0:
        raise ValueError(
            f"cos(theta) is non-positive at 2θ={two_theta_deg}° — "
            f"invalid diffraction angle"
        )

    d_angstrom = (k * wavelength_angstrom) / (fwhm_rad * cos_theta)
    return d_angstrom / 10.0  # Å → nm


def scherrer_from_peaks(
    peaks: Sequence[Peak],
    wavelength_angstrom: float,
    *,
    k: float = 0.9,
) -> list[tuple[Peak, float]]:
    """Batch-compute crystallite sizes from a list of :class:`Peak` objects.

    Each peak's ``fwhm`` (degrees 2θ) and ``two_theta`` (degrees 2θ) are
    passed to :func:`scherrer`.  Peaks without a fitted FWHM
    (``fwhm is None`` or ``fwhm <= 0``) are skipped silently — callers
    that need to know about skips should pre-filter the peak list.

    Parameters
    ----------
    peaks:
        Sequence of :class:`~xinmatch.core.model.Peak` objects.
    wavelength_angstrom:
        Wavelength in Å.
    k:
        Scherrer constant (default 0.9).

    Returns
    -------
    list[tuple[Peak, float]]
        One ``(peak, crystallite_size_nm)`` tuple per valid peak, in input
        order.
    """
    results: list[tuple[Peak, float]] = []
    for p in peaks:
        if p.fwhm is None or p.fwhm <= 0:
            continue
        size = scherrer(p.fwhm, p.two_theta, wavelength_angstrom, k=k)
        results.append((p, size))
    return results


def scherrer_williamson_hall(
    fwhm_deg_list: Sequence[float],
    two_theta_deg_list: Sequence[float],
    wavelength_angstrom: float,
    *,
    k: float = 0.9,
) -> tuple[float, float]:
    """Williamson-Hall analysis for crystallite size and micro-strain.

    Fits the Williamson-Hall equation [3]:

    .. math::
        \\beta\\,\\cos\\theta = K\\,\\lambda / D + 4\\,\\varepsilon\\,\\sin\\theta

    where ``β`` is the FWHM (radians), ``θ`` is the Bragg angle, ``D`` is
    the volume-weighted crystallite size and ``ε`` is the micro-strain.
    Linear regression of ``y = β cos θ`` versus ``x = sin θ`` yields:

    * intercept ``c = K λ / D`` → ``D = K λ / c`` (in Å, returned in nm)
    * slope ``m = 4 ε`` → ``ε = m / 4``

    Parameters
    ----------
    fwhm_deg_list:
        FWHM values in degrees 2θ, one per peak.
    two_theta_deg_list:
        2θ positions in degrees, one per peak.
    wavelength_angstrom:
        Wavelength in Å.
    k:
        Scherrer constant (default 0.9).

    Returns
    -------
    tuple[float, float]
        ``(D_nm, strain_epsilon)`` — crystallite size in nm and micro-strain
        (dimensionless).

    Raises
    ------
    ValueError
        If the input lists have different lengths, contain fewer than two
        points, contain non-positive FWHM / out-of-range 2θ, or if the
        fitted intercept is non-positive (degenerate input that would
        imply infinite crystallite size).
    """
    n = len(fwhm_deg_list)
    if n != len(two_theta_deg_list):
        raise ValueError(
            f"fwhm_deg_list and two_theta_deg_list must have the same "
            f"length: got {n} and {len(two_theta_deg_list)}"
        )
    if n < 2:
        raise ValueError(
            f"Williamson-Hall requires at least 2 points for linear "
            f"regression, got {n}"
        )
    if wavelength_angstrom <= 0:
        raise ValueError(
            f"wavelength_angstrom must be positive, got {wavelength_angstrom}"
        )
    if k <= 0:
        raise ValueError(f"Scherrer constant k must be positive, got {k}")

    fwhm_arr = np.asarray(fwhm_deg_list, dtype=np.float64)
    two_theta_arr = np.asarray(two_theta_deg_list, dtype=np.float64)

    if np.any(fwhm_arr <= 0):
        raise ValueError("All FWHM values must be positive")
    if np.any(two_theta_arr <= 0) or np.any(two_theta_arr >= 180):
        raise ValueError("All 2θ values must be in (0, 180)")

    fwhm_rad = fwhm_arr * _DEG2RAD
    theta_rad = 0.5 * two_theta_arr * _DEG2RAD
    cos_theta = np.cos(theta_rad)
    sin_theta = np.sin(theta_rad)

    if np.any(cos_theta <= 0):
        raise ValueError("cos(theta) is non-positive for at least one peak")

    y = fwhm_rad * cos_theta  # β cos θ
    x = sin_theta              # sin θ

    coeffs = np.polyfit(x, y, 1)
    slope, intercept = float(coeffs[0]), float(coeffs[1])

    if intercept <= 0:
        raise ValueError(
            f"Williamson-Hall intercept is non-positive ({intercept}); "
            f"cannot compute crystallite size (D = Kλ/c)"
        )

    d_angstrom = (k * wavelength_angstrom) / intercept
    d_nm = d_angstrom / 10.0
    strain = slope / 4.0
    return d_nm, strain
