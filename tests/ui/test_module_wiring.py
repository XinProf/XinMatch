"""批次 1 接线 —— 五个占位模块动作接到既有能力的单测。

HANDOVER §7.2 P2「GUI 剩余向导 / 主题」拆解后的第一批：不改任何 core 能力，
只把菜单/工具栏里仍是 `_placeholder` 的模块动作接到已经存在的入口：

* ``data_import``    → ``_open_data_file``（与工具栏「打开数据…」Ctrl+O 同槽）；
* ``raw_processing`` → 聚合菜单（背景扣除 / 平滑 / Kα2 剥离 / 重置，无新逻辑）；
* ``peak_list``      → ``_detect_peaks``（与工具栏「峰检测」同槽）；
* ``restraints``     → ``_focus_restraints``（右侧坞的限制条件页翻到最前）；
* ``rietveld``       → ``_open_refinement_wizard``（与精修向导 Ctrl+Shift+W 同槽）。

仍占位：``data_export`` / ``user_db`` / ``indexing`` / ``quant_analysis`` /
``microstructure``（批次 2+）。
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from xinmatch.ui.main_window import MainWindow  # noqa: E402


def _trigger(win, mod_id: str) -> None:
    win.module_actions[mod_id].trigger()


def test_data_import_opens_data_file(qapp, monkeypatch):
    win = MainWindow()
    calls: list[bool] = []
    monkeypatch.setattr(win, "_open_data_file", lambda: calls.append(True))
    _trigger(win, "data_import")
    assert calls == [True]


def test_peak_list_triggers_peak_detection(qapp, monkeypatch):
    win = MainWindow()
    calls: list[bool] = []
    monkeypatch.setattr(win, "_detect_peaks", lambda: calls.append(True))
    _trigger(win, "peak_list")
    assert calls == [True]


def test_rietveld_opens_refinement_wizard(qapp, monkeypatch):
    win = MainWindow()
    calls: list[bool] = []
    monkeypatch.setattr(win, "_open_refinement_wizard", lambda: calls.append(True))
    _trigger(win, "rietveld")
    assert calls == [True]


def test_restraints_focuses_right_dock_tab(qapp):
    win = MainWindow()
    _trigger(win, "restraints")
    assert win._restraints_tabs.currentIndex() == 0
    assert win._restraints_dock.isVisible() or not win.isVisible()
    # 状态栏给出限制条件相关提示（与样品元素快速录入的提示区分开）
    assert "周期表" in win.statusBar().currentMessage()


def test_restraints_focus_switches_back_from_other_tab(qapp):
    """从峰列表页切回限制条件页（索引 0），验证不是 no-op。"""
    win = MainWindow()
    win._restraints_tabs.setCurrentIndex(1)
    _trigger(win, "restraints")
    assert win._restraints_tabs.currentIndex() == 0


def test_raw_processing_menu_aggregates_preprocess_actions(qapp):
    """「原始数据处理」模块动作带子菜单，聚合工具栏已有的四个预处理动作。"""
    win = MainWindow()
    menu = win.module_actions["raw_processing"].menu()
    assert menu is not None
    actions = menu.actions()
    assert [a.text() for a in actions] == ["背景扣除", "平滑", "Kα2 剥离", "重置"]
    # 与工具栏动作是同一批对象（改一个地方两处同步）
    assert actions[0] is win.background_action
    assert actions[3] is win.reset_action


def test_still_placeholder_modules_announce(qapp):
    """未接线的模块动作仍然只做占位播报，不抛异常。"""
    win = MainWindow()
    win.show()
    for mod_id, label in (
        ("user_db", "用户数据库"),
        ("indexing", "指标化"),
        ("quant_analysis", "定量分析"),
        ("microstructure", "微结构分析"),
    ):
        _trigger(win, mod_id)
        assert label in win.statusBar().currentMessage(), mod_id
