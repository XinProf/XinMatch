"""参考数据库选择对话框 (v3.0.0: 只有 ``.xinDB``)。

v3.0.0 把"能检索的参考库"收敛成一种格式 —— 列存 ``.xinDB``。旧版这个对话框
承担的四件事（构建 COD 全库 / 为 PolyXRD dump 建转换索引 / 选 PDF-2 源目录 /
挂载 v2 原生库）**全部随旧格式一起删除**，现在它只做三件事：

1. **列出**所有已知库（内置四行 + 用户挂载），可用性、相数、路径当场可见；
2. **挂载 / 卸载**任意位置的 ``.xinDB``（只改注册表，绝不删用户的文件）；
3. **选定**当前用于检索的那一个。

默认库是 COD-Inorg：便携包把它放在 ``<exe>/data/``，解压即可检索。
"""
from __future__ import annotations

import logging

from PySide6 import QtCore, QtGui, QtWidgets

from xinmatch.core.db.multi_db import (
    DEFAULT_LIBRARY_ID,
    LibraryRecord,
    add_external_library,
    list_libraries,
    remove_external_library,
)
from xinmatch.ui.dialogs.config import load_config, save_config

__all__ = ["LibraryDialog"]

logger = logging.getLogger(__name__)

#: Table columns: name / phase count / path / status.
_COLUMNS = ("库", "相数", "路径", "状态")


class LibraryDialog(QtWidgets.QDialog):
    """Modal picker for the active search-match reference library."""

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
        self.resize(880, 520)
        records = list(libraries) if libraries is not None else list_libraries()
        self._records: list[LibraryRecord] = []
        self._ids: list[str] = []

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
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)

        self._populate_table(records, current_id)

        #: 注册表备注（built_at / 来源 / 缺库原因）—— 只读，一屏说清。
        self._note_label = QtWidgets.QLabel(" ")
        self._note_label.setWordWrap(True)
        self._note_label.setStyleSheet("color: #555555;")

        self._add_btn = QtWidgets.QPushButton("挂载 .xinDB…")
        self._add_btn.setToolTip(
            "挂载任意文件夹下的 .xinDB 参考库（只登记路径，不复制文件）。\n"
            "v3.0.0 起只支持 .xinDB；旧的 cod_inorganics.db / PDF2 dump 已不再支持。"
        )
        self._add_btn.clicked.connect(self._add_external_library)
        self._remove_btn = QtWidgets.QPushButton("移除挂载")
        self._remove_btn.setToolTip("仅从列表移除挂载（不删除库文件）")
        self._remove_btn.clicked.connect(self._remove_selected_library)
        self._refresh_btn = QtWidgets.QPushButton("刷新")
        self._refresh_btn.setToolTip("重新探测各库是否可用（插拔移动硬盘后用）")
        self._refresh_btn.clicked.connect(self._reload_libraries)

        button_row = QtWidgets.QHBoxLayout()
        button_row.addWidget(self._add_btn)
        button_row.addWidget(self._remove_btn)
        button_row.addWidget(self._refresh_btn)
        button_row.addStretch(1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._table)
        layout.addLayout(button_row)
        layout.addWidget(self._note_label)
        layout.addWidget(
            QtWidgets.QDialogButtonBox(
                QtWidgets.QDialogButtonBox.StandardButton.Ok
                | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
                accepted=self.accept,
                rejected=self.reject,
            )  # type: ignore[call-overload]
        )
        self._refresh_note()

    # ------------------------------------------------------------------
    # Table population / refresh
    # ------------------------------------------------------------------
    def _populate_table(
        self, records: list[LibraryRecord], current_id: str | None
    ) -> None:
        """Fill the table from *records* and pick the pre-selected row."""
        self._records = list(records)
        self._ids = [rec.id for rec in records]
        self._table.setRowCount(len(records))
        grey = QtGui.QBrush(QtGui.QColor("#888888"))
        selected_row = -1
        for row, rec in enumerate(records):
            count = "—" if rec.entry_count is None else f"{rec.entry_count:,}"
            if rec.available:
                status = "默认库" if rec.default else "可用"
            else:
                status = f"不可用：{rec.unavailable_reason or '未知原因'}"
            cells = [rec.display_name, count, str(rec.path), status]
            for col, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(text)
                item.setToolTip(str(rec.note or rec.path))
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
            # No usable saved selection: prefer the default library, else the
            # first available one.
            for row, rec in enumerate(records):
                if rec.available and rec.default:
                    selected_row = row
                    break
        if selected_row < 0:
            for row, rec in enumerate(records):
                if rec.available:
                    selected_row = row
                    break
        if selected_row >= 0:
            self._table.selectRow(selected_row)

    def _refresh_note(self) -> None:
        """Rebuild the bullet note label from the current records."""
        lines = [f"• {rec.display_name}：{rec.note}" for rec in self._records if rec.note]
        if not any(rec.available for rec in self._records):
            lines.append(
                "• 没有可用的参考库：把 COD-Inorg-*.xinDB 放进程序目录的 data\\ 下，"
                "或用「挂载 .xinDB…」指定它所在的位置。"
            )
        self._note_label.setText("\n".join(lines) or " ")

    def _reload_libraries(self) -> None:
        """Re-query the registry and rebuild the table (keeping selection)."""
        prev = self.selected_id() if self._ids else None
        records = list_libraries()
        self._populate_table(records, prev)
        self._refresh_note()

    def _select_id(self, library_id: str) -> None:
        """Select the row of *library_id* (no-op when it is not listed)."""
        if library_id in self._ids:
            self._table.selectRow(self._ids.index(library_id))

    def selected_record(self) -> LibraryRecord | None:
        """Return the record of the selected row (``None`` when empty)."""
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        if 0 <= row < len(self._records):
            return self._records[row]
        return None

    def selected_id(self) -> str:
        """Return the chosen library id (falls back to an available library)."""
        rows = self._table.selectionModel().selectedRows()
        if rows:
            row = rows[0].row()
            if 0 <= row < len(self._ids):
                return self._ids[row]
        for rec in self._records:
            if rec.available and rec.default:
                return rec.id
        for rec in self._records:
            if rec.available:
                return rec.id
        return self._ids[0] if self._ids else ""

    # ------------------------------------------------------------------
    # Mount / unmount
    # ------------------------------------------------------------------
    def _add_external_library(self) -> None:
        """Pick a ``.xinDB`` file anywhere on disk and mount it."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "选择 .xinDB 参考库（任意文件夹）",
            "",
            "XinMatch v3 数据库 (*.xinDB);;所有文件 (*)",
        )
        if not path:
            return
        self.add_external_path(path)

    def add_external_path(self, path: str) -> str | None:
        """Mount *path* and return its library id (``None`` on failure).

        Public (non-underscored) so tests and scripted flows can mount a
        library without driving the native file dialog.
        """
        try:
            ext = add_external_library(path)
        except (ValueError, FileNotFoundError, OSError) as exc:
            QtWidgets.QMessageBox.warning(self, "无法挂载参考库", str(exc))
            return None

        self._reload_libraries()
        self._select_id(ext.id)
        logger.info("mounted %s", ext.path)
        return ext.id

    def _remove_selected_library(self) -> None:
        """Unmount the selected external library (source file is untouched)."""
        record = self.selected_record()
        if record is None:
            return
        if not record.external:
            QtWidgets.QMessageBox.information(
                self, "无法移除", "内置参考库不能移除；只能移除手动挂载的外部库。"
            )
            return
        answer = QtWidgets.QMessageBox.question(
            self,
            "移除挂载",
            f"从列表中移除「{record.display_name}」？\n\n"
            f"库文件不会被删除：{record.path}",
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        remove_external_library(record.id)
        cfg = load_config()
        if (cfg.get("reference_db") or {}).get("selected_library_id") == record.id:
            cfg.setdefault("reference_db", {})["selected_library_id"] = DEFAULT_LIBRARY_ID
            save_config(cfg)
        self._reload_libraries()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
        """Nothing to tear down in v3.0.0 (no worker threads), kept for symmetry."""
        super().closeEvent(event)
