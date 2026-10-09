"""Solution ranking, deduplication, and figure-of-merit (T9.4).

Implements the solution post-processing used by the reference software's indexing
results dialog (``docs/indexing_solutions.md``):

* :func:`rank_solutions` — sort candidate unit cells by FOM (best
  first).
* :func:`deduplicate` — collapse solutions with near-equal cell
  parameters (lattice-metric singularities — see Dicvol manual §
  *Lattice metric singularity* — can produce many equivalent cells).
* :func:`smith_snyder_fom` — Smith-Snyder ``F_N`` figure-of-merit.
* :func:`wolff_fom` — de Wolff ``M(20)`` figure-of-merit (the Treor
  and Dicvol "main" FoM).

References
----------
* P.M. de Wolff, "A simplified criterion for the reliability of a
  powder pattern indexing", J. Appl. Cryst. 1 (1968), 108-113.
* G.S. Smith, R.L. Snyder, "F_N: a criterion for rating powder
  diffraction patterns", J. Appl. Cryst. 12 (1979), 60-65.
* P.-E. Werner, L. Eriksson, M. Westdahl, J. Appl. Cryst. 18 (1985),
  367-370 (Treor — uses M(20)).
* A. Boultif, D. Louër, J. Appl. Cryst. 37 (2004), 724-731 (Dicvol).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from xinmatch.core.index.lattice import (
    LatticeSolution,
    compute_d_for_system,
)
from xinmatch.core.model.entry import CellParams

if TYPE_CHECKING:
    pass

# Cu Kα1 default wavelength.
_DEFAULT_WAVELENGTH = 1.5406  # Å

# Default cut-off N for FOM (de Wolff M(20), Smith-Snyder F_N).
_DEFAULT_N_FOM = 20


def _d_to_two_theta(d: float, wavelength: float) -> float:
    """d → 2θ (Bragg, n=1).  ``+inf`` if d ≤ λ/2."""
    if d <= 0:
        return math.inf
    sin_theta = wavelength / (2.0 * d)
    if sin_theta > 1.0:
        return math.inf
    return math.degrees(2.0 * math.asin(sin_theta))


def _enumerate_hkl_for_system(
    crystal_system: str,
    max_index: int = 12,
) -> list[tuple[int, int, int]]:
    """Yield all symmetry-unique ``(h, k, l)`` triples up to
    *max_index* per axis.  For high-symmetry systems this over-generates
    (gives non-unique representatives); that is acceptable for FOM
    computation (we just need the calculated peak count in the
    2θ range)."""
    out: list[tuple[int, int, int]] = []
    rng = range(0, max_index + 1)
    if crystal_system == "cubic":
        for h in rng:
            for k in range(h + 1):
                for ll in range(k + 1):
                    if h == 0 and k == 0 and ll == 0:
                        continue
                    out.append((h, k, ll))
    elif crystal_system in ("tetragonal", "hexagonal"):
        for h in rng:
            for k in range(h + 1):
                for ll in rng:
                    if h == 0 and k == 0 and ll == 0:
                        continue
                    out.append((h, k, ll))
    else:
        # orthorhombic / monoclinic / triclinic / trigonal — full
        # enumeration.
        for h in rng:
            for k in rng:
                for ll in rng:
                    if h == 0 and k == 0 and ll == 0:
                        continue
                    out.append((h, k, ll))
    return out


def _calc_peaks_in_range(
    solution: LatticeSolution,
    d_min: float,
    d_max: float,
) -> list[float]:
    """Generated calculated d-spacings within ``[d_min, d_max]`` for
    *solution.cell* under *solution.crystal_system*.

    The d-list is de-duplicated (symmetry-equivalent reflections give
    the same d).
    """
    out: set[float] = set()
    for hkl in _enumerate_hkl_for_system(solution.crystal_system):
        try:
            d = compute_d_for_system(hkl, solution.cell, solution.crystal_system)
        except (ValueError, ZeroDivisionError):
            continue
        if not math.isfinite(d) or d <= 0:
            continue
        if d_min <= d <= d_max:
            out.add(round(d, 6))
    return sorted(out, reverse=True)


# --------------------------------------------------------------------- #
# Figure-of-merit computation
# --------------------------------------------------------------------- #


def wolff_fom(
    solution: LatticeSolution,
    all_peaks_d: list[float],
    *,
    wavelength: float = _DEFAULT_WAVELENGTH,
    n: int = _DEFAULT_N_FOM,
) -> float:
    """de Wolff ``M(N)`` figure-of-merit.

    The Treor/Dicvol standard FOM, defined as (de Wolff 1968):

    .. math::

        M(N) = \\frac{Q'_N}{2\\,\\overline{|\\Delta 2\\theta|}\\,Q^{calc}_N}

    where ``Q'_N = Σ 1/d²`` over the first *N* indexed observed peaks
    (ordered by ascending 2θ), ``Q^{calc}_N`` is the same sum over all
    *calculated* reflections whose *d* falls within the indexed
    observed range, and ``\\overline{|Δ2θ|}`` is the mean absolute 2θ
    deviation of the indexed peaks.  Treor's rule: a solution is
    acceptable iff ``M(20) ≥ 10`` (Werner 1985).

    Parameters
    ----------
    solution:
        Candidate :class:`LatticeSolution` (carries cell, hkl
        assignments and n_indexed).
    all_peaks_d:
        Full list of observed peak d-spacings (same length & order as
        ``solution.hkl_assignments``).
    wavelength:
        Wavelength in Å for the d → 2θ conversion.  Defaults to Cu Kα1.
    n:
        Cut-off *N* for the FOM (default 20 — i.e. ``M(20)``).

    Returns
    -------
    float
        ``M(N)`` value.  Returns ``0.0`` for solutions with no indexed
        peaks.
    """
    if solution.n_indexed == 0 or not all_peaks_d:
        return 0.0

    # Pair observed d's with their (hkl) assignment and convert to 2θ.
    indexed: list[tuple[float, float]] = []  # (2θ_obs, d_obs)
    for d_obs, hkl in zip(all_peaks_d, solution.hkl_assignments, strict=False):
        if hkl is None:
            continue
        if d_obs <= 0:
            continue
        tt_obs = _d_to_two_theta(d_obs, wavelength)
        if not math.isfinite(tt_obs):
            continue
        # Compute the 2θ_calc from the cell + assigned hkl.
        try:
            d_calc = compute_d_for_system(hkl, solution.cell, solution.crystal_system)
        except (ValueError, ZeroDivisionError):
            continue
        tt_calc = _d_to_two_theta(d_calc, wavelength)
        if not math.isfinite(tt_calc):
            continue
        indexed.append((tt_obs, d_obs, tt_calc))

    # Sort by ascending 2θ_obs, take first n.
    indexed.sort(key=lambda x: x[0])
    n_used = min(n, len(indexed))
    if n_used == 0:
        return 0.0
    indexed = indexed[:n_used]

    # Mean abs Δ2θ
    delta_sum = sum(abs(tt_obs - tt_calc) for tt_obs, _d, tt_calc in indexed)
    delta_avg = delta_sum / n_used
    if delta_avg <= 0:
        # Perfect fit — return a large but finite value.
        return 1e6

    # Q'_N: sum of 1/d² for indexed observed peaks.
    q_pos = sum(1.0 / (d * d) for _tt, d, _tt_c in indexed if d > 0)
    if q_pos <= 0:
        return 0.0

    # Q_calc_N: sum of 1/d² for all calculated reflections with
    # d ≥ d_min_indexed and d ≤ d_max_indexed (= the range of indexed
    # observed d's).
    d_min_idx = min(d for _tt, d, _tt_c in indexed if d > 0)
    d_max_idx = max(d for _tt, d, _tt_c in indexed if d > 0)
    # Expand slightly outward to catch boundary reflections.
    d_lo = d_min_idx * (1.0 - 1e-4)
    d_hi = d_max_idx * (1.0 + 1e-4)
    calc_d_list = _calc_peaks_in_range(solution, d_lo, d_hi)
    q_calc = sum(1.0 / (d * d) for d in calc_d_list if d > 0)
    if q_calc <= 0:
        return 0.0

    return q_pos / (2.0 * delta_avg * q_calc)


def smith_snyder_fom(
    solution: LatticeSolution,
    all_peaks_d: list[float],
    *,
    wavelength: float = _DEFAULT_WAVELENGTH,
    n: int = _DEFAULT_N_FOM,
) -> float:
    """Smith-Snyder ``F_N`` figure-of-merit.

    Defined as (Smith & Snyder 1979):

    .. math::

        F_N = \\frac{1}{N_{avg}}
              \\cdot \\frac{N_{pos}}{N_{obs}}
              \\cdot \\frac{1}{\\overline{|\\Delta 2\\theta|}}

    where ``N_pos`` is the number of indexed peaks among the first *N*
    observed peaks (sorted by ascending 2θ), ``N_obs`` is the number of
    observed peaks in the considered 2θ range (here clamped to *N*),
    ``N_{avg}`` is the expected number of peaks in the 2θ range for a
    random lattice with this volume (here approximated by the count of
    calculated reflections in the indexed d-range — see
    :func:`_calc_peaks_in_range`), and
    ``\\overline{|Δ2θ|}`` is the mean absolute 2θ deviation of the
    indexed peaks.

    The simplification ``N_{avg} ≈ N_calc`` follows the original
    Smith-Snyder paper's prescription that *N_avg* may be approximated
    by the calculated peak count.

    Returns
    -------
    float
        ``F_N`` value.  ``0.0`` for solutions with no indexed peaks.
    """
    if solution.n_indexed == 0 or not all_peaks_d:
        return 0.0

    # Collect (2θ_obs, d_obs, 2θ_calc, indexed?) for ALL observed peaks.
    obs_sorted: list[tuple[float, float, float | None, bool]] = []
    for d_obs, hkl in zip(all_peaks_d, solution.hkl_assignments, strict=False):
        if d_obs <= 0:
            continue
        tt_obs = _d_to_two_theta(d_obs, wavelength)
        if not math.isfinite(tt_obs):
            continue
        if hkl is None:
            obs_sorted.append((tt_obs, d_obs, None, False))
            continue
        try:
            d_calc = compute_d_for_system(hkl, solution.cell, solution.crystal_system)
        except (ValueError, ZeroDivisionError):
            obs_sorted.append((tt_obs, d_obs, None, False))
            continue
        tt_calc = _d_to_two_theta(d_calc, wavelength)
        if not math.isfinite(tt_calc):
            obs_sorted.append((tt_obs, d_obs, None, False))
            continue
        obs_sorted.append((tt_obs, d_obs, tt_calc, True))

    obs_sorted.sort(key=lambda x: x[0])
    n_used = min(n, len(obs_sorted))
    if n_used == 0:
        return 0.0
    obs_first_n = obs_sorted[:n_used]

    n_pos = sum(1 for _tt, _d, _ttc, indexed in obs_first_n if indexed)
    n_obs = n_used
    if n_pos == 0:
        return 0.0

    delta_sum = 0.0
    d_min_idx = math.inf
    d_max_idx = 0.0
    for tt_obs, d_obs, tt_calc, indexed in obs_first_n:
        if not indexed or tt_calc is None:
            continue
        delta_sum += abs(tt_obs - tt_calc)
        if d_obs > 0:
            if d_obs < d_min_idx:
                d_min_idx = d_obs
            if d_obs > d_max_idx:
                d_max_idx = d_obs
    delta_avg = delta_sum / n_pos if n_pos else math.inf
    if delta_avg <= 0:
        # Perfect fit.
        return 1e6

    if d_min_idx == math.inf or d_max_idx == 0.0:
        return 0.0

    d_lo = d_min_idx * (1.0 - 1e-4)
    d_hi = d_max_idx * (1.0 + 1e-4)
    calc_d_list = _calc_peaks_in_range(solution, d_lo, d_hi)
    n_avg = len(calc_d_list)
    if n_avg == 0:
        return 0.0

    return (n_pos / n_obs) * (1.0 / delta_avg) * (1.0 / n_avg)


# --------------------------------------------------------------------- #
# Ranking & deduplication
# --------------------------------------------------------------------- #


def rank_solutions(solutions: list[LatticeSolution]) -> list[LatticeSolution]:
    """Sort candidate solutions by FOM (best first).

    The reference software feature: *solution list ordering*
    (``docs/indexing_solutions.md``, FoM column).  The best solution is
    at index 0.

    The sorting key is ``(-fom, -n_indexed, +volume, +n_unindexed)``:
    higher FOM first; on a tie, more peaks indexed first; on a tie,
    smaller cell volume first (Treor's "smaller volume = higher
    priority" rule, Werner 1985 §3); finally fewer unindexed peaks.
    """
    return sorted(
        solutions,
        key=lambda s: (
            -s.fom,
            -s.n_indexed,
            s.volume,
            s.n_unindexed,
        ),
    )


def deduplicate(
    solutions: list[LatticeSolution],
    *,
    tol_cell: float = 0.01,
) -> list[LatticeSolution]:
    """Remove (near-)duplicate solutions.

    Two solutions are considered equivalent ("the same cell") if for
    every direct-lattice parameter ``p ∈ {a, b, c, α, β, γ}`` the
    absolute difference is below *tol_cell* (Å for lengths, degrees for
    angles).  This catches the lattice-metric singularities that Dicvol
    warns about (e.g. an hexagonal cell appearing as orthorhombic with
    ``a/2, a·√3, c``) — for the simplified engine here we only test
    direct parameter equivalence; full singularity detection is left to
    a future refinement phase.

    The first occurrence (after :func:`rank_solutions`) is kept.

    Parameters
    ----------
    solutions:
        List of candidate solutions (will be ranked first internally).
    tol_cell:
        Tolerance in Å (lengths) and degrees (angles).  Default
        ``0.01`` — appropriate for well-converged indexing solutions.
    """
    ranked = rank_solutions(solutions)
    kept: list[LatticeSolution] = []
    for sol in ranked:
        is_dup = False
        for k in kept:
            if _cells_equivalent(sol.cell, k.cell, tol_cell):
                is_dup = True
                break
        if not is_dup:
            kept.append(sol)
    return kept


def _cells_equivalent(c1: CellParams, c2: CellParams, tol: float) -> bool:
    """Check direct-lattice equivalence within *tol*."""
    return (
        abs(c1.a - c2.a) <= tol
        and abs(c1.b - c2.b) <= tol
        and abs(c1.c - c2.c) <= tol
        and abs(c1.alpha - c2.alpha) <= tol
        and abs(c1.beta - c2.beta) <= tol
        and abs(c1.gamma - c2.gamma) <= tol
    )


__all__ = [
    "rank_solutions",
    "deduplicate",
    "smith_snyder_fom",
    "wolff_fom",
]
