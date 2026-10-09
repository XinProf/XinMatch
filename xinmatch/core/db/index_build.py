"""Build inverted indexes for fast reference-database search (Phase 5 / T5.3).

Two acceleration structures are built from the base tables:

* ``element_combo`` — maps a hash of an entry's *exact* element set to the
  list of entry ids sharing that set.  Speeds up "contains exactly these
  elements" queries.
* ``peaks`` d-spacing index — a B-tree index on ``peaks.d`` (and an optional
  R-tree) so ``WHERE d BETWEEN ? AND ?`` is O(log n) instead of a full scan.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3

logger = logging.getLogger(__name__)


def _element_set_hash(elements: list[str]) -> str:
    """Return a stable hash for a sorted list of element symbols.

    Parameters
    ----------
    elements:
        Element symbols (will be sorted internally).
    """
    key = ",".join(sorted(elements))
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def build_element_index(conn: sqlite3.Connection) -> int:
    """Rebuild the ``element_combo`` inverted index from the ``elements`` table.

    Implements the reference software's element-set search acceleration (Phase 5 / T5.3).
    For each unique element set found across all entries, a row is written
    to ``element_combo`` mapping the set hash to the newline-joined entry ids.

    Parameters
    ----------
    conn:
        Open database connection.

    Returns
    -------
    int
        Number of distinct element sets indexed.
    """
    # Group elements by entry_id.
    cur = conn.execute(
        "SELECT entry_id, element FROM elements ORDER BY entry_id, element",
    )
    groups: dict[str, list[str]] = {}
    for entry_id, element in cur:
        groups.setdefault(entry_id, []).append(element)

    # Invert: element_set_hash -> list[entry_id]
    combo: dict[str, list[str]] = {}
    for entry_id, elements in groups.items():
        h = _element_set_hash(elements)
        combo.setdefault(h, []).append(entry_id)

    with conn:
        conn.execute("DELETE FROM element_combo")
        conn.executemany(
            "INSERT INTO element_combo (element_set_hash, entry_ids) VALUES (?, ?)",
            [(h, "\n".join(eids)) for h, eids in combo.items()],
        )
    logger.info("built element index: %d distinct element sets", len(combo))
    return len(combo)


def build_d_index(conn: sqlite3.Connection) -> None:
    """Ensure the d-spacing range index exists and statistics are fresh.

    Implements the reference software's d-value search acceleration (Phase 5 / T5.3).  The
    B-tree index ``idx_peaks_d`` already exists in the schema; this function
    guarantees it and runs ``ANALYZE`` so the query planner uses it for
    ``WHERE d BETWEEN ? AND ?``.

    Parameters
    ----------
    conn:
        Open database connection.
    """
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_peaks_d ON peaks(d)",
    )
    conn.execute("ANALYZE peaks")
    logger.debug("d-spacing index ensured and analyzed")


def build_rtree_d_index(conn: sqlite3.Connection) -> bool:
    """Build a 1-D R-tree virtual table over ``peaks.d`` (optional).

    R-tree range queries are faster than B-tree for very large peak tables.
    Falls back gracefully (returns ``False``) if the SQLite build lacks the
    rtree module; the B-tree index still serves d-range queries.

    Parameters
    ----------
    conn:
        Open database connection.

    Returns
    -------
    bool
        ``True`` if the R-tree was created successfully.
    """
    try:
        conn.execute("DROP TABLE IF EXISTS peaks_d_rtree")
        conn.execute(
            "CREATE VIRTUAL TABLE peaks_d_rtree USING rtree(id, d_lo, d_hi)",
        )
    except sqlite3.OperationalError as exc:
        logger.warning("rtree module unavailable (%s); using B-tree d index", exc)
        return False
    cur = conn.execute("SELECT rowid, d FROM peaks")
    rows = [(rid, float(d), float(d)) for rid, d in cur]
    with conn:
        conn.executemany(
            "INSERT INTO peaks_d_rtree (id, d_lo, d_hi) VALUES (?, ?, ?)",
            rows,
        )
    logger.info("built R-tree d index over %d peaks", len(rows))
    return True


def build_all_indexes(conn: sqlite3.Connection) -> dict[str, object]:
    """Build every acceleration index in one call.

    Parameters
    ----------
    conn:
        Open database connection.

    Returns
    -------
    dict
        Summary with keys ``element_sets`` and ``rtree``.
    """
    n_sets = build_element_index(conn)
    build_d_index(conn)
    rtree_ok = build_rtree_d_index(conn)
    return {"element_sets": n_sets, "rtree": rtree_ok}
