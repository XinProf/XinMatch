"""v3.6.2 — 谱图下方的参考线条（stick）分区。

用户需求（2026-11-08）：

- 候选列表里选中一个物相时，谱图下方独立行区显示它的**峰位与强度**；
- 已确认的物相也一并列在这里，用来查漏"还有哪些峰没被匹配"；
- 鼠标勾选可切「只要角度位置」/「同时显示角度和强度」。

关键约束：分区与主谱图**共用同一横坐标**，否则竖线对不上上面的峰。
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

import numpy as np
import pytest
from PySide6 import QtCore

from xinmatch.core.model import Entry
from xinmatch.core.model.pattern import Pattern
from xinmatch.ui.pattern_view import X_MODE_D, PatternPanel
from xinmatch.ui.stick_lane import (
    ROW_FILL,
    LaneRow,
    StickLaneView,
    lane_row_from_entry,
)


def _synth(n: int = 1200) -> Pattern:
    x = np.linspace(5.0, 90.0, n)
    y = 20.0 + 800.0 * np.exp(-((x - 28.4) ** 2) / (2.0 * 0.15**2))
    return Pattern(two_theta=x, intensity=y, wavelength=1.5406)


def _entry(entry_id: str = "96-900-8213", formula: str = "MgCO3") -> Entry:
    return Entry(
        entry_id=entry_id,
        formula=formula,
        d_spacings=np.array([3.0, 2.0, 1.5], dtype=np.float64),
        intensities=np.array([100.0, 25.0, 4.0], dtype=np.float64),
    )


@pytest.fixture
def panel(qapp):
    widget = PatternPanel()
    widget.resize(820, 520)
    widget.show()
    qapp.processEvents()
    widget.add_pattern(_synth())
    yield widget
    widget.view.clear()
    widget.lane.set_rows([])
    widget.setParent(None)
    widget.deleteLater()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# 画的是不是"一根峰一条线"
# ---------------------------------------------------------------------------
def test_one_vertical_bar_per_reflection(panel):
    row = LaneRow("MgCO3", (21.0, 28.4, 40.0), (1.0, 0.5, 0.2))
    panel.set_confirmed_lane_rows([row])
    assert panel.lane.row_count() == 1

    curve = panel.lane.row_curve(0)
    assert curve is not None
    xs, ys = curve.getData()
    assert len(xs) == 6, "3 根竖线 = 6 个端点（connect=pairs）"
    # 竖线是垂直线段：x 成对相同，y 从行基线长到基线 + 高度占比。
    assert xs[0] == pytest.approx(xs[1]) == pytest.approx(21.0)
    assert ys[0] == pytest.approx(0.0)
    assert ys[1] == pytest.approx(ROW_FILL * 1.0)


def test_intensity_mode_keeps_relative_heights(panel):
    row = LaneRow("A", (21.0, 28.4), (1.0, 0.25))
    panel.set_confirmed_lane_rows([row])
    fractions = panel.lane.bar_fractions(0)
    assert fractions[0] == pytest.approx(ROW_FILL)
    assert fractions[1] == pytest.approx(ROW_FILL * 0.25)


def test_angle_only_mode_makes_every_bar_equal(panel):
    row = LaneRow("A", (21.0, 28.4, 40.0), (1.0, 0.25, 0.05))
    panel.set_confirmed_lane_rows([row])
    panel.lane.set_show_intensity(False)
    assert panel.lane.show_intensity() is False
    assert panel.lane.bar_fractions(0) == pytest.approx([ROW_FILL] * 3)

    xs, ys = panel.lane.row_curve(0).getData()
    heights = ys[1::2]
    assert heights == pytest.approx([ROW_FILL] * 3)


def test_intensity_toggle_emits_signal(panel):
    panel.set_confirmed_lane_rows([LaneRow("A", (21.0,), (1.0,))])
    seen: list[bool] = []
    panel.lane.intensity_toggled.connect(seen.append)
    panel.lane.set_show_intensity(False)
    assert seen == [False]


# ---------------------------------------------------------------------------
# 显示 / 隐藏与行序
# ---------------------------------------------------------------------------
def test_lane_hidden_when_there_are_no_rows(panel):
    assert panel.lane.isVisible() is False
    panel.set_confirmed_lane_rows([LaneRow("A", (21.0,), (1.0,))])
    panel.show()
    panel.lane.parentWidget().show()
    assert panel.lane.isVisible() is True
    panel.set_confirmed_lane_rows([])
    assert panel.lane.isVisible() is False


def test_candidate_row_is_drawn_on_top(panel):
    panel.set_confirmed_lane_rows([LaneRow("A", (21.0,), (1.0,))])
    panel.set_candidate_lane_row(
        LaneRow("B", (28.4,), (1.0,), candidate=True)
    )
    rows = panel.lane_rows()
    assert [r.label for r in rows] == ["B", "A"]
    assert rows[0].candidate is True
    assert rows[0].display_label().startswith("候选 ")

    panel.set_candidate_lane_row(None)
    assert [r.label for r in panel.lane_rows()] == ["A"]


# ---------------------------------------------------------------------------
# 与主谱图的横坐标联动
# ---------------------------------------------------------------------------
def test_lane_shares_x_range_with_pattern(panel):
    """同一 2θ 在谱图与分区里必须落在同一个像素列上（否则竖线对不上峰）。"""
    panel.set_confirmed_lane_rows([LaneRow("A", (28.4,), (1.0,))])
    panel.view.fit_data_range()
    panel.lane.sync_geometry()
    QtCore.QCoreApplication.processEvents()

    main_vb = panel.view.plotItem.vb
    lane_vb = panel.lane._plot.plotItem.vb
    main_x = main_vb.mapViewToScene(QtCore.QPointF(28.4, 0.0)).x()
    lane_x = lane_vb.mapViewToScene(QtCore.QPointF(28.4, 0.0)).x()
    assert abs(main_x - lane_x) <= 1.5


def test_lane_converts_positions_when_x_mode_switches_to_d(panel):
    panel.set_confirmed_lane_rows([LaneRow("A", (28.4,), (1.0,))])
    panel.x_combo.setCurrentIndex(1)  # d 值
    assert panel.view.x_mode() == X_MODE_D

    xs, _ys = panel.lane.row_curve(0).getData()
    expected = panel.view.x_display_of(28.4)
    assert xs[0] == pytest.approx(expected, rel=1e-6)
    assert expected != pytest.approx(28.4, rel=0.01), "d 模式没有做换算"


def test_left_axis_width_matches_pattern(panel):
    panel.set_confirmed_lane_rows([LaneRow("A", (21.0,), (1.0,))])
    panel.view.fit_data_range()
    panel.lane.sync_geometry()
    QtCore.QCoreApplication.processEvents()
    axis = panel.lane._plot.plotItem.getAxis("left")
    assert axis.fixedWidth == pytest.approx(panel.view.left_axis_width(), abs=3.0)


# ---------------------------------------------------------------------------
# 参考条目 → 行数据
# ---------------------------------------------------------------------------
def test_lane_row_from_entry_normalizes_and_converts():
    row = lane_row_from_entry(_entry(), 1.5406)
    assert row.label == "MgCO3"
    assert row.candidate is False
    assert len(row.positions) == 3
    assert row.heights[0] == pytest.approx(1.0)
    assert row.heights[1] == pytest.approx(0.25)
    # d = 3.0 Å → 2θ ≈ 29.8°，比 d = 2.0 Å 的角度小（d 越大角度越小）。
    assert row.positions[0] < row.positions[1]
    assert 29.0 < row.positions[0] < 30.5


def test_lane_row_from_entry_honours_overrides():
    row = lane_row_from_entry(
        _entry(), 1.5406, color="#123456", candidate=True, label="自定义", tooltip="T"
    )
    assert row.color == "#123456"
    assert row.candidate is True
    assert row.label == "自定义"
    assert row.display_label() == "候选 自定义"
    assert row.tooltip == "T"


def test_empty_row_is_tolerated(panel):
    """没有可用反射的相也要能占位（不画线，但不炸）。"""
    panel.set_confirmed_lane_rows([LaneRow("空相", (), ())])
    assert panel.lane.row_count() == 1
    assert panel.lane.row_curve(0) is None


def test_display_positions_fall_back_without_transform(qapp):
    """分区可脱离主视图单独用：宿主没有换算函数时按物理 2θ 直接画。"""
    import pyqtgraph as pg

    class _StubView:
        """只有 ``plotItem.vb`` 与 ``left_axis_width`` 的最小宿主。"""

        def __init__(self) -> None:
            self.plotItem = SimpleNamespace(vb=pg.ViewBox())

        @staticmethod
        def left_axis_width() -> int:
            return 40

    lane = StickLaneView(_StubView())
    lane.set_rows([LaneRow("A", (28.4, 40.0), (1.0, 0.5))])
    xs, _ys = lane.row_curve(0).getData()
    assert list(xs[::2]) == pytest.approx([28.4, 40.0])
    lane.setParent(None)
    lane.deleteLater()
    qapp.processEvents()
