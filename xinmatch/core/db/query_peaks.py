"""d-spacing (peak-based) search-match (Phase 5 / T5.4) ⭐ core.

Implements the reference software's *Search/Match → Peak-based search*: given a list of
experimental d-spacings, rank reference entries by how many of their
calculated peaks fall within a tolerance window of the experimental peaks.

The query uses the ``idx_peaks_d`` B-tree index so each experimental peak is
matched in O(log n) via ``WHERE d BETWEEN ? AND ?``.
"""

from __future__ import annotations

import logging
import math
import sqlite3
from collections import Counter

logger = logging.getLogger(__name__)


def search_by_d(
    conn: sqlite3.Connection,
    peak_ds: list[float],
    tolerance: float = 0.02,
    *,
    wavelength: float | None = None,
    window_deg: float = 0.3,
    min_matches: int = 1,
    max_candidates: int | None = None,
    strongest_peak_only: bool = False,
) -> list[tuple[str, float]]:
    """Search reference entries by experimental d-spacings.

    Implements the reference software's peak-based search-match (Phase 5 / T5.4).

    For every experimental d-spacing *d*, the database peaks within the
    matching window are collected; an entry scores one point per
    *distinct experimental peak* it matches.  Results are returned
    sorted by match count descending.

    Two window modes:

    * **Fixed-Å window** (default, backwards compatible): every peak uses
      ``[d - tolerance, d + tolerance]``.  On a full COD-scale database
      (millions of peak rows) a fixed Å window is too wide at small *d*
      and retrieves tens of thousands of candidates per peak.
    * **Fixed-2θ window** (``wavelength`` given): the window is converted
      from a constant 2θ half-width (``window_deg`` full width, same
      convention as the FoM correlation window), which narrows with
      decreasing *d* — physically correct (a constant angular window on
      the diffractometer) and far more selective on real databases.

    With ``min_matches`` / ``max_candidates`` the returned candidate set
    is pruned to the entries that matched at least *min_matches*
    distinct peaks and, when given, capped to the top *max_candidates*
    by match count — bounding the downstream FoM scoring cost.

    Parameters
    ----------
    conn:
        Open database connection.
    peak_ds:
        Experimental d-spacings (Å) to match against.
    tolerance:
        Half-width of the matching window in Å (only used when
        *wavelength* is ``None``; default 0.02).
    wavelength:
        Wavelength in Å.  When given, windows are derived from a
        constant 2θ window instead of *tolerance*.
    window_deg:
        Full width of the 2θ window in degrees (default 0.3 — the reference software
        default, same as the FoM correlation window).  Only used when
        *wavelength* is given.
    min_matches:
        Minimum number of distinct experimental peaks an entry must
        match to be returned (default 1 = no pruning).
    max_candidates:
        Optional cap on the number of returned candidates (applied after
        sorting by match count descending).
    strongest_peak_only:
        Hanawalt-style constraint (default ``False``): when ``True``,
        only entries whose *strongest* peak (maximum reference
        intensity) falls inside an experimental window are kept.  This
        prunes the "many peaks happen to coincide with a dense
        multi-phase pattern" false positives that dominate pure match
        counting on full COD-scale databases, and keeps the true phases
        (their strongest lines are present in the pattern).  The score
        remains the number of matched experimental peaks.

    Returns
    -------
    list[tuple[str, float]]
        ``(entry_id, matched_peak_count)`` tuples ordered by descending
        match count.  Only entries with at least one match are returned.
    """
    if not peak_ds:
        return []

    def _window(d: float) -> tuple[float, float]:
        if wavelength is None:
            return d - tolerance, d + tolerance
        # Constant 2θ half-window → d window.  2θ = 2·asin(λ/(2d)).
        half_rad = math.radians(window_deg / 2.0)
        theta = math.asin(wavelength / (2.0 * d))
        sin_lo = math.sin(theta - half_rad)
        if sin_lo <= 0.0:
            return d * 0.9, wavelength / (2.0 * math.sin(theta + half_rad))
        return (
            wavelength / (2.0 * math.sin(theta + half_rad)),
            wavelength / (2.0 * sin_lo),
        )

    scores: Counter[str] = Counter()
    if strongest_peak_only:
        # Restrict to entries whose strongest peak falls in a window.
        # One query per experimental peak; the correlated subquery is
        # served by the idx_peaks_entry_id index.
        for d in peak_ds:
            lo, hi = _window(d)
            cur = conn.execute(
                "SELECT DISTINCT entry_id FROM peaks p "
                "WHERE p.d BETWEEN ? AND ? "
                "AND p.intensity = (SELECT MAX(intensity) FROM peaks "
                "                     WHERE entry_id = p.entry_id)",
                (lo, hi),
            )
            for (entry_id,) in cur:
                scores[entry_id] += 1
    else:
        for d in peak_ds:
            lo, hi = _window(d)
            cur = conn.execute(
                "SELECT DISTINCT entry_id FROM peaks WHERE d BETWEEN ? AND ?",
                (lo, hi),
            )
            for (entry_id,) in cur:
                scores[entry_id] += 1

    # Prune by minimum match count, sort by count desc, then cap.
    ranked = sorted(
        ((eid, float(cnt)) for eid, cnt in scores.items()
         if cnt >= min_matches),
        key=lambda kv: (-kv[1], kv[0]),
    )
    if max_candidates is not None:
        ranked = ranked[:max_candidates]
    return ranked


def search_by_d_with_intensity(
    conn: sqlite3.Connection,
    peak_ds: list[float],
    intensities: list[float] | None = None,
    tolerance: float = 0.02,
) -> list[tuple[str, float]]:
    """Intensity-weighted d-spacing search (the reference software FoM-style scoring).

    Like :func:`search_by_d` but each matched peak contributes the
    experimental intensity instead of 1, producing a figure-of-merit score.

    Parameters
    ----------
    conn:
        Open database connection.
    peak_ds:
        Experimental d-spacings (Å).
    intensities:
        Experimental intensities aligned with *peak_ds*.  If ``None``,
        every peak has weight 1 (same as :func:`search_by_d`).
    tolerance:
        Half-width of the matching window in Å.

    Returns
    -------
    list[tuple[str, float]]
        ``(entry_id, score)`` tuples ordered by descending score.
    """
    if not peak_ds:
        return []
    if intensities is None:
        intensities = [1.0] * len(peak_ds)
    if len(intensities) != len(peak_ds):
        raise ValueError("peak_ds and intensities must have the same length")

    scores: dict[str, float] = {}
    for d, w in zip(peak_ds, intensities, strict=True):
        cur = conn.execute(
            "SELECT DISTINCT entry_id FROM peaks WHERE d BETWEEN ? AND ?",
            (d - tolerance, d + tolerance),
        )
        for (entry_id,) in cur:
            scores[entry_id] = scores.get(entry_id, 0.0) + float(w)

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked


def get_entry_peaks(
    conn: sqlite3.Connection,
    entry_id: str,
) -> list[tuple[float, float, int | None, int | None, int | None]]:
    """Return the d–I–hkl peak table for a single entry.

    Parameters
    ----------
    conn:
        Open database connection.
    entry_id:
        Entry identifier.

    Returns
    -------
    list[tuple[float, float, int | None, int | None, int | None]]
        Peaks as ``(d, intensity, h, k, l)`` ordered by descending intensity.
    """
    cur = conn.execute(
        """
        SELECT d, intensity, h, k, l FROM peaks
        WHERE entry_id = ?
        ORDER BY intensity DESC
        """,
        (entry_id,),
    )
    return cur.fetchall()
