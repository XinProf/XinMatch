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

import itertools
import math

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets

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

# ---------------------------------------------------------------------------
# 谱图工具模式（v3.6.2）：图标行里的"可保持选中"工具，语义对齐姊妹项目
# XinRefinement 的 ``gui/plot_tools.py``。
# ---------------------------------------------------------------------------
TOOL_ZOOM_X = "zoom_x"
TOOL_ZOOM_Y = "zoom_y"
TOOL_ZOOM_RECT = "zoom_rect"
TOOL_CROSSHAIR = "crosshair"
PLOT_TOOL_MODES: tuple[str, ...] = (
    TOOL_ZOOM_X,
    TOOL_ZOOM_Y,
    TOOL_ZOOM_RECT,
    TOOL_CROSSHAIR,
)

#: 轴提示文案（点击可切显示，故写进 tooltip）。
_AXIS_HINT = "左键切换显示，右键选择"


class _PatternViewBox(pg.ViewBox):
    """ViewBox 扩展：框选时可锁定某一轴（``zoom_x`` / ``zoom_y``）。

    pyqtgraph 0.13.7 在 ``RectMode`` 下的 ``mouseDragEvent`` **不看**
    ``mouseEnabled``（``ViewBox.py:1332`` 直接走 ``showAxRect``），所以
    ``setMouseEnabled(x=False)`` 并不能实现"只改纵轴"的框选——那个开关只
    影响平移。这里改在 ``showAxRect`` 处把不参与缩放的那一轴换回当前视野；
    ``ViewBox.setRange`` 用 ``min/max`` 取值，因此传进去的矩形无需先归一化。
    """

    #: 缩放完成信号：参数为被锁定的轴（``"x"`` / ``"y"`` / ``None"``）。
    axis_rect_applied = QtCore.Signal(object)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        #: 被锁定、不参与框选的轴：``None`` / ``"x"`` / ``"y"``。
        self.axis_lock: str | None = None

    def showAxRect(self, ax, **kwargs) -> None:  # noqa: N802 (pyqtgraph 命名)
        """按 ``axis_lock`` 把框选矩形"撑开"成整幅，再交给父类应用。

        锁定某一轴时**不加边距**（``padding=0``）：被锁的那一轴要原样保留，
        而 pyqtgraph 默认的 2% 边距会把它也一起撑开，锁定就白做了。
        """
        rect = QtCore.QRectF(ax).normalized()
        (x0, x1), (y0, y1) = self.viewRange()
        if self.axis_lock == "y":
            rect = QtCore.QRectF(rect.left(), y0, rect.width(), y1 - y0)
        elif self.axis_lock == "x":
            rect = QtCore.QRectF(x0, rect.top(), x1 - x0, rect.height())
        if self.axis_lock is not None:
            kwargs.setdefault("padding", 0)
        super().showAxRect(rect, **kwargs)
        self.axis_rect_applied.emit(self.axis_lock)


class ClickableAxisItem(pg.AxisItem):
    """可点击的坐标轴（v3.6.2）：左键循环、右键弹出模式菜单。

    pyqtgraph 的 ``AxisItem`` 是纯 ``GraphicsWidget``，默认不接受鼠标按键，
    必须显式 ``setAcceptedMouseButtons`` 才能收到 ``mousePressEvent``。
    事件只发出按键，具体"切到哪个模式"由 :class:`PatternPanel` 决定——
    面板里的下拉框仍是模式的唯一真相源（只是被隐藏了）。
    """

    #: 轴被按下：参数为 :class:`QtCore.Qt.MouseButton`。
    clicked = QtCore.Signal(object)

    def __init__(self, orientation: str, **kwargs) -> None:
        super().__init__(orientation, **kwargs)
        self.setAcceptedMouseButtons(
            QtCore.Qt.MouseButton.LeftButton | QtCore.Qt.MouseButton.RightButton
        )
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setToolTip(_AXIS_HINT)

    def mousePressEvent(self, ev) -> None:  # noqa: N802 (Qt 命名)
        """把左/右键按下转成 :attr:`clicked`，其余照旧忽略。"""
        button = ev.button()
        if button in (
            QtCore.Qt.MouseButton.LeftButton,
            QtCore.Qt.MouseButton.RightButton,
        ):
            ev.accept()
            self.clicked.emit(button)
            return
        super().mousePressEvent(ev)


class PatternView(pg.PlotWidget):
    """Widget displaying one or more overlaid experimental/reference patterns.

    Corresponds to the upper-left graphics panel in the reference software's
    working area (``docs/working_area.md``).
    """

    #: Emitted while the mouse moves over the plot; argument is the
    #: human-readable ``(2θ, I, d)`` string, mirrored into the status bar.
    cursor_moved = QtCore.Signal(str)

    #: 横轴 / 纵轴被点击（v3.6.2）；参数为 :class:`QtCore.Qt.MouseButton`。
    x_axis_clicked = QtCore.Signal(object)
    y_axis_clicked = QtCore.Signal(object)

    #: 轴显示模式变更（参数为新模式字符串），供联动组件（参考线分区）刷新。
    x_mode_changed = QtCore.Signal(str)
    y_mode_changed = QtCore.Signal(str)

    def __init__(self, parent=None) -> None:
        """Set up the plot item, grid, legend and cursor crosshair."""
        self._viewbox = _PatternViewBox()
        self._bottom_axis = ClickableAxisItem("bottom")
        self._left_axis = ClickableAxisItem("left")
        super().__init__(
            parent,
            viewBox=self._viewbox,
            axisItems={"bottom": self._bottom_axis, "left": self._left_axis},
        )
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
        # v3.1.0：参考线条（"stick"）叠加层，独立于实验曲线存放，
        # 便于按相位增删而不动 _records。
        self._sticks: dict[str, dict] = {}
        self._counter = itertools.count(1)
        # v1.3.1：轴显示模式（默认 2θ / 计数）。
        self._x_mode = X_MODE_TWO_THETA
        self._y_mode = Y_MODE_COUNTS
        # v3.6.2：谱图工具（默认十字线读数，保持改造前的既有体验）。
        self._tool: str | None = TOOL_CROSSHAIR

        self._bottom_axis.clicked.connect(self.x_axis_clicked)
        self._left_axis.clicked.connect(self.y_axis_clicked)
        self._viewbox.axis_rect_applied.connect(self._on_axis_rect_applied)
        self.scene().sigMouseMoved.connect(self._on_scene_mouse_moved)
        # 把默认工具落到 ViewBox 上（十字线可见 + 平移模式），使初始状态显式。
        self.set_plot_tool(TOOL_CROSSHAIR)

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
            self._bottom_axis.setToolTip(f"当前：d 值（Å）｜{_AXIS_HINT}")
        else:
            self._plot.setLabel("bottom", "2θ", units="°")
            self._bottom_axis.setToolTip(f"当前：衍射角 2θ｜{_AXIS_HINT}")
        self._refresh_all_curves()
        self.fit_data_range()
        self.x_mode_changed.emit(mode)

    def set_y_mode(self, mode: str) -> None:
        """切换 Y 轴显示：``counts``（原始计数）↔ ``sqrt`` ↔ ``log``（log₁₀）。

        切换后重绘全部曲线并适配数据范围；crosshair 读数仍显示原始计数。
        """
        if mode not in Y_MODES:
            raise ValueError(f"未知 Y 轴模式: {mode!r}")
        self._y_mode = mode
        if mode == Y_MODE_SQRT:
            self._plot.setLabel("left", "√Intensity")
            self._left_axis.setToolTip(f"当前：平方根强度｜{_AXIS_HINT}")
        elif mode == Y_MODE_LOG:
            self._plot.setLabel("left", "log₁₀(Intensity)")
            self._left_axis.setToolTip(f"当前：对数强度｜{_AXIS_HINT}")
        else:
            self._plot.setLabel("left", "Intensity", units="counts")
            self._left_axis.setToolTip(f"当前：原始计数｜{_AXIS_HINT}")
        self._refresh_all_curves()
        self.fit_data_range()
        self.y_mode_changed.emit(mode)

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
        self._refresh_all_sticks()

    def fit_data_range(self) -> None:
        """X/Y 范围适配当前全部数据（打开数据 / 删数据 / 切轴后调用）。

        走 ``enableAutoRange + autoRange``：一次性按数据包围盒重算视野
        （带 pyqtgraph 默认边距），不永久锁定用户后续缩放。
        """
        self._plot.enableAutoRange()
        self._plot.vb.autoRange()

    # ------------------------------------------------------------------
    # 视图操作（v3.6.2 — 谱图快捷图标行）
    # ------------------------------------------------------------------
    def data_bounds(self) -> QtCore.QRectF | None:
        """全部曲线的数据包围盒（显示坐标）；无数据时返回 ``None``。

        不能指望 ``ViewBox.autoRange()``：曲线带 ``clipToView`` 时它只看当前
        窗口内的点，缩放过一次之后就再也"复位"不回去了。
        """
        low_x = low_y = math.inf
        high_x = high_y = -math.inf
        for rec in self._records.values():
            pattern = rec["pattern"]
            xs = self._x_display(pattern)
            ys = self._y_display(pattern)
            mask = np.isfinite(xs) & np.isfinite(ys)
            if not bool(mask.any()):
                continue
            low_x = min(low_x, float(xs[mask].min()))
            high_x = max(high_x, float(xs[mask].max()))
            low_y = min(low_y, float(ys[mask].min()))
            high_y = max(high_y, float(ys[mask].max()))
        if not (low_x < high_x and low_y < high_y):
            return None
        return QtCore.QRectF(low_x, low_y, high_x - low_x, high_y - low_y)

    def reset_view(self) -> None:
        """恢复默认视场：横轴覆盖全量数据、纵轴贴合全谱。"""
        bounds = self.data_bounds()
        if bounds is None:
            self.fit_data_range()
            return
        self._plot.vb.setRange(bounds, padding=0.02)

    def pan_x(self, frac: float) -> None:
        """视野沿横轴平移 ``frac`` × 当前视场宽度（正数向右）。"""
        (x0, x1), _ = self._plot.vb.viewRange()
        shift = (x1 - x0) * float(frac)
        self._plot.vb.setXRange(x0 + shift, x1 + shift, padding=0)

    def zoom_scale(self, factor: float) -> None:
        """以视场中心为锚点缩放横轴（``factor < 1`` 放大），纵轴随之贴合数据。

        纵轴不按同一比例缩放：谱图的纵向动态范围随横轴窗口变化极大，
        固定比例缩放在弱峰区会立刻把曲线推出视野。
        """
        (x0, x1), _ = self._plot.vb.viewRange()
        center = (x0 + x1) / 2.0
        half = (x1 - x0) * float(factor) / 2.0
        self._plot.vb.setXRange(center - half, center + half, padding=0)
        self.fit_y_range()

    def fit_y_range(self) -> None:
        """把纵轴贴合"当前横轴窗口内"的数据包络（纵向框选 / 步进缩放后用）。"""
        (x0, x1), _ = self._plot.vb.viewRange()
        low = math.inf
        high = -math.inf
        for rec in self._records.values():
            pattern = rec["pattern"]
            xs = self._x_display(pattern)
            ys = self._y_display(pattern)
            mask = (xs >= x0) & (xs <= x1) & np.isfinite(ys)
            if not bool(mask.any()):
                continue
            low = min(low, float(ys[mask].min()))
            high = max(high, float(ys[mask].max()))
        if not (low < high):
            return
        pad = (high - low) * 0.05
        self._plot.vb.setYRange(low - pad, high + pad, padding=0)

    def tool(self) -> str | None:
        """当前选中的谱图工具（:data:`PLOT_TOOL_MODES` 之一或 ``None``）。"""
        return self._tool

    def set_plot_tool(self, tool: str | None) -> None:
        """切换谱图工具：框选按轴 / 区域 / 十字线（``None`` = 平移）。

        - ``zoom_x`` / ``zoom_y``：``RectMode`` + 锁定另一轴（见
          :class:`_PatternViewBox`），横向框选后纵轴自动贴合新窗口数据；
        - ``zoom_rect``：默认矩形缩放（两轴同时改）；
        - ``crosshair``：平移模式 + 显示十字线与读数；
        - ``None``：仅平移（十字线隐藏）。
        """
        if tool is not None and tool not in PLOT_TOOL_MODES:
            raise ValueError(f"未知谱图工具: {tool!r}")
        self._tool = tool
        vb = self._viewbox
        if tool == TOOL_ZOOM_X:
            vb.axis_lock = "y"
            vb.setMouseMode(pg.ViewBox.RectMode)
        elif tool == TOOL_ZOOM_Y:
            vb.axis_lock = "x"
            vb.setMouseMode(pg.ViewBox.RectMode)
        elif tool == TOOL_ZOOM_RECT:
            vb.axis_lock = None
            vb.setMouseMode(pg.ViewBox.RectMode)
        else:
            vb.axis_lock = None
            vb.setMouseMode(pg.ViewBox.PanMode)
        self.set_crosshair_visible(tool == TOOL_CROSSHAIR)

    def set_crosshair_visible(self, visible: bool) -> None:
        """显示 / 隐藏十字线与读数标签（框选时隐藏以免干扰拉框）。"""
        for item in (self._vline, self._hline, self._readout):
            item.setVisible(bool(visible))

    def crosshair_visible(self) -> bool:
        """十字线当前是否可见。"""
        return bool(self._readout.isVisible())

    def _on_axis_rect_applied(self, axis: str | None) -> None:
        """横向框选结束后让纵轴贴合新窗口（``zoom_x`` 的"纵轴自动"语义）。"""
        if axis == "y":
            self.fit_y_range()

    def x_display_of(self, two_theta: float) -> float:
        """物理 2θ → 当前横轴显示坐标（联动谱图下方的参考线分区用）。"""
        return self._x_to_display(float(two_theta))

    def left_axis_width(self) -> int:
        """左侧坐标轴当前像素宽度（供参考线分区对齐横坐标）。"""
        return int(self._left_axis.width())

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
        # NOTE (2026-11-08): ``PlotItem.addItem()`` already appends *curve* to
        # the legend on its own -- it calls ``legend.addItem(item, name=item.name())``
        # whenever the item implements ``plotData`` and carries a name
        # (pyqtgraph 0.13.7, PlotItem.py:516-552).  Calling
        # ``self._legend.addItem(...)`` here as well produced **two identical
        # legend rows per curve** (the 2026-11-08 "one phase drawn twice"
        # report): the plot only ever held one item, the legend held two.
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
        # ``PlotItem.removeItem()`` drops the matching legend row by item
        # identity (LegendItem.removeItem matches ``sample.item is item``), so
        # there is nothing to remove from the legend here.  Doing it by *name*
        # used to be wrong twice over: it deleted a same-named sibling row and
        # it was redundant after addItem stopped double-adding.
        self._plot.removeItem(rec["curve"])
        self.fit_data_range()

    def patterns(self) -> dict[str, Pattern]:
        """Mapping of handle -> :class:`Pattern` currently displayed."""
        return {k: v["pattern"] for k, v in self._records.items()}

    # ------------------------------------------------------------------
    # Reference stick patterns (v3.1.0 — sequential phase identification)
    # ------------------------------------------------------------------
    def add_stick_pattern(
        self,
        name: str,
        two_theta,
        heights,
        color: str | None = None,
    ) -> str:
        """Overlay a reference line ("stick") pattern; returns its handle.

        Each reflection is drawn as a vertical bar from ``y = 0`` up to
        *heights* (in the same intensity unit as the experimental curve), so
        a confirmed phase's line positions can be compared directly against
        the measured peaks — the visual check that the sequential
        identification actually explains the pattern.

        Sticks are added with ``ignoreBounds=True`` (they never disturb the
        autorange the experimental curve establishes) and rendered as a
        single ``connect="pairs"`` curve, so a 150-reflection card costs one
        item instead of 150.

        Parameters
        ----------
        name:
            Legend label (usually ``"<entry_id> <formula>"``).
        two_theta:
            Reflection positions in **physical** 2θ degrees; converted to the
            current X display mode automatically.
        heights:
            Bar heights, same length as *two_theta*.
        color:
            Bar colour; defaults to the next entry of :data:`PATTERN_COLORS`.
        """
        xs = np.asarray(two_theta, dtype=float).ravel()
        hs = np.asarray(heights, dtype=float).ravel()
        if xs.size == 0 or xs.size != hs.size:
            raise ValueError(
                f"stick arrays must be non-empty and equal length, got "
                f"{xs.size} positions / {hs.size} heights"
            )
        key = f"S{next(self._counter)}"
        pen_color = color or PATTERN_COLORS[len(self._records) % len(PATTERN_COLORS)]
        curve = pg.PlotDataItem(
            [0.0, 0.0],
            [0.0, 0.0],
            pen=pg.mkPen(pen_color, width=1.0),
            connect="pairs",
            name=name,
        )
        self._plot.addItem(curve, ignoreBounds=True)
        self._sticks[key] = {
            "two_theta": xs,
            "heights": hs,
            "curve": curve,
            "name": name,
            "color": pen_color,
        }
        self._apply_stick_data(key)
        # Legend row is added by ``PlotItem.addItem()`` (see the note in
        # ``add_pattern``) -- do not add it a second time here.
        return key

    def remove_stick_pattern(self, key: str) -> None:
        """Remove a stick pattern added under *key* (no-op if absent)."""
        rec = self._sticks.pop(key, None)
        if rec is None:
            return
        self._plot.removeItem(rec["curve"])

    def clear_sticks(self) -> None:
        """Remove every reference stick pattern."""
        for key in list(self._sticks):
            self.remove_stick_pattern(key)

    def stick_count(self) -> int:
        """Number of reference stick patterns currently overlaid."""
        return len(self._sticks)

    def _apply_stick_data(self, key: str) -> None:
        """(Re)compute the display coordinates of one stick pattern."""
        rec = self._sticks[key]
        xs = rec["two_theta"]
        hs = rec["heights"]
        if self._x_mode == X_MODE_D:
            xs = np.asarray([self._x_to_display(float(x)) for x in xs], dtype=float)
            finite = np.isfinite(xs)
            xs = xs[finite]
            hs = hs[finite]
        else:
            xs = np.asarray(xs, dtype=float)
        ys = np.asarray([self._y_to_display(float(h)) for h in hs], dtype=float)
        # connect="pairs" links (0,1), (2,3), … → duplicate each x to get a
        # bar from the baseline to the reflection height.
        x_pairs = np.repeat(xs, 2)
        y_pairs = np.empty(x_pairs.size, dtype=float)
        y_pairs[0::2] = 0.0
        y_pairs[1::2] = ys
        rec["curve"].setData(x_pairs, y_pairs, connect="pairs")

    def _refresh_all_sticks(self) -> None:
        """Recompute every stick pattern after an axis-mode change."""
        for key in self._sticks:
            self._apply_stick_data(key)

    def clear(self) -> None:
        """Remove all overlaid patterns (and reference stick patterns)."""
        self.clear_sticks()
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

        v3.6.2：十字线被隐藏时（框选工具下）不再刷新读数，省一次无谓重绘。
        """
        if not self.crosshair_visible():
            return
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
    """谱图区面板（v3.6.2）：快捷图标行 + 谱图 + 参考线条分区。

    自下而上三层：

    - **快捷图标行**（:class:`~xinmatch.ui.plot_toolbar.PlotToolBar`）：复位 /
      按轴框选 / 平移 / 步进缩放 / 十字线；
    - **谱图**（:class:`PatternView`）：横纵轴可点击切换显示（左键循环、
      右键菜单）；
    - **参考线条分区**（:class:`~xinmatch.ui.stick_lane.StickLaneView`）：
      候选相与已确认相各占一行，与谱图共用横坐标。

    原先顶部的「X 轴 / Y 轴 / 适应数据范围」控制条（v1.3.1）**隐藏但保留**：
    ``x_combo`` / ``y_combo`` 仍是轴模式的唯一真相源（轴的点击切换最终也是
    改它们的 index），``fit_button`` 的「适应数据范围」由图标行的"原始谱图"
    按钮接管。
    """

    #: 转发视图的 crosshair 读数（物理量文本），供主窗口镜像到状态栏。
    cursor_moved = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        # 延迟导入：plot_toolbar 反向依赖本模块（PatternView），顶层导入会成环。
        from xinmatch.ui.plot_toolbar import PlotToolBar
        from xinmatch.ui.stick_lane import StickLaneView

        self.view = PatternView()
        self._confirmed_rows: list = []
        self._candidate_row = None
        self._axis_menu: QtWidgets.QMenu | None = None

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

        # 控制条整体隐藏（v3.6.2 用户要求）：切轴改到点击坐标轴本身。
        self._axis_bar = QtWidgets.QWidget(self)
        self._axis_bar.setLayout(bar)
        self._axis_bar.setVisible(False)

        self.toolbar = PlotToolBar(self.view, self)
        self.lane = StickLaneView(self.view, self)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._axis_bar)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.view, stretch=1)
        layout.addWidget(self.lane)

        self.x_combo.currentIndexChanged.connect(self._on_x_changed)
        self.y_combo.currentIndexChanged.connect(self._on_y_changed)
        self.fit_button.clicked.connect(self.view.fit_data_range)
        self.view.cursor_moved.connect(self.cursor_moved)
        # 轴点击切显示（左键循环 / 右键菜单）。
        self.view.x_axis_clicked.connect(self._on_x_axis_clicked)
        self.view.y_axis_clicked.connect(self._on_y_axis_clicked)
        # 轴模式变了，参考线分区的横坐标换算也要跟着变。
        self.view.x_mode_changed.connect(lambda _mode: self.lane.refresh())

    # ------------------------------------------------------------------
    # 轴显示模式：下拉框（隐藏）+ 轴点击
    # ------------------------------------------------------------------
    def _on_x_changed(self, index: int) -> None:
        mode = X_MODES[index] if 0 <= index < len(X_MODES) else X_MODE_TWO_THETA
        self.view.set_x_mode(mode)

    def _on_y_changed(self, index: int) -> None:
        mode = Y_MODES[index] if 0 <= index < len(Y_MODES) else Y_MODE_COUNTS
        self.view.set_y_mode(mode)

    def _on_x_axis_clicked(self, button) -> None:
        """横轴被点击：左键循环到下一模式，右键弹出模式菜单。"""
        if button == QtCore.Qt.MouseButton.RightButton:
            self._axis_menu = self._build_axis_menu(self.x_combo, "X 轴显示")
        else:
            self._cycle_combo(self.x_combo)

    def _on_y_axis_clicked(self, button) -> None:
        """纵轴被点击：左键循环到下一模式，右键弹出模式菜单。"""
        if button == QtCore.Qt.MouseButton.RightButton:
            self._axis_menu = self._build_axis_menu(self.y_combo, "Y 轴显示")
        else:
            self._cycle_combo(self.y_combo)

    @staticmethod
    def _cycle_combo(combo: QtWidgets.QComboBox, step: int = 1) -> None:
        """把下拉框循环推进 *step* 格（隐藏的下拉框仍是模式真相源）。"""
        count = combo.count()
        if count <= 0:
            return
        combo.setCurrentIndex((combo.currentIndex() + step) % count)

    def _build_axis_menu(
        self, combo: QtWidgets.QComboBox, title: str, *, popup: bool = True
    ) -> QtWidgets.QMenu:
        """按 *combo* 的候选项建一个"直接选模式"的右键菜单（默认就地弹出）。"""
        menu = QtWidgets.QMenu(self)
        menu.setTitle(title)
        for index in range(combo.count()):
            action = menu.addAction(combo.itemText(index))
            action.setCheckable(True)
            action.setChecked(index == combo.currentIndex())
            action.triggered.connect(
                lambda _checked=False, idx=index, c=combo: c.setCurrentIndex(idx)
            )
        if popup:
            menu.popup(QtGui.QCursor.pos())
        return menu

    # ------------------------------------------------------------------
    # 参考线条分区
    # ------------------------------------------------------------------
    def set_confirmed_lane_rows(self, rows) -> None:
        """设置"已确认物相"的行（主窗口在序贯状态变化后调用）。"""
        self._confirmed_rows = list(rows)
        self._refresh_lane()

    def set_candidate_lane_row(self, row) -> None:
        """设置 / 清除"候选列表高亮相"的预览行（``None`` = 清除）。"""
        self._candidate_row = row
        self._refresh_lane()

    def lane_rows(self) -> list:
        """当前参考线分区的行（候选行在最上，其后为已确认相）。"""
        return self.lane.rows()

    def _refresh_lane(self) -> None:
        rows = ([self._candidate_row] if self._candidate_row is not None else [])
        rows = rows + list(self._confirmed_rows)
        self.lane.set_rows(rows)

    # ------------------------------------------------------------------
    # Drop-in 代理：主窗口 / 旧调用点可直接用 PatternPanel 当视图用
    # ------------------------------------------------------------------
    def add_pattern(self, pattern: Pattern, name: str | None = None,
                    color: str | None = None) -> str:
        """代理到内部视图的 :meth:`PatternView.add_pattern`。"""
        key = self.view.add_pattern(pattern, name=name, color=color)
        self.lane.sync_geometry()
        return key

    def remove_pattern(self, key: str) -> None:
        """代理到内部视图的 :meth:`PatternView.remove_pattern`。"""
        self.view.remove_pattern(key)
        self.lane.sync_geometry()

    def clear(self) -> None:
        """代理到内部视图的 :meth:`PatternView.clear`。"""
        self.view.clear()

    def patterns(self) -> dict[str, Pattern]:
        """代理到内部视图的 :meth:`PatternView.patterns`。"""
        return self.view.patterns()

    def add_stick_pattern(
        self, name: str, two_theta, heights, color: str | None = None
    ) -> str:
        """代理到内部视图的 :meth:`PatternView.add_stick_pattern`。"""
        return self.view.add_stick_pattern(name, two_theta, heights, color)

    def remove_stick_pattern(self, key: str) -> None:
        """代理到内部视图的 :meth:`PatternView.remove_stick_pattern`。"""
        self.view.remove_stick_pattern(key)

    def clear_sticks(self) -> None:
        """代理到内部视图的 :meth:`PatternView.clear_sticks`。"""
        self.view.clear_sticks()

    def apply_theme_colors(self) -> None:
        """主题切换后重设谱图与参考线分区配色。"""
        self.view.apply_theme_colors()
        self.lane.apply_theme_colors()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        """窗口尺寸变化后重新对齐参考线分区的左轴宽度。"""
        super().resizeEvent(event)
        self.lane.sync_geometry()
