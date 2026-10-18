"""Main-window integration for mounted PolyXRD libraries (v2.0.0).

First search on a freshly mounted PolyXRD database triggers a one-off
conversion.  That must happen inside the busy dialog (with a cancel button),
not on the GUI thread — this test drives the real
``MainWindow._open_library_with_index`` path with ``run_with_busy`` stubbed to
run inline, and verifies the second call hits the cache.
"""

from __future__ import annotations

import sqlite3

import pytest

from xinmatch.core.db import multi_db
from xinmatch.core.search.search_match import fetch_entries_by_ids
from xinmatch.ui import main_window as mw

PDF2_TABLE = (
    "CREATE TABLE phases (cod_id INTEGER, ref_id TEXT, formula TEXT, name TEXT,"
    " mineral TEXT, space_group TEXT, cell_a REAL, cell_b REAL, cell_c REAL,"
    " cell_alpha REAL, cell_beta REAL, cell_gamma REAL, n_peaks INTEGER,"
    " peaks_d TEXT, peaks_i TEXT)"
)


@pytest.fixture
def isolated_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("XINMATCH_USER_DATA", str(tmp_path / "userdata"))
    monkeypatch.setenv("XINMATCH_LIBRARIES_JSON", str(tmp_path / "libraries.json"))
    return tmp_path


@pytest.fixture
def polyxrd_db(isolated_registry):
    path = isolated_registry / "mounted" / "PDF2_2004.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(PDF2_TABLE)
    conn.executemany(
        "INSERT INTO phases VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (1, "PDF2-000001", "SiO2", "Quartz", "Quartz", "P3221", 4.913, 4.913,
             5.405, 90, 90, 120, 2, "4.26,3.34", "100,80"),
            (2, "PDF2-000009", "Al2O3", "Corundum", "Corundum", "R-3c", 4.759,
             4.759, 12.99, 90, 90, 120, 2, "2.55,2.09", "100,60"),
        ],
    )
    conn.commit()
    conn.close()
    return path


def test_open_library_builds_index_in_busy_dialog(
    qapp, isolated_registry, polyxrd_db, monkeypatch
):
    busy_titles: list[str] = []

    def fake_busy(parent, title, message, work, *, on_success=None, on_error=None):
        busy_titles.append(title)
        result = work()  # run inline (the real dialog uses a QThread)
        if on_success is not None:
            on_success(result)
        return True

    monkeypatch.setattr(mw, "run_with_busy", fake_busy)
    ext = multi_db.add_external_library(polyxrd_db)

    win = mw.MainWindow()
    try:
        conn = win._open_library_with_index(ext.id)
        try:
            assert fetch_entries_by_ids(conn, ["PDF2-000001"])[0].formula == "SiO2"
        finally:
            conn.close()
        assert busy_titles == ["建立检索索引"]

        # Second open: the sidecar is fresh, so no extra conversion dialog.
        conn = win._open_library_with_index(ext.id)
        conn.close()
        assert busy_titles == ["建立检索索引"]
        assert multi_db.library_by_id(ext.id).needs_index is False  # type: ignore[union-attr]
    finally:
        win.close()


def test_open_library_without_index_raises_for_callers_that_skip_ui(
    qapp, isolated_registry, polyxrd_db
):
    """Core contract: ``open_library`` itself never converts silently."""
    ext = multi_db.add_external_library(polyxrd_db)
    with pytest.raises(multi_db.LibraryNeedsIndexError):
        multi_db.open_library(ext.id)
