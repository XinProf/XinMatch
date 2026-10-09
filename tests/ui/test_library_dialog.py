"""Multi-library mount — GUI picker dialog + search fallback wiring (offscreen).

Covers:
* the picker lists every registry library with display name / count / path /
  availability;
* the chosen library id round-trips through the YAML config;
* unavailable libraries are greyed out, carry their friendly reason and are
  not selectable;
* ``MainWindow.open_search_library`` falls back to the default library (and
  warns) when the configured library cannot be opened.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore, QtWidgets

from xinmatch.core.db.multi_db import (
    KIND_XINMATCH,
    LibraryNotAvailableError,
    LibraryRecord,
    list_libraries,
)
from xinmatch.ui import main_window as mw
from xinmatch.ui.dialogs import (
    LibraryDialog,
    default_config,
    load_config,
    save_config,
)
from xinmatch.ui.main_window import MainWindow


# ---------------------------------------------------------------------------
# Picker dialog
# ---------------------------------------------------------------------------
def test_dialog_lists_all_registry_libraries(qapp):
    """The live registry's three libraries show up as three table rows."""
    expected = {rec.id for rec in list_libraries()}
    dialog = LibraryDialog()
    assert dialog._table.rowCount() == len(expected)
    assert set(dialog._ids) == expected


def test_unavailable_row_shows_reason_and_is_not_selectable(qapp):
    ghost = LibraryRecord(
        id="cod_full",
        display_name="COD full database",
        kind="cod_full",
        path=Path("data/cod_full.db"),
        entry_count=300,
        available=False,
        unavailable_reason="not built yet; run tools.build_cod_full_xinmatch",
        note="built from the 522k-CIF archive",
    )
    ok = LibraryRecord(
        id="cod_inorganics",
        display_name="COD Inorganics (default, bundled)",
        kind=KIND_XINMATCH,
        path=Path("data/cod_inorganics.db"),
        entry_count=71199,
        available=True,
        note="shipped with XinMatch",
    )
    dialog = LibraryDialog(current_id="cod_inorganics", libraries=[ghost, ok])

    assert dialog._table.rowCount() == 2
    status = dialog._table.item(0, 3)
    assert "not built yet" in status.text()
    # The ghost row cannot be selected.
    assert not (status.flags() & QtCore.Qt.ItemFlag.ItemIsSelectable)
    # Selection falls back to the available library.
    assert dialog.selected_id() == "cod_inorganics"


def test_unavailable_saved_selection_falls_back_to_first_available(qapp):
    ghost = LibraryRecord(
        id="cod_full",
        display_name="COD full database",
        kind="cod_full",
        path=Path("data/cod_full.db"),
        available=False,
        unavailable_reason="not built yet",
    )
    ok = LibraryRecord(
        id="cod_inorganics",
        display_name="COD Inorganics (default, bundled)",
        kind=KIND_XINMATCH,
        path=Path("data/cod_inorganics.db"),
        available=True,
    )
    # Saved config points at the unbuilt library: dialog must not crash and
    # must pre-select an available library instead.
    dialog = LibraryDialog(current_id="cod_full", libraries=[ghost, ok])
    assert dialog.selected_id() == "cod_inorganics"


def test_selection_roundtrips_through_yaml(tmp_path: Path, qapp):
    dialog = LibraryDialog(current_id="cod_inorganics")
    chosen = dialog.selected_id()
    cfg = default_config()
    cfg["reference_db"]["selected_library_id"] = chosen
    target = tmp_path / "xinmatch.yaml"
    save_config(cfg, target)
    loaded = load_config(target)
    assert loaded["reference_db"]["selected_library_id"] == chosen
    # Untouched defaults still merged in.
    assert loaded["searchmatch"]["min_fom"] == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# Main-window wiring: fallback when the chosen library cannot be opened
# ---------------------------------------------------------------------------
def test_open_search_library_uses_selected_when_available(qapp, monkeypatch):
    win = MainWindow()
    monkeypatch.setattr(
        mw, "load_config",
        lambda *a, **k: {"reference_db": {"selected_library_id": "pdf2_2004"}},
    )
    fake_conn = MagicMock(name="pdf2-conn")
    opened: list[str] = []

    def fake_open(library_id: str):
        opened.append(library_id)
        return fake_conn

    monkeypatch.setattr(mw, "open_library", fake_open)
    with patch("PySide6.QtWidgets.QMessageBox.warning") as warn:
        conn = win.open_search_library()
    assert conn is fake_conn
    assert opened == ["pdf2_2004"]
    assert warn.called is False
    assert win._active_library_id == "pdf2_2004"


def test_open_search_library_falls_back_to_default_with_warning(qapp, monkeypatch):
    win = MainWindow()
    monkeypatch.setattr(
        mw, "load_config",
        lambda *a, **k: {"reference_db": {"selected_library_id": "cod_full"}},
    )
    default_conn = MagicMock(name="default-conn")
    opened: list[str] = []

    def fake_open(library_id: str):
        opened.append(library_id)
        if library_id == "cod_full":
            raise LibraryNotAvailableError(
                "library 'cod_full' is not available: not built yet"
            )
        assert library_id == "cod_inorganics"  # fallback target
        return default_conn

    monkeypatch.setattr(mw, "open_library", fake_open)
    with patch("PySide6.QtWidgets.QMessageBox.warning") as warn:
        conn = win.open_search_library()

    assert conn is default_conn
    assert opened == ["cod_full", "cod_inorganics"]
    assert warn.called
    text = warn.call_args.args[-1]
    assert "not built yet" in text  # friendly reason surfaced to the user
    assert win._active_library_id == "cod_inorganics"


def test_library_dialog_action_wired_in_settings_menu(qapp):
    win = MainWindow()
    assert hasattr(win, "library_action")
    menu_actions = set()
    for menu in win.menuBar().findChildren(QtWidgets.QMenu):
        menu_actions.update(menu.actions())
    assert win.library_action in menu_actions
