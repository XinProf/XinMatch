"""v3.6.2 — 谱图快捷图标行 + 视图操作 + 轴点击切换。

覆盖用户 2026-11-08 的两条要求：

- 「这个位置可以参考 XinRefinement 那样显示一些快捷图标以便对谱图进行处理」
  → :class:`~xinmatch.ui.plot_toolbar.PlotToolBar` 的按钮全部落到
  :class:`~xinmatch.ui.pattern_view.PatternView` 的视图操作上；
- 「这个区域可以不用要（隐藏，但功能保留），把功能放入横竖轴中，鼠标点击
  左键可切换不同的显示，鼠标右键也可以切换」
  → 顶部控制条隐藏、下拉框仍是模式真相源；轴的左键循环 / 右键菜单。

全部 offscreen 运行，不依赖真实数据库。
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6 import QtCore

from xinmatch.core.model.pattern import Pattern
from xinmatch.ui.pattern_view import (
    PLOT_TOOL_MODES,
    TOOL_CROSSHAIR,
    TOOL_ZOOM_RECT,
    TOOL_ZOOM_X,
    TOOL_ZOOM_Y,
    PatternPanel,
    PatternView,
)
from xinmatch.ui.plot_icons import PLOT_TOOL_KEYS
from xinmatch.ui.plot_toolbar import PAN_FRAC, ZOOM_STEP, PlotToolBar


def _synth(n: int = 1500) -> Pattern:
    """宽带谱：10° 处一根巨峰 + 25° 一根小峰（用来区分"纵轴贴合"取哪段数据）。"""
    x = np.linspace(5.0, 90.0, n)
    y = np.full_like(x, 20.0)
    y += 5000.0 * np.exp(-((x - 10.0) ** 2) / (2.0 * 0.12**2))
    y += 120.0 * np.exp(-((x - 25.0) ** 2) / (2.0 * 0.12**2))
    return Pattern(two_theta=x, intensity=y, wavelength=1.5406)


@pytest.fixture
def panel(qapp):
    """新建面板并显式销毁（pyqtgraph 的 LabelItem 延迟回收会带崩后续测试）。"""
    widget = PatternPanel()
    widget.resize(800, 520)
    yield widget
    widget.view.clear()
    widget.lane.set_rows([])
    widget.setParent(None)
    widget.deleteLater()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# 图标行装配
# ---------------------------------------------------------------------------
def test_toolbar_has_one_button_per_icon(panel):
    """图标行的按钮集合必须与绘图模块的键集合一致（不漏图标、不多死按钮）。"""
    assert isinstance(panel.toolbar, PlotToolBar)
    assert set(panel.toolbar.buttons) == set(PLOT_TOOL_KEYS)


def test_every_button_has_tooltip(panel):
    for key, button in panel.toolbar.buttons.items():
        assert button.toolTip().strip(), key


def test_mode_buttons_are_exclusive_but_cancellable(panel):
    """互斥但可取消：点 B 会取消 A，再点 B 自己则回到 None（无工具）。"""
    toolbar = panel.toolbar
    toolbar.buttons["zoom_x"].click()
    assert toolbar.mode == TOOL_ZOOM_X
    toolbar.buttons["zoom_y"].click()
    assert toolbar.mode == TOOL_ZOOM_Y
    assert toolbar.buttons["zoom_x"].isChecked() is False
    toolbar.buttons["zoom_y"].click()  # 再点一次 = 取消
    assert toolbar.mode is None


def test_crosshair_button_is_checked_initially(panel):
    """默认工具是十字线（与改造前"鼠标一动就有读数"的体验一致）。"""
    assert panel.view.tool() == TOOL_CROSSHAIR
    assert panel.toolbar.buttons["crosshair"].isChecked() is True


# ---------------------------------------------------------------------------
# 视图操作：复位 / 平移 / 步进缩放
# ---------------------------------------------------------------------------
def _x_range(panel: PatternPanel) -> tuple[float, float]:
    x0, x1 = panel.view.plotItem.vb.viewRange()[0]
    return float(x0), float(x1)


def test_reset_restores_full_x_range(panel):
    """复位必须能"缩回去"——``clipToView`` 让 autoRange 只看可见点，不能依赖它。"""
    panel.add_pattern(_synth())
    panel.view.plotItem.vb.setXRange(20.0, 30.0, padding=0)
    assert _x_range(panel) == pytest.approx((20.0, 30.0), rel=1e-6)
    panel.view.reset_view()
    x0, x1 = _x_range(panel)
    assert x0 <= 5.0 and x1 >= 90.0, "复位后全量数据没有都进视野"
    assert x1 - x0 < 100.0, "复位后视野过于宽松"


def test_pan_right_then_left_returns(panel):
    panel.add_pattern(_synth())
    before = _x_range(panel)
    panel.view.pan_x(PAN_FRAC)
    after_right = _x_range(panel)
    width = before[1] - before[0]
    assert after_right[0] == pytest.approx(before[0] + width * PAN_FRAC, rel=1e-6)
    panel.view.pan_x(-PAN_FRAC)
    assert _x_range(panel) == pytest.approx(before, rel=1e-6)


def test_zoom_in_narrows_and_zoom_out_restores(panel):
    panel.add_pattern(_synth())
    before = _x_range(panel)
    panel.view.zoom_scale(ZOOM_STEP)
    zoomed = _x_range(panel)
    assert zoomed[1] - zoomed[0] == pytest.approx(
        (before[1] - before[0]) * ZOOM_STEP, rel=1e-6
    )
    # 中心不变（以视场中心为锚点）。
    assert (zoomed[0] + zoomed[1]) / 2 == pytest.approx(
        (before[0] + before[1]) / 2, rel=1e-9
    )
    panel.view.zoom_scale(1.0 / ZOOM_STEP)
    assert _x_range(panel) == pytest.approx(before, rel=1e-6)


def test_fit_y_range_only_uses_visible_window(panel):
    """纵轴"贴合"只看当前横轴窗口内的数据（10° 巨峰不该撑高 20–30° 的视野）。"""
    panel.add_pattern(_synth())
    vb = panel.view.plotItem.vb
    vb.setXRange(20.0, 30.0, padding=0)
    panel.view.fit_y_range()
    y0, y1 = vb.viewRange()[1]
    assert y1 < 500.0, "10° 处 5000 计数的巨峰把纵轴撑上去了"
    assert y0 < 30.0


# ---------------------------------------------------------------------------
# 按轴框选：zoom_x 只改横轴（纵轴贴合），zoom_y 只改纵轴
# ---------------------------------------------------------------------------
def test_zoom_x_changes_only_x_and_refits_y(panel):
    panel.add_pattern(_synth())
    view = panel.view
    vb = view.plotItem.vb
    view.set_plot_tool(TOOL_ZOOM_X)
    assert vb.axis_lock == "y"
    y_before = vb.viewRange()[1]
    vb.showAxRect(QtCore.QRectF(20.0, 0.0, 10.0, 100.0))
    x0, x1 = vb.viewRange()[0]
    assert (x0, x1) == pytest.approx((20.0, 30.0), rel=1e-6)
    y0, y1 = vb.viewRange()[1]
    assert (y0, y1) != pytest.approx(tuple(y_before), rel=1e-6), "纵轴没有重新贴合"
    assert y1 < 500.0


def test_zoom_y_changes_only_y(panel):
    panel.add_pattern(_synth())
    view = panel.view
    vb = view.plotItem.vb
    view.set_plot_tool(TOOL_ZOOM_Y)
    assert vb.axis_lock == "x"
    x_before = vb.viewRange()[0]
    vb.showAxRect(QtCore.QRectF(0.0, 100.0, 10.0, 200.0))
    assert vb.viewRange()[0] == pytest.approx(tuple(x_before), rel=1e-9)
    y0, y1 = vb.viewRange()[1]
    assert y0 == pytest.approx(100.0) and y1 == pytest.approx(300.0)


def test_zoom_rect_changes_both_axes(panel):
    panel.add_pattern(_synth())
    vb = panel.view.plotItem.vb
    panel.view.set_plot_tool("zoom_rect")
    assert vb.axis_lock is None
    vb.showAxRect(QtCore.QRectF(20.0, 100.0, 10.0, 200.0))
    # 不锁轴时沿用 pyqtgraph 默认的 2% 边距，故只比对中心与宽度量级。
    (x0, x1), (y0, y1) = vb.viewRange()
    assert (x0 + x1) / 2 == pytest.approx(25.0, rel=1e-6)
    assert (y0 + y1) / 2 == pytest.approx(200.0, rel=1e-6)
    assert 10.0 <= x1 - x0 <= 11.0 and 200.0 <= y1 - y0 <= 220.0


def test_unknown_tool_is_rejected(panel):
    with pytest.raises(ValueError):
        panel.view.set_plot_tool("teleport")


# ---------------------------------------------------------------------------
# 十字线工具
# ---------------------------------------------------------------------------
def test_crosshair_hidden_outside_crosshair_tool(panel):
    panel.add_pattern(_synth())
    assert panel.view.crosshair_visible() is True
    panel.view.set_plot_tool(TOOL_ZOOM_X)
    assert panel.view.crosshair_visible() is False
    panel.view.set_plot_tool(TOOL_CROSSHAIR)
    assert panel.view.crosshair_visible() is True


def test_crosshair_readout_reaches_toolbar_hint(panel):
    """读数贴谱图显示一份（状态栏可能被其它消息占用）。"""
    panel.add_pattern(_synth())
    panel.view.set_crosshair_position(25.0, 140.0)
    assert "2θ" in panel.toolbar.lbl_hint.text()

    panel.view.set_plot_tool(TOOL_ZOOM_RECT)
    panel.toolbar.lbl_hint.setText("")  # 框选模式下不该再显示读数
    panel.view.set_crosshair_position(25.0, 140.0)
    assert panel.toolbar.lbl_hint.text() == ""


# ---------------------------------------------------------------------------
# 顶部控制条隐藏 + 轴点击切换
# ---------------------------------------------------------------------------
def test_axis_bar_is_hidden_but_still_works(panel):
    """控制条不可见；``x_combo`` / ``y_combo`` 仍是模式真相源。"""
    assert panel._axis_bar.isVisible() is False
    panel.x_combo.setCurrentIndex(1)
    assert panel.view.x_mode() == "d"
    panel.y_combo.setCurrentIndex(2)
    assert panel.view.y_mode() == "log"


def test_left_click_on_axis_cycles_modes(panel):
    from PySide6 import QtCore as Qt

    assert panel.x_combo.currentIndex() == 0
    panel._on_x_axis_clicked(Qt.Qt.MouseButton.LeftButton)
    assert panel.x_combo.currentIndex() == 1
    assert panel.view.x_mode() == "d"
    panel._on_x_axis_clicked(Qt.Qt.MouseButton.LeftButton)  # 循环回绕
    assert panel.x_combo.currentIndex() == 0
    assert panel.view.x_mode() == "two_theta"

    panel._on_y_axis_clicked(Qt.Qt.MouseButton.LeftButton)
    panel._on_y_axis_clicked(Qt.Qt.MouseButton.LeftButton)
    assert panel.y_combo.currentIndex() == 2
    assert panel.view.y_mode() == "log"


def test_right_click_on_axis_builds_mode_menu(panel):
    menu = panel._build_axis_menu(panel.x_combo, "X 轴显示", popup=False)
    texts = [a.text() for a in menu.actions()]
    assert texts == ["2θ (角度)", "d 值"]
    assert menu.actions()[0].isChecked() is True

    menu.actions()[1].trigger()
    assert panel.view.x_mode() == "d"
    menu.deleteLater()


def test_axis_click_signals_are_wired(panel):
    """视图发出的轴点击信号必须真的驱动面板（不是只在测试里调内部函数）。"""
    received: list[object] = []
    panel.view.x_axis_clicked.connect(received.append)
    panel.view.x_axis_clicked.emit(QtCore.Qt.MouseButton.LeftButton)
    assert received
    assert panel.view.x_mode() == "d"


def test_plot_tools_constant_covers_all_mode_tools():
    assert set(PLOT_TOOL_MODES) == {"zoom_x", "zoom_y", "zoom_rect", "crosshair"}
    assert PlotToolBar is not None


def test_pattern_view_still_exposes_legacy_api(panel):
    """改造不能删既有公开接口（主窗口与 .xinm 存档都依赖它们）。"""
    view = PatternView()
    assert hasattr(view, "fit_data_range")
    assert hasattr(view, "add_stick_pattern")
    assert panel.add_pattern(_synth(200)) in panel.patterns()
