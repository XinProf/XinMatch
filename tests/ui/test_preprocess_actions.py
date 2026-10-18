"""v1.7.x：工具栏预处理动作接线测试（平滑 / 背景扣除 / Kα2 剥离 / 重置 / 峰检测）。

此前这 5 个动作只是 ``_placeholder``，触发后仅在状态栏喊一句；核心层
``core.preprocess`` 早已具备全部能力。本测试锁定接线后的行为：

* 处理结果**替换**当前曲线（``pattern_view`` 始终只有 1 条曲线，不叠图）；
* 「重置」回到打开时的原始谱（``_raw_pattern`` 未被预处理污染）；
* 峰检测把结果填进峰列表，不改动谱图数据；
* 未载入数据时给出提示而不是崩溃。
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np

from xinmatch.core.model.pattern import Pattern
from xinmatch.ui.main_window import MainWindow


def _pattern() -> Pattern:
    """3 个高斯峰 + 平坦背景 + 轻微基线起伏。"""
    x = np.linspace(10.0, 80.0, 1401)
    y = 100.0 + 2.0 * np.sin(x)
    for center in (28.5, 47.3, 56.1):
        y = y + 800.0 * np.exp(-((x - center) / 0.3) ** 2)
    return Pattern(two_theta=x, intensity=y)


def _loaded_window(qapp) -> MainWindow:
    """等价于「打开数据」成功后的状态（走真实的 _apply_loaded_pattern）。"""
    win = MainWindow()
    win._apply_loaded_pattern(_pattern(), "sample.dat")
    return win


def test_smoothing_replaces_curve_instead_of_stacking(qapp):
    win = _loaded_window(qapp)
    before = win._current_pattern.intensity.copy()
    win.smooth_action.trigger()
    assert len(win.pattern_view.patterns()) == 1, "预处理应替换曲线而不是叠加"
    assert not np.allclose(win._current_pattern.intensity, before)
    assert win._current_pattern.two_theta.shape == before.shape


def test_background_subtraction_lowers_flat_regions(qapp):
    win = _loaded_window(qapp)
    before = float(np.median(win._current_pattern.intensity))
    win.background_action.trigger()
    after = float(np.median(win._current_pattern.intensity))
    assert after < before
    assert len(win.pattern_view.patterns()) == 1


def test_alpha2_strip_keeps_shape(qapp):
    win = _loaded_window(qapp)
    shape = win._current_pattern.intensity.shape
    win.ko2_action.trigger()
    assert win._current_pattern.intensity.shape == shape
    assert len(win.pattern_view.patterns()) == 1


def test_reset_restores_raw_pattern(qapp):
    win = _loaded_window(qapp)
    raw = win._raw_pattern.intensity.copy()
    win.smooth_action.trigger()
    assert not np.allclose(win._current_pattern.intensity, raw)
    win.reset_action.trigger()
    assert np.allclose(win._current_pattern.intensity, raw)
    assert len(win.pattern_view.patterns()) == 1


def test_peak_detection_fills_peak_table(qapp):
    win = _loaded_window(qapp)
    intensity_before = win._current_pattern.intensity.copy()
    win.peakdetect_action.trigger()
    assert win.peak_table.model().rowCount() >= 3
    # 峰检测不改动谱图数据。
    assert np.allclose(win._current_pattern.intensity, intensity_before)


def test_preprocess_without_data_informs(qapp):
    win = MainWindow()
    with patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
        win.smooth_action.trigger()
    mock_info.assert_called()
    assert win._current_pattern is None


def test_toolbar_actions_are_wired_not_placeholders(qapp):
    """5 个动作不再指向 ``_placeholder``（触发后不会写「占位」状态）。"""
    win = _loaded_window(qapp)
    with patch.object(win, "_placeholder") as mock_placeholder:
        for action in (
            win.background_action,
            win.smooth_action,
            win.ko2_action,
            win.reset_action,
            win.peakdetect_action,
        ):
            action.trigger()
    mock_placeholder.assert_not_called()
