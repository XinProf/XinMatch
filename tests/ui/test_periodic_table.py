"""T13.4 — tests for the 118-element periodic-table selector (offscreen)."""

from __future__ import annotations

from xinmatch.core.model.restraints import ElementState
from xinmatch.ui.periodic_table import PeriodicTableWidget


def test_all_118_buttons_present(qapp):
    w = PeriodicTableWidget()
    assert len(w._buttons) == 118


def test_click_cycles_through_three_states(qapp):
    w = PeriodicTableWidget()
    # Default is OPTIONAL; cycle: optional -> required -> excluded -> optional.
    w._cycle("O")
    assert w._states["O"] == ElementState.REQUIRED
    w._cycle("O")
    assert w._states["O"] == ElementState.EXCLUDE
    w._cycle("O")
    assert w._states["O"] == ElementState.OPTIONAL


def test_state_changed_signal_emitted(qapp):
    w = PeriodicTableWidget()
    caught: list[tuple[str, ElementState]] = []
    w.state_changed.connect(lambda s, st: caught.append((s, st)))
    w._cycle("Fe")
    assert ("Fe", ElementState.REQUIRED) in caught


def test_states_only_returns_active(qapp):
    w = PeriodicTableWidget()
    w.set_states({"O": ElementState.REQUIRED, "Fe": ElementState.EXCLUDE})
    s = w.states()
    assert s == {"O": ElementState.REQUIRED, "Fe": ElementState.EXCLUDE}


def test_set_states_roundtrip(qapp):
    w = PeriodicTableWidget()
    wanted = {"Cu": "green", "Pb": "red"}
    w.set_states(wanted)
    out = w.states()
    assert out["Cu"] == ElementState.REQUIRED
    assert out["Pb"] == ElementState.EXCLUDE
    # Round-trip: build a fresh widget, apply the same states, equal result.
    w2 = PeriodicTableWidget()
    w2.set_states(out)
    assert w2.states() == out


def test_toggle_disables_buttons_but_keeps_states(qapp):
    w = PeriodicTableWidget()
    w.set_states({"Si": ElementState.REQUIRED})
    w.set_enabled(False)
    assert not w.is_enabled()
    # Buttons disabled yet states retained.
    assert not w._buttons["Si"].isEnabled()
    assert w.states() == {"Si": ElementState.REQUIRED}
    w.set_enabled(True)
    assert w._buttons["Si"].isEnabled()


def test_reset_clears_all(qapp):
    w = PeriodicTableWidget()
    w.set_states({"H": ElementState.EXCLUDE, "C": ElementState.REQUIRED})
    w.reset()
    assert w.states() == {}


# ----------------------------------------------------------------------
# 2026-11-08 修复的回归：符号被裁 / 按钮被压扁
# ----------------------------------------------------------------------
def test_buttons_keep_fixed_size_under_global_qss(qapp):
    """全局 QPushButton 的 padding / min-height 不得压扁或裁掉元素按钮。

    病根两条，均在此断言：
    ① 全局 ``padding: 5px 14px`` 会吃掉 28 px 内容宽度 → 符号被裁；
    ② 全局 ``min-height: 20px`` 优先级高于 ``setFixedSize()`` →
       按钮实际高度 25 px（设定 33 px），大字体下必裁。
    """
    from PySide6 import QtCore

    from xinmatch.ui.periodic_table import _BORDER_PX

    old = qapp.styleSheet()
    qapp.setStyleSheet("QPushButton { padding: 5px 14px; min-height: 20px; }")
    try:
        w = PeriodicTableWidget()
        w.show()
        qapp.processEvents()
        wanted = QtCore.QSize(w._cell_w, w._cell_h)
        for symbol, btn in w._buttons.items():
            assert btn.minimumSize() == wanted, symbol
            assert btn.maximumSize() == wanted, symbol
            assert btn.size() == wanted, symbol
            fm = btn.fontMetrics()
            assert btn.width() >= fm.horizontalAdvance(symbol) + 2 * _BORDER_PX
            assert btn.height() >= fm.height() + 2 * _BORDER_PX
    finally:
        qapp.setStyleSheet(old)


def test_cell_size_follows_font_metrics(qapp):
    """按钮尺寸由字体度量决定，且两个字母的符号也放得下。"""
    from PySide6 import QtGui

    w = PeriodicTableWidget()
    metrics = QtGui.QFontMetrics(w._buttons["Og"].font())
    assert w._cell_w >= metrics.horizontalAdvance("Og")
    assert w._cell_h >= metrics.height()
    assert w._cell_w >= 30 and w._cell_h >= 26  # 下限，防字体异常时按钮退化


def test_state_visuals_differ_by_border_style(qapp):
    """三态不只靠颜色：必含实线、排除虚线、都加粗（色盲友好）。"""
    w = PeriodicTableWidget()
    w.set_states({"O": ElementState.REQUIRED, "Fe": ElementState.EXCLUDE})
    req = w._buttons["O"].styleSheet()
    exc = w._buttons["Fe"].styleSheet()
    opt = w._buttons["H"].styleSheet()
    assert "solid" in req and "bold" in req
    assert "dashed" in exc and "bold" in exc
    assert "padding: 0px" in req  # 必须压掉全局 padding
    assert "normal" in opt
    # 三态边框色互不相同
    assert len({req, exc, opt}) == 3


def test_tooltip_reports_current_state(qapp):
    w = PeriodicTableWidget()
    assert "不限制" in w._buttons["C"].toolTip()
    w._cycle("C")
    assert "必含" in w._buttons["C"].toolTip()
    w._cycle("C")
    assert "排除" in w._buttons["C"].toolTip()


def test_picker_dialog_returns_table_to_panel(qapp, monkeypatch):
    """弹窗关闭后周期表实例必须回到面板并隐藏（滚动区需先解绑）。"""
    from PySide6 import QtWidgets

    from xinmatch.ui.periodic_table import PeriodicTablePanel

    panel = PeriodicTablePanel()
    monkeypatch.setattr(QtWidgets.QDialog, "exec", lambda self: 0)
    panel._open_picker()
    assert panel._table.parent() is panel
    assert panel._table.isHidden()
