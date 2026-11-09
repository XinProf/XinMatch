"""谱图快捷操作行（v3.6.2）：一排直接作用于谱图的图标按钮。

位置：紧贴谱图上方（原先的"X 轴 / Y 轴 / 适应数据范围"控制条被隐藏，
轴切换改为点击坐标轴本身，见 :mod:`xinmatch.ui.pattern_view`）。

按钮 → 动作（语义与姊妹项目 XinRefinement 的 ``gui/plot_tools.py`` 一致）：

============  ==================================================
按钮          动作
============  ==================================================
原始谱图      恢复默认视场（横轴全量 + 纵轴贴合全谱）
横向框选      拖出角度区间，只改横轴（纵轴自动贴合该区间）
纵向框选      拖出强度区间，只改纵轴
区域放大      拖出矩形，横纵轴一起改
左移 / 右移   视场整体平移 25%
放大 / 缩小   以视场中心为锚点步进缩放（纵轴随之贴合）
十字线        十字线跟随鼠标，行尾显示角度与强度读数
============  ==================================================

模式类按钮（框选三种 + 十字线）互斥，但**允许再点一次取消**——因此不用
``QButtonGroup`` 的 exclusive 模式（exclusive 组不允许取消勾选）。
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from xinmatch.ui.pattern_view import PLOT_TOOL_MODES, TOOL_CROSSHAIR, PatternView
from xinmatch.ui.plot_icons import plot_icon

__all__ = ["PAN_FRAC", "ZOOM_STEP", "PlotToolBar"]

#: 按钮顺序（分组之间插分隔线）。
TOOL_GROUPS: tuple[tuple[str, ...], ...] = (
    ("reset",),
    ("zoom_x", "zoom_y", "zoom_rect"),
    ("pan_left", "pan_right"),
    ("zoom_in", "zoom_out"),
    ("crosshair",),
)

#: 可保持选中态的工具（其余为"点一下就执行"的瞬时按钮）。
MODE_TOOLS: tuple[str, ...] = PLOT_TOOL_MODES

#: 平移步长（视场宽度的比例）与缩放系数（``<1`` 为放大）。
PAN_FRAC = 0.25
ZOOM_STEP = 0.8

_ICON_PX = 22

#: 中文 tooltip（与 :mod:`xinmatch.ui.plot_icons` 的键名一一对应）。
_TOOLTIPS: dict[str, str] = {
    "reset": "恢复默认视场：横轴全量 + 纵轴贴合全谱",
    "zoom_x": "横向框选：拖出角度区间，只改横轴（纵轴自动贴合该区间）",
    "zoom_y": "纵向框选：拖出强度区间，只改纵轴",
    "zoom_rect": "区域放大：拖出矩形，横轴纵轴一起改",
    "pan_left": f"视场左移 {PAN_FRAC:.0%}",
    "pan_right": f"视场右移 {PAN_FRAC:.0%}",
    "zoom_in": "以视场中心放大（纵轴随之贴合）",
    "zoom_out": "以视场中心缩小（纵轴随之贴合）",
    "crosshair": "十字线读数：跟随鼠标显示 2θ 与强度",
}


class PlotToolBar(QtWidgets.QWidget):
    """谱图操作按钮行（贴着谱图上方显示）。"""

    def __init__(self, view: PatternView, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.view = view
        self.buttons: dict[str, QtWidgets.QToolButton] = {}

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(4, 1, 4, 1)
        lay.setSpacing(2)

        # 互斥由代码保证，不用 exclusive：用户要求再点一次能取消。
        self._group = QtWidgets.QButtonGroup(self)
        self._group.setExclusive(False)

        for index, group in enumerate(TOOL_GROUPS):
            if index:
                line = QtWidgets.QFrame()
                line.setFrameShape(QtWidgets.QFrame.Shape.VLine)
                line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
                lay.addWidget(line)
            for key in group:
                btn = QtWidgets.QToolButton()
                btn.setCheckable(key in MODE_TOOLS)
                btn.setAutoRaise(True)
                btn.setIconSize(QtCore.QSize(_ICON_PX, _ICON_PX))
                icon = plot_icon(key)
                if icon is not None:
                    btn.setIcon(icon)
                else:  # 图标绘制失败时退化为文字，功能不受影响
                    btn.setText(key)
                btn.setToolTip(_TOOLTIPS.get(key, key))
                btn.clicked.connect(lambda _checked=False, k=key: self._on_click(k))
                lay.addWidget(btn)
                self._group.addButton(btn)
                self.buttons[key] = btn

        lay.addStretch(1)
        self.lbl_hint = QtWidgets.QLabel("")
        self.lbl_hint.setStyleSheet("color: #6b6b6b;")
        lay.addWidget(self.lbl_hint)

        self.view.cursor_moved.connect(self._on_cursor_info)
        # 初始状态与视图一致（默认十字线工具）。
        self._sync_buttons(self.view.tool())

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def _on_click(self, key: str) -> None:
        """按钮点击：模式类切换选中态，动作类立即执行。"""
        btn = self.buttons[key]
        if key in MODE_TOOLS:
            active = btn.isChecked()
            for other in MODE_TOOLS:  # 单选：先清掉其它工具
                if other != key:
                    self.buttons[other].setChecked(False)
            self.view.set_plot_tool(key if active else None)
            if not active:
                self.lbl_hint.setText("")
            return
        if btn.isChecked():  # 瞬时按钮不该保持选中
            btn.setChecked(False)
        if key == "reset":
            self.view.reset_view()
        elif key == "pan_left":
            self.view.pan_x(-PAN_FRAC)
        elif key == "pan_right":
            self.view.pan_x(PAN_FRAC)
        elif key == "zoom_in":
            self.view.zoom_scale(ZOOM_STEP)
        elif key == "zoom_out":
            self.view.zoom_scale(1.0 / ZOOM_STEP)

    def _on_cursor_info(self, text: str) -> None:
        """十字线读数：贴着谱图显示一份（状态栏可能被其它消息占用）。"""
        self.lbl_hint.setText(text if self.view.tool() == TOOL_CROSSHAIR else "")

    def set_tool(self, tool: str | None) -> None:
        """程序化切换工具（测试与快捷键用），保持按钮状态一致。"""
        self.view.set_plot_tool(tool)
        self._sync_buttons(tool)
        self.lbl_hint.setText("")

    def _sync_buttons(self, tool: str | None) -> None:
        for key in MODE_TOOLS:
            self.buttons[key].setChecked(key == tool)

    @property
    def mode(self) -> str | None:
        """当前工具（转发 :meth:`PatternView.tool`）。"""
        return self.view.tool()
