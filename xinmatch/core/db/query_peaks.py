"""d-spacing (peak-based) search-match (Phase 5 / T5.4) ⭐ core.

Implements Match!'s *Search/Match → Peak-based search*: given a list of
experimental d-spacings, rank reference entries by how many of their
calculated peaks fall within a tolerance window of the experimental peaks.

The query uses the ``idx_peaks_d`` B-tree index so each experimental peak is
matched in O(log n) via ``WHERE d BETWEEN ? AND ?``.
"""

from __future__ import annotations

import logging
import sqlite3
from collections import Counter

logger = logging.getLogger(__name__)


def search_by_d(
    conn: sqlite3.Connection,
    peak_ds: list[float],
    tolerance: float = 0.02,
) -> list[tuple[str, float]]:
    """Search reference entries by experimental d-spacings.

    Implements Match!'s peak-based search-match (Phase 5 / T5.4).

    For every experimental d-spacing *d*, the database peaks within
    ``[d - tolerance, d + tolerance]`` are collected; an entry scores one
    point per *distinct experimental peak* it matches.  Results are returned
    sorted by match count descending.

    Parameters
    ----------
    conn:
        Open database connection.
    peak_ds:
        Experimental d-spacings (Å) to match against.
    tolerance:
        Half-width of the matching window in Å (default 0.02).

    Returns
    -------
    list[tuple[str, float]]
        ``(entry_id, matched_peak_count)`` tuples ordered by descending
        match count.  Only entries with at least one match are returned.
    """
    if not peak_ds:
        return []

    scores: Counter[str] = Counter()
    for d in peak_ds:
        lo = d - tolerance
        hi = d + tolerance
        cur = conn.execute(
            "SELECT DISTINCT entry_id FROM peaks WHERE d BETWEEN ? AND ?",
            (lo, hi),
        )
        for (entry_id,) in cur:
            scores[entry_id] += 1

    # Sort by count desc, then entry_id for deterministic ordering.
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [(eid, float(cnt)) for eid, cnt in ranked]


def search_by_d_with_intensity(
    conn: sqlite3.Connection,
    peak_ds: list[float],
    intensities: list[float] | None = None,
    tolerance: float = 0.02,
) -> list[tuple[str, float]]:
    """Intensity-weighted d-spacing search (Match! FoM-style scoring).

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
