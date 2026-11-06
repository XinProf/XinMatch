"""Mineral-name normalisation: the ruler must not over-count.

Every case below is taken from an actual ``entries.mineral_name`` value in
COD-Inorg-20261020 (see ``docs/基准报告-物相检索-v3.md`` §17).  The positive
cases are spelling variants of one mineral; the negative cases are *different
species or polymorphs whose names merely contain the truth name* — those would
inflate phase recall if the matcher were naively substring-based.
"""

from __future__ import annotations

import pytest

from xinmatch.core.search.mineral_name import mineral_name_matches, mineral_species_key


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("Zincite", "zincite"),
        ("zincite", "zincite"),
        ("  Quartz  ", "quartz"),
        # Polymorph / polytype qualifiers are dropped.
        ("Quartz low", "quartz"),
        ("Quartz high", "quartz"),
        ("Muscovite-2M1", "muscovite"),
        ("Muscovite 2M1", "muscovite"),
        ("Muscovite-3T", "muscovite"),
        ("Kaolinite 2M", "kaolinite"),
        ("Clinochlore 2M", "clinochlore"),
        # Parenthetical notes and structural prefixes are dropped.
        ("Brucite (deuterated)", "brucite"),
        ("Dolomite (quenched from 1323 K, 11 kbar)", "dolomite"),
        ("Hematite-proto", "hematite"),
        # A leading qualifier is NOT a species change but is kept verbatim, so
        # "K-feldspar" stays distinct from "Feldspar" (aliases cover it).
        ("K-feldspar", "k feldspar"),
        ("K feldspar at 350 C", "k feldspar at 350 c"),
    ],
)
def test_species_key_normalisation(raw: str, key: str) -> None:
    assert mineral_species_key(raw) == key


@pytest.mark.parametrize(
    ("raw", "truth"),
    [
        ("Nitrocalcite", "Calcite"),
        ("Barytocalcite", "Calcite"),
        ("Magnesium calcite", "Calcite"),
        ("Strontiofluorite", "Fluorite"),
        ("Zirconolite", "Zircon"),
        ("Pseudorutile", "Rutile"),
        ("Rongibbsite", "Gibbsite"),
        ("Rutile", "Anatase"),
        ("Cristobalite", "Quartz"),
        ("Anatase", "Rutile"),
    ],
)
def test_lookalike_names_do_not_match(raw: str, truth: str) -> None:
    """A name that merely *contains* the truth name must not count as a hit."""
    assert not mineral_name_matches(raw, [truth])


def test_variants_of_the_same_mineral_match() -> None:
    assert mineral_name_matches("Quartz high", ["Quartz"])
    assert mineral_name_matches("Muscovite-2M1", ["Muscovite 2M1"])
    assert mineral_name_matches("deuterated brucite at 90 K", ["Brucite"])


def test_nameless_card_never_matches() -> None:
    """No name is no evidence — must not become "matches everything"."""
    assert not mineral_name_matches(None, ["Quartz"])
    assert not mineral_name_matches("", ["Quartz"])
    assert not mineral_name_matches("   ", ["Quartz"])
    # ... and neither does an empty acceptance set.
    assert not mineral_name_matches("Quartz", [])


@pytest.mark.parametrize(
    "placeholder",
    ["hexagonal", "Cubic", "monoclinic", "unknown", "none", "not determined"],
)
def test_crystal_system_words_are_not_names(placeholder: str) -> None:
    """A crystal system is not a phase identity.

    COD stores ``mineral_name="hexagonal"`` on a few entries (the 2-1 leader,
    card 96-157-7381, is one).  If that counted as a name, the ruler would call
    a correct hit a miss — it must collapse to "no name" and fall back to
    composition instead.
    """
    assert mineral_species_key(placeholder) == ""
