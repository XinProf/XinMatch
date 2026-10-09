"""T13.3 — tests for the three sortable list tables (offscreen)."""

from __future__ import annotations

import numpy as np
from PySide6 import QtCore, QtWidgets

from xinmatch.core.model.entry import Entry
from xinmatch.core.model.peak import Peak
from xinmatch.core.model.phase import Phase
from xinmatch.core.search.fom import CandidateResult
from xinmatch.ui.tables import (
    CandidateListTable,
    MatchListTable,
    PeakListTable,
)


def _make_entry(entry_id: str, formula: str = "Si O2", mineral: str | None = None) -> Entry:
    return Entry(
        entry_id=entry_id,
        formula=formula,
        d_spacings=np.array([3.3, 2.4, 1.8]),
        intensities=np.array([1000.0, 600.0, 300.0]),
        mineral_name=mineral,
        quality="*",
    )


def _candidate(fom: float, entry_id: str) -> CandidateResult:
    return CandidateResult(
        entry=_make_entry(entry_id),
        fom=fom,
        p_values={"peakpos": 0.9, "intensity": 0.8},
        i_scale=1.0,
    )


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
    results = [_candidate(0.5, "1"), _candidate(0.9, "2"), _candidate(0.7, "3")]
    table = CandidateListTable()
    table.set_candidates(results)
    table.resize(600, 200)
    table.show()
    assert table.model().rowCount() == 3
    # Default sort is FoM descending (column 9).
    foms = [float(table.model().index(r, 9).data(QtCore.Qt.ItemDataRole.DisplayRole))
            for r in range(table.model().rowCount())]
    assert foms == sorted(foms, reverse=True)


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
    assert any("选中" in t for t in texts)

    viewed: list[str] = []
    table.view_entry.connect(lambda e: viewed.append(e))
    next(a for a in menu.actions() if "查看条目" in a.text()).trigger()
    assert viewed == ["COD-100001"]


# ---------------------------------------------------------------------------
# Match list
# ---------------------------------------------------------------------------
def test_match_table_fills_rows(qapp):
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
