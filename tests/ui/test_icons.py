"""原创 SVG 图标库测试（offscreen）。

覆盖：
* :data:`xinmatch.ui.icons.ICON_NAMES` 覆盖主工具栏全部 12 个动作（模块）名；
* 每个图标名在浅 / 深主题下都返回非空 ``QIcon``；
* 自绘图标渲染像素与 Qt 内置 ``SP_*`` 标准图标内容不同（非"换皮"）；
* :func:`xinmatch.ui.icons.is_svg_icon` 语义正确；
* 未知名回退通用图标、绝不为空。
"""

from __future__ import annotations

import pytest
from PySide6 import QtGui, QtWidgets

from xinmatch.ui.icons import ICON_NAMES, icon, is_svg_icon
from xinmatch.ui.main_window import TOOLBAR_MODULES
from xinmatch.ui.theme import THEMES

#: 用于比对"非标准图标"的 Qt 内置 pixmap 常量。
_STANDARD_SAMPLES = (
    QtWidgets.QStyle.SP_DialogOpenButton,
    QtWidgets.QStyle.SP_FileDialogDetailedView,
    QtWidgets.QStyle.SP_MediaPlay,
    QtWidgets.QStyle.SP_DialogHelpButton,
)


def _pix_image(ic: QtGui.QIcon, size: int = 48) -> QtGui.QImage:
    """取图标在指定尺寸下渲染的 QImage（用于逐像素比对）。"""
    return ic.pixmap(size, size).toImage()


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_icon_non_null(qapp, theme):
    for name in ICON_NAMES:
        ic = icon(name, theme)
        assert isinstance(ic, QtGui.QIcon)
        assert not ic.isNull(), f"{name} ({theme}) 为空图标"


def test_unknown_name_falls_back_to_generic(qapp):
    for name in ("totally_unknown_action", "", "does_not_exist"):
        ic = icon(name, "light")
        assert isinstance(ic, QtGui.QIcon)
        assert not ic.isNull()


def test_is_svg_icon_semantics(qapp):
    for name in ICON_NAMES:
        assert is_svg_icon(name) is True
    for name in ("open_", "zzz", "unknown", ""):
        assert is_svg_icon(name) is False


def test_toolbar_modules_all_mapped_to_known_icons(qapp):
    """工具栏 12 个动作（模块 id）必须全部有对应图标名且该名受支持。"""
    from xinmatch.ui.icons import MODULE_ICON_NAMES

    assert set(TOOLBAR_MODULES) <= set(MODULE_ICON_NAMES)
    for mod_id in TOOLBAR_MODULES:
        mapped = MODULE_ICON_NAMES[mod_id]
        assert mapped in ICON_NAMES, f"{mod_id} -> {mapped} 不在 ICON_NAMES"


@pytest.mark.parametrize("name", sorted(ICON_NAMES))
def test_icon_differs_from_standard_pixmap(qapp, name):
    """自绘图标渲染内容与任意 Qt 内置标准图标都不相同。"""
    style = qapp.style()
    ours = _pix_image(icon(name))
    for std in _STANDARD_SAMPLES:
        ref = _pix_image(style.standardIcon(std))
        # 尺寸对齐后逐像素比对； ours 至少在一个像素上与 ref 不同。
        w = min(ours.width(), ref.width())
        h = min(ours.height(), ref.height())
        diff = False
        for yy in range(0, h, 3):
            for xx in range(0, w, 3):
                if ours.pixelColor(xx, yy) != ref.pixelColor(xx, yy):
                    diff = True
                    break
            if diff:
                break
        assert diff, f"图标 {name} 与标准图标 {std} 渲染内容相同"


def test_chart_tokens_present_and_contrast_ok():
    """图谱区令牌两主题齐备；深底上文本 / 网格与背景可区分。"""
    for name, tokens in THEMES.items():
        for key in ("chart_bg", "chart_grid", "chart_axis", "chart_cursor", "chart_text"):
            assert key in tokens, f"{name} 缺少 {key}"
        bg = QtGui.QColor(tokens["chart_bg"])
        text = QtGui.QColor(tokens["chart_text"])
        grid = QtGui.QColor(tokens["chart_grid"])
        # 文本与背景亮度差（对比度粗略断言）。
        assert abs(bg.lightness() - text.lightness()) > 60
        # 网格与背景可区分。
        assert bg.lightness() != grid.lightness() or bg.toRgb() != grid.toRgb()
