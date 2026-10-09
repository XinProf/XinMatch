"""T13.1 — Main window skeleton: 15 modules reachable, docks in place."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
from PySide6 import QtWidgets

import xinmatch
from xinmatch.core.model.entry import CellParams, Entry
from xinmatch.core.model.pattern import Pattern
from xinmatch.core.search.fom import CandidateResult
from xinmatch.ui.main_window import MODULES, MainWindow
from xinmatch.ui.pattern_view import PatternView


def test_window_constructs(qapp):
    win = MainWindow()
    assert win.windowTitle()


def test_all_fifteen_modules_have_actions(qapp):
    win = MainWindow()
    expected = {mod_id for mod_id, _, _ in MODULES}
    assert len(expected) == 15
    assert set(win.module_actions) == expected


def test_every_module_action_appears_in_a_menu(qapp):
    win = MainWindow()
    menu_actions: set[QtWidgets.QAction] = set()
    for menu in win.menuBar().findChildren(QtWidgets.QMenu):
        menu_actions.update(menu.actions())
    for action in win.module_actions.values():
        assert action in menu_actions, f"module action {action.text()} missing from menus"


def test_placeholder_action_writes_status_bar(qapp):
    win = MainWindow()
    win.show()
    win.module_actions["search_match"].trigger()
    assert "Search-Match" in win.statusBar().currentMessage()


def test_dock_panels_present(qapp):
    win = MainWindow()
    names = {d.objectName() for d in win.findChildren(QtWidgets.QDockWidget)}
    assert {"candidateDock", "rightDock", "matchDock"} <= names


def test_central_widget_is_pattern_view(qapp):
    win = MainWindow()
    assert isinstance(win.centralWidget(), PatternView)


# ---------------------------------------------------------------------------
# T13.8 refinement-wizard wiring / Phase 16 3D view / About / icon
# ---------------------------------------------------------------------------
def _cand(entry_id: str) -> CandidateResult:
    return CandidateResult(
        entry=Entry(
            entry_id=entry_id, formula="X",
            d_spacings=np.array([2.5]), intensities=np.array([100.0]),
            cell=CellParams(3.0, 3.0, 5.0),
        ),
        fom=0.9,
    )


def test_refinement_wizard_and_3d_view_actions_present(qapp):
    win = MainWindow()
    assert hasattr(win, "refinement_wizard_action")
    assert hasattr(win, "structure_view_action")
    assert win.refinement_wizard_action.shortcut().toString() == "Ctrl+Shift+W"
    assert win.structure_view_action.shortcut().toString() == "Ctrl+Shift+V"
    # Both appear in some menu.
    menu_actions = set()
    for menu in win.menuBar().findChildren(QtWidgets.QMenu):
        menu_actions.update(menu.actions())
    assert win.refinement_wizard_action in menu_actions
    assert win.structure_view_action in menu_actions


def test_open_wizard_without_candidates_informs_not_crashes(qapp):
    win = MainWindow()
    with patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
        win._open_refinement_wizard()
    mock_info.assert_called()  # friendly message, no crash


def test_open_structure_view_without_candidates_informs(qapp):
    win = MainWindow()
    with patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
        win._open_structure_view()
    mock_info.assert_called()


def test_set_candidates_and_pattern_store_state(qapp):
    win = MainWindow()
    win.set_candidates([_cand("96-100-0005")])
    assert len(win._candidates) == 1
    win.set_pattern(Pattern(np.linspace(10, 80, 50), np.ones(50)))
    assert win._current_pattern is not None


def test_about_dialog_dynamic_version(qapp):
    win = MainWindow()
    with patch("PySide6.QtWidgets.QMessageBox.about") as mock_about:
        win._open_about()
    assert mock_about.called
    # Version string shown must equal the live package version, never hardcoded.
    text = mock_about.call_args[0][2]
    assert xinmatch.__version__ in text


def test_window_icon_set_when_asset_exists(qapp):
    from xinmatch.ui.main_window import _asset_path
    win = MainWindow()
    if _asset_path("logo.png").is_file():
        assert not win.windowIcon().isNull()
