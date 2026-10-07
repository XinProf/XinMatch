"""Multi-field search filters for the reference database (Phase 5 / T5.5).

Implements Match!'s *Search/Match → Restraints* panel: element
(required / excluded), crystal system, space group, year range, and
arbitrary combinations thereof.  Each filter returns a set of entry ids;
:func:`search_combined` intersects them.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)


def search_by_elements(
    conn: sqlite3.Connection,
    required: set[str] | None = None,
    excluded: set[str] | None = None,
) -> list[str]:
    """Return entry ids whose element set includes all *required* elements
    and none of the *excluded* elements.

    Implements Match!'s *Restraints → Composition* element filter
    (Phase 5 / T5.5).  Uses the ``elements`` inverted-index table.

    Parameters
    ----------
    conn:
        Open database connection.
    required:
        Elements that must be present.
    excluded:
        Elements that must not be present.

    Returns
    -------
    list[str]
        Matching entry ids.
    """
    required = set(required or [])
    excluded = set(excluded or [])
    if not required and not excluded:
        return [r[0] for r in conn.execute("SELECT entry_id FROM entries")]

    candidates: set[str]
    if required:
        placeholders = ",".join("?" for _ in required)
        cur = conn.execute(
            f"""
            SELECT entry_id FROM elements
            WHERE element IN ({placeholders})
            GROUP BY entry_id
            HAVING COUNT(DISTINCT element) = ?
            """,
            (*required, len(required)),
        )
        candidates = {row[0] for row in cur}
    else:
        candidates = {row[0] for row in conn.execute("SELECT entry_id FROM entries")}

    if excluded:
        placeholders = ",".join("?" for _ in excluded)
        cur = conn.execute(
            f"SELECT DISTINCT entry_id FROM elements WHERE element IN ({placeholders})",
            (*excluded,),
        )
        bad = {row[0] for row in cur}
        candidates -= bad

    return sorted(candidates)


def search_by_crystal_system(conn: sqlite3.Connection, system: str) -> list[str]:
    """Return entry ids with the given crystal system.

    Implements Match!'s *Restraints → Crystallography → Crystal system*.

    Parameters
    ----------
    conn:
        Open database connection.
    system:
        Crystal system name (``cubic``, ``hexagonal``, ...).

    Returns
    -------
    list[str]
        Matching entry ids.
    """
    cur = conn.execute(
        "SELECT entry_id FROM entries WHERE crystal_system = ? ORDER BY entry_id",
        (system.lower(),),
    )
    return [row[0] for row in cur]


def search_by_space_group(conn: sqlite3.Connection, sg: str) -> list[str]:
    """Return entry ids with the given space-group symbol.

    Implements Match!'s *Restraints → Crystallography → Space group*.

    Parameters
    ----------
    conn:
        Open database connection.
    sg:
        Hermann–Mauguin space-group symbol (e.g. ``Pm-3m``).

    Returns
    -------
    list[str]
        Matching entry ids.
    """
    cur = conn.execute(
        "SELECT entry_id FROM entries WHERE space_group = ? ORDER BY entry_id",
        (sg,),
    )
    return [row[0] for row in cur]


def search_by_year(
    conn: sqlite3.Connection,
    year_min: int | None = None,
    year_max: int | None = None,
) -> list[str]:
    """Return entry ids whose publication year is within ``[year_min, year_max]``.

    Implements Match!'s *Restraints → Bibliography → Year*.

    Parameters
    ----------
    conn:
        Open database connection.
    year_min:
        Inclusive lower bound (``None`` = no lower bound).
    year_max:
        Inclusive upper bound (``None`` = no upper bound).

    Returns
    -------
    list[str]
        Matching entry ids.
    """
    clauses: list[str] = []
    params: list[Any] = []
    if year_min is not None:
        clauses.append("year >= ?")
        params.append(year_min)
    if year_max is not None:
        clauses.append("year <= ?")
        params.append(year_max)
    where = " AND ".join(clauses) if clauses else "1"
    cur = conn.execute(
        f"SELECT entry_id FROM entries WHERE {where} ORDER BY entry_id",
        params,
    )
    return [row[0] for row in cur]


def search_by_mineral_name(conn: sqlite3.Connection, name: str) -> list[str]:
    """Return entry ids whose mineral name contains *name* (case-insensitive).

    Parameters
    ----------
    conn:
        Open database connection.
    name:
        Substring to match against ``mineral_name``.

    Returns
    -------
    list[str]
        Matching entry ids.
    """
    cur = conn.execute(
        "SELECT entry_id FROM entries WHERE mineral_name LIKE ? ORDER BY entry_id",
        (f"%{name}%",),
    )
    return [row[0] for row in cur]


def search_by_formula(conn: sqlite3.Connection, formula: str) -> list[str]:
    """Return entry ids whose formula matches *formula* exactly.

    Parameters
    ----------
    conn:
        Open database connection.
    formula:
        Formula string to match (e.g. ``"C Ca O3"``).

    Returns
    -------
    list[str]
        Matching entry ids.
    """
    cur = conn.execute(
        "SELECT entry_id FROM entries WHERE formula = ? ORDER BY entry_id",
        (formula,),
    )
    return [row[0] for row in cur]


def search_combined(conn: sqlite3.Connection, **filters: Any) -> list[str]:
    """Combine multiple search filters (intersection of entry-id sets).

    Implements Match!'s combined restraints query (Phase 5 / T5.5).  Accepted
    keyword filters:

    * ``elements`` / ``required``: ``set[str]`` of required elements
    * ``excluded``: ``set[str]`` of forbidden elements
    * ``crystal_system``: ``str``
    * ``space_group``: ``str``
    * ``year_min`` / ``year_max``: ``int``
    * ``mineral_name``: ``str`` (substring)
    * ``formula``: ``str`` (exact)

    Unrecognised keys are ignored.  The result is the intersection of the
    per-filter entry-id sets.

    Parameters
    ----------
    conn:
        Open database connection.
    **filters:
        Filter keywords as listed above.

    Returns
    -------
    list[str]
        Entry ids satisfying every supplied filter, sorted.
    """
    # Collect per-filter id sets.
    sets: list[set[str]] = []

    if "elements" in filters or "required" in filters:
        req = filters.get("required", filters.get("elements"))
        exc = filters.get("excluded")
        ids = search_by_elements(conn, required=req, excluded=exc)
        sets.append(set(ids))

    if "crystal_system" in filters:
        sets.append(set(search_by_crystal_system(conn, filters["crystal_system"])))

    if "space_group" in filters:
        sets.append(set(search_by_space_group(conn, filters["space_group"])))

    if "year_min" in filters or "year_max" in filters:
        sets.append(set(search_by_year(
            conn,
            year_min=filters.get("year_min"),
            year_max=filters.get("year_max"),
        )))

    if "mineral_name" in filters:
        sets.append(set(search_by_mineral_name(conn, filters["mineral_name"])))

    if "formula" in filters:
        sets.append(set(search_by_formula(conn, filters["formula"])))

    if not sets:
        return [r[0] for r in conn.execute("SELECT entry_id FROM entries ORDER BY entry_id")]

    result = sets[0]
    for s in sets[1:]:
        result &= s
    return sorted(result)
