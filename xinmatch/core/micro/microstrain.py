"""Micro-strain analysis via the Williamson-Hall method (T11.2).

Implements Match!'s *Crystallite size estimation* (Williamson-Hall tab),
see ``docs/crystallite_size.md``.  The Williamson-Hall (WH) method [1, 2]
separates the two dominant sources of peak broadening — finite crystallite
size (D) and lattice micro-strain (ε) — by linearising their angular
dependence against ``sin θ``.

Williamson-Hall equation
------------------------
The size broadening ``β_D`` and strain broadening ``β_ε`` add (in quadrature
for Gaussian profiles, linearly for Lorentzian).  Assuming the Gaussian
case, the total sample FWHM is::

    β² = (K λ / (D cos θ))² + (4 ε tan θ)²

Multiplying by ``cos θ / λ`` and rearranging gives the *Williamson-Hall
equation*::

    β cos θ / λ  =  K / D  +  4 ε sin θ / λ

where:

* ``β`` is the sample FWHM (radians), after instrumental-broadening
  correction.
* ``θ`` is the Bragg angle (half the diffraction angle 2θ).
* ``λ`` is the wavelength (Å).
* ``D`` is the volume-weighted crystallite size (Å → returned in nm).
* ``ε`` is the micro-strain (dimensionless).
* ``K`` is the Scherrer constant (default 0.9).

Linear regression of ``y = β cos θ / λ`` versus ``x = 4 sin θ / λ``:

* intercept ``c = K / D``  →  ``D = K / c`` (Å, returned in nm)
* slope     ``m = ε``

Instrumental-broadening correction
---------------------------------
Before the WH fit, the instrumental contribution to the peak width must be
removed.  Following Match! and the Caglioti framework, the variances add
quadratically (Gaussian profile assumption)::

    β_sample² = β_observed² − β_instrumental²

The instrumental FWHM at each peak's 2θ is either supplied directly or
interpolated from a (2θ, FWHM) standard table (e.g. LaB₆ or Si).

References
----------
[1] G.K. Williamson, W.H. Hall, "X-ray line broadening from forged
    aluminium and wolfram", *Acta Metall.* **1** (1953), 22-31.
[2] C.E. Warren, B.L. Averbach, "The effect of cold-work distortion on the
    widths of X-ray diffraction lines", *J. Appl. Phys.* **23** (1952),
    497-503.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from xinmatch.core.model import Peak

# Radians per degree.
_DEG2RAD = float(np.pi) / 180.0


@dataclass
class MicrostrainResult:
    """Williamson-Hall micro-strain analysis result.

    Attributes
    ----------
    crystallite_size_nm:
        Volume-weighted crystallite size ``D`` (nm) from the WH intercept.
        ``None`` if the intercept is non-positive (degenerate fit).
    microstrain:
        Lattice micro-strain ``ε`` (dimensionless) from the WH slope.
    intercept:
        Raw linear-fit intercept ``= K / D`` (Å⁻¹).
    slope:
        Raw linear-fit slope ``= ε`` (dimensionless).
    r_squared:
        Coefficient of determination ``R²`` of the linear fit.
    n_peaks:
        Number of peaks used in the fit.
    x_values:
        ``4 sin θ / λ`` (Å⁻¹) — independent variable.
    y_values:
        ``β cos θ / λ`` (Å⁻¹) — dependent variable.
    sample_fwhm_deg:
        Sample FWHM (degrees 2θ) after instrumental correction, per peak.
    instrumental_corrected:
        ``True`` if instrumental-broadening correction was applied.
    """

    crystallite_size_nm: float | None
    microstrain: float
    intercept: float
    slope: float
    r_squared: float
    n_peaks: int
    x_values: np.ndarray
    y_values: np.ndarray
    sample_fwhm_deg: np.ndarray
    instrumental_corrected: bool


def instrumental_corrected_fwhm(
    observed_fwhm_deg: float | Sequence[float],
    instrumental_fwhm_deg: float | Sequence[float],
) -> np.ndarray | float:
    """Remove the instrumental broadening contribution from observed FWHM.

    Uses the Gaussian (quadratic) quadrature formula::

        β_sample² = β_observed² − β_instrumental²

    ``β_sample`` is set to ``0`` if ``β_instrumental ≥ β_observed``
    (the instrumental broadening exceeds the observed — a physically
    degenerate case that is clipped rather than producing a NaN).

    Parameters
    ----------
    observed_fwhm_deg:
        Observed peak FWHM(s) in degrees 2θ.
    instrumental_fwhm_deg:
        Instrumental FWHM(s) at the corresponding 2θ, in degrees 2θ.

    Returns
    -------
    numpy.ndarray or float
        Sample FWHM(s) in degrees 2θ, same shape as the input.  A scalar
        float is returned when both inputs are scalar.
    """
    obs = np.asarray(observed_fwhm_deg, dtype=np.float64)
    inst = np.asarray(instrumental_fwhm_deg, dtype=np.float64)
    if np.any(obs < 0):
        raise ValueError("observed FWHM must be non-negative")
    if np.any(inst < 0):
        raise ValueError("instrumental FWHM must be non-negative")

    var = np.maximum(obs ** 2 - inst ** 2, 0.0)
    sample = np.sqrt(var)

    # Return a scalar if the inputs were scalar.
    if sample.ndim == 0:
        return float(sample)
    return sample


def williamson_hall(
    fwhm_deg: Sequence[float],
    two_theta_deg: Sequence[float],
    wavelength_angstrom: float,
    *,
    k: float = 0.9,
    instrumental_fwhm: Sequence[float] | None = None,
) -> MicrostrainResult:
    """Williamson-Hall analysis for crystallite size and micro-strain.

    Fits the Williamson-Hall equation::

        β cos θ / λ  =  K / D  +  ε · (4 sin θ / λ)

    by ordinary-least-squares linear regression of ``y = β cos θ / λ``
    versus ``x = 4 sin θ / λ``:

    * ``intercept c = K / D`` → ``D = K / c`` (Å, returned in nm)
    * ``slope     m = ε``     (micro-strain, dimensionless)

    Parameters
    ----------
    fwhm_deg:
        Observed peak FWHM values in **degrees 2θ**.  Must be positive.
    two_theta_deg:
        Peak positions in **degrees 2θ**.  Must be in ``(0, 180)``.
    wavelength_angstrom:
        Wavelength in Å (e.g. Cu Kα1 = 1.5406).
    k:
        Scherrer constant (default 0.9).
    instrumental_fwhm:
        Optional instrumental FWHM(s) in degrees 2θ, one per peak.  If
        provided, the sample FWHM is computed via Gaussian quadrature
        (``β_sample² = β_obs² − β_inst²``) before the WH fit.  If ``None``
        (default) the observed FWHM is used as-is (no instrumental
        correction).

    Returns
    -------
    MicrostrainResult
        Crystallite size (nm), micro-strain, fit statistics, and the
        ``x`` / ``y`` regression arrays.

    Raises
    ------
    ValueError
        If the input arrays have mismatched lengths, contain fewer than
        two points, contain non-positive FWHM / out-of-range 2θ, or if
        the wavelength or Scherrer constant is non-positive.
    """
    n = len(fwhm_deg)
    if n != len(two_theta_deg):
        raise ValueError(
            f"fwhm_deg and two_theta_deg must have the same length: "
            f"got {n} and {len(two_theta_deg)}"
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

    obs_fwhm = np.asarray(fwhm_deg, dtype=np.float64)
    two_theta = np.asarray(two_theta_deg, dtype=np.float64)

    if np.any(obs_fwhm <= 0):
        raise ValueError("All observed FWHM values must be positive")
    if np.any(two_theta <= 0) or np.any(two_theta >= 180):
        raise ValueError("All 2θ values must be in (0, 180)")

    if instrumental_fwhm is not None:
        inst = np.asarray(instrumental_fwhm, dtype=np.float64)
        if inst.size != n:
            raise ValueError(
                f"instrumental_fwhm must have the same length ({n}) as "
                f"fwhm_deg, got {inst.size}"
            )
        if np.any(inst < 0):
            raise ValueError(
                "All instrumental FWHM values must be non-negative"
            )
        sample_fwhm = instrumental_corrected_fwhm(obs_fwhm, inst)
        # Replace any zero sample FWHM with a small positive value to
        # avoid division-by-zero downstream.  The caller should be aware
        # that these peaks carry no size/strain information.
        sample_fwhm = np.where(sample_fwhm > 0, sample_fwhm, 1e-6)
        corrected = True
    else:
        sample_fwhm = obs_fwhm.copy()
        corrected = False

    theta_rad = 0.5 * two_theta * _DEG2RAD
    cos_theta = np.cos(theta_rad)
    sin_theta = np.sin(theta_rad)

    if np.any(cos_theta <= 0):
        raise ValueError("cos(theta) is non-positive for at least one peak")

    beta_rad = sample_fwhm * _DEG2RAD
    # y = β cos θ / λ  (Å⁻¹)
    y = beta_rad * cos_theta / wavelength_angstrom
    # x = 4 sin θ / λ  (Å⁻¹)
    x = 4.0 * sin_theta / wavelength_angstrom

    # Ordinary least squares: y = slope * x + intercept.
    x_mean = float(x.mean())
    y_mean = float(y.mean())
    ss_xx = float(np.sum((x - x_mean) ** 2))
    if ss_xx <= 0:
        raise ValueError(
            "All x values are identical (sin θ constant) — cannot fit a "
            "line.  Need peaks at different 2θ angles."
        )
    ss_xy = float(np.sum((x - x_mean) * (y - y_mean)))
    slope = ss_xy / ss_xx
    intercept = y_mean - slope * x_mean

    # R² (coefficient of determination).
    y_fit = slope * x + intercept
    ss_res = float(np.sum((y - y_fit) ** 2))
    ss_tot = float(np.sum((y - y_mean) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0

    # Crystallite size from intercept: D = K / c (Å).
    if intercept > 0:
        d_angstrom = k / intercept
        d_nm = d_angstrom / 10.0
    else:
        d_nm = None

    return MicrostrainResult(
        crystallite_size_nm=d_nm,
        microstrain=float(slope),
        intercept=float(intercept),
        slope=float(slope),
        r_squared=float(r_squared),
        n_peaks=n,
        x_values=x,
        y_values=y,
        sample_fwhm_deg=sample_fwhm,
        instrumental_corrected=corrected,
    )


def williamson_hall_from_peaks(
    peaks: Sequence[Peak],
    wavelength_angstrom: float,
    *,
    k: float = 0.9,
    instrumental_peaks: Sequence[Peak] | None = None,
) -> MicrostrainResult:
    """Williamson-Hall analysis from a list of :class:`Peak` objects.

    Convenience wrapper around :func:`williamson_hall` that extracts the
    FWHM and 2θ from :class:`~xinmatch.core.model.Peak` objects.  Peaks
    without a fitted FWHM (``fwhm is None`` or ``fwhm <= 0``) are skipped
    silently.

    If ``instrumental_peaks`` is provided, the instrumental FWHM at each
    sample peak's 2θ is obtained by linear interpolation of the
    instrumental peak list (2θ → FWHM).

    Parameters
    ----------
    peaks:
        Sample peaks (must have ``fwhm`` and ``two_theta`` set).
    wavelength_angstrom:
        Wavelength in Å.
    k:
        Scherrer constant (default 0.9).
    instrumental_peaks:
        Optional instrumental-standard peaks (2θ → FWHM) for
        instrumental-broadening correction.

    Returns
    -------
    MicrostrainResult
    """
    sample_peaks = [p for p in peaks if p.fwhm is not None and p.fwhm > 0]
    if len(sample_peaks) < 2:
        raise ValueError(
            f"Need at least 2 peaks with valid FWHM, got {len(sample_peaks)}"
        )

    fwhm_list = [p.fwhm for p in sample_peaks]
    tt_list = [p.two_theta for p in sample_peaks]

    inst_fwhm = None
    if instrumental_peaks is not None:
        inst_peaks = [p for p in instrumental_peaks
                       if p.fwhm is not None and p.fwhm > 0]
        if len(inst_peaks) >= 2:
            inst_tt = np.array([p.two_theta for p in inst_peaks])
            inst_fw = np.array([p.fwhm for p in inst_peaks])
            order = np.argsort(inst_tt)
            inst_tt = inst_tt[order]
            inst_fw = inst_fw[order]
            inst_fwhm = np.interp(tt_list, inst_tt, inst_fw).tolist()

    return williamson_hall(
        fwhm_list,
        tt_list,
        wavelength_angstrom,
        k=k,
        instrumental_fwhm=inst_fwhm,
    )


# Convenient alias.
compute_microstrain = williamson_hall
