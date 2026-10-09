"""Rietveld refinement skeleton (T10.4).

A self-contained Rietveld refinement (Rietveld 1967, 1969) that refines
the *overall* profile parameters — scale factor, zero-point shift, unit
cell and Caglioti U/V/W — against a powder pattern.  Atomic coordinates
are **not** refined in this skeleton; if the :class:`Entry` carries atoms
the structure factor is evaluated, otherwise the entry's tabulated
``d_spacings``/``intensities`` are used as fixed Bragg intensities.

This corresponds to the first few cycles of the reference software's Rietveld run
(``docs/Rietveld.md``, ``docs/Rietveld_Auto_Par.md``): zero point → cell
→ U/V/W, before turning on atomic parameters.

References
----------
* H.M. Rietveld, Acta Cryst. 22 (1967) 151-152; J. Appl. Cryst. 2 (1969) 65-71.
* R.A. Young (ed.), "The Rietveld Method", IUCr/OUP 1993.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import least_squares

from xinmatch.core.index.lattice import compute_d
from xinmatch.core.model.entry import CellParams, Entry
from xinmatch.core.model.pattern import Pattern

from .peak_model import PeakModel
from .structure_factor import Atom, multiplicity, structure_factor

_DEG2RAD = math.pi / 180.0


@dataclass
class RietveldResult:
    """Outcome of a Rietveld refinement.

    Attributes
    ----------
    rwp:
        Weighted profile R-factor (fraction).
    rp:
        Profile R-factor (fraction).
    chi2:
        Reduced chi-squared.
    scale:
        Refined overall scale factor.
    zero_shift:
        Refined zero-point 2θ shift (degrees).
    cell:
        Refined unit-cell parameters.
    peak_model:
        Peak model with refined Caglioti U/V/W.
    fitted_pattern:
        Calculated pattern on the same 2θ grid as the input.
    """

    rwp: float
    rp: float
    chi2: float
    scale: float
    zero_shift: float
    cell: CellParams
    peak_model: PeakModel
    fitted_pattern: Pattern


def _two_theta_from_d(d: float, wavelength: float) -> float:
    sin_theta = wavelength / (2.0 * d)
    sin_theta = min(max(sin_theta, -1.0), 1.0)
    return math.degrees(2.0 * math.asin(sin_theta))


class RietveldRefinement:
    """Rietveld refinement of scale, zero point, cell and Caglioti U/V/W.

    Parameters
    ----------
    pattern:
        Experimental (background-subtracted) powder pattern.
    entry:
        Reference entry.  If ``entry.atoms`` is present (a list of
        :class:`Atom`), structure factors are computed; otherwise the
        entry's ``d_spacings`` and ``intensities`` are used as fixed
        Bragg intensities.
    peak_model:
        Initial peak-shape model.
    wavelength:
        Radiation wavelength in Å.
    """

    def __init__(
        self,
        pattern: Pattern,
        entry: Entry,
        peak_model: PeakModel,
        *,
        wavelength: float,
    ) -> None:
        self.pattern = pattern
        self.entry = entry
        self.peak_model = peak_model
        self.wavelength = float(wavelength)

        self._tth = pattern.two_theta
        self._y_obs = pattern.intensity

        # Determine the reflection list.
        self._atoms: list[Atom] | None = getattr(entry, "atoms", None)
        self._cell = entry.cell if entry.cell is not None else CellParams(1.0, 1.0, 1.0)

        if self._atoms:
            # Generate hkl from the cell up to the max 2θ of the pattern.
            self._hkls = self._generate_hkl_from_cell()
        else:
            # Use the entry's tabulated (hkl, d, I) if hkl is present,
            # otherwise just the d/I list.
            if entry.hkl is not None:
                self._hkls = list(entry.hkl)
                self._ref_d = np.asarray(entry.d_spacings, dtype=np.float64)
                self._ref_i = np.asarray(entry.intensities, dtype=np.float64)
            else:
                self._hkls = []
                self._ref_d = np.asarray(entry.d_spacings, dtype=np.float64)
                self._ref_i = np.asarray(entry.intensities, dtype=np.float64)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _generate_hkl_from_cell(self) -> list[tuple[int, int, int]]:
        max_tth = float(self._tth.max()) if self._tth.size else 90.0
        d_min = self.wavelength / (2.0 * math.sin(_DEG2RAD * max_tth / 2.0))
        hkls: list[tuple[int, int, int]] = []
        max_idx = 30
        for h in range(-max_idx, max_idx + 1):
            for k in range(-max_idx, max_idx + 1):
                for ll in range(-max_idx, max_idx + 1):
                    if h == 0 and k == 0 and ll == 0:
                        continue
                    if (h, k, ll) > (-h, -k, -ll):
                        continue
                    try:
                        d = compute_d((h, k, ll), self._cell)
                    except ValueError:
                        continue
                    if d >= d_min:
                        hkls.append((h, k, ll))
        return hkls

    def _bragg_intensities(self, cell: CellParams) -> tuple[np.ndarray, np.ndarray]:
        """Return (positions_2theta, intensities) for all reflections.

        If atoms are available, ``I = |F|² · m · LP``.  Otherwise the
        entry's tabulated intensities are used (only the 2θ positions are
        recomputed from the refined cell).
        """
        if self._atoms:
            positions: list[float] = []
            ints: list[float] = []
            for hkl in self._hkls:
                try:
                    d = compute_d(hkl, cell)
                except ValueError:
                    continue
                tth = _two_theta_from_d(d, self.wavelength)
                if tth < self._tth.min() - 5.0 or tth > self._tth.max() + 5.0:
                    continue
                f = structure_factor(hkl, self._atoms, cell, wavelength=self.wavelength)
                f_sq = float((f * f.conjugate()).real)
                lp = (1.0 + math.cos(2.0 * _DEG2RAD * tth) ** 2) / (
                    math.sin(_DEG2RAD * tth / 2.0) * math.cos(_DEG2RAD * tth / 2.0) + 1e-12
                )
                m = multiplicity(hkl, self._crystal_system(cell))
                positions.append(tth)
                ints.append(f_sq * m * lp)
            return np.array(positions), np.array(ints)

        # No atoms: use tabulated intensities, recompute 2θ from refined cell
        # only if hkl is available; otherwise keep the tabulated d-spacings.
        if self._hkls:
            positions = []
            for hkl in self._hkls:
                try:
                    d = compute_d(hkl, cell)
                except ValueError:
                    positions.append(0.0)
                    continue
                positions.append(_two_theta_from_d(d, self.wavelength))
            return np.array(positions), self._ref_i.copy()

        positions = np.array(
            [_two_theta_from_d(float(d), self.wavelength) for d in self._ref_d]
        )
        return positions, self._ref_i.copy()

    @staticmethod
    def _crystal_system(cell: CellParams) -> str:
        """Best-effort crystal-system guess from cell parameters."""
        a, b, c = cell.a, cell.b, cell.c
        alpha, beta, gamma = cell.alpha, cell.beta, cell.gamma
        ninety = [abs(alpha - 90.0) < 0.5, abs(beta - 90.0) < 0.5, abs(gamma - 90.0) < 0.5]
        if a == b == c and all(ninety):
            return "cubic"
        if a == b and all(ninety) and abs(c - a) > 0.5:
            return "tetragonal"
        if a == b and abs(gamma - 120.0) < 0.5 and ninety[0] and ninety[1]:
            return "hexagonal"
        if all(ninety) and not (a == b == c):
            return "orthorhombic"
        if ninety[0] and ninety[2] and not ninety[1]:
            return "monoclinic"
        return "triclinic"

    # ------------------------------------------------------------------
    # Model evaluation
    # ------------------------------------------------------------------
    def _calc_pattern(
        self,
        params: np.ndarray,
    ) -> tuple[np.ndarray, float, float, CellParams, PeakModel]:
        scale = params[0]
        zero_shift = params[1]
        a, b, c = params[2], params[3], params[4]
        alpha, beta, gamma = params[5], params[6], params[7]
        u, v, w = params[8], params[9], params[10]

        cell = CellParams(a, b, c, alpha, beta, gamma)
        pm = PeakModel(
            shape=self.peak_model.shape,
            eta=self.peak_model.eta,
            asymmetry=self.peak_model.asymmetry,
            caglioti_uvw=(u, v, w),
        )

        positions, intensities = self._bragg_intensities(cell)
        y_calc = np.zeros_like(self._tth)
        for pos, inten in zip(positions, intensities, strict=True):
            if inten <= 0:
                continue
            tth_pos = pos + zero_shift
            if tth_pos < self._tth[0] - 5.0 or tth_pos > self._tth[-1] + 5.0:
                continue
            fwhm = pm.fwhm(tth_pos)
            if fwhm <= 0.0:
                fwhm = 0.05
            y_calc += scale * inten * pm.shape_function(self._tth, tth_pos, fwhm, 1.0)
        return y_calc, scale, zero_shift, cell, pm

    def _residuals(self, params: np.ndarray) -> np.ndarray:
        y_calc, *_ = self._calc_pattern(params)
        return self._y_obs - y_calc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fit(self, *, n_iter: int = 50) -> RietveldResult:
        """Run the refinement.

        Parameters
        ----------
        n_iter:
            Maximum number of least-squares iterations.

        Returns
        -------
        RietveldResult
        """
        u0, v0, w0 = self.peak_model.caglioti_uvw
        x0 = np.array(
            [
                1.0,                      # scale
                0.0,                      # zero shift
                self._cell.a, self._cell.b, self._cell.c,
                self._cell.alpha, self._cell.beta, self._cell.gamma,
                u0, v0, w0,
            ],
            dtype=np.float64,
        )
        bounds_lo = np.array(
            [1e-6, -2.0, 0.1, 0.1, 0.1, 10.0, 10.0, 10.0, -1.0, -1.0, 1e-4]
        )
        bounds_hi = np.array(
            [1e6, 2.0, 1e4, 1e4, 1e4, 170.0, 170.0, 170.0, 10.0, 10.0, 10.0]
        )

        result = least_squares(
            self._residuals,
            x0=x0,
            bounds=(bounds_lo, bounds_hi),
            method="trf",
            max_nfev=n_iter * 20,
        )

        y_calc, scale, zero_shift, cell, pm = self._calc_pattern(result.x)

        rwp = self._compute_rwp(y_calc)
        rp = self._compute_rp(y_calc)
        chi2 = self._compute_chi2(y_calc)

        fitted = Pattern(
            two_theta=self._tth.copy(),
            intensity=y_calc,
            wavelength=self.pattern.wavelength,
            step=self.pattern.step,
        )
        return RietveldResult(
            rwp=rwp,
            rp=rp,
            chi2=chi2,
            scale=float(scale),
            zero_shift=float(zero_shift),
            cell=cell,
            peak_model=pm,
            fitted_pattern=fitted,
        )

    def compute_rwp(self) -> float:
        """Weighted profile R-factor using Poisson-like weights.

        .. math::

            R_{wp} = \\sqrt{\\frac{\\sum w_i (y_i^{obs} - y_i^{calc})^2}
                                  {\\sum w_i (y_i^{obs})^2}}

        with :math:`w_i = 1 / \\max(y_i^{obs}, \\sigma_{noise}^2)`.
        """
        y_calc, *_ = self._calc_pattern(
            np.array([
                1.0, 0.0,
                self._cell.a, self._cell.b, self._cell.c,
                self._cell.alpha, self._cell.beta, self._cell.gamma,
                *self.peak_model.caglioti_uvw,
            ])
        )
        return self._compute_rwp(y_calc)

    def _compute_rwp(self, y_calc: np.ndarray) -> float:
        noise = float(np.median(np.abs(np.diff(self._y_obs)))) / 1.4826 if self._y_obs.size > 1 else 1.0
        noise = max(noise, 1e-6)
        variance = np.maximum(self._y_obs, noise ** 2)
        weight = 1.0 / np.sqrt(variance)
        num = np.sum((weight * (self._y_obs - y_calc)) ** 2)
        den = np.sum((weight * self._y_obs) ** 2)
        return float(np.sqrt(num / den)) if den > 0 else 1.0

    def compute_rp(self) -> float:
        """Profile R-factor ``Rp = Σ|y_obs - y_calc| / Σ|y_obs|``."""
        y_calc, *_ = self._calc_pattern(
            np.array([
                1.0, 0.0,
                self._cell.a, self._cell.b, self._cell.c,
                self._cell.alpha, self._cell.beta, self._cell.gamma,
                *self.peak_model.caglioti_uvw,
            ])
        )
        return self._compute_rp(y_calc)

    def _compute_rp(self, y_calc: np.ndarray) -> float:
        num = np.sum(np.abs(self._y_obs - y_calc))
        den = np.sum(np.abs(self._y_obs))
        return float(num / den) if den > 0 else 1.0

    def compute_chi2(self) -> float:
        """Reduced chi-squared ``χ² = Σ w_i (y_obs - y_calc)² / (N - P)``."""
        y_calc, *_ = self._calc_pattern(
            np.array([
                1.0, 0.0,
                self._cell.a, self._cell.b, self._cell.c,
                self._cell.alpha, self._cell.beta, self._cell.gamma,
                *self.peak_model.caglioti_uvw,
            ])
        )
        return self._compute_chi2(y_calc)

    def _compute_chi2(self, y_calc: np.ndarray) -> float:
        noise = float(np.median(np.abs(np.diff(self._y_obs)))) / 1.4826 if self._y_obs.size > 1 else 1.0
        noise = max(noise, 1e-6)
        variance = np.maximum(self._y_obs, noise ** 2)
        weight = 1.0 / variance
        n_params = 11
        dof = max(self._y_obs.size - n_params, 1)
        chi2 = float(np.sum(weight * (self._y_obs - y_calc) ** 2) / dof)
        return chi2
