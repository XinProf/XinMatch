"""Batch FoM scoring and ranking of search-match candidates (Phase 6 / T6.3).

This module wraps the per-candidate scoring pipeline
(:func:`~xinmatch.core.search.fom_criteria.score_candidate`) into a batch
operation: given the experimental peaks and a *pruned* list of candidate
:class:`~xinmatch.core.model.Entry` objects (typically 100-1000 entries left
after the d-value / restraint pre-filter steps), it computes the FoM for
each, sorts the results by descending FoM, and offers a Top-N selection.

Match! feature: the ranked *candidate list* displayed in the bottom-left of
the Match! GUI is the output of this batch scoring step.  The Top-N cutoff
mirrors Match!'s "minimum FoM" filter and the practical limit on what the
user can reasonably inspect (default 20).

The :class:`CandidateResult` dataclass also carries the per-criterion P
values, the ``(exp_idx, ref_idx)`` correlation pairs, and the intensity
scaling factor — fields needed by the GUI's candidate-list rendering
(FoM columns, "P(2θ)" / "P(I/I₀)" / "I scale fct." columns) and by the
"show unassociated peaks" feature (:func:`CandidateList.show_unassociated_peaks`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from xinmatch.core.model import Entry, Peak
from xinmatch.core.search.correlate import correlate_peaks
from xinmatch.core.search.fom_criteria import (
    DEFAULT_WEIGHTS,
    FomWeights,
    compute_fom,
    compute_p_values,
)

__all__ = [
    "CandidateResult",
    "rank_candidates",
    "select_top_n",
]


# --------------------------------------------------------------------------- #
# Per-candidate result container
# --------------------------------------------------------------------------- #
@dataclass
class CandidateResult:
    """FoM scoring result for a single candidate reference entry.

    Match! feature: one row in the candidate list (peak-based
    search-match, Phase 6 / T6.3).

    Attributes
    ----------
    entry:
        The reference-database entry that was scored.
    fom:
        Figure-of-merit (descending sort key).  Not clamped — may drift
        slightly outside ``[0, 1]`` in degenerate cases (mirrors Match!'s
        raw FoM).
    p_values:
        Per-criterion agreement values ``{peakpos, intensity, npeaks,
        ncorr, i_scale}`` as returned by
        :func:`~xinmatch.core.search.fom_criteria.compute_p_values`.
    pairs:
        ``(exp_idx, ref_idx)`` correlations produced by the peak
        correlation step.  Used by the GUI to highlight matched peaks
        and by :meth:`CandidateList.show_unassociated_peaks`.
    i_scale:
        Reference → experimental intensity scaling factor.  Mirrors
        ``p_values["i_scale"]``; duplicated as a top-level field for
        convenient serialisation / display.
    """

    entry: Entry
    fom: float
    p_values: dict[str, float] = field(default_factory=dict)
    pairs: list[tuple[int, int]] = field(default_factory=list)
    i_scale: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict (JSON-friendly)."""
        return {
            "entry": self.entry.to_dict(),
            "fom": float(self.fom),
            "p_values": dict(self.p_values),
            "pairs": [list(p) for p in self.pairs],
            "i_scale": float(self.i_scale),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CandidateResult:
        """Reconstruct a :class:`CandidateResult` from :meth:`to_dict` output."""
        return cls(
            entry=Entry.from_dict(d["entry"]),
            fom=float(d["fom"]),
            p_values=dict(d.get("p_values", {})),
            pairs=[tuple(p) for p in d.get("pairs", [])],
            i_scale=float(d.get("i_scale", 1.0)),
        )


# --------------------------------------------------------------------------- #
# Batch scoring + ranking
# --------------------------------------------------------------------------- #
def rank_candidates(
    exp_peaks: list[Peak],
    entries: list[Entry],
    wavelength: float,
    *,
    weights: FomWeights | None = None,
    window_deg: float = 0.3,
) -> list[CandidateResult]:
    """Score every candidate entry and return results sorted by FoM desc.

    Implements Match!'s *ranked candidate list* calculation (Phase 6 /
    T6.3): for each candidate reference entry, correlate its (d, I) peak
    table with the experimental peaks, compute the five FoM agreement
    criteria, assemble the FoM, and sort the result list by descending
    FoM.

    Parameters
    ----------
    exp_peaks:
        Experimental peaks (must carry ``two_theta`` and ``intensity``).
    entries:
        Pre-pruned candidate entries (e.g. 1000 left after d-value or
        restraint filtering).  Full COD-scale scoring (500k entries) is
        out of scope here and requires the Hanawalt/Fink pre-filter
        (T6.0, not yet implemented).
    wavelength:
        Wavelength in Å (used both for d→2θ conversion in the
        correlation step).
    weights:
        Optional :class:`~xinmatch.core.search.fom_criteria.FomWeights`
        override.  ``None`` uses the default Match! 4.3 weights.
    window_deg:
        Full width of the peak-correlation window in degrees 2θ
        (default 0.3° — the Match! default).

    Returns
    -------
    list[CandidateResult]
        One result per input entry, sorted by descending FoM.  Ties
        keep the input order (Python's ``sorted`` is stable).
    """
    w = weights if weights is not None else DEFAULT_WEIGHTS
    results: list[CandidateResult] = []
    for entry in entries:
        # Build the reference (d, intensity) peak list expected by the
        # correlate / FoM pipeline.  Entry stores d_spacings / intensities
        # as numpy arrays; .tolist() gives plain Python floats.
        ref_peaks_d_intensity: list[tuple[float, float]] = list(
            zip(
                entry.d_spacings.tolist(),
                entry.intensities.tolist(),
                strict=True,
            )
        )
        pairs = correlate_peaks(
            exp_peaks,
            ref_peaks_d_intensity,
            wavelength,
            window_deg,
        )
        p = compute_p_values(
            exp_peaks,
            ref_peaks_d_intensity,
            pairs,
            wavelength,
        )
        fom = compute_fom(p, w)
        results.append(
            CandidateResult(
                entry=entry,
                fom=fom,
                p_values=p,
                pairs=pairs,
                i_scale=float(p.get("i_scale", 1.0)),
            )
        )
    # Stable sort: ties preserve input order (deterministic for tests).
    results.sort(key=lambda r: r.fom, reverse=True)
    return results


def select_top_n(
    results: list[CandidateResult],
    n: int = 20,
) -> list[CandidateResult]:
    """Return the first *n* entries of a ranked candidate list.

    Implements Match!'s practical Top-N display limit (Phase 6 / T6.3).
    The default ``n=20`` matches the number of candidate-list rows
    typically shown in the Match! GUI without scrolling.

    Parameters
    ----------
    results:
        Ranked candidate list (e.g. as returned by :func:`rank_candidates`).
    n:
        Number of top candidates to keep.  ``0`` returns an empty list.
        Negative values raise :class:`ValueError`.

    Returns
    -------
    list[CandidateResult]
        A *new* list (the input is not mutated) of length
        ``min(n, len(results))``.
    """
    if n < 0:
        raise ValueError(f"n must be non-negative, got {n}")
    return list(results[:n])
