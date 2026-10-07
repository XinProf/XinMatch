"""Peak correlation: pair experimental peaks with reference peaks (T6.1).

Implements Match!'s *peak correlation* step that runs as part of the
peak-based search-match (Match! user manual, *Search-Match Basics* /
*Figure-of-Merit Calculation* chapters).

Given a list of experimental peaks and a reference peak table
(``(d, intensity)`` or ``(2θ, intensity)``), find a one-to-one pairing
such that each pair agrees in 2θ within a tolerance window.  Two
strategies are provided:

* **Greedy** (default): sort both lists by 2θ ascending; for each
  experimental peak, scan the reference peaks whose 2θ falls within
  ``±window/2`` of the experimental 2θ and pick the unmatched reference
  peak of **highest intensity**.  The "prefer strongest reference peak"
  rule mirrors the behaviour described in the Match! reference manual:
  when several database peaks fall inside the correlation window, the
  most intense one is taken as the corresponding peak of the unknown
  pattern.
* **Hungarian** (optional): build a cost matrix of 2θ mismatches within
  the window and solve optimally with
  :func:`scipy.optimize.linear_sum_assignment`.  Useful when many
  experimental and reference peaks overlap inside the same window and a
  globally optimal one-to-one assignment is preferred.

Both strategies return ``[(exp_idx, ref_idx), ...]`` with no exp or ref
index appearing twice.

Algorithm source: Match! 4.x user manual (*Peak correlation*,
*Figure-of-Merit Calculation*).  The greedy heuristic is the documented
default; the Hungarian option is a XinMatch extension for robustness.
"""

from __future__ import annotations

import math

import numpy as np

from xinmatch.core.model import Peak


def d_to_two_theta(d: float, wavelength: float) -> float:
    """Convert a d-spacing to scattering angle 2θ (degrees) via Bragg's law.

    Bragg's law (first order, *n=1*)::

        λ = 2 d sin θ   ⇒   2θ = 2 arcsin(λ / (2 d))

    Parameters
    ----------
    d:
        Interplanar d-spacing in Å (must be positive).
    wavelength:
        Wavelength in Å (must be positive).  Cu Kα = 1.5406.

    Returns
    -------
    float
        Scattering angle 2θ in degrees.  ``math.inf`` if *d* is strictly
        below ``wavelength / 2`` (no real solution — the reference peak
        is unreachable at this wavelength and will never correlate).
        At the exact boundary ``d = wavelength / 2`` (``sin θ = 1``),
        ``2θ = 180°`` is returned.

    Raises
    ------
    ValueError
        If *d* or *wavelength* is non-positive.
    """
    if d <= 0.0:
        raise ValueError(f"d-spacing must be positive, got {d}")
    if wavelength <= 0.0:
        raise ValueError(f"wavelength must be positive, got {wavelength}")
    sin_theta = wavelength / (2.0 * d)
    if sin_theta > 1.0:
        # Reference d below the accessible range for this wavelength.
        # Place at +inf so the peak never matches any experimental angle.
        return math.inf
    return math.degrees(2.0 * math.asin(sin_theta))


def correlate(
    exp_peaks: list[Peak],
    ref_peaks_2theta_intensity: list[tuple[float, float]],
    window_deg: float = 0.3,
    *,
    method: str = "greedy",
) -> list[tuple[int, int]]:
    """Correlate experimental peaks with reference ``(2θ, intensity)`` pairs.

    Match! feature: *peak correlation* step of the peak-based
    search-match (T6.1).

    Parameters
    ----------
    exp_peaks:
        Experimental peaks (must carry ``two_theta`` and ``intensity``).
    ref_peaks_2theta_intensity:
        Reference peaks as ``(two_theta_deg, intensity)`` tuples.
    window_deg:
        Full width of the correlation window in degrees 2θ.  A reference
        peak is a candidate for an experimental peak if
        ``|2θ_ref − 2θ_exp| ≤ window_deg / 2``.  Default 0.3°
        (Match! default).
    method:
        ``'greedy'`` (default) or ``'hungarian'``.

    Returns
    -------
    list[tuple[int, int]]
        ``(exp_idx, ref_idx)`` pairs, one-to-one on both sides, sorted by
        experimental index ascending.

    Raises
    ------
    ValueError
        If *method* is unknown.
    """
    if method == "greedy":
        return _greedy_correlate(exp_peaks, ref_peaks_2theta_intensity, window_deg)
    if method == "hungarian":
        return _hungarian_correlate(exp_peaks, ref_peaks_2theta_intensity, window_deg)
    raise ValueError(
        f"unknown method {method!r}; expected 'greedy' or 'hungarian'"
    )


def correlate_peaks(
    exp_peaks: list[Peak],
    ref_peaks_d_intensity: list[tuple[float, float]],
    wavelength: float,
    window_deg: float = 0.3,
    *,
    method: str = "greedy",
) -> list[tuple[int, int]]:
    """Correlate experimental peaks with reference ``(d, intensity)`` pairs.

    Convenience wrapper around :func:`correlate` that first converts the
    reference d-spacings to 2θ using :func:`d_to_two_theta`.

    Parameters
    ----------
    exp_peaks:
        Experimental peaks.
    ref_peaks_d_intensity:
        Reference peaks as ``(d_spacing_Å, intensity)`` tuples.
    wavelength:
        Wavelength in Å used for the d→2θ conversion.
    window_deg:
        Full width of the correlation window in degrees 2θ (default 0.3).
    method:
        ``'greedy'`` (default) or ``'hungarian'``.

    Returns
    -------
    list[tuple[int, int]]
        ``(exp_idx, ref_idx)`` pairs.
    """
    ref_2theta_intensity = [
        (d_to_two_theta(d, wavelength), intensity)
        for d, intensity in ref_peaks_d_intensity
    ]
    return correlate(exp_peaks, ref_2theta_intensity, window_deg, method=method)


# --------------------------------------------------------------------- #
# Greedy correlation
# --------------------------------------------------------------------- #


def _greedy_correlate(
    exp_peaks: list[Peak],
    ref_peaks_2theta_intensity: list[tuple[float, float]],
    window_deg: float,
) -> list[tuple[int, int]]:
    """Greedy one-to-one peak correlation.

    Both lists are sorted by 2θ ascending.  A sliding window advances
    over the reference list (which never has to retreat because the
    experimental 2θ is monotonically non-decreasing).  For each
    experimental peak, all unmatched reference peaks within the window
    are scanned and the one of **highest intensity** is selected.
    """
    half_window = window_deg / 2.0

    # Indices into the original lists, sorted by 2θ ascending.
    # Experimental peaks with identical 2θ keep a stable order (Python's
    # sorted is stable) so the original list order acts as a tie-breaker.
    exp_idx_sorted = sorted(
        range(len(exp_peaks)),
        key=lambda i: exp_peaks[i].two_theta,
    )
    ref_idx_sorted = sorted(
        range(len(ref_peaks_2theta_intensity)),
        key=lambda i: ref_peaks_2theta_intensity[i][0],
    )

    # Reference 2θ values in the sorted order (for the sliding window).
    ref_tt_sorted = [ref_peaks_2theta_intensity[i][0] for i in ref_idx_sorted]

    matched_ref: set[int] = set()
    pairs: list[tuple[int, int]] = []

    lo = 0
    n_ref = len(ref_tt_sorted)
    for ei in exp_idx_sorted:
        exp_tt = exp_peaks[ei].two_theta
        # Advance lo until the reference peak is at or above the lower
        # bound of the window.  Since exp_tt is non-decreasing across
        # iterations, lo only moves forward.
        while lo < n_ref and ref_tt_sorted[lo] < exp_tt - half_window:
            lo += 1
        # Scan the candidate window and pick the strongest unmatched ref.
        hi = lo
        best_ref = -1
        best_intensity = -math.inf
        while hi < n_ref and ref_tt_sorted[hi] <= exp_tt + half_window:
            r_idx = ref_idx_sorted[hi]
            if r_idx not in matched_ref:
                _, intensity = ref_peaks_2theta_intensity[r_idx]
                if intensity > best_intensity:
                    best_intensity = intensity
                    best_ref = r_idx
            hi += 1
        if best_ref >= 0:
            pairs.append((ei, best_ref))
            matched_ref.add(best_ref)

    # Sort by experimental index for stable, deterministic output.
    pairs.sort(key=lambda p: p[0])
    return pairs


# --------------------------------------------------------------------- #
# Hungarian (optimal) correlation
# --------------------------------------------------------------------- #


def _hungarian_correlate(
    exp_peaks: list[Peak],
    ref_peaks_2theta_intensity: list[tuple[float, float]],
    window_deg: float,
) -> list[tuple[int, int]]:
    """Globally optimal one-to-one correlation via the Hungarian algorithm.

    Cost = |2θ_exp − 2θ_ref| if within the window, else a large constant
    so the assignment avoids impossible pairings.  Uses
    :func:`scipy.optimize.linear_sum_assignment`.
    """
    from scipy.optimize import linear_sum_assignment

    n_exp = len(exp_peaks)
    n_ref = len(ref_peaks_2theta_intensity)
    if n_exp == 0 or n_ref == 0:
        return []

    half_window = window_deg / 2.0
    # "Forbidden" cost: large enough that the solver will avoid it
    # whenever a within-window match exists.
    forbidden = half_window * 1e6 + 1.0

    cost = np.full((n_exp, n_ref), fill_value=forbidden, dtype=np.float64)
    for i, peak in enumerate(exp_peaks):
        for j, (ref_tt, _) in enumerate(ref_peaks_2theta_intensity):
            if ref_tt == math.inf:
                continue
            diff = abs(peak.two_theta - ref_tt)
            if diff <= half_window:
                cost[i, j] = diff

    row_ind, col_ind = linear_sum_assignment(cost)
    pairs: list[tuple[int, int]] = []
    for i, j in zip(row_ind, col_ind, strict=True):
        if cost[i, j] < forbidden:
            pairs.append((int(i), int(j)))
    pairs.sort(key=lambda p: p[0])
    return pairs
