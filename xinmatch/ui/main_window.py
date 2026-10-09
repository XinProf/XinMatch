"""Main application window skeleton.

T13.1 — Main window skeleton (menu / toolbar / status bar / dock panels).

Layout follows Match!'s "working area" (``docs/working_area.md``):
upper-left graphics (the :class:`~xinmatch.ui.pattern_view.PatternView`,
central widget), candidate list dock at the bottom, tabbed
restraints / peak-list / data-sheet dock upper-right, and the match list
dock lower-right.  A menu bar on top, a toolbar below it and a status bar
at the bottom mirror ``docs/working_area.md`` and ``docs/function_keys.md``.

Every one of the 15 functional modules in ``FUNCTION_MAP.md`` has exactly
one placeholder QAction here; the action merely announces itself in the
status bar until the real workflow dialogs land in T13.3+.  Icons are
Qt built-in standard pixmaps only — no Match! icons or visual assets are
reused.
"""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from xinmatch.core.model.pattern import Pattern
from xinmatch.core.model.phase import Phase
from xinmatch.core.refine.cif_store import export_cifs, match_entry_cifs
from xinmatch.core.search.fom import CandidateResult
from xinmatch.ui.about_dialog import AboutDialog
from xinmatch.ui.dialogs.colors_dialog import ColorsDialog
from xinmatch.ui.dialogs.config import load_config, save_config
from xinmatch.ui.dialogs.options_dialog import OptionsDialog
from xinmatch.ui.pattern_view import PatternView
from xinmatch.ui.periodic_table import PeriodicTableWidget
from xinmatch.ui.refinement_wizard import RefinementWizard
from xinmatch.ui.shortcuts import install_shortcuts
from xinmatch.ui.structure_view import (
    StructureViewDialog,
    resolve_entry_cif,
)
from xinmatch.ui.tables import CandidateListTable, MatchListTable, PeakListTable
from xinmatch.ui.theme import apply_theme, current_theme


def _asset_path(name: str) -> Path:
    """Resolve a top-level ``assets/`` file (logo.png / splash.png)."""
    return Path(__file__).resolve().parents[2] / "assets" / name

# 15 functional modules (FUNCTION_MAP.md sections 1–15).
# (module id, label, Match! help anchor this module maps to)
MODULES: tuple[tuple[str, str, str], ...] = (
    ("data_import", "数据导入", "import_diffraction-data"),
    ("data_export", "数据导出", "export"),
    ("raw_processing", "原始数据处理", "rawdata-proc"),
    ("peak_list", "寻峰与峰列表", "peaklist_basics"),
    ("profile_fitting", "Profile Fitting", "profilefitting"),
    ("search_match", "Search-Match", "searchmatch"),
    ("restraints", "限制条件检索", "restraints"),
    ("reference_db", "参考数据库", "reference_pattern_database"),
    ("user_db", "用户数据库", "userdatabase"),
    ("indexing", "指标化", "indexing"),
    ("rietveld", "Rietveld与LeBail", "Rietveld"),
    ("quant_analysis", "定量分析", "quant_analysis_RIR"),
    ("microstructure", "微结构分析", "crystallite_size"),
    ("report_print", "报告与打印", "report_basics"),
    ("options", "选项与设置", "options"),
)

# Menu grouping: (menu title, module ids in display order).
MENU_LAYOUT: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("文件(&F)", ("data_import", "data_export")),
    ("图谱(&P)", ("raw_processing", "peak_list", "profile_fitting")),
    ("分析(&A)", ("search_match", "restraints", "quant_analysis", "microstructure")),
    ("数据库(&D)", ("reference_db", "user_db")),
    ("计算(&C)", ("indexing", "rietveld")),
    ("报告(&R)", ("report_print",)),
    ("设置(&O)", ("options",)),
)

# Subset of modules exposed on the main toolbar as quick buttons.
TOOLBAR_MODULES: tuple[str, ...] = (
    "data_import", "data_export", "raw_processing", "peak_list",
    "profile_fitting", "search_match", "restraints", "indexing",
    "rietveld", "quant_analysis", "report_print", "options",
)

# Qt built-in standard pixmap names per module (safe fallback if missing).
_TOOLBAR_ICONS: dict[str, str] = {
    "data_import": "SP_DialogOpenButton",
    "data_export": "SP_DialogSaveButton",
    "raw_processing": "SP_FileDialogDetailedView",
    "peak_list": "SP_FileDialogListView",
    "profile_fitting": "SP_MediaPlay",
    "search_match": "SP_BrowserReload",
    "restraints": "SP_FileDialogContentsView",
    "reference_db": "SP_DirHomeIcon",
    "user_db": "SP_FileDialogNewFolder",
    "indexing": "SP_ArrowRight",
    "rietveld": "SP_MediaSeekForward",
    "quant_analysis": "SP_FileDialogInfoView",
    "microstructure": "SP_FileDialogDetailedView",
    "report_print": "SP_FileDialogPrintPreview",
    "options": "SP_FileDialogDetailedView",
}


class MainWindow(QtWidgets.QMainWindow):
    """Top-level application window; see module docstring for layout."""

    def __init__(self, parent=None) -> None:
        """Build actions, menus, toolbar, status bar, central view and docks."""
        super().__init__(parent)
        self.setWindowTitle("XinMatch")
        self.resize(1280, 800)

        # Application icon (original assets/logo.png; absent -> Qt default icon).
        logo = _asset_path("logo.png")
        if logo.is_file():
            self.setWindowIcon(QtGui.QIcon(str(logo)))

        # State fed by the controller layer: current experimental pattern and
        # the latest search-match candidate list.
        self._current_pattern: Pattern | None = None
        self._candidates: list[CandidateResult] = []
        self._last_outcome = None

        self.module_actions: dict[str, QtGui.QAction] = {}

        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._build_statusbar()
        self._build_central()
        self._build_docks()
        self._install_shortcuts()
        # T13.7：默认浅色主题（窗口级 palette + QSS，可被切换）。
        apply_theme(self, "light")
        self._theme_action.setText(f"切换主题（当前：{current_theme()}）")

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    def _build_actions(self) -> None:
        """Create one placeholder QAction per functional module."""
        style = self.style()
        for mod_id, label, anchor in MODULES:
            action = QtGui.QAction(label, self)
            pix = getattr(
                QtWidgets.QStyle, _TOOLBAR_ICONS.get(mod_id, ""), None
            )
            if pix is not None:
                action.setIcon(style.standardIcon(pix))
            action.setStatusTip(f"{label}（Match!: {anchor}）— 占位动作")
            if mod_id == "options":
                # T13.5 集成：选项模块动作直接打开选项设置对话框（持久化）。
                action.triggered.connect(self._open_options_dialog)
            else:
                action.triggered.connect(
                    lambda _checked=False, lbl=label: self._placeholder(lbl)
                )
            self.module_actions[mod_id] = action

    def _build_menus(self) -> None:
        """Assemble the menu bar from :data:`MENU_LAYOUT`."""
        menus: dict[str, QtWidgets.QMenu] = {}
        for title, ids in MENU_LAYOUT:
            menu = menus[title] = self.menuBar().addMenu(title)
            for mod_id in ids:
                menu.addAction(self.module_actions[mod_id])
        exit_action = QtGui.QAction("退出(&Q)", self)
        exit_action.setShortcut(QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Quit))
        exit_action.triggered.connect(self.close)
        menus["文件(&F)"].addSeparator()
        menus["文件(&F)"].addAction(exit_action)

        # T13.5 / T13.7 集成：颜色线型设置与主题切换入口（设置菜单）。
        colors_action = QtGui.QAction("颜色与线型设置…", self)
        colors_action.triggered.connect(self._open_colors_dialog)
        menus["设置(&O)"].addSeparator()
        menus["设置(&O)"].addAction(colors_action)
        self._theme_action = QtGui.QAction("切换主题（当前：浅色）", self)
        self._theme_action.triggered.connect(self._toggle_theme)
        menus["设置(&O)"].addAction(self._theme_action)
        menus["设置(&O)"].addSeparator()
        about_action = QtGui.QAction("关于 XinMatch…", self)
        about_action.triggered.connect(self._open_about)
        menus["设置(&O)"].addAction(about_action)
        self.about_action = about_action

        # T13.8 / Phase 16：精修菜单（精修向导 + 3D 结构视图）。
        refine_menu = self.menuBar().addMenu("精修(&E)")
        self.refinement_wizard_action = QtGui.QAction("打开精修向导…", self)
        self.refinement_wizard_action.setShortcut("Ctrl+Shift+W")
        self.refinement_wizard_action.setStatusTip(
            "打开 Rietveld 精修向导（GSAS-II 后端）"
        )
        self.refinement_wizard_action.triggered.connect(
            self._open_refinement_wizard
        )
        refine_menu.addAction(self.refinement_wizard_action)
        self.export_cifs_action = QtGui.QAction("导出所选相 CIF…", self)
        self.export_cifs_action.setStatusTip(
            "从 COD 归档匹配并导出所选候选相的 CIF（供 GSAS-II 等工作目录调用）"
        )
        self.export_cifs_action.triggered.connect(self._export_selected_cifs)
        refine_menu.addAction(self.export_cifs_action)
        refine_menu.addSeparator()
        self.structure_view_action = QtGui.QAction("3D 结构视图…", self)
        self.structure_view_action.setShortcut("Ctrl+Shift+V")
        self.structure_view_action.setStatusTip("以 3Dmol.js 显示当前选定相的晶体结构")
        self.structure_view_action.triggered.connect(self._open_structure_view)
        refine_menu.addAction(self.structure_view_action)

    def _build_toolbar(self) -> None:
        """Main toolbar with the most frequent module quick actions."""
        toolbar = self.addToolBar("主工具栏")
        toolbar.setObjectName("mainToolbar")
        toolbar.setMovable(False)
        for mod_id in TOOLBAR_MODULES:
            toolbar.addAction(self.module_actions[mod_id])

    def _build_statusbar(self) -> None:
        """Status bar: transient module messages + permanent cursor readout."""
        self.statusBar().showMessage("就绪")
        self._cursor_label = QtWidgets.QLabel("2θ=—   I=—   d=—")
        self.statusBar().addPermanentWidget(self._cursor_label)

    def _build_central(self) -> None:
        """Central widget: the diffraction pattern graphics panel."""
        self.pattern_view = PatternView(self)
        self.setCentralWidget(self.pattern_view)
        self.pattern_view.cursor_moved.connect(self._cursor_label.setText)

    def _build_docks(self) -> None:
        """Dock panels mirroring the Match! working area."""
        # Bottom: candidate list (working_area.md).  T13.3 候选列表表格挂载。
        self.candidate_table = CandidateListTable()
        cand = QtWidgets.QDockWidget("候选列表 Candidate List", self)
        cand.setObjectName("candidateDock")
        cand.setWidget(self.candidate_table)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, cand)

        # Upper-right: tabbed restraints / peak list / data sheet.  T13.4 周期表
        # 进"限制条件"页，T13.3 峰列表进"峰列表"页；数据表留占位。
        self.periodic_table = PeriodicTableWidget()
        self.peak_table = PeakListTable()
        tabs = QtWidgets.QTabWidget()
        tabs.addTab(self.periodic_table, "限制条件")
        tabs.addTab(self.peak_table, "峰列表")
        tabs.addTab(QtWidgets.QWidget(), "数据表")
        right = QtWidgets.QDockWidget("检索与数据", self)
        right.setObjectName("rightDock")
        right.setWidget(tabs)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, right)

        # Lower-right: match list, tabified with the right dock.  T13.3 匹配表挂载。
        self.match_table = MatchListTable()
        match = QtWidgets.QDockWidget("匹配物相 Match List", self)
        match.setObjectName("matchDock")
        match.setWidget(self.match_table)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, match)
        self.tabifyDockWidget(right, match)

    # ------------------------------------------------------------------
    # T13.5 / T13.6 / T13.7 integration
    # ------------------------------------------------------------------
    def _install_shortcuts(self) -> None:
        """Register the full Match!-style shortcut map (T13.6)."""
        self.shortcuts = install_shortcuts(self)

    def _open_options_dialog(self) -> None:
        """T13.5 — options settings dialog with config persistence."""
        dialog = OptionsDialog(load_config(), self)
        if dialog.exec():
            save_config(dialog.values())

    def _open_colors_dialog(self) -> None:
        """T13.5 — colors & linestyles dialog with config persistence."""
        config = load_config()
        dialog = ColorsDialog(config.get("colors", {}), self)
        if dialog.exec():
            config["colors"] = dialog.values()
            save_config(config)

    def _toggle_theme(self) -> None:
        """T13.7 — switch light/dark theme on the main window."""
        target = "dark" if current_theme() == "light" else "light"
        apply_theme(self, target)
        self._theme_action.setText(f"切换主题（当前：{current_theme()}）")

    # ------------------------------------------------------------------
    # T13.8 / Phase 16 integration: state feeding + refinement wizard / 3D view
    # ------------------------------------------------------------------
    def set_pattern(self, pattern: Pattern) -> None:
        """Store the current experimental pattern and plot it centrally."""
        self._current_pattern = pattern
        self.pattern_view.add_pattern(pattern, name="实验谱")

    def set_candidates(self, results: list[CandidateResult]) -> None:
        """Store the latest search-match results and fill the candidate dock."""
        self._candidates = list(results)
        self.candidate_table.set_candidates(self._candidates)

    def _selected_candidate_results(self) -> list[CandidateResult]:
        """Candidate rows selected in the dock; fall back to all candidates."""
        idxs = self.candidate_table.selectionModel().selectedRows()
        if not idxs:
            return list(self._candidates)
        proxy = self.candidate_table.model()
        selected: list[CandidateResult] = []
        for idx in idxs:
            row = proxy.mapToSource(idx).row()
            if 0 <= row < len(self._candidates):
                selected.append(self._candidates[row])
        return selected or list(self._candidates)

    def _open_refinement_wizard(self) -> None:
        """T13.8 — open the Rietveld refinement wizard for current phases."""
        candidates = self._selected_candidate_results()
        if not candidates:
            QtWidgets.QMessageBox.information(
                self,
                "无已鉴定相",
                "当前没有候选物相。\n请先运行 Search-Match，并在候选列表中选择要精修的相。",
            )
            return
        if self._current_pattern is None:
            QtWidgets.QMessageBox.information(
                self,
                "无实验衍射谱",
                "尚未载入实验衍射谱。\n请先导入衍射数据，再打开精修向导。",
            )
            return

        phases: list[Phase] = []
        cif_paths: dict[str, str] = {}
        for cand in candidates:
            entry_id = cand.entry.entry_id
            cif = resolve_entry_cif(entry_id)
            if cif is None:
                continue
            phases.append(Phase(entry=cand.entry))
            cif_paths[entry_id] = str(cif)

        if not phases:
            QtWidgets.QMessageBox.information(
                self,
                "找不到 CIF",
                "选中相在本地 COD 归档中没有对应的 CIF 文件，无法运行 Rietveld 精修。",
            )
            return

        wizard = RefinementWizard(
            phases, cif_paths, self._current_pattern, parent=self
        )
        wizard.refinement_finished.connect(self._on_refinement_finished)
        wizard.exec()

    def _on_refinement_finished(self, outcome) -> None:
        """Remember the last refinement result for downstream views."""
        self._last_outcome = outcome
        rwp = getattr(outcome.r_factors, "rwp", None)
        msg = "精修完成。" if rwp is None else f"精修完成（Rwp = {rwp * 100:.2f}%）。"
        self.statusBar().showMessage(msg, 8000)

    def _open_structure_view(self) -> None:
        """Phase 16 — open the 3D viewer for the currently selected phase."""
        candidates = self._selected_candidate_results()
        if not candidates:
            QtWidgets.QMessageBox.information(
                self,
                "无已鉴定相",
                "当前没有候选物相。\n请先运行 Search-Match，并在候选列表中选择一个相查看其晶体结构。",
            )
            return
        entry_id = candidates[0].entry.entry_id
        dialog = StructureViewDialog(self)
        dialog.load_entry(entry_id)  # friendly empty page if CIF missing
        dialog.setWindowTitle(f"3D 结构视图 — {entry_id}")
        dialog.exec()

    def _export_selected_cifs(self) -> None:
        """Export matched COD CIFs of the selected candidates to a folder.

        Match! equivalent: ``docs/export_entry_data.md`` (exporting entry
        data).  The exported CIFs live in the user's chosen directory and
        are what a GSAS-II working folder would consume — the COD archive
        itself is never written to.
        """
        candidates = self._selected_candidate_results()
        if not candidates:
            QtWidgets.QMessageBox.information(
                self,
                "无已鉴定相",
                "当前没有候选物相。\n请先运行 Search-Match，并选择要导出 CIF 的相。",
            )
            return
        entry_ids = [cand.entry.entry_id for cand in candidates]
        matched = match_entry_cifs(entry_ids)
        if not matched:
            QtWidgets.QMessageBox.information(
                self,
                "找不到 CIF",
                "所选相在本地 COD 归档中没有对应的 CIF 文件，无法导出。",
            )
            return
        missing = [eid for eid in entry_ids if eid not in matched]
        out_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self, "选择导出目录（所选相 CIF）"
        )
        if not out_dir:
            return
        exported = export_cifs(matched, out_dir)
        note = ""
        if missing:
            note = "\n\n以下相无 CIF（已跳过）：" + "、".join(missing)
        QtWidgets.QMessageBox.information(
            self,
            "导出完成",
            f"已导出 {len(exported)} 个 CIF 到：\n{Path(out_dir)}\n"
            + "\n".join(f"• {name}" for name in exported)
            + note,
        )

    def _open_about(self) -> None:
        """Show the About box; version read dynamically from xinmatch.__version__."""
        AboutDialog(self).exec()

    # ------------------------------------------------------------------
    # Placeholder handler
    # ------------------------------------------------------------------
    def _placeholder(self, label: str) -> None:
        """Announce a not-yet-implemented module in the status bar."""
        self.statusBar().showMessage(
            f"[{label}] 模块骨架已就位，具体工作流在后续任务中实现", 5000
        )
