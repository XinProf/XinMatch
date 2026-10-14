"""Reference-database picker dialog (multi-library GUI layer).

Lists every registry entry from
:func:`xinmatch.core.db.multi_db.list_libraries` in a table — display name,
entry count, on-disk path and availability — greys out and explains the reason
for unavailable libraries, and lets the user single-select one as the active
search-match database.  The chosen id is persisted by the caller (the main
window) into the YAML config under ``reference_db.selected_library_id``.

In addition to picking, the dialog can now drive two long-running / external
set-up actions from here:

* **构建 COD 全库…** — launches
  :func:`tools.build_cod_full_xinmatch.build` on a background
  :class:`~PySide6.QtCore.QThread`, streaming ``progress: N inserted`` log
  lines into a read-only log view and a busy progress bar, with a cancel
  button.  When the build finishes the registry table is refreshed so the new
  ``cod_full`` library becomes selectable immediately.
* **PDF-2 源路径…** — point the GUI at the local PolyXRD ``PDF2_2004.sqlite``
  dump (or its containing directory).  The choice is persisted to the YAML
  config and injected into the core layer via
  :func:`xinmatch.core.db.multi_db.set_pdf2_source_dir`, taking precedence
  over the ``XINMATCH_POLYXRD_DIR`` environment variable.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from xinmatch.core.db.multi_db import (
    LibraryRecord,
    cod_full_db_path,
    list_libraries,
    set_pdf2_source_dir,
)
from xinmatch.ui.dialogs.config import load_config, save_config

__all__ = ["LibraryDialog"]

_COLUMNS = ("参考数据库", "条目数", "路径", "状态")

#: Name of the logger the COD builder streams its progress records to.
_BUILDER_LOGGER = "tools.build_cod_full_xinmatch"


class _LogRelay(logging.Handler):
    """Forward builder log records to the GUI; parse ``progress: N inserted``.

    The handler is attached on the worker thread for the duration of the build
    and forwards every record through a Qt signal so the append / progress-bar
    updates run on the UI thread.
    """

    _PROGRESS_RE = re.compile(r"progress:\s*(\d+)\s+inserted")

    def __init__(self, on_log, on_progress) -> None:
        super().__init__()
        self._on_log = on_log
        self._on_progress = on_progress

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401 - Qt hook
        self._on_log(self.format(record))
        match = self._PROGRESS_RE.search(record.getMessage())
        if match:
            self._on_progress(int(match.group(1)))


class _BuildCodThread(QtCore.QThread):
    """Run the COD-full builder off the UI thread.

    Signals
    -------
    log_line(str):
        Every log record emitted by the builder (already formatted).
    progress(int):
        The running ``entries_inserted`` count parsed from ``progress: N``
        lines.
    done(object):
        The builder's summary dict once it returns (or an ``{"error": ...}``
        dict when the build raises).
    """

    log_line = QtCore.Signal(str)
    progress = QtCore.Signal(int)
    done = QtCore.Signal(object)

    def __init__(
        self,
        builder,
        out: Path,
        *,
        limit: int | None,
        cod_index: Path,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._builder = builder
        self._out = out
        self._limit = limit
        self._cod_index = cod_index

    def run(self) -> None:
        handler = _LogRelay(self.log_line.emit, self.progress.emit)
        lg = logging.getLogger(_BUILDER_LOGGER)
        lg.addHandler(handler)
        lg.setLevel(logging.INFO)
        try:
            summary = self._builder(
                self._out,
                start=0,
                limit=self._limit,
                resume=True,
                dmin=1.0,
                max_peaks=100,
                cod_index=self._cod_index,
                log_every=200,
            )
        except Exception as exc:  # defensive: keep the UI responsive
            logging.getLogger(_BUILDER_LOGGER).exception("build failed")
            summary = {"error": str(exc), "entries_inserted": 0}
        finally:
            lg.removeHandler(handler)
        # Capture the cancellation request on the worker thread *before* the
        # thread object finishes (the flag is unreliable to re-read from the UI
        # thread once run() returns).
        payload = dict(summary) if isinstance(summary, dict) else {}
        payload["_cancelled"] = self.isInterruptionRequested()
        self.done.emit(payload)


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
        self.resize(820, 560)
        records = list(libraries) if libraries is not None else list_libraries()

        #: Override builder callable (tests inject a fast fake; ``None`` pulls
        #: the real :func:`tools.build_cod_full_xinmatch.build` lazily).
        self._builder = None
        self._build_thread: _BuildCodThread | None = None

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

        self._populate_table(records, current_id)

        # Build-entry / sidecar hints from the registry notes (read-only).
        self._note_label = QtWidgets.QLabel(" ")
        self._note_label.setWordWrap(True)
        self._note_label.setStyleSheet("color: #555555;")
        self._refresh_note()

        # --- COD-full build controls -------------------------------------
        self._build_btn = QtWidgets.QPushButton("构建 COD 全库…")
        self._build_btn.clicked.connect(self._start_build)
        self._cancel_btn = QtWidgets.QPushButton("取消构建")
        self._cancel_btn.clicked.connect(self._cancel_build)
        self._cancel_btn.setEnabled(False)
        build_row = QtWidgets.QHBoxLayout()
        build_row.addWidget(self._build_btn)
        build_row.addWidget(self._cancel_btn)
        build_row.addStretch(1)

        self._progress_bar = QtWidgets.QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setFormat("就绪")

        self._log_view = QtWidgets.QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumHeight(140)
        self._log_view.setPlaceholderText("构建日志将在此显示…")

        # --- PDF-2 source path controls ----------------------------------
        self._pdf2_btn = QtWidgets.QPushButton("PDF-2 源路径…")
        self._pdf2_btn.clicked.connect(self._choose_pdf2_source)
        self._pdf2_clear_btn = QtWidgets.QPushButton("清除")
        self._pdf2_clear_btn.clicked.connect(self._clear_pdf2_source)
        self._pdf2_path_label = QtWidgets.QLabel(self._pdf2_source_label_text())
        self._pdf2_path_label.setStyleSheet("color: #333333;")
        pdf2_row = QtWidgets.QHBoxLayout()
        pdf2_row.addWidget(self._pdf2_btn)
        pdf2_row.addWidget(self._pdf2_clear_btn)
        pdf2_row.addWidget(self._pdf2_path_label, stretch=1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._table)
        layout.addLayout(build_row)
        layout.addWidget(self._progress_bar)
        layout.addWidget(self._log_view)
        layout.addLayout(pdf2_row)
        layout.addWidget(self._note_label)
        layout.addWidget(
            QtWidgets.QDialogButtonBox(
                QtWidgets.QDialogButtonBox.StandardButton.Ok
                | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
                accepted=self.accept,
                rejected=self.reject,
            )  # type: ignore[call-overload]
        )

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

    def _refresh_note(self) -> None:
        """Rebuild the bullet note label from the current records."""
        lines = [
            f"• {rec.display_name}：{rec.note}"
            for rec in self._records
            if rec.note
        ]
        self._note_label.setText("\n".join(lines) or " ")

    def _reload_libraries(self) -> None:
        """Re-query the registry and rebuild the table (keeping selection)."""
        prev = self.selected_id() if self._ids else None
        records = list_libraries()
        self._populate_table(records, prev)
        self._refresh_note()

    def selected_id(self) -> str:
        """Return the chosen library id (falls back to an available library)."""
        rows = self._table.selectionModel().selectedRows()
        if rows:
            row = rows[0].row()
            if 0 <= row < len(self._ids):
                return self._ids[row]  # type: ignore[no-any-return]
        for rec in self._records:
            if rec.available:
                return rec.id
        return self._ids[0] if self._ids else ""

    # ------------------------------------------------------------------
    # COD-full build
    # ------------------------------------------------------------------
    def _resolve_builder(self):
        """Return ``(builder_callable, cod_index_path)``.

        The real builder imports gemmi; we defer that import until a build is
        actually launched so offscreen widget tests (which inject a fake) pay
        no import cost.
        """
        if self._builder is not None:
            return self._builder, None
        from tools.build_cod_full_xinmatch import DEFAULT_COD_INDEX, build

        return build, DEFAULT_COD_INDEX

    def _start_build(self) -> None:
        """Confirm then launch the full COD build in the background."""
        answer = QtWidgets.QMessageBox.question(
            self,
            "构建 COD 全库",
            "全量构建会从 CIF 归档计算粉末谱，预计耗时分钟级到数小时，"
            f"输出到 {cod_full_db_path()}。\n\n是否开始后台构建？",
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self._launch_build(limit=None)

    def _launch_build(self, limit: int | None = None) -> None:
        """Launch the build thread (shared by the button and tests)."""
        if self._build_thread is not None:
            return
        builder, cod_index = self._resolve_builder()
        thread = _BuildCodThread(
            builder,
            cod_full_db_path(),
            limit=limit,
            cod_index=cod_index,
            parent=self,
        )
        thread.log_line.connect(self._append_log)
        thread.progress.connect(self._on_build_progress)
        thread.done.connect(self._on_build_done)
        self._build_thread = thread

        self._build_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._progress_bar.setRange(0, 0)  # busy / indeterminate
        self._progress_bar.setFormat("构建中…")
        self._log_view.clear()
        thread.start()

    def _append_log(self, line: str) -> None:
        self._log_view.appendPlainText(line)

    def _on_build_progress(self, inserted: int) -> None:
        self._progress_bar.setFormat(f"已插入 {inserted:,} 条")

    def _cancel_build(self) -> None:
        """Ask the running thread to stop after its current batch."""
        if self._build_thread is not None:
            self._build_thread.requestInterruption()

    def _on_build_done(self, summary: object) -> None:
        cancelled = bool(isinstance(summary, dict) and summary.get("_cancelled"))
        self._build_thread = None
        self._build_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._progress_bar.setRange(0, 100)

        if cancelled:
            self._progress_bar.setFormat("已取消")
            QtWidgets.QMessageBox.information(
                self, "构建已取消", "已请求取消，构建中止；列表未刷新。"
            )
            return

        if isinstance(summary, dict) and summary.get("error"):
            self._progress_bar.setFormat("构建失败")
            QtWidgets.QMessageBox.warning(
                self, "构建失败", f"COD 全库构建出错：{summary['error']}"
            )
            return

        self._progress_bar.setFormat("完成")
        # Refresh the registry so cod_full becomes selectable immediately.
        self._reload_libraries()
        inserted = summary.get("entries_inserted", 0) if isinstance(summary, dict) else 0
        seconds = summary.get("seconds", 0) if isinstance(summary, dict) else 0
        per_min = (
            summary.get("entries_per_min", 0) if isinstance(summary, dict) else 0
        )
        QtWidgets.QMessageBox.information(
            self,
            "COD 全库构建完成",
            f"已插入 {inserted:,} 条，用时 {seconds} 秒（约 {per_min:,} 条/分钟）。\n"
            "参考数据库列表已刷新。",
        )

    # ------------------------------------------------------------------
    # PDF-2 source path
    # ------------------------------------------------------------------
    def _pdf2_source_label_text(self) -> str:
        """One-line status of the currently configured PDF-2 source."""
        cfg = load_config()
        val = (cfg.get("pdf2_source_dir") or "").strip()
        if val:
            return f"当前：{val}"
        env = os.environ.get("XINMATCH_POLYXRD_DIR")
        if env:
            return f"当前：环境变量 XINMATCH_POLYXRD_DIR = {env}"
        return "当前：未配置（使用内置默认目录）"

    def _choose_pdf2_source(self) -> None:
        """Pick a PDF2_2004.sqlite file, persist it and inject it live."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "选择 PDF-2 数据库 (PDF2_2004.sqlite)",
            "",
            "SQLite 数据库 (*.sqlite);;所有文件 (*)",
        )
        if not path:
            return
        cfg = load_config()
        cfg["pdf2_source_dir"] = path
        save_config(cfg)
        set_pdf2_source_dir(path)
        self._pdf2_path_label.setText(self._pdf2_source_label_text())
        self._reload_libraries()

    def _clear_pdf2_source(self) -> None:
        """Clear the override (fall back to env var / built-in default)."""
        cfg = load_config()
        cfg["pdf2_source_dir"] = ""
        save_config(cfg)
        set_pdf2_source_dir(None)
        self._pdf2_path_label.setText(self._pdf2_source_label_text())
        self._reload_libraries()

    # ------------------------------------------------------------------
    # Close handling
    # ------------------------------------------------------------------
    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
        """If a build is running, ask before closing.

        The real builder is a synchronous long function that cannot be
        interrupted mid-CIF; we only *request* cancellation and wait briefly for
        the thread to exit after its current batch.  We deliberately avoid
        :meth:`QThread.terminate` (it can leave SQLite in a corrupt state).
        """
        thread = self._build_thread
        if thread is not None and thread.isRunning():
            answer = QtWidgets.QMessageBox.question(
                self,
                "构建进行中",
                "COD 全库构建正在进行中。关闭窗口将请求取消并等待当前批次结束。\n"
                "是否关闭？",
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No,
            )
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            thread.requestInterruption()
            thread.wait(3000)
        super().closeEvent(event)
