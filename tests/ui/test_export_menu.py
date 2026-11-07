"""批次 2 接线 —— 「数据导出」聚合菜单与三张表 CSV 导出的单测。

覆盖：

* ``data_export`` 模块动作带聚合子菜单（谱图 ×2 / 峰列表 / 候选 / 匹配 +
  既有的 .xinm 项目 / 所选相 CIF，共 7 项）；
* 谱图 ASCII 导出（profile 头格式 / 两列）落盘且可被 ``core.io.free``
  的读取函数原样读回；
* 峰列表 / 候选列表 / 匹配列表 CSV 导出（表头 + 行数 + 编码 utf-8-sig）；
* 空数据守卫（无谱图 / 无峰 / 无候选 / 无匹配 → 提示框，不抛异常）；
* 三张表的 ``export_requested`` 右键信号接到同一批导出方法。
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from xinmatch.core.io.free import (  # noqa: E402
    read_ascii_profile_2col,
    read_ascii_profile_3col,
)
from xinmatch.core.model.entry import Entry  # noqa: E402
from xinmatch.core.model.pattern import Pattern  # noqa: E402
from xinmatch.core.model.peak import Peak  # noqa: E402
from xinmatch.core.model.phase import Phase  # noqa: E402
from xinmatch.core.search.fom import CandidateResult  # noqa: E402
from xinmatch.ui.main_window import MainWindow  # noqa: E402

_EXPECTED_EXPORT_ITEMS = (
    "导出谱图 (ASCII profile)…",
    "导出谱图 (两列 2θ–I)…",
    "导出峰列表 (CSV)…",
    "导出候选列表 (CSV)…",
    "导出匹配列表 (CSV)…",
    "导出物相分析（.xinm）…",
    "导出所选相 CIF…",
)


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


def _mk_candidate(fom: float, entry_id: str, formula: str = "Si O2") -> CandidateResult:
    return CandidateResult(
        entry=_mk_entry(entry_id, formula=formula),
        fom=fom,
        p_values={"peakpos": 0.9, "intensity": 0.8},
        i_scale=1.0,
    )


def _save_dialog(tmp_path, monkeypatch, filename: str):
    """Patch QFileDialog.getSaveFileName to return *filename* under tmp_path."""
    from PySide6 import QtWidgets

    target = str(tmp_path / filename)

    def _fake(*_args, **_kwargs):
        return target, ""

    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", _fake)
    return target


# ---------------------------------------------------------------------------
# 聚合菜单
# ---------------------------------------------------------------------------
def test_data_export_has_aggregated_menu(qapp):
    win = MainWindow()
    menu = win.module_actions["data_export"].menu()
    assert menu is not None
    texts = [a.text() for a in menu.actions()]  # 分隔符条目 text 为空串
    assert texts == list(_EXPECTED_EXPORT_ITEMS[:5]) + [""] + \
        list(_EXPECTED_EXPORT_ITEMS[5:])
    # 与既有动作同对象：改一个地方两处同步
    assert menu.actions()[6] is win.export_xinm_action
    assert menu.actions()[7] is win.export_cifs_action


def test_data_export_no_longer_placeholder(qapp):
    """data_export 已接线：触发动作不再走占位播报。"""
    win = MainWindow()
    win.show()
    win.module_actions["data_export"].trigger()
    assert "模块骨架已就位" not in win.statusBar().currentMessage()


# ---------------------------------------------------------------------------
# 谱图 ASCII
# ---------------------------------------------------------------------------
def test_export_pattern_profile_roundtrip(qapp, tmp_path, monkeypatch):
    win = MainWindow()
    win.set_pattern(Pattern(np.linspace(10.0, 80.0, 141), np.arange(141, dtype=float)))
    target = _save_dialog(tmp_path, monkeypatch, "pattern.txt")
    win._export_pattern_ascii("profile")
    assert (tmp_path / "pattern.txt").exists()
    back = read_ascii_profile_3col(target)
    np.testing.assert_allclose(back.two_theta, np.linspace(10.0, 80.0, 141))


def test_export_pattern_2col_roundtrip(qapp, tmp_path, monkeypatch):
    win = MainWindow()
    tt = np.linspace(5.0, 60.0, 111)
    ii = np.linspace(1.0, 50.0, 111)
    win.set_pattern(Pattern(tt, ii))
    target = _save_dialog(tmp_path, monkeypatch, "pattern.xy")
    win._export_pattern_ascii("2col")
    back = read_ascii_profile_2col(target)
    np.testing.assert_allclose(back.two_theta, tt)
    np.testing.assert_allclose(back.intensity, ii)


def test_export_pattern_guard_no_pattern(qapp, monkeypatch):
    from PySide6 import QtWidgets

    win = MainWindow()
    shown: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "information",
        lambda *a, **k: shown.append(a[1]),
    )
    win._export_pattern_ascii("profile")
    assert shown, "无谱图时必须提示而不是崩 vocab 溃"


# ---------------------------------------------------------------------------
# 三张表 CSV
# ---------------------------------------------------------------------------
def test_export_peak_list_csv(qapp, tmp_path, monkeypatch):
    win = MainWindow()
    win.peak_table.set_peaks([
        Peak(two_theta=25.3, intensity=100.0, fwhm=0.12),
        Peak(two_theta=35.9, intensity=50.0),
    ])
    _save_dialog(tmp_path, monkeypatch, "peaks.csv")
    win._export_peak_list_csv()
    text = (tmp_path / "peaks.csv").read_text(encoding="utf-8-sig")
    lines = text.strip().splitlines()
    assert lines[0] == "2theta_deg,d_A,intensity,relative_pct,fwhm_deg,hkl"
    assert len(lines) == 3
    assert "100.0000" in lines[1] and "0.1200" in lines[1]


def test_export_peak_list_guard_empty(qapp, monkeypatch):
    from PySide6 import QtWidgets

    win = MainWindow()
    shown: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "information",
        lambda *a, **k: shown.append(a[1]),
    )
    win._export_peak_list_csv()
    assert shown


def test_export_candidates_csv(qapp, tmp_path, monkeypatch):
    win = MainWindow()
    win.set_candidates([
        _mk_candidate(0.9, "96-900-0001", formula="Al2 Be3 Si6 O18"),
        _mk_candidate(0.6, "96-900-0004", formula="C Ca O3"),
    ])
    _save_dialog(tmp_path, monkeypatch, "candidates.csv")
    win._export_candidates_csv()
    text = (tmp_path / "candidates.csv").read_text(encoding="utf-8-sig")
    lines = text.strip().splitlines()
    assert lines[0] == "entry_id,mineral_name,formula,space_group,fom"
    assert len(lines) == 3
    assert "96-900-0001" in lines[1]


def test_export_candidates_guard_empty(qapp, monkeypatch):
    from PySide6 import QtWidgets

    win = MainWindow()
    shown: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "information",
        lambda *a, **k: shown.append(a[1]),
    )
    win._export_candidates_csv()
    assert shown


def test_export_matches_csv(qapp, tmp_path, monkeypatch):
    win = MainWindow()
    phase = Phase(entry=_mk_entry("96-900-0001"), scale_factor=0.5,
                  weight_fraction=0.25)
    win.match_table.set_phases([phase])
    _save_dialog(tmp_path, monkeypatch, "matches.csv")
    win._export_matches_csv()
    text = (tmp_path / "matches.csv").read_text(encoding="utf-8-sig")
    lines = text.strip().splitlines()
    assert lines[0] == "entry_id,mineral_name,formula,scale_factor,weight_pct"
    assert "25.00" in lines[1]


def test_export_matches_guard_empty(qapp, monkeypatch):
    from PySide6 import QtWidgets

    win = MainWindow()
    shown: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "information",
        lambda *a, **k: shown.append(a[1]),
    )
    win._export_matches_csv()
    assert shown


# ---------------------------------------------------------------------------
# 右键「导出 (CSV)…」信号接线
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("table_attr,method_name", [
    ("peak_table", "_export_peak_list_csv"),
    ("candidate_table", "_export_candidates_csv"),
    ("match_table", "_export_matches_csv"),
])
def test_table_export_signals_wired(qapp, monkeypatch, table_attr, method_name):
    """右键菜单的「导出 (CSV)…」不再悬空：export_requested → 对应导出方法。"""
    win = MainWindow()
    calls: list[bool] = []
    monkeypatch.setattr(win, method_name, lambda: calls.append(True))
    getattr(win, table_attr).export_requested.emit()
    assert calls == [True]
