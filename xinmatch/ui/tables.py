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

from collections.abc import Iterable
from typing import Any

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from xinmatch.core.model.entry import CellParams, Entry
from xinmatch.core.model.peak import Peak
from xinmatch.core.model.phase import Phase
from xinmatch.core.search.fom import CandidateResult
from xinmatch.core.search.phase_key import group_same_phase

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


def _cell_text(cell: CellParams | None) -> str:
    """One-line unit-cell summary used by the candidate-list variant tooltip."""
    if cell is None:
        return "晶胞未知"
    return (f"a={cell.a:.4f} b={cell.b:.4f} c={cell.c:.4f} "
            f"α={cell.alpha:.2f} β={cell.beta:.2f} γ={cell.gamma:.2f}")


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

    def peaks(self) -> list[Peak]:
        """The full peak list currently in the model (export / tests)."""
        return list(self._model._peaks)

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
    """Table model wrapping ``list[CandidateResult]`` with phase-family folding.

    A reference library holds many cards for the *same* phase (18 beryl-type
    entries can fill a Top-40 on their own), so the candidate list folds each
    phase family into one row by default — see
    :mod:`xinmatch.core.search.phase_key`.  ``merge=False`` (or
    :meth:`set_merge`) unfolds every card while keeping the "变体" column, so
    the user can inspect which card was which.
    """

    HEADERS = ("", "质量", "条目", "化学式", "晶系", "物相",
               "P(2θ)", "P(I/I₀)", "I缩放", "FoM", "变体")

    #: Marker drawn in the first column for a strong-line anchored candidate
    #: (v3.3.0).  It sits in the colour band so no column is added.
    ANCHOR_MARK = "★"

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._results: list[CandidateResult] = []
        self._colors: list[QtGui.QColor | None] = []
        #: 条目 id → 是否通过「强线锚定」判据（少线相标记，v3.3.0）。
        self._anchored: set[str] = set()
        #: 相位族（源行索引分组，族内按排名先后）。
        self._families: list[list[int]] = []
        #: 源行 → 族序号（-1 = 不属于任何族）。
        self._family_of: list[int] = []
        #: 源行 → 所在相位族的成员数（1 = 无变体）。
        self._family_size: list[int] = []
        #: 展示行 → 源行。合并变体时只保留族代表，所以两者不一定相同。
        self._visible: list[int] = []
        self._merge = True
        #: 展示行数上限（§35 方案 B）。``None`` = 不截断（兼容既有调用方）。
        #: 折叠时一行 ≈ 一个相族，所以截断同时是「族数上限」。
        self._max_rows: int | None = None

    # -- population ------------------------------------------------------
    def set_candidates(self, results: list[CandidateResult],
                       colors: list[QtGui.QColor | None] | None = None,
                       *,
                       families: list[list[int]] | None = None,
                       merge: bool | None = None,
                       anchored_ids: Iterable[str] | None = None) -> None:
        """Replace rows with *results*; optional per-row pattern *colors*.

        *families* are index groups from
        :func:`xinmatch.core.search.phase_key.group_same_phase`; they are
        computed here when omitted.  With *merge* the table shows one row per
        phase family (its best-ranked member); otherwise every card is a row
        but the "变体" column still reports ``族内名次/族内条数``.

        *anchored_ids* are the entries the sequential engine flagged as
        strong-line anchored (``ResidualSearchResult.anchored_ids``); their
        first column gets a marker.  Ordering is never changed here — the mark
        only tells the user which sparse phases a peak-count FoM buries.
        """
        self.beginResetModel()
        self._results = list(results)
        self._colors = list(colors) if colors is not None else [None] * len(self._results)
        self._anchored = set(anchored_ids or ())
        if families is None:
            families = group_same_phase([r.entry for r in self._results])
        self._families = [list(g) for g in families if g]
        if merge is not None:
            self._merge = bool(merge)
        self._rebuild_rows()
        self.endResetModel()

    def set_merge(self, merge: bool) -> None:
        """Fold (``True``) or unfold (``False``) the same-phase variants."""
        merge = bool(merge)
        if merge == self._merge:
            return
        self.beginResetModel()
        self._merge = merge
        self._rebuild_rows()
        self.endResetModel()

    def set_max_rows(self, max_rows: int | None) -> None:
        """Cap the number of displayed rows (``None`` = unlimited).

        候选表可能一次收到几百张卡（§35：检索侧取足够多的卡以填满族的显示
        预算），表格在这里截断。折叠时一行 ≈ 一个相族，所以这是「族数上限」；
        展开时按卡计。``0`` / 负数按不截断处理（防御脏配置）。
        """
        value: int | None = None
        if max_rows is not None:
            value = int(max_rows)
            if value <= 0:
                value = None
        if value == self._max_rows:
            return
        self.beginResetModel()
        self._max_rows = value
        self._rebuild_rows()
        self.endResetModel()

    @property
    def max_rows(self) -> int | None:
        """The current display-row cap (``None`` = unlimited)."""
        return self._max_rows

    @property
    def merging(self) -> bool:
        return self._merge

    def has_families(self) -> bool:
        """True when at least one family holds more than one card."""
        return any(len(g) > 1 for g in self._families)

    def _rebuild_rows(self) -> None:
        n = len(self._results)
        self._family_of = [-1] * n
        self._family_size = [1] * n
        visible: list[int] = []
        covered: set[int] = set()
        for fi, group in enumerate(self._families):
            members = [i for i in group if 0 <= i < n]
            if not members:
                continue
            for i in members:
                self._family_of[i] = fi
                self._family_size[i] = len(members)
                covered.add(i)
            visible.extend(members[:1] if self._merge else members)
        # 调用方只给了部分族时，落单的行也要显示——否则候选会静默消失。
        visible.extend(i for i in range(n) if i not in covered)
        # 行数上限（§35）：折叠时前 N 行 = 前 N 个族；展开时 = 前 N 张卡。
        if self._max_rows is not None:
            visible = visible[: self._max_rows]
        self._visible = visible

    # -- row accessors ---------------------------------------------------
    def result_at(self, row: int) -> CandidateResult | None:
        """The :class:`CandidateResult` backing display *row*."""
        if 0 <= row < len(self._visible):
            return self._results[self._visible[row]]
        return None

    def visible_results(self) -> list[CandidateResult]:
        """Candidates in display order (the folded set when merging)."""
        return [self._results[i] for i in self._visible]

    def family_members(self, row: int) -> list[int]:
        """Source-row indices of *row*'s phase family (best-ranked first)."""
        if not 0 <= row < len(self._visible):
            return []
        fi = self._family_of[self._visible[row]]
        if fi < 0:
            return [self._visible[row]]
        return [i for i in self._families[fi] if 0 <= i < len(self._results)]

    def family_results(self, row: int) -> list[CandidateResult]:
        """All candidates of *row*'s phase family, best-ranked first."""
        return [self._results[i] for i in self.family_members(row)]

    def family_size_at(self, row: int) -> int:
        """Number of cards in the row's phase family (1 when it has no siblings)."""
        if 0 <= row < len(self._visible):
            return self._family_size[self._visible[row]]
        return 1

    def entry_id_at(self, row: int) -> str | None:
        if 0 <= row < len(self._visible):
            return self._results[self._visible[row]].entry.entry_id
        return None

    def variant_text(self, row: int) -> str:
        """Text for the "变体" column at display *row*."""
        if not 0 <= row < len(self._visible):
            return ""
        src = self._visible[row]
        size = self._family_size[src]
        if size <= 1:
            return ""
        if self._merge:
            return f"{size} 条"
        members = self.family_members(row)
        rank = members.index(src) + 1 if src in members else 1
        return f"{rank}/{size}"

    def variant_tooltip(self, row: int) -> str:
        """Multi-line tooltip listing every card of the row's family + its cell."""
        members = self.family_results(row)
        if len(members) <= 1:
            return ""
        lines = [f"同一物相的 {len(members)} 张卡片（按当前排名）："]
        for k, res in enumerate(members, 1):
            entry = res.entry
            mark = "▶" if k == 1 else "  "
            lines.append(f"{mark} {k}. {entry.entry_id}  {_cell_text(entry.cell)}")
        lines.append("右键 → 展开同相变体，可逐张查看与确认。")
        return "\n".join(lines)

    def is_anchored(self, row: int) -> bool:
        """Whether display *row* carries the strong-line anchor mark."""
        if not 0 <= row < len(self._visible):
            return False
        return self._results[self._visible[row]].entry.entry_id in self._anchored

    def anchor_tooltip(self, row: int) -> str:
        """Explanation for the anchor mark (empty when the row is not marked)."""
        if not self.is_anchored(row):
            return ""
        return (
            "★ 最强参考线落在强残差峰上，且位置精度高、自身反射解释过半。\n"
            "这类「少线相」在按峰条数计分的 FoM 里天然排在后面，\n"
            "所以即使排名靠后也值得看一眼——确认前请核对参考线条。"
        )

    # -- model API -------------------------------------------------------
    def rowCount(self, parent: QtCore.QModelIndex | QtCore.QPersistentModelIndex = QtCore.QModelIndex()) -> int:  # noqa: N802, B008
        return 0 if parent.isValid() else len(self._visible)

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
        src = self._visible[index.row()]
        result = self._results[src]
        entry: Entry = result.entry
        col = index.column()
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            phase = entry.mineral_name or entry.formula
            if entry.mineral_name and entry.formula:
                phase = f"{entry.formula} ({entry.mineral_name})"
            values = (
                self.ANCHOR_MARK if entry.entry_id in self._anchored else "",
                entry.quality or "—",
                entry.entry_id,
                entry.formula,
                _crystal_system_letter(entry.cell),
                phase,
                _fmt(result.p_values.get("peakpos")),
                _fmt(result.p_values.get("intensity")),
                _fmt(result.i_scale, 3),
                _fmt(result.fom, 3),
                self.variant_text(index.row()),
            )
            return values[col]
        if role == QtCore.Qt.ItemDataRole.ToolTipRole and col == 10:
            return self.variant_tooltip(index.row()) or None
        if role == QtCore.Qt.ItemDataRole.ToolTipRole and col == 0:
            return self.anchor_tooltip(index.row()) or None
        if role == QtCore.Qt.ItemDataRole.BackgroundRole and col == 0:
            color = self._colors[src] if src < len(self._colors) else None
            if color is not None:
                return QtGui.QBrush(color)
        if role == _SORT_ROLE:
            keys = (
                1 if entry.entry_id in self._anchored else 0,
                entry.quality or "",
                entry.entry_id,
                entry.formula,
                _crystal_system_letter(entry.cell),
                entry.mineral_name or entry.formula,
                result.p_values.get("peakpos", 0.0),
                result.p_values.get("intensity", 0.0),
                result.i_scale,
                result.fom,
                self._family_size[src],
            )
            return keys[col]
        return None


class CandidateListTable(QtWidgets.QTableView):
    """Sortable candidate-list table with phase-family folding (v3.2.0).

    Rows arrive already ranked by FoM.  Cards describing the *same* phase
    (``group_same_phase``) are folded into one row by default so a family of
    18 near-identical entries cannot flood the list; the "变体" column shows
    ``N 条``, its tooltip lists every card with its unit cell, and the
    context menu can toggle between folded and unfolded views.

    Signals
    -------
    candidate_activated(str):
        Confirm the entry as a matching phase — double-click, Enter, or the
        context-menu "确认为匹配物相" item (v3.1.0 sequential workflow).
    view_entry(str):
        Context-menu "查看条目".
    toggle_selection(str):
        Reserved: selection toggle requested from outside (kept for API
        compatibility; no longer exposed in the context menu).
    export_requested():
        Context-menu "导出候选列表".
    family_mode_changed(bool):
        Emitted after the fold/unfold toggle; ``True`` means variants are
        merged again.  Any exporter/report should write
        :meth:`visible_results` so its row count matches what the user sees.
    """

    candidate_activated = QtCore.Signal(str)
    view_entry = QtCore.Signal(str)
    toggle_selection = QtCore.Signal(str)
    export_requested = QtCore.Signal()
    family_mode_changed = QtCore.Signal(bool)

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

    # -- public API ------------------------------------------------------
    def set_candidates(self, results: list[CandidateResult],
                       colors: list[QtGui.QColor | None] | None = None,
                       *,
                       merge: bool | None = None,
                       anchored_ids: Iterable[str] | None = None) -> None:
        """Fill from search-match *results* (optionally with pattern colors).

        *merge* keeps the fold state across calls when left ``None``.
        *anchored_ids* marks strong-line anchored rows (see
        ``_CandidateListModel.set_candidates``).  显示行数上限由
        :meth:`set_max_rows` 单独控制（跨调用保持）。
        """
        self._model.set_candidates(
            results, colors, merge=merge, anchored_ids=anchored_ids
        )
        self.resizeColumnsToContents()

    def set_max_rows(self, max_rows: int | None) -> None:
        """Cap displayed rows (``None`` = unlimited); see the model method."""
        self._model.set_max_rows(max_rows)

    def max_rows(self) -> int | None:
        """The current display-row cap (``None`` = unlimited)."""
        return self._model.max_rows

    def is_anchored(self, row: int) -> bool:
        """Whether **proxy** (display) *row* carries the anchor mark."""
        src = self._proxy.mapToSource(self._proxy.index(row, 0))
        return self._model.is_anchored(src.row())

    def set_merge_families(self, merge: bool) -> None:
        """Fold / unfold the same-phase variants (no-op when unchanged)."""
        before = self._model.merging
        self._model.set_merge(merge)
        if self._model.merging != before:
            self.resizeColumnsToContents()
            self.family_mode_changed.emit(self._model.merging)

    def is_merging_families(self) -> bool:
        return self._model.merging

    def visible_results(self) -> list[CandidateResult]:
        """Candidates in the currently displayed (possibly folded) order."""
        return self._model.visible_results()

    def result_at(self, row: int) -> CandidateResult | None:
        """Candidate behind *row* — a **proxy** (display) row index."""
        src = self._proxy.mapToSource(self._proxy.index(row, 0))
        return self._model.result_at(src.row())

    def family_size_at(self, row: int) -> int:
        """Phase-family size of *row* — a **proxy** (display) row index."""
        src = self._proxy.mapToSource(self._proxy.index(row, 0))
        return self._model.family_size_at(src.row())

    def family_results_at(self, row: int) -> list[CandidateResult]:
        """Every card of *row*'s phase family — proxy row index."""
        src = self._proxy.mapToSource(self._proxy.index(row, 0))
        return self._model.family_results(src.row())

    def current_entry_id(self) -> str | None:
        """Entry id of the highlighted row (``None`` when nothing is selected)."""
        rows = self.selectionModel().selectedRows() if self.selectionModel() else []
        if not rows:
            current = self.currentIndex()
            return self._entry_id(current) if current.isValid() else None
        return self._entry_id(rows[0])

    def selected_results(self) -> list[CandidateResult]:
        """Candidates under the selection (falls back to the current row).

        Maps through the model's fold table, so it stays correct while
        variants are merged (``row != candidate index`` in that mode).
        """
        indexes = self.selectionModel().selectedRows() if self.selectionModel() else []
        if not indexes:
            current = self.currentIndex()
            indexes = [current] if current.isValid() else []
        out: list[CandidateResult] = []
        for idx in indexes:
            result = self._model.result_at(self._proxy.mapToSource(idx).row())
            if result is not None:
                out.append(result)
        return out

    def _entry_id(self, proxy_index: QtCore.QModelIndex) -> str | None:
        return self._model.entry_id_at(self._proxy.mapToSource(proxy_index).row())

    # -- signals / menu --------------------------------------------------
    def _on_double_clicked(self, proxy_index: QtCore.QModelIndex) -> None:
        eid = self._entry_id(proxy_index)
        if eid is not None:
            self.candidate_activated.emit(eid)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        """Enter / Return confirms the highlighted candidate (v3.1.0)."""
        if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            eid = self.current_entry_id()
            if eid is not None:
                self.candidate_activated.emit(eid)
                return
        super().keyPressEvent(event)

    def _build_menu(self, pos: QtCore.QPoint) -> QtWidgets.QMenu:
        """Build the candidate-list context menu (exposed for inspection/tests)."""
        index = self.indexAt(pos)
        menu = QtWidgets.QMenu(self)
        eid = self._entry_id(index) if index.isValid() else None
        act_confirm = menu.addAction("确认为匹配物相（加入匹配列表）  Enter")
        act_confirm.setEnabled(eid is not None)
        act_confirm.triggered.connect(
            lambda _c=False, e=eid: e and self.candidate_activated.emit(e)  # type: ignore[func-returns-value]
        )
        menu.addSeparator()
        act_view = menu.addAction("查看条目...")
        act_view.setEnabled(eid is not None)
        act_view.triggered.connect(lambda _c=False, e=eid: e and self.view_entry.emit(e))  # type: ignore[func-returns-value]
        menu.addSeparator()
        merging = self._model.merging
        size = self.family_size_at(index.row()) if index.isValid() else 1
        if self._model.has_families():
            label = f"展开同相变体（{size} 条）" if merging else "合并同相变体"
        else:
            label = "无同相变体"
        act_family = menu.addAction(label)
        act_family.setEnabled(self._model.has_families())
        act_family.triggered.connect(lambda _c=False: self.set_merge_families(not merging))
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

    def phases(self) -> list[Phase]:
        """The confirmed phases currently in the model (export / tests)."""
        return list(self._model._phases)

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
