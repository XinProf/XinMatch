"""Le Bail whole-pattern decomposition (T10.3).

Implements the Le Bail (1988) / Pawley (1981) method for extracting
integrated reflection intensities ``I(hkl)`` from a powder pattern when
only the unit-cell parameters and peak-shape model are known — *no*
atomic coordinates required.

This is Match!'s *Tools → Pattern decomposition (Le Bail fit) using
FullProf* command (``docs/LeBail.md``), reimplemented natively on top of
:mod:`scipy` rather than shelling out to FullProf.

Algorithm
---------
1. Generate all ``hkl`` reflections whose 2θ falls inside the fitted range.
2. Assign starting intensities (uniform).
3. Compute the full calculated profile as a sum of pseudo-Voigt peaks.
4. Redistribute the observed intensity back to each reflection
   proportionally to its share of the calculated profile
   (Le Bail's "intensity partitioning"):

   .. math::

       I_i^{\\text{new}} = I_i^{\\text{old}} \\sum_x
           \\frac{y_i^{\\text{calc}}(x)}{y^{\\text{calc}}(x)}

5. Repeat from step 3 for ``n_iter`` cycles.

References
----------
* A. Le Bail, H. Duroy, J.L. Fourquet, Mater. Res. Bull. 23 (1988) 447-452.
* G.S. Pawley, J. Appl. Cryst. 14 (1981) 357-361.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from xinmatch.core.index.lattice import compute_d
from xinmatch.core.model.entry import CellParams
from xinmatch.core.model.pattern import Pattern

from .peak_model import PeakModel
from .structure_factor import get_orbit, multiplicity

_DEG2RAD = math.pi / 180.0


def _crystal_system_from_cell(cell: CellParams) -> str:
    """Infer the crystal system from unit-cell parameters (within tolerance)."""
    a, b, c = cell.a, cell.b, cell.c
    alpha, beta, gamma = cell.alpha, cell.beta, cell.gamma
    tol = 1e-3
    deg90 = 90.0
    if (abs(a - b) < tol and abs(b - c) < tol
            and abs(alpha - deg90) < tol and abs(beta - deg90) < tol
            and abs(gamma - deg90) < tol):
        return "cubic"
    if (abs(a - b) < tol and abs(b - c) >= tol
            and abs(alpha - deg90) < tol and abs(beta - deg90) < tol
            and abs(gamma - deg90) < tol):
        return "tetragonal"
    if (abs(a - b) >= tol and abs(b - c) >= tol and abs(a - c) >= tol
            and abs(alpha - deg90) < tol and abs(beta - deg90) < tol
            and abs(gamma - deg90) < tol):
        return "orthorhombic"
    if (abs(a - b) >= tol and abs(b - c) >= tol
            and abs(alpha - deg90) < tol and abs(gamma - deg90) < tol
            and abs(beta - deg90) >= tol):
        return "monoclinic"
    if (abs(a - b) < tol and abs(b - c) < tol
            and abs(alpha - beta) < tol and abs(beta - gamma) < tol
            and abs(alpha - deg90) >= tol):
        return "trigonal"
    if (abs(a - b) < tol and abs(b - c) >= tol
            and abs(alpha - deg90) < tol and abs(beta - deg90) < tol
            and abs(gamma - 120.0) < tol):
        return "hexagonal"
    return "triclinic"


def _generate_hkl(
    cell: CellParams,
    wavelength: float,
    two_theta_range: tuple[float, float],
    crystal_system: str = "cubic",
    max_index: int = 30,
) -> list[tuple[int, int, int]]:
    """Generate one representative ``hkl`` per symmetry orbit in the 2θ range.

    Uses a simple cubic bounding-box search over ``h, k, l ∈ [-max_index,
    max_index]`` and keeps only the lexicographically smallest reflection of
    each symmetry orbit (so equivalent reflections that overlap at the same
    d-spacing contribute to a single peak).  ``(0,0,0)`` is excluded.
    """
    lo, hi = two_theta_range
    sin_lo = math.sin(_DEG2RAD * lo / 2.0)
    sin_hi = math.sin(_DEG2RAD * hi / 2.0)
    # d = λ / (2 sinθ); valid when sinθ ≤ 1.
    d_max = wavelength / (2.0 * max(sin_lo, 1e-12))
    d_min = wavelength / (2.0 * min(sin_hi, 1.0)) if sin_hi <= 1.0 else 0.0

    seen_orbits: set[frozenset] = set()
    hkls: list[tuple[int, int, int]] = []
    for h in range(-max_index, max_index + 1):
        for k in range(-max_index, max_index + 1):
            for ll in range(-max_index, max_index + 1):
                if h == 0 and k == 0 and ll == 0:
                    continue
                try:
                    d = compute_d((h, k, ll), cell)
                except ValueError:
                    continue
                if not (d_min <= d <= d_max):
                    continue
                # Keep only one representative per orbit.
                orbit = get_orbit((h, k, ll), crystal_system)
                key = frozenset(orbit)
                if key in seen_orbits:
                    continue
                seen_orbits.add(key)
                # Representative: lexicographically smallest in the orbit.
                rep = min(orbit)
                hkls.append(rep)
    return hkls


def _two_theta_from_d(d: float, wavelength: float) -> float:
    """Bragg 2θ (degrees) from d-spacing."""
    sin_theta = wavelength / (2.0 * d)
    sin_theta = min(max(sin_theta, -1.0), 1.0)
    return math.degrees(2.0 * math.asin(sin_theta))


def le_bail(
    pattern: Pattern,
    cell: CellParams,
    peak_model: PeakModel,
    *,
    wavelength: float,
    n_iter: int = 10,
    two_theta_range: tuple[float, float] = (5.0, 90.0),
) -> dict[str, Any]:
    """Run a Le Bail pattern decomposition.

    Parameters
    ----------
    pattern:
        Experimental (background-subtracted) diffraction pattern.
    cell:
        Unit-cell parameters of the phase.
    peak_model:
        Peak-shape model (Caglioti U/V/W, pseudo-Voigt η, asymmetry).
    wavelength:
        Radiation wavelength in Å.
    n_iter:
        Number of Le Bail intensity-redistribution cycles.
    two_theta_range:
        ``(2θ_min, 2θ_max)`` in degrees — only reflections inside this
        window are fitted.

    Returns
    -------
    dict
        ``{"intensities": {hkl: I}, "rwp": float, "cell": CellParams,
        "converged": bool}``.
    """
    tth = pattern.two_theta
    y_obs = pattern.intensity

    # Restrict to the fitted 2θ window.
    mask = (tth >= two_theta_range[0]) & (tth <= two_theta_range[1])
    tth_fit = tth[mask]
    y_fit = y_obs[mask]
    if tth_fit.size < 2:
        return {
            "intensities": {},
            "rwp": 1.0,
            "cell": cell,
            "converged": False,
        }

    crystal_system = _crystal_system_from_cell(cell)
    hkls = _generate_hkl(cell, wavelength, two_theta_range, crystal_system=crystal_system)
    if not hkls:
        return {
            "intensities": {},
            "rwp": 1.0,
            "cell": cell,
            "converged": False,
        }

    mults = np.array([multiplicity(h, crystal_system) for h in hkls], dtype=float)

    # Compute 2θ position and FWHM for each reflection.
    positions = np.array(
        [_two_theta_from_d(compute_d(h, cell), wavelength) for h in hkls]
    )
    fwhms = np.array([peak_model.fwhm(float(p)) for p in positions])

    # Pre-compute the normalised peak shape for each reflection (area = 1).
    # Multiplicity is handled separately: y_calc = Σ_i (I_i * m_i) * P_i(x),
    # so the Le Bail recovers the peak area A_i = I_i * m_i, and we return
    # I_i = A_i / m_i as the per-reflection intensity.
    shape_matrix = np.zeros((len(hkls), tth_fit.size))
    for i, (_h, pos, fwhm) in enumerate(zip(hkls, positions, fwhms, strict=True)):
        if fwhm <= 0.0:
            fwhm = 0.05  # fall-back to avoid zero-width peaks
        shape_matrix[i] = peak_model.shape_function(tth_fit, float(pos), fwhm, 1.0)

    # Initial intensities: distribute the total observed counts uniformly,
    # weighted by the peak shape integral (= 1) so all start equal.
    step = float(np.median(np.diff(tth_fit))) if tth_fit.size > 1 else 0.02
    total_counts = float(np.trapz(y_fit, tth_fit))
    intensities = np.full(len(hkls), total_counts / len(hkls))

    rwp = 1.0
    for _ in range(n_iter):
        # y_calc = Σ_i I_i * P_i(x)
        y_calc = intensities @ shape_matrix
        # Avoid division by zero.
        y_calc_safe = np.where(y_calc > 1e-12, y_calc, 1e-12)
        # Le Bail redistribution (integral form):
        # I_i_new = I_i_old * ∫ [y_obs * P_i / y_calc] dx
        #          ≈ I_i_old * step * Σ_x [y_obs * P_i / y_calc]
        ratio = y_fit / y_calc_safe
        contributions = shape_matrix * ratio[np.newaxis, :]
        intensities = intensities * step * contributions.sum(axis=1)
        # Guard against negative / NaN intensities.
        intensities = np.maximum(intensities, 0.0)

    # Final Rwp.
    y_calc = intensities @ shape_matrix
    num = np.sum((y_fit - y_calc) ** 2)
    den = np.sum(y_fit ** 2)
    rwp = float(np.sqrt(num / den)) if den > 0 else 1.0

    # Convert recovered peak areas A_i back to per-reflection intensities
    # I_i = A_i / m_i.
    per_reflection = intensities / np.maximum(mults, 1.0)

    return {
        "intensities": {h: float(i) for h, i in zip(hkls, per_reflection, strict=True)},
        "rwp": rwp,
        "cell": cell,
        "converged": True,
    }
