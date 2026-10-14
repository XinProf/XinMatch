"""Sortable table views for the three main list panels (T13.3).

Implements the three table widgets that back the reference software "working area"
panels (see ``docs/working_area.md``):

* :class:`PeakListTable`     — the *peak list*  (``docs/peaklist_basics.md``,
  ``docs/peaklist_peak-editing.md``).  Columns: 2θ / d / I / I/I₀ / FWHM /
  hkl and the correlation / mark / exclude flags.
* :class:`CandidateListTable` — the *candidate list*
  (``docs/candidate_list_basics.md``, ``docs/candidate_list_entry-selection.md``).
  Columns mirror the reference software layout: colour swatch, quality mark, entry id,
  formula, crystal system, phase name, P(2θ), P(I/I₀), I scale factor, FoM.
* :class:`MatchListTable`     — the *match list* (``docs/match_list_basics.md``).
  One row per selected :class:`~xinmatch.core.model.phase.Phase`.

All three views use a :class:`~PySide6.QtWidgets.QTableView` fed by a
:class:`~PySide6.QtCore.QAbstractTableModel` plus a
:class:`~PySide6.QtWidgets.QSortFilterProxyModel`, so column-header clicks
sort numerically (via the ``Qt.UserRole`` sort key) while the displayed
text stays nicely formatted.  Row colours are painted through a QBrush in
``Qt.BackgroundRole`` rather than hard-coded stylesheet strings, so the
theme QSS can override them.

The views only *display* data and *announce* user intents through Qt
signals; all mutations (edit / delete / export) are handled by the
controller that owns them — this keeps the widgets pure-UI and testable in
offscreen mode.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from xinmatch.core.model.entry import CellParams, Entry
from xinmatch.core.model.peak import Peak
from xinmatch.core.model.phase import Phase
from xinmatch.core.search.fom import CandidateResult

__all__ = [
    "PeakListTable",
    "CandidateListTable",
    "MatchListTable",
]

# Role under which the raw (sortable) value is exposed to the proxy model.
_SORT_ROLE = QtCore.Qt.ItemDataRole.UserRole


def _crystal_system_letter(cell: CellParams | None) -> str:
    """Return the single-letter crystal system code for *cell* (GUI-side).

    The reference software uses one-letter codes in the "Cryst." column (see
    ``docs/candidate_list_basics.md``).  We derive it from the unit-cell
    parameters here so the GUI layer does not depend on the indexed SQL
    query helpers in :mod:`xinmatch.core.db`.  Returns ``"X"`` when the cell
    is unknown / partial.
    """
    if cell is None:
        return "X"
    a, b, c = cell.a, cell.b, cell.c
    alpha, beta, gamma = cell.alpha, cell.beta, cell.gamma
    ortho = abs(alpha - 90) < 1e-3 and abs(beta - 90) < 1e-3 and abs(gamma - 90) < 1e-3
    if not ortho:
        # Monoclinic has one non-90 angle (usually beta); triclinic otherwise.
        n_non90 = sum(abs(ang - 90) > 1e-3 for ang in (alpha, beta, gamma))
        return "M" if n_non90 == 1 else "A"
    if abs(a - b) < 1e-3 and abs(b - c) < 1e-3:
        return "C"
    if abs(a - b) < 1e-3:
        return "T"
    return "O"


def _fmt(value: Any, digits: int = 3) -> str:
    """Format a float for display, returning ``"—"`` for ``None``."""
    if value is None:
        return "—"
    if isinstance(value, (int, float, np.floating)):
        return f"{float(value):.{digits}f}"
    return str(value)


# ---------------------------------------------------------------------------
# Peak list
# ---------------------------------------------------------------------------
class _PeakListModel(QtCore.QAbstractTableModel):
    """Table model wrapping ``list[Peak]``."""

    HEADERS = ("2θ (°)", "d (Å)", "I", "I/I₀", "FWHM (°)", "hkl", "关联", "标记", "排除")

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._peaks: list[Peak] = []
        self._imax: float = 0.0

    # -- data population -------------------------------------------------
    def set_peaks(self, peaks: list[Peak]) -> None:
        """Replace the displayed rows with *peaks* (sorted by 2θ by caller)."""
        self.beginResetModel()
        self._peaks = list(peaks)
        self._imax = max((p.intensity for p in self._peaks), default=0.0)
        self.endResetModel()

    def peak_at(self, row: int) -> Peak | None:
        if 0 <= row < len(self._peaks):
            return self._peaks[row]
        return None

    # -- model API -------------------------------------------------------
    def rowCount(self, parent: QtCore.QModelIndex | QtCore.QPersistentModelIndex = QtCore.QModelIndex()) -> int:  # noqa: N802, B008
        return 0 if parent.isValid() else len(self._peaks)

    def columnCount(self, parent: QtCore.QModelIndex | QtCore.QPersistentModelIndex = QtCore.QModelIndex()) -> int:  # noqa: N802, B008
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation,  # noqa: N802
                   role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> Any:
        if role == QtCore.Qt.ItemDataRole.DisplayRole and orientation == QtCore.Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    def data(self, index: QtCore.QModelIndex | QtCore.QPersistentModelIndex,
             role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        peak = self._peaks[index.row()]
        col = index.column()
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            values = (
                _fmt(peak.two_theta),
                _fmt(peak.d),
                _fmt(peak.intensity, 1),
                _fmt((peak.intensity / self._imax * 100.0) if self._imax else 0.0, 1),
                _fmt(peak.fwhm),
                " ".join(str(x) for x in peak.hkl) if peak.hkl else "—",
                "✓" if peak.correlated else "",
                "✓" if peak.marked else "",
                "✓" if peak.excluded else "",
            )
            return values[col]
        if role == _SORT_ROLE:
            keys = (
                peak.two_theta,
                peak.d if peak.d is not None else float("inf"),
                peak.intensity,
                (peak.intensity / self._imax) if self._imax else 0.0,
                peak.fwhm if peak.fwhm is not None else float("inf"),
                peak.hkl if peak.hkl else (),
                peak.correlated,
                peak.marked,
                peak.excluded,
            )
            return keys[col]
        return None


class PeakListTable(QtWidgets.QTableView):
    """Sortable peak-list table with context menu and double-click signal.

    Signals
    -------
    peak_activated(int):
        Emitted with the peak index (in the underlying ``list[Peak]``
        order) when a row is double-clicked.
    edit_peak(int):
        Context-menu "编辑峰" triggered.
    remove_peaks(list):
        Context-menu "删除峰" triggered; carries the selected indices.
    export_requested():
        Context-menu "导出峰列表" triggered.
    """

    peak_activated = QtCore.Signal(int)
    edit_peak = QtCore.Signal(int)
    remove_peaks = QtCore.Signal(list)
    export_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = _PeakListModel(self)
        self._proxy = QtCore.QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(_SORT_ROLE)
        self.setModel(self._proxy)
        self.setSortingEnabled(True)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.doubleClicked.connect(self._on_double_clicked)
        self.horizontalHeader().setStretchLastSection(True)

    # -- public API ------------------------------------------------------
    def set_peaks(self, peaks: list[Peak]) -> None:
        """Fill the table from *peaks* (see :meth:`_PeakListModel.set_peaks`)."""
        self._model.set_peaks(peaks)
        self.resizeColumnsToContents()

    def _source_row(self, proxy_index: QtCore.QModelIndex) -> int:
        return self._proxy.mapToSource(proxy_index).row()  # type: ignore[no-any-return]

    # -- signals / menu --------------------------------------------------
    def _on_double_clicked(self, proxy_index: QtCore.QModelIndex) -> None:
        self.peak_activated.emit(self._source_row(proxy_index))

    def _build_menu(self, pos: QtCore.QPoint) -> QtWidgets.QMenu:
        """Build the peak-list context menu (exposed for inspection/tests)."""
        index = self.indexAt(pos)
        menu = QtWidgets.QMenu(self)
        row = self._source_row(index) if index.isValid() else -1
        act_edit = menu.addAction("编辑峰...")
        act_edit.setEnabled(row >= 0)
        act_edit.triggered.connect(lambda _c=False, r=row: self.edit_peak.emit(r))
        act_remove = menu.addAction("删除峰")
        act_remove.setEnabled(row >= 0)

        def _do_remove() -> None:
            rows = sorted({self._source_row(i) for i in self.selectedIndexes()
                           if i.column() == 0}) or ([row] if row >= 0 else [])
            self.remove_peaks.emit(rows)

        act_remove.triggered.connect(_do_remove)
        menu.addSeparator()
        act_export = menu.addAction("导出峰列表 (CSV)...")
        act_export.triggered.connect(self.export_requested.emit)
        return menu

    def _context_menu(self, pos: QtCore.QPoint) -> None:
        self._build_menu(pos).exec(self.viewport().mapToGlobal(pos))


# ---------------------------------------------------------------------------
# Candidate list
# ---------------------------------------------------------------------------
class _CandidateListModel(QtCore.QAbstractTableModel):
    """Table model wrapping ``list[CandidateResult]``."""

    HEADERS = ("", "质量", "条目", "化学式", "晶系", "物相",
               "P(2θ)", "P(I/I₀)", "I缩放", "FoM")

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._results: list[CandidateResult] = []
        self._colors: list[QtGui.QColor | None] = []

    def set_candidates(self, results: list[CandidateResult],
                       colors: list[QtGui.QColor | None] | None = None) -> None:
        """Replace rows with *results*; optional per-row pattern *colors*."""
        self.beginResetModel()
        self._results = list(results)
        self._colors = list(colors) if colors is not None else [None] * len(self._results)
        self.endResetModel()

    def entry_id_at(self, row: int) -> str | None:
        if 0 <= row < len(self._results):
            return self._results[row].entry.entry_id
        return None

    def rowCount(self, parent: QtCore.QModelIndex | QtCore.QPersistentModelIndex = QtCore.QModelIndex()) -> int:  # noqa: N802, B008
        return 0 if parent.isValid() else len(self._results)

    def columnCount(self, parent: QtCore.QModelIndex | QtCore.QPersistentModelIndex = QtCore.QModelIndex()) -> int:  # noqa: N802, B008
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation,  # noqa: N802
                   role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> Any:
        if role == QtCore.Qt.ItemDataRole.DisplayRole and orientation == QtCore.Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    def data(self, index: QtCore.QModelIndex | QtCore.QPersistentModelIndex,
             role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        result = self._results[index.row()]
        entry: Entry = result.entry
        col = index.column()
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            phase = entry.mineral_name or entry.formula
            if entry.mineral_name and entry.formula:
                phase = f"{entry.formula} ({entry.mineral_name})"
            values = (
                "",
                entry.quality or "—",
                entry.entry_id,
                entry.formula,
                _crystal_system_letter(entry.cell),
                phase,
                _fmt(result.p_values.get("peakpos")),
                _fmt(result.p_values.get("intensity")),
                _fmt(result.i_scale, 3),
                _fmt(result.fom, 3),
            )
            return values[col]
        if role == QtCore.Qt.ItemDataRole.BackgroundRole and col == 0:
            color = self._colors[index.row()] if index.row() < len(self._colors) else None
            if color is not None:
                return QtGui.QBrush(color)
        if role == _SORT_ROLE:
            keys = (
                0,
                entry.quality or "",
                entry.entry_id,
                entry.formula,
                _crystal_system_letter(entry.cell),
                entry.mineral_name or entry.formula,
                result.p_values.get("peakpos", 0.0),
                result.p_values.get("intensity", 0.0),
                result.i_scale,
                result.fom,
            )
            return keys[col]
        return None


class CandidateListTable(QtWidgets.QTableView):
    """Sortable candidate-list table.

    Signals
    -------
    candidate_activated(str):
        Double-click; carries the entry id (the reference software "select as matching").
    view_entry(str):
        Context-menu "查看条目".
    toggle_selection(str):
        Context-menu "选中/取消选中".
    export_requested():
        Context-menu "导出候选列表".
    """

    candidate_activated = QtCore.Signal(str)
    view_entry = QtCore.Signal(str)
    toggle_selection = QtCore.Signal(str)
    export_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = _CandidateListModel(self)
        self._proxy = QtCore.QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(_SORT_ROLE)
        self.setModel(self._proxy)
        self.setSortingEnabled(True)
        # Default: FoM descending (the reference software default candidate order).
        self.sortByColumn(9, QtCore.Qt.SortOrder.DescendingOrder)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.doubleClicked.connect(self._on_double_clicked)
        self.horizontalHeader().setStretchLastSection(True)

    def set_candidates(self, results: list[CandidateResult],
                       colors: list[QtGui.QColor | None] | None = None) -> None:
        """Fill from search-match *results* (optionally with pattern colors)."""
        self._model.set_candidates(results, colors)
        self.resizeColumnsToContents()

    def _entry_id(self, proxy_index: QtCore.QModelIndex) -> str | None:
        return self._model.entry_id_at(self._proxy.mapToSource(proxy_index).row())

    def _on_double_clicked(self, proxy_index: QtCore.QModelIndex) -> None:
        eid = self._entry_id(proxy_index)
        if eid is not None:
            self.candidate_activated.emit(eid)

    def _build_menu(self, pos: QtCore.QPoint) -> QtWidgets.QMenu:
        """Build the candidate-list context menu (exposed for inspection/tests)."""
        index = self.indexAt(pos)
        menu = QtWidgets.QMenu(self)
        eid = self._entry_id(index) if index.isValid() else None
        act_view = menu.addAction("查看条目...")
        act_view.setEnabled(eid is not None)
        act_view.triggered.connect(lambda _c=False, e=eid: e and self.view_entry.emit(e))  # type: ignore[func-returns-value]
        act_toggle = menu.addAction("选中/取消选中")
        act_toggle.setEnabled(eid is not None)
        act_toggle.triggered.connect(lambda _c=False, e=eid: e and self.toggle_selection.emit(e))  # type: ignore[func-returns-value]
        menu.addSeparator()
        act_export = menu.addAction("导出候选列表 (CSV)...")
        act_export.triggered.connect(self.export_requested.emit)
        return menu

    def _context_menu(self, pos: QtCore.QPoint) -> None:
        self._build_menu(pos).exec(self.viewport().mapToGlobal(pos))


# ---------------------------------------------------------------------------
# Match list
# ---------------------------------------------------------------------------
class _MatchListModel(QtCore.QAbstractTableModel):
    """Table model wrapping ``list[Phase]``."""

    HEADERS = ("", "条目", "化学式", "晶系", "物相", "含量 (%)")

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._phases: list[Phase] = []
        self._colors: list[QtGui.QColor | None] = []

    def set_phases(self, phases: list[Phase],
                   colors: list[QtGui.QColor | None] | None = None) -> None:
        self.beginResetModel()
        self._phases = list(phases)
        self._colors = list(colors) if colors is not None else [None] * len(self._phases)
        self.endResetModel()

    def entry_id_at(self, row: int) -> str | None:
        if 0 <= row < len(self._phases):
            return self._phases[row].entry.entry_id
        return None

    def rowCount(self, parent: QtCore.QModelIndex | QtCore.QPersistentModelIndex = QtCore.QModelIndex()) -> int:  # noqa: N802, B008
        return 0 if parent.isValid() else len(self._phases)

    def columnCount(self, parent: QtCore.QModelIndex | QtCore.QPersistentModelIndex = QtCore.QModelIndex()) -> int:  # noqa: N802, B008
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation,  # noqa: N802
                   role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> Any:
        if role == QtCore.Qt.ItemDataRole.DisplayRole and orientation == QtCore.Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    def data(self, index: QtCore.QModelIndex | QtCore.QPersistentModelIndex,
             role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        phase = self._phases[index.row()]
        entry = phase.entry
        col = index.column()
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            name = entry.mineral_name or entry.formula
            amount = f"{phase.weight_fraction * 100:.1f}" if phase.weight_fraction is not None else "—"
            values = ("", entry.entry_id, entry.formula, _crystal_system_letter(entry.cell), name, amount)
            return values[col]
        if role == QtCore.Qt.ItemDataRole.BackgroundRole and col == 0:
            color = self._colors[index.row()] if index.row() < len(self._colors) else None
            if color is not None:
                return QtGui.QBrush(color)
        if role == _SORT_ROLE:
            keys = (0, entry.entry_id, entry.formula,
                    _crystal_system_letter(entry.cell), entry.mineral_name or entry.formula,
                    phase.weight_fraction if phase.weight_fraction is not None else -1.0)
            return keys[col]
        return None


class MatchListTable(QtWidgets.QTableView):
    """Sortable match-list table.

    Signals
    -------
    phase_activated(str):
        Double-click; the reference software un-selects the phase back to the candidate
        list (``docs/match_list_basics.md``).  Carries the entry id.
    remove_phase(str):
        Context-menu "从匹配列表移除".
    export_requested():
        Context-menu "导出匹配列表".
    """

    phase_activated = QtCore.Signal(str)
    remove_phase = QtCore.Signal(str)
    export_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = _MatchListModel(self)
        self._proxy = QtCore.QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(_SORT_ROLE)
        self.setModel(self._proxy)
        self.setSortingEnabled(True)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.doubleClicked.connect(self._on_double_clicked)
        self.horizontalHeader().setStretchLastSection(True)

    def set_phases(self, phases: list[Phase],
                   colors: list[QtGui.QColor | None] | None = None) -> None:
        """Fill from selected *phases* (optionally with pattern colors)."""
        self._model.set_phases(phases, colors)
        self.resizeColumnsToContents()

    def _entry_id(self, proxy_index: QtCore.QModelIndex) -> str | None:
        return self._model.entry_id_at(self._proxy.mapToSource(proxy_index).row())

    def _on_double_clicked(self, proxy_index: QtCore.QModelIndex) -> None:
        eid = self._entry_id(proxy_index)
        if eid is not None:
            self.phase_activated.emit(eid)

    def _build_menu(self, pos: QtCore.QPoint) -> QtWidgets.QMenu:
        """Build the match-list context menu (exposed for inspection/tests)."""
        index = self.indexAt(pos)
        menu = QtWidgets.QMenu(self)
        eid = self._entry_id(index) if index.isValid() else None
        act_remove = menu.addAction("从匹配列表移除")
        act_remove.setEnabled(eid is not None)
        act_remove.triggered.connect(lambda _c=False, e=eid: e and self.remove_phase.emit(e))  # type: ignore[func-returns-value]
        menu.addSeparator()
        act_export = menu.addAction("导出匹配列表 (CSV)...")
        act_export.triggered.connect(self.export_requested.emit)
        return menu

    def _context_menu(self, pos: QtCore.QPoint) -> None:
        self._build_menu(pos).exec(self.viewport().mapToGlobal(pos))
