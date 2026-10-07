"""Peak-shape model for Le Bail / Rietveld refinement (T10.1).

Implements the three ingredients Match!/FullProf use to describe a powder
peak profile:

1. **Caglioti width model** — the FWHM as a function of 2θ follows
   ``H² = U·tan²θ + V·tanθ + W`` (Caglioti, Paoletti & Ricci 1958).
2. **pseudo-Voigt shape** — a Gaussian/Lorentzian mixture with mixing
   parameter ``η`` (Ida, Toraya & Marumo 2000).
3. **Asymmetry** — low-2θ axial-divergence asymmetry implemented as
   different left/right half-widths.

These mirror the parameters turned on in Match!'s *Parameter Turn-On*
dialog (``docs/Rietveld_ParTurnOn.md``): U, V, W, ``η`` (``X1``/``X2``)
and the asymmetry coefficients.

References
----------
* G. Caglioti, A. Paoletti, F.P. Ricci, Nucl. Instr. 3 (1958) 223-228.
* T. Ida, S. Toraya, H. Marumo, J. Appl. Cryst. 33 (2000) 1311-1316.
* J. Rodriguez-Carvajal, Physica B 192 (1993) 55-69 (FullProf).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from xinmatch.core.peak.shapes import gaussian, lorentzian

_DEG2RAD = np.pi / 180.0


def caglioti_fwhm(two_theta_deg: float, u: float, v: float, w: float) -> float:
    """Caglioti FWHM as a function of scattering angle.

    .. math::

        H(2\\theta)^2 = U\\,\\tan^2\\theta + V\\,\\tan\\theta + W

    where :math:`\\theta = 2\\theta / 2`.  ``U``, ``V``, ``W`` are the
    Caglioti half-width parameters (Match!/FullProf *U, V, W*).

    Parameters
    ----------
    two_theta_deg:
        Scattering angle 2θ in degrees.
    u, v, w:
        Caglioti parameters.

    Returns
    -------
    float
        Full width at half maximum in degrees 2θ.  Returns ``0.0`` if the
        radicand is negative (non-physical parameter combination).
    """
    theta = _DEG2RAD * float(two_theta_deg) / 2.0
    tan_theta = np.tan(theta)
    h_sq = u * tan_theta * tan_theta + v * tan_theta + w
    if h_sq <= 0.0:
        return 0.0
    return float(np.sqrt(h_sq))


def asymmetric_pseudo_voigt(
    two_theta: np.ndarray,
    center: float,
    fwhm: float,
    eta: float,
    asymmetry: float = 0.0,
) -> np.ndarray:
    """Asymmetric pseudo-Voigt peak normalised to **unit area**.

    The asymmetry is modelled by splitting the peak at its centre and using
    different half-widths on the low- and high-angle sides:

    .. math::

        H_{\\text{left}}  = H \\cdot (1 - \\alpha), \\qquad
        H_{\\text{right}} = H \\cdot (1 + \\alpha)

    with :math:`\\alpha \\in (-1, 1)`.  Each side is a half pseudo-Voigt
    (area = 1/2), so the total integral equals 1.  ``alpha = 0`` reduces
    to the ordinary (symmetric) pseudo-Voigt.

    Parameters
    ----------
    two_theta:
        2θ grid in degrees.
    center:
        Peak centre (degrees 2θ).
    fwhm:
        Symmetric FWHM used as the reference width (degrees 2θ).
    eta:
        Lorentzian fraction in ``[0, 1]``.
    asymmetry:
        Asymmetry parameter ``alpha`` in ``(-1, 1)``.  Positive values make
        the low-angle side broader (the common axial-divergence case).

    Returns
    -------
    numpy.ndarray
        Peak shape with unit area (multiply by the integrated intensity to
        get the contribution to the calculated profile).
    """
    x = np.asarray(two_theta, dtype=np.float64)
    eta = float(np.clip(eta, 0.0, 1.0))
    alpha = float(np.clip(asymmetry, -0.99, 0.99))

    fwhm_left = fwhm * (1.0 - alpha)
    fwhm_right = fwhm * (1.0 + alpha)

    # Each full pseudo-Voigt has area = 1; we keep only the appropriate half
    # (area 1/2 each) so the composite integrates to 1.
    g_l = gaussian(x, center, fwhm_left, 1.0)
    l_l = lorentzian(x, center, fwhm_left, 1.0)
    pv_left = eta * l_l + (1.0 - eta) * g_l

    g_r = gaussian(x, center, fwhm_right, 1.0)
    l_r = lorentzian(x, center, fwhm_right, 1.0)
    pv_right = eta * l_r + (1.0 - eta) * g_r

    left_mask = x < center
    y = np.where(left_mask, pv_left, pv_right)
    return y


@dataclass
class PeakModel:
    """Container describing the peak profile for a refinement.

    Mirrors the peak-shape settings in Match!'s Rietveld options
    (``docs/options_Rietveld.md``).

    Attributes
    ----------
    shape:
        Peak shape name.  Currently only ``'pseudo_voigt'`` is supported
        (FullProf's default for powder work).
    eta:
        pseudo-Voigt Lorentzian fraction ``η`` in ``[0, 1]``.
    asymmetry:
        Asymmetry parameter ``α`` in ``(-1, 1)``.
    caglioti_uvw:
        Caglioti parameters ``(U, V, W)`` for the 2θ-dependent FWHM.
    """

    shape: str = "pseudo_voigt"
    eta: float = 0.5
    asymmetry: float = 0.0
    caglioti_uvw: tuple[float, float, float] = (0.0, 0.0, 0.1)

    def __post_init__(self) -> None:
        if self.shape != "pseudo_voigt":
            raise NotImplementedError(
                f"peak shape {self.shape!r} not implemented; "
                "only 'pseudo_voigt' is supported"
            )
        self.eta = float(np.clip(self.eta, 0.0, 1.0))
        self.asymmetry = float(np.clip(self.asymmetry, -0.99, 0.99))
        if len(self.caglioti_uvw) != 3:
            raise ValueError("caglioti_uvw must be a (U, V, W) tuple of length 3")

    def fwhm(self, two_theta_deg: float) -> float:
        """Return the Caglioti FWHM at *two_theta_deg* (degrees 2θ)."""
        u, v, w = self.caglioti_uvw
        return caglioti_fwhm(two_theta_deg, u, v, w)

    def shape_function(
        self,
        two_theta: np.ndarray,
        center: float,
        fwhm: float,
        intensity: float,
    ) -> np.ndarray:
        """Evaluate the peak shape at *two_theta*.

        Returns ``intensity * asymmetric_pseudo_voigt(...)``, i.e. the peak
        contribution whose integral equals *intensity*.
        """
        return intensity * asymmetric_pseudo_voigt(
            two_theta, center, fwhm, self.eta, self.asymmetry
        )
