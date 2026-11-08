"""T13.2 — PatternView: multi-pattern overlay, crosshair, offscreen render."""

from __future__ import annotations

import numpy as np
import pytest
from PySide6 import QtGui

from xinmatch.core.model.pattern import Pattern
from xinmatch.ui.pattern_view import PatternView
from xinmatch.ui.theme import apply_theme


def _synth(n_points: int = 50_000, seed: int = 0) -> Pattern:
    """Synthetic powder pattern: a few Gaussians + noise on a uniform grid."""
    rng = np.random.default_rng(seed)
    x = np.linspace(5.0, 90.0, n_points)
    y = np.full_like(x, 20.0)
    for center, height in ((28.4, 800.0), (47.3, 400.0), (56.1, 200.0)):
        y += height * np.exp(-((x - center) ** 2) / (2.0 * 0.15**2))
    y += rng.normal(0.0, 3.0, size=x.shape)
    return Pattern(
        two_theta=x,
        intensity=y,
        wavelength=1.5406,
        metadata={"sample_id": "synthetic"},
    )


def test_add_and_remove_pattern(qapp):
    view = PatternView()
    k1 = view.add_pattern(_synth(2_000), name="A")
    k2 = view.add_pattern(_synth(2_000), name="B")
    assert set(view.patterns()) == {k1, k2}
    view.remove_pattern(k1)
    assert set(view.patterns()) == {k2}


def test_patterns_get_distinct_colors(qapp):
    view = PatternView()
    k1 = view.add_pattern(_synth(500), name="A")
    k2 = view.add_pattern(_synth(500), name="B")
    assert view._records[k1]["color"] != view._records[k2]["color"]


# ---------------------------------------------------------------------------
# Legend bookkeeping (2026-11-08 regression)
# ---------------------------------------------------------------------------
def _plot_data_items(view: PatternView) -> int:
    return sum(
        1 for it in view.plotItem.items
        if hasattr(it, "implements") and it.implements("plotData")
    )


def _legend_rows(view: PatternView) -> int:
    return len(view._legend.items)


@pytest.fixture
def view(qapp):
    """每次用新的 PatternView，并**显式销毁**。

    pyqtgraph 0.13.7 的 ``LabelItem`` 若在解释器退出时被延迟回收，会在
    ``sizeHint()`` 里抛 ``'LabelItem' object has no attribute '_sizeHint'``
    （父类构造早于该属性赋值）。多个 widget 累积到 session 末一起 gc 就会
    把无关测试带崩，所以这里 deterministically 清空并断开父子关系。
    """
    v = PatternView()
    yield v
    v.clear()
    v.setParent(None)
    v.deleteLater()
    qapp.processEvents()


def test_legend_has_exactly_one_row_per_curve(view):
    """每条曲线在 plot 里 1 个 item，图例也必须只有 1 行。

    回归：``PlotItem.addItem()`` 自己会把带 ``name`` 的 PlotDataItem 加进
    legend（pyqtgraph 0.13.7，PlotItem.py:516-552），旧代码又手动
    ``legend.addItem()`` 一次 → 图例双份。用户看到「选 1 个相标出 2 个、
    确认 2 个相给 4 个、试样也 2 条」，实际曲线一直只有 1 条。
    """
    view.add_pattern(_synth(500), name="36%实验.txt")
    assert _plot_data_items(view) == 1
    assert _legend_rows(view) == 1, "同一曲线在 legend 里出现多行"

    view.add_stick_pattern("96-900-8213 O2 Ti", [25.3, 37.8], [100.0, 30.0])
    assert _plot_data_items(view) == 2
    assert _legend_rows(view) == 2

    view.add_stick_pattern("96-900-4141 O2 Ti", [27.4, 36.1], [100.0, 45.0])
    assert _plot_data_items(view) == 3
    assert _legend_rows(view) == 3


def test_removing_same_named_curves_leaves_legend_consistent(view):
    """同名曲线（同一相重画）删一条只该少一行，不能按名字误删兄弟行。

    回归：旧 ``remove_pattern`` 用 ``legend.removeItem(name)`` 按名字删，
    两条同名时会把别人的图例行删掉；现在交给 ``PlotItem.removeItem``
    按 item 身份精确移除。
    """
    ka = view.add_pattern(_synth(500), name="dup")
    kb = view.add_pattern(_synth(500), name="dup")
    assert _legend_rows(view) == 2

    view.remove_pattern(ka)
    assert _plot_data_items(view) == 1
    assert _legend_rows(view) == 1
    # 剩下那条曲线仍然在图里，且 patterns() 只剩 kb
    assert set(view.patterns()) == {kb}


def test_clear_removes_every_legend_row(view):
    view.add_pattern(_synth(500), name="A")
    view.add_stick_pattern("P1", [25.0, 30.0], [100.0, 10.0])
    view.add_stick_pattern("P2", [27.0, 32.0], [100.0, 20.0])
    assert _legend_rows(view) == 3

    view.clear()
    assert _plot_data_items(view) == 0
    assert _legend_rows(view) == 0


def test_crosshair_readout_and_signal(qapp):
    view = PatternView()
    view.add_pattern(_synth(500), name="A")
    received: list[str] = []
    view.cursor_moved.connect(received.append)
    view.set_crosshair_position(30.0, 120.0)
    text = view._readout.toPlainText()
    assert "2θ" in text and "30.000" in text
    assert "120.0" in text
    assert "d =" in text
    assert received and received[-1] == text


def test_fifty_k_points_render_offscreen(qapp):
    view = PatternView()
    view.resize(640, 400)
    view.add_pattern(_synth(50_000), name="big")
    pix = view.grab()
    assert not pix.isNull()
    image = pix.toImage()
    # Sample the rendered image: background + axes + curve must produce >2 colors.
    colors = set()
    for yy in range(0, image.height(), 16):
        for xx in range(0, image.width(), 16):
            colors.add(image.pixelColor(xx, yy).rgb())
    assert len(colors) > 2


def _view_bg(view: PatternView) -> QtGui.QColor:
    """读谱图区背景色（pyqtgraph 0.13.7：setBackground 落到 QGraphicsView 笔刷）。"""
    return view.backgroundBrush().color()


def test_light_theme_plot_background_is_light(qapp):
    apply_theme(qapp, "light")
    view = PatternView()
    bg = _view_bg(view)
    assert bg.red() >= 220 and bg.green() >= 220 and bg.blue() >= 220


def test_dark_theme_plot_background_is_dark_non_black(qapp):
    apply_theme(qapp, "dark")
    view = PatternView()
    bg = _view_bg(view)
    assert bg.red() < 64 and bg.green() < 64 and bg.blue() < 64
    assert (bg.red(), bg.green(), bg.blue()) != (0, 0, 0)


def test_apply_theme_colors_idempotent_and_switches(qapp):
    apply_theme(qapp, "light")
    view = PatternView()
    light_bg = _view_bg(view)
    # 反复调用不抛异常。
    for _ in range(3):
        view.apply_theme_colors()
    # 切到深色后重设，颜色确实变化。
    apply_theme(qapp, "dark")
    view.apply_theme_colors()
    dark_bg = _view_bg(view)
    assert light_bg != dark_bg
    assert dark_bg.lightness() < light_bg.lightness()
    # 还原浅色，避免污染后续测试。
    apply_theme(qapp, "light")
