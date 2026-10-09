"""T13.7 — 浅/深主题：对比度达标、关键控件可构造、图标非空。"""

from __future__ import annotations

import pytest
from PySide6 import QtGui, QtWidgets

from xinmatch.ui.theme import THEMES, apply_theme, current_theme, icon


def _lum(color: QtGui.QColor) -> float:
    """归一化亮度（0..1），便于对比度阈值断言。"""
    return color.lightness() / 255.0


def _contrast_ok(fg: QtGui.QColor, bg: QtGui.QColor, threshold: float = 0.4) -> bool:
    return abs(_lum(fg) - _lum(bg)) > threshold


@pytest.mark.parametrize("name", ["light", "dark"])
def test_palette_contrast_meets_threshold(qapp, name):
    apply_theme(qapp, name)
    pal = qapp.palette()
    assert _contrast_ok(
        pal.color(QtGui.QPalette.ColorRole.WindowText),
        pal.color(QtGui.QPalette.ColorRole.Window),
    )
    assert _contrast_ok(
        pal.color(QtGui.QPalette.ColorRole.Text),
        pal.color(QtGui.QPalette.ColorRole.Base),
    )
    assert _contrast_ok(
        pal.color(QtGui.QPalette.ColorRole.HighlightedText),
        pal.color(QtGui.QPalette.ColorRole.Highlight),
    )


@pytest.mark.parametrize("name", ["light", "dark"])
def test_key_widgets_construct_and_inherit_theme(qapp, name):
    apply_theme(qapp, name)
    table = QtWidgets.QTableWidget(2, 2)
    table.setHorizontalHeaderLabels(["2θ", "I"])
    button = QtWidgets.QPushButton("运行")
    pal = table.palette()
    cg = QtGui.QPalette.ColorGroup.Active
    role = QtGui.QPalette.ColorRole
    assert _contrast_ok(
        pal.color(cg, role.Text),
        pal.color(cg, role.Base),
    )
    bpal = button.palette()
    assert _contrast_ok(
        bpal.color(cg, role.ButtonText),
        bpal.color(cg, role.Button),
    )


def test_dark_theme_readable_controls(qapp):
    apply_theme(qapp, "dark")
    table = QtWidgets.QTableWidget()
    table.setStyleSheet("")  # 不额外覆盖，验证来自主题令牌
    dock = QtWidgets.QDockWidget("候选列表")
    dock.setWidget(QtWidgets.QTableWidget())
    pal = table.palette()
    text = pal.color(QtGui.QPalette.ColorRole.Text)
    base = pal.color(QtGui.QPalette.ColorRole.Base)
    assert text.lightness() > base.lightness()  # 深色主题：浅字深底
    assert _contrast_ok(text, base)


def test_apply_theme_unknown_name_raises(qapp):
    with pytest.raises(ValueError):
        apply_theme(qapp, "neon")


def test_current_theme_tracks_application(qapp):
    apply_theme(qapp, "light")
    assert current_theme() == "light"
    apply_theme(qapp, "dark")
    assert current_theme() == "dark"


@pytest.mark.parametrize("name", ["open", "save", "run", "reset", "search", "help"])
def test_icon_returns_non_null(qapp, name):
    ico = icon(name, "dark")
    assert isinstance(ico, QtGui.QIcon)
    assert not ico.isNull()


def test_unknown_icon_name_falls_back(qapp):
    ico = icon("totally_unknown_action", "light")
    assert isinstance(ico, QtGui.QIcon)
    assert not ico.isNull()


def test_both_themes_defined_with_semantic_tokens():
    assert set(THEMES) == {"light", "dark"}
    common = set(THEMES["light"]) & set(THEMES["dark"])
    assert {"bg", "base", "text", "accent", "selection", "border"} <= common
