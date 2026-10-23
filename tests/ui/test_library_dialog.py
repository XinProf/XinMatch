"""Reference-library picker (v3.0.0: ``.xinDB`` only) — dialog + fallback wiring.

Covers:
* the picker lists every registry library with display name / count / path /
  availability, and marks the default one;
* the chosen library id round-trips through the YAML config;
* unavailable libraries are greyed out, carry their friendly reason and are
  not selectable; a saved-but-unavailable selection falls back to the default;
* ``MainWindow.open_search_library`` falls back to the default library (and
  warns) when the configured library cannot be opened.

The dialog is driven with synthetic :class:`LibraryRecord` objects so the test
does not depend on the 1.8 GiB ``.xinDB`` files being present; the fallback
test stubs ``resolve_default`` for the same reason.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore, QtWidgets

from xinmatch.core.db import multi_db
from xinmatch.core.db.multi_db import (
    DEFAULT_LIBRARY_ID,
    KIND_XINDB,
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

COD_FULL = "xindb_cod_full"
COD_INORG = DEFAULT_LIBRARY_ID


def _available(lib_id: str, *, default: bool = False) -> LibraryRecord:
    return LibraryRecord(
        id=lib_id,
        display_name="COD Inorganics（默认）" if default else "COD Full",
        kind=KIND_XINDB,
        path=Path(f"data/{lib_id}.xinDB"),
        entry_count=78_036 if default else 521_361,
        available=True,
        note="v3 列存库（只读）",
        default=default,
    )


def _missing(lib_id: str, reason: str = "未找到库文件") -> LibraryRecord:
    return LibraryRecord(
        id=lib_id,
        display_name="COD Full",
        kind=KIND_XINDB,
        path=Path(f"data/{lib_id}.xinDB"),
        available=False,
        unavailable_reason=reason,
        note="尚未构建该库",
    )


# ---------------------------------------------------------------------------
# Picker dialog
# ---------------------------------------------------------------------------
def test_dialog_lists_all_registry_libraries(qapp):
    """The live registry's built-in rows all show up as table rows."""
    expected = {rec.id for rec in list_libraries()}
    assert COD_INORG in expected  # 默认库永远在列表里（不可用也列出来）
    dialog = LibraryDialog()
    assert dialog._table.rowCount() == len(expected)
    assert set(dialog._ids) == expected


def test_default_row_is_marked_and_preselected(qapp):
    dialog = LibraryDialog(libraries=[_available(COD_INORG, default=True)])
    assert dialog._table.item(0, 3).text() == "默认库"
    assert dialog.selected_id() == COD_INORG
    assert dialog.selected_record().default is True


def test_unavailable_row_shows_reason_and_is_not_selectable(qapp):
    ghost = _missing(COD_FULL, "尚未构建该库")
    ok = _available(COD_INORG, default=True)
    dialog = LibraryDialog(current_id=COD_FULL, libraries=[ghost, ok])

    assert dialog._table.rowCount() == 2
    status = dialog._table.item(0, 3)
    assert "不可用" in status.text()
    assert "尚未构建该库" in status.text()
    # The ghost row cannot be selected.
    assert not (status.flags() & QtCore.Qt.ItemFlag.ItemIsSelectable)
    # Selection falls back to the available (default) library.
    assert dialog.selected_id() == COD_INORG


def test_unavailable_saved_selection_falls_back_to_first_available(qapp):
    # Saved config points at an unbuilt library: the dialog must not crash and
    # must pre-select an available library instead.
    dialog = LibraryDialog(
        current_id=COD_FULL,
        libraries=[_missing(COD_FULL), _available(COD_INORG, default=True)],
    )
    assert dialog.selected_id() == COD_INORG


def test_available_saved_selection_is_kept(qapp):
    dialog = LibraryDialog(
        current_id=COD_FULL,
        libraries=[_available(COD_INORG, default=True), _available(COD_FULL)],
    )
    assert dialog.selected_id() == COD_FULL


def test_selection_roundtrips_through_yaml(tmp_path: Path, qapp):
    dialog = LibraryDialog(current_id=COD_INORG, libraries=[_available(COD_INORG, default=True)])
    chosen = dialog.selected_id()
    cfg = default_config()
    cfg["reference_db"]["selected_library_id"] = chosen
    target = tmp_path / "xinmatch.yaml"
    save_config(cfg, target)
    loaded = load_config(target)
    assert loaded["reference_db"]["selected_library_id"] == chosen
    # Untouched defaults still merged in.
    assert loaded["searchmatch"]["min_fom"] == pytest.approx(0.6)


def test_config_default_points_at_the_inorganic_library():
    cfg = default_config()
    assert cfg["reference_db"]["selected_library_id"] == COD_INORG
    # v3.0.0 removed the PDF-2 source directory knob entirely.
    assert "pdf2_source_dir" not in cfg["reference_db"]


# ---------------------------------------------------------------------------
# Main-window wiring: fallback when the chosen library cannot be opened
# ---------------------------------------------------------------------------
def _patch_open(monkeypatch, opened: list[str], behaviour) -> None:
    def fake_open(library_id: str):
        opened.append(library_id)
        return behaviour(library_id)

    monkeypatch.setattr(mw, "open_library", fake_open)


def test_open_search_library_uses_selected_when_available(qapp, monkeypatch):
    win = MainWindow()
    monkeypatch.setattr(
        mw,
        "load_config",
        lambda *a, **k: {"reference_db": {"selected_library_id": COD_FULL}},
    )
    reader = MagicMock(name="xindb-reader")
    opened: list[str] = []
    _patch_open(monkeypatch, opened, lambda _lib_id: reader)

    with patch("PySide6.QtWidgets.QMessageBox.warning") as warn:
        conn = win.open_search_library()

    assert conn is reader
    assert opened == [COD_FULL]
    assert warn.called is False
    assert win._active_library_id == COD_FULL


def test_open_search_library_falls_back_to_default_with_warning(qapp, monkeypatch):
    win = MainWindow()
    monkeypatch.setattr(
        mw,
        "load_config",
        lambda *a, **k: {"reference_db": {"selected_library_id": COD_FULL}},
    )
    monkeypatch.setattr(mw, "resolve_default", lambda: _available(COD_INORG, default=True))

    default_reader = MagicMock(name="default-reader")
    opened: list[str] = []

    def behaviour(library_id: str):
        if library_id == COD_FULL:
            raise LibraryNotAvailableError(
                f"library {COD_FULL!r} is not available: 尚未构建该库"
            )
        return default_reader

    _patch_open(monkeypatch, opened, behaviour)

    with patch("PySide6.QtWidgets.QMessageBox.warning") as warn:
        conn = win.open_search_library()

    assert conn is default_reader
    assert opened == [COD_FULL, COD_INORG]  # fallback target = 默认库
    assert warn.called
    text = warn.call_args.args[-1]
    assert "尚未构建该库" in text  # friendly reason surfaced to the user
    assert win._active_library_id == COD_INORG


def test_open_search_library_without_saved_selection_uses_default(qapp, monkeypatch):
    win = MainWindow()
    monkeypatch.setattr(mw, "load_config", lambda *a, **k: {})
    monkeypatch.setattr(mw, "resolve_default", lambda: _available(COD_INORG, default=True))
    reader = MagicMock(name="reader")
    opened: list[str] = []
    _patch_open(monkeypatch, opened, lambda _lib_id: reader)

    with patch("PySide6.QtWidgets.QMessageBox.warning") as warn:
        conn = win.open_search_library()

    assert conn is reader
    assert opened == [COD_INORG]
    assert warn.called is False


def test_open_search_library_raises_when_everything_is_broken(qapp, monkeypatch):
    win = MainWindow()
    monkeypatch.setattr(
        mw,
        "load_config",
        lambda *a, **k: {"reference_db": {"selected_library_id": COD_FULL}},
    )
    monkeypatch.setattr(mw, "resolve_default", lambda: _available(COD_INORG, default=True))

    def behaviour(library_id: str):
        raise LibraryNotAvailableError(f"{library_id} is not available")

    opened: list[str] = []
    _patch_open(monkeypatch, opened, behaviour)

    with patch("PySide6.QtWidgets.QMessageBox.warning"), patch(
        "PySide6.QtWidgets.QMessageBox.critical"
    ) as critical:
        with pytest.raises(LibraryNotAvailableError):
            win.open_search_library()

    assert opened == [COD_FULL, COD_INORG]
    assert critical.called


def test_library_dialog_action_wired_in_settings_menu(qapp):
    win = MainWindow()
    assert hasattr(win, "library_action")
    menu_actions = set()
    for menu in win.menuBar().findChildren(QtWidgets.QMenu):
        menu_actions.update(menu.actions())
    assert win.library_action in menu_actions


def test_multi_db_has_no_legacy_kind_names():
    """v3.0.0 的注册表模块里不该再出现旧格式的 kind 名字。"""
    for legacy in ("KIND_XINMATCH", "KIND_PDF2", "KIND_POLYXRD", "KIND_COD_FULL"):
        assert not hasattr(multi_db, legacy)
