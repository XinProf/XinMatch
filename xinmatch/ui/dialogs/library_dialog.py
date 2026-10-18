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

v2.0.0 adds external-library mounting:

* **添加外部库…** — pick a ``*.sqlite`` / ``*.db`` file from *any* folder.
  XinMatch-schema files are searchable immediately; PolyXRD ``phases`` dumps
  are converted once into a XinMatch-schema index (``_IndexThread``, with a
  progress bar and cooperative cancel) and cached under the user data
  directory.  The mount is persisted in ``<user-data>/libraries.json``, so the
  path keeps working across restarts without copying the file next to the
  executable.
* **移除所选** / **建立/重建索引** — unmount (the source file is never
  touched) or force a re-conversion after the source database is rebuilt.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from xinmatch.core.cancel import OperationCancelledError, set_cancel_check
from xinmatch.core.db.multi_db import (
    KIND_POLYXRD,
    LibraryRecord,
    add_external_library,
    cod_full_db_path,
    ensure_library_index,
    list_libraries,
    remove_external_library,
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


class _IndexThread(QtCore.QThread):
    """Convert a mounted PolyXRD database into a XinMatch-schema index.

    The conversion lives in the core layer (``ensure_library_index``); this
    thread only wires progress + cooperative cancellation (``check_cancelled``
    polls ``isInterruptionRequested`` through the thread-local predicate).
    """

    progress = QtCore.Signal(int)
    done = QtCore.Signal(object)

    def __init__(
        self,
        library_id: str,
        *,
        force: bool = False,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.library_id = library_id
        self._force = force

    def run(self) -> None:  # noqa: D102
        set_cancel_check(self.isInterruptionRequested)
        try:
            summary = ensure_library_index(
                self.library_id, force=self._force, progress=self.progress.emit
            )
        except OperationCancelledError:
            self.done.emit({"_cancelled": True})
            return
        except Exception as exc:  # noqa: BLE001 - surfaced in the dialog
            self.done.emit({"error": str(exc), "_library_id": self.library_id})
            return
        finally:
            set_cancel_check(None)
        payload = dict(summary or {})
        payload["_cancelled"] = self.isInterruptionRequested()
        payload["_library_id"] = self.library_id
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
        #: PolyXRD index-conversion thread (v2.0.0 external libraries).
        self._index_thread: _IndexThread | None = None
        self._index_lib_id: str | None = None

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

        # --- External library mount / index controls (v2.0.0) -------------
        self._add_btn = QtWidgets.QPushButton("添加外部库…")
        self._add_btn.setToolTip(
            "挂载任意文件夹下的参考数据库（*.sqlite / *.db）。\n"
            "支持 XinMatch 格式与 PolyXRD phases 表（含 peaks_d/peaks_i）。"
        )
        self._add_btn.clicked.connect(self._add_external_library)
        self._remove_btn = QtWidgets.QPushButton("移除所选")
        self._remove_btn.setToolTip("仅从列表移除挂载（不删除源数据库文件）")
        self._remove_btn.clicked.connect(self._remove_selected_library)
        self._index_btn = QtWidgets.QPushButton("建立/重建索引")
        self._index_btn.setToolTip("为所选 PolyXRD 数据库建立检索索引（首次使用必须）")
        self._index_btn.clicked.connect(self._rebuild_index)
        mount_row = QtWidgets.QHBoxLayout()
        mount_row.addWidget(self._add_btn)
        mount_row.addWidget(self._remove_btn)
        mount_row.addWidget(self._index_btn)
        mount_row.addStretch(1)

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
        layout.addLayout(mount_row)
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
    # External libraries (v2.0.0)
    # ------------------------------------------------------------------
    def _add_external_library(self) -> None:
        """Pick a database file anywhere on disk and mount it."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "选择参考数据库（任意文件夹）",
            "",
            "SQLite 数据库 (*.sqlite *.db);;所有文件 (*)",
        )
        if not path:
            return
        self.add_external_path(path)

    def add_external_path(self, path: str) -> str | None:
        """Mount *path* and start indexing it when needed; returns the id.

        Public (non-underscored) so tests and scripted flows can mount a
        database without driving the native file dialog.
        """
        try:
            ext = add_external_library(path)
        except (ValueError, FileNotFoundError, OSError) as exc:
            QtWidgets.QMessageBox.warning(self, "无法挂载数据库", str(exc))
            return None

        self._reload_libraries()
        self._select_id(ext.id)
        record = next((r for r in self._records if r.id == ext.id), None)
        self._append_log(
            f"已挂载：{ext.path}"
            + ("（XinMatch 格式，可直接检索）" if record and not record.needs_index
               else "（PolyXRD 格式，正在建立检索索引…）")
        )
        if record is not None and record.needs_index:
            self._start_index(ext.id, force=False)
        return ext.id

    def _remove_selected_library(self) -> None:
        """Unmount the selected external library (source file is untouched)."""
        record = self.selected_record()
        if record is None:
            return
        if not record.external:
            QtWidgets.QMessageBox.information(
                self, "无法移除", "内置参考数据库不能移除；只能移除手动挂载的外部库。"
            )
            return
        answer = QtWidgets.QMessageBox.question(
            self,
            "移除挂载",
            f"从列表中移除「{record.display_name}」？\n\n"
            f"源文件不会被删除：{record.path}",
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        remove_external_library(record.id)
        cfg = load_config()
        if (cfg.get("reference_db") or {}).get("selected_library_id") == record.id:
            cfg.setdefault("reference_db", {})["selected_library_id"] = "cod_inorganics"
            save_config(cfg)
        self._append_log(f"已移除挂载：{record.display_name}")
        self._reload_libraries()

    def _rebuild_index(self) -> None:
        """Force a rebuild of the selected PolyXRD database's search index."""
        record = self.selected_record()
        if record is None:
            return
        if record.kind != KIND_POLYXRD:
            QtWidgets.QMessageBox.information(
                self,
                "无需建立索引",
                "只有 PolyXRD 格式（phases 表）的外部库需要转换索引；"
                "XinMatch 格式的数据库可直接检索。",
            )
            return
        self._start_index(record.id, force=True)

    def _start_index(self, library_id: str, *, force: bool) -> None:
        """Launch the index-conversion thread (shared by add / rebuild)."""
        if self._index_thread is not None:
            return
        self._index_lib_id = library_id
        thread = _IndexThread(library_id, force=force, parent=self)
        thread.progress.connect(self._on_build_progress)
        thread.done.connect(self._on_index_done)
        self._index_thread = thread

        self._progress_bar.setRange(0, 0)
        self._progress_bar.setFormat("建立检索索引…")
        self._add_btn.setEnabled(False)
        self._index_btn.setEnabled(False)
        self._remove_btn.setEnabled(False)
        self._log_view.clear()
        self._append_log(f"开始转换：{library_id}（源文件只读，输出到用户数据目录）")
        thread.start()

    def _on_index_done(self, summary: object) -> None:
        """Handle the index thread result (refresh the table on success)."""
        self._index_thread = None
        self._add_btn.setEnabled(True)
        self._index_btn.setEnabled(True)
        self._remove_btn.setEnabled(True)
        self._progress_bar.setRange(0, 100)
        payload = summary if isinstance(summary, dict) else {}

        if payload.get("_cancelled"):
            self._progress_bar.setFormat("已取消")
            self._append_log("已取消转换（未写入索引）")
            return
        if payload.get("error"):
            self._progress_bar.setFormat("转换失败")
            QtWidgets.QMessageBox.warning(
                self, "建立索引失败", f"无法转换该数据库：\n\n{payload['error']}"
            )
            return

        self._progress_bar.setFormat("索引就绪")
        entries = payload.get("entries_indexed", 0)
        seconds = payload.get("seconds", 0)
        self._append_log(f"索引完成：{entries:,} 条，用时 {seconds} 秒")
        lib_id = str(payload.get("_library_id") or self._index_lib_id or "")
        self._reload_libraries()
        if lib_id:
            self._select_id(lib_id)

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
        index_thread = self._index_thread
        if index_thread is not None and index_thread.isRunning():
            # The conversion polls check_cancelled() every few hundred rows, so
            # requesting interruption stops it quickly and leaves no sidecar.
            index_thread.requestInterruption()
            index_thread.wait(5000)
        super().closeEvent(event)
