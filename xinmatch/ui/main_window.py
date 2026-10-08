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

from PySide6 import QtCore, QtGui, QtWidgets

from xinmatch.ui.pattern_view import PatternView

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

        self.module_actions: dict[str, QtGui.QAction] = {}

        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._build_statusbar()
        self._build_central()
        self._build_docks()

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
        # Bottom: candidate list (working_area.md).
        cand = QtWidgets.QDockWidget("候选列表 Candidate List", self)
        cand.setObjectName("candidateDock")
        cand.setWidget(QtWidgets.QWidget())
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, cand)

        # Upper-right: tabbed restraints / peak list / data sheet.
        tabs = QtWidgets.QTabWidget()
        tabs.addTab(QtWidgets.QWidget(), "限制条件")
        tabs.addTab(QtWidgets.QWidget(), "峰列表")
        tabs.addTab(QtWidgets.QWidget(), "数据表")
        right = QtWidgets.QDockWidget("检索与数据", self)
        right.setObjectName("rightDock")
        right.setWidget(tabs)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, right)

        # Lower-right: match list, tabified with the right dock.
        match = QtWidgets.QDockWidget("匹配物相 Match List", self)
        match.setObjectName("matchDock")
        match.setWidget(QtWidgets.QWidget())
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, match)
        self.tabifyDockWidget(right, match)

    # ------------------------------------------------------------------
    # Placeholder handler
    # ------------------------------------------------------------------
    def _placeholder(self, label: str) -> None:
        """Announce a not-yet-implemented module in the status bar."""
        self.statusBar().showMessage(
            f"[{label}] 模块骨架已就位，具体工作流在后续任务中实现", 5000
        )
