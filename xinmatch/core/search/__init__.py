"""Search-Match engine (Phase 6 / T6.1 + T6.2 + T7).

Peak-based search-match core, GUI-free.  Consumes
:class:`~xinmatch.core.model.Peak` lists and reference ``(d, I)`` peak
tables and produces FoM-ranked candidate lists.

Submodules
----------
correlate
    Experimental ↔ reference peak correlation (greedy / Hungarian)
    and Bragg's law d→2θ helper.
fom_criteria
    Figure-of-Merit (FoM) computation: P values, weights, scoring.
restraints_apply
    Apply :class:`~xinmatch.core.model.Restraints` to the reference database
    and to candidate lists (pre-search pruning, post-search pruning,
    candidate ranking by restraint satisfaction).
"""

from .correlate import correlate, correlate_peaks, d_to_two_theta
from .fom_criteria import (
    DEFAULT_WEIGHTS,
    FomWeights,
    compute_fom,
    compute_p_values,
    score_candidate,
)
from .restraints_apply import (
    apply_restraints,
    prune_candidates,
    score_restraints_match,
)

__all__ = [
    # correlate
    "correlate",
    "correlate_peaks",
    "d_to_two_theta",
    # fom
    "FomWeights",
    "DEFAULT_WEIGHTS",
    "compute_p_values",
    "compute_fom",
    "score_candidate",
    # restraints
    "apply_restraints",
    "prune_candidates",
    "score_restraints_match",
]
