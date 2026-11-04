"""Sequential (iterative) phase identification — v3.1.0.

The single-shot search-match returns one ranked candidate list for the whole
pattern.  Real multi-phase samples need a *loop*: accept the best phase, take
its peaks out of the problem, search again on what is left, accept the next
phase, and so on.  This module is the GUI-free engine behind that loop.

Two layers, deliberately separated:

:class:`SequentialIdentifier`
    Owns the bookkeeping.  It keeps the **original** experimental peak list
    (never mutated), the confirmed phases in confirmation order, and derives —
    from scratch on every change — each phase's peak correlation, its
    count-space scale factor, and the peak-by-peak residual intensity
    ``I_obs − Σ(phase contributions)``.  A peak counts as *explained* when its
    residual drops to a few percent of its own observed intensity; explained
    peaks leave the residual set, partially explained ones stay with their
    reduced intensity (a superposition is genuine physics, not a rounding
    error).

:func:`search_residual`
    Runs the ordinary :func:`~xinmatch.core.search.search_match.search_match`
    on the residual peak set and rewrites the returned ``pairs`` back into
    original-peak indices, so the GUI can highlight exactly which measured
    peaks a candidate would explain.  Already confirmed entries are dropped
    from the list — the user is looking for the *next* phase.

Why rebuild instead of incremental updates
------------------------------------------
Confirmation order matters: phase B's scale factor is fitted against the
intensity left over *after* phase A, so removing A must be able to change
B's numbers.  Recomputing every layer from the original peaks on each
mutation keeps the state a pure function of ``(exp_peaks, phases)`` — no
accumulated float drift, no stale correlations, and undo is simply "drop the
last phase and rebuild".  Cost is one correlation pass per confirmed phase
(O(n_exp × n_ref) with small n), i.e. microseconds.

Scale factor convention
-----------------------
``Phase.scale_factor`` here is **counts per unit relative reference
intensity**: ``contribution_i = scale · (I_ref_i / I_ref_max)``.  It is fitted
by least squares in *count* space over the correlated peaks::

    scale = Σ(I_residual,i · r_i) / Σ(r_i²),    r_i = I_ref,i / I_ref,max

This is deliberately **not** :attr:`CandidateResult.i_scale`, which is
dimensionless (both sides normalised to 100, ≈ 1.0 for a shape match) and
therefore useless for subtracting counts from a measured peak.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np

from xinmatch.core.model import Entry, Peak, Phase
from xinmatch.core.search.correlate import correlate_peaks
from xinmatch.core.search.fom import CandidateResult

logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_ABS_FLOOR",
    "DEFAULT_ANCHOR_ALPHA",
    "DEFAULT_ANCHOR_MAX_REFLECTIONS",
    "DEFAULT_ANCHOR_MIN_NCORR",
    "DEFAULT_ANCHOR_MIN_PAIRS",
    "DEFAULT_ANCHOR_PEAKPOS",
    "DEFAULT_ANCHOR_POLICY",
    "DEFAULT_EXPLAINED_FRAC",
    "DEFAULT_MIN_PEAK_FRAC",
    "AnchorPolicy",
    "PhaseSelection",
    "ResidualSearchResult",
    "SequentialIdentifier",
    "search_residual",
]


#: A peak whose residual intensity falls to this fraction of its **own**
#: observed intensity is considered fully explained by the confirmed phases.
#: Relative (not absolute) so a 200-count minor line is not swallowed just
#: because the major phase has a 50 000-count peak.
DEFAULT_EXPLAINED_FRAC: float = 0.05

#: Absolute floor, as a fraction of the pattern maximum, below which a peak
#: counts as explained regardless of its own intensity.  Guards against
#: floating-point dust keeping "peaks" with 1e-9 counts alive forever.
DEFAULT_ABS_FLOOR: float = 0.002

#: Peaks weaker than this fraction of the pattern maximum are **ignored** for
#: residual searching (neither "explained" nor "left over"): a 0.5 % line
#: carries no phase-identification information above the noise, and letting
#: such peaks into the residual set makes the next round match noise — measured
#: on the synthetic 2-phase sample (synth_02): after both true phases were
#: confirmed, 32 of 51 detected peaks were still "unexplained" at 92 % of the
#: intensity, and round 3 returned Fe0.75V0.25 / Ag2O3Te nonsense.  This is the
#: usual search-match "minimum intensity" cut (1 % is the common default).
DEFAULT_MIN_PEAK_FRAC: float = 0.01

#: Peak-correlation window (degrees 2θ) — the project default.
DEFAULT_WINDOW_DEG: float = 0.3


# --------------------------------------------------------------------------- #
# Strong-line anchoring (v3.3.0) — sparse-phase recall in the sequential loop
# --------------------------------------------------------------------------- #
# Why this exists
# ---------------
# ``P_npeaks`` in the FoM counts *how many* measured peaks a candidate
# explains, as a fraction of the residual peak count.  In a residual set that
# a "peak-rich" card (a 40-reflection intermetallic) can carpet, that reward
# is dominated by sheer reflection count: a correct 6-line phase (Fe, KCl,
# NaCl) explains 2–6 peaks and never reaches the top of the list, even when
# one of its lines sits exactly on the strongest leftover peak.  Measured on
# the synthetic bench (synth_07): the true KCl was **absent from a 1000-deep
# candidate pool**, and Fe entered round 1 at rank #94/1000 with
# ``P_peakpos = 0.998``, ``P_intensity = 0.99`` and its strongest line on
# 1.00× the maximum residual intensity.
#
# The rule below asks: "does this candidate's **strongest** reference line sit
# on a strong residual peak, is it positionally accurate, and does it account
# for at least half of its own reflections?"  A dense card cannot pass the
# reflection-count guard, so the carpet stays where it is.
#
# Measured trade-off (v3.3.0) — why the *ordering* is off by default
# ------------------------------------------------------------------
# | bench                | FoM order (default) | anchored first |
# |----------------------|--------------------:|---------------:|
# | synthetic_v3, 13 seq |           10/13     | **11/13**      |
# | synthetic_v3 recall  |           19/24     | **21/24**      |
# | real 12 samples      |            5/12     | 4/12           |
# | real 43 phases       |           23/43     | 22/43          |
#
# The synthetic gain is real (synth_07's NaCl is recovered from rank 10), but
# on real sample 3-2 the promoted card is a Bi-Y-O coincidence whose
# ``P_peakpos`` (0.984) is actually *better* than the true CaF₂'s (0.928);
# confirming it pollutes the residual and CaF₂ is lost even with 5 rounds.
# Synthesised patterns carry the reference's exact relative intensities, real
# ones never do — that is exactly the assumption the rule leans on, so the
# synthetic bench overstates its value.  Hence: report the candidates it would
# promote (:attr:`ResidualSearchResult.anchored_ids`, used by the GUI to mark
# them) and let the user decide, instead of silently reordering.
DEFAULT_ANCHOR_ALPHA: float = 0.3

#: Minimum ``P_peakpos`` for the anchor rule (position accuracy).
DEFAULT_ANCHOR_PEAKPOS: float = 0.98

#: Minimum number of correlated pairs (a 1-line coincidence proves nothing).
DEFAULT_ANCHOR_MIN_PAIRS: int = 2

#: Minimum ``P_ncorr`` — share of the candidate's *own* reflections that the
#: residual pattern actually accounts for.  This is what separates "a real
#: phase with few lines" from "a huge card with one lucky coincidence".
DEFAULT_ANCHOR_MIN_NCORR: float = 0.5

#: Reflection-count ceiling: candidates with more reference lines than this
#: are never promoted.  They are exactly the dense cards whose ``P_npeaks``
#: advantage the anchor rule is meant to counterbalance.
DEFAULT_ANCHOR_MAX_REFLECTIONS: int = 20


@dataclass(frozen=True)
class AnchorPolicy:
    """Thresholds of the strong-line anchoring rule (see module constants).

    Attributes
    ----------
    alpha:
        Minimum strength of the residual peak the candidate's strongest
        reference line is anchored on, as a fraction of the strongest
        residual peak.
    min_peakpos:
        Minimum ``P_peakpos`` of the candidate.
    min_pairs:
        Minimum number of correlated ``(exp, ref)`` pairs.
    min_ncorr:
        Minimum ``P_ncorr`` (share of the candidate's own lines explained).
    max_reflections:
        Candidates with more reference lines than this are never promoted.
    """

    alpha: float = DEFAULT_ANCHOR_ALPHA
    min_peakpos: float = DEFAULT_ANCHOR_PEAKPOS
    min_pairs: int = DEFAULT_ANCHOR_MIN_PAIRS
    min_ncorr: float = DEFAULT_ANCHOR_MIN_NCORR
    max_reflections: int = DEFAULT_ANCHOR_MAX_REFLECTIONS


#: Policy used when :func:`search_residual` is called without an explicit
#: *anchor_policy*.
DEFAULT_ANCHOR_POLICY: AnchorPolicy = AnchorPolicy()


# --------------------------------------------------------------------------- #
# Result containers
# --------------------------------------------------------------------------- #
@dataclass
class PhaseSelection:
    """One confirmed phase plus the peak bookkeeping that produced it.

    Attributes
    ----------
    phase:
        The confirmed :class:`~xinmatch.core.model.Phase`.  Its
        ``correlations`` and ``scale_factor`` are kept in sync with the
        values below on every rebuild.
    pairs:
        ``(original_exp_index, ref_index)`` correlations.  Indices refer to
        the **original** experimental peak list handed to
        :class:`SequentialIdentifier`, not to the residual subset.
    explained:
        Original experimental peak indices that this phase (in combination
        with the earlier ones) reduced below the explained threshold.
        Cumulative — after selecting phase *k* this lists everything
        explained so far.
    scale:
        Counts per unit relative reference intensity (see module docstring).
    covered_fraction:
        Fraction of the total observed peak intensity explained so far.
    n_residual_peaks:
        Number of peaks still unexplained after this phase.
    """

    phase: Phase
    pairs: list[tuple[int, int]] = field(default_factory=list)
    explained: list[int] = field(default_factory=list)
    scale: float = 0.0
    covered_fraction: float = 0.0
    n_residual_peaks: int = 0

    @property
    def entry_id(self) -> str:
        """Reference-database id of the confirmed phase."""
        return self.phase.entry.entry_id


@dataclass
class ResidualSearchResult:
    """Outcome of a search on the residual (unexplained) peaks.

    Attributes
    ----------
    candidates:
        Ranked candidates, best first.  ``pairs`` are remapped to original
        experimental peak indices.
    n_residual_peaks:
        Size of the residual peak set the search ran on.
    n_explained:
        Number of original peaks already explained by confirmed phases.
    n_ignored:
        Number of peaks below the search floor (neither explained nor left
        over — just too weak to identify a phase).
    covered_fraction:
        Fraction of the *significant* observed peak intensity already
        explained.
    excluded_ids:
        Entry ids filtered out because they are already confirmed phases.
    anchored_ids:
        Entry ids that satisfy the strong-line anchoring rule (v3.3.0):
        strongest reference line on a strong residual peak, accurate
        position, ≥ half of their own reflections accounted for, and few
        enough reflections to not be a peak-rich carpet.  The GUI marks
        these rows — they are the sparse phases a pure FoM ranking buries.
        Empty when promotion is disabled *and* the caller does not ask for
        the marks; see :func:`search_residual`.
    """

    candidates: list[CandidateResult] = field(default_factory=list)
    n_residual_peaks: int = 0
    n_explained: int = 0
    n_ignored: int = 0
    covered_fraction: float = 0.0
    excluded_ids: list[str] = field(default_factory=list)
    anchored_ids: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Sequential identifier
# --------------------------------------------------------------------------- #
class SequentialIdentifier:
    """Track confirmed phases and the residual experimental peaks.

    The object is a pure state machine: every mutation (``select`` /
    ``remove`` / ``undo`` / ``clear``) triggers a full rebuild from the
    original peak list, so the derived state always equals what a fresh
    analysis of the same phase sequence would produce.

    Parameters
    ----------
    exp_peaks:
        Original experimental peaks (positions and intensities as measured).
        The objects are **not** mutated.
    wavelength:
        Wavelength in Å, used for the d→2θ conversion in the correlation.
    window_deg:
        Peak-correlation window width (degrees 2θ), default 0.3°.
    explained_frac:
        Relative residual threshold for "fully explained"
        (:data:`DEFAULT_EXPLAINED_FRAC`).
    abs_floor:
        Absolute residual floor as a fraction of the pattern maximum
        (:data:`DEFAULT_ABS_FLOOR`).
    min_peak_frac:
        Peaks weaker than this fraction of the pattern maximum are ignored by
        the residual search (:data:`DEFAULT_MIN_PEAK_FRAC`).
    """

    def __init__(
        self,
        exp_peaks: Sequence[Peak],
        *,
        wavelength: float,
        window_deg: float = DEFAULT_WINDOW_DEG,
        explained_frac: float = DEFAULT_EXPLAINED_FRAC,
        abs_floor: float = DEFAULT_ABS_FLOOR,
        min_peak_frac: float = DEFAULT_MIN_PEAK_FRAC,
    ) -> None:
        if wavelength <= 0.0:
            raise ValueError(f"wavelength must be positive, got {wavelength}")
        if not 0.0 <= explained_frac < 1.0:
            raise ValueError(
                f"explained_frac must be in [0, 1), got {explained_frac}"
            )
        if not 0.0 <= min_peak_frac < 1.0:
            raise ValueError(
                f"min_peak_frac must be in [0, 1), got {min_peak_frac}"
            )
        self._exp_peaks: list[Peak] = list(exp_peaks)
        self.wavelength = float(wavelength)
        self.window_deg = float(window_deg)
        self.explained_frac = float(explained_frac)
        self.abs_floor = float(abs_floor)
        self.min_peak_frac = float(min_peak_frac)

        self._phases: list[Phase] = []
        self._selections: list[PhaseSelection] = []
        self._observed = self._observed_intensity()
        n = len(self._exp_peaks)
        self._residual = self._observed.copy()
        self._explained = np.zeros(n, dtype=bool)
        self._ignored = self._ignored_mask_for(self._observed)
        self._correlated = np.zeros(n, dtype=bool)
        self._covered_fraction = 0.0

    def _observed_intensity(self) -> np.ndarray:
        """Observed intensity per original peak (fresh array)."""
        n = len(self._exp_peaks)
        return np.fromiter(
            (float(p.intensity) for p in self._exp_peaks),
            dtype=np.float64,
            count=n,
        )

    def _ignored_mask_for(self, observed: np.ndarray) -> np.ndarray:
        """Peaks below the search floor (``min_peak_frac`` of the maximum)."""
        n = observed.size
        mask = np.zeros(n, dtype=bool)
        if n == 0:
            return mask
        peak_max = float(observed.max())
        if peak_max <= 0.0 or self.min_peak_frac <= 0.0:
            return mask
        return observed < self.min_peak_frac * peak_max

    # ------------------------------------------------------------------ #
    # Read-only state
    # ------------------------------------------------------------------ #
    @property
    def exp_peaks(self) -> list[Peak]:
        """The original experimental peak list (a copy of the reference)."""
        return list(self._exp_peaks)

    @property
    def phases(self) -> list[Phase]:
        """Confirmed phases, in confirmation order."""
        return list(self._phases)

    @property
    def selections(self) -> list[PhaseSelection]:
        """Per-phase bookkeeping, in confirmation order."""
        return list(self._selections)

    @property
    def n_peaks(self) -> int:
        """Number of original experimental peaks."""
        return len(self._exp_peaks)

    def __len__(self) -> int:
        return len(self._phases)

    @property
    def residual_intensity(self) -> np.ndarray:
        """Residual intensity per original peak (copy)."""
        return self._residual.copy()

    @property
    def explained_mask(self) -> np.ndarray:
        """Boolean mask: ``True`` where the peak is fully explained."""
        return self._explained.copy()

    @property
    def ignored_mask(self) -> np.ndarray:
        """Boolean mask: ``True`` where the peak is below the search floor."""
        return self._ignored.copy()

    @property
    def correlated_mask(self) -> np.ndarray:
        """Boolean mask: ``True`` where some confirmed phase correlates the peak.

        Superset of :attr:`explained_mask`: a peak that is only *partly*
        accounted for (superposition with an unconfirmed phase) is correlated
        but not yet explained.
        """
        return self._correlated.copy()

    @property
    def residual_indices(self) -> list[int]:
        """Original indices of the peaks that still need a phase.

        Peaks below the search floor (:attr:`ignored_mask`) are excluded —
        they are not "left over", they simply carry no usable phase
        information.
        """
        return [
            i
            for i in range(len(self._exp_peaks))
            if not self._explained[i] and not self._ignored[i]
        ]

    @property
    def explained_indices(self) -> list[int]:
        """Original indices of the peaks already explained."""
        return [i for i, done in enumerate(self._explained) if done]

    @property
    def ignored_indices(self) -> list[int]:
        """Original indices of the peaks below the search floor."""
        return [i for i, skip in enumerate(self._ignored) if skip]

    @property
    def n_residual_peaks(self) -> int:
        """How many (significant) peaks still wait for a phase."""
        return int(np.count_nonzero(~self._explained & ~self._ignored))

    @property
    def n_explained(self) -> int:
        """How many peaks are already accounted for."""
        return int(np.count_nonzero(self._explained))

    @property
    def n_ignored(self) -> int:
        """How many peaks are below the search floor."""
        return int(np.count_nonzero(self._ignored))

    @property
    def covered_fraction(self) -> float:
        """Fraction of the *significant* observed intensity explained so far."""
        return float(self._covered_fraction)

    @property
    def residual_peaks(self) -> list[Peak]:
        """Residual peaks as fresh :class:`Peak` objects.

        Intensity is the leftover after subtracting every confirmed phase;
        position / FWHM / d / hkl / mark / exclude flags are carried over.
        The ``correlated`` flag is reset — the re-search correlates again.
        Peaks below the search floor are not returned.
        """
        out: list[Peak] = []
        for i, peak in enumerate(self._exp_peaks):
            if self._explained[i] or self._ignored[i]:
                continue
            out.append(
                Peak(
                    two_theta=float(peak.two_theta),
                    intensity=float(self._residual[i]),
                    fwhm=peak.fwhm,
                    d=peak.d,
                    hkl=peak.hkl,
                    correlated=False,
                    marked=peak.marked,
                    excluded=peak.excluded,
                )
            )
        return out

    # ------------------------------------------------------------------ #
    # Lookup
    # ------------------------------------------------------------------ #
    def find(self, entry_id: str) -> Phase | None:
        """Return the confirmed phase with *entry_id*, or ``None``."""
        for phase in self._phases:
            if phase.entry.entry_id == entry_id:
                return phase
        return None

    def is_selected(self, entry_id: str) -> bool:
        """Whether *entry_id* has already been confirmed."""
        return self.find(entry_id) is not None

    def selection_of(self, entry_id: str) -> PhaseSelection | None:
        """Return the bookkeeping of a confirmed phase, or ``None``."""
        for sel in self._selections:
            if sel.phase.entry.entry_id == entry_id:
                return sel
        return None

    # ------------------------------------------------------------------ #
    # Mutations
    # ------------------------------------------------------------------ #
    def select(self, candidate: CandidateResult) -> PhaseSelection:
        """Confirm *candidate* as a matching phase and rebuild the residual.

        The candidate may come from any search (full pattern or residual):
        its correlation table is **recomputed** against the current residual
        peaks, so a stale or differently-indexed ``pairs`` list cannot leak
        into the bookkeeping.

        Selecting an entry that is already confirmed is a no-op that returns
        the existing selection (double-click / repeated Enter safety).

        Returns
        -------
        PhaseSelection
            The bookkeeping for this phase.  A copy of it is also available
            through :attr:`selections`.
        """
        entry = candidate.entry
        existing = self.selection_of(entry.entry_id)
        if existing is not None:
            logger.debug("phase %s already selected; ignoring", entry.entry_id)
            return existing
        self._phases.append(Phase(entry=entry))
        self._rebuild()
        return self._selections[-1]

    def remove(self, entry_id: str) -> bool:
        """Remove a confirmed phase (anywhere in the sequence) and rebuild.

        Returns ``True`` if the phase was present.  Later phases keep their
        relative order; their scale factors are re-fitted against the
        residual produced by the phases that remain, which is why order-
        independent removal is safe.
        """
        for i, phase in enumerate(self._phases):
            if phase.entry.entry_id == entry_id:
                del self._phases[i]
                self._rebuild()
                return True
        return False

    def undo(self) -> Phase | None:
        """Remove the most recently confirmed phase; return it (or ``None``)."""
        if not self._phases:
            return None
        phase = self._phases.pop()
        self._rebuild()
        return phase

    def clear(self) -> None:
        """Forget every confirmed phase (residual returns to the raw peaks)."""
        self._phases.clear()
        self._rebuild()

    def reset(self, exp_peaks: Sequence[Peak] | None = None) -> None:
        """Start over, optionally with a new peak list."""
        if exp_peaks is not None:
            self._exp_peaks = list(exp_peaks)
            self._observed = self._observed_intensity()
        self._phases.clear()
        self._rebuild()

    # ------------------------------------------------------------------ #
    # Rebuild
    # ------------------------------------------------------------------ #
    def _explained_threshold(self) -> np.ndarray:
        """Per-peak explained threshold (relative, with an absolute floor)."""
        n = len(self._exp_peaks)
        if n == 0:
            return np.zeros(0, dtype=np.float64)
        peak_max = float(self._observed.max())
        floor = self.abs_floor * peak_max if peak_max > 0.0 else 0.0
        return np.maximum(self.explained_frac * self._observed, floor)

    def _rebuild(self) -> None:
        """Recompute correlations, scales, residuals and flags from scratch."""
        n = len(self._exp_peaks)
        threshold = self._explained_threshold()
        self._residual = self._observed.copy()
        self._ignored = self._ignored_mask_for(self._observed)
        self._explained = np.zeros(n, dtype=bool)
        self._correlated = np.zeros(n, dtype=bool)
        self._selections = []

        significant = ~self._ignored
        total = float(self._observed[significant].sum()) if n else 0.0
        for phase in self._phases:
            pairs, scale = self._layer_for(phase.entry)
            ref_max = float(phase.entry.intensity_max)
            intensities = phase.entry.intensities
            for exp_idx, ref_idx in pairs:
                if ref_max <= 0.0 or ref_idx >= len(intensities):
                    continue
                rel = float(intensities[ref_idx]) / ref_max
                self._residual[exp_idx] = max(
                    0.0, float(self._residual[exp_idx]) - scale * rel
                )
                self._correlated[exp_idx] = True
            # "Explained" is evaluated against the threshold each round: a
            # peak becomes explained as soon as the *cumulative* residual of
            # the confirmed phases is small enough, which is what makes the
            # residual set shrink monotonically as phases are added.
            self._explained = (self._residual <= threshold) & significant
            covered = (
                1.0 - (float(self._residual[significant].sum()) / total)
                if total > 0
                else 0.0
            )
            self._covered_fraction = min(max(covered, 0.0), 1.0)
            # Keep the Phase object the single source of truth downstream
            # (Rietveld / report / CIF export all read these two fields).
            phase.correlations = list(pairs)
            phase.scale_factor = scale
            self._selections.append(
                PhaseSelection(
                    phase=phase,
                    pairs=list(pairs),
                    explained=self.explained_indices,
                    scale=scale,
                    covered_fraction=self._covered_fraction,
                    n_residual_peaks=self.n_residual_peaks,
                )
            )

        if not self._phases:
            self._covered_fraction = 0.0

    def _layer_for(self, entry: Entry) -> tuple[list[tuple[int, int]], float]:
        """Correlate *entry* against the live residual set, fit its scale.

        Returns ``(pairs_in_original_indices, scale)``.  Peaks that are not
        yet explained (and not below the search floor) take part in the
        correlation; the rest belong to earlier phases or to the noise.
        """
        active = [
            i
            for i in range(len(self._exp_peaks))
            if not self._explained[i] and not self._ignored[i]
        ]
        if not active:
            return [], 0.0
        ref = [
            (float(d), float(i))
            for d, i in zip(entry.d_spacings, entry.intensities, strict=True)
        ]
        if not ref:
            return [], 0.0
        sub = [self._exp_peaks[i] for i in active]
        pairs_sub = correlate_peaks(
            sub, ref, self.wavelength, self.window_deg
        )
        pairs = [(active[exp_i], ref_i) for exp_i, ref_i in pairs_sub]
        scale = self._fit_scale(entry, pairs)
        return pairs, scale

    def _fit_scale(self, entry: Entry, pairs: list[tuple[int, int]]) -> float:
        """Least-squares count-space scale over the correlated peaks."""
        if not pairs:
            return 0.0
        ref_max = float(entry.intensity_max)
        if ref_max <= 0.0:
            return 0.0
        intensities = entry.intensities
        num = 0.0
        den = 0.0
        for exp_idx, ref_idx in pairs:
            if ref_idx >= len(intensities):
                continue
            rel = float(intensities[ref_idx]) / ref_max
            num += float(self._residual[exp_idx]) * rel
            den += rel * rel
        if den <= 0.0:
            return 0.0
        return num / den


# --------------------------------------------------------------------------- #
# Residual search
# --------------------------------------------------------------------------- #
def _default_search_fn() -> Callable[..., list[CandidateResult]]:
    """Resolve :func:`search_match` lazily (avoids an import cycle)."""
    from xinmatch.core.search.search_match import search_match

    return search_match


def _anchor_ok(
    cand: CandidateResult,
    residual_intensity: np.ndarray,
    peak_max: float,
    policy: AnchorPolicy,
) -> bool:
    """Whether *cand* satisfies the strong-line anchoring rule.

    ``cand.pairs`` must still be in **residual** peak order, i.e. this runs
    before the pairs are remapped to original experimental indices.

    Everything is defensive: candidates that carry no ``p_values``, no
    ``pairs`` or an entry without intensities simply do not qualify.
    """
    p_values = cand.p_values
    if not p_values:
        return False
    intensities = cand.entry.intensities
    if intensities is None:
        return False
    n_ref = int(intensities.size)
    if n_ref == 0 or n_ref > policy.max_reflections:
        return False
    if float(p_values.get("peakpos", 0.0)) < policy.min_peakpos:
        return False
    if len(cand.pairs) < policy.min_pairs:
        return False
    if float(p_values.get("ncorr", 0.0)) < policy.min_ncorr:
        return False
    strongest = int(np.argmax(intensities))
    anchored = next((e for e, r in cand.pairs if r == strongest), None)
    if anchored is None or not 0 <= anchored < residual_intensity.size:
        return False
    return bool(residual_intensity[anchored] >= policy.alpha * peak_max)


def _anchor_flags(
    candidates: list[CandidateResult],
    residual_intensity: np.ndarray,
    policy: AnchorPolicy,
) -> list[bool]:
    """Per-candidate "is strong-line anchored" verdicts.

    All ``False`` when there is nothing to compare against (empty residual set
    or a flat one) — the rule never promotes on degenerate input.
    """
    if not candidates or residual_intensity.size == 0:
        return [False] * len(candidates)
    peak_max = float(residual_intensity.max())
    if peak_max <= 0.0:
        return [False] * len(candidates)
    return [
        _anchor_ok(cand, residual_intensity, peak_max, policy)
        for cand in candidates
    ]


def _promote_anchored(
    candidates: list[CandidateResult],
    flags: list[bool],
) -> list[CandidateResult]:
    """Move anchored candidates to the front, keeping the order otherwise.

    A stable partition: promoted candidates come first (still by descending
    FoM), the rest keep their original relative order.  Nothing is dropped and
    no FoM is recomputed.

    **Off by default** — see the module-level note on the measured trade-off.
    """
    if len(candidates) < 2:
        return candidates
    if not any(flags) or all(flags):
        return candidates
    hot = [c for c, f in zip(candidates, flags, strict=True) if f]
    cold = [c for c, f in zip(candidates, flags, strict=True) if not f]
    hot.sort(key=lambda c: c.fom, reverse=True)
    logger.debug("anchored promotion: %d/%d candidates", len(hot), len(candidates))
    return hot + cold


def search_residual(
    identifier: SequentialIdentifier,
    conn: object,
    *,
    top_n: int = 20,
    exclude_matched: bool = True,
    promote_anchored: bool = False,
    anchor_policy: AnchorPolicy | None = None,
    search_fn: Callable[..., list[CandidateResult]] | None = None,
    **search_kwargs: object,
) -> ResidualSearchResult:
    """Run search-match on the residual peaks of *identifier*.

    Thin orchestration around :func:`~xinmatch.core.search.search_match.search_match`:

    1. take :attr:`SequentialIdentifier.residual_peaks`;
    2. rank candidates against them (same engine, same FoM — only the peak
       set is smaller);
    3. drop entries that are already confirmed phases
       (*exclude_matched*, default on) so the list answers "what is left?";
    4. flag the candidates that pass the strong-line anchoring rule and
       report them as :attr:`ResidualSearchResult.anchored_ids` — the sparse
       phases a peak-count-driven FoM buries;
    5. remap every candidate's ``pairs`` from residual indices back to
       original experimental peak indices, so the GUI can highlight the
       measured peaks a candidate would explain.

    Parameters
    ----------
    identifier:
        The live :class:`SequentialIdentifier`.
    conn:
        Reference database handle (``.xinDB`` reader or SQLite connection —
        the engine dispatches by type).
    top_n:
        Number of candidates to keep.
    exclude_matched:
        Drop already confirmed entry ids from the result.
    promote_anchored:
        Promote the anchored candidates to the **front** of the list instead
        of only marking them.  **Off by default**: it recovers a sparse phase
        on the synthetic bench (10/13 → 11/13) but costs one real sample
        (5/12 → 4/12) — see the module-level note.  Interactive use can turn
        it on; the autonomous bench should not.
    anchor_policy:
        Thresholds of the rule; ``None`` uses :data:`DEFAULT_ANCHOR_POLICY`.
    search_fn:
        Injection point for tests / alternative engines.  Defaults to
        :func:`~xinmatch.core.search.search_match.search_match`.
    **search_kwargs:
        Forwarded to *search_fn* (``weights``, ``window_deg``,
        ``restraints``, …).  The anchoring flags are deliberately **not**
        forwarded — they belong to this layer, not to the search engine.

    Returns
    -------
    ResidualSearchResult
        Empty ``candidates`` when nothing is left to search.
    """
    covered = identifier.covered_fraction
    n_explained = identifier.n_explained
    n_ignored = identifier.n_ignored
    residual_peaks = identifier.residual_peaks
    indices = identifier.residual_indices
    if not residual_peaks:
        logger.debug("no residual peaks left; search skipped")
        return ResidualSearchResult(
            candidates=[],
            n_residual_peaks=0,
            n_explained=n_explained,
            n_ignored=n_ignored,
            covered_fraction=covered,
        )

    if search_fn is None:
        search_fn = _default_search_fn()

    ranked = search_fn(
        residual_peaks,
        conn,
        identifier.wavelength,
        top_n=top_n,
        **search_kwargs,
    )

    matched = {phase.entry.entry_id for phase in identifier.phases}
    excluded: list[str] = []
    kept: list[CandidateResult] = []
    for cand in ranked:
        eid = cand.entry.entry_id
        if exclude_matched and eid in matched:
            excluded.append(eid)
            continue
        kept.append(cand)

    # Anchoring runs while ``pairs`` still index the residual peak list — the
    # rule compares against residual intensity, so it must see the un-remapped
    # indices.
    residual_intensity = np.fromiter(
        (float(p.intensity) for p in residual_peaks),
        dtype=np.float64,
        count=len(residual_peaks),
    )
    policy = DEFAULT_ANCHOR_POLICY if anchor_policy is None else anchor_policy
    flags = _anchor_flags(kept, residual_intensity, policy)
    anchored_ids = [
        cand.entry.entry_id
        for cand, flag in zip(kept, flags, strict=True)
        if flag
    ]
    if promote_anchored:
        kept = _promote_anchored(kept, flags)

    for cand in kept:
        # Residual index → original index.  Guard the upper bound: a
        # candidate whose pairs came from somewhere else must not produce an
        # out-of-range index that later crashes the peak-list highlight.
        cand.pairs = [
            (indices[exp_idx], ref_idx)
            for exp_idx, ref_idx in cand.pairs
            if 0 <= exp_idx < len(indices)
        ]

    return ResidualSearchResult(
        candidates=kept,
        n_residual_peaks=len(residual_peaks),
        n_explained=n_explained,
        n_ignored=n_ignored,
        covered_fraction=covered,
        excluded_ids=excluded,
        anchored_ids=anchored_ids,
    )
