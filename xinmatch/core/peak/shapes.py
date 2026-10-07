"""Peak profile (shape) functions.

Implements the analytical peak shapes used by Match!'s profile fitting
(*Profile Fitting* dialog).  Match! uses the *Intermediate Lorentzian* (IL)
profile; here we provide the standard building blocks from which IL and
pseudo-Voigt are composed:

* Gaussian
* Lorentzian (Cauchy)
* pseudo-Voigt (linear combination of Gaussian and Lorentzian)
* Pearson VII

Conversion helpers ``fwhm_to_sigma`` / ``sigma_to_fwhm`` are provided so the
functions can be parameterised either way.  Each shape is normalised to
*area* = ``amplitude`` (i.e. the integral over all x equals ``amplitude``),
which is the convention used for integrated intensities.
"""

from __future__ import annotations

import numpy as np

# 2 * sqrt(2 * ln 2)  — converts Gaussian σ to FWHM and back.
_FWHM_TO_SIGMA = 1.0 / (2.0 * np.sqrt(2.0 * np.log(2.0)))


def fwhm_to_sigma(fwhm: float | np.ndarray) -> float | np.ndarray:
    """Convert Gaussian FWHM to standard deviation σ."""
    return fwhm * _FWHM_TO_SIGMA


def sigma_to_fwhm(sigma: float | np.ndarray) -> float | np.ndarray:
    """Convert Gaussian standard deviation σ to FWHM."""
    return sigma / _FWHM_TO_SIGMA


def gaussian(
    x: np.ndarray,
    center: float,
    fwhm: float,
    amplitude: float,
) -> np.ndarray:
    """Normalised Gaussian peak.

    .. math::

        G(x) = \\frac{A}{\\sigma\\sqrt{2\\pi}}
               \\exp\\!\\left[-\\frac{(x-c)^2}{2\\sigma^2}\\right]

    where :math:`\\sigma = \\mathrm{FWHM} / (2\\sqrt{2\\ln 2})`.

    Parameters
    ----------
    x:
        Independent variable (e.g. 2θ in degrees).
    center:
        Peak centre.
    fwhm:
        Full width at half maximum.
    amplitude:
        Peak *area* (integrated intensity).
    """
    x = np.asarray(x, dtype=np.float64)
    sigma = fwhm_to_sigma(fwhm)
    prefactor = amplitude / (sigma * np.sqrt(2.0 * np.pi))
    return prefactor * np.exp(-0.5 * ((x - center) / sigma) ** 2)


def lorentzian(
    x: np.ndarray,
    center: float,
    fwhm: float,
    amplitude: float,
) -> np.ndarray:
    """Normalised Lorentzian (Cauchy) peak.

    .. math::

        L(x) = \\frac{A}{\\pi} \\cdot \\frac{\\Gamma/2}
               {(x-c)^2 + (\\Gamma/2)^2}

    where :math:`\\Gamma` is the FWHM.
    """
    x = np.asarray(x, dtype=np.float64)
    gamma = fwhm  # Γ
    return amplitude * (gamma / 2.0) / (np.pi * ((x - center) ** 2 + (gamma / 2.0) ** 2))


def pseudo_voigt(
    x: np.ndarray,
    center: float,
    fwhm: float,
    amplitude: float,
    eta: float = 0.5,
) -> np.ndarray:
    """Normalised pseudo-Voigt peak.

    A linear combination of a Gaussian and a Lorentzian sharing the same
    FWHM:

    .. math::

        V(x) = \\eta \\, L(x) + (1 - \\eta) \\, G(x)

    Parameters
    ----------
    x, center, fwhm, amplitude:
        As for :func:`gaussian` / :func:`lorentzian`.
    eta:
        Lorentzian fraction in ``[0, 1]``.  ``0`` gives a pure Gaussian,
        ``1`` a pure Lorentzian.
    """
    eta = float(np.clip(eta, 0.0, 1.0))
    g = gaussian(x, center, fwhm, amplitude)
    lor = lorentzian(x, center, fwhm, amplitude)
    return eta * lor + (1.0 - eta) * g


def pearson_vii(
    x: np.ndarray,
    center: float,
    fwhm: float,
    amplitude: float,
    shape: float = 2.0,
) -> np.ndarray:
    """Normalised Pearson VII peak.

    .. math::

        P(x) = A \\cdot N \\cdot
               \\left[1 + \\left(\\frac{2\\sqrt{2^{1/m}-1}}{w}(x-c)\\right)^2\\right]^{-m}

    where *w* is the FWHM, *m* (``shape``) controls the shape, and the
    normalisation

    .. math::

        N = \\frac{2\\sqrt{2^{1/m}-1}\\,\\Gamma(m)}
                  {w\\,\\sqrt{\\pi}\\,\\Gamma(m-1/2)}

    ensures the integral equals *amplitude*.  ``m → ∞`` approaches a
    Gaussian, ``m = 1`` is a Lorentzian.

    Parameters
    ----------
    x, center, fwhm, amplitude:
        As for :func:`gaussian`.
    shape:
        Shape parameter *m* (> 0.5 for a normalisable distribution).
    """
    from scipy.special import gamma as gamma_func

    x = np.asarray(x, dtype=np.float64)
    m = float(shape)
    if m <= 0.5:
        raise ValueError("Pearson VII shape parameter m must be > 0.5")
    w = fwhm
    scale = 2.0 * np.sqrt(2.0 ** (1.0 / m) - 1.0) / w
    # Normalisation constant so the integral equals `amplitude`.
    norm = scale * gamma_func(m) / (np.sqrt(np.pi) * gamma_func(m - 0.5))
    return amplitude * norm * (1.0 + (scale * (x - center)) ** 2) ** (-m)


# Mapping of shape name -> callable for use by profile fitting.
SHAPE_FUNCTIONS = {
    "gaussian": gaussian,
    "lorentzian": lorentzian,
    "pseudo_voigt": pseudo_voigt,
    "pearson_vii": pearson_vii,
}
