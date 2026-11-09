"""谱图下方的参考线条（stick）分区（v3.6.2）。

需求来源（用户报障/需求，2026-11-08）：候选列表里选中一个物相时，希望在
**主谱图下方的独立行区**里看到该相的峰位与强度，和上面的实测谱对照着判断
"这个相到底能不能对上"；已确认的物相也要一并列在这里，以便查漏——**有没有
峰还没被任何物相匹配**。

布局
----
每一相占一行：左侧是物相名（默认取化学式，如 ``MgCO3``），行内是从行基线
向上生长的竖线，横坐标与主谱图**共用同一套 X 范围**（``setXLink``），因此
竖线正上方就是谱图里的对应峰位。行间有淡色分隔线。

两种显示模式（鼠标勾选）
------------------------
- 勾选「同时显示峰强」（默认）：竖线高度 = 该峰相对强度（行内归一化），
  一眼看出强峰弱峰；
- 取消勾选：所有竖线等高，只保留角度位置，避免弱线几乎看不见。

横坐标对齐
----------
参考线分区必须与主谱图**像素级对齐**，否则竖线对不上上面的峰。做法是把
本区左侧坐标轴宽度同步成主谱图左轴宽度（``sync_geometry``）；底部坐标轴
隐藏，不占额外内边距。X 轴模式（2θ / d 值）由 :class:`~xinmatch.ui.
pattern_view.PatternView` 的换算函数统一提供，切换轴后本区同步重画。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets

from xinmatch.core.search.correlate import d_to_two_theta
from xinmatch.ui import theme as _theme

__all__ = ["CANDIDATE_COLOR", "LaneRow", "StickLaneView", "lane_row_from_entry"]

#: "候选相预览行"的竖线颜色（虚线绘制；与主谱图参考线条的调色板刻意错开，
#: 避免把预览行误读成某个已确认相）。
CANDIDATE_COLOR = "#ff7f0e"

#: 每行像素高与表头高（分区总高 = 表头 + 行数 × 行高）。
ROW_HEIGHT = 20
HEADER_HEIGHT = 22

#: 竖线最大高度占行高的比例（留一点上边距，行间不粘连）。
ROW_FILL = 0.86

#: 标签框相对视场左边缘的横坐标偏移（视场宽度的比例）。
_LABEL_INSET = 0.006


@dataclass(frozen=True)
class LaneRow:
    """参考线条分区里的一行（一个物相）。

    Attributes
    ----------
    label:
        行首标签，通常为化学式（如 ``"MgCO3"``）。
    positions:
        峰位，**物理 2θ 角度**；显示时按当前 X 轴模式换算。
    heights:
        相对强度 ``0..1``，须与 *positions* 等长。
    color:
        竖线颜色；默认沿用主谱图参考线条的调色板顺序，便于两处对照。
    tooltip:
        行标签的悬浮说明（条目号 / 完整化学式等）。
    candidate:
        ``True`` 表示这是"候选列表里高亮的相"的预览行（虚线绘制 + 标注
        「候选」），与已确认相匹配行区分。
    """

    label: str
    positions: tuple[float, ...]
    heights: tuple[float, ...]
    color: str = "#1f77b4"
    tooltip: str = ""
    candidate: bool = False
    extra: dict = field(default_factory=dict, compare=False)

    def display_label(self) -> str:
        """行首显示文本（候选行加「候选」前缀）。"""
        return f"候选 {self.label}" if self.candidate else self.label


def lane_row_from_entry(
    entry,
    wavelength: float,
    *,
    color: str = "#1f77b4",
    candidate: bool = False,
    label: str | None = None,
    tooltip: str = "",
) -> LaneRow:
    """把参考条目转成一行参考线条（d 值 → 2θ，强度归一化到 ``0..1``）。

    与主谱图里叠加的参考线条（"高度 = 比例因子 × 相对强度"）不同，这里用
    **行内归一化**：一行里最强的那根竖线占满行高，其余按比例缩放。参考线
    分区的用途是"这相的峰位落在哪、强线是哪几条"，与绝对计数无关。
    """
    positions: list[float] = []
    intensities: list[float] = []
    for d_value, intensity in zip(entry.d_spacings, entry.intensities, strict=True):
        two_theta = d_to_two_theta(float(d_value), wavelength)
        if not math.isfinite(two_theta):
            continue
        positions.append(float(two_theta))
        intensities.append(float(intensity))
    peak = max(intensities) if intensities else 0.0
    heights = tuple(value / peak for value in intensities) if peak > 0 else ()
    return LaneRow(
        label=label or (getattr(entry, "formula", "") or entry.entry_id),
        positions=tuple(positions),
        heights=heights,
        color=color,
        tooltip=tooltip or f"{entry.entry_id} {getattr(entry, 'formula', '')}".strip(),
        candidate=candidate,
    )


class StickLaneView(QtWidgets.QWidget):
    """谱图下方的参考线条分区：一行一个物相，X 轴与主谱图联动。"""

    #: 「同时显示峰强」勾选状态变化（``True`` = 显示强度）。
    intensity_toggled = QtCore.Signal(bool)

    def __init__(self, view, parent: QtWidgets.QWidget | None = None) -> None:
        """*view* 为主谱图 :class:`~xinmatch.ui.pattern_view.PatternView`。"""
        super().__init__(parent)
        self._view = view
        self._rows: list[LaneRow] = []
        self._items: list = []
        self._labels: list[tuple[pg.TextItem, float]] = []
        self._row_curves: list[pg.PlotDataItem | None] = []
        self._show_intensity = True

        self._title = QtWidgets.QLabel("参考线")
        self._title.setToolTip(
            "候选列表里高亮的物相 + 已确认的物相，峰位与主谱图共用横坐标"
        )
        self._check = QtWidgets.QCheckBox("同时显示峰强")
        self._check.setChecked(True)
        self._check.setToolTip(
            "勾选：竖线高度反映参考峰相对强度；取消：所有竖线等高，只看角度位置"
        )
        self._check.toggled.connect(self._on_intensity_toggled)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(6, 0, 6, 0)
        header.setSpacing(8)
        header.addWidget(self._title)
        header.addStretch(1)
        header.addWidget(self._check)

        self._plot = pg.PlotWidget()
        self._plot.setMenuEnabled(False)
        self._plot.hideAxis("bottom")
        self._plot.plotItem.getAxis("left").setStyle(showValues=False, tickLength=0)
        self._plot.plotItem.hideButtons()
        # 横向可平移（X 与主谱图联动，实际由主谱图驱动）；纵向固定给行号。
        self._plot.setMouseEnabled(x=True, y=False)
        self._plot.plotItem.vb.setXLink(view.plotItem.vb)
        self._plot.plotItem.vb.setMouseMode(pg.ViewBox.PanMode)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addWidget(self._plot, stretch=1)

        self._plot.plotItem.vb.sigRangeChanged.connect(self._on_x_range_changed)
        self.apply_theme_colors()
        self.setVisible(False)

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------
    def set_rows(self, rows: list[LaneRow]) -> None:
        """整体替换行数据并重画；空列表时整个分区隐藏。"""
        self._rows = list(rows)
        self._redraw()
        visible = bool(self._rows)
        self.setVisible(visible)
        if visible:
            self.setFixedHeight(HEADER_HEIGHT + ROW_HEIGHT * len(self._rows))

    def rows(self) -> list[LaneRow]:
        """当前行数据（按显示顺序）。"""
        return list(self._rows)

    def row_count(self) -> int:
        """行数。"""
        return len(self._rows)

    def show_intensity(self) -> bool:
        """是否显示峰强（``False`` = 只显示角度位置）。"""
        return self._show_intensity

    def set_show_intensity(self, enabled: bool) -> None:
        """设置「同时显示峰强」并同步复选框。"""
        self._check.setChecked(bool(enabled))

    def bar_fractions(self, row_index: int) -> list[float]:
        """第 *row_index* 行每条竖线的高度占比（测试与自检用）。

        勾选峰强时各条按相对强度不等高，取消勾选时全为 :data:`ROW_FILL`。
        """
        if not 0 <= row_index < len(self._rows):
            raise IndexError(row_index)
        row = self._rows[row_index]
        if not self._show_intensity:
            return [ROW_FILL] * len(row.heights)
        return [ROW_FILL * float(h) for h in row.heights]

    def row_curve(self, row_index: int) -> pg.PlotDataItem | None:
        """第 *row_index* 行的竖线图元（``connect="pairs"`` 的 PlotDataItem）。"""
        if not 0 <= row_index < len(self._row_curves):
            return None
        return self._row_curves[row_index]

    def refresh(self) -> None:
        """按当前 X 轴模式重画（主谱图切 2θ ↔ d 值后调用）。"""
        self._redraw()

    def apply_theme_colors(self) -> None:
        """按当前主题重设背景 / 分隔线 / 标签配色（幂等）。"""
        tokens = _theme.THEMES[_theme.current_theme()]
        self._plot.setBackground(tokens["chart_bg"])
        self._title.setStyleSheet(f"color: {tokens['chart_text']};")
        self._redraw()

    def sync_geometry(self) -> None:
        """把左侧坐标轴宽度对齐主谱图（保证竖线与上方的峰同列）。

        用 ``AxisItem.fixedWidth`` 而不是 ``width()`` 判断是否需要改：后者是
        当前几何宽度，布局还没跑时拿不到刚设的约束，会反复重设。
        """
        width = max(int(self._view.left_axis_width()), 1)
        axis = self._plot.plotItem.getAxis("left")
        if axis.fixedWidth != width:
            axis.setWidth(width)

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------
    def _on_intensity_toggled(self, enabled: bool) -> None:
        self._show_intensity = bool(enabled)
        self._redraw()
        self.intensity_toggled.emit(self._show_intensity)

    def _clear_items(self) -> None:
        for item in self._items:
            self._plot.removeItem(item)
        self._items.clear()
        self._labels.clear()
        self._row_curves.clear()

    def _redraw(self) -> None:
        """按当前行数据 / 模式 / 主题重建全部图元。"""
        self._clear_items()
        count = len(self._rows)
        if count == 0:
            return
        tokens = _theme.THEMES[_theme.current_theme()]
        # 行间分隔线（第 0..count 条边界）。
        separator_pen = pg.mkPen(tokens["chart_grid"], width=1)
        for boundary in range(count + 1):
            line = pg.InfiniteLine(pos=float(boundary), angle=0, pen=separator_pen)
            self._plot.addItem(line, ignoreBounds=True)
            self._items.append(line)

        for index, row in enumerate(self._rows):
            baseline = float(count - 1 - index)  # 第 0 行在最上面
            curve = self._draw_row(row, baseline)
            self._row_curves.append(curve)
            if curve is not None:
                self._items.append(curve)
            self._items.append(self._draw_label(row, baseline + 0.5))

        self._plot.plotItem.vb.setYRange(0.0, float(count), padding=0)
        self.sync_geometry()
        self._place_labels()

    def _display_positions(self, row: LaneRow) -> list[float]:
        """物理 2θ → 当前横轴显示坐标（d 值模式下由主视图换算）。"""
        convert = getattr(self._view, "x_display_of", None)
        if convert is None:
            return [float(x) for x in row.positions]
        out: list[float] = []
        for two_theta in row.positions:
            value = float(convert(float(two_theta)))
            if value == value and abs(value) != float("inf"):
                out.append(value)
        return out

    def _draw_row(self, row: LaneRow, baseline: float) -> pg.PlotDataItem | None:
        """画一行的竖线（``connect="pairs"``：每条线两个端点）。"""
        xs = self._display_positions(row)
        heights = list(row.heights)[: len(xs)]
        if not xs:
            return None
        style = (
            QtCore.Qt.PenStyle.DashLine
            if row.candidate
            else QtCore.Qt.PenStyle.SolidLine
        )
        pen = pg.mkPen(row.color, width=1.6, style=style)
        x_pairs: list[float] = []
        y_pairs: list[float] = []
        for x, height in zip(xs, heights, strict=False):
            fraction = ROW_FILL * (float(height) if self._show_intensity else 1.0)
            x_pairs.extend([x, x])
            y_pairs.extend([baseline, baseline + fraction])
        curve = pg.PlotDataItem(x_pairs, y_pairs, pen=pen, connect="pairs")
        self._plot.addItem(curve, ignoreBounds=True)
        return curve

    def _draw_label(self, row: LaneRow, y: float) -> pg.TextItem:
        """行首标签：贴着视场左边缘，带半透明底以便压在竖线上仍可读。"""
        tokens = _theme.THEMES[_theme.current_theme()]
        fill = QtGui.QColor(tokens["chart_bg"])
        fill.setAlpha(210)
        item = pg.TextItem(
            row.display_label(),
            color=tokens["chart_text"],
            anchor=(0, 0.5),
            fill=pg.mkBrush(fill),
        )
        if row.tooltip:
            item.setToolTip(row.tooltip)
        self._plot.addItem(item, ignoreBounds=True)
        self._labels.append((item, y))
        return item

    def _place_labels(self) -> None:
        """把标签横坐标贴到当前视场左边缘（平移 / 缩放后调用）。"""
        if not self._labels:
            return
        (x0, x1), _ = self._plot.plotItem.vb.viewRange()
        x = x0 + (x1 - x0) * _LABEL_INSET
        for item, y in self._labels:
            item.setPos(x, y)

    def _on_x_range_changed(self, *_args) -> None:
        self._place_labels()
