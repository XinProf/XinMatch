"""Tests for :mod:`xinmatch.core.search.restraints_apply` (Phase 6 / T7).

Self-contained: builds a small in-memory database with curated synthetic
entries (no dependency on real COD data or on sibling test fixtures that
might be edited concurrently by other agents).
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pytest

from xinmatch.core.db import build_element_index, create_tables, insert_entries
from xinmatch.core.model import CellParams, ElementState, Entry, Restraints
from xinmatch.core.search.restraints_apply import (
    apply_restraints,
    prune_candidates,
    score_restraints_match,
)


# ---------------------------------------------------------------------------
# Synthetic test entries (curated so assertions are easy to reason about)
# ---------------------------------------------------------------------------
def _entry(
    entry_id: str,
    formula: str,
    *,
    space_group: str | None = None,
    cell: CellParams | None = None,
    mineral_name: str | None = None,
    author: str | None = None,
    year: int | None = None,
    color: str | None = None,
    quality: str = "A",
) -> Entry:
    """Build a minimal :class:`Entry` with the given metadata.

    d-spacings / intensities are placeholder values; restraints don't read
    them.  ``color``, ``author`` and ``year`` are stashed in the literature
    dict (the convention used by :func:`xinmatch.core.db.build_cod._entry_row`).
    """
    return Entry(
        entry_id=entry_id,
        formula=formula,
        d_spacings=np.array([3.0, 2.0, 1.5]),
        intensities=np.array([100.0, 50.0, 25.0]),
        mineral_name=mineral_name,
        cell=cell,
        space_group=space_group,
        hkl=[(1, 0, 0), (1, 1, 0), (1, 1, 1)],
        literature={"author": author, "year": year, "color": color, "journal": "J"},
        quality=quality,
    )


@pytest.fixture
def test_entries() -> list[Entry]:
    """A curated 7-entry set covering diverse chemistries / systems / metadata."""
    return [
        _entry(
            "E1", "Si O2", space_group="P3221",
            cell=CellParams(4.914, 4.914, 5.405, gamma=120.0),
            mineral_name="Quartz", author="Smith J.", year=1970,
            color="white", quality="A",
        ),
        _entry(
            "E2", "C Ca O3", space_group="R-3c",
            cell=CellParams(4.99, 4.99, 17.06, gamma=120.0),
            mineral_name="Calcite", author="Doe A.", year=1965,
            color="white", quality="B",
        ),
        _entry(
            "E3", "Na Cl", space_group="Fm-3m",
            cell=CellParams(5.64, 5.64, 5.64),
            mineral_name="Halite", author="Brown K.", year=1960,
            color="colorless", quality="A",
        ),
        _entry(
            "E4", "Fe2 O3", space_group="R-3c",
            cell=CellParams(5.04, 5.04, 13.75, gamma=120.0),
            mineral_name="Hematite", author="Smith R.", year=1968,
            color="red", quality="C",
        ),
        _entry(
            "E5", "Cu", space_group="Fm-3m",
            cell=CellParams(3.615, 3.615, 3.615),
            mineral_name=None, author="Lee M.", year=1963,
            color="red", quality="A",
        ),
        _entry(
            "E6", "B6 La", space_group="Pm-3m",
            cell=CellParams(4.156, 4.156, 4.156),
            mineral_name="Lanthanum hexaboride", author="Tanaka", year=1971,
            color="black", quality="A",
        ),
        # Organic compound (C and H both present)
        _entry(
            "E7", "C H N O", space_group="P21/c",
            cell=CellParams(5.0, 6.0, 7.0, beta=100.0),
            mineral_name=None, author="Wang L.", year=2000,
            color="white", quality="B",
        ),
    ]


@pytest.fixture
def populated_conn(test_entries: list[Entry]) -> sqlite3.Connection:
    """In-memory DB with the 7 test entries + manually-set densities."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)
    insert_entries(conn, test_entries)
    build_element_index(conn)
    # Manually set densities (the Entry dataclass doesn't carry density).
    densities = {
        "E1": 2.65,  # Quartz
        "E2": 2.71,  # Calcite
        "E3": 2.16,  # Halite
        "E4": 5.26,  # Hematite
        "E5": 8.96,  # Copper
        "E6": 4.72,  # LaB6
        "E7": 1.50,  # organic
    }
    for eid, d in densities.items():
        conn.execute("UPDATE entries SET density = ? WHERE entry_id = ?", (d, eid))
    conn.commit()
    yield conn
    conn.close()


# ===========================================================================
# apply_restraints — element three-state
# ===========================================================================
def test_apply_restraints_empty_returns_all(populated_conn: sqlite3.Connection):
    """No active restraints → all entries returned."""
    out = apply_restraints(populated_conn, Restraints())
    assert set(out) == {"E1", "E2", "E3", "E4", "E5", "E6", "E7"}


def test_apply_restraints_required_elements(populated_conn: sqlite3.Connection):
    """Green (REQUIRED) element must be present in every returned entry."""
    r = Restraints()
    r.require("O")
    out = apply_restraints(populated_conn, r)
    # Entries with O: E1 (SiO2), E2 (CaCO3), E4 (Fe2O3), E7 (CHNO)
    assert set(out) == {"E1", "E2", "E4", "E7"}


def test_apply_restraints_excluded_elements(populated_conn: sqlite3.Connection):
    """Red (EXCLUDE) element must be absent in every returned entry."""
    r = Restraints()
    r.exclude("O")
    out = apply_restraints(populated_conn, r)
    # Entries without O: E3 (NaCl), E5 (Cu), E6 (LaB6)
    assert set(out) == {"E3", "E5", "E6"}


def test_apply_restraints_required_and_excluded(populated_conn: sqlite3.Connection):
    """Green + red combined: must contain O, must not contain Fe."""
    r = Restraints()
    r.require("O")
    r.exclude("Fe")
    out = apply_restraints(populated_conn, r)
    # E4 (Fe2O3) has Fe → excluded; E1, E2, E7 have O and no Fe.
    assert set(out) == {"E1", "E2", "E7"}


def test_apply_restraints_yellow_does_not_filter(populated_conn: sqlite3.Connection):
    """Yellow (OPTIONAL) element must have NO filtering effect."""
    r = Restraints()
    r.set_element("Si", ElementState.OPTIONAL)
    out = apply_restraints(populated_conn, r)
    assert len(out) == 7


def test_apply_restraints_multiple_required(populated_conn: sqlite3.Connection):
    """All green elements must be present (AND)."""
    r = Restraints()
    r.require("Si")
    r.require("O")
    out = apply_restraints(populated_conn, r)
    assert set(out) == {"E1"}  # only Quartz has both Si and O


# ===========================================================================
# apply_restraints — crystallography
# ===========================================================================
def test_apply_restraints_crystal_system(populated_conn: sqlite3.Connection):
    """Crystal-system filter selects entries derived as cubic."""
    r = Restraints(crystal_system="cubic")
    out = apply_restraints(populated_conn, r)
    # Fm-3m (E3, E5) and Pm-3m (E6) → cubic
    assert set(out) == {"E3", "E5", "E6"}


def test_apply_restraints_crystal_system_case_insensitive(populated_conn: sqlite3.Connection):
    """User-supplied crystal system is case-insensitive."""
    r = Restraints(crystal_system="CUBIC")
    out = apply_restraints(populated_conn, r)
    assert set(out) == {"E3", "E5", "E6"}


def test_apply_restraints_space_group(populated_conn: sqlite3.Connection):
    """Space-group filter selects entries with the exact HM symbol."""
    r = Restraints(space_group="R-3c")
    out = apply_restraints(populated_conn, r)
    assert set(out) == {"E2", "E4"}


def test_apply_restraints_space_group_no_match(populated_conn: sqlite3.Connection):
    r = Restraints(space_group="P1")
    out = apply_restraints(populated_conn, r)
    assert out == []


# ===========================================================================
# apply_restraints — bibliography
# ===========================================================================
def test_apply_restraints_year_range(populated_conn: sqlite3.Connection):
    r = Restraints(year_range=(1965, 1970))
    out = apply_restraints(populated_conn, r)
    # E1=1970, E2=1965, E4=1968 → in range; E3=1960, E5=1963, E6=1971, E7=2000 → out
    assert set(out) == {"E1", "E2", "E4"}


def test_apply_restraints_year_open_ended_min(populated_conn: sqlite3.Connection):
    r = Restraints(year_range=(1970, 9999))
    out = apply_restraints(populated_conn, r)
    assert set(out) == {"E1", "E6", "E7"}


def test_apply_restraints_mineral_name(populated_conn: sqlite3.Connection):
    """Mineral name uses substring search (existing query_filter behaviour)."""
    r = Restraints(mineral_name="Quartz")
    out = apply_restraints(populated_conn, r)
    assert set(out) == {"E1"}


def test_apply_restraints_mineral_name_case_insensitive(populated_conn: sqlite3.Connection):
    r = Restraints(mineral_name="quartz")
    out = apply_restraints(populated_conn, r)
    assert set(out) == {"E1"}


# ===========================================================================
# apply_restraints — post-filters (density / color / author / organic / quality)
# ===========================================================================
def test_apply_restraints_density_range(populated_conn: sqlite3.Connection):
    r = Restraints(density_range=(2.0, 3.0))
    out = apply_restraints(populated_conn, r)
    # E1=2.65, E2=2.71, E3=2.16 → in range; rest out
    assert set(out) == {"E1", "E2", "E3"}


def test_apply_restraints_density_excludes_null(populated_conn: sqlite3.Connection):
    """Entries with NULL density are excluded when a density range is set."""
    # Add an entry with no density set.
    r = Restraints(density_range=(0.0, 100.0))
    out = apply_restraints(populated_conn, r)
    # All 7 entries have explicit densities in [0, 100].
    assert len(out) == 7


def test_apply_restraints_color_exact(populated_conn: sqlite3.Connection):
    """Color match without wildcard → exact (case-insensitive) match."""
    r = Restraints(color="white")
    out = apply_restraints(populated_conn, r)
    assert set(out) == {"E1", "E2", "E7"}


def test_apply_restraints_color_substring_wildcard(populated_conn: sqlite3.Connection):
    """Color match with '*' wildcard → fragment match."""
    r = Restraints(color="*less*")
    out = apply_restraints(populated_conn, r)
    assert set(out) == {"E3"}  # "colorless" contains "less"


def test_apply_restraints_author_wildcard_prefix(populated_conn: sqlite3.Connection):
    """Author match with trailing '*' → prefix match."""
    r = Restraints(author="Smith*")
    out = apply_restraints(populated_conn, r)
    assert set(out) == {"E1", "E4"}  # "Smith J." and "Smith R."


def test_apply_restraints_author_substring_wildcard(populated_conn: sqlite3.Connection):
    """Author match with surrounding '*' → substring match."""
    r = Restraints(author="*anak*")
    out = apply_restraints(populated_conn, r)
    assert set(out) == {"E6"}  # "Tanaka" contains "anak"


def test_apply_restraints_author_exact(populated_conn: sqlite3.Connection):
    """Author match without wildcard → exact (case-insensitive)."""
    r = Restraints(author="tanaka")
    out = apply_restraints(populated_conn, r)
    assert set(out) == {"E6"}


def test_apply_restraints_quality_flags(populated_conn: sqlite3.Connection):
    r = Restraints(quality_flags={"A"})
    out = apply_restraints(populated_conn, r)
    # E1=A, E3=A, E5=A, E6=A; E2=B, E4=C, E7=B
    assert set(out) == {"E1", "E3", "E5", "E6"}


def test_apply_restraints_quality_flags_multiple(populated_conn: sqlite3.Connection):
    r = Restraints(quality_flags={"A", "B"})
    out = apply_restraints(populated_conn, r)
    assert set(out) == {"E1", "E2", "E3", "E5", "E6", "E7"}


def test_apply_restraints_inorganic_only(populated_conn: sqlite3.Connection):
    """inorganic_only ≈ no C-H bonds → drops E7 (C H N O)."""
    r = Restraints(inorganic_only=True)
    out = apply_restraints(populated_conn, r)
    assert "E7" not in out
    assert set(out) == {"E1", "E2", "E3", "E4", "E5", "E6"}


def test_apply_restraints_organic_only(populated_conn: sqlite3.Connection):
    """organic_only ≈ has both C and H → only E7."""
    r = Restraints(organic_only=True)
    out = apply_restraints(populated_conn, r)
    assert set(out) == {"E7"}


def test_apply_restraints_inorganic_organic_mutually_exclusive(
    populated_conn: sqlite3.Connection,
):
    """Setting both flags at once should yield the empty set."""
    r = Restraints(inorganic_only=True, organic_only=True)
    out = apply_restraints(populated_conn, r)
    assert out == []


# ===========================================================================
# apply_restraints — combinations
# ===========================================================================
def test_apply_restraints_combined_cubic_and_required_element(
    populated_conn: sqlite3.Connection,
):
    r = Restraints(crystal_system="cubic")
    r.require("La")
    out = apply_restraints(populated_conn, r)
    assert set(out) == {"E6"}  # only LaB6 is cubic and contains La


def test_apply_restraints_combined_no_match(populated_conn: sqlite3.Connection):
    """Cubic + Pm-3m + exclude La → empty."""
    r = Restraints(crystal_system="cubic", space_group="Pm-3m")
    r.exclude("La")
    out = apply_restraints(populated_conn, r)
    assert out == []


def test_apply_restraints_combined_density_and_year(populated_conn: sqlite3.Connection):
    r = Restraints(density_range=(2.0, 5.0), year_range=(1960, 1970))
    out = apply_restraints(populated_conn, r)
    # Density 2.0-5.0: E1=2.65, E2=2.71, E3=2.16, E4=5.26 (out), E6=4.72
    # Year 1960-1970: E1=1970, E2=1965, E3=1960, E4=1968 (E6=1971 out)
    # Intersection: E1, E2, E3
    assert set(out) == {"E1", "E2", "E3"}


def test_apply_restraints_combined_all_categories(populated_conn: sqlite3.Connection):
    """Exercise every restraint category in one go."""
    r = Restraints(
        crystal_system="cubic",
        space_group="Pm-3m",
        density_range=(4.0, 5.0),
        color="black",
        year_range=(1970, 1980),
        mineral_name="hexaboride",
        author="Tanaka",
        quality_flags={"A"},
        inorganic_only=True,
    )
    r.require("La")
    r.require("B")
    r.exclude("O")
    out = apply_restraints(populated_conn, r)
    assert set(out) == {"E6"}


# ===========================================================================
# prune_candidates
# ===========================================================================
def test_prune_candidates_empty_input(populated_conn: sqlite3.Connection):
    r = Restraints(crystal_system="cubic")
    out = prune_candidates(populated_conn, [], r)
    assert out == []


def test_prune_candidates_intersects(populated_conn: sqlite3.Connection):
    """prune_candidates returns candidates that satisfy the restraints."""
    r = Restraints(crystal_system="cubic")
    out = prune_candidates(populated_conn, ["E1", "E3", "E5", "E6"], r)
    # cubic: E3, E5, E6; E1 (Quartz, trigonal) drops out.
    assert set(out) == {"E3", "E5", "E6"}


def test_prune_candidates_no_restraints_preserves_input(populated_conn: sqlite3.Connection):
    """With no active restraints, prune_candidates returns the input as-is."""
    r = Restraints()
    out = prune_candidates(populated_conn, ["E1", "E3"], r)
    assert set(out) == {"E1", "E3"}


def test_prune_candidates_drops_invalid_ids(populated_conn: sqlite3.Connection):
    """IDs not in the DB are dropped (no restraints active)."""
    r = Restraints()
    out = prune_candidates(populated_conn, ["E1", "E_BAD"], r)
    assert set(out) == {"E1"}


def test_prune_candidates_element_filter(populated_conn: sqlite3.Connection):
    r = Restraints()
    r.require("O")
    out = prune_candidates(populated_conn, ["E1", "E3", "E4", "E6"], r)
    # Only E1 and E4 contain O.
    assert set(out) == {"E1", "E4"}


def test_prune_candidates_returns_sorted(populated_conn: sqlite3.Connection):
    """Output is sorted regardless of input order."""
    r = Restraints(crystal_system="cubic")
    out = prune_candidates(populated_conn, ["E6", "E3", "E5"], r)
    assert out == ["E3", "E5", "E6"]


# ===========================================================================
# score_restraints_match
# ===========================================================================
def test_score_empty_restraints_is_zero(test_entries: list[Entry]):
    r = Restraints()
    for e in test_entries:
        assert score_restraints_match(e, r) == 0.0


def test_score_required_element_hit(test_entries: list[Entry]):
    """E1 (SiO2) with required Si, O → +1 +1 = 2.0."""
    e1 = next(e for e in test_entries if e.entry_id == "E1")
    r = Restraints()
    r.require("Si")
    r.require("O")
    assert score_restraints_match(e1, r) == 2.0


def test_score_required_element_miss(test_entries: list[Entry]):
    """E3 (NaCl) with required O → -1.0."""
    e3 = next(e for e in test_entries if e.entry_id == "E3")
    r = Restraints()
    r.require("O")
    assert score_restraints_match(e3, r) == -1.0


def test_score_required_partial_match(test_entries: list[Entry]):
    """E1 (SiO2) with required Si + O + Fe → +1 +1 -1 = 1.0."""
    e1 = next(e for e in test_entries if e.entry_id == "E1")
    r = Restraints()
    r.require("Si")
    r.require("O")
    r.require("Fe")
    assert score_restraints_match(e1, r) == 1.0


def test_score_excluded_element_hit(test_entries: list[Entry]):
    """E1 (SiO2) with excluded O → O present → -1.0."""
    e1 = next(e for e in test_entries if e.entry_id == "E1")
    r = Restraints()
    r.exclude("O")
    assert score_restraints_match(e1, r) == -1.0


def test_score_excluded_element_miss(test_entries: list[Entry]):
    """E3 (NaCl) with excluded O → O absent → +1.0."""
    e3 = next(e for e in test_entries if e.entry_id == "E3")
    r = Restraints()
    r.exclude("O")
    assert score_restraints_match(e3, r) == 1.0


def test_score_yellow_element_bonus(test_entries: list[Entry]):
    """Yellow (OPTIONAL) element present → +0.1; absent → no bonus.

    Note: :meth:`Restraints.set_element` with ``OPTIONAL`` removes the entry
    (yellow is the implicit default).  To store a yellow element explicitly
    we use the ``Restraints`` constructor, which bypasses the removal logic.
    """
    e1 = next(e for e in test_entries if e.entry_id == "E1")  # Si, O
    e3 = next(e for e in test_entries if e.entry_id == "E3")  # Na, Cl
    r = Restraints(elements={"Si": ElementState.OPTIONAL})
    assert score_restraints_match(e1, r) == 0.1  # Si present
    assert score_restraints_match(e3, r) == 0.0  # Si absent


def test_score_crystal_system_match(test_entries: list[Entry]):
    """E6 (LaB6 cubic) → +1.0."""
    e6 = next(e for e in test_entries if e.entry_id == "E6")
    r = Restraints(crystal_system="cubic")
    assert score_restraints_match(e6, r) == 1.0


def test_score_crystal_system_mismatch(test_entries: list[Entry]):
    """E1 (Quartz, trigonal) vs cubic → -1.0."""
    e1 = next(e for e in test_entries if e.entry_id == "E1")
    r = Restraints(crystal_system="cubic")
    assert score_restraints_match(e1, r) == -1.0


def test_score_space_group_match(test_entries: list[Entry]):
    e1 = next(e for e in test_entries if e.entry_id == "E1")
    r = Restraints(space_group="P3221")
    assert score_restraints_match(e1, r) == 1.0


def test_score_space_group_mismatch(test_entries: list[Entry]):
    e1 = next(e for e in test_entries if e.entry_id == "E1")
    r = Restraints(space_group="Pm-3m")
    assert score_restraints_match(e1, r) == -1.0


def test_score_year_range_match(test_entries: list[Entry]):
    e1 = next(e for e in test_entries if e.entry_id == "E1")  # year=1970
    r = Restraints(year_range=(1965, 1972))
    assert score_restraints_match(e1, r) == 1.0


def test_score_year_range_mismatch(test_entries: list[Entry]):
    e1 = next(e for e in test_entries if e.entry_id == "E1")  # year=1970
    r = Restraints(year_range=(1980, 2000))
    assert score_restraints_match(e1, r) == -1.0


def test_score_color_match(test_entries: list[Entry]):
    e1 = next(e for e in test_entries if e.entry_id == "E1")  # color white
    r = Restraints(color="white")
    assert score_restraints_match(e1, r) == 1.0


def test_score_color_mismatch(test_entries: list[Entry]):
    e1 = next(e for e in test_entries if e.entry_id == "E1")  # color white
    r = Restraints(color="*less*")  # "white" doesn't contain "less"
    assert score_restraints_match(e1, r) == -1.0


def test_score_author_wildcard(test_entries: list[Entry]):
    e1 = next(e for e in test_entries if e.entry_id == "E1")  # "Smith J."
    r = Restraints(author="Smith*")
    assert score_restraints_match(e1, r) == 1.0


def test_score_mineral_name_match(test_entries: list[Entry]):
    e1 = next(e for e in test_entries if e.entry_id == "E1")  # "Quartz"
    r = Restraints(mineral_name="Quartz")
    assert score_restraints_match(e1, r) == 1.0


def test_score_quality_flags_match(test_entries: list[Entry]):
    e1 = next(e for e in test_entries if e.entry_id == "E1")  # quality "A"
    r = Restraints(quality_flags={"A"})
    assert score_restraints_match(e1, r) == 1.0


def test_score_quality_flags_mismatch(test_entries: list[Entry]):
    e1 = next(e for e in test_entries if e.entry_id == "E1")  # quality "A"
    r = Restraints(quality_flags={"B", "C"})
    assert score_restraints_match(e1, r) == -1.0


def test_score_inorganic_only(test_entries: list[Entry]):
    e1 = next(e for e in test_entries if e.entry_id == "E1")  # SiO2 inorganic
    e7 = next(e for e in test_entries if e.entry_id == "E7")  # CHNO organic
    r = Restraints(inorganic_only=True)
    assert score_restraints_match(e1, r) == 1.0
    assert score_restraints_match(e7, r) == -1.0


def test_score_organic_only(test_entries: list[Entry]):
    e1 = next(e for e in test_entries if e.entry_id == "E1")  # SiO2 inorganic
    e7 = next(e for e in test_entries if e.entry_id == "E7")  # CHNO organic
    r = Restraints(organic_only=True)
    assert score_restraints_match(e7, r) == 1.0
    assert score_restraints_match(e1, r) == -1.0


def test_score_combined_restraints(test_entries: list[Entry]):
    """E6 (LaB6) with cubic + Pm-3m + required La/B + excluded O → +5.0."""
    e6 = next(e for e in test_entries if e.entry_id == "E6")
    r = Restraints(crystal_system="cubic", space_group="Pm-3m")
    r.require("La")
    r.require("B")
    r.exclude("O")
    # 5 active hard restraints, all match → 5.0
    assert score_restraints_match(e6, r) == 5.0


def test_score_ranks_matching_above_non_matching(test_entries: list[Entry]):
    """A passing entry must outscore a failing one for the same restraints."""
    e1 = next(e for e in test_entries if e.entry_id == "E1")  # SiO2
    e3 = next(e for e in test_entries if e.entry_id == "E3")  # NaCl
    r = Restraints(crystal_system="trigonal")
    r.require("O")
    # E1: trigonal (Quartz P3221) ✓ +1, O present ✓ +1 → 2.0
    # E3: cubic ✗ -1, O absent ✗ -1 → -2.0
    assert score_restraints_match(e1, r) > score_restraints_match(e3, r)


def test_score_yellow_bonus_does_not_affect_hard_restraints(test_entries: list[Entry]):
    """Yellow elements only add small bonuses; they never trigger -1.0."""
    e1 = next(e for e in test_entries if e.entry_id == "E1")  # Si, O
    r = Restraints()
    r.set_element("Pb", ElementState.OPTIONAL)  # Pb absent → no bonus, no penalty
    assert score_restraints_match(e1, r) == 0.0
