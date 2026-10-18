"""GUI tests for mounting external databases in the library dialog (v2.0.0).

The dialog is the user-facing half of the feature: pick a ``.sqlite`` file from
any folder, get a progress bar while the PolyXRD dump is converted, and see the
mount survive in the picker.  Everything runs offscreen; the Qt thread is
pumped manually instead of using ``QTest.qWait``.
"""

from __future__ import annotations

import sqlite3
import time

import numpy as np
import pytest
from PySide6 import QtWidgets

from xinmatch.core.db import build_element_index, create_tables, insert_entries, multi_db
from xinmatch.core.model import Entry
from xinmatch.ui.dialogs import library_dialog as ld

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
    # Never touch the developer's real YAML config from a test.
    monkeypatch.setattr(ld, "load_config", lambda: {"reference_db": {}})
    monkeypatch.setattr(ld, "save_config", lambda cfg: None)
    return tmp_path


@pytest.fixture
def polyxrd_db(isolated_registry):
    path = isolated_registry / "mount_here" / "COD_inorganics.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(PDF2_TABLE)
    conn.executemany(
        "INSERT INTO phases VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (1, "PDF2-000001", "SiO2", "Quartz", "Quartz", "P3221", 4.913, 4.913,
             5.405, 90, 90, 120, 2, "4.26,3.34", "100,80"),
        ],
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def native_db(isolated_registry):
    path = isolated_registry / "native" / "lab6.sqlite"
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


def _wait_for_index(qapp, dialog: ld.LibraryDialog, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while dialog._index_thread is not None and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    qapp.processEvents()
    assert dialog._index_thread is None, "index thread did not finish"


def test_mount_native_library_is_instant(qapp, isolated_registry, native_db):
    dialog = ld.LibraryDialog()
    try:
        lib_id = dialog.add_external_path(str(native_db))
        assert lib_id is not None
        assert dialog._index_thread is None  # no conversion needed
        assert lib_id in dialog._ids
        record = multi_db.library_by_id(lib_id)
        assert record is not None and record.available and not record.needs_index
        assert record.display_name == "lab6"
    finally:
        dialog.close()


def test_mount_polyxrd_library_builds_index(qapp, isolated_registry, polyxrd_db):
    dialog = ld.LibraryDialog()
    try:
        lib_id = dialog.add_external_path(str(polyxrd_db))
        assert lib_id is not None
        assert dialog._index_thread is not None  # conversion started
        _wait_for_index(qapp, dialog)

        record = multi_db.library_by_id(lib_id)
        assert record is not None
        assert record.kind == multi_db.KIND_POLYXRD
        assert record.needs_index is False
        assert record.entry_count == 1  # one source phase
    finally:
        dialog.close()


def test_mount_rejects_unsupported_file(qapp, isolated_registry, tmp_path, monkeypatch):
    warnings: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "warning", lambda *a, **k: warnings.append(str(a[-1]))
    )
    junk = tmp_path / "junk.sqlite"
    junk.write_bytes(b"not a database at all")

    dialog = ld.LibraryDialog()
    try:
        assert dialog.add_external_path(str(junk)) is None
        assert warnings, "expected a warning message for an unsupported file"
        assert not [r for r in multi_db.list_libraries() if r.external]
    finally:
        dialog.close()


def test_remove_selected_external_library(qapp, isolated_registry, native_db, monkeypatch):
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "question",
        lambda *a, **k: QtWidgets.QMessageBox.StandardButton.Yes,
    )
    dialog = ld.LibraryDialog()
    try:
        lib_id = dialog.add_external_path(str(native_db))
        assert lib_id is not None
        dialog._select_id(lib_id)
        dialog._remove_selected_library()
        assert multi_db.library_by_id(lib_id) is None
        assert lib_id not in dialog._ids
    finally:
        dialog.close()


def test_builtin_library_cannot_be_removed(qapp, isolated_registry, monkeypatch):
    messages: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "information", lambda *a, **k: messages.append(str(a[-1]))
    )
    dialog = ld.LibraryDialog()
    try:
        dialog._select_id("cod_inorganics")
        dialog._remove_selected_library()
        assert messages, "expected an explanation for built-in libraries"
        assert multi_db.library_by_id("cod_inorganics") is not None
    finally:
        dialog.close()
