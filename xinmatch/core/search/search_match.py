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
from typing import Any, cast

import numpy as np

from xinmatch.core.db.query_peaks import search_by_d
from xinmatch.core.model import CellParams, Entry, Peak, Restraints
from xinmatch.core.model.element_symbols import element_constraint_sets
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

    # --- Pass 1: scalar metadata, one row per entry ---------------------
    scalars: dict[str, tuple] = {}
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
            scalars[row[0]] = row

    # --- Pass 2: peak tables, ONE query per chunk -----------------------
    # (v1.7.x) This used to be one ``SELECT ... WHERE entry_id = ?`` per
    # entry: 3000 candidates meant 3000 round-trips and ~0.7 s of pure
    # SQLite overhead.  Batching by chunk drops that to ceil(N/500) queries
    # while a linear group-by keeps the per-entry (d, I desc) ordering.
    peaks_by_id: dict[str, list[tuple]] = {}
    for i in range(0, len(ids), chunk_size):
        chunk = ids[i : i + chunk_size]
        placeholders = ",".join("?" for _ in chunk)
        cur = conn.execute(
            f"SELECT entry_id, d, intensity, h, k, l FROM peaks "
            f"WHERE entry_id IN ({placeholders}) "
            f"ORDER BY entry_id, intensity DESC",
            chunk,
        )
        for eid, d, intensity, h, k, ell in cur:
            peaks_by_id.setdefault(eid, []).append((d, intensity, h, k, ell))

    # --- Assemble (only ids present in both tables) --------------------
    out: dict[str, Entry] = {}
    for eid, row in scalars.items():
        (
            _eid, formula, mineral_name, space_group,
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

        peak_rows = peaks_by_id.get(eid, [])
        ds = [float(r[0]) for r in peak_rows]
        ints = [float(r[1]) if r[1] is not None else 0.0 for r in peak_rows]
        hkls: list[tuple[int, int, int] | None] = [
            (r[2], r[3], r[4]) if r[2] is not None else None
            for r in peak_rows
        ]
        # hkl 行缺失时以 None 占位，保持与 d/I 的行对齐；Entry.hkl 只接受
        # 非空 hkl 元组列表，故这里 cast 收窄（None 占位仅出现在 hkl_field
        # 为 truthy 但部分行缺 hkl 的情形，Entry 消费端按位取值可容忍）。
        hkl_field = (
            cast("list[tuple[int, int, int]] | None", hkls)
            if any(h is not None for h in hkls)
            else None
        )

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
    return [out[eid] for eid in ids if eid in out]


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
def _is_v3_reader(db: object) -> bool:
    """True when *db* is a v3 ``.xinDB`` reader instead of a sqlite connection.

    v3.0.0 起默认参考库是列存 ``.xinDB``：它**不是** sqlite3.Connection
    （没有可用的 ``peaks`` 行表），所以检索入口必须按对象类型分流。
    用 isinstance 而不是鸭子类型，避免把"恰好有 fetch_peaks 方法"的
    测试替身误判成 v3。
    """
    from xinmatch.core.db.reader_v3 import XinDBReader

    return isinstance(db, XinDBReader)


def _search_match_v3(
    exp_peaks: list[Peak],
    reader,
    wavelength: float,
    *,
    restraints: Restraints | None = None,
    window_deg: float = 0.3,
    top_n: int = 20,
    recall_min_matches: int = 2,
) -> list[CandidateResult]:
    """v3 分支：委托给 :func:`search_v3.search_match_v3`。

    只搬运 v2 签名里语义对得上的参数，元素部分走
    :func:`~xinmatch.core.model.element_symbols.element_constraint_sets` ——
    四态（必有 / 含有 / 可能 / 没有）+ 闭环一次折算成预筛的三个集合，
    与 SQL 直查、基准脚本共用同一份口径。晶系/年份这类谓词 v3 的预筛矩阵
    不表达，留给调用方在结果上二次过滤（GUI 目前不启用这些谓词）。
    """
    from xinmatch.core.db.search_v3 import search_match_v3

    allowed: set[str] | None = None
    any_of: set[str] | None = None
    excluded: set[str] | None = None
    if restraints is not None:
        required, required_any, banned = element_constraint_sets(restraints)
        allowed = required or None
        any_of = required_any or None
        # 「必须不含」：样品侧元素合理性（XRF/EDS 未检出的元素一律排除），
        # 用来挡 Bi-Y-O 这类化学上不可能的假卡（基准报告 §11.5 的下一步）。
        # 闭环开启时这里已经被补成了「允许池之外的 118-n 个元素」。
        excluded = banned or None

    result = search_match_v3(
        exp_peaks,
        reader,
        wavelength,
        window_deg=window_deg,
        top_n=top_n,
        min_match=max(2, int(recall_min_matches)),
        elements_allowed=allowed,
        elements_any=any_of,
        elements_excluded=excluded,
    )
    return result.candidates


def search_match(
    exp_peaks: list[Peak],
    conn,
    wavelength: float,
    *,
    restraints: Restraints | None = None,
    weights: FomWeights | None = None,
    window_deg: float = 0.3,
    top_n: int = 20,
    pre_filter: Callable[[list[Peak], sqlite3.Connection], list[str]] | None = None,
    recall_top_k: int = 40,
    recall_min_matches: int = 2,
    recall_max_candidates: int = 3000,
    recall_strongest_peak: bool = True,
    recall_strongest_k: int = 5,
) -> list[CandidateResult]:
    """Run a full peak-based search-match (Phase 6 / T6.4).

    Implements the reference software's *Search → Search-Match* (``Ctrl+M``) command:
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
        (default 0.3° — the reference software default).
    top_n:
        Maximum number of ranked candidates to return (default 20).
    pre_filter:
        Optional callable ``(exp_peaks, conn) -> list[str]`` producing
        candidate entry ids.  When given, takes precedence over
        ``restraints`` and the default d-value search.  Reserved for
        the future Hanawalt/Fink index (T6.0).
    recall_top_k:
        Only the *k* strongest experimental peaks (by intensity) are
        used for candidate recall via the d-value search.  The full peak
        set is still used for FoM scoring.  Bounding recall keeps the
        d-value query fast on full COD-scale databases; strong peaks are
        the most discriminating ones (the reference software behaves
        similarly).  Default 40 (T6.0): minor-phase lines with
        intermediate intensity (e.g. CaCO₃ in 2-1, 50% phase whose
        strongest lines sit at intensity ranks 21–40) are recalled
        instead of being cut off at 20.
    recall_min_matches:
        Minimum number of distinct recall peaks an entry must match to
        enter the FoM scoring stage.
    recall_max_candidates:
        Cap on the number of entries sent to FoM scoring (after recall
        ranking by match count).  Bounds the per-candidate correlation
        cost on large databases.  Applied in **all** recall modes
        (including the Hanawalt prefilter — T6.0, previously ignored).
        When ``restraints`` admit more entries than the cap, the restrained
        set is intersected with the d-value recall before capping, so a wide
        restraint can no longer push the whole library into FoM scoring;
        narrow restraints (fewer entries than the cap) are scored unchanged.
        Default 3000 (T6.0): FoM scoring of 3000 candidates costs
        ~0.8 s (fetch ~0.7 s) while the recall query dominates, so the
        cap is relaxed to keep true minor phases past the match-count
        cutoff; the historical 800 cap dropped them.
    recall_strongest_peak:
        Hanawalt-style recall (default ``True``): keep only entries whose
        strongest reference peak falls inside an experimental strong-peak
        window.  On full COD-scale databases this prunes the false
        positives that dominate plain match counting on dense multi-phase
        patterns while keeping the true phases.  Plain match-count recall
        (``False``) saturates on sparse patterns: when the pattern has few
        peaks, hundreds of dense cards match *all* of them, the
        ``recall_max_candidates`` cutoff then truncates the tied
        candidates by ``entry_id`` order, and true phases whose id sorts
        late (e.g. the ``96-900-xxxx`` COD-selected series) are dropped
        before FoM scoring ever sees them.
    recall_strongest_k:
        Hanawalt top-K strength (default 5).  With
        ``recall_strongest_peak=True``, entries whose **any of the K
        strongest reference peaks** falls inside an experimental strong
        peak window are kept (K=1 ⇔ strongest peak only, the historical
        behaviour).  K>1 relaxes the strongest-line rule for multi-phase
        patterns where a minor phase's strongest line is masked by the
        major phase while its 2nd–Kth lines are still observed (T6.0).
        Measured on the COD 71k database: CaCO₃ in 2-1 and Al₂O₃ in
        3-1/4-1 were recalled 0 times at K=1; K=5 recalls them (Al₂O₃
        cards at candidate rank 14/15/52, match 5–6).  Ignored when
        ``recall_strongest_peak=False``.

    Returns
    -------
    list[CandidateResult]
        FoM-ranked candidate results, length ``<= top_n``.
    """
    # v3.0.0：列存 .xinDB 走专门的检索管线（向量化预筛 + 峰批量解码）。
    # 放在最前面而不是在各个分支里判断，是因为 v3 根本没有 peaks 行表，
    # 下面任何一条 SQL 路径都不可能对它工作。
    if _is_v3_reader(conn):
        return _search_match_v3(
            exp_peaks,
            conn,
            wavelength,
            restraints=restraints,
            window_deg=window_deg,
            top_n=top_n,
            recall_min_matches=recall_min_matches,
        )

    # Step 1 — candidate generation.
    def _d_recall(restrict_to: set[str] | None = None) -> list[str]:
        """d-value recall on the strongest experimental peaks.

        Candidate recall uses the strongest experimental peaks only — fast on
        full COD-scale databases, and the most discriminating peaks drive the
        window query.  FoM scoring below still uses the complete experimental
        peak set.  ``restrict_to`` keeps only entries already vetted by the
        restraints (used when those admit more entries than we are willing to
        score).
        """
        strong_peaks = sorted(
            exp_peaks, key=lambda p: (p.intensity if p.intensity is not None else 0.0),
            reverse=True,
        )[:recall_top_k]
        peak_ds = _exp_d_values(strong_peaks, wavelength)
        if not peak_ds:
            return []
        effective_k = recall_strongest_k if recall_strongest_peak else 0
        ranked_ids = search_by_d(
            conn,
            peak_ds,
            wavelength=wavelength,
            window_deg=window_deg,
            min_matches=min(recall_min_matches, len(peak_ds))
            if not recall_strongest_peak
            else 1,
            # No cap here: restrictions are applied first so the cap never
            # discards restrained candidates in favour of unrestricted ones.
            max_candidates=None,
            strongest_k=effective_k,
        )
        ids = [eid for eid, _ in ranked_ids]
        if restrict_to is not None:
            ids = [eid for eid in ids if eid in restrict_to]
        return ids

    if pre_filter is not None:
        entry_ids: list[str] = list(pre_filter(exp_peaks, conn))
        logger.debug("pre_filter produced %d candidate ids", len(entry_ids))
    elif restraints is not None:
        restrained = apply_restraints(conn, restraints)
        logger.debug("restraints produced %d candidate ids", len(restrained))
        if len(restrained) <= recall_max_candidates:
            # Small enough to score as-is: keeps narrow restraints exact.
            entry_ids = restrained
        else:
            # Wide restraints (e.g. "must contain O" on the 113k COD library)
            # would otherwise send every entry through FoM scoring.  Intersect
            # with the d-value recall so the cap keeps the best-scoring ones.
            entry_ids = _d_recall(set(restrained))
            logger.debug(
                "restraints ∩ d-recall produced %d candidate ids", len(entry_ids)
            )
    else:
        entry_ids = _d_recall()
        logger.debug("search_by_d produced %d candidate ids", len(entry_ids))

    # Hard cap in every mode (docstring contract): bounds fetch + FoM cost.
    if recall_max_candidates is not None and len(entry_ids) > recall_max_candidates:
        logger.debug(
            "capping %d candidates to recall_max_candidates=%d",
            len(entry_ids), recall_max_candidates,
        )
        entry_ids = entry_ids[:recall_max_candidates]

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
    **kwargs: Any,
) -> list[CandidateResult]:
    """Run search-match restricted to a subset of *marked* peaks (T6.5).

    Implements the reference software's *Search → Search-Match (marked peaks only)*
    command (``Ctrl+Shift+M``): the user marks one or more experimental
    peaks (e.g. peaks not yet explained by the selected phases) and the
    search is rerun using only those peaks.  the reference software notes that when
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
