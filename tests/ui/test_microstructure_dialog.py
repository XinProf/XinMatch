"""批次 5 接线 —— 微结构分析对话框（Scherrer / Williamson-Hall）单测。

覆盖：

* 构造：波长默认取谱图波长、K 默认 0.9、两页初始「（未计算）」；
* Scherrer：单峰数值与手算一致、无 FWHM 的峰被跳过、算术平均；
* Williamson-Hall：纯尺寸合成峰 → D 复原、纯应变合成峰 → ε 复原、
  回归数据表与峰顺序对齐；
* 单峰时 W-H 给出「无法拟合」提示但 Scherrer 页照常出结果（不互相阻断）；
* 峰列表全无 FWHM → information 提示且不计算；
* 主窗口守卫：无谱图 / 峰列表为空；
* 模块动作 ``microstructure`` 打开对话框且不再占位播报。
"""

from __future__ import annotations

import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from xinmatch.core.model.pattern import Pattern  # noqa: E402
from xinmatch.core.model.peak import Peak  # noqa: E402
from xinmatch.ui.main_window import MainWindow  # noqa: E402
from xinmatch.ui.microstructure_dialog import MicrostructureDialog  # noqa: E402

_LAMBDA = 1.5406
_K = 0.9


def _pattern(wavelength: float = _LAMBDA) -> Pattern:
    return Pattern(
        two_theta=np.linspace(10.0, 80.0, 700),
        intensity=np.zeros(700),
        wavelength=wavelength,
    )


def _scherrer_expected(two_theta: float, fwhm_deg: float) -> float:
    """手算 D (nm)：K λ / (β_rad cos θ)，θ = 2θ/2。"""
    beta_rad = math.radians(fwhm_deg)
    cos_theta = math.cos(math.radians(two_theta / 2.0))
    return _K * _LAMBDA / (beta_rad * cos_theta) / 10.0


def _size_only_peaks(d_nm: float, two_thetas=(20.0, 40.0, 60.0)) -> list[Peak]:
    """纯尺寸宽化（β ∝ 1/cos θ，截距 Kλ/D、斜率 0）。"""
    peaks = []
    for tt in two_thetas:
        cos_theta = math.cos(math.radians(tt / 2.0))
        beta_rad = _K * _LAMBDA / (d_nm * 10.0 * cos_theta)
        peaks.append(Peak(two_theta=tt, intensity=1000.0,
                          fwhm=math.degrees(beta_rad)))
    return peaks


def _strain_only_peaks(strain: float, two_thetas=(20.0, 40.0, 60.0)) -> list[Peak]:
    """纯应变宽化（β = 4ε·tan θ → βcosθ 线性于 sinθ，截距 0、斜率 ε）。"""
    peaks = []
    for tt in two_thetas:
        tan_theta = math.tan(math.radians(tt / 2.0))
        beta_rad = 4.0 * strain * tan_theta
        peaks.append(Peak(two_theta=tt, intensity=1000.0,
                          fwhm=math.degrees(beta_rad)))
    return peaks


def _fwhm_peaks() -> list[Peak]:
    return [
        Peak(two_theta=25.0, intensity=1000.0, fwhm=0.2000),
        Peak(two_theta=45.0, intensity=600.0, fwhm=0.2500),
    ]


# ----------------------------------------------------------------------
def test_construct_defaults(qapp):
    dlg = MicrostructureDialog(_pattern(1.7889), _fwhm_peaks())
    assert dlg._lambda_spin.value() == pytest.approx(1.7889)
    assert dlg._k_spin.value() == pytest.approx(0.9)
    assert dlg._tabs.count() == 2
    assert dlg._tabs.tabText(0) == "Scherrer"
    assert dlg._tabs.tabText(1) == "Williamson-Hall"
    assert dlg._scherrer_table.rowCount() == 0
    assert dlg._wh_table.rowCount() == 0
    assert "未计算" in dlg._scherrer_summary.text()
    assert "未计算" in dlg._wh_result.text()


def test_scherrer_value_matches_hand_calc(qapp):
    peaks = [Peak(two_theta=30.0, intensity=1000.0, fwhm=0.2)]
    dlg = MicrostructureDialog(_pattern(), peaks)
    dlg._run_calc()
    assert dlg._scherrer_table.rowCount() == 1
    shown = float(dlg._scherrer_table.item(0, 2).text())
    assert shown == pytest.approx(_scherrer_expected(30.0, 0.2), rel=1e-3)
    assert "平均晶粒尺寸" in dlg._scherrer_summary.text()


def test_scherrer_skips_peaks_without_fwhm(qapp):
    peaks = [
        Peak(two_theta=25.0, intensity=1000.0, fwhm=None),
        Peak(two_theta=30.0, intensity=800.0, fwhm=0.0),
        Peak(two_theta=35.0, intensity=600.0, fwhm=0.1500),
    ]
    dlg = MicrostructureDialog(_pattern(), peaks)
    dlg._run_calc()
    # 只有一个峰带有效 FWHM → 表 1 行，且 2θ 是 35°
    assert dlg._scherrer_table.rowCount() == 1
    assert float(dlg._scherrer_table.item(0, 0).text()) == pytest.approx(35.0)


def test_scherrer_mean_is_arithmetic(qapp):
    peaks = _fwhm_peaks()
    dlg = MicrostructureDialog(_pattern(), peaks)
    dlg._run_calc()
    d1 = _scherrer_expected(peaks[0].two_theta, peaks[0].fwhm)
    d2 = _scherrer_expected(peaks[1].two_theta, peaks[1].fwhm)
    assert "平均晶粒尺寸" in dlg._scherrer_summary.text()
    shown = float(
        dlg._scherrer_summary.text().split("D = ")[1].split(" nm")[0]
    )
    assert shown == pytest.approx((d1 + d2) / 2.0, rel=1e-3)


def test_wh_recovers_size_from_size_only_peaks(qapp):
    dlg = MicrostructureDialog(_pattern(), _size_only_peaks(50.0))
    dlg._run_calc()
    text = dlg._wh_result.text()
    assert "50.00 nm" in text
    assert "R² = " in text
    assert "n = 3" in text
    assert dlg._wh_table.rowCount() == 3


def test_wh_recovers_strain_from_strain_only_peaks(qapp):
    dlg = MicrostructureDialog(_pattern(), _strain_only_peaks(0.002))
    dlg._run_calc()
    assert "2.000e-03" in dlg._wh_result.text()


def test_wh_table_rows_follow_peak_order(qapp):
    peaks = _fwhm_peaks()
    dlg = MicrostructureDialog(_pattern(), peaks)
    dlg._run_calc()
    assert dlg._wh_table.rowCount() == 2
    assert float(dlg._wh_table.item(0, 0).text()) == pytest.approx(
        peaks[0].two_theta
    )
    assert float(dlg._wh_table.item(1, 0).text()) == pytest.approx(
        peaks[1].two_theta
    )
    # x = 4 sinθ/λ 与峰位一致
    x0 = 4.0 * math.sin(math.radians(peaks[0].two_theta / 2.0)) / _LAMBDA
    assert float(dlg._wh_table.item(0, 1).text()) == pytest.approx(x0, rel=1e-5)


def test_wh_single_peak_warns_but_scherrer_still_works(qapp):
    peaks = [Peak(two_theta=30.0, intensity=1000.0, fwhm=0.2)]
    dlg = MicrostructureDialog(_pattern(), peaks)
    dlg._run_calc()
    assert "无法做 Williamson-Hall 拟合" in dlg._wh_result.text()
    assert dlg._wh_table.rowCount() == 0
    # Scherrer 页不受影响
    assert dlg._scherrer_table.rowCount() == 1


def test_no_fwhm_prompts_and_skips(qapp, monkeypatch):
    from PySide6 import QtWidgets

    peaks = [Peak(two_theta=25.0, intensity=1000.0)]
    dlg = MicrostructureDialog(_pattern(), peaks)
    shown: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "information",
        lambda *a, **k: shown.append(a[1]),
    )
    dlg._run_calc()
    assert shown == ["没有可用的 FWHM"]
    assert dlg._scherrer_table.rowCount() == 0
    assert "未计算" in dlg._wh_result.text()


# ----------------------------------------------------------------------
def test_main_window_guard_no_pattern(qapp, monkeypatch):
    from PySide6 import QtWidgets

    win = MainWindow()
    shown: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "information",
        lambda *a, **k: shown.append(a[1]),
    )
    win._open_microstructure()
    assert shown == ["尚无谱图"]


def test_main_window_guard_empty_peaks(qapp, monkeypatch):
    from PySide6 import QtWidgets

    win = MainWindow()
    win.set_pattern(_pattern())
    shown: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "information",
        lambda *a, **k: shown.append(a[1]),
    )
    win._open_microstructure()
    assert shown == ["峰列表为空"]


def test_module_action_opens_dialog(qapp, monkeypatch):
    win = MainWindow()
    win.set_pattern(_pattern())
    win.peak_table.set_peaks(_fwhm_peaks())
    opened: list[int] = []
    monkeypatch.setattr(
        MicrostructureDialog, "exec", lambda self: opened.append(1),
    )
    win.module_actions["microstructure"].trigger()
    assert opened == [1]


def test_module_action_no_longer_placeholder(qapp, monkeypatch):
    win = MainWindow()
    win.set_pattern(_pattern())
    win.peak_table.set_peaks(_fwhm_peaks())
    monkeypatch.setattr(MicrostructureDialog, "exec", lambda self: None)
    win.show()
    win.module_actions["microstructure"].trigger()
    assert "模块骨架已就位" not in win.statusBar().currentMessage()
