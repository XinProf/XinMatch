"""Full peak-based Search-Match main loop (Phase 6 / T6.4).

Orchestrates the complete peak-based search-match workflow documented in
``docs/searchmatch_peak_based.md``:

1. **Candidate generation** — get a list of candidate ``entry_id``s.
   Either:
   * apply :class:`~xinmatch.core.model.Restraints` (composition, crystal
     system, year, ...); or
   * run the d-value retrieval :func:`~xinmatch.core.db.query_peaks.search_by_d`
     on the experimental d-spacing set; or
   * call a user-supplied ``pre_filter`` callable (e.g. Hanawalt/Fink
     index lookup, T6.0 — interface reserved, not yet implemented).
2. **Entry fetch** — materialise :class:`~xinmatch.core.model.Entry`
   objects for the candidate ids (``fetch_entries_by_ids``).
3. **Rank** — :func:`~xinmatch.core.search.fom.rank_candidates` runs
   correlate → compute P values → compute FoM and sorts descending.
4. **Top-N** — :func:`~xinmatch.core.search.fom.select_top_n` keeps the
   first *n* candidates (default 20, the practical GUI display limit).

The function is GUI-free; the GUI layer (Phase 14) wraps it to refresh the
candidate-list view.  Performance target: 1000 candidates scored in under
2 seconds on synthetic data (no real COD dependency) — see
``tests/search/test_search_match.py::test_perf_1000_candidates_under_2s``.
"""

from __future__ import annotations

import logging
import math
import sqlite3
from collections.abc import Callable

import numpy as np

from xinmatch.core.db.query_peaks import search_by_d
from xinmatch.core.model import CellParams, Entry, Peak, Restraints
from xinmatch.core.search.fom import CandidateResult, rank_candidates, select_top_n
from xinmatch.core.search.fom_criteria import FomWeights
from xinmatch.core.search.restraints_apply import apply_restraints

logger = logging.getLogger(__name__)

__all__ = [
    "search_match",
    "search_marked_peaks",
    "fetch_entries_by_ids",
]


# --------------------------------------------------------------------------- #
# Entry fetch helper
# --------------------------------------------------------------------------- #
def fetch_entries_by_ids(
    conn: sqlite3.Connection,
    entry_ids: list[str],
) -> list[Entry]:
    """Materialise :class:`Entry` objects for the given *entry_ids*.

    Reconstructs each Entry from the ``entries`` table (scalar metadata)
    and the ``peaks`` table (d–I–hkl list).  Used by
    :func:`search_match` to bridge the SQL candidate-id set to the
    dataclass-based FoM pipeline.

    Order is preserved: the returned list follows *entry_ids*; ids not
    present in the database are skipped (so the output may be shorter
    than the input).

    Parameters
    ----------
    conn:
        Open SQLite connection to the reference database.
    entry_ids:
        Candidate ids to fetch.

    Returns
    -------
    list[Entry]
        Entries present in the database, in *entry_ids* order.
    """
    if not entry_ids:
        return []

    # SQLite limits statements to ~999 bound parameters per statement by
    # default; chunk the IN(...) clause to stay well below that.
    chunk_size = 500
    ids = list(entry_ids)
    out: dict[str, Entry] = {}

    for i in range(0, len(ids), chunk_size):
        chunk = ids[i : i + chunk_size]
        placeholders = ",".join("?" for _ in chunk)
        cur = conn.execute(
            f"""
            SELECT entry_id, formula, mineral_name, space_group,
                   a, b, c, alpha, beta, gamma, color, year, author,
                   journal, quality
            FROM entries WHERE entry_id IN ({placeholders})
            """,
            chunk,
        )
        for row in cur.fetchall():
            (
                eid, formula, mineral_name, space_group,
                a, b, c, alpha, beta, gamma,
                color, year, author, journal, quality,
            ) = row
            cell: CellParams | None = None
            if a is not None:
                cell = CellParams(
                    a=float(a), b=float(b), c=float(c),
                    alpha=float(alpha) if alpha is not None else 90.0,
                    beta=float(beta) if beta is not None else 90.0,
                    gamma=float(gamma) if gamma is not None else 90.0,
                )
            literature: dict[str, object] = {}
            if author is not None:
                literature["author"] = author
            if journal is not None:
                literature["journal"] = journal
            if year is not None:
                literature["year"] = int(year)
            if color is not None:
                literature["color"] = color

            # Fetch the d–I–hkl peak table for this entry.
            peak_cur = conn.execute(
                "SELECT d, intensity, h, k, l FROM peaks "
                "WHERE entry_id = ? ORDER BY intensity DESC",
                (eid,),
            )
            peak_rows = peak_cur.fetchall()
            ds = [float(r[0]) for r in peak_rows]
            ints = [float(r[1]) if r[1] is not None else 0.0 for r in peak_rows]
            hkls: list[tuple[int, int, int] | None] = [
                (r[2], r[3], r[4]) if r[2] is not None else None
                for r in peak_rows
            ]
            hkl_field = hkls if any(h is not None for h in hkls) else None

            out[eid] = Entry(
                entry_id=eid,
                formula=formula or "",
                d_spacings=np.array(ds, dtype=np.float64),
                intensities=np.array(ints, dtype=np.float64),
                mineral_name=mineral_name,
                cell=cell,
                space_group=space_group,
                hkl=hkl_field,
                literature=literature,
                quality=quality or "",
            )

    # Preserve input order; skip ids missing from the DB.
    return [out[eid] for eid in entry_ids if eid in out]


# --------------------------------------------------------------------------- #
# d-spacing helper
# --------------------------------------------------------------------------- #
def _exp_d_values(exp_peaks: list[Peak], wavelength: float) -> list[float]:
    """Return the d-spacings (Å) of the experimental peaks.

    Uses ``peak.d`` when available; otherwise derives it from
    ``peak.two_theta`` via Bragg's law (``d = λ / (2 sin θ)``).  Peaks at
    ``2θ = 0`` (``sin θ = 0``) cannot yield a finite d and are skipped —
    they cannot be matched to any reference peak anyway.
    """
    out: list[float] = []
    for p in exp_peaks:
        if p.d is not None and p.d > 0:
            out.append(float(p.d))
            continue
        if p.two_theta <= 0.0:
            continue
        sin_theta = math.sin(math.radians(p.two_theta / 2.0))
        if sin_theta > 0.0:
            out.append(wavelength / (2.0 * sin_theta))
    return out


# --------------------------------------------------------------------------- #
# Public search-match entry points
# --------------------------------------------------------------------------- #
def search_match(
    exp_peaks: list[Peak],
    conn: sqlite3.Connection,
    wavelength: float,
    *,
    restraints: Restraints | None = None,
    weights: FomWeights | None = None,
    window_deg: float = 0.3,
    top_n: int = 20,
    pre_filter: Callable[[list[Peak], sqlite3.Connection], list[str]] | None = None,
) -> list[CandidateResult]:
    """Run a full peak-based search-match (Phase 6 / T6.4).

    Implements Match!'s *Search → Search-Match* (``Ctrl+M``) command:
    compare the experimental peak list to every candidate reference
    pattern, compute the FoM for each, and return a ranked candidate
    list (Top-N).

    The candidate-generation step uses one of three strategies, in
    order of preference:

    1. ``pre_filter`` callable — fast index-based pruning (Hanawalt /
       Fink, T6.0 — interface reserved, not yet wired up here).
    2. ``restraints`` — SQL filters (elements, crystal system, year,
       ...).  When the user has set restraints in the *Restraints* tab,
       this is the natural path.
    3. ``search_by_d`` — d-value retrieval against the experimental
       d-spacing set.  The default fallback.

    After candidate generation the function fetches the full
    :class:`~xinmatch.core.model.Entry` objects (with their d–I peak
    tables), runs :func:`~xinmatch.core.search.fom.rank_candidates` to
    score and sort, and trims to ``top_n``.

    Parameters
    ----------
    exp_peaks:
        Experimental peaks (must carry ``two_theta`` and ``intensity``;
        ``d`` is used if present, otherwise derived from ``two_theta``
        and *wavelength*).
    conn:
        Open SQLite connection to the reference database.
    wavelength:
        Wavelength in Å (e.g. 1.5406 for Cu Kα).
    restraints:
        Optional :class:`Restraints`; when provided, candidate ids
        come from :func:`~xinmatch.core.search.restraints_apply.apply_restraints`.
    weights:
        Optional :class:`FomWeights` override for the FoM calculation.
    window_deg:
        Full width of the peak-correlation window in degrees 2θ
        (default 0.3° — Match! default).
    top_n:
        Maximum number of ranked candidates to return (default 20).
    pre_filter:
        Optional callable ``(exp_peaks, conn) -> list[str]`` producing
        candidate entry ids.  When given, takes precedence over
        ``restraints`` and the default d-value search.  Reserved for
        the future Hanawalt/Fink index (T6.0).

    Returns
    -------
    list[CandidateResult]
        FoM-ranked candidate results, length ``<= top_n``.
    """
    # Step 1 — candidate generation.
    if pre_filter is not None:
        entry_ids: list[str] = list(pre_filter(exp_peaks, conn))
        logger.debug("pre_filter produced %d candidate ids", len(entry_ids))
    elif restraints is not None:
        entry_ids = apply_restraints(conn, restraints)
        logger.debug("restraints produced %d candidate ids", len(entry_ids))
    else:
        peak_ds = _exp_d_values(exp_peaks, wavelength)
        if not peak_ds:
            # No usable d-spacings → no candidates.
            return []
        ranked_ids = search_by_d(conn, peak_ds)
        entry_ids = [eid for eid, _ in ranked_ids]
        logger.debug("search_by_d produced %d candidate ids", len(entry_ids))

    if not entry_ids:
        return []

    # Step 2 — fetch Entry objects.
    entries = fetch_entries_by_ids(conn, entry_ids)
    logger.debug("fetched %d entries from db", len(entries))

    # Step 3 — rank by FoM.
    ranked = rank_candidates(
        exp_peaks,
        entries,
        wavelength,
        weights=weights,
        window_deg=window_deg,
    )

    # Step 4 — Top-N.
    return select_top_n(ranked, top_n)


def search_marked_peaks(
    exp_peaks: list[Peak],
    conn: sqlite3.Connection,
    wavelength: float,
    marked_indices: list[int],
    **kwargs: object,
) -> list[CandidateResult]:
    """Run search-match restricted to a subset of *marked* peaks (T6.5).

    Implements Match!'s *Search → Search-Match (marked peaks only)*
    command (``Ctrl+Shift+M``): the user marks one or more experimental
    peaks (e.g. peaks not yet explained by the selected phases) and the
    search is rerun using only those peaks.  Match! notes that when
    multiple peaks are marked, the candidate ids are unioned (logical
    OR) because the user cannot yet know whether they belong to the
    same phase.

    This wrapper simply slices the experimental peak list by
    *marked_indices* and forwards to :func:`search_match` with the
    remaining keyword arguments.

    Parameters
    ----------
    exp_peaks:
        Full experimental peak list.
    conn:
        Open SQLite connection.
    wavelength:
        Wavelength in Å.
    marked_indices:
        Indices into *exp_peaks* to restrict the search to.  Out-of-range
        indices raise :class:`IndexError`.  An empty list returns an
        empty candidate list (no peaks to match).
    **kwargs:
        Forwarded to :func:`search_match` (``restraints``, ``weights``,
        ``window_deg``, ``top_n``, ``pre_filter``).

    Returns
    -------
    list[CandidateResult]
        FoM-ranked candidate results for the marked-peak subset.
    """
    if not marked_indices:
        return []
    marked = [exp_peaks[i] for i in marked_indices]  # raises IndexError OOB
    return search_match(marked, conn, wavelength, **kwargs)
