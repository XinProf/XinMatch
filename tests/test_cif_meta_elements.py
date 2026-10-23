"""Regression tests for CIF metadata extraction (:mod:`cif_meta`).

The failure modes covered here all share one consequence: a phase whose element
list comes out empty is invisible to every element-filtered search, so it can
never be matched no matter how well its peaks agree.  They are silent by nature
-- the build still succeeds and the library still looks complete -- which is why
each one gets an explicit test.

Three distinct causes were found in the 2026-10-20 COD snapshot:

1. ``_chemical_formula_sum`` written as a CIF *text field* (``;...;``).  gemmi
   returns the delimiters verbatim, so ``";Al1.15 Ba0.04 ... Zn0.54\\n;"`` does
   not start with an element symbol and the parser returns ``[]``.
2. Files that carry no ``_chemical_formula_sum`` at all, only
   ``_chemical_formula_structural`` / ``_chemical_formula_moiety``.
3. Files that carry no formula of any kind.  The atom-site list is then the only
   element source.

Deuterium (``D``) and tritium (``T``) are a fourth, smaller case: they are not
IUPAC element symbols, so a pure deuteride lost its hydrogen entirely.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from xinmatch.core.db.cif_meta import (
    elements_from_formula,
    elements_from_sites,
    parse_meta,
)

#: Minimal but complete ``_atom_site`` header, so gemmi accepts the file as a
#: small structure and the site-list fallback has something to read.
_ATOM_SITE_HEADER = """\
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
"""


def _write_cif(tmp_path: Path, body: str, sites: str = "O1 O 0.0 0.0 0.0\n") -> Path:
    """Write a small but valid CIF and return its path."""
    path = tmp_path / "test.cif"
    path.write_text(
        "data_test\n"
        "_cell_length_a 5.0\n"
        "_cell_length_b 5.0\n"
        "_cell_length_c 5.0\n"
        "_cell_angle_alpha 90\n"
        "_cell_angle_beta 90\n"
        "_cell_angle_gamma 90\n"
        "_symmetry_space_group_name_H-M 'P 1'\n"
        f"{body}"
        f"{_ATOM_SITE_HEADER}"
        f"{sites}",
        encoding="utf-8",
    )
    return path


def test_text_field_formula_keeps_its_elements(tmp_path: Path) -> None:
    """A ``;``-delimited formula must lose the delimiters, not its chemistry."""
    path = _write_cif(
        tmp_path,
        "_chemical_formula_sum\n"
        ";K0.89 Al1.15 Si2.92\n"
        " O12\n"
        ";\n",
    )
    meta = parse_meta(path)
    assert meta is not None
    assert meta.formula == "K0.89 Al1.15 Si2.92 O12"
    assert meta.elements == ["Al", "K", "O", "Si"]


def test_single_line_quoted_formula_unchanged(tmp_path: Path) -> None:
    """The common quoting form must behave exactly as before."""
    path = _write_cif(tmp_path, "_chemical_formula_sum 'C3 O6 Sr'\n")
    meta = parse_meta(path)
    assert meta is not None
    assert meta.formula == "C3 O6 Sr"
    assert meta.elements == ["C", "O", "Sr"]


def test_structural_formula_fallback(tmp_path: Path) -> None:
    """No sum formula: the structural formula is the next-best source."""
    path = _write_cif(
        tmp_path,
        "_chemical_formula_structural 'Mg S O4 (H2 O)7'\n"
        "_chemical_name_mineral  Kieserite\n",
    )
    meta = parse_meta(path)
    assert meta is not None
    assert meta.elements == ["H", "Mg", "O", "S"]


def test_moiety_formula_fallback(tmp_path: Path) -> None:
    """The moiety formula is tried when the structural one is absent."""
    path = _write_cif(tmp_path, "_chemical_formula_moiety 'C8 H10 N4 O2'\n")
    meta = parse_meta(path)
    assert meta is not None
    assert meta.elements == ["C", "H", "N", "O"]


def test_site_list_fallback_when_no_formula(tmp_path: Path) -> None:
    """With no formula at all the atom sites still identify the elements."""
    path = _write_cif(
        tmp_path,
        "_chemical_name_systematic 'no formula in this file'\n",
        sites="Hf1 Hf4+ 0.0 0.0 0.0\nV1 V3+ 0.5 0.5 0.5\n",
    )
    meta = parse_meta(path)
    assert meta is not None
    assert meta.formula is None
    assert meta.elements == ["Hf", "V"]


def test_base64_formula_still_rejected(tmp_path: Path) -> None:
    """The delimiter handling must not turn a base64 blob into elements.

    Some COD entries store an encoded attachment in ``_chemical_formula_sum``.
    Rejecting those is what stops the library from gaining fictitious elements
    such as ``Q`` or ``Zz``.
    """
    blob = "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo="
    path = _write_cif(tmp_path, f"_chemical_formula_sum '{blob}'\n", sites="Si1 Si4+ 0.0 0.0 0.0\n")
    meta = parse_meta(path)
    assert meta is not None
    # The formula field is unusable, so the site list takes over -- but no
    # symbol may be invented from the blob.
    assert meta.elements == ["Si"]


@pytest.mark.parametrize(
    ("formula", "expected"),
    [
        ("D2 O", ["H", "O"]),
        ("D", ["H"]),
        ("T2 O", ["H", "O"]),
        # Two-letter symbols must not be mistaken for an isotope prefix.
        ("Dy2 O3", ["Dy", "O"]),
        # A real formula never contains a semicolon, so a stray one is a
        # delimiter and not chemistry.
        (";C O2;", ["C", "O"]),
        (None, []),
        ("", []),
        ("?", []),
    ],
)
def test_elements_from_formula_cases(formula: str | None, expected: list[str]) -> None:
    """Table of the formula shapes that reach the parser in a COD build."""
    assert elements_from_formula(formula) == expected


def test_elements_from_sites_ignores_unknown_symbols() -> None:
    """A placeholder site type contributes nothing rather than a fake element."""

    class _Site:
        def __init__(self, symbol: str) -> None:
            self.type_symbol = symbol

    class _Structure:
        sites = [_Site("M"), _Site("O2-"), _Site("Fe3+"), _Site("")]

    assert elements_from_sites(_Structure()) == ["Fe", "O"]
