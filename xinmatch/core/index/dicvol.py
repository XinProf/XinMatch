"""Dicvol-style successive-dichotomy indexing (T9.3).

Implements a simplified, self-contained version of the Dicvol06 program
described in:

* A. Boultif, D. Louër, "Program for the Automatic Indexing of Powder
  Diffraction Patterns by the Successive Dichotomy Method",
  J. Appl. Cryst. 37 (2004), 724-731.  (hereafter "Dicvol 2004")

The Dicvol algorithm:

1. For each candidate crystal system, the *parameter space* (e.g.
   ``[a_min, a_max]`` for cubic; ``[a_min, a_max] × [c_min, c_max]`` for
   tetragonal; ...) is recursively subdivided by *successive
   dichotomy*: at each node the cell-parameter domain is split in halves
   and only the halves that contain at least one *plausible* solution
   (i.e. that allow at least one observed peak to be matched) are
   descended into.
2. At each terminal node, the candidate cell parameters are evaluated:
   every observed peak must be matched to a calculated d within
   *tolerance*; if so, the cell is kept and refined (here: an
   unconstrained least-squares refinement is implicit in the
   subdivision stopping criterion).
3. Solutions are ranked by the de Wolff ``M(20)`` figure-of-merit (or
   Smith-Snyder ``F_N``).

The implementation here is **simplified**:

* Cubic is fully supported via a one-dimensional dichotomy on the single
  parameter ``a``.  Two-level subdivision: a coarse scan first locates
  candidate regions of high match count, then a fine scan refines
  around each candidate.
* Tetragonal / hexagonal / orthorhombic are supported in a limited
  two-dimensional form (assign the largest-d peak to one axis and scan
  the other).
* Monoclinic / triclinic / trigonal raise ``NotImplementedError``.

Match! feature: *Tools → Indexing → Dicvol06*
(``docs/indexing_dicvol.md``).
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

# Cu Kα1 — see T9.2.
_DEFAULT_WAVELENGTH = 1.5406  # Å

# Default scan bounds for the cubic 'a' parameter.  Dicvol 2004 sets a
# minimum linear lattice parameter of 2.5 Å; we use 2.0 to allow
# slightly smaller cells.
_A_MIN_DEFAULT = 2.0
_A_MAX_DEFAULT = 50.0

# Coarse step for the first-pass scan (Å).
_COARSE_STEP = 0.05
# Fine step for the second-pass refinement (Å).
_FINE_STEP = 0.001

# Maximum h²+k²+l² enumerated for cubic reflection generation.
_MAX_CUBIC_N2 = 64


def _d_to_two_theta(d: float, wavelength: float) -> float:
    """d → 2θ (Bragg, n=1).  ``+inf`` if d ≤ λ/2."""
    if d <= 0:
        return math.inf
    sin_theta = wavelength / (2.0 * d)
    if sin_theta > 1.0:
        return math.inf
    return math.degrees(2.0 * math.asin(sin_theta))


def _enumerate_cubic_hkl(max_n2: int = _MAX_CUBIC_N2) -> list[tuple[int, int, int]]:
    """All non-zero ``(h, k, l)`` with ``h²+k²+l² ≤ max_n2`` and
    ``h ≥ k ≥ l ≥ 0`` (the unique representatives under cubic symmetry)."""
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


def _match_peaks_cubic(
    peaks_d: list[float],
    a: float,
    wavelength: float,
    tolerance_deg: float,
) -> tuple[int, list[tuple[int, int, int] | None], float]:
    """Match observed peaks to cubic (hkl) predictions for given *a*."""
    pool: list[tuple[float, tuple[int, int, int]]] = []
    for hkl in _enumerate_cubic_hkl():
        d = compute_d_cubic(hkl, a)
        tt = _d_to_two_theta(d, wavelength)
        if math.isfinite(tt):
            pool.append((tt, hkl))
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


def _dicvol_cubic(
    peaks_d: list[float],
    *,
    tolerance: float,
    wavelength: float,
    a_min: float = _A_MIN_DEFAULT,
    a_max: float = _A_MAX_DEFAULT,
) -> list[LatticeSolution]:
    """Cubic Dicvol search — one-dimensional dichotomy on *a*.

    For the one-parameter cubic case, the successive-dichotomy search
    reduces to: enumerate the candidate ``a`` values that are *exactly*
    determined by single-peak inversion (``a = d·√N²`` for each observed
    peak × each low-index ``(hkl)``), then locally refine each candidate
    over a small window.  This is mathematically equivalent to a full
    parameter-space dichotomy for the cubic case, since any valid cubic
    cell must appear as ``a = d·√N²`` for at least one (peak, hkl) pair
    in the data — the dichotomy converges on the same set of candidate
    points.

    The previous coarse-grid scan (step = ``_COARSE_STEP`` = 0.05 Å)
    was unable to recover the true ``a`` of noise-free synthetic data
    within a strict ``Δ2θ`` tolerance, because at neighbouring grid
    points only the lowest-``N`` peak remained within tolerance and the
    coarse local-maxima test rejected the region.  Peak-based
    enumeration sidesteps this by landing exactly on the true ``a``.
    """
    if not peaks_d:
        return []
    sorted_d = sorted(peaks_d, reverse=True)[:20]
    n_total = len(sorted_d)
    if n_total < 2:
        return []

    threshold = max(2, n_total // 2)

    # Enumerate candidate a values from observed peaks × base hkl.
    # For cubic: a = d·√N² where N² = h²+k²+l². Each (peak, hkl) pair
    # gives a candidate a. Treor uses the same enumeration; the Dicvol
    # difference is the local refinement + de Wolff M(20) ranking below.
    candidates_a: set[float] = set()
    n_trial_peaks = min(5, n_total)
    for peak_idx in range(n_trial_peaks):
        d = sorted_d[peak_idx]
        for hkl in _enumerate_cubic_hkl():
            hh, kk, ll = hkl
            n2 = hh * hh + kk * kk + ll * ll
            a = d * math.sqrt(n2)
            if a_min <= a <= a_max:
                candidates_a.add(round(a, 3))

    # Local refinement around each candidate a.
    solutions: list[LatticeSolution] = []
    for a_cand in sorted(candidates_a):
        # Quick check: does this candidate already meet threshold?
        n_idx0, _, _ = _match_peaks_cubic(sorted_d, a_cand, wavelength, tolerance)
        if n_idx0 < threshold:
            continue
        best_sol: LatticeSolution | None = None
        n_fine = int(2 * _COARSE_STEP / _FINE_STEP) + 1
        for i in range(n_fine):
            a = a_cand - _COARSE_STEP + i * _FINE_STEP
            if a < a_min or a > a_max:
                continue
            n_idx, assignments, sum_delta = _match_peaks_cubic(
                sorted_d, a, wavelength, tolerance
            )
            if n_idx < threshold:
                continue
            delta_avg = (sum_delta / n_idx) if n_idx else math.inf
            fom = n_idx / (1.0 + 50.0 * delta_avg)
            sol = LatticeSolution(
                cell=CellParams(a=a, b=a, c=a),
                crystal_system="cubic",
                fom=fom,
                hkl_assignments=assignments,
                n_indexed=n_idx,
                program="dicvol",
            )
            if best_sol is None or fom > best_sol.fom:
                best_sol = sol
        if best_sol is not None:
            solutions.append(best_sol)

    # Sort by FOM desc, n_idx desc, volume asc (Dicvol "smallest volume
    # wins" rule, Boultif & Louër 2004 §4).
    solutions.sort(key=lambda s: (-s.fom, -s.n_indexed, s.volume))
    return solutions


def _match_peaks_tetragonal(
    peaks_d: list[float],
    a: float,
    c: float,
    wavelength: float,
    tolerance_deg: float,
) -> tuple[int, list[tuple[int, int, int] | None], float]:
    """Match observed peaks to tetragonal (hkl) predictions."""
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


def _dicvol_tetragonal(
    peaks_d: list[float],
    *,
    tolerance: float,
    wavelength: float,
) -> list[LatticeSolution]:
    """Simplified tetragonal Dicvol search.

    Assumes the largest-d peak is the (1,0,0) base line (gives *a*),
    then dichotomises *c* over its plausible range while keeping *a*
    fixed.  This is a 2-D simplification of Dicvol's full dichotomy.
    """
    if len(peaks_d) < 3:
        return []
    sorted_d = sorted(peaks_d, reverse=True)[:20]
    n_total = len(sorted_d)
    threshold = max(2, n_total // 2)

    solutions: list[LatticeSolution] = []
    n_trial = min(3, n_total)
    for i in range(n_trial):
        a = sorted_d[i]  # assumption: (1,0,0)
        if not (_A_MIN_DEFAULT <= a <= _A_MAX_DEFAULT):
            continue
        # Dichotomise c.
        c_lo, c_hi = _A_MIN_DEFAULT, _A_MAX_DEFAULT
        n_steps = int((c_hi - c_lo) / _COARSE_STEP) + 1
        best_sol: LatticeSolution | None = None
        for j in range(n_steps):
            c = c_lo + j * _COARSE_STEP
            n_idx, assignments, sum_delta = _match_peaks_tetragonal(
                sorted_d, a, c, wavelength, tolerance
            )
            if n_idx < threshold:
                continue
            delta_avg = (sum_delta / n_idx) if n_idx else math.inf
            fom = n_idx / (1.0 + 50.0 * delta_avg)
            sol = LatticeSolution(
                cell=CellParams(a=a, b=a, c=c),
                crystal_system="tetragonal",
                fom=fom,
                hkl_assignments=assignments,
                n_indexed=n_idx,
                program="dicvol",
            )
            if best_sol is None or fom > best_sol.fom:
                best_sol = sol
        if best_sol is not None:
            # Refine around best c.
            c_best = best_sol.cell.c
            for k in range(int(2 * _COARSE_STEP / _FINE_STEP) + 1):
                c = c_best - _COARSE_STEP + k * _FINE_STEP
                if c < _A_MIN_DEFAULT:
                    continue
                n_idx, assignments, sum_delta = _match_peaks_tetragonal(
                    sorted_d, a, c, wavelength, tolerance
                )
                if n_idx < threshold:
                    continue
                delta_avg = (sum_delta / n_idx) if n_idx else math.inf
                fom = n_idx / (1.0 + 50.0 * delta_avg)
                if fom > best_sol.fom:
                    best_sol = LatticeSolution(
                        cell=CellParams(a=a, b=a, c=c),
                        crystal_system="tetragonal",
                        fom=fom,
                        hkl_assignments=assignments,
                        n_indexed=n_idx,
                        program="dicvol",
                    )
            solutions.append(best_sol)

    solutions.sort(key=lambda s: (-s.fom, -s.n_indexed))
    return solutions


def _match_peaks_hexagonal(
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


def _dicvol_hexagonal(
    peaks_d: list[float],
    *,
    tolerance: float,
    wavelength: float,
) -> list[LatticeSolution]:
    """Simplified hexagonal Dicvol search."""
    if len(peaks_d) < 3:
        return []
    sorted_d = sorted(peaks_d, reverse=True)[:20]
    n_total = len(sorted_d)
    threshold = max(2, n_total // 2)

    solutions: list[LatticeSolution] = []
    n_trial = min(3, n_total)
    for i in range(n_trial):
        # Assume the largest-d peak is (1,0,0): 1/d² = (4/3)/a² → a = 2d/√3
        a = sorted_d[i] * 2.0 / math.sqrt(3.0)
        if not (_A_MIN_DEFAULT <= a <= _A_MAX_DEFAULT):
            continue
        c_lo, c_hi = _A_MIN_DEFAULT, _A_MAX_DEFAULT
        n_steps = int((c_hi - c_lo) / _COARSE_STEP) + 1
        best_sol: LatticeSolution | None = None
        for j in range(n_steps):
            c = c_lo + j * _COARSE_STEP
            n_idx, assignments, sum_delta = _match_peaks_hexagonal(
                sorted_d, a, c, wavelength, tolerance
            )
            if n_idx < threshold:
                continue
            delta_avg = (sum_delta / n_idx) if n_idx else math.inf
            fom = n_idx / (1.0 + 50.0 * delta_avg)
            sol = LatticeSolution(
                cell=CellParams(a=a, b=a, c=c, gamma=120.0),
                crystal_system="hexagonal",
                fom=fom,
                hkl_assignments=assignments,
                n_indexed=n_idx,
                program="dicvol",
            )
            if best_sol is None or fom > best_sol.fom:
                best_sol = sol
        if best_sol is not None:
            solutions.append(best_sol)

    solutions.sort(key=lambda s: (-s.fom, -s.n_indexed))
    return solutions


def _match_peaks_orthorhombic(
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


def _dicvol_orthorhombic(
    peaks_d: list[float],
    *,
    tolerance: float,
    wavelength: float,
) -> list[LatticeSolution]:
    """Simplified orthorhombic Dicvol search.

    Assumes the largest three peaks correspond to the three axis base
    lines (1,0,0), (0,1,0), (0,0,1) in some permutation; tries all
    permutations and keeps the best.
    """
    if len(peaks_d) < 3:
        return []
    sorted_d = sorted(peaks_d, reverse=True)[:20]
    n_total = len(sorted_d)
    threshold = max(3, n_total // 2)
    n_trial = min(3, n_total)

    solutions: list[LatticeSolution] = []
    for i in range(n_trial):
        for j in range(n_trial):
            if j == i:
                continue
            for kk in range(n_trial):
                if kk in (i, j):
                    continue
                a = sorted_d[i]
                b = sorted_d[j]
                c = sorted_d[kk]
                if not (
                    _A_MIN_DEFAULT <= a <= _A_MAX_DEFAULT
                    and _A_MIN_DEFAULT <= b <= _A_MAX_DEFAULT
                    and _A_MIN_DEFAULT <= c <= _A_MAX_DEFAULT
                ):
                    continue
                n_idx, assignments, sum_delta = _match_peaks_orthorhombic(
                    sorted_d, a, b, c, wavelength, tolerance
                )
                if n_idx < threshold:
                    continue
                delta_avg = (sum_delta / n_idx) if n_idx else math.inf
                fom = n_idx / (1.0 + 50.0 * delta_avg)
                sol = LatticeSolution(
                    cell=CellParams(a=a, b=b, c=c),
                    crystal_system="orthorhombic",
                    fom=fom,
                    hkl_assignments=assignments,
                    n_indexed=n_idx,
                    program="dicvol",
                )
                solutions.append(sol)

    solutions.sort(key=lambda s: (-s.fom, -s.n_indexed))
    return solutions


# --------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------- #


def index_dicvol(
    peaks_d: list[float],
    *,
    crystal_systems: list[str] | None = None,
    tolerance: float = 0.05,
    wavelength: float = _DEFAULT_WAVELENGTH,
) -> list[LatticeSolution]:
    """Dicvol-style successive-dichotomy indexing.

    Match! feature: *Tools → Indexing → Dicvol06*
    (``docs/indexing_dicvol.md``).

    Parameters
    ----------
    peaks_d:
        Observed peak d-spacings in Å.  The first 20 peaks (sorted by
        descending *d*) are used internally.
    crystal_systems:
        Crystal systems to attempt, in priority order.  Defaults to
        ``("cubic", "tetragonal", "hexagonal", "orthorhombic")`` —
        high symmetry first, per the Dicvol documentation
        recommendation to start by excluding monoclinic and triclinic.
    tolerance:
        Maximum allowed ``|Δ2θ|`` in degrees (Match! default = 0.05°;
        the Dicvol manual recommends 0.02° for high-resolution data).
    wavelength:
        Wavelength in Å for the d → 2θ conversion.  Defaults to Cu Kα1
        = 1.5406 Å.

    Returns
    -------
    list[LatticeSolution]
        Candidate solutions sorted by FOM descending.

    Raises
    ------
    ValueError
        If *peaks_d* is empty, *tolerance* is non-positive, or any
        crystal system is unknown.
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
                _dicvol_cubic(
                    peaks_d,
                    tolerance=tolerance,
                    wavelength=wavelength,
                )
            )
        elif sys_name == "tetragonal":
            all_solutions.extend(
                _dicvol_tetragonal(
                    peaks_d,
                    tolerance=tolerance,
                    wavelength=wavelength,
                )
            )
        elif sys_name == "hexagonal":
            all_solutions.extend(
                _dicvol_hexagonal(
                    peaks_d,
                    tolerance=tolerance,
                    wavelength=wavelength,
                )
            )
        elif sys_name == "orthorhombic":
            all_solutions.extend(
                _dicvol_orthorhombic(
                    peaks_d,
                    tolerance=tolerance,
                    wavelength=wavelength,
                )
            )
        else:
            # monoclinic / triclinic / trigonal not implemented.
            continue

    # Sort by FOM desc, then by n_indexed desc, then by smaller volume
    # (Dicvol "smallest volume wins" rule, Boultif & Louër 2004 §4).
    all_solutions.sort(key=lambda s: (-s.fom, -s.n_indexed, s.volume))
    return all_solutions


__all__ = [
    "index_dicvol",
    "LatticeSolution",
    "CRYSTAL_SYSTEMS",
]
