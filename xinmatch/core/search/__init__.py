"""Search-Match engine (Phase 6 / T6.1 + T6.2 + T6.3 + T6.4 + T6.7 + T7).

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
fom
    Batch FoM scoring + ranking (CandidateResult, rank_candidates,
    select_top_n).
search_match
    Full peak-based search-match main loop (search_match,
    search_marked_peaks, fetch_entries_by_ids).
candidate_list
    CandidateList container backing the candidate-list GUI panel
    (sort, filter, selection, unassociated-peak introspection).
restraints_apply
    Apply :class:`~xinmatch.core.model.Restraints` to the reference database
    and to candidate lists (pre-search pruning, post-search pruning,
    candidate ranking by restraint satisfaction).
"""

from .candidate_list import CandidateList
from .correlate import correlate, correlate_peaks, d_to_two_theta
from .fom import CandidateResult, rank_candidates, select_top_n
from .fom_criteria import (
    DEFAULT_WEIGHTS,
    FomWeights,
    compute_fom,
    compute_p_values,
    score_candidate,
)
from .hanawalt_fink import (
    build_hanawalt_lookup,
    fink_index,
    hanawalt_index,
    make_hanawalt_key,
    pre_filter,
    pre_filter_fink,
    pre_filter_hanawalt,
)
from .pfsm import (
    compute_reference_pattern,
    compute_rwp,
    fit_scale_shift,
    pfsm_rank,
    pfsm_score,
)
from .residual_update import (
    EXPLAINED_THRESHOLD,
    build_residual_peaks,
    recompute_fom_after_selection,
)
from .restraints_apply import (
    apply_restraints,
    prune_candidates,
    score_restraints_match,
)
from .search_match import (
    fetch_entries_by_ids,
    search_marked_peaks,
    search_match,
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
    # batch fom (T6.3)
    "CandidateResult",
    "rank_candidates",
    "select_top_n",
    # search-match main loop (T6.4 / T6.5)
    "search_match",
    "search_marked_peaks",
    "fetch_entries_by_ids",
    # candidate list (T6.7)
    "CandidateList",
    # restraints
    "apply_restraints",
    "prune_candidates",
    "score_restraints_match",
    # Hanawalt / Fink coarse pre-filter (T6.0)
    "hanawalt_index",
    "fink_index",
    "make_hanawalt_key",
    "build_hanawalt_lookup",
    "pre_filter_hanawalt",
    "pre_filter_fink",
    "pre_filter",
    # PFSM (T6.6)
    "compute_reference_pattern",
    "fit_scale_shift",
    "compute_rwp",
    "pfsm_score",
    "pfsm_rank",
    # Residual-driven FoM recompute (T6.8)
    "recompute_fom_after_selection",
    "build_residual_peaks",
    "EXPLAINED_THRESHOLD",
]
