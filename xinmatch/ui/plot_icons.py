"""谱图快捷操作按钮的图标（QPainter 程序化绘制，零素材依赖）。

与 ``xinmatch/ui/icons.py``（SVG 素材图标，用于菜单/工具栏）分开：这里是
**谱图区专用**的一组小图标，风格与姊妹项目 XinRefinement 的
``gui/button_icons.py`` 保持一致（32×32 设计坐标、家族色描边 + 浅色填充、
多尺寸各渲染一份位图以适配高 DPI），语义也一一对应：

============  ============================================
键名          含义
============  ============================================
reset         恢复默认视场（横轴全量 + 纵轴贴合全谱）
zoom_x        横向框选（只改 X 轴）
zoom_y        纵向框选（只改 Y 轴）
zoom_rect     区域放大（X/Y 一起改）
pan_left      视场左移 25%
pan_right     视场右移 25%
zoom_in       以视场中心放大
zoom_out      以视场中心缩小
crosshair     十字线读数模式
============  ============================================

图标绘制是纯 QPainter 代码，与绘图框架无关，因此可从姊妹项目直接复用。
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)

__all__ = ["PLOT_TOOL_KEYS", "plot_icon"]

#: 一次渲染多个尺寸，高 DPI 下由 Qt 挑最合适的一张。
_SIZES = (16, 20, 24, 32, 48)

_PLOT_ZOOM = "#17becf"    # 青：缩放
_PLOT_PAN = "#9467bd"     # 紫：平移
_PLOT_RESET = "#1f77b4"   # 蓝：复位
_PLOT_CURSOR = "#d32f2f"  # 红：十字线（与谱图上的红线同色）


def _tint(hex_color: str, alpha: int) -> QColor:
    c = QColor(hex_color)
    c.setAlpha(alpha)
    return c


def _frame(p: QPainter, color: str, alpha: int = 24) -> None:
    """浅色方框（谱图视场的示意底）。"""
    p.setPen(QPen(_tint(color, 110), 1.4))
    p.setBrush(_tint(color, alpha))
    p.drawRoundedRect(QRectF(4.5, 6.0, 23.0, 20.0), 3.0, 3.0)


def _curve(p: QPainter, color: str) -> None:
    """框内一条衍射峰折线（纯示意）。"""
    p.setPen(QPen(QColor(color), 1.6, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath(QPointF(7.0, 22.0))
    path.lineTo(12.0, 22.0)
    path.lineTo(14.0, 12.5)
    path.lineTo(16.5, 22.0)
    path.lineTo(19.5, 22.0)
    path.lineTo(21.0, 17.0)
    path.lineTo(22.5, 22.0)
    p.drawPath(path)


def _double_arrow(p: QPainter, color: str, horizontal: bool) -> None:
    """双向箭头（横向 / 纵向），两端带箭头头。"""
    p.setPen(QPen(QColor(color), 2.2, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    if horizontal:
        p.drawLine(QPointF(9.0, 16.0), QPointF(23.0, 16.0))
        for x, s in ((9.0, 1.0), (23.0, -1.0)):
            p.drawLine(QPointF(x, 16.0), QPointF(x + 3.2 * s, 13.0))
            p.drawLine(QPointF(x, 16.0), QPointF(x + 3.2 * s, 19.0))
    else:
        p.drawLine(QPointF(16.0, 8.0), QPointF(16.0, 24.0))
        for y, s in ((8.0, 1.0), (24.0, -1.0)):
            p.drawLine(QPointF(16.0, y), QPointF(13.0, y + 3.2 * s))
            p.drawLine(QPointF(16.0, y), QPointF(19.0, y + 3.2 * s))


def _pan_icon(p: QPainter, to_right: bool) -> None:
    """平移：视场框 + 单向粗箭头（+ 尾部运动线）。"""
    _frame(p, _PLOT_PAN, alpha=18)
    y = 16.0
    p.setPen(QPen(QColor(_PLOT_PAN), 2.6, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if to_right:
        p.drawLine(QPointF(10.0, y), QPointF(22.0, y))
        p.drawLine(QPointF(22.0, y), QPointF(18.0, y - 3.6))
        p.drawLine(QPointF(22.0, y), QPointF(18.0, y + 3.6))
        for dy in (-5.0, 5.0):
            p.drawLine(QPointF(7.5, y + dy), QPointF(13.0, y + dy))
    else:
        p.drawLine(QPointF(22.0, y), QPointF(10.0, y))
        p.drawLine(QPointF(10.0, y), QPointF(14.0, y - 3.6))
        p.drawLine(QPointF(10.0, y), QPointF(14.0, y + 3.6))
        for dy in (-5.0, 5.0):
            p.drawLine(QPointF(24.5, y + dy), QPointF(19.0, y + dy))


def _magnifier(p: QPainter, color: str, plus: bool) -> None:
    """放大镜（+ / −）。"""
    p.setPen(QPen(QColor(color), 2.4))
    p.setBrush(_tint(color, 26))
    p.drawEllipse(QPointF(14.0, 13.5), 8.0, 8.0)
    p.drawLine(QPointF(20.0, 19.5), QPointF(26.0, 25.5))
    p.setPen(QPen(QColor(color), 2.2, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(10.5, 13.5), QPointF(17.5, 13.5))
    if plus:
        p.drawLine(QPointF(14.0, 10.0), QPointF(14.0, 17.0))


def _draw_plot_reset(p: QPainter) -> None:
    """原始谱图：完整视场框 + 谱线 + 回到原点的弧形箭头。"""
    _frame(p, _PLOT_RESET)
    _curve(p, _PLOT_RESET)
    p.setPen(QPen(QColor(_PLOT_RESET), 1.8, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(20.0, 2.0, 9.0, 9.0), 40 * 16, 250 * 16)
    p.setBrush(QColor(_PLOT_RESET))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawPolygon(QPolygonF([QPointF(20.6, 4.2), QPointF(25.2, 5.4),
                             QPointF(21.8, 8.2)]))


def _draw_plot_zoom_x(p: QPainter) -> None:
    """横向框选：视场框 + 中间横向双向箭头。"""
    _frame(p, _PLOT_ZOOM)
    _double_arrow(p, _PLOT_ZOOM, horizontal=True)


def _draw_plot_zoom_y(p: QPainter) -> None:
    """纵向框选：视场框 + 纵向双向箭头。"""
    _frame(p, _PLOT_ZOOM)
    _double_arrow(p, _PLOT_ZOOM, horizontal=False)


def _draw_plot_zoom_rect(p: QPainter) -> None:
    """区域放大：虚线矩形框（框选动作的通用符号）。"""
    p.setPen(QPen(QColor(_PLOT_ZOOM), 2.0, Qt.PenStyle.DashLine))
    p.setBrush(_tint(_PLOT_ZOOM, 22))
    p.drawRect(QRectF(6.0, 7.0, 20.0, 18.0))
    p.setPen(QPen(_tint(_PLOT_ZOOM, 150), 1.2))
    p.drawLine(QPointF(6.0, 16.0), QPointF(26.0, 16.0))
    p.drawLine(QPointF(16.0, 7.0), QPointF(16.0, 25.0))


def _draw_plot_pan_left(p: QPainter) -> None:
    _pan_icon(p, to_right=False)


def _draw_plot_pan_right(p: QPainter) -> None:
    _pan_icon(p, to_right=True)


def _draw_plot_zoom_in(p: QPainter) -> None:
    _magnifier(p, _PLOT_ZOOM, plus=True)


def _draw_plot_zoom_out(p: QPainter) -> None:
    _magnifier(p, _PLOT_ZOOM, plus=False)


def _draw_plot_crosshair(p: QPainter) -> None:
    """十字线：红色竖线 + 顶部横标 + 峰位三角。"""
    _frame(p, _PLOT_CURSOR, alpha=16)
    p.setPen(QPen(QColor(_PLOT_CURSOR), 2.0))
    p.drawLine(QPointF(16.0, 4.5), QPointF(16.0, 27.0))
    p.drawLine(QPointF(10.5, 9.0), QPointF(21.5, 9.0))
    p.setPen(QPen(QColor(_PLOT_CURSOR), 1.2, Qt.PenStyle.DashLine))
    p.drawLine(QPointF(6.0, 22.0), QPointF(26.0, 22.0))
    p.setBrush(QColor(_PLOT_CURSOR))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawPolygon(QPolygonF([QPointF(13.0, 22.0), QPointF(19.0, 22.0),
                             QPointF(16.0, 16.0)]))


_DRAWERS = {
    "reset": _draw_plot_reset,
    "zoom_x": _draw_plot_zoom_x,
    "zoom_y": _draw_plot_zoom_y,
    "zoom_rect": _draw_plot_zoom_rect,
    "pan_left": _draw_plot_pan_left,
    "pan_right": _draw_plot_pan_right,
    "zoom_in": _draw_plot_zoom_in,
    "zoom_out": _draw_plot_zoom_out,
    "crosshair": _draw_plot_crosshair,
}

#: 全部可用键名（顺序即默认按钮顺序）。
PLOT_TOOL_KEYS: tuple[str, ...] = tuple(_DRAWERS)


def plot_icon(key: str) -> QIcon | None:
    """按 *key* 返回谱图操作图标；未知键返回 ``None``（调用方退化为文字）。"""
    draw = _DRAWERS.get(key)
    if draw is None:
        return None
    icon = QIcon()
    for size in _SIZES:
        pm = QPixmap(QSize(size, size))
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(size / 32.0, size / 32.0)
        draw(painter)
        painter.end()
        icon.addPixmap(pm)
    return icon
