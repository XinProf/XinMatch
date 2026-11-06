"""「样品元素」快速录入 → 元素补集约束 → 工具栏状态（2026-11-06）。

基准报告 §20 的结论：多相样品的次相缺的是**化学信息**，不是预筛名额或排序键。
但「只允许 Zn/Al/Ca/O/F」在预筛层只能表达成「其余 113 个元素全部标红」，
用户在 118 个按钮上逐个点是做不到的。这个快捷入口把一句话变成一次点击。

这里固定四件事：
1. 解析是纯函数、大小写不敏感、去重、拒绝非元素符号；
2. 生成的约束**只含 EXCLUDE**，绝不能把检出元素标成 REQUIRED
   （`prescreen(elements_allowed=...)` 是「必须全部含有」语义，见 §20.5）；
3. 约束真的能进 `_current_restraints()`；
4. 工具栏按钮常显状态，点击能跳到「限制条件」页并聚焦输入框。
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from xinmatch.core.model.restraints import ElementState
from xinmatch.ui.main_window import MainWindow
from xinmatch.ui.periodic_table import (
    ELEMENT_SYMBOLS,
    PeriodicTablePanel,
    parse_element_symbols,
)

SAMPLE = "zn, O o F Al Ca"
EXPECTED = ("O", "F", "Al", "Ca", "Zn")


# ---------------------------------------------------------------------------
# 纯解析层
# ---------------------------------------------------------------------------

def test_parse_normalises_case_and_deduplicates():
    known, unknown = parse_element_symbols(SAMPLE)
    assert known == list(EXPECTED)
    assert unknown == []


def test_parse_accepts_common_separators():
    assert parse_element_symbols("Zn;Al、Ca，O/F")[0] == [
        "O", "F", "Al", "Ca", "Zn"
    ]


def test_parse_reports_unknown_instead_of_guessing():
    known, unknown = parse_element_symbols("Zn Xx Al2O3")
    assert known == ["Zn"]
    assert unknown == ["Xx", "Al2O3"]


def test_parse_empty():
    assert parse_element_symbols("   ") == ([], [])


def test_symbol_table_has_118_entries():
    assert len(ELEMENT_SYMBOLS) == 118


# ---------------------------------------------------------------------------
# 面板层
# ---------------------------------------------------------------------------

def test_quick_entry_builds_exclude_complement(qapp):
    panel = PeriodicTablePanel()
    detected, unknown = panel.apply_detected_elements(SAMPLE)
    assert detected == list(EXPECTED)
    assert unknown == []

    states = panel.states()
    assert len(states) == len(ELEMENT_SYMBOLS) - len(EXPECTED)
    assert all(st == ElementState.EXCLUDE for st in states.values())
    # 检出元素必须保持「可选」：次相未必含主相的每一个元素。
    for sym in EXPECTED:
        assert sym not in states
    assert "Bi" in states and "Pb" in states


def test_quick_entry_summary_and_state(qapp):
    panel = PeriodicTablePanel()
    panel.apply_detected_elements(SAMPLE)
    assert panel.quick_elements() == EXPECTED
    assert "仅允许" in panel._summary.text()
    assert "113" in panel._summary.text()


def test_quick_entry_enables_filter_when_it_was_off(qapp):
    panel = PeriodicTablePanel()
    panel.set_enabled(False)
    panel.apply_detected_elements(SAMPLE)
    assert panel.is_enabled()


def test_quick_entry_emits_selection_changed(qapp):
    panel = PeriodicTablePanel()
    caught: list[int] = []
    panel.selection_changed.connect(lambda: caught.append(1))
    panel.apply_detected_elements(SAMPLE)
    assert caught


def test_unknown_symbols_change_nothing(qapp):
    panel = PeriodicTablePanel()
    detected, unknown = panel.apply_detected_elements("Zn Xx")
    assert detected == ["Zn"]
    assert unknown == ["Xx"]
    assert panel.states() == {}
    assert panel.quick_elements() == ()


def test_manual_edit_or_clear_leaves_quick_mode(qapp):
    panel = PeriodicTablePanel()
    panel.apply_detected_elements(SAMPLE)
    panel._on_table_state_changed("Bi", ElementState.OPTIONAL)
    assert panel.quick_elements() == ()

    panel.apply_detected_elements(SAMPLE)
    panel._clear_all()
    assert panel.quick_elements() == ()
    assert panel._detected_edit.text() == ""
    assert panel.states() == {}


# ---------------------------------------------------------------------------
# 主窗口接线
# ---------------------------------------------------------------------------

def test_toolbar_action_tracks_panel_state(qapp):
    win = MainWindow()
    action = win.sample_elements_action
    assert action.text() == "样品元素：未设置"

    win.periodic_panel.apply_detected_elements(SAMPLE)
    assert "仅 O F Al Ca Zn" in action.text()

    win.periodic_panel.set_enabled(False)
    assert action.text() == "样品元素：已关闭"


def test_restraints_carry_the_complement_into_search(qapp):
    win = MainWindow()
    win.periodic_panel.apply_detected_elements(SAMPLE)
    restraints = win._current_restraints()
    assert restraints is not None
    assert len(restraints.elements) == 113
    assert set(restraints.elements.values()) == {ElementState.EXCLUDE}
    assert "Zn" not in restraints.elements
    assert "Bi" in restraints.elements


def test_toolbar_action_jumps_to_restraints_tab(qapp):
    win = MainWindow()
    win.show()
    qapp.processEvents()
    win._restraints_tabs.setCurrentIndex(1)
    win.focus_sample_elements()
    assert win._restraints_tabs.currentIndex() == 0
    assert win._restraints_dock.isVisible()
    assert win.periodic_panel._detected_edit.hasFocus()
