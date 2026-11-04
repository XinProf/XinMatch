"""v3 (``.xinDB``) search-match integration (M3 / S3.3).

Why a separate entry point
---------------------------
The v2 engine (:func:`~xinmatch.core.search.search_match.search_match`) works
on a ``sqlite3.Connection`` whose schema it knows: it recalls candidates by
querying the ``peaks`` table and then re-reads them through
:func:`~xinmatch.core.search.search_match.fetch_entries_by_ids`.

A v3 database stores the same information in a different physical shape
(columnar blocks, CSR offsets, a prescreen matrix).  Rewriting the v2 engine
to understand both layouts would put the scoring path at risk — and the
scoring path is the one thing that must not change.

So the split is:

``xinmatch.core.search``
    untouched.  It still owns candidate scoring and ranking.
``this module``
    owns the v3 *data access*: prescreen → decode → hand plain
    :class:`~xinmatch.core.model.entry.Entry` objects to the v2 scorer.

The v2 scorer only needs ``(exp_peaks, entries, wavelength)`` — it never
sees the database.  That is the seam that keeps the accuracy guarantee:
**the ranking code is the same code, fed with the same numbers.**

Usage
-----
::

    from xinmatch.core.db.reader_v3 import XinDBReader
    from xinmatch.core.db.search_v3 import search_match_v3

    with XinDBReader("D:/XRD-DB/COD-Inorg.xinDB") as reader:
        results = search_match_v3(peaks, reader, wavelength=1.5406)
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass

import numpy as np

from xinmatch.core.model.entry import CellParams, Entry
from xinmatch.core.model.peak import Peak
from xinmatch.core.search.fom import CandidateResult, rank_candidates

from .reader_v3 import DEFAULT_RANK_LIMIT, XinDBReader

logger = logging.getLogger(__name__)

#: Default number of candidates handed to the scoring stage.  Single source of
#: truth is :data:`xinmatch.core.db.reader_v3.DEFAULT_RANK_LIMIT` (the prescreen
#: cap); keeping a second literal here silently let the two drift apart.
DEFAULT_CANDIDATE_LIMIT = DEFAULT_RANK_LIMIT

#: Number of strongest experimental peaks used for the prescreen.  Mirrors
#: the v2 recall stage (``recall_top_k=40``): the strongest measured lines
#: are the most discriminating ones.
PRESCREEN_TOP_K = 40

#: Correlation window (degrees 2θ) used by the scorer — the project default.
DEFAULT_WINDOW_DEG = 0.3


@dataclass
class SearchV3Result:
    """Outcome of a v3 search-match.

    Attributes
    ----------
    candidates:
        Ranked results, best first (same type the v2 engine returns).
    seconds:
        Wall time of the whole search.
    n_prescreened:
        Number of phases that survived the prescreen.
    truncated:
        ``True`` when the candidate cap was reached — the caller may want to
        widen it to be sure no true phase was dropped.
    """

    candidates: list[CandidateResult]
    seconds: float
    n_prescreened: int
    truncated: bool


def _exp_d_intensity_pairs(
    exp_peaks: list[Peak], wavelength: float
) -> list[tuple[float, float]]:
    """Return ``(d, intensity)`` pairs, skipping peaks that yield no finite d.

    Peaks that carry an explicit ``d`` use it; the rest are converted from
    2θ with Bragg's law ``d = λ / (2 sin θ)``.  Skipping is why the pair list
    has to be built in one pass: taking the first *N* intensities separately
    from the first *N* d-spacings silently mispairs them as soon as one peak
    is skipped (the surviving weights would decorate the wrong measurement
    windows).
    """
    pairs: list[tuple[float, float]] = []
    for peak in exp_peaks:
        d: float | None = None
        if peak.d is not None and peak.d > 0:
            d = float(peak.d)
        else:
            try:
                sin_theta = math.sin(math.radians(peak.two_theta) / 2.0)
            except ValueError:
                d = None
            else:
                if sin_theta > 0.0:
                    d = wavelength / (2.0 * sin_theta)
        if d is None:
            continue
        pairs.append((d, float(peak.intensity or 0.0)))
    return pairs


def _exp_d_values(exp_peaks: list[Peak], wavelength: float) -> list[float]:
    """Extract the d-spacings of *exp_peaks*.

    Peaks that carry an explicit ``d`` use it; the rest are converted from
    2θ with Bragg's law ``d = λ / (2 sin θ)``.  Mirrors
    :func:`~xinmatch.core.search.search_match._exp_d_values` exactly — the
    conversion used to carry a spurious ``1.0 / d`` here, which fed the
    prescreen reciprocal spacings and made every real search miss.
    """
    return [d for d, _intensity in _exp_d_intensity_pairs(exp_peaks, wavelength)]


def _entry_from_meta(meta: dict) -> Entry:
    """Build an :class:`Entry` from a reader meta dict."""
    a = float(meta.get("cell_a") or 0.0)
    cell = None
    if a > 0:
        cell = CellParams(
            a=a,
            b=float(meta.get("cell_b") or a),
            c=float(meta.get("cell_c") or a),
            alpha=float(meta.get("cell_alpha") or 90.0),
            beta=float(meta.get("cell_beta") or 90.0),
            gamma=float(meta.get("cell_gamma") or 90.0),
        )
    elements = frozenset(meta.get("elements_list") or ())
    return Entry(
        entry_id=str(meta["entry_id"]),
        formula=str(meta.get("formula") or ""),
        d_spacings=np.asarray(meta["peaks_d_list"], dtype=np.float64),
        intensities=np.asarray(meta["peaks_i_list"], dtype=np.float64),
        mineral_name=meta.get("mineral_name") or None,
        cell=cell,
        space_group=meta.get("space_group") or None,
        hkl=None,
        literature={},
        quality="",
        elements=elements,
    )


def search_match_v3(
    exp_peaks: list[Peak],
    reader: XinDBReader,
    wavelength: float,
    *,
    candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
    window_deg: float = DEFAULT_WINDOW_DEG,
    min_match: int = 2,
    top_n: int = 20,
    tolerance: float = 0.02,
    tolerance_rel: float = 0.0,
    elements_allowed: set[str] | None = None,
) -> SearchV3Result:
    """Run a peak-based search-match against a v3 ``.xinDB`` library.

    The candidate generation differs from v2 (a vectorised prescreen on the
    strong-peak matrix instead of SQL window queries), but the **scoring and
    ranking are the v2 code path** — :func:`rank_candidates` — fed with the
    complete reflection lists decoded from the CSR arrays.  A phase that
    survives the prescreen therefore receives exactly the score the v2
    engine would give it.

    Args:
        exp_peaks: Experimental peaks (2θ + intensity).
        reader: An open :class:`~xinmatch.core.db.reader_v3.XinDBReader`.
        wavelength: X-ray wavelength (Å).
        candidate_limit: Maximum number of phases scored.
        window_deg: Correlation window (degrees 2θ).
        min_match: Minimum number of measurement windows a phase must hit.
        top_n: Number of ranked results to return.
        tolerance: Absolute d-window half-width for the prescreen (Å).
        tolerance_rel: Relative d-window component.
        elements_allowed: Optional element pool restriction.

    Returns:
        A :class:`SearchV3Result`.
    """
    t0 = time.perf_counter()
    if not exp_peaks:
        return SearchV3Result(
            candidates=[], seconds=0.0, n_prescreened=0, truncated=False
        )

    # ── Step 1: prescreen (v3-specific) ────────────────────
    strong = sorted(
        exp_peaks,
        key=lambda p: (p.intensity if p.intensity is not None else 0.0),
        reverse=True,
    )[:PRESCREEN_TOP_K]
    pairs = _exp_d_intensity_pairs(strong, wavelength)
    if not pairs:
        return SearchV3Result(
            candidates=[], seconds=time.perf_counter() - t0,
            n_prescreened=0, truncated=False,
        )
    peak_ds = [d for d, _intensity in pairs]
    strong_i = [intensity for _d, intensity in pairs]

    screen = reader.prescreen(
        peak_ds,
        strong_i,
        tolerance=tolerance,
        tolerance_rel=tolerance_rel,
        min_match=min_match,
        rank_limit=candidate_limit,
        elements_allowed=elements_allowed,
    )
    if not screen.candidate_ids:
        return SearchV3Result(
            candidates=[], seconds=time.perf_counter() - t0,
            n_prescreened=0, truncated=screen.truncated,
        )

    # ── Step 2: decode full reflections (v3-specific) ─────
    # The reflections are fetched in **one batched pass**: a single scan
    # over the peak chunks serves every candidate, instead of one chunk
    # lookup per phase.  The scalars come from ``fetch_meta``, which does
    # not touch the peak data at all.
    peaks_map = reader.fetch_peaks(screen.candidate_ids)
    entries: list[Entry] = []
    for entry_id in screen.candidate_ids:
        meta = reader.fetch_meta(entry_id)
        if meta is None:
            continue
        batch = peaks_map.get(entry_id)
        if batch is None or not batch[0]:
            continue
        meta["peaks_d_list"] = batch[0]
        meta["peaks_i_list"] = batch[1]
        entries.append(_entry_from_meta(meta))

    # ── Step 3: rank with the untouched v2 scorer ──────────
    ranked = rank_candidates(
        exp_peaks,
        entries,
        wavelength,
        window_deg=window_deg,
    )

    return SearchV3Result(
        candidates=ranked[:top_n],
        seconds=time.perf_counter() - t0,
        n_prescreened=len(screen.candidate_ids),
        truncated=screen.truncated,
    )


__all__ = [
    "DEFAULT_CANDIDATE_LIMIT",
    "PRESCREEN_TOP_K",
    "SearchV3Result",
    "search_match_v3",
]
