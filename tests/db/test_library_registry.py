"""Tests for the external-library registry (v2.0.0).

A mounted database lives **anywhere** on disk; the registry only remembers the
path (``<user-data>/libraries.json``) so the mount survives restarts without
copying gigabytes next to the executable.
"""

from __future__ import annotations

import json
import sqlite3

import numpy as np
import pytest

from xinmatch.core.db import build_element_index, create_tables, insert_entries, multi_db, polyxrd
from xinmatch.core.model import Entry
from xinmatch.core.search.search_match import fetch_entries_by_ids

PDF2_TABLE = (
    "CREATE TABLE phases (cod_id INTEGER, ref_id TEXT, formula TEXT, name TEXT,"
    " mineral TEXT, space_group TEXT, cell_a REAL, cell_b REAL, cell_c REAL,"
    " cell_alpha REAL, cell_beta REAL, cell_gamma REAL, n_peaks INTEGER,"
    " peaks_d TEXT, peaks_i TEXT)"
)


@pytest.fixture
def isolated_registry(tmp_path, monkeypatch):
    """Point the registry and the sidecar cache at a throw-away directory."""
    monkeypatch.setenv("XINMATCH_USER_DATA", str(tmp_path / "userdata"))
    monkeypatch.setenv("XINMATCH_LIBRARIES_JSON", str(tmp_path / "libraries.json"))
    return tmp_path


@pytest.fixture
def pdf2_db(isolated_registry):
    path = isolated_registry / "some_other_folder" / "PDF2_2004.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(PDF2_TABLE)
    conn.executemany(
        "INSERT INTO phases VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (1, "PDF2-000001", "SiO2", "Quartz", "Quartz", "P3221", 4.913, 4.913,
             5.405, 90, 90, 120, 2, "4.26,3.34", "100,80"),
            (2, "PDF2-000002", "Al2O3", "Corundum", "Corundum", "R-3c", 4.759,
             4.759, 12.99, 90, 90, 120, 2, "2.55,2.09", "100,60"),
        ],
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def native_db(isolated_registry):
    path = isolated_registry / "elsewhere" / "native.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    create_tables(conn)
    insert_entries(
        conn,
        [
            Entry(
                entry_id="N-1",
                formula="LaB6",
                d_spacings=np.array([4.157, 2.937]),
                intensities=np.array([100.0, 45.0]),
            )
        ],
    )
    build_element_index(conn)
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def structure_only_db(isolated_registry):
    path = isolated_registry / "cod_index.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE cod_entries (cod_id INTEGER, formula TEXT)")
    conn.execute("INSERT INTO cod_entries VALUES (1, 'C')")
    conn.commit()
    conn.close()
    return path


# ---------------------------------------------------------------------------
# Registry persistence
# ---------------------------------------------------------------------------
def test_add_native_library_is_immediately_searchable(native_db):
    ext = multi_db.add_external_library(native_db, label="My LaB6")
    assert ext.id.startswith("ext_")
    assert ext.display_name == "My LaB6"

    record = multi_db.library_by_id(ext.id)
    assert record is not None
    assert record.external and record.available and not record.needs_index
    assert record.kind == multi_db.KIND_XINMATCH
    assert record.entry_count == 1

    conn = multi_db.open_library(ext.id)
    try:
        assert fetch_entries_by_ids(conn, ["N-1"])[0].formula == "LaB6"
    finally:
        conn.close()


def test_add_is_idempotent_and_updates_label(pdf2_db):
    first = multi_db.add_external_library(pdf2_db)
    second = multi_db.add_external_library(pdf2_db, label="Renamed")
    assert first.id == second.id
    libs = [lib for lib in multi_db.load_external_libraries() if lib.id == first.id]
    assert len(libs) == 1
    assert libs[0].label == "Renamed"


def test_registry_survives_reload(pdf2_db):
    ext = multi_db.add_external_library(pdf2_db)
    raw = json.loads(multi_db.library_registry_path().read_text(encoding="utf-8"))
    assert raw["version"] >= 1
    assert raw["libraries"][0]["id"] == ext.id
    assert raw["libraries"][0]["path"] == str(pdf2_db.resolve())

    reloaded = multi_db.load_external_libraries()
    assert [lib.id for lib in reloaded] == [ext.id]


def test_corrupt_registry_is_tolerated(isolated_registry):
    path = multi_db.library_registry_path()
    path.write_text("{not json", encoding="utf-8")
    assert multi_db.load_external_libraries() == []
    assert multi_db.library_by_id("cod_inorganics") is not None  # built-ins intact


def test_remove_library(pdf2_db):
    ext = multi_db.add_external_library(pdf2_db)
    assert multi_db.remove_external_library(ext.id) is True
    assert multi_db.remove_external_library(ext.id) is False
    assert multi_db.library_by_id(ext.id) is None
    assert all(not r.external for r in multi_db.list_libraries())


def test_add_rejects_unsupported_and_missing(structure_only_db, isolated_registry):
    with pytest.raises(ValueError, match="structures only|no peak"):
        multi_db.add_external_library(structure_only_db)
    with pytest.raises(FileNotFoundError):
        multi_db.add_external_library(isolated_registry / "nope.sqlite")


# ---------------------------------------------------------------------------
# PolyXRD mount → index → search
# ---------------------------------------------------------------------------
def test_polyxrd_mount_requires_index_then_works(pdf2_db):
    ext = multi_db.add_external_library(pdf2_db, label="PDF-2")
    record = multi_db.library_by_id(ext.id)
    assert record is not None
    assert record.kind == multi_db.KIND_POLYXRD
    assert record.needs_index is True
    assert record.entry_count == 2  # estimated from the source
    assert record.sidecar is not None

    with pytest.raises(multi_db.LibraryNeedsIndexError) as excinfo:
        multi_db.open_library(ext.id)
    assert excinfo.value.source == pdf2_db.resolve()

    summary = multi_db.ensure_library_index(ext.id)
    assert summary is not None
    assert summary["entries_indexed"] == 2

    record = multi_db.library_by_id(ext.id)
    assert record is not None and not record.needs_index

    conn = multi_db.open_library(ext.id)
    try:
        entry = fetch_entries_by_ids(conn, ["PDF2-000001"])[0]
        assert entry.formula == "SiO2"
        assert entry.mineral_name == "Quartz"
        assert entry.space_group == "P3221"
        assert entry.n_peaks == 2
    finally:
        conn.close()

    # second call is a cache hit
    assert multi_db.ensure_library_index(ext.id) is None


def test_ensure_library_index_force_rebuilds(pdf2_db):
    ext = multi_db.add_external_library(pdf2_db)
    multi_db.ensure_library_index(ext.id)
    assert multi_db.ensure_library_index(ext.id, force=True) is not None


def test_ensure_library_index_noop_for_native(native_db):
    ext = multi_db.add_external_library(native_db)
    assert multi_db.ensure_library_index(ext.id) is None


def test_ensure_library_index_unknown_id():
    with pytest.raises(multi_db.LibraryNotAvailableError):
        multi_db.ensure_library_index("ext_doesnotexist")


# ---------------------------------------------------------------------------
# open_search_database (CLI / batch convenience)
# ---------------------------------------------------------------------------
def test_open_search_database_converts_unregistered_path(pdf2_db):
    conn = multi_db.open_search_database(pdf2_db)
    try:
        assert fetch_entries_by_ids(conn, ["PDF2-000002"])[0].formula == "Al2O3"
    finally:
        conn.close()
    assert polyxrd.sidecar_is_fresh(pdf2_db)


def test_open_search_database_without_build(pdf2_db):
    with pytest.raises(multi_db.LibraryNeedsIndexError):
        multi_db.open_search_database(pdf2_db, build_index=False)


def test_open_search_database_native_and_errors(native_db, structure_only_db, tmp_path):
    conn = multi_db.open_search_database(native_db)
    try:
        assert fetch_entries_by_ids(conn, ["N-1"])
    finally:
        conn.close()

    with pytest.raises(multi_db.LibraryNotAvailableError):
        multi_db.open_search_database(structure_only_db)
    with pytest.raises(FileNotFoundError):
        multi_db.open_search_database(tmp_path / "absent.db")


# ---------------------------------------------------------------------------
# .sqlite extension support for built-in locations
# ---------------------------------------------------------------------------
def test_with_sqlite_fallback(tmp_path):
    base = tmp_path / "cod_inorganics.db"
    alt = tmp_path / "cod_inorganics.sqlite"
    assert multi_db._with_sqlite_fallback(base) == base  # neither exists
    alt.write_bytes(b"")
    assert multi_db._with_sqlite_fallback(base) == alt
    base.write_bytes(b"")
    assert multi_db._with_sqlite_fallback(base) == base  # .db wins when both
