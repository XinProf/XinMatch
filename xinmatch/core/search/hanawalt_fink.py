"""Hanawalt & Fink coarse pre-filter for search-match (Phase 6 / T6.0).

Before running the expensive full FoM calculation over the whole reference
database (typically 500k entries), we prune the candidate set down to a
few thousand entries using the classic **Hanawalt** (three strongest
lines) and **Fink** (eight strongest lines) search methods.

Both methods are *index based*: a hash key is derived from the strongest
*d*-spacings of each reference entry and stored in an inverted index.
At query time the experimental pattern's strongest lines are quantised
the same way and matched against the index (with adjacent-bin neighbours
to absorb small *d*-spacing errors).

Match! feature: the "pre-filter" step that runs before the full FoM
calculation.  Match! itself uses element restraints and d-value search
by default; the Hanawalt/Fink indexes are the textbook ICDD PDF search
methods (Hanawalt 1938, Fink 1970) implemented here as a fast first-pass
pruner suitable for 500k-entry databases.

Algorithm sources:
* J. D. Hanawalt, "Chemical Analysis by X-Ray Diffraction",
  Ind. Eng. Chem. Anal. Ed. 10, 462 (1938).
* W. F. Fink, "A Method of X-Ray Diffraction Analysis Using Eight
  Selected Lines", Anal. Chem. 42, 1559 (1970).
"""

from __future__ import annotations

import math
from itertools import combinations, product

import numpy as np

from xinmatch.core.model import Entry, Peak

__all__ = [
    "hanawalt_index",
    "fink_index",
    "make_hanawalt_key",
    "build_hanawalt_lookup",
    "pre_filter_hanawalt",
    "pre_filter_fink",
    "pre_filter",
]


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #
def _quantize(d: float, tolerance: float) -> str:
    """Quantise a *d*-spacing into a bin string.

    The bin index is ``round(d / tolerance)``; two *d*-values in the same
    (or an adjacent) bin are treated as matching.  The default
    ``tolerance = 0.03 Å`` gives roughly 0.03 Å resolution, the classic
    Hanawalt grouping width.
    """
    return str(int(round(d / tolerance)))


def _peak_d(p: Peak, wavelength: float) -> float | None:
    """Return the *d*-spacing of a peak, deriving it from 2θ if needed."""
    if p.d is not None and p.d > 0:
        return float(p.d)
    if p.two_theta <= 0.0:
        return None
    sin_theta = math.sin(math.radians(p.two_theta / 2.0))
    if sin_theta <= 0.0:
        return None
    return wavelength / (2.0 * sin_theta)


def _exp_d_sorted(exp_peaks: list[Peak], wavelength: float, n: int) -> list[float]:
    """Return the *n* strongest experimental *d*-spacings (intensity desc)."""
    ds: list[float] = []
    for p in sorted(exp_peaks, key=lambda pk: pk.intensity, reverse=True):
        d = _peak_d(p, wavelength)
        if d is not None and d > 0:
            ds.append(d)
        if len(ds) >= n:
            break
    return ds


# --------------------------------------------------------------------------- #
# Index extractors
# --------------------------------------------------------------------------- #
def hanawalt_index(entry: Entry) -> tuple[float, float, float]:
    """Return the three strongest *d*-spacings of *entry*.

    Implements the **Hanawalt three-strongest-lines** index: the *d*
    values of the three most intense reflections, in descending
    intensity order.  If the entry has fewer than three peaks the
    missing positions are padded with ``0.0``.

    Match! feature: corresponds to the "three strongest lines" used by
    the Hanawalt manual search method.

    Parameters
    ----------
    entry:
        Reference database entry.

    Returns
    -------
    tuple[float, float, float]
        Top-3 *d*-spacings (Å) sorted by descending intensity.
    """
    if entry.n_peaks == 0:
        return (0.0, 0.0, 0.0)
    idx = np.argsort(entry.intensities)[::-1][:3]
    top = [float(entry.d_spacings[i]) for i in idx]
    while len(top) < 3:
        top.append(0.0)
    return (top[0], top[1], top[2])


def fink_index(entry: Entry) -> tuple[float, ...]:
    """Return the Fink index of *entry*: up to eight strongest *d* values.

    The **Fink method** takes the eight most intense reflections and
    sorts them by *descending d-spacing* (rather than intensity).  This
    makes the index less sensitive to intensity errors (e.g. from
    preferred orientation) than the Hanawalt index.

    Match! feature: corresponds to the Fink "eight selected lines"
    search method.

    Parameters
    ----------
    entry:
        Reference database entry.

    Returns
    -------
    tuple[float, ...]
        Up to 8 *d*-spacings (Å), sorted by descending *d*.  Padded to
        length 8 with ``0.0`` if the entry has fewer than eight peaks.
    """
    if entry.n_peaks == 0:
        return (0.0,) * 8
    n = min(8, entry.n_peaks)
    idx = np.argsort(entry.intensities)[::-1][:n]
    ds = sorted((float(entry.d_spacings[i]) for i in idx), reverse=True)
    while len(ds) < 8:
        ds.append(0.0)
    return tuple(ds)


# --------------------------------------------------------------------------- #
# Key construction
# --------------------------------------------------------------------------- #
def make_hanawalt_key(
    entry: Entry,
    *,
    tolerance: float = 0.03,
) -> tuple[str, ...]:
    """Build the canonical Hanawalt hash-key tuple for *entry*.

    The key is the quantised bin strings of the three strongest
    *d*-spacings (in intensity order).  Adjacent-bin lookups are
    performed by the caller.

    Match! feature: key format mirrors the ICDD Hanawalt index grouping.

    Parameters
    ----------
    entry:
        Reference database entry.
    tolerance:
        Bin width in Å (default 0.03).

    Returns
    -------
    tuple[str, ...]
        Three bin strings.
    """
    return tuple(_quantize(d, tolerance) for d in hanawalt_index(entry))


# --------------------------------------------------------------------------- #
# Inverted-index builders
# --------------------------------------------------------------------------- #
def build_hanawalt_lookup(
    entries: list[Entry],
    *,
    tolerance: float = 0.03,
    n_pool: int = 5,
) -> dict[str, list[str]]:
    """Build a Hanawalt inverted index.

    For each entry the ``n_pool`` strongest lines are considered and all
    :math:`\\binom{n_{\\text{pool}}}{3}` 3-line combinations are used as
    keys.  Indexing under multiple combinations (instead of only the
    strict top-3) makes the index robust to intensity reordering caused
    by preferred orientation, so the true phase is still found.

    Match! feature: Hanawalt index lookup phase of the coarse
    pre-filter (T6.0).

    Parameters
    ----------
    entries:
        Reference database entries to index.
    tolerance:
        Bin width in Å.
    n_pool:
        Number of strongest lines to draw 3-line combinations from
        (default 5 → 10 keys per entry).

    Returns
    -------
    dict[str, list[str]]
        Mapping ``"bin1_bin2_bin3"`` → ``[entry_id, ...]``.
    """
    lookup: dict[str, list[str]] = {}
    k = 3
    for entry in entries:
        if entry.n_peaks == 0:
            continue
        n = min(n_pool, entry.n_peaks)
        idx = np.argsort(entry.intensities)[::-1][:n]
        ds = entry.d_spacings[idx]
        # combinations() yields ascending index tuples; since ``idx`` is
        # sorted by intensity descending, each combo is already in
        # intensity-descending order — the canonical Hanawalt order.
        for combo in combinations(range(n), k):
            bins = [_quantize(float(ds[i]), tolerance) for i in combo]
            key = "_".join(bins)
            lookup.setdefault(key, []).append(entry.entry_id)
    return lookup


def build_fink_lookup(
    entries: list[Entry],
    *,
    tolerance: float = 0.03,
    n_lines: int = 8,
) -> dict[str, list[str]]:
    """Build a Fink-style per-bin inverted index.

    Each entry is indexed under the bin of each of its ``n_lines``
    strongest *d*-values.  Counting how many of the unknown's strong
    lines fall into the same bins as an entry gives a robust match
    score without the combinatorial explosion of 8-line keys.

    Match! feature: Fink eight-line index lookup phase of the coarse
    pre-filter (T6.0).

    Parameters
    ----------
    entries:
        Reference database entries.
    tolerance:
        Bin width in Å.
    n_lines:
        Number of strongest lines to index per entry (default 8).

    Returns
    -------
    dict[str, list[str]]
        Mapping ``bin`` → ``[entry_id, ...]``.
    """
    lookup: dict[str, list[str]] = {}
    for entry in entries:
        if entry.n_peaks == 0:
            continue
        n = min(n_lines, entry.n_peaks)
        idx = np.argsort(entry.intensities)[::-1][:n]
        seen: set[str] = set()
        for i in idx:
            b = _quantize(float(entry.d_spacings[i]), tolerance)
            if b in seen:
                continue
            seen.add(b)
            lookup.setdefault(b, []).append(entry.entry_id)
    return lookup


# --------------------------------------------------------------------------- #
# Pre-filter queries
# --------------------------------------------------------------------------- #
def pre_filter_hanawalt(
    exp_peaks: list[Peak],
    entries: list[Entry],
    *,
    wavelength: float,
    top_k: int = 2000,
    tolerance: float = 0.03,
    n_pool: int = 5,
) -> list[str]:
    """Coarse pre-filter using the Hanawalt three-strongest-lines index.

    Builds the Hanawalt inverted index from *entries*, then queries it
    with the experimental pattern's strong lines (all 3-line
    combinations of the ``n_pool`` strongest, plus ±1-bin neighbours)
    and returns the ``top_k`` entry ids ranked by hit count.

    Match! feature: Hanawalt coarse pre-filter (T6.0).

    Parameters
    ----------
    exp_peaks:
        Experimental peaks.
    entries:
        Reference database entries.
    wavelength:
        Wavelength in Å (used to derive *d* from 2θ when ``peak.d`` is
        not set).
    top_k:
        Maximum number of candidate ids to return.
    tolerance:
        Bin width in Å.
    n_pool:
        Number of strongest experimental lines to draw 3-line combos
        from.

    Returns
    -------
    list[str]
        Candidate ``entry_id``s, most-hit first.  Empty if the
        experimental peaks carry no usable *d*-spacings.
    """
    exp_ds = _exp_d_sorted(exp_peaks, wavelength, n_pool)
    if len(exp_ds) < 3:
        return []
    lookup = build_hanawalt_lookup(entries, tolerance=tolerance, n_pool=n_pool)
    counts: dict[str, int] = {}
    for combo in combinations(range(len(exp_ds)), 3):
        combo_ds = [exp_ds[i] for i in combo]
        bins = [_quantize(d, tolerance) for d in combo_ds]
        for offsets in product((-1, 0, 1), repeat=3):
            nb = [str(int(b) + o) for b, o in zip(bins, offsets, strict=True)]
            key = "_".join(nb)
            for eid in lookup.get(key, ()):
                counts[eid] = counts.get(eid, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [eid for eid, _ in ranked[:top_k]]


def pre_filter_fink(
    exp_peaks: list[Peak],
    entries: list[Entry],
    *,
    wavelength: float,
    top_k: int = 2000,
    tolerance: float = 0.03,
    n_lines: int = 8,
) -> list[str]:
    """Coarse pre-filter using the Fink eight-strongest-lines index.

    Builds a per-bin Fink index from *entries*, queries it with the
    experimental pattern's strongest lines (each line ±1 bin), counts
    shared bins per entry, and returns the ``top_k`` entry ids.

    Match! feature: Fink coarse pre-filter (T6.0).

    Parameters
    ----------
    exp_peaks:
        Experimental peaks.
    entries:
        Reference database entries.
    wavelength:
        Wavelength in Å.
    top_k:
        Maximum number of candidate ids.
    tolerance:
        Bin width in Å.
    n_lines:
        Number of strongest experimental lines to use.

    Returns
    -------
    list[str]
        Candidate ``entry_id``s, most-shared-bins first.
    """
    exp_ds = _exp_d_sorted(exp_peaks, wavelength, n_lines)
    if not exp_ds:
        return []
    lookup = build_fink_lookup(entries, tolerance=tolerance, n_lines=n_lines)
    counts: dict[str, int] = {}
    for d in exp_ds:
        b = int(_quantize(d, tolerance))
        for off in (-1, 0, 1):
            for eid in lookup.get(str(b + off), ()):
                counts[eid] = counts.get(eid, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [eid for eid, _ in ranked[:top_k]]


def pre_filter(
    exp_peaks: list[Peak],
    entries: list[Entry],
    *,
    method: str = "both",
    **kwargs: object,
) -> list[str]:
    """Unified coarse pre-filter entry point.

    Dispatches to :func:`pre_filter_hanawalt`, :func:`pre_filter_fink`,
    or both (union of candidate id sets).

    Match! feature: coarse pre-filter before full FoM (T6.0).

    Parameters
    ----------
    exp_peaks:
        Experimental peaks.
    entries:
        Reference database entries.
    method:
        ``"hanawalt"``, ``"fink"``, or ``"both"`` (default).
    **kwargs:
        Forwarded to the selected filter(s) (``wavelength``,
        ``top_k``, ``tolerance``, ...).

    Returns
    -------
    list[str]
        Candidate ``entry_id``s.

    Raises
    ------
    ValueError
        If *method* is not one of ``hanawalt``, ``fink``, ``both``.
    """
    if method == "hanawalt":
        return pre_filter_hanawalt(exp_peaks, entries, **kwargs)  # type: ignore[arg-type]
    if method == "fink":
        return pre_filter_fink(exp_peaks, entries, **kwargs)  # type: ignore[arg-type]
    if method == "both":
        h = set(pre_filter_hanawalt(exp_peaks, entries, **kwargs))  # type: ignore[arg-type]
        f = set(pre_filter_fink(exp_peaks, entries, **kwargs))  # type: ignore[arg-type]
        return list(h | f)
    raise ValueError(f"unknown pre_filter method: {method!r}")
