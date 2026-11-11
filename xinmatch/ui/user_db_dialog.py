"""用户数据库对话框 —— 自建参考相的管理入口。

它是 :mod:`xinmatch.core.db.user_db` 的**唯一** GUI 门面，核心层负责一切
（清单、整库重建、注册表挂载），这里只做三件事：

1. **看见** —— 列出用户库里每一相的 ID / 化学式 / 矿物名 / 空间群 / 峰数，
   并常显库文件路径与相数（用户最常问的两个问题）；
2. **增删** —— 添加 CIF（可多选）、删除选中、重建库；
3. **说清失败** —— 解析失败的 CIF 绝不静默：一份一份列在对话框底部，
   并说明"条目已保留在清单里，修好重开即可"，避免用户重复导入。

为什么不做"编辑条目"：用户库的真相源是清单里的**原始 CIF 路径**，条目内容
只能通过改源文件再重建来更新 —— 在对话框里改化学式只会造出库与源不一致的
第二真相。
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from xinmatch.core.db import user_db as udb
from xinmatch.core.db.user_db import UserDbResult, UserEntry
from xinmatch.ui.busy import run_with_busy

__all__ = ["UserDbDialog"]

logger = logging.getLogger(__name__)

#: 表格列（顺序即显示顺序）。
_COLUMNS: tuple[str, ...] = ("条目 ID", "化学式", "矿物名", "空间群", "峰数")

#: CIF 文件选择框的通配符（含少数把结构写成 .txt 的来源）。
_CIF_FILTER = "晶体结构文件 (*.cif *.CIF *.txt);;所有文件 (*)"


class UserDbDialog(QtWidgets.QDialog):
    """Manage the user-built reference library (``UserDB.xinDB``).

    The dialog is intentionally *not* a modal editor for phase contents: every
    mutation goes through :mod:`xinmatch.core.db.user_db`, which rebuilds the
    whole ``.xinDB`` from the manifest.  That keeps a single source of truth.

    Signals:
        library_changed: 库内容发生变化（导入 / 删除 / 重建成功）。主窗口据此
            刷新当前库的相数与"大库"提示。
    """

    library_changed = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """Build the table, the action row and the status note."""
        super().__init__(parent)
        self.setWindowTitle("用户数据库")
        self.resize(820, 520)

        #: 当前清单里解析失败、因而没能入库的 ``(路径, 原因)`` —— 常显在底部。
        self._last_skipped: tuple[tuple[str, str], ...] = ()
        #: 是否发生过内容变更（关窗后主窗口据此决定要不要刷新库状态）。
        self._dirty = False

        self._table = QtWidgets.QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(list(_COLUMNS))
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)

        self._add_btn = QtWidgets.QPushButton("添加 CIF…")
        self._add_btn.setToolTip(
            "选择一个或多个 CIF 结构文件加入用户库。\n"
            "同一份 CIF 重复添加是幂等的；库内容变化后立即可被检索命中。"
        )
        self._add_btn.clicked.connect(self._on_add_clicked)
        self._remove_btn = QtWidgets.QPushButton("删除选中")
        self._remove_btn.setToolTip(
            "从用户库移除选中条目（只改清单，源 CIF 文件不会被删除）"
        )
        self._remove_btn.clicked.connect(self._on_remove_clicked)
        self._rebuild_btn = QtWidgets.QPushButton("重建库")
        self._rebuild_btn.setToolTip(
            "按清单重新构建 UserDB.xinDB。\n"
            "改了某个源 CIF 的内容、或补上了之前解析失败的文件后用它。"
        )
        self._rebuild_btn.clicked.connect(self._on_rebuild_clicked)
        self._open_dir_btn = QtWidgets.QPushButton("打开库目录")
        self._open_dir_btn.setToolTip("在文件管理器里打开用户库所在目录")
        self._open_dir_btn.clicked.connect(self._open_library_dir)

        action_row = QtWidgets.QHBoxLayout()
        action_row.addWidget(self._add_btn)
        action_row.addWidget(self._remove_btn)
        action_row.addWidget(self._rebuild_btn)
        action_row.addWidget(self._open_dir_btn)
        action_row.addStretch(1)

        self._status_label = QtWidgets.QLabel(" ")
        self._status_label.setWordWrap(True)
        self._status_label.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._detail_label = QtWidgets.QLabel(" ")
        self._detail_label.setWordWrap(True)
        self._detail_label.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._table, 1)
        layout.addLayout(action_row)
        layout.addWidget(self._status_label)
        layout.addWidget(self._detail_label)
        layout.addWidget(
            QtWidgets.QDialogButtonBox(
                QtWidgets.QDialogButtonBox.StandardButton.Close,
                rejected=self.reject,
            )  # type: ignore[call-overload]
        )

        self.refresh()

    # ------------------------------------------------------------------
    # 只读视图
    # ------------------------------------------------------------------
    def entries(self) -> list[UserEntry]:
        """当前显示的行（按 entry_id 排序，与库内顺序一致）。"""
        return udb.list_user_entries()

    def entry_ids(self) -> list[str]:
        """当前显示的 entry_id 列表（与表格行一一对应）。"""
        return [e.entry_id for e in self.entries()]

    def selected_entry_ids(self) -> list[str]:
        """用户勾选的 entry_id（按行号升序，空表返回空列表）。"""
        ids = self.entry_ids()
        rows = sorted({idx.row() for idx in self._table.selectionModel().selectedRows()})
        return [ids[row] for row in rows if 0 <= row < len(ids)]

    def changed(self) -> bool:
        """本次对话框生命周期内库内容是否变过。"""
        return self._dirty

    # ------------------------------------------------------------------
    # 刷新 / 渲染
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """从磁盘重读库内容并重画表格（不做任何写操作）。"""
        entries = udb.list_user_entries()
        self._table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            cells = (
                entry.entry_id,
                entry.formula or "—",
                entry.mineral_name or "—",
                entry.space_group or "—",
                f"{entry.n_peaks:,}",
            )
            for col, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(text)
                item.setToolTip(entry.entry_id)
                if col == 4:
                    item.setTextAlignment(
                        QtCore.Qt.AlignmentFlag.AlignRight
                        | QtCore.Qt.AlignmentFlag.AlignVCenter
                    )
                self._table.setItem(row, col, item)
        self._render_status(len(entries))

    def _render_status(self, count: int) -> None:
        """状态行：库路径 + 相数 + 空库/无库的下一步提示。"""
        library = udb.user_library_path()
        if count == 0:
            head = (
                f"用户库为空（{library}）" if library.is_file() else "尚未建立用户库"
            )
            hint = "点「添加 CIF…」导入结构文件（可多选）；导入后即可参与检索。"
            self._status_label.setText(f"{head}　·　{hint}")
        else:
            size_kb = library.stat().st_size / 1024 if library.is_file() else 0.0
            head = f"共 {count} 相　·　{library}（{size_kb:,.1f} KB）"
            hint = "用户库已挂入参考库列表，Search-Match 可直接命中这些相。"
            self._status_label.setText(f"{head}\n{hint}")
        self._render_detail()

    def _render_detail(self) -> None:
        """细节行：清单里解析失败的文件逐条列出（绝不静默失败）。

        注意这批文件的口径不是"上一次操作"，而是"**当前清单**里仍然入不了库
        的那些"：失败条目按设计留在清单中（修好源文件重建即可），所以它们会
        在每次重建时重复出现 —— 这正是我们要的，用户能一眼看到自己的库缺了
        哪几相。
        """
        if not self._last_skipped:
            self._detail_label.setText(" ")
            return
        lines = [f"以下 {len(self._last_skipped)} 份文件仍在清单中但未能入库："]
        for path, reason in self._last_skipped[:10]:
            lines.append(f"　• {path} —— {reason}")
        if len(self._last_skipped) > 10:
            lines.append(f"　… 另有 {len(self._last_skipped) - 10} 份，详见日志")
        self._detail_label.setText("\n".join(lines))

    # ------------------------------------------------------------------
    # 写操作（核心层同步执行；按钮路径外包忙碌对话框）
    # ------------------------------------------------------------------
    def add_paths(self, paths: Iterable[str | Path]) -> UserDbResult:
        """把若干 CIF 加入用户库并刷新视图（同步，供测试与脚本调用）。"""
        result = udb.add_cif_files(paths)
        self._after_change(result)
        return result

    def remove_entry_ids(self, entry_ids: Sequence[str]) -> UserDbResult:
        """删除若干条目并刷新视图（同步，供测试与脚本调用）。"""
        result = udb.remove_entries(entry_ids)
        self._after_change(result)
        return result

    def rebuild_now(self) -> UserDbResult:
        """按清单整库重建（同步），用于源 CIF 内容改过之后。"""
        result = udb.rebuild()
        self._after_change(result)
        return result

    def _after_change(self, result: UserDbResult) -> None:
        """统一收尾：记录跳过项、刷新表格、通知主窗口。"""
        self._last_skipped = tuple(result.skipped)
        self.refresh()
        self._dirty = True
        self.library_changed.emit()
        if result.skipped:
            logger.warning("用户库跳过 %d 份文件", len(result.skipped))

    # ------------------------------------------------------------------
    # 按钮槽
    # ------------------------------------------------------------------
    def _on_add_clicked(self) -> None:
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "选择要加入用户库的 CIF 文件", "", _CIF_FILTER
        )
        if not paths:
            return
        self._run_busy(
            "正在导入 CIF…",
            lambda: udb.add_cif_files(paths),
            f"导入 {len(paths)} 份 CIF",
        )

    def _on_remove_clicked(self) -> None:
        targets = self.selected_entry_ids()
        if not targets:
            QtWidgets.QMessageBox.information(
                self, "删除条目", "请先在列表中选择要删除的条目。"
            )
            return
        answer = QtWidgets.QMessageBox.question(
            self,
            "删除条目",
            f"从用户库移除选中的 {len(targets)} 个条目？\n\n"
            "只改用户库清单，源 CIF 文件不会被删除。",
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self._run_busy(
            "正在重建用户库…",
            lambda: udb.remove_entries(targets),
            f"移除 {len(targets)} 个条目",
        )

    def _on_rebuild_clicked(self) -> None:
        self._run_busy("正在重建用户库…", udb.rebuild, "按清单重新构建")

    def _run_busy(
        self,
        text: str,
        work: Callable[[], UserDbResult],
        status: str,
    ) -> None:
        """在工作线程里跑 *work*，结束后回到 GUI 线程刷新视图。

        用户可能一次导入几百份 CIF（每相 10–30 ms ⇒ 数秒），同步跑会让对话框
        假死并诱发重复点击 —— 所以按钮路径一律走忙碌对话框；``add_paths`` 等
        同步 API 留给测试与脚本。
        """
        def _on_success(result: UserDbResult) -> None:
            self._after_change(result)
            logger.info("用户库已更新（%s）：%d 相", status, result.total)

        def _on_error(message: str) -> None:
            QtWidgets.QMessageBox.warning(self, "用户数据库操作失败", message)

        run_with_busy(
            self,
            "用户数据库",
            text,
            work,
            on_success=_on_success,
            on_error=_on_error,
        )

    def _open_library_dir(self) -> None:
        """在系统文件管理器里打开用户库所在目录（不存在则先创建）。"""
        directory = udb.user_library_path().parent
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QtWidgets.QMessageBox.warning(self, "无法打开目录", str(exc))
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(directory)))
