"""T13.3 — tests for the three sortable list tables (offscreen)."""

from __future__ import annotations

import numpy as np
from PySide6 import QtCore, QtWidgets

from xinmatch.core.model.entry import CellParams, Entry
from xinmatch.core.model.peak import Peak
from xinmatch.core.model.phase import Phase
from xinmatch.core.search.fom import CandidateResult
from xinmatch.ui.tables import (
    CandidateListTable,
    MatchListTable,
    PeakListTable,
)


def _make_entry(entry_id: str, formula: str = "Si O2", mineral: str | None = None,
                cell: CellParams | None = None, space_group: str | None = None) -> Entry:
    return Entry(
        entry_id=entry_id,
        formula=formula,
        d_spacings=np.array([3.3, 2.4, 1.8]),
        intensities=np.array([1000.0, 600.0, 300.0]),
        mineral_name=mineral,
        cell=cell,
        space_group=space_group,
        quality="*",
    )


def _candidate(fom: float, entry_id: str, *, formula: str = "Si O2",
               cell: CellParams | None = None) -> CandidateResult:
    return CandidateResult(
        entry=_make_entry(entry_id, formula=formula, cell=cell),
        fom=fom,
        p_values={"peakpos": 0.9, "intensity": 0.8},
        i_scale=1.0,
    )


#: 三张 beryl 型卡片 + 一张方解石——折叠口径的标准夹具（族内 3 条）。
_BERYL_CELL = CellParams(a=9.215, b=9.215, c=9.190)
_CALCITE_CELL = CellParams(a=4.990, b=4.990, c=17.061)


def _family_fixture() -> list[CandidateResult]:
    """Beryl family ×3 (descending FoM) followed by calcite."""
    return [
        _candidate(0.90, "96-900-0001", formula="Al2 Be3 Si6 O18", cell=_BERYL_CELL),
        _candidate(0.85, "96-900-0002", formula="Al1.5 Be3 Si6 O18", cell=_BERYL_CELL),
        _candidate(0.80, "96-900-0003", formula="Al2 Be3 Si6 O18", cell=_BERYL_CELL),
        _candidate(0.60, "96-900-0004", formula="C Ca O3", cell=_CALCITE_CELL),
    ]


def _center(view: QtWidgets.QTableView, row: int = 0) -> QtCore.QPoint:
    """Viewport-centre point of *row*, column 0 (for menu/double-click)."""
    idx = view.model().index(row, 0)
    return view.visualRect(idx).center()


# ---------------------------------------------------------------------------
# Peak list
# ---------------------------------------------------------------------------
def test_peak_table_fills_rows(qapp):
    peaks = [Peak(two_theta=25.0, intensity=100.0), Peak(two_theta=35.0, intensity=50.0)]
    table = PeakListTable()
    table.set_peaks(peaks)
    assert table.model().rowCount() == 2


def test_peak_table_sorts_by_two_theta(qapp):
    peaks = [
        Peak(two_theta=35.0, intensity=50.0),
        Peak(two_theta=15.0, intensity=90.0),
        Peak(two_theta=25.0, intensity=70.0),
    ]
    table = PeakListTable()
    table.set_peaks(peaks)
    table.resize(500, 200)
    table.show()
    # Sort column 0 (2θ) ascending.
    table.sortByColumn(0, QtCore.Qt.SortOrder.AscendingOrder)
    values = []
    for r in range(table.model().rowCount()):
        vals = table.model().index(r, 0).data(QtCore.Qt.ItemDataRole.DisplayRole)
        values.append(float(vals))
    assert values == sorted(values)


def test_peak_table_doubleclick_emits(qapp):
    peaks = [Peak(two_theta=25.0, intensity=100.0), Peak(two_theta=35.0, intensity=50.0)]
    table = PeakListTable()
    table.set_peaks(peaks)
    table.resize(500, 200)
    table.show()
    # Deterministic order: sort ascending so proxy row 0 == source row 0.
    table.sortByColumn(0, QtCore.Qt.SortOrder.AscendingOrder)
    caught = []
    table.peak_activated.connect(lambda i: caught.append(i))
    table.doubleClicked.emit(table.model().index(0, 0))
    assert caught == [0]


def test_peak_context_menu_actions_and_signals(qapp):
    peaks = [Peak(two_theta=25.0, intensity=100.0)]
    table = PeakListTable()
    table.set_peaks(peaks)
    table.resize(500, 200)
    table.show()
    menu = table._build_menu(_center(table))
    texts = [a.text() for a in menu.actions()]
    assert any("编辑峰" in t for t in texts)
    assert any("删除峰" in t for t in texts)
    assert any("导出" in t for t in texts)

    edit_caught: list[int] = []
    table.edit_peak.connect(lambda i: edit_caught.append(i))
    next(a for a in menu.actions() if "编辑峰" in a.text()).trigger()
    assert edit_caught == [0]

    export_caught: list[None] = []
    table.export_requested.connect(lambda: export_caught.append(None))
    next(a for a in menu.actions() if "导出" in a.text()).trigger()
    assert export_caught == [None]


# ---------------------------------------------------------------------------
# Candidate list
# ---------------------------------------------------------------------------
def test_candidate_table_fills_and_default_fom_sort(qapp):
    # Distinct compositions → three separate phase families → three rows even
    # though folding is on by default (v3.2.0).
    results = [
        _candidate(0.5, "1", formula="Si O2"),
        _candidate(0.9, "2", formula="Ti O2"),
        _candidate(0.7, "3", formula="Al2 O3"),
    ]
    table = CandidateListTable()
    table.set_candidates(results)
    table.resize(600, 200)
    table.show()
    assert table.model().rowCount() == 3
    # Default sort is FoM descending (column 9).
    foms = [float(table.model().index(r, 9).data(QtCore.Qt.ItemDataRole.DisplayRole))
            for r in range(table.model().rowCount())]
    assert foms == sorted(foms, reverse=True)


def test_candidate_table_folds_same_phase_variants(qapp):
    table = CandidateListTable()
    table.set_candidates(_family_fixture())
    table.resize(600, 300)
    table.show()
    # 3 beryl cards collapse into 1 row, calcite keeps its own.
    assert table.model().rowCount() == 2
    assert table.is_merging_families() is True
    assert table.family_size_at(0) == 3
    assert table.family_size_at(1) == 1
    # Unfolded ids never appear while folded.
    ids = [r.entry.entry_id for r in table.visible_results()]
    assert ids == ["96-900-0001", "96-900-0004"]
    # The "变体" column reports the family size on the representative row.
    variant = [table.model().index(r, 10).data(QtCore.Qt.ItemDataRole.DisplayRole)
               for r in range(2)]
    assert variant[0] == "3 条"
    assert variant[1] == ""
    # Its tooltip lists every card plus the unit cell.
    tip = table.model().index(0, 10).data(QtCore.Qt.ItemDataRole.ToolTipRole)
    assert "96-900-0001" in tip and "96-900-0003" in tip
    assert "a=9.2150" in tip


def test_candidate_table_expands_and_recollapses(qapp):
    table = CandidateListTable()
    table.set_candidates(_family_fixture())
    table.resize(600, 300)
    table.show()
    seen: list[bool] = []
    table.family_mode_changed.connect(lambda m: seen.append(m))

    table.set_merge_families(False)
    assert table.model().rowCount() == 4
    variant = [table.model().index(r, 10).data(QtCore.Qt.ItemDataRole.DisplayRole)
               for r in range(4)]
    assert variant == ["1/3", "2/3", "3/3", ""]

    table.set_merge_families(True)
    assert table.model().rowCount() == 2
    assert seen == [False, True]


def test_candidate_selection_maps_through_fold_table(qapp):
    """Folded rows are not candidate indices: selection must still resolve."""
    table = CandidateListTable()
    table.set_candidates(_family_fixture())
    table.resize(600, 300)
    table.show()
    # Proxy row 1 is calcite (source index 3), not beryl card #2.
    table.selectRow(1)
    assert table.current_entry_id() == "96-900-0004"
    assert [r.entry.entry_id for r in table.selected_results()] == ["96-900-0004"]
    # Folded mode still exposes the whole family for the representative row.
    assert [r.entry.entry_id for r in table.family_results_at(0)] == [
        "96-900-0001", "96-900-0002", "96-900-0003",
    ]


def test_candidate_context_menu_toggles_families(qapp):
    table = CandidateListTable()
    table.set_candidates(_family_fixture())
    table.resize(600, 300)
    table.show()
    menu = table._build_menu(_center(table))
    texts = [a.text() for a in menu.actions()]
    assert any("展开同相变体" in t for t in texts)
    next(a for a in menu.actions() if "展开同相变体" in a.text()).trigger()
    assert table.model().rowCount() == 4
    # Menu now offers the inverse action.
    texts2 = [a.text() for a in table._build_menu(_center(table)).actions()]
    assert any("合并同相变体" in t for t in texts2)


def test_candidate_context_menu_without_families(qapp):
    table = CandidateListTable()
    table.set_candidates([_candidate(0.9, "COD-100001", formula="Ti O2")])
    table.resize(600, 200)
    table.show()
    action = next(a for a in table._build_menu(_center(table)).actions()
                  if "变体" in a.text())
    assert action.text() == "无同相变体"
    assert action.isEnabled() is False


def test_candidate_table_doubleclick_emits_entry_id(qapp):
    results = [_candidate(0.9, "COD-100001")]
    table = CandidateListTable()
    table.set_candidates(results)
    table.resize(600, 200)
    table.show()
    caught: list[str] = []
    table.candidate_activated.connect(lambda e: caught.append(e))
    table.doubleClicked.emit(table.model().index(0, 0))
    assert caught == ["COD-100001"]


def test_candidate_context_menu(qapp):
    results = [_candidate(0.9, "COD-100001")]
    table = CandidateListTable()
    table.set_candidates(results)
    table.resize(600, 200)
    table.show()
    menu = table._build_menu(_center(table))
    texts = [a.text() for a in menu.actions()]
    assert any("查看条目" in t for t in texts)
    # v3.1.0: the old "选中/取消选中" item became the confirm action that
    # feeds the sequential phase-identification loop.
    assert any("确认" in t for t in texts)

    viewed: list[str] = []
    table.view_entry.connect(lambda e: viewed.append(e))
    next(a for a in menu.actions() if "查看条目" in a.text()).trigger()
    assert viewed == ["COD-100001"]


def test_candidate_table_marks_anchored_rows(qapp):
    """v3.3.0: strong-line anchored rows get a ★ in the colour band.

    The mark is informational only — no column is added and the FoM order is
    untouched, so a sparse phase the peak-count criterion buried becomes
    *visible* without the engine deciding for the user.
    """
    results = [
        _candidate(0.90, "96-900-0001", formula="Si O2"),
        _candidate(0.60, "96-900-0004", formula="Cl Na"),
    ]
    table = CandidateListTable()
    table.set_candidates(results, anchored_ids=["96-900-0004"])
    table.resize(600, 200)
    table.show()

    marks = [table.model().index(r, 0).data(QtCore.Qt.ItemDataRole.DisplayRole)
             for r in range(table.model().rowCount())]
    assert marks == ["", "★"]
    assert table.is_anchored(0) is False
    assert table.is_anchored(1) is True
    tip = table.model().index(1, 0).data(QtCore.Qt.ItemDataRole.ToolTipRole)
    assert tip and "少线相" in tip
    assert table.model().index(0, 0).data(QtCore.Qt.ItemDataRole.ToolTipRole) is None
    # Ranking is unchanged: the marked row is still the lower-FoM row.
    assert [r.entry.entry_id for r in table.visible_results()] == [
        "96-900-0001", "96-900-0004",
    ]


def test_candidate_table_anchor_mark_survives_family_fold(qapp):
    """A marked member keeps its mark when its family folds into one row."""
    results = [
        _candidate(0.90, "96-900-0001", formula="Al2 Be3 Si6 O18", cell=_BERYL_CELL),
        _candidate(0.85, "96-900-0002", formula="Al1.5 Be3 Si6 O18", cell=_BERYL_CELL),
        _candidate(0.60, "96-900-0004", formula="C Ca O3", cell=_CALCITE_CELL),
    ]
    table = CandidateListTable()
    table.set_candidates(results, anchored_ids=["96-900-0002"])
    table.resize(600, 200)
    table.show()
    assert table.model().rowCount() == 2
    # The folded family is represented by its best card (0001), which is not
    # the marked one — so the representative row carries no mark, and the mark
    # comes back when the variants are unfolded.
    assert table.is_anchored(0) is False
    table.set_merge_families(False)
    ids = [r.entry.entry_id for r in table.visible_results()]
    assert ids[1] == "96-900-0002"
    assert table.is_anchored(1) is True


# ---------------------------------------------------------------------------
# Match list
# ---------------------------------------------------------------------------def test_match_table_fills_rows(qapp):
    phases = [Phase(entry=_make_entry("P-1", "Si O2", "Quartz"), weight_fraction=0.5)]
    table = MatchListTable()
    table.set_phases(phases)
    table.resize(500, 200)
    table.show()
    assert table.model().rowCount() == 1
    # Amount column shows 50.0%.
    amount = table.model().index(0, 5).data(QtCore.Qt.ItemDataRole.DisplayRole)
    assert amount.startswith("50.0")


def test_match_table_doubleclick_emits_entry_id(qapp):
    phases = [Phase(entry=_make_entry("P-2"))]
    table = MatchListTable()
    table.set_phases(phases)
    table.resize(500, 200)
    table.show()
    caught: list[str] = []
    table.phase_activated.connect(lambda e: caught.append(e))
    table.doubleClicked.emit(table.model().index(0, 0))
    assert caught == ["P-2"]


def test_match_context_menu_remove(qapp):
    phases = [Phase(entry=_make_entry("P-3"))]
    table = MatchListTable()
    table.set_phases(phases)
    table.resize(500, 200)
    table.show()
    menu = table._build_menu(_center(table))
    removed: list[str] = []
    table.remove_phase.connect(lambda e: removed.append(e))
    next(a for a in menu.actions() if "移除" in a.text()).trigger()
    assert removed == ["P-3"]
