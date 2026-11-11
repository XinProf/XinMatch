"""T13.1 — Main window skeleton: 15 modules reachable, docks in place."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
from PySide6 import QtWidgets

from xinmatch.core.model.entry import CellParams, Entry
from xinmatch.core.model.pattern import Pattern
from xinmatch.core.search.fom import CandidateResult
from xinmatch.ui.main_window import MODULES, MainWindow
from xinmatch.ui.pattern_view import PatternPanel, PatternView


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


def test_user_db_action_opens_dialog(qapp, monkeypatch):
    # 2026-11-11：用户数据库接通后，15 个模块动作**全部**有了真实入口，
    # 原先"改测仍为占位的模块"的用例已无对象 —— 改钉接线本身。
    win = MainWindow()
    calls: list[bool] = []
    monkeypatch.setattr(win, "_open_user_db_dialog", lambda: calls.append(True))
    win.module_actions["user_db"].trigger()
    assert calls == [True]


def test_dock_panels_present(qapp):
    win = MainWindow()
    names = {d.objectName() for d in win.findChildren(QtWidgets.QDockWidget)}
    assert {"candidateDock", "rightDock", "matchDock"} <= names


def test_central_widget_is_pattern_view(qapp):
    # v1.3.1：中央控件为 PatternPanel（轴切换控制条 + 谱图视图）。
    win = MainWindow()
    assert isinstance(win.centralWidget(), PatternPanel)
    assert isinstance(win.pattern_view, PatternView)


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
    instances = []

    class FakeAbout:
        def __init__(self, *args, **kwargs):
            instances.append(self)

        def exec(self):
            return 0

    with patch("xinmatch.ui.main_window.AboutDialog", FakeAbout):
        win._open_about()
    # About 对话框被实例化并展示；版本语义由 AboutDialog 内部动态读取保证。
    assert len(instances) == 1


def test_window_icon_set_when_asset_exists(qapp):
    from xinmatch.ui.main_window import _asset_path
    win = MainWindow()
    if _asset_path("logo.png").is_file():
        assert not win.windowIcon().isNull()


def test_about_in_help_menu_not_settings(qapp):
    """关于 XinMatch… 位于独立"帮助"菜单，不在"设置"菜单中。"""
    win = MainWindow()
    settings_menu = next(
        m for m in win.menuBar().findChildren(QtWidgets.QMenu)
        if m.title() == "设置(&O)"
    )
    assert win.about_action not in settings_menu.actions()
    help_menu = next(
        m for m in win.menuBar().findChildren(QtWidgets.QMenu)
        if m.title() == "帮助(&H)"
    )
    assert win.about_action in help_menu.actions()


def test_toolbar_processing_actions_present(qapp):
    """工具栏补齐：背景扣除/平滑/Kα2 剥离/重置/峰检测/COD 搜索/精修向导。"""
    win = MainWindow()
    for attr in (
        "background_action", "smooth_action", "ko2_action",
        "reset_action", "peakdetect_action", "codsearch_action",
    ):
        action = getattr(win, attr)
        assert action.text(), f"{attr} must have a label"
        assert not action.icon().isNull(), f"{attr} must have an icon"
    assert win.refinement_wizard_action in win.findChildren(QtWidgets.QToolBar)[0].actions()


def test_codsearch_action_opens_library_dialog(qapp):
    """COD 搜索动作触发库选择对话框（不崩溃）。"""
    win = MainWindow()
    with patch.object(win, "_open_library_dialog") as mock_open:
        win.codsearch_action.trigger()
    mock_open.assert_called_once()
