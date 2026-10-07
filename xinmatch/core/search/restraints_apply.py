"""Apply :class:`~xinmatch.core.model.Restraints` to the reference database
and to candidate lists (Phase 6 / T7).

This module bridges the Restraints data model (T1) and the database query
filters (T5) so that search-match can prune the candidate pool before running
expensive FoM calculations.

Three public functions are provided:

* :func:`apply_restraints`        — query the database for entries matching all
                                   active restraints (Match! *Restraints* tab).
* :func:`prune_candidates`        — intersect an existing candidate list with
                                   the restraints-matching set (post-search
                                   pruning).
* :func:`score_restraints_match` — rank candidates by how well they satisfy
                                   the restraints; yellow element hits give
                                   small bonuses.

The implementation reuses :mod:`xinmatch.core.db.query_filter` for the indexed
SQL queries (element, crystal system, space group, year, mineral name) and
applies non-indexed fields (density, color, author, inorganic/organic,
quality flags) as Python-side post-filters.

Match! compatibility notes
--------------------------
* Element three-state colour coding (red / yellow / green) follows the
  *Restraints → Composition* spec: red excludes, green requires, yellow is
  optional (no filtering effect, but contributes a small bonus in
  :func:`score_restraints_match`).
* Text-field wildcards (``*``) follow Match!'s convention: without ``*``,
  exact (case-insensitive) match; with ``*``, the wildcard matches any
  sequence (e.g. ``"Aas*"`` → prefix match, ``"*doki*"`` → substring match).
* ``inorganic_only`` strictly requires atomic coordinates to detect C-H
  bonds.  We approximate it as "formula contains neither C nor H together"
  (see :func:`_is_inorganic`); this is conservative but matches Match!'s
  documented fallback behaviour for databases without structure data.
"""

from __future__ import annotations

import re
import sqlite3

from xinmatch.core.db.build_cod import derive_crystal_system
from xinmatch.core.db.query_filter import (
    search_by_crystal_system,
    search_by_elements,
    search_by_mineral_name,
    search_by_space_group,
    search_by_year,
)
from xinmatch.core.model import ElementState, Entry, Restraints, parse_formula

__all__ = [
    "apply_restraints",
    "prune_candidates",
    "score_restraints_match",
]


# ---------------------------------------------------------------------------
# Text-field wildcard helper (Match! '*' semantics)
# ---------------------------------------------------------------------------
def _matches_text(value: str | None, pattern: str) -> bool:
    """Match *value* against *pattern* using Match! wildcards.

    Match! uses ``'*'`` as a wildcard that matches any sequence (including
    the empty string).  Without ``'*'`` in the pattern, an exact (case-
    insensitive) match is required; with one or more ``'*'``, the literal
    segments between wildcards must appear in order.

    Examples
    --------
    >>> _matches_text("Quartz low", "Quartz*")
    True
    >>> _matches_text("Quartz", "quartz")
    True
    >>> _matches_text("Benjaminite", "*amin*")
    True
    >>> _matches_text("Calcite", "Quartz")
    False
    """
    if value is None:
        return False
    # Convert '*' wildcards to regex '.*' and escape the literal parts.
    parts = pattern.split("*")
    regex = ".*".join(re.escape(p) for p in parts)
    return re.fullmatch(regex, value, re.IGNORECASE) is not None


def _is_inorganic(formula: str | None) -> bool:
    """Approximate Match!'s *no C-H bonds* inorganic flag.

    Match! defines an inorganic compound as one without C-H bonds, which
    strictly requires atomic coordinates (only available for COD or user
    databases with full structure data).  When coordinates are unavailable,
    we approximate by:

        inorganic = NOT (formula contains both C and H)

    This conservatively excludes most organic compounds (which contain both
    C and H) while admitting some edge cases like methane-storing inorganic
    phases.  The heuristic is documented in :doc:`docs/restraints_composition`.
    """
    if not formula:
        return True
    elements = parse_formula(formula)
    return not ("C" in elements and "H" in elements)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def apply_restraints(conn: sqlite3.Connection, restraints: Restraints) -> list[str]:
    """Return entry ids satisfying all *restraints*.

    Implements Match!'s *Restraints* tab: the candidate list shown in the
    bottom-left of the Match! GUI is restricted to entries that satisfy
    every active restraint (logical AND across all subpages).

    Element three-state semantics:

    * 🔴 EXCLUDE  — entries containing this element are filtered out.
    * 🟢 REQUIRED — entries must contain this element.
    * 🟡 OPTIONAL — no effect on filtering (considered in
      :func:`score_restraints_match`).

    Indexed fields (elements, crystal system, space group, year, mineral
    name) use the SQL filters from :mod:`~xinmatch.core.db.query_filter`.
    Non-indexed fields (density, color, author, inorganic/organic, quality
    flags) are applied as Python-side post-filters on the SQL-filtered set.

    Parameters
    ----------
    conn:
        Open SQLite connection to the reference database.
    restraints:
        :class:`~xinmatch.core.model.Restraints` object; only non-default
        fields are applied.

    Returns
    -------
    list[str]
        Sorted entry ids matching every active restraint.
    """
    sets: list[set[str]] = []

    # Elements (green required + red excluded — yellow does not filter).
    required = {e for e, s in restraints.elements.items() if s == ElementState.REQUIRED}
    excluded = {e for e, s in restraints.elements.items() if s == ElementState.EXCLUDE}
    if required or excluded:
        sets.append(set(search_by_elements(conn, required=required, excluded=excluded)))

    # Crystal system.
    if restraints.crystal_system:
        sets.append(set(search_by_crystal_system(conn, restraints.crystal_system)))

    # Space group.
    if restraints.space_group:
        sets.append(set(search_by_space_group(conn, restraints.space_group)))

    # Year range.
    if restraints.year_range is not None:
        ymin, ymax = restraints.year_range
        sets.append(set(search_by_year(conn, year_min=ymin, year_max=ymax)))

    # Mineral name (substring search via existing query_filter).
    if restraints.mineral_name:
        sets.append(set(search_by_mineral_name(conn, restraints.mineral_name)))

    # Intersect all per-field sets, or fall back to all entries.
    if sets:
        result = sets[0]
        for s in sets[1:]:
            result &= s
    else:
        result = {row[0] for row in conn.execute("SELECT entry_id FROM entries")}

    # Apply non-indexed post-filters (density / color / author / organic /
    # quality flags).
    result = _post_filter(conn, result, restraints)

    return sorted(result)


def _post_filter(
    conn: sqlite3.Connection,
    entry_ids: set[str],
    restraints: Restraints,
) -> set[str]:
    """Apply non-indexed restraints on a set of entry ids.

    Filters by:

    * ``density_range``    — inclusive ``[lo, hi]`` interval (entries with
      NULL density are excluded when a range is set).
    * ``color``            — Match! wildcard text match (case-insensitive).
    * ``author``           — Match! wildcard text match (case-insensitive).
    * ``inorganic_only``   — approximate 'no C-H bonds' check on the formula.
    * ``organic_only``     — inverse of inorganic_only.
    * ``quality_flags``    — entry's ``quality`` must be in the set.

    Returns the (possibly reduced) set of entry ids.  If no post-filter is
    active, returns *entry_ids* unchanged.
    """
    if not entry_ids:
        return entry_ids
    has_post = (
        restraints.density_range is not None
        or restraints.color is not None
        or restraints.author is not None
        or bool(restraints.inorganic_only)
        or bool(restraints.organic_only)
        or bool(restraints.quality_flags)
    )
    if not has_post:
        return entry_ids

    placeholders = ",".join("?" for _ in entry_ids)
    cur = conn.execute(
        f"""
        SELECT entry_id, density, color, author, formula, quality
        FROM entries WHERE entry_id IN ({placeholders})
        """,
        tuple(entry_ids),
    )
    out: set[str] = set()
    for entry_id, density, color, author, formula, quality in cur:
        if restraints.density_range is not None:
            if density is None:
                continue
            lo, hi = restraints.density_range
            if not (lo <= density <= hi):
                continue
        if restraints.color is not None and not _matches_text(color, restraints.color):
            continue
        if restraints.author is not None and not _matches_text(author, restraints.author):
            continue
        if restraints.inorganic_only and not _is_inorganic(formula):
            continue
        if restraints.organic_only and _is_inorganic(formula):
            continue
        if restraints.quality_flags and quality not in restraints.quality_flags:
            continue
        out.add(entry_id)
    return out


def prune_candidates(
    conn: sqlite3.Connection,
    candidates: list[str],
    restraints: Restraints,
) -> list[str]:
    """Filter an existing candidate list by *restraints*.

    Implements Match!'s post-search restraints pruning: after a search-match
    run, the candidate list is intersected with the restraints-matching set
    so that entries removed by a restraint (e.g. an excluded element) drop
    out of the candidate list as well.

    Entries in *candidates* that are not present in the database are also
    dropped (they cannot satisfy any restraint).

    Parameters
    ----------
    conn:
        Open SQLite connection to the reference database.
    candidates:
        Entry ids to filter (e.g. the FoM-ranked search-match result).
    restraints:
        Active restraints; same semantics as :func:`apply_restraints`.

    Returns
    -------
    list[str]
        Sorted subset of *candidates* that satisfies every active restraint.
    """
    if not candidates:
        return []
    matches = set(apply_restraints(conn, restraints))
    return sorted(set(candidates) & matches)


def score_restraints_match(entry: Entry, restraints: Restraints) -> float:
    """Score how well *entry* matches the active *restraints*.

    Used to rank candidates within the pruned pool.  Each active hard
    restraint contributes ``+1.0`` when satisfied or ``-1.0`` when failed;
    yellow (OPTIONAL) element hits add a small ``+0.1`` bonus each.  An
    empty :class:`Restraints` yields ``0.0`` (all candidates equal).

    Density is **not** scored here because the :class:`Entry` dataclass does
    not carry a density field; density filtering is handled by
    :func:`apply_restraints` via the database ``density`` column.

    Parameters
    ----------
    entry:
        Reference-database entry to score.
    restraints:
        Active restraints.

    Returns
    -------
    float
        Match score; higher is better.
    """
    score = 0.0
    entry_elements = set(entry.elements)

    # Elements (hard: required / excluded; soft: optional).
    for elem, state in restraints.elements.items():
        if state == ElementState.REQUIRED:
            score += 1.0 if elem in entry_elements else -1.0
        elif state == ElementState.EXCLUDE:
            score += 1.0 if elem not in entry_elements else -1.0
        elif state == ElementState.OPTIONAL and elem in entry_elements:
            score += 0.1

    # Crystal system (derived from space group / cell).
    if restraints.crystal_system:
        cs = derive_crystal_system(entry)
        score += 1.0 if cs == restraints.crystal_system.lower() else -1.0

    # Space group (exact symbol match).
    if restraints.space_group:
        score += 1.0 if entry.space_group == restraints.space_group else -1.0

    # Year range.
    if restraints.year_range is not None:
        year = entry.literature.get("year")
        if year is not None:
            lo, hi = restraints.year_range
            score += 1.0 if lo <= year <= hi else -1.0
        else:
            score -= 1.0

    # Color (Match! wildcard match).
    if restraints.color is not None:
        color = entry.literature.get("color")
        score += 1.0 if _matches_text(color, restraints.color) else -1.0

    # Author (Match! wildcard match).
    if restraints.author is not None:
        author = entry.literature.get("author")
        score += 1.0 if _matches_text(author, restraints.author) else -1.0

    # Mineral name (Match! wildcard match).
    if restraints.mineral_name:
        score += 1.0 if _matches_text(entry.mineral_name, restraints.mineral_name) else -1.0

    # Inorganic / organic (heuristic via formula).
    if restraints.inorganic_only:
        score += 1.0 if _is_inorganic(entry.formula) else -1.0
    if restraints.organic_only:
        score += 1.0 if not _is_inorganic(entry.formula) else -1.0

    # Quality flags.
    if restraints.quality_flags:
        score += 1.0 if entry.quality in restraints.quality_flags else -1.0

    return score
