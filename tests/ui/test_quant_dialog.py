"""批次 4 接线 —— RIR 定量分析对话框（参考软件 quant_analysis_RIR）的单测。

覆盖：

* 对话框构造：每相主峰强度取 ``Phase.correlations`` 指向的实验峰最大
  积分强度，RIR 列默认 1.0 可编辑，wt% 列初始为「—」；
* 计算：两相强度 2:1、RIR 1:2 → wt% 50/50（Hill–Howard 绝热法，
  算法本身由 ``tests/quant`` 覆盖，这里只测 GUI 封装）；
* RIR 非数字 → 警告不崩；所有相强度 0 → 提示无可计算物相；
* 「应用到匹配列表」把 wt% 写回 ``Phase.weight_fraction``；
* 主窗口守卫：无已确认物相 → information 提示；
* 模块动作 ``quant_analysis`` 打开对话框且不再占位播报。
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from xinmatch.core.model.entry import Entry  # noqa: E402
from xinmatch.core.model.peak import Peak  # noqa: E402
from xinmatch.core.model.phase import Phase  # noqa: E402
from xinmatch.ui.main_window import MainWindow  # noqa: E402
from xinmatch.ui.quant_dialog import QuantDialog  # noqa: E402


def _mk_entry(entry_id: str, formula: str = "Si O2",
              mineral: str | None = None) -> Entry:
    return Entry(
        entry_id=entry_id,
        formula=formula,
        d_spacings=np.array([3.3, 2.4, 1.8]),
        intensities=np.array([1000.0, 600.0, 300.0]),
        mineral_name=mineral,
        quality="*",
    )


def _fixture() -> tuple[list[Peak], list[Phase]]:
    """两相：A 匹配到峰 0（强度 200）/ 峰 1（强度 100）→ 主峰 200；
    B 匹配到峰 1（强度 100）→ 主峰 100。2:1 强度、1:2 RIR → wt% 50/50。"""
    peaks = [
        Peak(two_theta=25.0, intensity=200.0),
        Peak(two_theta=35.0, intensity=100.0),
    ]
    phase_a = Phase(entry=_mk_entry("96-900-0001", "Al2 Be3 Si6 O18", "Beryl"))
    phase_a.correlations = [(0, 0), (1, 1)]
    phase_b = Phase(entry=_mk_entry("96-900-0004", "C Ca O3", "Calcite"))
    phase_b.correlations = [(1, 0)]
    return peaks, [phase_a, phase_b]


def test_dialog_constructs_with_correlation_intensities(qapp):
    peaks, phases = _fixture()
    dlg = QuantDialog(phases, peaks)
    # A 主峰 = max(200, 100) = 200；B 主峰 = 100
    assert dlg._table.item(0, 1).text().startswith("200")
    assert dlg._table.item(1, 1).text().startswith("100")
    assert dlg._table.item(0, 3).text() == "—"
    assert dlg._table.item(0, 2).text() == "1.0"
    assert not dlg._apply_button.isEnabled()


def test_calc_fills_weight_fractions(qapp):
    peaks, phases = _fixture()
    dlg = QuantDialog(phases, peaks)
    # A: I=200 RIR=2 → 100；B: I=100 RIR=1 → 100 → 各 50 %
    dlg._table.item(0, 2).setText("2.0")
    dlg._table.item(1, 2).setText("1.0")
    dlg._run_calc()
    assert dlg._table.item(0, 3).text() == "50.00"
    assert dlg._table.item(1, 3).text() == "50.00"
    assert dlg._apply_button.isEnabled()


def test_calc_invalid_rir_warns(qapp, monkeypatch):
    from PySide6 import QtWidgets

    peaks, phases = _fixture()
    dlg = QuantDialog(phases, peaks)
    dlg._table.item(0, 2).setText("abc")
    shown: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "warning",
        lambda *a, **k: shown.append(a[1]),
    )
    dlg._run_calc()
    assert shown and not dlg._apply_button.isEnabled()


def test_calc_all_zero_intensity_prompts(qapp, monkeypatch):
    from PySide6 import QtWidgets

    peaks, phases = _fixture()
    for p in phases:
        p.correlations = []  # 无匹配 → 强度 0
    dlg = QuantDialog(phases, peaks)
    shown: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "information",
        lambda *a, **k: shown.append(a[1]),
    )
    dlg._run_calc()
    assert shown and not dlg._apply_button.isEnabled()


def test_apply_writes_weight_fraction(qapp):
    peaks, phases = _fixture()
    dlg = QuantDialog(phases, peaks)
    dlg._run_calc()
    got: list[list] = []
    dlg.quant_applied.connect(lambda ps: got.append(ps))
    dlg._apply()
    assert len(got) == 1
    a, b = got[0]
    assert a.weight_fraction == pytest.approx(2 / 3)
    assert b.weight_fraction == pytest.approx(1 / 3)


def test_main_window_guard_no_phases(qapp, monkeypatch):
    from PySide6 import QtWidgets

    win = MainWindow()
    shown: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "information",
        lambda *a, **k: shown.append(a[1]),
    )
    win._open_quant_dialog()
    assert shown == ["无已确认物相"]


def test_module_action_opens_dialog(qapp, monkeypatch):
    win = MainWindow()
    peaks, phases = _fixture()
    win.match_table.set_phases(phases)
    win.peak_table.set_peaks(peaks)
    opened: list[int] = []
    monkeypatch.setattr(
        QuantDialog, "exec", lambda self: opened.append(1),
    )
    win.module_actions["quant_analysis"].trigger()
    assert opened == [1]


def test_module_action_no_longer_placeholder(qapp, monkeypatch):
    from PySide6 import QtWidgets

    win = MainWindow()
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "information", lambda *a, **k: None
    )
    monkeypatch.setattr(QuantDialog, "exec", lambda self: None)
    win.show()
    win.module_actions["quant_analysis"].trigger()
    assert "模块骨架已就位" not in win.statusBar().currentMessage()
