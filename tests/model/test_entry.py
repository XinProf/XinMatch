"""Tests for :class:`xinmatch.core.model.Entry`, :class:`CellParams`, and :func:`parse_formula`."""

import numpy as np
import pytest

from xinmatch.core.model import CellParams, Entry, parse_formula


def test_parse_formula_simple():
    assert parse_formula("C Ca O3") == {"C": 1.0, "Ca": 1.0, "O": 3.0}


def test_parse_formula_decimal():
    assert parse_formula("B6 La0.987") == {"B": 6.0, "La": 0.987}


def test_parse_formula_nonexistent_returns_empty():
    assert parse_formula("") == {}


def test_entry_elements_derived_from_formula():
    e = Entry(
        entry_id="1",
        formula="C Ca O3",
        d_spacings=np.array([3.0, 2.0, 1.5]),
        intensities=np.array([1000.0, 500.0, 200.0]),
    )
    assert e.elements == frozenset({"C", "Ca", "O"})


def test_entry_normalized_intensities():
    e = Entry(
        entry_id="1",
        formula="Si O2",
        d_spacings=np.array([3.0, 2.0]),
        intensities=np.array([500.0, 250.0]),
    )
    norm = e.normalized_intensities()
    assert norm.max() == pytest.approx(1000.0)
    assert norm[1] == pytest.approx(500.0)


def test_entry_n_peaks():
    e = Entry(
        entry_id="1",
        formula="Si",
        d_spacings=np.array([3.0, 2.0, 1.5, 1.0]),
        intensities=np.array([1.0, 1.0, 1.0, 1.0]),
    )
    assert e.n_peaks == 4


def test_cell_params_roundtrip():
    cell = CellParams(a=4.0, b=5.0, c=6.0, alpha=90.0, beta=90.0, gamma=120.0)
    restored = CellParams.from_dict(cell.to_dict())
    assert restored.a == pytest.approx(4.0)
    assert restored.gamma == pytest.approx(120.0)


def test_entry_serialization_roundtrip():
    e = Entry(
        entry_id="COD-1000001",
        formula="C Ca O3",
        mineral_name="Calcite",
        cell=CellParams(a=5.0, b=5.0, c=15.0, gamma=120.0),
        space_group="R-3c",
        d_spacings=np.array([3.85, 3.05, 2.29]),
        intensities=np.array([1000.0, 800.0, 300.0]),
        hkl=[(0, 1, 2), (1, 0, 4), (1, 1, 3)],
        literature={"author": "Chessin", "year": 1965},
        quality="B",
    )
    restored = Entry.from_dict(e.to_dict())
    assert restored.entry_id == "COD-1000001"
    assert restored.mineral_name == "Calcite"
    assert restored.space_group == "R-3c"
    np.testing.assert_array_equal(restored.d_spacings, e.d_spacings)
    assert restored.literature["year"] == 1965
    assert restored.hkl == [(0, 1, 2), (1, 0, 4), (1, 1, 3)]
