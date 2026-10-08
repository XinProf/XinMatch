"""Residual-driven FoM recompute after phase selection (Phase 6 / T6.8).

When the user accepts a candidate as a *matching phase* (double-click in
Match!'s candidate list), the peaks that this phase explains must be
removed from the experimental peak list before the remaining candidates
are re-scored.  Otherwise the FoM of unrelated candidates is unfairly
penalised for peaks that have already been explained.

Match! feature: *auto-recompute FoM on phase selection* — the candidate
list is refreshed after every "select as matching" action so that the
next-best phase surfaces to the top.  This module mirrors that workflow
without touching the GUI: it takes a :class:`~xinmatch.core.model.Project`
and a just-selected :class:`~xinmatch.core.model.Phase`, builds the
residual peak list (experimental peaks minus the contribution of the
selected phase), and re-ranks the project's candidate entries by FoM.

Algorithm (simplified, peak-based):

1. Identify the experimental peaks that the selected phase has
   correlated to its reference peaks (``phase.correlations``).
2. For each correlated experimental peak, subtract the phase's
   contributed intensity::

       I_residual = max(0, I_exp − scale · I_ref_normalised)

   where ``I_ref_normalised`` is the reference intensity scaled to the
   experimental intensity scale (max = 100 → experimental max).  Peaks
   whose residual intensity drops below an ``explained_threshold``
   fraction of the experimental max are considered *fully explained*
   and removed from the residual list.  Peaks not correlated to the
   selected phase are kept unchanged.
3. Re-run :func:`~xinmatch.core.search.fom.rank_candidates` on the
   residual peak list against the project's candidate entries.

The result is a fresh :class:`~xinmatch.core.search.fom.CandidateResult`
list sorted by descending residual-FoM.  The caller (typically the GUI
/ CLI layer) writes it back into ``project.candidates`` and refreshes
the candidate-list view.
"""

from __future__ import annotations

import logging
from typing import Any

from xinmatch.core.model import Peak, Phase, Project
from xinmatch.core.search.fom import CandidateResult, rank_candidates
from xinmatch.core.search.fom_criteria import FomWeights

logger = logging.getLogger(__name__)

__all__ = [
    "recompute_fom_after_selection",
    "build_residual_peaks",
    "EXPLAINED_THRESHOLD",
]


# Default: a peak whose residual intensity is below 1 % of the
# experimental max intensity is considered fully explained by the
# selected phase and removed from the residual list.  Match! uses a
# similar "min intensity" cutoff when refreshing the candidate list.
EXPLAINED_THRESHOLD: float = 0.01


def build_residual_peaks(
    exp_peaks: list[Peak],
    selected_phase: Phase,
    *,
    explained_threshold: float = EXPLAINED_THRESHOLD,
) -> list[Peak]:
    """Return the residual experimental peaks after subtracting *selected_phase*.

    This is the simplified peak-based residual: for each experimental
    peak that the selected phase has correlated to one of its reference
    peaks, the phase's contributed intensity (``scale_factor · I_ref``)
    is subtracted.  Peaks whose residual intensity falls below
    ``explained_threshold × max(I_exp)`` are dropped entirely
    (considered fully explained); the rest are kept with their reduced
    intensity.  Experimental peaks not correlated to the selected phase
    are returned unchanged.

    Match! feature: *subtract selected phase contribution* step of the
    auto-recompute-FoM workflow.

    Parameters
    ----------
    exp_peaks:
        Original experimental peak list.
    selected_phase:
        Phase just accepted as matching.  Its ``correlations`` list of
        ``(exp_idx, ref_idx)`` pairs drives the subtraction; its
        ``scale_factor`` and ``entry.intensities`` provide the reference
        intensity profile.
    explained_threshold:
        Fraction of the experimental max intensity below which a peak is
        considered fully explained (default 1 %).

    Returns
    -------
    list[Peak]
        Residual peaks (possibly fewer than the input if some were
        fully explained).  Order follows *exp_peaks* with explained
        peaks skipped.
    """
    if not exp_peaks:
        return []

    # Map exp_idx → ref_idx for the selected phase's correlations.
    explained: dict[int, int] = {
        ei: ri for ei, ri in selected_phase.correlations
    }
    if not explained:
        # Phase explains no experimental peaks → residual = original.
        return list(exp_peaks)

    exp_max = max((p.intensity for p in exp_peaks), default=0.0)
    threshold = explained_threshold * exp_max if exp_max > 0 else 0.0

    ref_intensities = selected_phase.entry.intensities
    ref_max = selected_phase.entry.intensity_max
    scale = float(selected_phase.scale_factor)

    residual: list[Peak] = []
    for i, peak in enumerate(exp_peaks):
        if i not in explained:
            residual.append(peak)
            continue
        ref_idx = explained[i]
        if ref_idx < 0 or ref_idx >= len(ref_intensities):
            # Out-of-range ref index (stale correlation) → keep peak.
            residual.append(peak)
            continue
        ref_i = float(ref_intensities[ref_idx])
        # Normalise reference intensity to the experimental scale
        # (max = 100 → experimental max) so the subtraction is on the
        # same intensity axis as the experimental peaks.
        ref_norm = (ref_i / ref_max * exp_max) if ref_max > 0 else 0.0
        residual_i = max(0.0, float(peak.intensity) - scale * ref_norm)
        if residual_i < threshold:
            # Fully explained → drop.
            continue
        # Keep the peak with reduced intensity.  Copy the other fields
        # so the original Peak object is not mutated.
        residual.append(
            Peak(
                two_theta=peak.two_theta,
                intensity=residual_i,
                fwhm=peak.fwhm,
                d=peak.d,
                hkl=peak.hkl,
                correlated=False,  # Reset: re-correlation is rank_candidates' job.
                marked=peak.marked,
                excluded=peak.excluded,
            )
        )
    return residual


def recompute_fom_after_selection(
    project: Project,
    selected_phase: Phase,
    *,
    wavelength: float | None = None,
    weights: FomWeights | None = None,
    window_deg: float = 0.3,
    explained_threshold: float = EXPLAINED_THRESHOLD,
) -> list[CandidateResult]:
    """Recompute candidate FoM after a phase is selected (T6.8).

    Builds the residual experimental peak list (experimental peaks
    minus the contribution of *selected_phase*), then re-ranks the
    project's current candidate entries against it using
    :func:`~xinmatch.core.search.fom.rank_candidates`.

    Match! feature: *auto-recompute FoM on matching-phase selection*.
    After the user accepts a candidate as a matching phase, the
    candidate list is refreshed so that the next-best phase rises to
    the top.  This function is GUI-free; the caller writes the
    returned list back into ``project.candidates`` and refreshes the
    candidate-list view.

    Parameters
    ----------
    project:
        The current analysis project.  ``project.peaks`` provides the
        experimental peaks; ``project.candidates`` (a list of
        ``(Entry, fom)`` tuples) provides the candidate entries to
        re-score.  ``project.patterns[0].wavelength`` is used as the
        wavelength fallback when *wavelength* is not given.
    selected_phase:
        The phase just accepted as matching.  Its ``correlations``
        and ``scale_factor`` drive the residual computation.
    wavelength:
        Wavelength in Å.  When ``None`` (default), falls back to
        ``project.patterns[0].wavelength``; if the project has no
        patterns, Cu Kα (1.5406 Å) is used.
    weights:
        Optional :class:`FomWeights` override for the recompute.
        ``None`` uses the default Match! 4.3 weights.
    window_deg:
        Peak-correlation window width in degrees 2θ (default 0.3).
    explained_threshold:
        Fraction of the experimental max intensity below which a peak
        is considered fully explained and dropped from the residual
        list (default 1 %).

    Returns
    -------
    list[CandidateResult]
        Re-ranked candidate results sorted by descending residual FoM.
        Empty if the project has no peaks or no candidate entries.

    Notes
    -----
    The function does **not** mutate *project*; the caller is
    responsible for updating ``project.candidates`` and pushing the
    previous state onto the undo stack (``project.snapshot()``) before
    calling this function.
    """
    # Resolve wavelength: explicit > project pattern > Cu Kα fallback.
    if wavelength is not None:
        wl = float(wavelength)
    elif project.patterns:
        wl = float(project.patterns[0].wavelength)
    else:
        wl = 1.5406  # Cu Kα fallback (Match! default for most labs).

    # Build the residual peak list.
    residual_peaks = build_residual_peaks(
        project.peaks,
        selected_phase,
        explained_threshold=explained_threshold,
    )
    logger.debug(
        "residual: %d exp peaks → %d residual peaks after subtracting %s",
        len(project.peaks),
        len(residual_peaks),
        selected_phase.entry.entry_id,
    )

    # Extract Entry objects from the project's candidate list.
    # project.candidates is list[tuple[Entry, float]] per the Project
    # dataclass; we tolerate CandidateResult-like objects too.
    entries: list[Any] = []
    for c in project.candidates:
        if isinstance(c, tuple):
            entries.append(c[0])
        elif hasattr(c, "entry"):
            entries.append(c.entry)
        else:
            entries.append(c)

    if not entries or not residual_peaks:
        return []

    return rank_candidates(
        residual_peaks,
        entries,
        wl,
        weights=weights,
        window_deg=window_deg,
    )
