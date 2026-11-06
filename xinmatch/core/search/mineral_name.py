"""Mineral-name identity: normalise a trivial name to a *species key*.

Why this exists
---------------
Reference libraries spell the same mineral in many ways, and the benchmark needs
a rule that is **conservative** (a ruler that over-counts is worse than one that
under-counts):

===========================  ==================  =============================
Library value                Species key         Remark
===========================  ==================  =============================
``Zincite``                  ``zincite``         plain
``zincite``                  ``zincite``         case
``Quartz low`` / ``Quartz high``  ``quartz``      polymorph qualifier
``Muscovite-2M1`` / ``Muscovite 2M1``  ``muscovite``  polytype suffix
``Brucite (deuterated)``     ``brucite``         parenthetical note
``Hematite-proto``           ``hematite``        structural prefix
``Nitrocalcite``             ``nitrocalcite``    **different species**
``Anatase`` / ``Rutile``     ``anatase`` / ``rutile``  **different polymorphs**
===========================  ==================  =============================

The rule is therefore *not* substring matching: ``calcite`` must not match
``nitrocalcite``, and ``anatase`` must not match ``rutile`` even though both are
TiO₂.  Only a **leading or trailing qualifier** (polytype / temperature /
deuteration / provenance) is discarded, never an embedded word — so
``magnesium calcite`` stays a species of its own.  A name that is *nothing but* a
placeholder (``hexagonal``) collapses to the empty key, i.e. "no name".

Algorithm source: none (string normalisation for benchmarking); the qualifier
list is curated from the observed spellings of COD-Inorg-20261020 (probe
recorded in ``docs/基准报告-物相检索-v3.md`` §17).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

#: Leading or trailing words that qualify a mineral name without changing the
#: species.  Curated from actual ``entries.mineral_name`` values in COD-Inorg:
#: dropping them merges ``Quartz low`` / ``Quartz high`` with ``Quartz`` while
#: keeping ``Nitrocalcite`` apart from ``Calcite``.
_QUALIFIERS: frozenset[str] = frozenset({
    "low", "high", "deuterated", "quenched", "dental",
    "proto", "ideal", "natural", "synthetic",
    "heated", "annealed", "hydrated", "anhydrous",
})

#: Names that are **not** mineral names at all: crystal-system words and
#: placeholders.  COD writes these into ``_chemical_name_mineral`` for a handful
#: of entries (24 of 20,700 named cards in COD-Inorg), and treating them as a
#: real name makes the ruler *under*-count: the 2-1 leader carries
#: ``mineral_name="hexagonal"`` and was scored a miss until this rule existed.
_PLACEHOLDERS: frozenset[str] = frozenset({
    "hexagonal", "cubic", "tetragonal", "monoclinic", "orthorhombic",
    "triclinic", "trigonal", "rhombohedral", "amorphous",
    "unknown", "none", "not determined", "unidentified", "phase", "compound",
})

#: Polytype / stacking-variant suffix such as ``2M1``, ``3T``, ``1M``, ``2H``.
_POLYTYPE_RE = re.compile(r"^\d+[a-z]\d*$")

_PAREN_RE = re.compile(r"\([^)]*\)")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
#: Trailing measurement clause: ``"deuterated brucite at 90 K"`` → ``"deuterated brucite"``.
_AT_CLAUSE_RE = re.compile(r"\bat\s+-?\d+(?:\.\d+)?\s*k\b.*$")


def mineral_species_key(name: str | None) -> str:
    """Normalise a mineral name to its species key (empty string if unusable).

    Steps, in order:

    1. drop parenthetical notes — ``"Brucite (deuterated)"`` → ``"Brucite"``;
    2. drop a trailing measurement clause — ``"deuterated brucite at 90 K"``;
    3. lowercase and collapse every non-alphanumeric run to one space, so
       ``"Muscovite-2M1"`` and ``"Muscovite 2M1"`` agree;
    4. drop **leading and trailing** qualifier tokens (see :data:`_QUALIFIERS`)
       and polytype suffixes — ``"quartz high"`` → ``"quartz"``,
       ``"deuterated brucite"`` → ``"brucite"``.

    Words that are neither leading nor trailing qualifiers are kept, which is
    what prevents ``"Nitrocalcite"`` from being read as calcite and
    ``"magnesium calcite"`` from being read as ``"calcite"``.

    Args:
        name: Raw ``Entry.mineral_name`` (may be ``None`` or empty).

    Returns:
        The species key, or ``""`` when the name carries no usable token — also
        for a pure placeholder such as ``"hexagonal"``, because a crystal system
        is not evidence of a species.
    """
    if not name:
        return ""
    text = _PAREN_RE.sub(" ", name)
    text = _AT_CLAUSE_RE.sub(" ", text.lower())
    tokens = [t for t in _NON_ALNUM_RE.split(text) if t]
    while tokens and (tokens[-1] in _QUALIFIERS or _POLYTYPE_RE.match(tokens[-1])):
        tokens.pop()
    while len(tokens) > 1 and tokens[0] in _QUALIFIERS:
        tokens.pop(0)
    key = " ".join(tokens)
    return "" if key in _PLACEHOLDERS else key


def mineral_name_matches(
    candidate: str | None,
    accepted: Iterable[str],
) -> bool:
    """Whether *candidate* names the same species as any of *accepted*.

    Args:
        candidate: The card's ``Entry.mineral_name``.
        accepted: Names that the truth phase is known by (variants allowed).

    Returns:
        ``True`` only when both sides normalise to the same non-empty key, so a
        nameless card never matches by accident.
    """
    key = mineral_species_key(candidate)
    if not key:
        return False
    return any(mineral_species_key(a) == key for a in accepted)


def has_species_name(name: str | None) -> bool:
    """Whether *name* carries a usable species key (not empty, not a placeholder).

    Callers that treat a name as *evidence* must gate on this instead of
    ``if name:`` — ``"hexagonal"`` is a non-empty string that says nothing about
    the phase.

    Args:
        name: Raw ``Entry.mineral_name``.

    Returns:
        ``True`` only when :func:`mineral_species_key` yields a non-empty key.
    """
    return bool(mineral_species_key(name))


__all__ = ["has_species_name", "mineral_name_matches", "mineral_species_key"]
