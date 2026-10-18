"""Tests for the PolyXRD ``.sqlite`` compatibility layer (v2.0.0).

Synthetic databases cover every layout PolyXRD ships::

* ``phases`` with the PDF-2 column set (``ref_id`` / ``mineral``);
* ``phases`` with the COD column set (``cod_id`` only);
* ``cod_entries`` structure-only index (no peaks → not searchable).

The real dumps (``D:\\Project\\XRD\\PolyXRD\\cod_data``) are exercised by the
acceptance run, not here: the suite stays fast and hermetic.
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pytest

from xinmatch.core.cancel import OperationCancelledError, set_cancel_check
from xinmatch.core.db import build_element_index, create_tables, insert_entries, polyxrd
from xinmatch.core.model import Entry

PDF2_TABLE = (
    "CREATE TABLE phases (cod_id INTEGER, ref_id TEXT, formula TEXT, name TEXT,"
    " mineral TEXT, space_group TEXT, cell_a REAL, cell_b REAL, cell_c REAL,"
    " cell_alpha REAL, cell_beta REAL, cell_gamma REAL, n_peaks INTEGER,"
    " peaks_d TEXT, peaks_i TEXT)"
)
PDF2_ROWS = [
    (1, "PDF2-000001", "SiO2", "Quartz", "Quartz", "P3221", 4.913, 4.913, 5.405,
     90, 90, 120, 3, "4.26,3.34,2.46", "100,80,30"),
    (2, "PDF2-000002", "Al2O3", "Corundum", "Corundum", "R-3c", 4.759, 4.759, 12.99,
     90, 90, 120, 2, "2.55,2.09", "100,60"),
    (3, "PDF2-000003", "TiO2", "", "", "P42/mnm", 4.594, 4.594, 2.959,
     90, 90, 90, 2, "3.25,1.62", "100,40"),
]

COD_TABLE = (
    "CREATE TABLE phases (cod_id INTEGER, formula TEXT, space_group TEXT,"
    " cell_a REAL, cell_b REAL, cell_c REAL, cell_alpha REAL, cell_beta REAL,"
    " cell_gamma REAL, n_peaks INTEGER, peaks_d TEXT, peaks_i TEXT)"
)
COD_ROWS = [
    (101, "NaCl", "Fm-3m", 5.64, 5.64, 5.64, 90, 90, 90, 2, "3.26,2.82", "100,60"),
    (102, "Fe2O3", "R-3c", 5.04, 5.04, 13.75, 90, 90, 120, 2, "2.70,2.52", "100,70"),
]


def _make_db(path, ddl: str, rows: list[tuple], table: str = "phases"):
    conn = sqlite3.connect(path)
    conn.execute(ddl)
    placeholders = ",".join("?" * len(rows[0]))
    conn.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', rows)
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def pdf2_db(tmp_path):
    """A PolyXRD PDF-2-style ``phases`` database."""
    return _make_db(tmp_path / "PDF2_2004.sqlite", PDF2_TABLE, PDF2_ROWS)


@pytest.fixture
def cod_db(tmp_path):
    """A PolyXRD COD-style ``phases`` database (no name/mineral columns)."""
    return _make_db(tmp_path / "COD_inorganics.sqlite", COD_TABLE, COD_ROWS)


@pytest.fixture
def entries_only_db(tmp_path):
    """A PolyXRD structure-only index (``cod_entries``, no peaks)."""
    path = tmp_path / "cod_index.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE cod_entries (cod_id INTEGER, formula TEXT)")
    conn.executemany("INSERT INTO cod_entries VALUES (?,?)", [(1, "C"), (2, "Si")])
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def native_db(tmp_path):
    """A native XinMatch-schema database."""
    path = tmp_path / "native.db"
    conn = sqlite3.connect(path)
    create_tables(conn)
    insert_entries(
        conn,
        [
            Entry(
                entry_id="N-1",
                formula="LaB6",
                d_spacings=np.array([4.157, 2.937, 2.078]),
                intensities=np.array([100.0, 45.0, 20.0]),
            )
        ],
    )
    build_element_index(conn)
    conn.commit()
    conn.close()
    return path


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------
def test_detect_pdf2_style(pdf2_db):
    schema = polyxrd.detect_source(pdf2_db)
    assert schema.kind == polyxrd.SCHEMA_POLYXRD
    assert schema.searchable and schema.needs_conversion
    assert schema.table == "phases"
    assert schema.id_column == "ref_id"
    assert schema.name_column == "mineral"
    assert schema.row_count == 3
    assert ("a", "cell_a") in schema.cell_columns


def test_detect_cod_style(cod_db):
    schema = polyxrd.detect_source(cod_db)
    assert schema.kind == polyxrd.SCHEMA_POLYXRD
    assert schema.id_column == "cod_id"
    assert schema.name_column is None
    assert schema.reason is None


def test_detect_structure_only_index(entries_only_db):
    schema = polyxrd.detect_source(entries_only_db)
    assert schema.kind == polyxrd.SCHEMA_POLYXRD_ENTRIES
    assert not schema.searchable
    assert "no peak table" in (schema.reason or "") or "structures only" in (
        schema.reason or ""
    )


def test_detect_native(native_db):
    schema = polyxrd.detect_source(native_db)
    assert schema.kind == polyxrd.SCHEMA_XINMATCH
    assert schema.row_count == 1
    assert schema.searchable


def test_detect_missing_and_garbage(tmp_path):
    missing = polyxrd.detect_source(tmp_path / "nope.sqlite")
    assert missing.kind == polyxrd.SCHEMA_UNKNOWN
    assert "not found" in (missing.reason or "")

    junk = tmp_path / "junk.sqlite"
    junk.write_bytes(b"this is not sqlite" * 10)
    bad = polyxrd.detect_source(junk)
    assert bad.kind == polyxrd.SCHEMA_UNKNOWN
    assert bad.reason


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------
def test_build_sidecar_pdf2_rows(pdf2_db, tmp_path):
    out = tmp_path / "sidecar.db"
    summary = polyxrd.build_sidecar(pdf2_db, out)
    assert summary["entries_indexed"] == 3
    assert summary["entries_skipped"] == 0

    conn = sqlite3.connect(out)
    try:
        ids = [r[0] for r in conn.execute("SELECT entry_id FROM entries ORDER BY entry_id")]
        assert ids == ["PDF2-000001", "PDF2-000002", "PDF2-000003"]
        minerals = [
            r[0]
            for r in conn.execute(
                "SELECT mineral_name FROM entries ORDER BY entry_id"
            )
        ]
        assert minerals == ["Quartz", "Corundum", None]
        # peak rows + element index
        assert conn.execute("SELECT COUNT(*) FROM peaks").fetchone()[0] == 7
        assert conn.execute("SELECT COUNT(DISTINCT element) FROM elements").fetchone()[0] >= 3
        meta = dict(conn.execute("SELECT key, value FROM ext_source_meta"))
        assert meta["kind"] == polyxrd.SCHEMA_POLYXRD
        assert meta["source_table"] == "phases"
    finally:
        conn.close()


def test_build_sidecar_prefixes_cod_ids(cod_db, tmp_path):
    out = tmp_path / "sidecar.db"
    polyxrd.build_sidecar(cod_db, out)
    conn = sqlite3.connect(out)
    try:
        ids = [r[0] for r in conn.execute("SELECT entry_id FROM entries ORDER BY entry_id")]
        assert ids == ["COD-101", "COD-102"]
    finally:
        conn.close()


def test_build_sidecar_respects_max_peaks(pdf2_db, tmp_path):
    out = tmp_path / "sidecar.db"
    polyxrd.build_sidecar(pdf2_db, out, max_peaks=1)
    conn = sqlite3.connect(out)
    try:
        assert conn.execute("SELECT COUNT(*) FROM peaks").fetchone()[0] == 3
        # strongest reflection first (100 for all three rows)
        top = conn.execute(
            "SELECT d FROM peaks WHERE entry_id='PDF2-000001'"
        ).fetchone()[0]
        assert top == pytest.approx(4.26)
    finally:
        conn.close()


def test_build_sidecar_limit(pdf2_db, tmp_path):
    out = tmp_path / "sidecar.db"
    summary = polyxrd.build_sidecar(pdf2_db, out, limit=2)
    assert summary["entries_indexed"] == 2


def test_build_sidecar_rejects_unsupported(entries_only_db, tmp_path):
    with pytest.raises(ValueError, match="structures only|no peak"):
        polyxrd.build_sidecar(entries_only_db, tmp_path / "x.db")


def test_build_sidecar_missing_source(tmp_path):
    with pytest.raises(FileNotFoundError):
        polyxrd.build_sidecar(tmp_path / "nope.sqlite", tmp_path / "x.db")


def test_build_sidecar_cancel_leaves_no_output(pdf2_db, tmp_path):
    set_cancel_check(lambda: True)
    try:
        with pytest.raises(OperationCancelledError):
            polyxrd.build_sidecar(pdf2_db, tmp_path / "sidecar.db")
    finally:
        set_cancel_check(None)
    assert not (tmp_path / "sidecar.db").exists()
    assert not (tmp_path / "sidecar.db.tmp").exists()


# ---------------------------------------------------------------------------
# Cache freshness
# ---------------------------------------------------------------------------
def test_sidecar_freshness_and_reuse(pdf2_db, tmp_path):
    index_dir = tmp_path / "indexes"
    out, summary = polyxrd.ensure_sidecar(pdf2_db, index_dir=index_dir)
    assert summary is not None
    assert out.exists()
    assert polyxrd.sidecar_is_fresh(pdf2_db, out)

    again, summary2 = polyxrd.ensure_sidecar(pdf2_db, index_dir=index_dir)
    assert again == out
    assert summary2 is None  # cache hit

    # touching the source invalidates the cache (PolyXRD rebuilds its dumps)
    import os

    os.utime(pdf2_db, (0, 0))
    assert not polyxrd.sidecar_is_fresh(pdf2_db, out)
    _out3, summary3 = polyxrd.ensure_sidecar(pdf2_db, index_dir=index_dir)
    assert summary3 is not None


def test_sidecar_freshness_false_when_missing(pdf2_db, tmp_path):
    assert not polyxrd.sidecar_is_fresh(pdf2_db, tmp_path / "absent.db")


def test_sidecar_path_is_stable(pdf2_db, tmp_path):
    a = polyxrd.sidecar_path_for(pdf2_db, index_dir=tmp_path)
    b = polyxrd.sidecar_path_for(pdf2_db, index_dir=tmp_path)
    assert a == b
    assert a.parent == tmp_path
    assert a.suffix == ".db"
