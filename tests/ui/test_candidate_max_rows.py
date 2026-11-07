"""§35 方案 B — 候选列表行数上限（``candidate_list.max_display_rows``）单测。

覆盖：

* :func:`xinmatch.ui.main_window._candidate_row_budget` 的换算口径——
  默认值、下限钳位、上限钳位（``candidate_limit`` 的 1000）、脏值回退；
* 候选表模型截断——折叠时前 N 行 = 前 N 个族、展开时前 N 张卡、
  ``None`` 兼容（不截断）、``0`` / 负数归一、跨 ``set_candidates`` 保持、
  ``visible_results()`` 与显示行一致；
* OptionsDialog 候选列表页新键 round-trip；
* ``MainWindow.set_candidates`` 按持久化配置把上限应用到表格（集成），
  且 ``win._candidates`` 仍持全量（项目存档 .xinm 口径不变）。

非 heavy 用例不触碰参考数据库（offscreen 安全）。
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


import numpy as np  # noqa: E402
import pytest  # noqa: E402

from xinmatch.core.model.entry import CellParams, Entry  # noqa: E402
from xinmatch.core.search.fom import CandidateResult  # noqa: E402
from xinmatch.ui.dialogs.config import DEFAULTS, default_config  # noqa: E402
from xinmatch.ui.dialogs.options_dialog import OptionsDialog  # noqa: E402
from xinmatch.ui.main_window import (  # noqa: E402
    _ROW_BUDGET_FETCH_CEILING,
    _candidate_row_budget,
)
from xinmatch.ui.tables import CandidateListTable  # noqa: E402

# ---------------------------------------------------------------------------
# 夹具（与 tests/ui/test_tables.py 同口径）
# ---------------------------------------------------------------------------
_BERYL_CELL = CellParams(a=9.215, b=9.215, c=9.190)
_CALCITE_CELL = CellParams(a=4.990, b=4.990, c=17.061)


def _candidate(fom: float, entry_id: str, *, formula: str = "Si O2",
               cell: CellParams | None = None) -> CandidateResult:
    return CandidateResult(
        entry=Entry(
            entry_id=entry_id,
            formula=formula,
            d_spacings=np.array([3.3, 2.4, 1.8]),
            intensities=np.array([1000.0, 600.0, 300.0]),
            cell=cell,
            quality="*",
        ),
        fom=fom,
        p_values={"peakpos": 0.9, "intensity": 0.8},
        i_scale=1.0,
    )


def _family_fixture() -> list[CandidateResult]:
    """Beryl family ×3 (descending FoM) followed by calcite."""
    return [
        _candidate(0.90, "96-900-0001", formula="Al2 Be3 Si6 O18", cell=_BERYL_CELL),
        _candidate(0.85, "96-900-0002", formula="Al1.5 Be3 Si6 O18", cell=_BERYL_CELL),
        _candidate(0.80, "96-900-0003", formula="Al2 Be3 Si6 O18", cell=_BERYL_CELL),
        _candidate(0.60, "96-900-0004", formula="C Ca O3", cell=_CALCITE_CELL),
    ]


# ---------------------------------------------------------------------------
# 1. _candidate_row_budget 换算
# ---------------------------------------------------------------------------
def test_defaults_declare_max_display_rows():
    """DEFAULTS 的候选列表节必须声明该键，默认 50（§35.3 裁定）。"""
    assert DEFAULTS["candidate_list"]["max_display_rows"] == 50


def test_budget_missing_section_falls_back_to_default():
    """配置缺节/缺键 → 按默认 50 行换算，fetch 钳到下限 200。"""
    assert _candidate_row_budget({}) == (200, 50)
    assert _candidate_row_budget({"candidate_list": {}}) == (200, 50)


def test_budget_small_rows_fetch_floors_at_200():
    """行数很小（20）时 fetch 取下限 200，保证折叠仍有足量候选。"""
    assert _candidate_row_budget(
        {"candidate_list": {"max_display_rows": 20}}
    ) == (200, 20)


def test_budget_scales_with_4x_margin():
    """fetch = 4 × 行数（族合并只减行数，显示 N 行需返回多于 N 卡）。"""
    assert _candidate_row_budget(
        {"candidate_list": {"max_display_rows": 150}}
    ) == (600, 150)


def test_budget_fetch_caps_at_ceiling():
    """fetch 钳到 _ROW_BUDGET_FETCH_CEILING；max_rows 本身不钳（引擎侧
    候选池受 candidate_limit 约束，截断语义仍成立）。"""
    assert _ROW_BUDGET_FETCH_CEILING == 1000
    assert _candidate_row_budget(
        {"candidate_list": {"max_display_rows": 500}}
    ) == (1000, 500)
    assert _candidate_row_budget(
        {"candidate_list": {"max_display_rows": 5000}}
    ) == (1000, 5000)


@pytest.mark.parametrize("raw", [0, -5, "abc", None])
def test_budget_dirty_values_fall_back_to_default(raw):
    """脏值（非正数 / 非整数字符串 / None）回退默认 50。"""
    assert _candidate_row_budget(
        {"candidate_list": {"max_display_rows": raw}}
    ) == (200, 50)


# ---------------------------------------------------------------------------
# 2. 表格模型截断
# ---------------------------------------------------------------------------
def test_cap_merged_counts_families(qapp):
    """折叠模式：上限 1 → 只显示第一个族的代表（行 = 族）。"""
    table = CandidateListTable()
    table.set_candidates(_family_fixture())
    assert table.model().rowCount() == 2  # 先证夹具基线：2 个族
    table.set_max_rows(1)
    assert table.model().rowCount() == 1
    assert table.family_size_at(0) == 3  # beryl 族整体保留
    ids = [c.entry.entry_id for c in table.visible_results()]
    assert ids == ["96-900-0001"]  # 族代表 = 排名最高者


def test_cap_expanded_counts_cards(qapp):
    """展开模式：上限 2 → 前 2 张卡（beryl 代表 + 变体 2）。"""
    table = CandidateListTable()
    table.set_candidates(_family_fixture())
    table.set_merge_families(False)
    assert table.model().rowCount() == 4
    table.set_max_rows(2)
    assert table.model().rowCount() == 2
    ids = [c.entry.entry_id for c in table.visible_results()]
    assert ids == ["96-900-0001", "96-900-0002"]


def test_cap_none_and_nonpositive_mean_unlimited(qapp):
    """``None`` / 0 / 负数都不截断（兼容既有调用方与脏配置）。"""
    table = CandidateListTable()
    table.set_candidates(_family_fixture())
    table.set_merge_families(False)
    for value in (None, 0, -3):
        table.set_max_rows(value)
        assert table.model().rowCount() == 4
        assert table.max_rows() is None  # widget 层是转发方法


def test_cap_keeps_top_ranked_prefix(qapp):
    """截断保留的是排名前缀（第 9 列 FoM 降序不变）。"""
    table = CandidateListTable()
    table.set_candidates(_family_fixture())
    table.set_max_rows(2)
    foms = [table.model().index(r, 9).data() for r in range(table.model().rowCount())]
    assert foms == sorted(foms, reverse=True)


def test_cap_persists_across_set_candidates(qapp):
    """上限跨 ``set_candidates`` 保持（main_window 只在回填时设一次）。"""
    table = CandidateListTable()
    table.set_candidates(_family_fixture())
    table.set_max_rows(1)
    table.set_candidates(_family_fixture())
    assert table.model().rowCount() == 1


def test_cap_larger_than_rows_is_noop(qapp):
    table = CandidateListTable()
    table.set_candidates(_family_fixture())
    table.set_max_rows(100)
    assert table.model().rowCount() == 2


# ---------------------------------------------------------------------------
# 3. OptionsDialog round-trip
# ---------------------------------------------------------------------------
def test_options_dialog_roundtrips_max_display_rows(qapp):
    """候选列表页的「行数上限」spin 能被写入并原样回收。"""
    cfg = default_config()
    cfg["candidate_list"]["max_display_rows"] = 120
    dialog = OptionsDialog(cfg)
    got = dialog.values()["candidate_list"]
    assert got["max_display_rows"] == 120


def test_options_dialog_default_shows_50(qapp):
    dialog = OptionsDialog(default_config())
    assert dialog.values()["candidate_list"]["max_display_rows"] == 50


# ---------------------------------------------------------------------------
# 4. MainWindow 集成（set_candidates 应用上限）
# ---------------------------------------------------------------------------
def test_main_window_set_candidates_applies_cap(qapp, monkeypatch):
    """回填时把持久化配置的行数上限应用到表格；全量仍存 win._candidates。"""
    from xinmatch.ui import main_window as mw

    win = mw.MainWindow()
    monkeypatch.setattr(
        mw, "load_config",
        lambda: {"candidate_list": {"max_display_rows": 1}},
    )
    win.set_candidates(_family_fixture())
    assert win.candidate_table.model().rowCount() == 1
    assert len(win._candidates) == 4  # 项目存档（.xinm）口径：全量
    # 报告同源：visible_results 与显示行一致
    assert len(win.candidate_table.visible_results()) == 1


def test_main_window_default_cap_50(qapp, monkeypatch):
    """默认配置（无 YAML 覆盖）下上限=50，截断对小额候选是 no-op。"""
    from xinmatch.ui import main_window as mw

    win = mw.MainWindow()
    monkeypatch.setattr(mw, "load_config", default_config)
    win.set_candidates(_family_fixture())
    assert win.candidate_table.max_rows() == 50
    assert win.candidate_table.model().rowCount() == 2
