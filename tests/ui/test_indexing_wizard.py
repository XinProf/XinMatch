"""批次 6 接线 —— 指标化向导（Treor90 / DicVol06）单测。

覆盖：

* 构造：算法默认 Treor90、波长取谱图、容差 0.05°、默认勾选高对称四系；
* 立方合成谱（a = 4.0 Å）→ 结果表出现 ``cubic a ≈ 4.0000`` 且 6/6 全指标化
  （**不断言首行**：立方解也可被四方胞等效描述，Treor 的首位常是
  ``a=2.0, c=2.3094`` 的同 FoM 四方解）；
* 参数守卫：未勾任何晶体系统 / 参与峰少于 4 个；
* 算法切换真的调用 ``index_dicvol``，并把勾选的晶体系统按高对称序传入；
* 空解 → 「未找到候选解」提示且复制按钮禁用；
* 选中行复制单胞参数到剪贴板；
* 主窗口守卫：无谱图 / 峰列表为空；
* 模块动作 ``indexing`` 打开向导且不再占位播报。
"""

from __future__ import annotations

import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from xinmatch.core.model.pattern import Pattern  # noqa: E402
from xinmatch.core.model.peak import Peak  # noqa: E402
from xinmatch.ui import indexing_wizard as iw  # noqa: E402
from xinmatch.ui.indexing_wizard import IndexingWizard  # noqa: E402
from xinmatch.ui.main_window import MainWindow  # noqa: E402

_LAMBDA = 1.5406


def _pattern(wavelength: float = _LAMBDA) -> Pattern:
    return Pattern(
        two_theta=np.linspace(10.0, 120.0, 1100),
        intensity=np.zeros(1100),
        wavelength=wavelength,
    )


def _cubic_peaks(a: float = 4.0, hkls=None) -> list[Peak]:
    """由 a 与 hkl 生成带精确 2θ 的峰（d = a/√N，2θ = 2 asin(λ/2d)）。"""
    if hkls is None:
        hkls = [(1, 1, 1), (2, 0, 0), (2, 2, 0), (3, 1, 1), (2, 2, 2), (4, 0, 0)]
    peaks = []
    for h, k, ll in hkls:
        d = a / math.sqrt(h * h + k * k + ll * ll)
        two_theta = 2.0 * math.degrees(math.asin(_LAMBDA / (2.0 * d)))
        peaks.append(Peak(two_theta=two_theta, intensity=1000.0))
    return peaks


# ----------------------------------------------------------------------
def test_construct_defaults(qapp):
    dlg = IndexingWizard(_pattern(1.7889), _cubic_peaks())
    assert dlg._algo_combo.currentData() == "treor"
    assert dlg._algo_combo.count() == 2
    assert dlg._lambda_spin.value() == pytest.approx(1.7889)
    assert dlg._tol_spin.value() == pytest.approx(0.05)
    checked = {k for k, b in dlg._system_checks.items() if b.isChecked()}
    assert checked == {"cubic", "tetragonal", "hexagonal", "orthorhombic"}
    assert dlg._table.rowCount() == 0
    assert not dlg._copy_button.isEnabled()
    assert "未计算" in dlg._summary.text()


def test_run_index_finds_cubic_cell(qapp):
    peaks = _cubic_peaks(4.0)
    dlg = IndexingWizard(_pattern(), peaks)
    dlg._run_index()
    assert dlg._table.rowCount() > 0
    assert dlg._copy_button.isEnabled()
    assert "候选解" in dlg._summary.text()
    # 存在一行 cubic 且 a ≈ 4.0，且该行 6/6 全指标化
    rows = [
        (dlg._table.item(r, 0).text(), float(dlg._table.item(r, 1).text()),
         dlg._table.item(r, 8).text())
        for r in range(dlg._table.rowCount())
    ]
    cubic = [r for r in rows if r[0] == "cubic" and abs(r[1] - 4.0) < 0.01]
    assert cubic, rows[:5]
    assert cubic[0][2] == "6/6"


def test_no_system_selected_prompts(qapp, monkeypatch):
    from PySide6 import QtWidgets

    dlg = IndexingWizard(_pattern(), _cubic_peaks())
    for box in dlg._system_checks.values():
        box.setChecked(False)
    shown: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "information",
        lambda *a, **k: shown.append(a[1]),
    )
    dlg._run_index()
    assert shown == ["未选择晶体系统"]
    assert dlg._table.rowCount() == 0


def test_too_few_peaks_prompts(qapp, monkeypatch):
    from PySide6 import QtWidgets

    dlg = IndexingWizard(_pattern(), _cubic_peaks(hkls=[(1, 1, 1), (2, 0, 0), (2, 2, 0)]))
    shown: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "information",
        lambda *a, **k: shown.append(a[1]),
    )
    dlg._run_index()
    assert shown == ["峰太少"]


def test_excluded_peaks_are_not_used(qapp, monkeypatch):
    from PySide6 import QtWidgets

    peaks = _cubic_peaks()
    for p in peaks[:3]:
        p.excluded = True
    dlg = IndexingWizard(_pattern(), peaks)
    assert "跳过已排除 3 个" in dlg._info_label.text()
    assert "参与指标化 3 个" in dlg._info_label.text()
    shown: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "information",
        lambda *a, **k: shown.append(a[1]),
    )
    dlg._run_index()
    # 只剩 3 个峰 → 峰太少
    assert shown == ["峰太少"]


def test_dicvol_engine_and_system_order(qapp, monkeypatch):
    calls: list[dict] = []

    def fake_dicvol(peaks_d, **kwargs):
        calls.append({"peaks_d": list(peaks_d), **kwargs})
        return []

    monkeypatch.setattr(iw, "index_dicvol", fake_dicvol)
    dlg = IndexingWizard(_pattern(), _cubic_peaks())
    dlg._algo_combo.setCurrentIndex(1)  # DicVol06
    for key in ("trigonal", "triclinic"):
        dlg._system_checks[key].setChecked(True)
    dlg._run_index()
    assert len(calls) == 1
    assert calls[0]["crystal_systems"] == [
        "cubic", "tetragonal", "hexagonal", "trigonal", "orthorhombic",
        "triclinic",
    ]
    assert calls[0]["tolerance"] == pytest.approx(0.05)
    assert calls[0]["wavelength"] == pytest.approx(_LAMBDA)
    assert len(calls[0]["peaks_d"]) == 6


def test_empty_solutions_summary(qapp, monkeypatch):
    monkeypatch.setattr(iw, "index_treor", lambda *a, **k: [])
    dlg = IndexingWizard(_pattern(), _cubic_peaks())
    dlg._run_index()
    assert dlg._table.rowCount() == 0
    assert "未找到候选解" in dlg._summary.text()
    assert not dlg._copy_button.isEnabled()


def test_copy_selected_cell(qapp):
    from PySide6 import QtWidgets

    dlg = IndexingWizard(_pattern(), _cubic_peaks())
    dlg._run_index()
    dlg._table.selectRow(0)
    dlg._copy_selected()
    text = QtWidgets.QApplication.clipboard().text()
    assert "a=" in text and "alpha=" in text
    assert "已复制单胞参数到剪贴板" in dlg._summary.text()


# ----------------------------------------------------------------------
def test_main_window_guard_no_pattern(qapp, monkeypatch):
    from PySide6 import QtWidgets

    win = MainWindow()
    shown: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "information",
        lambda *a, **k: shown.append(a[1]),
    )
    win._open_indexing_wizard()
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
    win._open_indexing_wizard()
    assert shown == ["峰列表为空"]


def test_module_action_opens_wizard(qapp, monkeypatch):
    win = MainWindow()
    win.set_pattern(_pattern())
    win.peak_table.set_peaks(_cubic_peaks())
    opened: list[int] = []
    monkeypatch.setattr(
        IndexingWizard, "exec", lambda self: opened.append(1),
    )
    win.module_actions["indexing"].trigger()
    assert opened == [1]


def test_module_action_no_longer_placeholder(qapp, monkeypatch):
    win = MainWindow()
    win.set_pattern(_pattern())
    win.peak_table.set_peaks(_cubic_peaks())
    monkeypatch.setattr(IndexingWizard, "exec", lambda self: None)
    win.show()
    win.module_actions["indexing"].trigger()
    assert "模块骨架已就位" not in win.statusBar().currentMessage()
