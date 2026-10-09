"""Tests for the real-COD XinMatch database builder (T6.9 upgrade).

Verifies the PolyXRD → XinMatch conversion logic in isolation:

* ``parse_csv_floats`` — CSV string parsing, empty handling;
* ``entry_from_row`` — d/I alignment, intensity-descending ordering,
  Top-N truncation, physical filtering (d > 0), cell construction,
  ref_id → entry_id;
* full pipeline over a tiny in-memory PolyXRD-style dump — schema,
  entries/peaks/elements rows, element index.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pytest

from tools.build_cod_xinmatch import (
    build,
    entry_from_row,
    parse_csv_floats,
)

# Column layout must match the ORDER of the SELECT in tools.build_cod_xinmatch.build.
COLUMNS = [
    "cod_id", "ref_id", "formula", "space_group",
    "cell_a", "cell_b", "cell_c", "cell_alpha", "cell_beta", "cell_gamma",
    "peaks_d", "peaks_i", "n_peaks",
]
COL = {name: i for i, name in enumerate(COLUMNS)}


def make_row(
    *,
    ref_id: str = "96-100-0005",
    formula: str = "O2 Ti",
    space_group: str | None = "I41/amd",
    cell: tuple[float, ...] = (3.78, 3.78, 9.51, 90.0, 90.0, 90.0),
    peaks_d: str = "3.52,1.89,2.38,1.70",
    peaks_i: str = "100,35,20,14",
    n_peaks: int = 4,
) -> tuple:
    """Build a row in the exact SELECT order of the builder."""
    return (
        1000005, ref_id, formula, space_group,
        cell[0], cell[1], cell[2], cell[3], cell[4], cell[5],
        peaks_d, peaks_i, n_peaks,
    )


# --------------------------------------------------------------------------- #
# parse_csv_floats
# --------------------------------------------------------------------------- #
def test_parse_csv_floats_basic():
    arr = parse_csv_floats("1.2,3.4,5.6")
    assert arr.tolist() == [1.2, 3.4, 5.6]


def test_parse_csv_floats_empty():
    assert parse_csv_floats("").size == 0
    assert parse_csv_floats(None).size == 0


def test_parse_csv_floats_garbage_returns_empty():
    assert parse_csv_floats("abc,def").size == 0


# --------------------------------------------------------------------------- #
# entry_from_row
# --------------------------------------------------------------------------- #
def test_entry_from_row_basic():
    e = entry_from_row(make_row(), max_peaks=100, col=COL)
    assert e is not None
    assert e.entry_id == "96-100-0005"       # ref_id becomes entry_id
    assert e.formula == "O2 Ti"
    assert e.space_group == "I41/amd"
    assert e.cell is not None
    assert e.cell.a == pytest.approx(3.78)
    assert e.cell.gamma == pytest.approx(90.0)
    # Ordered by intensity descending.
    assert e.intensities.tolist() == [100.0, 35.0, 20.0, 14.0]
    assert e.d_spacings[0] == pytest.approx(3.52)


def test_entry_from_row_reorders_by_intensity():
    # d values listed in decreasing order but intensities unsorted.
    e = entry_from_row(
        make_row(peaks_d="4.0,3.0,2.0", peaks_i="50,100,30"),
        max_peaks=100, col=COL,
    )
    assert e is not None
    assert e.intensities.tolist() == [100.0, 50.0, 30.0]
    assert e.d_spacings.tolist() == [3.0, 4.0, 2.0]


def test_entry_from_row_truncates_to_max_peaks():
    e = entry_from_row(
        make_row(
            peaks_d=",".join(str(float(i)) for i in range(10, 0, -1)),
            peaks_i=",".join(str(i) for i in range(10)),
        ),
        max_peaks=3, col=COL,
    )
    assert e is not None
    assert e.n_peaks == 3
    assert e.intensities.tolist() == [9.0, 8.0, 7.0]


def test_entry_from_row_drops_nonpositive_d():
    e = entry_from_row(
        make_row(peaks_d="3.0,-1.0,2.0,0.0", peaks_i="100,50,30,10"),
        max_peaks=100, col=COL,
    )
    assert e is not None
    assert e.d_spacings.tolist() == [3.0, 2.0]


def test_entry_from_row_empty_peaks_returns_none():
    assert entry_from_row(make_row(peaks_d="", peaks_i=""), max_peaks=100, col=COL) is None
    assert entry_from_row(make_row(peaks_d="3.0,2.0", peaks_i=""), max_peaks=100, col=COL) is None


def test_entry_from_row_mismatched_lengths_aligned():
    e = entry_from_row(
        make_row(peaks_d="3.0,2.0,1.0", peaks_i="100,50"),
        max_peaks=100, col=COL,
    )
    assert e is not None
    assert e.n_peaks == 2


def test_entry_from_row_no_cell():
    e = entry_from_row(make_row(cell=(None, None, None, None, None, None)), max_peaks=100, col=COL)
    assert e is not None
    assert e.cell is None


# --------------------------------------------------------------------------- #
# Full pipeline (tiny PolyXRD-style dump → XinMatch SQLite)
# --------------------------------------------------------------------------- #
def test_build_pipeline(tmp_path: Path):
    src = tmp_path / "polyxrd_cod.sqlite"
    out = tmp_path / "cod_xinmatch.db"
    s = sqlite3.connect(src)
    s.execute("CREATE TABLE phases ("
              "cod_id INTEGER, ref_id TEXT, formula TEXT, space_group TEXT,"
              "cell_a REAL, cell_b REAL, cell_c REAL,"
              "cell_alpha REAL, cell_beta REAL, cell_gamma REAL,"
              "n_peaks INTEGER, peaks_d TEXT, peaks_i TEXT)")
    insert_sql = (
        "INSERT INTO phases (cod_id, ref_id, formula, space_group,"
        " cell_a, cell_b, cell_c, cell_alpha, cell_beta, cell_gamma,"
        " peaks_d, peaks_i, n_peaks) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"
    )
    s.execute(insert_sql, make_row(ref_id="96-100-0005", formula="O2 Ti", peaks_d="3.52,1.89", peaks_i="100,35"))
    s.execute(insert_sql, make_row(ref_id="96-230-0451", formula="O Zn", peaks_d="2.82,1.62,2.48", peaks_i="100,37,25"))
    s.execute(insert_sql, make_row(ref_id="96-210-0001", formula="", peaks_d="", peaks_i=""))
    s.commit()
    s.close()

    summary = build(src, out, max_peaks=100)
    assert summary["entries_inserted"] == 2
    assert summary["skipped_empty"] == 1
    assert summary["peak_rows_total"] == 5

    conn = sqlite3.connect(out)
    entries = conn.execute("SELECT entry_id, formula FROM entries ORDER BY entry_id").fetchall()
    assert entries == [
        ("96-100-0005", "O2 Ti"),
        ("96-230-0451", "O Zn"),
    ]
    peak_rows = conn.execute("SELECT COUNT(*) FROM peaks").fetchone()[0]
    assert peak_rows == 5
    # Element index rows exist.
    elem_count = conn.execute("SELECT COUNT(*) FROM elements").fetchone()[0]
    assert elem_count == 4  # O, Ti, O, Zn (per-entry rows; duplicates OK)
    # d-window search works against the built index.
    hits = conn.execute(
        "SELECT DISTINCT entry_id FROM peaks WHERE d BETWEEN 3.5 AND 3.55"
    ).fetchall()
    assert hits == [("96-100-0005",)]
    conn.close()
