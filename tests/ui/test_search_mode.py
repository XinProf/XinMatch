"""统一检索入口（Search-Match 模式切换）测试：峰列表 FoM / SMPF 全谱拟合。

覆盖：
- 工具栏下拉框 ``self._search_mode_combo`` 存在、默认 ``peaks_fom``、
  切换只更新 ``self._search_mode`` 而不自动触发检索；
- 模块级转换函数 ``smpf_results_to_candidates``（SMPF ``(Entry, score)``
  → GUI :class:`~xinmatch.core.search.fom.CandidateResult`）单测；
- offscreen 冒烟：真实默认库 ``data/cod_inorganics.db`` + 合成谱，两种
  模式经统一入口 ``_run_search_match`` 均可填充候选列表，且 SMPF 模式
  不覆盖峰列表；
- SMPF 命中不劣化（UI 级）：synth_06 / synth_09 经统一入口 SMPF 检索后
  Top-1 与真相一致——判定口径复用
  :mod:`tests.search.test_synthetic_acceptance` 的 ``is_truth``（元素集 +
  归一化化学计量比例，兼容库内公式写法变体）；
- 回归锚点：两模式下 ``_selected_candidate_results()`` 非空且元素均为
  CandidateResult（精修向导 / 3D 视图 / CIF 导出链路不破）。

性能：SMPF 精排默认全库 prescreen=150 耗时较大，测试内统一用
``prescreen_top_n=60 / top_n=10`` 的包装限制（与
``tests/search/test_smpf.py::test_deterministic_single_pattern`` 同参数，
真相相仍在精排集合内）。
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sqlite3
from pathlib import Path

import numpy as np
import pytest
from PySide6 import QtWidgets

from tests.search.test_synthetic_acceptance import TRUTH, is_truth
from xinmatch.core.io import load_pattern
from xinmatch.core.model import Entry
from xinmatch.core.search.fom import CandidateResult
from xinmatch.core.search.smpf import search_match_smpf
from xinmatch.ui.main_window import (
    SEARCH_MODE_PEAKS_FOM,
    SEARCH_MODE_SMPF_FULL,
    MainWindow,
    smpf_results_to_candidates,
)

DB = Path(r"D:\Project\XRD\XinMatch\data\cod_inorganics.db")
SYNTH_DIR = Path(r"D:\Project\XRD\test_xrd\synthetic")

_HEAVY = pytest.mark.skipif(
    not SYNTH_DIR.exists() or not DB.exists(),
    reason="合成谱目录或默认库不存在（仓库外）",
)


def _patch_fast_smpf(monkeypatch) -> None:
    """把 GUI 调用的 search_match_smpf 限制到 prescreen=60 / top_n=10。"""
    real = search_match_smpf

    def _fast(pattern, conn, **kwargs):
        kwargs.setdefault("prescreen_top_n", 60)
        kwargs.setdefault("top_n", 10)
        return real(pattern, conn, **kwargs)

    monkeypatch.setattr("xinmatch.ui.main_window.search_match_smpf", _fast)


def _connect(monkeypatch, win) -> sqlite3.Connection:
    """开真实默认库连接并把窗口的库打开动作指向它（替代配置/多库挂载）。"""
    conn = sqlite3.connect(DB)
    monkeypatch.setattr(win, "open_search_library", lambda: conn)
    return conn


# ---------------------------------------------------------------------------
# 1. 模式控件存在性 / 默认值 / 切换行为（offscreen，不碰数据库）
# ---------------------------------------------------------------------------
def test_search_mode_combo_present_and_default(qapp):
    win = MainWindow()
    combo = win._search_mode_combo
    assert isinstance(combo, QtWidgets.QComboBox)
    assert combo.count() == 2
    assert combo.itemData(0) == SEARCH_MODE_PEAKS_FOM
    assert combo.itemData(1) == SEARCH_MODE_SMPF_FULL
    assert "峰列表" in combo.itemText(0)
    assert "SMPF" in combo.itemText(1)
    # 默认峰列表 FoM；tooltip 说明当前模式。
    assert win._search_mode == SEARCH_MODE_PEAKS_FOM
    assert combo.toolTip()


def test_combo_switch_updates_state_without_search(qapp):
    """切换模式只改内部状态，不自动触发检索（候选列表保持空）。"""
    win = MainWindow()
    win._search_mode_combo.setCurrentIndex(1)
    assert win._search_mode == SEARCH_MODE_SMPF_FULL
    assert win._candidates == []
    win._search_mode_combo.setCurrentIndex(0)
    assert win._search_mode == SEARCH_MODE_PEAKS_FOM


def test_no_pattern_still_informs_in_each_mode(qapp, monkeypatch):
    """无谱时两模式都走同一友好提示，不崩溃。"""
    from unittest.mock import patch

    win = MainWindow()
    for idx, mode in ((0, SEARCH_MODE_PEAKS_FOM), (1, SEARCH_MODE_SMPF_FULL)):
        win._search_mode_combo.setCurrentIndex(idx)
        assert win._search_mode == mode
        with patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
            win._run_search_match()
        mock_info.assert_called()
        assert win._candidates == []


# ---------------------------------------------------------------------------
# 2. SMPF 结果 → CandidateResult 转换（纯函数单测）
# ---------------------------------------------------------------------------
def test_smpf_results_to_candidates_conversion():
    entry = Entry(
        entry_id="96-210-0858",
        formula="Ba O3 Ti",
        d_spacings=np.array([2.0, 1.5]),
        intensities=np.array([100.0, 50.0]),
    )
    score = {
        "entry_id": "96-210-0858",
        "formula": "Ba O3 Ti",
        "scale": 123.4,
        "shift_deg": 0.0,
        "fwhm": 0.15,
        "eta": 0.5,
        "bg0": 10.0,
        "bg1": 0.0,
        "bg2": 0.0,
        "rwp": 0.089,
        "rexp": 0.071,
        "gof": 1.58,
        "fom": 0.701,
    }
    out = smpf_results_to_candidates([(entry, score), (entry, score)])
    assert len(out) == 2
    for c in out:
        assert isinstance(c, CandidateResult)
        assert c.entry is entry
        assert c.fom == pytest.approx(0.701)
        assert c.p_values == {
            "rwp": pytest.approx(0.089),
            "rexp": pytest.approx(0.071),
            "gof": pytest.approx(1.58),
        }
        # SMPF 无峰相关量：pairs 留空、i_scale 默认。
        assert c.pairs == []
        assert c.i_scale == 1.0


# ---------------------------------------------------------------------------
# 3. offscreen 冒烟：真实默认库 + 合成谱，两模式统一入口均可跑通
# ---------------------------------------------------------------------------
@_HEAVY
def test_unified_entry_runs_both_modes(qapp, monkeypatch):
    _patch_fast_smpf(monkeypatch)
    win = MainWindow()
    win.set_pattern(load_pattern(SYNTH_DIR / "synth_06.txt"))
    conn = _connect(monkeypatch, win)
    try:
        # --- 模式 1：峰列表 FoM（默认） ---
        win._run_search_match()
        n_fom = len(win._candidates)
        assert n_fom > 0, "FoM 模式候选列表为空"
        assert win.candidate_table.model().rowCount() == n_fom
        assert all(isinstance(c, CandidateResult) for c in win._candidates)
        peak_rows_fom = win.peak_table.model().rowCount()
        assert peak_rows_fom > 0  # FoM 模式覆盖峰列表
        assert "峰列表 FoM" in win.statusBar().currentMessage()
        sel_fom = win._selected_candidate_results()
        assert sel_fom and all(
            isinstance(c, CandidateResult) for c in sel_fom
        )

        # --- 模式 2：SMPF 全谱拟合 ---
        win._search_mode_combo.setCurrentIndex(1)
        assert win._search_mode == SEARCH_MODE_SMPF_FULL
        win._run_search_match()
        n_smpf = len(win._candidates)
        assert n_smpf > 0, "SMPF 模式候选列表为空"
        assert win.candidate_table.model().rowCount() == n_smpf
        assert all(isinstance(c, CandidateResult) for c in win._candidates)
        # SMPF 不寻峰：峰列表保持 FoM 模式的结果，不被覆盖。
        assert win.peak_table.model().rowCount() == peak_rows_fom
        assert "SMPF 全谱拟合" in win.statusBar().currentMessage()
        sel_smpf = win._selected_candidate_results()
        assert sel_smpf and all(
            isinstance(c, CandidateResult) for c in sel_smpf
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 4. SMPF 命中不劣化（UI 级）：synth_06 / synth_09 Top-1 = 真相
# ---------------------------------------------------------------------------
@_HEAVY
@pytest.mark.parametrize(
    "name",
    ["synth_06", "synth_09"],
)
def test_smpf_top1_hit_via_unified_entry(qapp, monkeypatch, name):
    """经统一入口 SMPF 检索后，Top-1 候选化学式与真相一致。

    判定口径与 tests/search/test_synthetic_acceptance.py 相同（is_truth：
    元素集 + 归一化比例），库内公式写法变体（如 "C 1 2 1" 对应真相
    "C"）可正确判定。参数同 test_unified_entry_runs_both_modes（prescreen=60）。
    """
    _patch_fast_smpf(monkeypatch)
    win = MainWindow()
    win.set_pattern(load_pattern(SYNTH_DIR / f"{name}.txt"))
    conn = _connect(monkeypatch, win)
    try:
        win._search_mode_combo.setCurrentIndex(1)
        assert win._search_mode == SEARCH_MODE_SMPF_FULL
        win._run_search_match()
        assert len(win._candidates) > 0
        top1 = win._candidates[0]
        truths = TRUTH[name]
        assert any(is_truth(top1.entry.formula, tf) for tf in truths), (
            f"{name} SMPF Top-1 = {top1.entry.formula!r}，真相 = {truths}；"
            f"前 5：{[c.entry.formula for c in win._candidates[:5]]}"
        )
    finally:
        conn.close()
