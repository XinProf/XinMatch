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
import os
import sqlite3
import threading
from collections import Counter, OrderedDict

logger = logging.getLogger(__name__)

# Module-level cache of each entry's top-K intensities (descending), used
# by the Hanawalt top-K prefilter to avoid a correlated subquery per
# window row.  Built lazily from the (entry_id, intensity) index.
#
# Cache key = (file path, mtime_ns, size):
# * in-memory databases have no path → never cached (their connection-id
#   would be reused across pytest fixtures, corrupting the table);
# * the (mtime, size) fingerprint invalidates the entry when the library file
#   is rebuilt / replaced at the same path — the previous path-only key
#   silently kept serving stale top-K thresholds;
# * an LRU bound keeps at most ``_TOP_K_CACHE_MAX`` databases resident
#   (each is roughly ``n_entries × 20`` floats);
# * reads/writes are guarded by a lock: the GUI searches from a worker thread
#   while a CLI batch may run concurrently in the same process.
_TOP_K_LIMIT = 20
_TOP_K_CACHE_MAX = 2

#: Upper bound used for an unbounded (window crossing 2θ = 0) d interval.
#: A finite sentinel keeps the bound parameters REAL and the query plan stable;
#: no real d-spacing comes anywhere near 10⁶ Å.
_D_WINDOW_MAX = 1.0e6

_top_k_cache: OrderedDict[
    tuple[str, int, int], dict[str, list[float]]
] = OrderedDict()
_top_k_lock = threading.Lock()


def _top_k_cache_key(conn: sqlite3.Connection) -> tuple[str, int, int] | None:
    """Return a change-detecting cache key for *conn*'s main database.

    ``None`` for in-memory / temporary databases (never cached).
    """
    row = conn.execute("PRAGMA database_list").fetchone()
    path = row[2] if row and row[2] else None
    if not path:
        return None
    try:
        st = os.stat(path)
    except OSError:
        # Path vanished between open and now: fall back to a non-fingerprinted
        # key so the caller still gets a usable (if uncacheable) result.
        return (path, 0, 0)
    return (path, st.st_mtime_ns, st.st_size)


def _load_top_k_intensities(conn: sqlite3.Connection) -> dict[str, list[float]]:
    """Return ``{entry_id: [top-20 intensities, descending]}`` (cached).

    Streams the full peaks table ordered by (entry_id, intensity DESC) and
    keeps only the top ``_TOP_K_LIMIT`` intensities per entry.  ~600 MB COD
    databases (2 M rows) take ~2 s, the 7.9 M-row PolyXRD PDF-2 conversion
    ~5 s on first use in a process; the result is cached per database file
    (path + mtime + size, LRU-bounded), so a GUI session pays it once per
    library.  In-memory connections are rebuilt on every call.

    A dedicated ``(entry_id, intensity DESC)`` index makes this an index-only
    scan (~30 % faster) but costs ~190 MB on the 163 k-entry PDF-2 sidecar, so
    the schema deliberately does **not** carry one: the cached dict makes the
    sort a once-per-process cost instead.
    """
    db_key = _top_k_cache_key(conn)
    if db_key is not None:
        with _top_k_lock:
            cached = _top_k_cache.get(db_key)
            if cached is not None:
                _top_k_cache.move_to_end(db_key)
                return cached

    cache: dict[str, list[float]] = {}
    cur = conn.execute(
        "SELECT entry_id, intensity FROM peaks "
        "ORDER BY entry_id, intensity DESC"
    )
    cur_eid: str | None = None
    cur_list: list[float] = []
    for eid, intensity in cur:
        if eid != cur_eid:
            if cur_eid is not None:
                cache[cur_eid] = cur_list
            cur_eid = eid
            cur_list = []
        if len(cur_list) < _TOP_K_LIMIT:
            cur_list.append(float(intensity))
    if cur_eid is not None:
        cache[cur_eid] = cur_list

    if db_key is not None:
        with _top_k_lock:
            _top_k_cache[db_key] = cache
            _top_k_cache.move_to_end(db_key)
            while len(_top_k_cache) > _TOP_K_CACHE_MAX:
                evicted, _ = _top_k_cache.popitem(last=False)
                logger.debug("evicted top-K cache for %s", evicted[0])
    return cache


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
    strongest_k: int = 0,
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

    Hanawalt-style prefiltering (``strongest_k``):

    * ``strongest_k=0`` (default): no Hanawalt constraint.
    * ``strongest_k=1``: only entries whose **strongest** reference peak
      (maximum intensity) falls inside an experimental window are kept
      (identical semantics to the legacy ``strongest_peak_only=True``).
    * ``strongest_k=K>1``: only entries with **any of their K strongest
      reference peaks** inside an experimental window are kept.  This
      relaxes the pure strongest-peak rule for the common multi-phase
      case where a minor phase's *strongest* line is masked by the
      major phase's pattern while its 2nd–Kth strongest lines are
      still observed.

    The score remains the number of matched experimental peaks.

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
        Legacy Hanawalt switch (default ``False``): when ``True``, treated
        as ``strongest_k=1`` unless *strongest_k* is already set.  Kept for
        API compatibility.
    strongest_k:
        Number of strongest reference peaks eligible for the Hanawalt
        window test (0 = disabled, 1 = strongest peak only, K = any of
        the top-K).  When ``strongest_peak_only=True`` and
        ``strongest_k==0``, this defaults to 1.

    Returns
    -------
    list[tuple[str, float]]
        ``(entry_id, matched_peak_count)`` tuples ordered by descending
        match count.  Only entries with at least one match are returned.
    """
    if not peak_ds:
        return []

    if strongest_k == 0 and strongest_peak_only:
        strongest_k = 1

    if strongest_k > 0:
        # The top-K correlated subquery is served by the
        # (entry_id, intensity) index.  Create it idempotently; on a
        # read-only connection (e.g. a mounted DB opened with mode=ro)
        # the CREATE fails and the query simply runs slower — still
        # correct.  DDL auto-commits in sqlite3, so no explicit commit
        # is issued here (avoids clobbering an outer transaction).
        try:
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_peaks_entry_intensity "
                "ON peaks(entry_id, intensity DESC)"
            )
        except sqlite3.Error:
            # Read-only / locked DB: proceed without the index.
            logger.debug("could not create idx_peaks_entry_intensity "
                         "(read-only connection?); top-K recall runs unindexed")

    def _window(d: float) -> tuple[float, float] | None:
        """Return the d interval covered by the 2θ window, or ``None``.

        ``None`` means the experimental peak cannot be matched by any
        reflection at the assumed wavelength: ``d <= λ/2`` is unphysical
        (sin θ > 1), so ``asin`` would raise ``ValueError``.  This happens in
        practice when a pattern is imported without wavelength metadata (the
        Cu Kα default) but was measured with a Mo / Ag tube, leaving
        high-angle peaks with d well below λ_Cu/2 ≈ 0.77 Å.
        """
        if wavelength is None:
            return d - tolerance, d + tolerance
        if d <= 0.0:
            return None
        # Constant 2θ half-window → d window.  2θ = 2·asin(λ/(2d)).
        arg = wavelength / (2.0 * d)
        if arg >= 1.0:
            return None
        theta = math.asin(arg)
        half_rad = math.radians(window_deg / 2.0)
        # Lower d ← upper 2θ; clamped at the back-scattering limit (λ/2).
        d_lo = wavelength / (2.0 * math.sin(min(theta + half_rad, math.pi / 2.0)))
        sin_lo = math.sin(theta - half_rad)
        # Upper d ← lower 2θ; unbounded when the window crosses 2θ = 0.
        d_hi = _D_WINDOW_MAX if sin_lo <= 0.0 else wavelength / (2.0 * sin_lo)
        return d_lo, d_hi

    scores: Counter[str] = Counter()
    skipped = 0
    if strongest_k:
        # Top-K Hanawalt: keep entries with any of their K strongest
        # reference peaks inside an experimental window.  Equivalence:
        # "some window row has intensity >= the entry's K-th strongest"
        # <=> "window MAX(intensity) >= the entry's K-th strongest".
        # The per-entry thresholds come from the cached top-K table
        # (loaded from the (entry_id, intensity) index), so the window
        # query needs no correlated subquery.
        thresholds = _load_top_k_intensities(conn)
        for d in peak_ds:
            window = _window(d)
            if window is None:
                skipped += 1
                continue
            lo, hi = window
            cur = conn.execute(
                "SELECT entry_id, MAX(intensity) FROM peaks "
                "WHERE d BETWEEN ? AND ? GROUP BY entry_id",
                (lo, hi),
            )
            for entry_id, maxi in cur:
                top = thresholds.get(entry_id)
                if top:
                    # K may exceed the entry's peak count: compare against
                    # the weakest stored peak (any-peak recall) then.
                    k_eff = min(strongest_k, len(top))
                    if maxi >= top[k_eff - 1]:
                        scores[entry_id] += 1
    else:
        for d in peak_ds:
            window = _window(d)
            if window is None:
                skipped += 1
                continue
            lo, hi = window
            cur = conn.execute(
                "SELECT DISTINCT entry_id FROM peaks WHERE d BETWEEN ? AND ?",
                (lo, hi),
            )
            for (entry_id,) in cur:
                scores[entry_id] += 1
    if skipped:
        logger.debug(
            "skipped %d of %d experimental d-spacings below the λ/2 limit "
            "(wavelength=%.4f Å) — check the pattern's wavelength metadata",
            skipped, len(peak_ds), wavelength or 0.0,
        )

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
