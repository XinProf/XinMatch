"""Treor-style trial-and-error indexing (T9.2).

Implements a simplified, self-contained version of the Treor90 program
described in:

* P.-E. Werner, "Trial-and-error computer methods for the indexing of
  unknown powder patterns", Z. Krist. 120 (1964), 375-387.
* P.-E. Werner, L. Eriksson, M. Westdahl, "Treor, a semi-exhaustive
  trial-and-error powder indexing program for all symmetries",
  J. Appl. Cryst. 18 (1985), 367-370.  (hereafter "Treor 1985")

This module is the *algebraic core* of Treor — it does not read or
write the original Treor input/output files; for that see
:mod:`xinmatch.core.io` (TODO).  The algorithm:

1. Sort peaks by *d* descending (= lowest 2θ first).
2. For each candidate crystal system (cubic first, since it has only
   one free parameter and is the easiest), try assigning the largest-*d*
   peaks to low-index Miller indices (the so-called *base lines* of
   Treor).
3. For each trial assignment, solve for the unit-cell parameters (using
   :func:`~xinmatch.core.index.lattice.solve_reciprocal_lattice`).
4. Re-compute predicted d's for all allowed reflections and count how
   many observed peaks are matched within the 2θ tolerance.
5. Rank by ``n_indexed`` and figure-of-merit, keep the best.

The implementation here is **simplified**:

* Cubic is fully supported (one-parameter search via assignment of the
  first peak to a low-index ``(h, k, l)``).
* Tetragonal / hexagonal / orthorhombic are supported in a limited form
  (assume the first 1-2 peaks are axis-aligned low-index base lines).
* Monoclinic / triclinic raise ``NotImplementedError``.

The reference software feature: *Tools → Indexing → Treor90* (``docs/indexing_treor.md``).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from xinmatch.core.index.lattice import (
    CRYSTAL_SYSTEMS,
    LatticeSolution,
    _validate_crystal_system,
    compute_d_cubic,
    compute_d_hexagonal,
    compute_d_orthorhombic,
    compute_d_tetragonal,
)
from xinmatch.core.model.entry import CellParams

if TYPE_CHECKING:
    pass

# Cu Kα1, the default wavelength used throughout the indexing engine
# when no wavelength is supplied explicitly.
_DEFAULT_WAVELENGTH = 1.5406  # Å

# Lowest common low-index cubic hkl's, ordered by N² = h²+k²+l² (Treor
# convention).  Used to enumerate trial base-line assignments.
_CUBIC_BASE_HKL: tuple[tuple[int, int, int], ...] = (
    (1, 0, 0),
    (1, 1, 0),
    (1, 1, 1),
    (2, 0, 0),
    (2, 1, 0),
    (2, 1, 1),
    (2, 2, 0),
    (2, 2, 1),
    (3, 0, 0),
    (3, 1, 0),
    (3, 1, 1),
    (2, 2, 2),
    (3, 2, 0),
    (3, 2, 1),
    (4, 0, 0),
    (3, 3, 0),
    (3, 3, 1),
    (4, 2, 0),
    (4, 2, 1),
)

# Maximum h²+k²+l² we enumerate when generating predicted cubic reflections
# (sufficient for d ≥ ~1 Å at typical cell lengths ≤ ~25 Å).
_MAX_CUBIC_N2 = 64


def _d_to_two_theta(d: float, wavelength: float) -> float:
    """d→2θ in degrees (Bragg's law, n=1).  Returns ``+inf`` if the
    d-spacing is below ``λ/2`` (unreachable)."""
    if d <= 0:
        return math.inf
    sin_theta = wavelength / (2.0 * d)
    if sin_theta > 1.0:
        return math.inf
    return math.degrees(2.0 * math.asin(sin_theta))


def _two_theta_to_d(two_theta: float, wavelength: float) -> float:
    """2θ→d in degrees (inverse Bragg)."""
    if two_theta <= 0 or two_theta >= 180:
        return math.inf
    sin_theta = math.sin(math.radians(two_theta / 2.0))
    if sin_theta <= 0:
        return math.inf
    return wavelength / (2.0 * sin_theta)


def _enumerate_cubic_hkl(max_n2: int = _MAX_CUBIC_N2) -> list[tuple[int, int, int]]:
    """All (h, k, l) with h²+k²+l² ≤ max_n2, h ≥ k ≥ l ≥ 0."""
    out: list[tuple[int, int, int]] = []
    limit = int(math.isqrt(max_n2)) + 1
    for h in range(limit):
        for k in range(h + 1):
            for ll in range(k + 1):
                if h == 0 and k == 0 and ll == 0:
                    continue
                if h * h + k * k + ll * ll > max_n2:
                    continue
                out.append((h, k, ll))
    return out


def _match_peaks_to_hkl_cubic(
    peaks_d: list[float],
    a: float,
    wavelength: float,
    tolerance_deg: float,
) -> tuple[int, list[tuple[int, int, int] | None], float]:
    """For each observed peak, find the cubic hkl whose predicted d gives
    the smallest |Δ2θ| within *tolerance_deg*.  Returns
    ``(n_indexed, hkl_assignments, sum_abs_delta_two_theta)``.
    """
    hkl_pool = _enumerate_cubic_hkl()
    # Pre-compute predicted (hkl, d, 2θ) for this 'a'
    predictions: list[tuple[float, tuple[int, int, int]]] = []
    for hkl in hkl_pool:
        d = compute_d_cubic(hkl, a)
        predictions.append((_d_to_two_theta(d, wavelength), hkl))
    predictions.sort(key=lambda x: x[0])

    n_indexed = 0
    sum_delta = 0.0
    assignments: list[tuple[int, int, int] | None] = []
    for d_obs in peaks_d:
        if d_obs <= 0:
            assignments.append(None)
            continue
        tt_obs = _d_to_two_theta(d_obs, wavelength)
        if not math.isfinite(tt_obs):
            assignments.append(None)
            continue
        best_hkl: tuple[int, int, int] | None = None
        best_err = math.inf
        for tt_calc, hkl in predictions:
            err = abs(tt_calc - tt_obs)
            if err < best_err:
                best_err = err
                best_hkl = hkl
        if best_hkl is not None and best_err <= tolerance_deg:
            n_indexed += 1
            sum_delta += best_err
            assignments.append(best_hkl)
        else:
            assignments.append(None)
    return n_indexed, assignments, sum_delta


def _treor_cubic(
    peaks_d: list[float],
    *,
    max_iter: int,
    tolerance: float,
    wavelength: float,
) -> list[LatticeSolution]:
    """Cubic Treor trial search — single-parameter 'a'."""
    if not peaks_d:
        return []
    # Sort peaks by d descending (= 2θ ascending) and take the first 20.
    sorted_d = sorted(peaks_d, reverse=True)[:20]
    n_total = len(sorted_d)

    solutions: list[LatticeSolution] = []
    seen_a: set[int] = set()  # de-duplicate by 'a' rounded to 0.001 Å
    iter_count = 0

    # Try assigning each of the first few peaks to each candidate hkl.
    n_trial_peaks = min(5, n_total)
    for peak_idx in range(n_trial_peaks):
        d = sorted_d[peak_idx]
        for hkl in _CUBIC_BASE_HKL:
            if iter_count >= max_iter:
                break
            iter_count += 1
            hh, kk, ll = hkl
            n2 = hh * hh + kk * kk + ll * ll
            a = d * math.sqrt(n2)
            if not (2.0 <= a <= 50.0):
                continue
            # De-duplicate.
            key = round(a, 3)
            if key in seen_a:
                continue
            seen_a.add(key)

            n_indexed, assignments, sum_delta = _match_peaks_to_hkl_cubic(
                sorted_d, a, wavelength, tolerance
            )
            if n_indexed < max(2, n_total // 2):
                continue

            # de Wolff-style M(N) surrogate (real M(20) computed in
            # solutions.py via wolff_fom()).
            delta_avg = (sum_delta / n_indexed) if n_indexed else math.inf
            fom = n_indexed / (1.0 + 50.0 * delta_avg)

            sol = LatticeSolution(
                cell=CellParams(a=a, b=a, c=a),
                crystal_system="cubic",
                fom=fom,
                hkl_assignments=assignments,
                n_indexed=n_indexed,
                program="treor",
            )
            solutions.append(sol)
        if iter_count >= max_iter:
            break

    return solutions


def _treor_tetragonal(
    peaks_d: list[float],
    *,
    max_iter: int,
    tolerance: float,
    wavelength: float,
) -> list[LatticeSolution]:
    """Simplified tetragonal search.

    Assumes the first observed peak (largest d) is the (1,0,0)/(0,1,0)
    base line (gives a) and the second peak (or one with significantly
    different l) is (0,0,1) (gives c).  Does an exhaustive scan over
    candidate (hkl) assignments for the first 2-3 peaks, but only the
    axis-aligned ones.
    """
    if len(peaks_d) < 3:
        return []
    sorted_d = sorted(peaks_d, reverse=True)[:20]

    solutions: list[LatticeSolution] = []
    iter_count = 0
    n_total = len(sorted_d)
    seen: set[tuple[int, int]] = set()

    # Pick peaks to assign as (1,0,0) (gives a) and (0,0,l) (gives c).
    n_trial = min(5, n_total)
    for i in range(n_trial):
        d_a = sorted_d[i]
        for j in range(n_total):
            if j == i:
                continue
            d_c = sorted_d[j]
            if iter_count >= max_iter:
                break
            iter_count += 1
            a = d_a  # because (1,0,0) → d = a
            c = d_c  # because (0,0,1) → d = c
            if not (2.0 <= a <= 50.0 and 2.0 <= c <= 50.0):
                continue
            key = (round(a, 3), round(c, 3))
            if key in seen:
                continue
            seen.add(key)

            # Now match all peaks against tetragonal hkl's.
            n_indexed, assignments, sum_delta = _match_peaks_to_hkl_tetragonal(
                sorted_d, a, c, wavelength, tolerance
            )
            if n_indexed < max(2, n_total // 2):
                continue

            delta_avg = (sum_delta / n_indexed) if n_indexed else math.inf
            fom = n_indexed / (1.0 + 50.0 * delta_avg)
            sol = LatticeSolution(
                cell=CellParams(a=a, b=a, c=c),
                crystal_system="tetragonal",
                fom=fom,
                hkl_assignments=assignments,
                n_indexed=n_indexed,
                program="treor",
            )
            solutions.append(sol)
        if iter_count >= max_iter:
            break
    return solutions


def _match_peaks_to_hkl_tetragonal(
    peaks_d: list[float],
    a: float,
    c: float,
    wavelength: float,
    tolerance_deg: float,
) -> tuple[int, list[tuple[int, int, int] | None], float]:
    """Match observed peaks to tetragonal (hkl) predictions."""
    # Generate all hkl with h²+k² ≤ ~64 and l² ≤ ~64.
    pool: list[tuple[float, tuple[int, int, int]]] = []
    limit = 12
    for h in range(limit + 1):
        for k in range(h + 1):
            for ll in range(limit + 1):
                if h == 0 and k == 0 and ll == 0:
                    continue
                if h * h + k * k > 64:
                    continue
                d = compute_d_tetragonal((h, k, ll), a, c)
                tt = _d_to_two_theta(d, wavelength)
                if math.isfinite(tt):
                    pool.append((tt, (h, k, ll)))
    pool.sort(key=lambda x: x[0])

    n_indexed = 0
    sum_delta = 0.0
    assignments: list[tuple[int, int, int] | None] = []
    for d_obs in peaks_d:
        if d_obs <= 0:
            assignments.append(None)
            continue
        tt_obs = _d_to_two_theta(d_obs, wavelength)
        if not math.isfinite(tt_obs):
            assignments.append(None)
            continue
        best_hkl: tuple[int, int, int] | None = None
        best_err = math.inf
        for tt_calc, hkl in pool:
            err = abs(tt_calc - tt_obs)
            if err < best_err:
                best_err = err
                best_hkl = hkl
        if best_hkl is not None and best_err <= tolerance_deg:
            n_indexed += 1
            sum_delta += best_err
            assignments.append(best_hkl)
        else:
            assignments.append(None)
    return n_indexed, assignments, sum_delta


def _treor_orthorhombic(
    peaks_d: list[float],
    *,
    max_iter: int,
    tolerance: float,
    wavelength: float,
) -> list[LatticeSolution]:
    """Simplified orthorhombic search.

    Assigns the first three peaks (largest d) to (1,0,0), (0,1,0),
    (0,0,1) in some permutation, solves for (a, b, c), and matches.
    """
    if len(peaks_d) < 3:
        return []
    sorted_d = sorted(peaks_d, reverse=True)[:20]
    n_total = len(sorted_d)
    n_trial = min(5, n_total)

    solutions: list[LatticeSolution] = []
    iter_count = 0
    seen: set[tuple[int, int, int]] = set()

    for i in range(n_trial):
        for j in range(n_trial):
            if j == i:
                continue
            for kk in range(n_trial):
                if kk in (i, j):
                    continue
                if iter_count >= max_iter:
                    break
                iter_count += 1
                a = sorted_d[i]
                b = sorted_d[j]
                c = sorted_d[kk]
                if not (2.0 <= a <= 50.0 and 2.0 <= b <= 50.0 and 2.0 <= c <= 50.0):
                    continue
                key = (round(a, 3), round(b, 3), round(c, 3))
                if key in seen:
                    continue
                seen.add(key)

                n_indexed, assignments, sum_delta = _match_peaks_to_hkl_orthorhombic(
                    sorted_d, a, b, c, wavelength, tolerance
                )
                if n_indexed < max(3, n_total // 2):
                    continue
                delta_avg = (sum_delta / n_indexed) if n_indexed else math.inf
                fom = n_indexed / (1.0 + 50.0 * delta_avg)
                sol = LatticeSolution(
                    cell=CellParams(a=a, b=b, c=c),
                    crystal_system="orthorhombic",
                    fom=fom,
                    hkl_assignments=assignments,
                    n_indexed=n_indexed,
                    program="treor",
                )
                solutions.append(sol)
            if iter_count >= max_iter:
                break
        if iter_count >= max_iter:
            break
    return solutions


def _match_peaks_to_hkl_orthorhombic(
    peaks_d: list[float],
    a: float,
    b: float,
    c: float,
    wavelength: float,
    tolerance_deg: float,
) -> tuple[int, list[tuple[int, int, int] | None], float]:
    pool: list[tuple[float, tuple[int, int, int]]] = []
    limit = 12
    for h in range(limit + 1):
        for k in range(limit + 1):
            for ll in range(limit + 1):
                if h == 0 and k == 0 and ll == 0:
                    continue
                if h * h > 64 or k * k > 64 or ll * ll > 64:
                    continue
                d = compute_d_orthorhombic((h, k, ll), a, b, c)
                tt = _d_to_two_theta(d, wavelength)
                if math.isfinite(tt):
                    pool.append((tt, (h, k, ll)))
    pool.sort(key=lambda x: x[0])

    n_indexed = 0
    sum_delta = 0.0
    assignments: list[tuple[int, int, int] | None] = []
    for d_obs in peaks_d:
        if d_obs <= 0:
            assignments.append(None)
            continue
        tt_obs = _d_to_two_theta(d_obs, wavelength)
        if not math.isfinite(tt_obs):
            assignments.append(None)
            continue
        best_hkl: tuple[int, int, int] | None = None
        best_err = math.inf
        for tt_calc, hkl in pool:
            err = abs(tt_calc - tt_obs)
            if err < best_err:
                best_err = err
                best_hkl = hkl
        if best_hkl is not None and best_err <= tolerance_deg:
            n_indexed += 1
            sum_delta += best_err
            assignments.append(best_hkl)
        else:
            assignments.append(None)
    return n_indexed, assignments, sum_delta


def _treor_hexagonal(
    peaks_d: list[float],
    *,
    max_iter: int,
    tolerance: float,
    wavelength: float,
) -> list[LatticeSolution]:
    """Simplified hexagonal search (assigns (1,0,0) → a, (0,0,1) → c)."""
    if len(peaks_d) < 3:
        return []
    sorted_d = sorted(peaks_d, reverse=True)[:20]
    n_total = len(sorted_d)
    n_trial = min(5, n_total)

    solutions: list[LatticeSolution] = []
    iter_count = 0
    seen: set[tuple[int, int]] = set()

    for i in range(n_trial):
        d_a = sorted_d[i]
        for j in range(n_total):
            if j == i:
                continue
            d_c = sorted_d[j]
            if iter_count >= max_iter:
                break
            iter_count += 1
            # For hexagonal, (1,0,0) → 1/d² = (4/3)·1/a² → a = d·2/√3
            a = d_a * 2.0 / math.sqrt(3.0)
            c = d_c
            if not (2.0 <= a <= 50.0 and 2.0 <= c <= 50.0):
                continue
            key = (round(a, 3), round(c, 3))
            if key in seen:
                continue
            seen.add(key)

            n_indexed, assignments, sum_delta = _match_peaks_to_hkl_hexagonal(
                sorted_d, a, c, wavelength, tolerance
            )
            if n_indexed < max(2, n_total // 2):
                continue
            delta_avg = (sum_delta / n_indexed) if n_indexed else math.inf
            fom = n_indexed / (1.0 + 50.0 * delta_avg)
            sol = LatticeSolution(
                cell=CellParams(a=a, b=a, c=c, gamma=120.0),
                crystal_system="hexagonal",
                fom=fom,
                hkl_assignments=assignments,
                n_indexed=n_indexed,
                program="treor",
            )
            solutions.append(sol)
        if iter_count >= max_iter:
            break
    return solutions


def _match_peaks_to_hkl_hexagonal(
    peaks_d: list[float],
    a: float,
    c: float,
    wavelength: float,
    tolerance_deg: float,
) -> tuple[int, list[tuple[int, int, int] | None], float]:
    pool: list[tuple[float, tuple[int, int, int]]] = []
    limit = 12
    for h in range(limit + 1):
        for k in range(h + 1):
            for ll in range(limit + 1):
                if h == 0 and k == 0 and ll == 0:
                    continue
                if h * h + h * k + k * k > 64:
                    continue
                d = compute_d_hexagonal((h, k, ll), a, c)
                tt = _d_to_two_theta(d, wavelength)
                if math.isfinite(tt):
                    pool.append((tt, (h, k, ll)))
    pool.sort(key=lambda x: x[0])

    n_indexed = 0
    sum_delta = 0.0
    assignments: list[tuple[int, int, int] | None] = []
    for d_obs in peaks_d:
        if d_obs <= 0:
            assignments.append(None)
            continue
        tt_obs = _d_to_two_theta(d_obs, wavelength)
        if not math.isfinite(tt_obs):
            assignments.append(None)
            continue
        best_hkl: tuple[int, int, int] | None = None
        best_err = math.inf
        for tt_calc, hkl in pool:
            err = abs(tt_calc - tt_obs)
            if err < best_err:
                best_err = err
                best_hkl = hkl
        if best_hkl is not None and best_err <= tolerance_deg:
            n_indexed += 1
            sum_delta += best_err
            assignments.append(best_hkl)
        else:
            assignments.append(None)
    return n_indexed, assignments, sum_delta


# --------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------- #


def index_treor(
    peaks_d: list[float],
    *,
    crystal_systems: list[str] | None = None,
    max_iter: int = 1000,
    tolerance: float = 0.05,
    wavelength: float = _DEFAULT_WAVELENGTH,
) -> list[LatticeSolution]:
    """Treor-style trial-and-error indexing.

    The reference software feature: *Tools → Indexing → Treor90*
    (``docs/indexing_treor.md``).

    Parameters
    ----------
    peaks_d:
        Observed peak d-spacings in Å.  Peaks are sorted internally by
        descending *d* (= ascending 2θ) and the first 20 are used, per
        Treor 1985 §3.
    crystal_systems:
        Crystal systems to attempt, in priority order.  Defaults to
        ``("cubic", "tetragonal", "hexagonal", "orthorhombic")``
        (high-symmetry first, Treor's standard procedure).
    max_iter:
        Maximum trial base-line assignments per crystal system.
    tolerance:
        Maximum allowed ``|Δ2θ|`` in degrees between an observed peak
        and its assigned calculated peak (the reference software default = 0.05°).
    wavelength:
        Wavelength in Å used to convert *d* → 2θ for the tolerance
        check.  Defaults to Cu Kα1 = 1.5406 Å.

    Returns
    -------
    list[LatticeSolution]
        All candidate solutions found, sorted by FOM descending (use
        :func:`xinmatch.core.index.solutions.rank_solutions` for
        re-ranking).  May be empty.

    Raises
    ------
    ValueError
        If *peaks_d* is empty, *tolerance* is non-positive, or any
        crystal system in *crystal_systems* is unknown.
    """
    if not peaks_d:
        raise ValueError("peaks_d must not be empty")
    if tolerance <= 0:
        raise ValueError(f"tolerance must be positive, got {tolerance}")
    if wavelength <= 0:
        raise ValueError(f"wavelength must be positive, got {wavelength}")

    if crystal_systems is None:
        crystal_systems = ["cubic", "tetragonal", "hexagonal", "orthorhombic"]

    for sys_name in crystal_systems:
        _validate_crystal_system(sys_name)

    all_solutions: list[LatticeSolution] = []
    for sys_name in crystal_systems:
        if sys_name == "cubic":
            all_solutions.extend(
                _treor_cubic(
                    peaks_d,
                    max_iter=max_iter,
                    tolerance=tolerance,
                    wavelength=wavelength,
                )
            )
        elif sys_name == "tetragonal":
            all_solutions.extend(
                _treor_tetragonal(
                    peaks_d,
                    max_iter=max_iter,
                    tolerance=tolerance,
                    wavelength=wavelength,
                )
            )
        elif sys_name == "hexagonal":
            all_solutions.extend(
                _treor_hexagonal(
                    peaks_d,
                    max_iter=max_iter,
                    tolerance=tolerance,
                    wavelength=wavelength,
                )
            )
        elif sys_name == "orthorhombic":
            all_solutions.extend(
                _treor_orthorhombic(
                    peaks_d,
                    max_iter=max_iter,
                    tolerance=tolerance,
                    wavelength=wavelength,
                )
            )
        else:
            # monoclinic / triclinic / trigonal — not implemented in
            # the simplified Treor.
            continue

    # Sort by FOM desc, then by n_indexed desc, then by smaller volume
    # (Treor's "smaller volume = higher priority" rule, Werner 1985 §3).
    all_solutions.sort(key=lambda s: (-s.fom, -s.n_indexed, s.volume))
    return all_solutions


__all__ = [
    "index_treor",
    "LatticeSolution",
    "CRYSTAL_SYSTEMS",
]
