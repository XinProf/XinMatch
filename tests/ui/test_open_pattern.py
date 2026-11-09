"""v1.0.0 体验修订：打开/导入 XRD 数据 + Search-Match 真实接线。

Offscreen GUI tests for the file→open-data flow, search-match wiring, and
report preview.  All fixtures are hermetic: synthetic ASCII data files are
written to ``tmp_path``; external DB / search calls are monkeypatched.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PySide6 import QtWidgets

from xinmatch.core.model.entry import CellParams, Entry
from xinmatch.core.model.pattern import Pattern
from xinmatch.core.search.fom import CandidateResult
from xinmatch.ui.main_window import MainWindow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _write_synthetic_2col(path, n: int = 1401) -> None:
    """Write a two-column ASCII file: 2θ = 10..80° step 0.05 with peaks."""
    two_theta = np.linspace(10.0, 80.0, n)
    # 模拟几个衍射峰 + 平坦背景。
    intensity = np.full_like(two_theta, 100.0)
    for center in (28.5, 47.3, 56.1):
        intensity += 800.0 * np.exp(-((two_theta - center) / 0.3) ** 2)
    lines = [
        f"{x:.5f} {y:.2f}"
        for x, y in zip(two_theta, intensity, strict=True)
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _cand(entry_id: str, formula: str = "X") -> CandidateResult:
    return CandidateResult(
        entry=Entry(
            entry_id=entry_id,
            formula=formula,
            d_spacings=np.array([2.5, 1.8]),
            intensities=np.array([100.0, 50.0]),
            cell=CellParams(3.0, 3.0, 5.0),
        ),
        fom=0.9,
    )


def _synthetic_pattern() -> Pattern:
    two_theta = np.linspace(10.0, 80.0, 1401)
    intensity = np.full_like(two_theta, 100.0)
    for center in (28.5, 47.3, 56.1):
        intensity += 800.0 * np.exp(-((two_theta - center) / 0.3) ** 2)
    return Pattern(two_theta=two_theta, intensity=intensity)


# ---------------------------------------------------------------------------
# 1. 打开成功
# ---------------------------------------------------------------------------
def test_open_data_success_loads_pattern(qapp, tmp_path):
    f = tmp_path / "sample.txt"
    _write_synthetic_2col(f)
    win = MainWindow()
    with patch(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        return_value=(str(f), ""),
    ):
        win.open_action.trigger()
    assert win.pattern_view.patterns(), "pattern_view should have ≥1 curve"
    assert win._current_pattern is not None
    msg = win.statusBar().currentMessage()
    assert "已打开" in msg
    assert "点" in msg


# ---------------------------------------------------------------------------
# 2. 打开取消
# ---------------------------------------------------------------------------
def test_open_data_cancel_does_nothing(qapp):
    win = MainWindow()
    with patch(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        return_value=("", ""),
    ):
        win.open_action.trigger()
    assert win.pattern_view.patterns() == {}
    assert win._current_pattern is None


# ---------------------------------------------------------------------------
# 3. 坏文件
# ---------------------------------------------------------------------------
def test_open_data_bad_file_warns(qapp, tmp_path):
    f = tmp_path / "junk.txt"
    f.write_text("hello world\nthis is not diffraction data\n", encoding="utf-8")
    win = MainWindow()
    with patch(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        return_value=(str(f), ""),
    ), patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn:
        win.open_action.trigger()
    mock_warn.assert_called()
    # 坏文件不应清空已有谱图（这里本来就没有，只断言不崩溃 + warning 被调）。


# ---------------------------------------------------------------------------
# 4. 检索成功
# ---------------------------------------------------------------------------
def test_search_match_success_fills_tables(qapp):
    """峰列表 FoM 接线（v3.6.3 起**不是**默认，必须显式切过去）。

    这里打桩的是 ``main_window.search_match``（峰列表 FoM 入口）；默认改成
    FPFM 后会走 ``_search_fpfm``，桩不会命中。这是「改默认值最容易被带崩的
    旧测试」之一：它测的是峰列表接线，就让它显式选峰列表，别依赖默认值。
    """
    win = MainWindow()
    win.set_pattern(_synthetic_pattern())
    win._search_mode_combo.setCurrentIndex(0)
    assert win._search_mode == "peaks_fom"
    fake_conn = MagicMock()
    fake_results = [_cand("96-100-0001"), _cand("96-100-0002", formula="Y")]
    with patch.object(
        MainWindow, "open_search_library", return_value=fake_conn
    ), patch(
        "xinmatch.ui.main_window.search_match", return_value=fake_results
    ):
        win.module_actions["search_match"].trigger()
    assert win.candidate_table.model().rowCount() > 0
    assert len(win._candidates) == 2
    assert win.peak_table.model().rowCount() > 0
    msg = win.statusBar().currentMessage()
    assert "候选" in msg


# ---------------------------------------------------------------------------
# 5. 检索无谱图
# ---------------------------------------------------------------------------
def test_search_match_without_pattern_informs(qapp):
    win = MainWindow()
    with patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
        win.module_actions["search_match"].trigger()
    mock_info.assert_called()
    assert win._candidates == []


# ---------------------------------------------------------------------------
# 6. 报告预览
# ---------------------------------------------------------------------------
def test_report_preview_dialog_shown(qapp):
    win = MainWindow()
    win.set_pattern(_synthetic_pattern())
    win.set_candidates([_cand("96-100-0001")])
    opened: list = []

    def _tracking_exec(self):
        opened.append(self)
        return 0

    with patch(
        "xinmatch.ui.main_window.render_text", return_value="FAKE_REPORT_TEXT"
    ), patch.object(QtWidgets.QDialog, "exec", _tracking_exec):
        win._run_report_preview()
    assert len(opened) == 1
    dlg = opened[0]
    # 对话框内应有只读 QPlainTextEdit，且包含 render_text 的输出。
    edits = dlg.findChildren(QtWidgets.QPlainTextEdit)
    assert edits, "report preview dialog should contain a QPlainTextEdit"
    assert "FAKE_REPORT_TEXT" in edits[0].toPlainText()
    assert edits[0].isReadOnly()


def test_report_preview_without_candidates_informs(qapp):
    win = MainWindow()
    with patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
        win.module_actions["report_print"].trigger()
    mock_info.assert_called()


# ---------------------------------------------------------------------------
# 7. _toggle_theme 防御性（apply_theme_colors 不存在时不崩）
# ---------------------------------------------------------------------------
def test_toggle_theme_without_apply_theme_colors_does_not_crash(qapp):
    win = MainWindow()
    # apply_theme_colors 可能由并行任务加入（存在则调用，不存在则 getattr 回退）；
    # 两种情况下 _toggle_theme 都不应崩溃。
    win._toggle_theme()


# ---------------------------------------------------------------------------
# 8. 岛津二进制 .raw 经 GUI 打开（真实样品，数据缺失时跳过）
# ---------------------------------------------------------------------------
def test_open_shimadzu_raw_via_gui(qapp):
    raw = Path(r"D:\Project\XRD\XRData\Shimadzu Data\Std\Si\Si.RAW")
    if not raw.exists():
        pytest.skip("Shimadzu 数据集不在本机")
    win = MainWindow()
    with patch(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        return_value=(str(raw), ""),
    ):
        win.open_action.trigger()
    assert win.pattern_view.patterns(), "Shimadzu .raw 应载入 ≥1 条谱线"
    assert win._current_pattern is not None
    assert win._current_pattern.step == pytest.approx(0.02)
    assert len(win._current_pattern) == 5751
    msg = win.statusBar().currentMessage()
    assert "已打开" in msg
    assert "Si.RAW" in msg
