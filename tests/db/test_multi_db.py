"""Tests for the multi-library registry and the PDF-2 sidecar parser.

The real PDF-2 dump (163,834 rows, 214 MB) and the built sidecar are used for
integration checks but are optional: when the source file is absent the
integration tests ``skip`` with a clear reason.  Synthetic fixtures cover the
CSV parsing and row-mapping logic so the suite stays fast and hermetic.
"""

from __future__ import annotations

import sqlite3

import pytest

from xinmatch.core.db import multi_db
from xinmatch.core.db.multi_db import (
    LibraryNotAvailableError,
    library_by_id,
    list_libraries,
    open_library,
    resolve_default,
)
from xinmatch.core.db.pdf2_index import entry_from_row, parse_csv_floats
from xinmatch.core.search.search_match import fetch_entries_by_ids


# ---------------------------------------------------------------------------
# Registry / manifest
# ---------------------------------------------------------------------------
def test_list_libraries_contains_known_ids():
    ids = {r.id for r in list_libraries()}
    assert {"cod_inorganics", "pdf2_2004", "cod_full"} <= ids


def test_resolve_default_is_cod_inorganics():
    rec = resolve_default()
    assert rec.id == "cod_inorganics"
    assert rec.kind == multi_db.KIND_XINMATCH


def test_library_by_id_unknown_returns_none():
    assert library_by_id("does-not-exist") is None


def test_default_library_is_available_in_repo():
    """The bundled cod_inorganics.db must be present in the dev checkout."""
    rec = resolve_default()
    assert rec.available, rec.unavailable_reason
    assert rec.entry_count and rec.entry_count > 0


def test_unavailable_record_carries_reason(tmp_path):
    """A record pointing at a missing file reports available=False + reason."""
    rec = multi_db._xinmatch_record(
        "ghost", "Ghost DB", multi_db.KIND_XINMATCH,
        tmp_path / "nope.db",
    )
    assert rec.available is False
    assert rec.unavailable_reason
    assert "not found" in rec.unavailable_reason


def test_open_library_unknown_id_raises_friendly():
    with pytest.raises(LibraryNotAvailableError, match="unknown library id"):
        open_library("no-such-library")


def test_open_library_missing_file_raises_friendly(monkeypatch, tmp_path):
    """open_library must not crash; it raises with the reason from the record."""
    missing = tmp_path / "missing.db"
    fake = multi_db._xinmatch_record(
        "cod_inorganics", "COD Inorganics (default, bundled)",
        multi_db.KIND_XINMATCH, missing,
    )
    monkeypatch.setattr(multi_db, "resolve_default", lambda: fake)
    monkeypatch.setattr(multi_db, "library_by_id", lambda _id: fake)
    with pytest.raises(LibraryNotAvailableError, match="not available"):
        open_library("cod_inorganics")


def test_open_default_library_is_searchable():
    """The default DB connection supports fetch_entries_by_ids."""
    conn = open_library("cod_inorganics")
    try:
        n = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        assert n > 0
        one_id = conn.execute("SELECT entry_id FROM entries LIMIT 1").fetchone()[0]
        entries = fetch_entries_by_ids(conn, [one_id])
        assert len(entries) == 1
        assert entries[0].entry_id == one_id
        assert entries[0].d_spacings.size > 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# PDF-2 CSV parsing (synthetic, hermetic)
# ---------------------------------------------------------------------------
def test_parse_csv_floats_robust():
    assert parse_csv_floats(None).size == 0
    assert parse_csv_floats("").size == 0
    assert parse_csv_floats("   ").size == 0
    out = parse_csv_floats("3.35,4.25,1.82")
    assert out.tolist() == [3.35, 4.25, 1.82]
    # garbage input must not raise
    assert parse_csv_floats("abc,def").size == 0


def _phases_row(values: dict[str, object]) -> sqlite3.Row:
    """Build a sqlite3.Row over a one-row in-memory ``phases`` table."""
    cols = ["cod_id", "ref_id", "formula", "name", "mineral", "space_group",
            "cell_a", "cell_b", "cell_c", "cell_alpha", "cell_beta",
            "cell_gamma", "peaks_d", "peaks_i", "n_peaks"]
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE phases (" + ", ".join(f"{c} TEXT" for c in cols) + ")"
    )
    conn.execute(
        f"INSERT INTO phases ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
        [values.get(c) for c in cols],
    )
    row = conn.execute("SELECT * FROM phases").fetchone()
    return row


def test_entry_from_row_maps_fields():
    row = _phases_row({
        "cod_id": 10649, "ref_id": "PDF2-010649", "formula": "O2 Si",
        "name": "Silicon Oxide", "mineral": "Quartz",
        "space_group": "P 32 2 1",
        "cell_a": 4.91, "cell_b": 4.91, "cell_c": 5.40,
        "cell_alpha": 90, "cell_beta": 90, "cell_gamma": 120,
        "peaks_d": "3.35,4.25,1.82", "peaks_i": "100,25,25", "n_peaks": 3,
    })
    e = entry_from_row(row, max_peaks=100)
    assert e is not None
    assert e.entry_id == "PDF2-010649"
    assert e.formula == "O2 Si"
    assert e.mineral_name == "Quartz"          # mineral preferred over name
    assert e.space_group == "P 32 2 1"
    # sorted by descending intensity, strongest first
    assert e.d_spacings[0] == pytest.approx(3.35)
    assert e.intensities[0] == 100.0


def test_entry_from_row_mineral_falls_back_to_name():
    row = _phases_row({
        "cod_id": 10002, "ref_id": "PDF2-010002", "formula": "C9 H8 N Na O3",
        "name": "Sodium hippurate", "mineral": "",
        "space_group": "", "cell_a": None,
        "peaks_d": "19.0,10.8", "peaks_i": "100,20", "n_peaks": 2,
    })
    e = entry_from_row(row, max_peaks=100)
    assert e is not None
    assert e.mineral_name == "Sodium hippurate"  # empty mineral -> name


def test_entry_from_row_empty_peaks_returns_none():
    row = _phases_row({
        "ref_id": "PDF2-099999", "formula": "X", "peaks_d": "", "peaks_i": "",
    })
    assert entry_from_row(row, max_peaks=100) is None


# ---------------------------------------------------------------------------
# Real PDF-2 integration (skipped when the dump / sidecar is absent)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def pdf2_source():
    src = multi_db.pdf2_source_path()
    if not src.exists():
        pytest.skip(f"PDF-2 source dump not found: {src}")
    return src


def test_real_pdf2_source_readonly_has_known_phases(pdf2_source):
    """Open the source read-only and check the textbook phases exist."""
    conn = sqlite3.connect(
        "file:" + pdf2_source.as_posix() + "?mode=ro", uri=True,
    )
    try:
        n = conn.execute("SELECT COUNT(*) FROM phases").fetchone()[0]
        assert n > 100_000
        for kw in ("Quartz", "Corundum", "Calcite"):
            row = conn.execute(
                "SELECT ref_id FROM phases WHERE mineral=? LIMIT 1", (kw,)
            ).fetchone()
            assert row is not None, f"{kw} missing from PDF-2"
    finally:
        conn.close()


def test_pdf2_sidecar_searchable_when_built():
    rec = library_by_id("pdf2_2004")
    if rec is None or not rec.available:
        pytest.skip(f"PDF-2 sidecar not built: {rec.unavailable_reason if rec else 'n/a'}")
    conn = open_library("pdf2_2004")
    try:
        row = conn.execute(
            "SELECT entry_id FROM entries WHERE mineral_name='Quartz' LIMIT 1"
        ).fetchone()
        assert row is not None
        entries = fetch_entries_by_ids(conn, [row[0]])
        assert entries and entries[0].d_spacings.size > 0
    finally:
        conn.close()
