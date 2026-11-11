"""批次 1 接线 —— 五个占位模块动作接到既有能力的单测。

HANDOVER §7.2 P2「GUI 剩余向导 / 主题」拆解后的第一批：不改任何 core 能力，
只把菜单/工具栏里仍是 `_placeholder` 的模块动作接到已经存在的入口：

* ``data_import``    → ``_open_data_file``（与工具栏「打开数据…」Ctrl+O 同槽）；
* ``raw_processing`` → 聚合菜单（背景扣除 / 平滑 / Kα2 剥离 / 重置，无新逻辑）；
* ``peak_list``      → ``_detect_peaks``（与工具栏「峰检测」同槽）；
* ``restraints``     → ``_focus_restraints``（右侧坞的限制条件页翻到最前）；
* ``rietveld``       → ``_open_refinement_wizard``（与精修向导 Ctrl+Shift+W 同槽）；
* ``user_db``        → ``_open_user_db_dialog``（2026-11-11：自建库管理，v3 原生
  ``.xinDB``，见 ``user_db_dialog.py`` / ``tests/db/test_user_db.py``）。

至此 15 个模块动作**全部**接线（``data_export`` / ``raw_processing`` 走聚合
菜单），``_placeholder`` 只剩兜底作用，由 ``test_no_module_action_is_placeholder``
守住。其余模块的单测见 ``test_export_menu.py`` / ``test_profile_fit_dialog.py`` /
``test_quant_dialog.py`` / ``test_microstructure_dialog.py`` /
``test_indexing_wizard.py`` / ``test_user_db_dialog.py``。
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


def test_user_db_action_opens_dialog(qapp, monkeypatch):
    """``user_db`` → ``_open_user_db_dialog``（自建库管理，2026-11-11 接线）。

    对话框本体走 ``run_with_busy`` + 真实写库，单测不在这里展开（见
    ``test_user_db_dialog.py``），此处只钉动作接线。
    """
    win = MainWindow()
    calls: list[bool] = []
    monkeypatch.setattr(win, "_open_user_db_dialog", lambda: calls.append(True))
    _trigger(win, "user_db")
    assert calls == [True]


def test_no_module_action_is_placeholder(qapp, monkeypatch):
    """15 个模块动作全部接线完毕，没有任何一个还落在 ``_placeholder``。

    ``_placeholder`` 保留为"以后新增模块忘了接线"的兜底，本用例保证它现在
    **不会**被任何模块触发。手写清单是刻意的：新增模块若忘了接线，这里会红。
    """
    from unittest.mock import patch

    from xinmatch.ui.main_window import MODULES

    win = MainWindow()
    handlers = (
        "_open_data_file",
        "_detect_peaks",
        "_focus_restraints",
        "_open_refinement_wizard",
        "_open_profile_fit",
        "_run_search_match",
        "_run_report_preview",
        "_open_library_dialog",
        "_open_user_db_dialog",
        "_open_indexing_wizard",
        "_open_quant_dialog",
        "_open_microstructure",
        "_open_options_dialog",
    )
    hits: list[str] = []
    for name in handlers:
        monkeypatch.setattr(
            win, name, (lambda n: lambda *a, **k: hits.append(n))(name)
        )
    with patch.object(win, "_placeholder") as placeholder:
        for mod_id, _label, _anchor in MODULES:
            if mod_id in ("data_export", "raw_processing"):
                continue  # 这两个走 setMenu 的聚合菜单，没有独立槽
            _trigger(win, mod_id)
    placeholder.assert_not_called()
    assert len(hits) == len(handlers), f"有模块没被触发：{sorted(set(handlers) - set(hits))}"
