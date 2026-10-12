"""Parameter Turn-On refinement strategy (T10.7).

Implements the reference software's *Parameter Turn-On* dialog
(``docs/Rietveld_ParTurnOn.md``): progressively enable refinement of
parameter *groups* in a fixed order, monitoring the weighted profile
R-factor at each stage.  If a stage does not improve Rwp its parameter
changes are rolled back, exactly as in the reference software's interactive dialog.

The default five-stage sequence is::

    Stage 1  Scale          →  refine overall intensity scale
    Stage 2  Background     →  (local refiner has no background; no-op)
    Stage 3  Zero / Lattice →  refine zero-point + unit-cell a,b,c,α,β,γ
    Stage 4  Profile U/V/W  →  refine Caglioti U, V, W
    Stage 5  Atoms          →  (local refiner does not refine atoms; no-op)

Stages 2 and 5 are placeholders: the in-tree
:class:`~xinmatch.core.refine.rietveld.RietveldRefinement` does not yet
model a background polynomial or refine atomic coordinates, so these
stages are no-ops.  They are kept in the schedule because the user-facing
strategy should match the reference software's 5-stage dialog regardless of which
backend engine is plugged in.

References
----------
* L.B. McCusker et al., "Rietveld refinement guidelines", IUCr (1999).
* R.A. Young (ed.), "The Rietveld Method", IUCr/OUP 1993, ch. 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import least_squares

from xinmatch.core.model.entry import Entry
from xinmatch.core.model.pattern import Pattern
from xinmatch.core.refine.peak_model import PeakModel
from xinmatch.core.refine.rietveld import RietveldRefinement, RietveldResult

# ---------------------------------------------------------------------------
# Parameter groups (indices in the 11-vector used by RietveldRefinement)
# ---------------------------------------------------------------------------
#   [0]    scale
#   [1]    zero_shift
#   [2..4] a, b, c
#   [5..7] alpha, beta, gamma
#   [8..10] U, V, W
_PARAM_NAMES: tuple[str, ...] = (
    "scale", "zero_shift",
    "a", "b", "c",
    "alpha", "beta", "gamma",
    "U", "V", "W",
)


# Default 5-stage strategy from the reference software's Parameter Turn-On dialog.
DEFAULT_STAGES: tuple[tuple[str, tuple[int, ...]], ...] = (
    ("scale", (0,)),
    ("background", ()),       # local refiner has no background parameter
    ("zero_lattice", (1, 2, 3, 4, 5, 6, 7)),
    ("profile_uvw", (8, 9, 10)),
    ("atoms", ()),            # local refiner does not refine atoms yet
)


# ---------------------------------------------------------------------------
# Convergence trajectory record
# ---------------------------------------------------------------------------
@dataclass
class TurnOnStep:
    """One stage of the parameter turn-on sequence.

    Attributes
    ----------
    stage_name:
        Name of the stage (e.g. ``'scale'``).
    rwp_before:
        Rwp at the start of this stage (= Rwp from the previous accepted
        stage, or the initial Rwp before any refinement).
    rwp_after:
        Rwp at the end of this stage's Rietveld run.
    accepted:
        ``True`` when ``rwp_after < rwp_before`` (the stage improved the
        fit); the stage's parameter changes are kept.  ``False`` ⇒ the
        stage was rolled back.
    params_enabled:
        Human-readable names of the parameters unlocked at this stage.
    """

    stage_name: str
    rwp_before: float
    rwp_after: float
    accepted: bool
    params_enabled: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parameter-locked Rietveld refinement
# ---------------------------------------------------------------------------
class _ParameterLockedRefinement(RietveldRefinement):
    """Rietveld refinement with per-parameter locking.

    Locked parameters retain their current values: their bounds are
    pinned to ``(x0, x0)`` so the optimizer cannot move them.  This is
    the engine behind the Turn-On strategy — at each stage only a subset
    of parameters is allowed to vary.

    A custom initial vector can be supplied via ``x0_override`` so that
    parameter values refined in a previous accepted stage are carried
    forward as the starting point for the next stage.
    """

    def __init__(
        self,
        pattern: Pattern,
        entry: Entry,
        peak_model: PeakModel,
        *,
        wavelength: float,
        locked_mask: np.ndarray | list[bool] | None = None,
        x0_override: np.ndarray | None = None,
    ) -> None:
        super().__init__(pattern, entry, peak_model, wavelength=wavelength)
        self.locked_mask: np.ndarray
        if locked_mask is None:
            self.locked_mask = np.zeros(11, dtype=bool)
        else:
            self.locked_mask = np.asarray(locked_mask, dtype=bool)
            if self.locked_mask.size != 11:
                raise ValueError(
                    f"locked_mask must have 11 entries, got {self.locked_mask.size}"
                )
        if x0_override is not None:
            x0_override = np.asarray(x0_override, dtype=np.float64)
            if x0_override.size != 11:
                raise ValueError(
                    f"x0_override must have 11 entries, got {x0_override.size}"
                )
        self._x0_override = x0_override

    def _initial_vector(self) -> np.ndarray:
        if self._x0_override is not None:
            return self._x0_override.copy()
        u0, v0, w0 = self.peak_model.caglioti_uvw
        return np.array(
            [
                1.0,                      # scale
                0.0,                      # zero shift
                self._cell.a, self._cell.b, self._cell.c,
                self._cell.alpha, self._cell.beta, self._cell.gamma,
                u0, v0, w0,
            ],
            dtype=np.float64,
        )

    def fit(self, *, n_iter: int = 50) -> RietveldResult:
        """Run the refinement with the configured parameter locks."""
        x0 = self._initial_vector()
        bounds_lo = np.array(
            [1e-6, -2.0, 0.1, 0.1, 0.1, 10.0, 10.0, 10.0, -1.0, -1.0, 1e-4]
        )
        bounds_hi = np.array(
            [1e6, 2.0, 1e4, 1e4, 1e4, 170.0, 170.0, 170.0, 10.0, 10.0, 10.0]
        )
        # Pin locked parameters' bounds to their current values so the
        # optimizer cannot move them.
        for i in range(11):
            if self.locked_mask[i]:
                v = float(x0[i])
                # Use a tiny but non-zero window so trf stays well-posed.
                eps = 1e-12 * max(abs(v), 1.0)
                bounds_lo[i] = v - eps
                bounds_hi[i] = v + eps

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

    def initial_rwp(self) -> float:
        """Rwp using the initial parameter vector (no refinement)."""
        x0 = self._initial_vector()
        y_calc, *_ = self._calc_pattern(x0)
        return self._compute_rwp(y_calc)


# ---------------------------------------------------------------------------
# Turn-on strategy
# ---------------------------------------------------------------------------
class TurnOnStrategy:
    """Parameter Turn-On refinement strategy.

    At each stage a Rietveld run is performed with only that stage's
    parameters unlocked; all other parameters are held at their current
    (initial or previously-refined) values.  If the stage's Rwp is not
    lower than the previous Rwp the stage is *rolled back* — its
    parameter changes are discarded and the previous values are kept.

    Parameters
    ----------
    stages:
        Optional list of ``(stage_name, parameter_indices)`` tuples.  If
        ``None``, :data:`DEFAULT_STAGES` is used (the reference software's 5-stage
        schedule).
    """

    def __init__(
        self,
        stages: list[tuple[str, tuple[int, ...]]] | None = None,
    ) -> None:
        self.stages: list[tuple[str, tuple[int, ...]]] = (
            list(stages) if stages is not None else list(DEFAULT_STAGES)
        )

    def run(
        self,
        pattern: Pattern,
        entry: Entry,
        peak_model: PeakModel,
        *,
        wavelength: float,
        n_iter: int = 20,
        rwp_tolerance: float = 1e-6,
    ) -> list[TurnOnStep]:
        """Execute the parameter turn-on sequence.

        Parameters
        ----------
        pattern:
            Experimental (background-subtracted) diffraction pattern.
        entry:
            Reference entry describing the phase.  May carry ``atoms`` for
            the structure-factor path (see
            :class:`RietveldRefinement`).
        peak_model:
            Initial peak-shape model.
        wavelength:
            Radiation wavelength in Å.
        n_iter:
            Maximum number of least-squares iterations per stage.
        rwp_tolerance:
            Minimum Rwp decrease required to accept a stage.  Stages
            whose Rwp decrease is below this threshold are rolled back.
            The default (1e-6) filters out numerical jitter from
            locked-parameter optimisation steps.

        Returns
        -------
        list[TurnOnStep]
            The convergence trajectory, one record per stage.
        """
        steps: list[TurnOnStep] = []

        # All parameters start locked.
        current_locked = np.ones(11, dtype=bool)
        current_x0: np.ndarray | None = None

        # Pre-estimate the initial scale to help the scale-only stage
        # converge.  Starting from the default scale=1.0 (which can be
        # orders of magnitude too low) with slightly misaligned peaks can
        # cause the trust-region optimiser to diverge.  We estimate the
        # scale from the ratio of observed to model peak heights and start
        # at 10 % of that estimate, giving the scale stage room to improve
        # while keeping the starting point reasonable.
        pre = _ParameterLockedRefinement(
            pattern, entry, peak_model,
            wavelength=wavelength,
            locked_mask=np.ones(11, dtype=bool),
        )
        x0_pre = pre._initial_vector()
        y_model, *_ = pre._calc_pattern(x0_pre)
        model_max = float(np.max(y_model)) if y_model.size else 0.0
        obs_max = float(np.max(pattern.intensity)) if pattern.intensity.size else 0.0
        if model_max > 1e-30 and obs_max > 0.0:
            est_scale = max(obs_max / model_max, 1e-6)
            current_x0 = x0_pre.copy()
            current_x0[0] = est_scale * 0.1  # start at 10 % of estimate

        for stage_name, param_indices in self.stages:
            # Unlock this stage's parameters.
            new_locked = current_locked.copy()
            for i in param_indices:
                if 0 <= i < 11:
                    new_locked[i] = False

            stage_refiner = _ParameterLockedRefinement(
                pattern, entry, peak_model,
                wavelength=wavelength,
                locked_mask=new_locked,
                x0_override=current_x0,
            )
            # The actual Rwp at the start of this stage's refinement —
            # equal to the previous *accepted* stage's rwp_after (or the
            # initial Rwp if no stage has been accepted yet).  This is
            # what we compare against to decide acceptance.
            rwp_before = stage_refiner.initial_rwp()

            # Stages that unlock no new parameters (e.g. 'background' and
            # 'atoms' in the local refiner) are true no-ops: skip the
            # optimisation step entirely so no numerical jitter from
            # previously-unlocked parameters can produce a spurious Rwp
            # decrease.
            if not param_indices:
                steps.append(
                    TurnOnStep(
                        stage_name=stage_name,
                        rwp_before=float(rwp_before),
                        rwp_after=float(rwp_before),
                        accepted=False,
                        params_enabled=[],
                    )
                )
                continue

            result = stage_refiner.fit(n_iter=n_iter)
            rwp_after = result.rwp

            # Accept the stage iff Rwp strictly decreased beyond tolerance.
            accepted = (rwp_before - rwp_after) > rwp_tolerance
            if accepted:
                current_locked = new_locked
                current_x0 = np.array(
                    [
                        result.scale,
                        result.zero_shift,
                        result.cell.a, result.cell.b, result.cell.c,
                        result.cell.alpha, result.cell.beta, result.cell.gamma,
                        *result.peak_model.caglioti_uvw,
                    ],
                    dtype=np.float64,
                )
            # On rejection (rollback) we keep current_locked and current_x0
            # unchanged — the next stage will start from the same state.

            steps.append(
                TurnOnStep(
                    stage_name=stage_name,
                    rwp_before=float(rwp_before),
                    rwp_after=float(rwp_after),
                    accepted=accepted,
                    params_enabled=[
                        _PARAM_NAMES[i] for i in param_indices if 0 <= i < 11
                    ],
                )
            )

        return steps


__all__ = [
    "DEFAULT_STAGES",
    "TurnOnStep",
    "TurnOnStrategy",
]
