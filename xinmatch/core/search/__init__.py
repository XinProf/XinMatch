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
mineral_name
    Mineral-name → species-key normalisation, used as the **benchmark** ruler
    for mineral-level ground truth (``Quartz high`` ≡ ``Quartz``,
    ``Nitrocalcite`` ≢ ``Calcite``, ``hexagonal`` ≡ no name).
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
from .fpfm import (
    FpfmConfig,
    expand_reflections,
    fit_candidate,
    generate_theory_profile,
    search_match_fpfm,
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
from .mineral_name import mineral_name_matches, mineral_species_key
from .pfsm import (
    compute_reference_pattern,
    compute_rwp,
    fit_scale_shift,
    pfsm_rank,
    pfsm_score,
)
from .phase_key import (
    PhaseFamily,
    families,
    group_same_phase,
    normalize_formula,
    parse_composition,
    same_phase,
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
from .sequential import (
    DEFAULT_ABS_FLOOR,
    DEFAULT_ANCHOR_ALPHA,
    DEFAULT_ANCHOR_MAX_REFLECTIONS,
    DEFAULT_ANCHOR_MIN_NCORR,
    DEFAULT_ANCHOR_MIN_PAIRS,
    DEFAULT_ANCHOR_PEAKPOS,
    DEFAULT_ANCHOR_POLICY,
    DEFAULT_EXPLAINED_FRAC,
    DEFAULT_MIN_PEAK_FRAC,
    AnchorPolicy,
    PhaseSelection,
    ResidualSearchResult,
    SequentialIdentifier,
    search_residual,
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
    # FPFM (full-pattern search-match)
    "FpfmConfig",
    "expand_reflections",
    "generate_theory_profile",
    "fit_candidate",
    "search_match_fpfm",
    # Residual-driven FoM recompute (T6.8)
    "recompute_fom_after_selection",
    "build_residual_peaks",
    "EXPLAINED_THRESHOLD",
    # Sequential / iterative phase identification (v3.1.0)
    "SequentialIdentifier",
    "PhaseSelection",
    "ResidualSearchResult",
    "search_residual",
    "DEFAULT_EXPLAINED_FRAC",
    "DEFAULT_ABS_FLOOR",
    "DEFAULT_MIN_PEAK_FRAC",
    # Strong-line anchoring / sparse-phase marks (v3.3.0)
    "AnchorPolicy",
    "DEFAULT_ANCHOR_POLICY",
    "DEFAULT_ANCHOR_ALPHA",
    "DEFAULT_ANCHOR_PEAKPOS",
    "DEFAULT_ANCHOR_MIN_PAIRS",
    "DEFAULT_ANCHOR_MIN_NCORR",
    "DEFAULT_ANCHOR_MAX_REFLECTIONS",
    # Phase-level identity / near-duplicate families (v3.2.0)
    "PhaseFamily",
    "parse_composition",
    "normalize_formula",
    "same_phase",
    "group_same_phase",
    "families",
    # Mineral-name normalisation (benchmark ruler, 2026-11-06)
    "mineral_species_key",
    "mineral_name_matches",
]
