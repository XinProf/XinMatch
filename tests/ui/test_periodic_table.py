"""T13.4 — tests for the 118-element periodic-table selector (offscreen)."""

from __future__ import annotations

from xinmatch.core.model.restraints import ElementState
from xinmatch.ui.periodic_table import PeriodicTableWidget


def test_all_118_buttons_present(qapp):
    w = PeriodicTableWidget()
    assert len(w._buttons) == 118


def test_click_cycles_through_four_states(qapp):
    """点击顺序对齐 PolyXRD：不限制 → 含有 → 可能 → 没有 → 必有 → 不限制。

    「必有」放末位是刻意的：它过滤最狠，误点一次只是回到起点（不限制），
    而不是把候选直接清空。
    """
    from xinmatch.ui.periodic_table import _CYCLE

    assert _CYCLE == (
        ElementState.OPTIONAL,
        ElementState.HAS,
        ElementState.MAYBE,
        ElementState.EXCLUDE,
        ElementState.REQUIRED,
    )
    w = PeriodicTableWidget()
    seen = []
    for _ in range(len(_CYCLE)):
        w._cycle("O")
        seen.append(w._states["O"])
    assert seen == [
        ElementState.HAS,
        ElementState.MAYBE,
        ElementState.EXCLUDE,
        ElementState.REQUIRED,
        ElementState.OPTIONAL,
    ]
    # 绕一圈回到原点，循环闭合。
    assert w._states["O"] == ElementState.OPTIONAL


def test_state_changed_signal_emitted(qapp):
    w = PeriodicTableWidget()
    caught: list[tuple[str, ElementState]] = []
    w.state_changed.connect(lambda s, st: caught.append((s, st)))
    w._cycle("Fe")
    assert ("Fe", ElementState.HAS) in caught


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
    assert "含有" in w._buttons["C"].toolTip()
    w._cycle("C")
    assert "可能" in w._buttons["C"].toolTip()
    w._cycle("C")
    assert "没有" in w._buttons["C"].toolTip()
    w._cycle("C")
    assert "必有" in w._buttons["C"].toolTip()


def test_tooltip_lists_the_whole_cycle(qapp):
    """tooltip 必须把五态循环写全，否则用户不知道还能点出「可能」。"""
    w = PeriodicTableWidget()
    tip = w._buttons["Na"].toolTip()
    for label in ("不限制", "含有", "可能", "没有", "必有"):
        assert label in tip, label


def test_four_states_are_visually_distinct(qapp):
    """四态不只靠颜色：线型 + 线宽 + 字重三重编码（色盲友好）。"""
    w = PeriodicTableWidget()
    w.set_states({
        "O": ElementState.HAS,
        "C": ElementState.MAYBE,
        "Fe": ElementState.EXCLUDE,
        "Si": ElementState.REQUIRED,
    })
    sheets = {
        state: w._buttons[sym].styleSheet()
        for sym, state in (
            ("O", ElementState.HAS), ("C", ElementState.MAYBE),
            ("Fe", ElementState.EXCLUDE), ("Si", ElementState.REQUIRED),
        )
    }
    assert len(set(sheets.values())) == 4
    assert "solid" in sheets[ElementState.HAS]
    assert "dotted" in sheets[ElementState.MAYBE]
    assert "dashed" in sheets[ElementState.EXCLUDE]
    assert "solid" in sheets[ElementState.REQUIRED]
    assert "3px" in sheets[ElementState.REQUIRED]   # 必有最粗


def test_legend_covers_four_active_states(qapp):
    from xinmatch.ui.periodic_table import LEGEND_ORDER

    assert LEGEND_ORDER == (
        ElementState.HAS, ElementState.MAYBE,
        ElementState.EXCLUDE, ElementState.REQUIRED,
    )


def test_grouped_splits_symbols_by_state(qapp):
    w = PeriodicTableWidget()
    w.set_states({
        "O": ElementState.REQUIRED,
        "Si": ElementState.HAS,
        "Al": ElementState.HAS,
        "H": ElementState.MAYBE,
        "Fe": ElementState.EXCLUDE,
    })
    groups = w.grouped()
    assert groups["required"] == ["O"]
    assert groups["has"] == ["Al", "Si"]       # 按周期表顺序，不是字母序
    assert groups["maybe"] == ["H"]
    assert groups["exclude"] == ["Fe"]


def test_apply_light_elements_only_fills_unset(qapp):
    """「补轻元素」只填 OPTIONAL 的格子，用户已明确标过的一律不动。"""
    from xinmatch.core.model.element_symbols import LIGHT_ELEMENTS

    w = PeriodicTableWidget()
    w.set_states({"O": ElementState.EXCLUDE, "C": ElementState.REQUIRED})
    changed = w.apply_light_elements()
    # O / C 已被明确标注 → 不在改动列表里
    assert "O" not in changed and "C" not in changed
    assert set(changed) == set(LIGHT_ELEMENTS) - {"O", "C"}
    assert w._states["O"] == ElementState.EXCLUDE
    assert w._states["C"] == ElementState.REQUIRED
    for sym in changed:
        assert w._states[sym] == ElementState.HAS
    # 再点一次没有可补的 → 空列表（面板据此给提示而不是静默无反应）
    assert w.apply_light_elements() == []


def test_picker_dialog_returns_table_to_panel(qapp, monkeypatch):
    """弹窗关闭后周期表实例必须回到面板并隐藏（滚动区需先解绑）。"""
    from PySide6 import QtWidgets

    from xinmatch.ui.periodic_table import PeriodicTablePanel

    panel = PeriodicTablePanel()
    monkeypatch.setattr(QtWidgets.QDialog, "exec", lambda self: 0)
    panel._open_picker()
    assert panel._table.parent() is panel
    assert panel._table.isHidden()


# ----------------------------------------------------------------------
# 闭环开关（v3.6.3，口径对齐 PolyXRD）
# ----------------------------------------------------------------------
def test_closed_world_off_by_default(qapp):
    from xinmatch.ui.periodic_table import PeriodicTablePanel

    panel = PeriodicTablePanel()
    assert panel.closed_world() is False
    assert "开放世界" in panel._closed_hint.text()


def test_closed_world_reports_pool_size(qapp):
    from xinmatch.core.model.element_symbols import ELEMENT_SYMBOLS
    from xinmatch.ui.periodic_table import PeriodicTablePanel

    panel = PeriodicTablePanel()
    panel.set_states({"O": ElementState.REQUIRED, "Si": ElementState.HAS,
                      "H": ElementState.MAYBE})
    panel.set_closed_world(True)
    hint = panel._closed_hint.text()
    assert "闭环已开启" in hint
    assert ">3<" in hint
    assert str(len(ELEMENT_SYMBOLS) - 3) in hint


def test_closed_world_without_pool_warns_it_is_a_noop(qapp):
    """只开闭环、一个元素都没标 → 等价于全库检索，必须说出来。"""
    from xinmatch.ui.periodic_table import PeriodicTablePanel

    panel = PeriodicTablePanel()
    panel.set_closed_world(True)
    assert "等价于全库检索" in panel._closed_hint.text()


def test_closed_world_toggle_emits_selection_changed(qapp):
    from xinmatch.ui.periodic_table import PeriodicTablePanel

    panel = PeriodicTablePanel()
    caught: list[int] = []
    panel.selection_changed.connect(lambda: caught.append(1))
    panel.set_closed_world(True)
    assert caught


def test_summary_shows_all_four_groups(qapp):
    from xinmatch.ui.periodic_table import PeriodicTablePanel

    panel = PeriodicTablePanel()
    panel.set_states({
        "O": ElementState.REQUIRED,
        "Si": ElementState.HAS,
        "H": ElementState.MAYBE,
        "Fe": ElementState.EXCLUDE,
    })
    text = panel._summary.text()
    for label in ("必有", "含有", "可能", "没有"):
        assert label in text, label
    assert "O" in text and "Si" in text and "H" in text and "Fe" in text


def test_panel_light_button_fills_and_notifies(qapp):
    from xinmatch.ui.periodic_table import PeriodicTablePanel

    panel = PeriodicTablePanel()
    caught: list[int] = []
    panel.selection_changed.connect(lambda: caught.append(1))
    changed = panel.apply_light_elements()
    # 返回顺序是**周期表顺序**（H 在 C 前），与摘要行展示一致。
    assert changed == ["H", "C", "N", "O", "S"]
    assert caught
    assert panel.states() == {
        "O": ElementState.HAS, "C": ElementState.HAS, "H": ElementState.HAS,
        "N": ElementState.HAS, "S": ElementState.HAS,
    }
