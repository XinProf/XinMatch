"""Diffraction pattern graphics view (pyqtgraph).

T13.2 — Pattern view: multi-pattern overlay, zoom / pan, cursor tracking.

参考软件行为（docs/）：
- ``diffpattern_basics.md`` — the diffraction pattern graphics; multiple
  patterns are stacked on top of each other; the legend in the upper-right
  corner lists sample IDs / entry names.
- ``diffpattern_zoom.md`` — mouse-wheel zoom, rubber-band area zoom and
  double-click zoom (provided here by pyqtgraph's default ViewBox
  interaction: left-drag pans, wheel zooms).
- ``diffpattern_zoom_track.md`` — "tracking": shift the viewing area while
  holding Shift / the middle mouse button (pyqtgraph default pan).
- ``options_diffpattern.md`` — "vertical line at mouse cursor position"
  (here a full crosshair: horizontal + vertical InfiniteLine plus a live
  ``(2θ, I, d)`` readout label).

Architecture boundary: the view only consumes
:class:`xinmatch.core.model.pattern.Pattern` data objects and never calls
back into ``xinmatch.core`` logic.

Implementation note: we subclass :class:`pyqtgraph.PlotWidget` (a
GraphicsView that already owns a single PlotItem) rather than building a
GraphicsView by hand — pyqtgraph 0.14's ``autoDownsample``/``clipToView``
code caches the enclosing "view" while an item first enters the scene, and
the hand-built layout resolves that cache to the GraphicsView itself.

主题
----
谱图区背景 / 网格 / 轴 / crosshair / 读数颜色统一从
:data:`xinmatch.ui.theme.THEMES` 的 ``chart_*`` 语义令牌取色；
:meth:`apply_theme_colors` 幂等可反复调用，主窗口切换浅/深主题后会重新调用。
默认浅色主题下谱图区为近白背景（严禁黑色），深色主题下为深灰（非纯黑）。
"""

from __future__ import annotations

import contextlib
import itertools
import math

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtWidgets

from xinmatch.core.model.pattern import Pattern
from xinmatch.ui import theme as _theme

# Clean distinct colors for stacked patterns; no commercial visual assets used.
PATTERN_COLORS: tuple[str, ...] = (
    "#1f77b4",
    "#d62728",
    "#2ca02c",
    "#9467bd",
    "#ff7f0e",
    "#17becf",
    "#8c564b",
    "#e377c2",
)

# ---------------------------------------------------------------------------
# 轴显示模式（v1.3.1）：X 角度(2θ) ↔ d 值；Y 计数 ↔ 平方根 ↔ 对数。
# crosshair 读数恒显物理量（2θ / 原始计数 / d），与显示模式解耦。
# ---------------------------------------------------------------------------
X_MODE_TWO_THETA = "two_theta"
X_MODE_D = "d"
X_MODES: tuple[str, ...] = (X_MODE_TWO_THETA, X_MODE_D)

Y_MODE_COUNTS = "counts"
Y_MODE_SQRT = "sqrt"
Y_MODE_LOG = "log"
Y_MODES: tuple[str, ...] = (Y_MODE_COUNTS, Y_MODE_SQRT, Y_MODE_LOG)


class PatternView(pg.PlotWidget):
    """Widget displaying one or more overlaid experimental/reference patterns.

    Corresponds to the upper-left graphics panel in the reference software's
    working area (``docs/working_area.md``).
    """

    #: Emitted while the mouse moves over the plot; argument is the
    #: human-readable ``(2θ, I, d)`` string, mirrored into the status bar.
    cursor_moved = QtCore.Signal(str)

    def __init__(self, parent=None) -> None:
        """Set up the plot item, grid, legend and cursor crosshair."""
        super().__init__(parent)
        # pyqtgraph's PlotWidget assigns ``self.clear = self.plotItem.clear`` as
        # an *instance* attribute, which shadows the ``clear()`` override below.
        # Consequence (until v1.7.x): clear() emptied the plot but left every
        # entry in ``_records`` — ``patterns()`` kept reporting removed curves
        # and repeated open/preprocess cycles leaked records.  Drop the instance
        # attribute so our class-level clear() actually runs.
        self.__dict__.pop("clear", None)
        self._plot = self.plotItem
        self._plot.setLabel("bottom", "2θ", units="°")
        self._plot.setLabel("left", "Intensity", units="counts")
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        # 参考软件 zoom/tracking: left-drag pan, wheel zoom (diffpattern_zoom.md).
        self._plot.setMouseEnabled(x=True, y=True)

        # Upper-right legend listing each overlaid pattern (diffpattern_basics.md).
        self._legend = self._plot.addLegend(offset=(12, 12))

        # Crosshair: horizontal + vertical InfiniteLine following the mouse
        # (参考软件 "vertical line at mouse cursor position", options_diffpattern.md).
        self._vline = pg.InfiniteLine(angle=90, pen=pg.mkPen("#555555", dash=[4, 3]))
        self._hline = pg.InfiniteLine(angle=0, pen=pg.mkPen("#555555", dash=[4, 3]))
        self._plot.addItem(self._vline, ignoreBounds=True)
        self._plot.addItem(self._hline, ignoreBounds=True)
        self._readout = pg.TextItem(anchor=(0, 1), color="#222222")
        self._plot.addItem(self._readout, ignoreBounds=True)

        # 按当前主题设置谱图区配色（浅色默认近白背景）。
        self.apply_theme_colors()

        self._records: dict[str, dict] = {}
        self._counter = itertools.count(1)
        # v1.3.1：轴显示模式（默认 2θ / 计数）。
        self._x_mode = X_MODE_TWO_THETA
        self._y_mode = Y_MODE_COUNTS

        self.scene().sigMouseMoved.connect(self._on_scene_mouse_moved)

    # ------------------------------------------------------------------
    # Axis display modes (v1.3.1)
    # ------------------------------------------------------------------
    def x_mode(self) -> str:
        """当前 X 轴显示模式（:data:`X_MODES` 之一）。"""
        return self._x_mode

    def y_mode(self) -> str:
        """当前 Y 轴显示模式（:data:`Y_MODES` 之一）。"""
        return self._y_mode

    def set_x_mode(self, mode: str) -> None:
        """切换 X 轴显示：``two_theta``（角度）↔ ``d``（布拉格换算间距）。

        换算用各图谱自身波长：``d = λ / (2 sin θ)``，``θ = 2θ/2``。
        切换后重绘全部曲线并适配数据范围。
        """
        if mode not in X_MODES:
            raise ValueError(f"未知 X 轴模式: {mode!r}")
        self._x_mode = mode
        if mode == X_MODE_D:
            self._plot.setLabel("bottom", "d", units="Å")
        else:
            self._plot.setLabel("bottom", "2θ", units="°")
        self._refresh_all_curves()
        self.fit_data_range()

    def set_y_mode(self, mode: str) -> None:
        """切换 Y 轴显示：``counts``（原始计数）↔ ``sqrt`` ↔ ``log``（log₁₀）。

        切换后重绘全部曲线并适配数据范围；crosshair 读数仍显示原始计数。
        """
        if mode not in Y_MODES:
            raise ValueError(f"未知 Y 轴模式: {mode!r}")
        self._y_mode = mode
        if mode == Y_MODE_SQRT:
            self._plot.setLabel("left", "√Intensity")
        elif mode == Y_MODE_LOG:
            self._plot.setLabel("left", "log₁₀(Intensity)")
        else:
            self._plot.setLabel("left", "Intensity", units="counts")
        self._refresh_all_curves()
        self.fit_data_range()

    def _x_display(self, pattern: Pattern) -> np.ndarray:
        """物理 2θ 数组 → 当前 X 模式下的显示数组。"""
        two_theta = np.asarray(pattern.two_theta, dtype=float)
        if self._x_mode != X_MODE_D:
            return two_theta
        wavelength = float(pattern.wavelength) or 1.5406
        with np.errstate(divide="ignore", invalid="ignore"):
            d_values = wavelength / (2.0 * np.sin(np.radians(two_theta) / 2.0))
        return np.asarray(d_values, dtype=float)

    def _y_display(self, pattern: Pattern) -> np.ndarray:
        """物理强度数组 → 当前 Y 模式下的显示数组。"""
        intensity = np.asarray(pattern.intensity, dtype=float)
        if self._y_mode == Y_MODE_SQRT:
            return np.asarray(np.sqrt(np.clip(intensity, 0.0, None)), dtype=float)
        if self._y_mode == Y_MODE_LOG:
            return np.asarray(
                np.log10(np.where(intensity > 0.0, intensity, 1.0)), dtype=float
            )
        return intensity

    def _x_to_display(self, two_theta: float) -> float:
        """单个物理 2θ 值 → 当前 X 模式下的显示坐标（crosshair 定位用）。"""
        if self._x_mode != X_MODE_D:
            return two_theta
        wavelength = self._anchor_wavelength() or 1.5406
        sin_theta = math.sin(math.radians(two_theta) / 2.0)
        if sin_theta <= 0.0:
            return float("inf")
        return wavelength / (2.0 * sin_theta)

    def _y_to_display(self, intensity: float) -> float:
        """单个物理强度值 → 当前 Y 模式下的显示坐标。"""
        if self._y_mode == Y_MODE_SQRT:
            return math.sqrt(max(intensity, 0.0))
        if self._y_mode == Y_MODE_LOG:
            return math.log10(intensity) if intensity > 0.0 else 0.0
        return intensity

    def _refresh_all_curves(self) -> None:
        """按当前轴模式原地重绘全部曲线（``setData``，不增删 item）。"""
        for rec in self._records.values():
            curve = rec["curve"]
            pattern = rec["pattern"]
            curve.setData(
                self._x_display(pattern),
                self._y_display(pattern),
                connect="finite",
            )

    def fit_data_range(self) -> None:
        """X/Y 范围适配当前全部数据（打开数据 / 删数据 / 切轴后调用）。

        走 ``enableAutoRange + autoRange``：一次性按数据包围盒重算视野
        （带 pyqtgraph 默认边距），不永久锁定用户后续缩放。
        """
        self._plot.enableAutoRange()
        self._plot.vb.autoRange()

    # ------------------------------------------------------------------
    # Theming
    # ------------------------------------------------------------------
    def apply_theme_colors(self) -> None:
        """从当前主题的 ``chart_*`` 令牌重设谱图区配色（幂等）。

        读取 :data:`xinmatch.ui.theme.THEMES` 中 ``current_theme()`` 对应的
        chart_bg / chart_grid / chart_axis / chart_cursor / chart_text，
        设置背景、坐标轴 pen 与刻度文本 pen、crosshair 虚线 pen、读数文本色。
        可在主题切换后反复调用，不抛异常、不重复添加 item。
        """
        tokens = _theme.THEMES[_theme.current_theme()]
        # 谱图区背景。
        self.setBackground(tokens["chart_bg"])
        # 坐标轴 / 刻度文本 pen（pyqtgraph 网格线与轴 pen 同源，随轴色变暗/变亮）。
        axis_pen = pg.mkPen(tokens["chart_axis"])
        for axis_name in ("bottom", "left"):
            axis = self._plot.getAxis(axis_name)
            axis.setPen(axis_pen)
            axis.setTextPen(tokens["chart_axis"])
        # showGrid 保留，alpha 控制网格淡度（颜色随 chart_axis）。
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        # crosshair 虚线。
        cursor_pen = pg.mkPen(tokens["chart_cursor"], dash=[4, 3])
        self._vline.setPen(cursor_pen)
        self._hline.setPen(cursor_pen)
        # 读数文本色。
        self._readout.setColor(tokens["chart_text"])

    # ------------------------------------------------------------------
    # Pattern management
    # ------------------------------------------------------------------
    def add_pattern(self, pattern: Pattern, name: str | None = None,
                    color: str | None = None) -> str:
        """Overlay *pattern*; returns a handle used by :meth:`remove_pattern`.

        Multiple patterns are stacked on top of each other exactly like in
        The reference software (``diffpattern_basics.md``, "Multiple
        diffraction patterns").  Each curve uses ``autoDownsample`` +
        ``clipToView`` so that a 50 000-point trace stays responsive.
        """
        key = f"P{next(self._counter)}"
        label = name or str(pattern.metadata.get("sample_id") or f"Pattern {key}")
        pen_color = color or PATTERN_COLORS[len(self._records) % len(PATTERN_COLORS)]
        # NOTE: clipToView is enabled via opts *after* addItem.  On
        # pyqtgraph 0.13.x + PySide6 6.11, constructing with clipToView=True
        # makes the first synchronous viewRangeChanged() (fired while the
        # item enters the scene, before it is reparented to the ViewBox's
        # child group) resolve the enclosing GraphicsView as if it were the
        # ViewBox and crash in ``autoRangeEnabled()``.
        curve = pg.PlotDataItem(
            pattern.two_theta,
            pattern.intensity,
            pen=pg.mkPen(pen_color, width=1.2),
            name=label,
            autoDownsample=True,
            connect="all",
        )
        self._plot.addItem(curve)
        curve.opts["clipToView"] = True
        self._legend.addItem(curve, label)
        self._records[key] = {
            "pattern": pattern,
            "curve": curve,
            "name": label,
            "color": pen_color,
        }
        # v1.3.1：打开数据后 X 轴范围随数据自行调整。
        self.fit_data_range()
        return key

    def remove_pattern(self, key: str) -> None:
        """Remove the pattern previously added under *key* (no-op if absent)."""
        rec = self._records.pop(key, None)
        if rec is None:
            return
        self._plot.removeItem(rec["curve"])
        with contextlib.suppress(KeyError, ValueError):
            self._legend.removeItem(rec["name"])
        self.fit_data_range()

    def patterns(self) -> dict[str, Pattern]:
        """Mapping of handle -> :class:`Pattern` currently displayed."""
        return {k: v["pattern"] for k, v in self._records.items()}

    def clear(self) -> None:
        """Remove all overlaid patterns."""
        for key in list(self._records):
            self.remove_pattern(key)

    # ------------------------------------------------------------------
    # Cursor tracking
    # ------------------------------------------------------------------
    def set_crosshair_position(self, x: float, y: float) -> None:
        """Place the crosshair at **物理坐标** (*x* = 2θ°, *y* = 原始计数)。

        v1.3.1：轴切到 d / 平方根 / 对数后，本函数入参仍是物理量——
        内部换算到当前显示坐标定位十字线，读数标签恒显
        ``(2θ, I, d)`` 物理值（d 由锚图谱波长按布拉格定律换算），
        并发出 :attr:`cursor_moved`（主窗口镜像到状态栏）。
        """
        self._vline.setPos(self._x_to_display(x))
        self._hline.setPos(self._y_to_display(y))
        wavelength = self._anchor_wavelength()
        d = math.nan
        if wavelength and 0.0 < x < 180.0:
            sin_theta = math.sin(math.radians(x) / 2.0)
            if sin_theta > 0.0:
                d = wavelength / (2.0 * sin_theta)
        text = f"2θ = {x:8.3f}°   I = {y:12.1f}   d = {d:7.3f} Å"
        self._readout.setText(text)
        (x0, x1), (y0, y1) = self._plot.vb.viewRange()
        self._readout.setPos(x0 + (x1 - x0) * 0.01, y1 - (y1 - y0) * 0.02)
        self.cursor_moved.emit(text)

    def _anchor_wavelength(self) -> float:
        """Wavelength of the bottom-most ("anchor") pattern."""
        for rec in self._records.values():
            return float(rec["pattern"].wavelength)
        return 0.0

    def _on_scene_mouse_moved(self, scene_pos) -> None:
        """Map a scene-coordinate mouse event to data coords and update.

        v1.3.1：鼠标给的是**显示坐标**（d / log 模式下亦然），先换算回
        物理量（2θ / 原始计数）再交给 :meth:`set_crosshair_position`，
        保证读数与状态栏恒为物理值。
        """
        view_pos = self._plot.vb.mapSceneToView(scene_pos)
        (x0, x1), (y0, y1) = self._plot.vb.viewRange()
        x_disp, y_disp = view_pos.x(), view_pos.y()
        if not (x0 <= x_disp <= x1 and y0 <= y_disp <= y1):
            return
        if self._x_mode == X_MODE_D:
            wavelength = self._anchor_wavelength() or 1.5406
            ratio = wavelength / (2.0 * x_disp) if x_disp > 0 else 2.0
            ratio = min(max(ratio, -1.0), 1.0)
            x_phys = 2.0 * math.degrees(math.asin(ratio))
        else:
            x_phys = x_disp
        if self._y_mode == Y_MODE_SQRT:
            y_phys = y_disp * y_disp
        elif self._y_mode == Y_MODE_LOG:
            y_phys = 10.0**y_disp
        else:
            y_phys = y_disp
        self.set_crosshair_position(x_phys, y_phys)


class PatternPanel(QtWidgets.QWidget):
    """谱图区面板（v1.3.1）：轴切换控制条 + :class:`PatternView`。

    顶上一行控制条：X 轴（2θ / d 值）、Y 轴（计数 / 平方根 / 对数）、
    「适应数据范围」按钮；下方为 pyqtgraph 视图。周期表面板从主工作区
    挪到侧坞后，这里把更多显示空间留给谱图本身。
    """

    #: 转发视图的 crosshair 读数（物理量文本），供主窗口镜像到状态栏。
    cursor_moved = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.view = PatternView()

        self.x_combo = QtWidgets.QComboBox()
        self.x_combo.addItems(["2θ (角度)", "d 值"])
        self.x_combo.setToolTip("X 轴显示：衍射角 2θ 或 Bragg 换算的 d 值")
        self.y_combo = QtWidgets.QComboBox()
        self.y_combo.addItems(["计数", "平方根", "对数"])
        self.y_combo.setToolTip("Y 轴显示：原始计数、平方根或对数（log₁₀）")
        self.fit_button = QtWidgets.QPushButton("适应数据范围")
        self.fit_button.setToolTip("按当前全部数据重新适配 X/Y 显示范围")

        bar = QtWidgets.QHBoxLayout()
        bar.setContentsMargins(4, 2, 4, 2)
        bar.addWidget(QtWidgets.QLabel("X 轴:"))
        bar.addWidget(self.x_combo)
        bar.addWidget(QtWidgets.QLabel("Y 轴:"))
        bar.addWidget(self.y_combo)
        bar.addStretch(1)
        bar.addWidget(self.fit_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(bar)
        layout.addWidget(self.view, stretch=1)

        self.x_combo.currentIndexChanged.connect(self._on_x_changed)
        self.y_combo.currentIndexChanged.connect(self._on_y_changed)
        self.fit_button.clicked.connect(self.view.fit_data_range)
        self.view.cursor_moved.connect(self.cursor_moved)

    def _on_x_changed(self, index: int) -> None:
        self.view.set_x_mode(X_MODE_D if index == 1 else X_MODE_TWO_THETA)

    def _on_y_changed(self, index: int) -> None:
        mode = Y_MODES[index] if 0 <= index < len(Y_MODES) else Y_MODE_COUNTS
        self.view.set_y_mode(mode)

    # ------------------------------------------------------------------
    # Drop-in 代理：主窗口 / 旧调用点可直接用 PatternPanel 当视图用
    # ------------------------------------------------------------------
    def add_pattern(self, pattern: Pattern, name: str | None = None,
                    color: str | None = None) -> str:
        """代理到内部视图的 :meth:`PatternView.add_pattern`。"""
        return self.view.add_pattern(pattern, name=name, color=color)

    def remove_pattern(self, key: str) -> None:
        """代理到内部视图的 :meth:`PatternView.remove_pattern`。"""
        self.view.remove_pattern(key)

    def clear(self) -> None:
        """代理到内部视图的 :meth:`PatternView.clear`。"""
        self.view.clear()

    def patterns(self) -> dict[str, Pattern]:
        """代理到内部视图的 :meth:`PatternView.patterns`。"""
        return self.view.patterns()

    def apply_theme_colors(self) -> None:
        """代理到内部视图的 :meth:`PatternView.apply_theme_colors`。"""
        self.view.apply_theme_colors()
