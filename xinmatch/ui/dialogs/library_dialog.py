"""Reference-database picker dialog (multi-library GUI layer).

Lists every registry entry from
:func:`xinmatch.core.db.multi_db.list_libraries` in a table — display name,
entry count, on-disk path and availability — greys out and explains the reason
for unavailable libraries, and lets the user single-select one as the active
search-match database.  The chosen id is persisted by the caller (the main
window) into the YAML config under ``reference_db.selected_library_id``.

The dialog is deliberately read-only / declarative: building or repairing a
missing library is done from the command line (see each record's ``note``),
never from here.
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from xinmatch.core.db.multi_db import LibraryRecord, list_libraries

__all__ = ["LibraryDialog"]

_COLUMNS = ("参考数据库", "条目数", "路径", "状态")


class LibraryDialog(QtWidgets.QDialog):
    """Modal picker for the active search-match reference database."""

    def __init__(
        self,
        current_id: str | None = None,
        libraries: list[LibraryRecord] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Build the picker.

        Parameters
        ----------
        current_id:
            The library id currently persisted in the config; its row is
            pre-selected when the library is available (an unavailable saved
            id falls back to the first available library instead).
        libraries:
            Registry records to display.  ``None`` calls
            :func:`~xinmatch.core.db.multi_db.list_libraries` live; tests pass
            synthetic records here.
        """
        super().__init__(parent)
        self.setWindowTitle("参考数据库")
        self.resize(760, 340)
        records = list(libraries) if libraries is not None else list_libraries()
        self._records = records
        self._ids = [rec.id for rec in records]

        self._table = QtWidgets.QTableWidget(len(records), len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self._table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Stretch
        )

        grey = QtGui.QBrush(QtGui.QColor("#888888"))
        selected_row = -1
        for row, rec in enumerate(records):
            count = (
                "—" if rec.entry_count is None else f"{rec.entry_count:,}"
            )
            status = (
                "可用"
                if rec.available
                else f"不可用：{rec.unavailable_reason or '未知原因'}"
            )
            cells = [rec.display_name, count, str(rec.path), status]
            for col, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(text)
                if not rec.available:
                    # Unavailable libraries are shown (so the user sees why
                    # they cannot pick them) but cannot be selected.
                    item.setFlags(
                        item.flags()
                        & ~QtCore.Qt.ItemFlag.ItemIsSelectable
                        & ~QtCore.Qt.ItemFlag.ItemIsEnabled
                    )
                    item.setForeground(grey)
                self._table.setItem(row, col, item)
            if rec.available and rec.id == current_id:
                selected_row = row

        if selected_row < 0:
            # No usable saved selection: default to the first available lib.
            for row, rec in enumerate(records):
                if rec.available:
                    selected_row = row
                    break
        if selected_row >= 0:
            self._table.selectRow(selected_row)

        # Build-entry / sidecar hints from the registry notes (read-only).
        note_lines = [
            f"• {rec.display_name}：{rec.note}"
            for rec in records
            if rec.note
        ]
        note = QtWidgets.QLabel("\n".join(note_lines) or " ")
        note.setWordWrap(True)
        note.setStyleSheet("color: #555555;")

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._table)
        layout.addWidget(note)
        layout.addWidget(
            QtWidgets.QDialogButtonBox(
                QtWidgets.QDialogButtonBox.StandardButton.Ok
                | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
                accepted=self.accept,
                rejected=self.reject,
            )
        )

    def selected_id(self) -> str:
        """Return the chosen library id (falls back to an available library)."""
        rows = self._table.selectionModel().selectedRows()
        if rows:
            row = rows[0].row()
            if 0 <= row < len(self._ids):
                return self._ids[row]
        for rec in self._records:
            if rec.available:
                return rec.id
        return self._ids[0] if self._ids else ""
