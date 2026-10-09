"""Profile / structure refinement engine (Phase 10 / T10.1-T10.4).

GUI-free implementation of the reference software's *Tools → Pattern decomposition (Le Bail)*
and *Quantify → Rietveld (FullProf)* commands
(``docs/LeBail.md``, ``docs/Rietveld.md``).  Unlike the reference software, which shells out
to FullProf, XinMatch ships a self-contained implementation built on
:mod:`scipy.optimize`.

Submodules
----------
peak_model
    Peak-shape model: Caglioti FWHM, asymmetric pseudo-Voigt,
    and the :class:`PeakModel` container used by both Le Bail and Rietveld.
structure_factor
    Atomic scattering factors, Debye--Waller factor, Lorentz--polarisation
    factor, the structure factor ``|F|²`` and reflection multiplicity.
le_bail
    Le Bail whole-pattern decomposition (intensity extraction without
    atomic coordinates).
rietveld
    Rietveld refinement skeleton (scale, zero-point, cell, Caglioti U/V/W).
"""

from .peak_model import PeakModel, asymmetric_pseudo_voigt, caglioti_fwhm
from .structure_factor import (
    Atom,
    atomic_scattering_factor,
    debye_waller_factor,
    lorentz_polarization,
    multiplicity,
    structure_factor,
)

__all__ = [
    # peak_model
    "PeakModel",
    "asymmetric_pseudo_voigt",
    "caglioti_fwhm",
    # structure_factor
    "Atom",
    "atomic_scattering_factor",
    "debye_waller_factor",
    "lorentz_polarization",
    "multiplicity",
    "structure_factor",
]
