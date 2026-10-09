"""T13.2 — PatternView: multi-pattern overlay, crosshair, offscreen render."""

from __future__ import annotations

import numpy as np
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
