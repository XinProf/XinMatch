"""集成测试：T13.3–T13.7 新控件挂载进 MainWindow。

Organizer 集成层验收：
* 三个表格（候选/峰/匹配）与周期表确实进入对应 dock；
* 快捷键全量注册到主窗口（T13.6）；
* 默认浅色主题生效、可切换（T13.7）；
* 选项对话框经配置持久化打开并写回（T13.5）。
"""

from __future__ import annotations

from PySide6 import QtGui, QtWidgets

from xinmatch.ui.main_window import MainWindow
from xinmatch.ui.periodic_table import PeriodicTablePanel
from xinmatch.ui.tables import CandidateListTable, MatchListTable, PeakListTable
from xinmatch.ui.theme import current_theme


def test_docks_host_new_tables(qapp):
    win = MainWindow()
    assert isinstance(win.candidate_table, CandidateListTable)
    assert isinstance(win.peak_table, PeakListTable)
    assert isinstance(win.match_table, MatchListTable)
    # v1.3.1：周期表改弹出式选择面板（PeriodicTablePanel），省空间给谱图。
    assert isinstance(win.periodic_panel, PeriodicTablePanel)
    # 表格确实在 dock 内（findChild 从主窗口命中同一实例）。
    assert win.findChild(CandidateListTable) is win.candidate_table
    assert win.findChild(PeakListTable) is win.peak_table
    assert win.findChild(MatchListTable) is win.match_table


def test_periodic_table_in_restraints_tab(qapp):
    win = MainWindow()
    tabs = win.findChild(QtWidgets.QTabWidget)
    assert tabs is not None
    assert tabs.indexOf(win.periodic_panel) == 0
    assert tabs.indexOf(win.peak_table) == 1


def test_shortcuts_installed_on_main_window(qapp):
    win = MainWindow()
    assert win.shortcuts
    # 全部快捷键以 QAction + WindowShortcut 形式挂在窗口上。
    actions = win.findChildren(QtGui.QAction)
    with_shortcut = [
        a for a in actions
        if a.shortcut() is not None and not a.shortcut().isEmpty()
    ]
    assert len(with_shortcut) >= len(win.shortcuts)


def test_default_theme_light_applied(qapp):
    MainWindow()
    assert current_theme() == "light"


def test_theme_toggle_switches_dark_and_back(qapp):
    win = MainWindow()
    win._toggle_theme()
    assert current_theme() == "dark"
    assert "dark" in win._theme_action.text()
    win._toggle_theme()
    assert current_theme() == "light"


def test_options_action_opens_dialog_and_persists(qapp, monkeypatch, tmp_path):
    from xinmatch.ui.dialogs import config as dcfg

    monkeypatch.setattr(dcfg, "config_path", lambda: tmp_path / "xinmatch.yaml")
    captured: dict = {}

    class _FakeOptionsDialog:
        def __init__(self, cfg, parent):
            captured["cfg"] = cfg

        def exec(self):
            return 1

        def values(self):
            return {"general": {"language": "zh"}}

    monkeypatch.setattr("xinmatch.ui.main_window.OptionsDialog", _FakeOptionsDialog)
    win = MainWindow()
    win._open_options_dialog()
    assert captured["cfg"] is not None
    assert (tmp_path / "xinmatch.yaml").exists()
    # 写回后可读回（持久化闭环）。
    saved = dcfg.load_config()
    assert saved["general"]["language"] == "zh"
