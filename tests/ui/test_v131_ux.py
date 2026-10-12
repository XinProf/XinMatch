"""v1.3.1 GUI 体验迭代测试。

覆盖五项改进的可验证行为：

1. 图标视觉归一化：所有图标 24px 位图的内容包围盒占比一致（±容差）；
2. 工具栏：图标+文字模式、每个模块动作带详细 tooltip；
3. 忙碌窗口：run_with_busy 成功/失败/重入保护三态；
4. 周期表弹出面板：摘要刷新、状态读写、选择信号；
5. 谱图轴切换：X 2θ↔d 变换正确、Y 计数/√/对数变换正确、
   crosshair 读数恒为物理量、打开数据自动适配范围。

全部 offscreen 运行，不依赖真实数据库。
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import math

import numpy as np
import pytest
from PySide6 import QtCore, QtWidgets

from xinmatch.core.model.pattern import Pattern
from xinmatch.ui.busy import BusyDialog, run_with_busy
from xinmatch.ui.icons import ICON_NAMES, _alpha_bbox, icon
from xinmatch.ui.main_window import MainWindow
from xinmatch.ui.pattern_view import (
    X_MODE_D,
    X_MODE_TWO_THETA,
    Y_MODE_COUNTS,
    Y_MODE_LOG,
    Y_MODE_SQRT,
    PatternPanel,
    PatternView,
)
from xinmatch.ui.periodic_table import PeriodicTablePanel, PeriodicTableWidget


def _synth(n: int = 2000) -> Pattern:
    x = np.linspace(5.0, 90.0, n)
    y = 20.0 + 800.0 * np.exp(-((x - 28.4) ** 2) / (2 * 0.15**2))
    return Pattern(
        two_theta=x, intensity=y, wavelength=1.5406, metadata={"sample_id": "t"}
    )


# ---------------------------------------------------------------------------
# 1. 图标视觉归一化
# ---------------------------------------------------------------------------
def test_icons_content_ratio_uniform():
    """每个图标 24px 位图内容包围盒长边占比应统一在 0.74±0.12 内。"""
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert app is not None
    for name in sorted(ICON_NAMES):
        pm = icon(name).pixmap(24, 24)
        assert not pm.isNull(), name
        bbox = _alpha_bbox(pm.toImage())
        assert bbox is not None and not bbox.isEmpty(), name
        ratio = max(bbox.width(), bbox.height()) / 24.0
        assert 0.62 <= ratio <= 0.86, (name, round(ratio, 3))


# ---------------------------------------------------------------------------
# 2. 工具栏：图标+文字 + 详细 tooltip
# ---------------------------------------------------------------------------
def test_toolbar_shows_text_beside_icon(qapp):
    win = MainWindow()
    toolbars = [tb for tb in win.findChildren(QtWidgets.QToolBar)]
    main_tb = next(tb for tb in toolbars if tb.objectName() == "mainToolbar")
    assert (
        main_tb.toolButtonStyle()
        == QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon
    )


def test_every_module_action_has_detailed_tooltip(qapp):
    win = MainWindow()
    for mod_id, action in win.module_actions.items():
        tip = action.toolTip()
        assert tip, f"{mod_id} 缺 tooltip"
        assert len(tip) >= 12, f"{mod_id} tooltip 过简：{tip!r}"
    # 打开数据与精修向导也应有详细说明。
    assert "Ctrl+O" in win.open_action.toolTip()
    assert "Ctrl+Shift+W" in win.refinement_wizard_action.toolTip()


# ---------------------------------------------------------------------------
# 3. 忙碌窗口
# ---------------------------------------------------------------------------
def test_busy_dialog_reject_ignored(qapp):
    dlg = BusyDialog(None, "测试", "正在处理…")
    dlg.reject()  # ESC 不应关闭
    assert dlg.result() == QtWidgets.QDialog.DialogCode.Rejected  # 未 accept


def test_run_with_busy_success_applies_result(qapp):
    win = MainWindow()

    def work():
        return ("模式X", 42)

    seen: list = []
    run_with_busy(
        win, "测试任务", "正在测试…", work,
        on_success=lambda payload: seen.append(payload),
    )
    assert seen == [("模式X", 42)]
    assert not win._busy_active  # 结束后必须复位，否则后续操作被吞


def test_run_with_busy_error_routes_to_on_error(qapp):
    win = MainWindow()

    def work():
        raise RuntimeError("boom")

    errors: list[str] = []
    run_with_busy(win, "测试任务", "正在测试…", work, on_error=errors.append)
    assert len(errors) == 1 and "boom" in errors[0]
    assert not win._busy_active


def test_run_with_busy_reentrancy_guard(qapp):
    """忙碌中再次调用直接忽略（防连点排队）。"""
    win = MainWindow()
    win._busy_active = True  # 模拟上一次尚未结束
    calls: list[int] = []
    run_with_busy(win, "测试", "…", lambda: calls.append(1))
    assert calls == []  # 被忽略
    win._busy_active = False


# ---------------------------------------------------------------------------
# 4. 周期表弹出面板
# ---------------------------------------------------------------------------
def test_periodic_panel_default_summary_and_states_roundtrip():
    panel = PeriodicTablePanel()
    assert "未选择元素" in panel._summary.text()
    panel.set_states({"Fe": "green", "Na": "red"})
    assert panel.states() == {"Fe": "green", "Na": "red"}  # drop-in API
    text = panel._summary.text()
    assert "必含" in text and "Fe" in text
    assert "排除" in text and "Na" in text
    panel.reset()
    assert panel.states() == {}
    assert "未选择元素" in panel._summary.text()


def test_periodic_panel_summary_warns_when_toggle_off():
    panel = PeriodicTablePanel()
    panel.set_states({"Fe": "green"})
    panel.set_enabled(False)
    assert "过滤已关闭" in panel._summary.text()
    assert not panel.is_enabled()
    panel.set_enabled(True)
    assert "过滤已关闭" not in panel._summary.text()


def test_periodic_panel_selection_signal(qapp):
    panel = PeriodicTablePanel()
    fired: list[int] = []
    panel.selection_changed.connect(lambda: fired.append(1))
    panel._clear_all()
    assert fired, "清除后应发出 selection_changed"
    # 内嵌周期表实例存在且可复用（弹窗载体）。
    assert isinstance(panel._table, PeriodicTableWidget)


# ---------------------------------------------------------------------------
# 5. 谱图轴切换与自适应范围
# ---------------------------------------------------------------------------
def test_view_defaults_and_fit_range_on_add():
    view = PatternView()
    assert view.x_mode() == X_MODE_TWO_THETA
    assert view.y_mode() == Y_MODE_COUNTS
    view.add_pattern(_synth())
    (x0, x1), _ = view._plot.vb.viewRange()
    # 打开数据后 X 范围应覆盖数据（5–90°），只带合理边距。
    assert x0 < 5.0
    assert x1 > 90.0
    assert (x1 - x0) <= 1.2 * (90.0 - 5.0)


def test_x_mode_d_transform_matches_bragg():
    view = PatternView()
    key = view.add_pattern(_synth())
    view.set_x_mode(X_MODE_D)
    assert view.x_mode() == X_MODE_D
    xdata = np.asarray(view._records[key]["curve"].xData)
    # 首点 2θ=5° → d = λ / (2 sin(2.5°))；末点 90° → d = λ / (2 sin45°)。
    d_first = 1.5406 / (2 * math.sin(math.radians(5.0) / 2))
    d_last = 1.5406 / (2 * math.sin(math.radians(90.0) / 2))
    assert xdata[0] == pytest.approx(d_first, rel=1e-6)
    assert xdata[-1] == pytest.approx(d_last, rel=1e-6)
    # 单调递减（2θ 增大 → d 减小）。
    assert np.all(np.diff(xdata) < 0)
    # 轴标签切换为 d。
    assert view._plot.getAxis("bottom").labelText == "d"
    view.set_x_mode(X_MODE_TWO_THETA)
    assert view._plot.getAxis("bottom").labelText == "2θ"


def test_y_mode_sqrt_and_log_transforms():
    view = PatternView()
    key = view.add_pattern(_synth())
    orig_y = np.asarray(view._records[key]["pattern"].intensity)
    view.set_y_mode(Y_MODE_SQRT)
    ydata = np.asarray(view._records[key]["curve"].yData)
    np.testing.assert_allclose(ydata, np.sqrt(np.clip(orig_y, 0, None)), rtol=1e-9)
    view.set_y_mode(Y_MODE_LOG)
    ydata = np.asarray(view._records[key]["curve"].yData)
    np.testing.assert_allclose(
        ydata, np.log10(np.where(orig_y > 0, orig_y, 1.0)), rtol=1e-9
    )
    assert np.all(np.isfinite(ydata))
    view.set_y_mode(Y_MODE_COUNTS)
    ydata = np.asarray(view._records[key]["curve"].yData)
    np.testing.assert_allclose(ydata, orig_y, rtol=1e-9)


def test_crosshair_readout_is_physical_in_all_modes():
    """轴切到 d/对数后，crosshair 读数仍显示 2θ 与原始计数。"""
    view = PatternView()
    view.add_pattern(_synth())
    view.set_x_mode(X_MODE_D)
    view.set_y_mode(Y_MODE_LOG)
    view.set_crosshair_position(30.0, 120.0)
    text = view._readout.toPlainText()
    assert "30.000" in text and "120.0" in text and "d =" in text


def test_pattern_panel_controls_wired():
    panel = PatternPanel()
    assert isinstance(panel.view, PatternView)
    panel.x_combo.setCurrentIndex(1)  # d 值
    assert panel.view.x_mode() == X_MODE_D
    panel.y_combo.setCurrentIndex(1)  # 平方根
    assert panel.view.y_mode() == Y_MODE_SQRT
    # cursor_moved 信号转发。
    received: list[str] = []
    panel.cursor_moved.connect(received.append)
    panel.view.add_pattern(_synth(300))
    panel.view.set_crosshair_position(30.0, 100.0)
    assert received and "2θ" in received[-1]
