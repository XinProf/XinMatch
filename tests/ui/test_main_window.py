"""T13.1 — Main window skeleton: 15 modules reachable, docks in place."""

from __future__ import annotations

from PySide6 import QtWidgets

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
