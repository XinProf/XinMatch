"""批次 3 接线 —— Profile Fitting 对话框（参考软件 F5）的单测。

覆盖：

* 对话框构造：谱形默认 pseudo-Voigt、初始峰数提示、结果表空、「应用到峰
  列表」禁用；
* 拟合：双高斯合成谱 + 近真值初值 → 结果表两行、Rwp 标签可见、拟合曲线
  叠加进谱图区（patterns 键数 +1）；
* 「应用到峰列表」发出精修峰；关闭对话框时叠加曲线被移除；
* 主窗口守卫：无谱图 / 峰列表为空 → information 提示不打开对话框；
* 模块动作 ``profile_fitting``（F5 快捷键同一入口）打开对话框；
* ``core.peak.profile_fit.fit_profile`` 本身的算法正确性由
  ``tests/peak`` 覆盖，这里只测 GUI 封装。
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np  # noqa: E402

from xinmatch.core.model.pattern import Pattern  # noqa: E402
from xinmatch.core.model.peak import Peak  # noqa: E402
from xinmatch.ui.main_window import MainWindow  # noqa: E402
from xinmatch.ui.profile_fit_dialog import ProfileFitDialog  # noqa: E402


def _synthetic_pattern() -> tuple[Pattern, list[Peak]]:
    """两支间隔 10° 的 Gaussian（FWHM 0.20°）叠加噪声底线。"""
    tt = np.linspace(20.0, 50.0, 1501)
    ii = np.full_like(tt, 5.0)
    for center, height in ((25.0, 500.0), (35.0, 250.0)):
        sigma = 0.20 / (2.0 * np.sqrt(2.0 * np.log(2.0)))
        ii = ii + height * np.exp(-0.5 * ((tt - center) / sigma) ** 2)
    pattern = Pattern(tt, ii)
    peaks = [Peak(two_theta=25.05, intensity=480.0, fwhm=0.22),
             Peak(two_theta=34.9, intensity=240.0, fwhm=0.22)]
    return pattern, peaks


def test_dialog_constructs(qapp):
    pattern, peaks = _synthetic_pattern()
    dlg = ProfileFitDialog(pattern, peaks, None)
    assert dlg._shape_combo.currentData() == "pseudo_voigt"
    assert dlg._table.rowCount() == 0
    assert not dlg._apply_button.isEnabled()
    assert dlg._rwp_label.isHidden()


def test_run_fit_fills_table_and_overlays(qapp):
    pattern, peaks = _synthetic_pattern()
    win = MainWindow()
    win.set_pattern(pattern)
    view = win.pattern_view
    dlg = ProfileFitDialog(pattern, peaks, view)
    assert len(view.patterns()) == 1  # 实验谱已在谱图区
    dlg._run_fit()
    assert dlg._table.rowCount() == 2
    assert not dlg._rwp_label.isHidden()
    assert dlg._apply_button.isEnabled()
    # Rwp 对合成谱应很小（模型与数据同形）
    assert "Rwp" in dlg._rwp_label.text()
    # 拟合曲线叠加：峰位置精修到 ±0.05° 内
    pos = float(dlg._table.item(0, 0).text())
    assert abs(pos - 25.0) < 0.05
    assert len(view.patterns()) == 2


def test_apply_emits_fitted_peaks(qapp):
    pattern, peaks = _synthetic_pattern()
    dlg = ProfileFitDialog(pattern, peaks, None)
    dlg._run_fit()
    got: list[list] = []
    dlg.fit_applied.connect(lambda p: got.append(p))
    dlg._apply_to_peak_list()
    assert len(got) == 1 and len(got[0]) == 2
    # 精修后峰带 FWHM 与面积强度
    assert got[0][0].fwhm is not None
    assert got[0][0].intensity > 0


def test_overlay_removed_on_close(qapp):
    pattern, peaks = _synthetic_pattern()
    win = MainWindow()
    win.set_pattern(pattern)
    view = win.pattern_view
    dlg = ProfileFitDialog(pattern, peaks, view)
    dlg._run_fit()
    assert len(view.patterns()) == 2
    dlg.close()
    assert len(view.patterns()) == 1


def test_refit_replaces_previous_overlay(qapp):
    """再次拟合替换上一条叠加曲线，而不是越叠越多。"""
    pattern, peaks = _synthetic_pattern()
    win = MainWindow()
    win.set_pattern(pattern)
    view = win.pattern_view
    dlg = ProfileFitDialog(pattern, peaks, view)
    dlg._run_fit()
    n_after_first = len(view.patterns())
    dlg._run_fit()
    assert len(view.patterns()) == n_after_first


# ---------------------------------------------------------------------------
# 主窗口守卫与模块动作
# ---------------------------------------------------------------------------
def test_main_window_guard_no_pattern(qapp, monkeypatch):
    from PySide6 import QtWidgets

    win = MainWindow()
    shown: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "information",
        lambda *a, **k: shown.append(a[1]),
    )
    win._open_profile_fit()
    assert shown == ["尚无谱图"]


def test_main_window_guard_no_peaks(qapp, monkeypatch):
    from PySide6 import QtWidgets

    win = MainWindow()
    win.set_pattern(Pattern(np.linspace(10.0, 80.0, 50), np.ones(50)))
    shown: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "information",
        lambda *a, **k: shown.append(a[1]),
    )
    win._open_profile_fit()
    assert shown == ["峰列表为空"]


def test_module_action_opens_dialog(qapp, monkeypatch):
    win = MainWindow()
    pattern, peaks = _synthetic_pattern()
    win.set_pattern(pattern)
    win.peak_table.set_peaks(peaks)
    opened: list[tuple] = []
    monkeypatch.setattr(
        ProfileFitDialog, "exec", lambda self: opened.append((self._pattern,)),
    )
    win.module_actions["profile_fitting"].trigger()
    assert len(opened) == 1
    assert opened[0][0] is pattern


def test_module_action_no_longer_placeholder(qapp, monkeypatch):
    from PySide6 import QtWidgets

    win = MainWindow()
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "information", lambda *a, **k: None
    )
    monkeypatch.setattr(ProfileFitDialog, "exec", lambda self: None)
    win.show()
    win.module_actions["profile_fitting"].trigger()
    assert "模块骨架已就位" not in win.statusBar().currentMessage()
