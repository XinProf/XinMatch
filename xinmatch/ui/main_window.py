"""Main application window skeleton.

T13.1 — Main window skeleton (menu / toolbar / status bar / dock panels).

Layout follows the reference software's "working area" (``docs/working_area.md``):
upper-left graphics (the :class:`~xinmatch.ui.pattern_view.PatternView`,
central widget), candidate list dock at the bottom, tabbed
restraints / peak-list / data-sheet dock upper-right, and the match list
dock lower-right.  A menu bar on top, a toolbar below it and a status bar
at the bottom mirror ``docs/working_area.md`` and ``docs/function_keys.md``.

Every one of the 15 functional modules in ``FUNCTION_MAP.md`` has exactly
one placeholder QAction here; the action merely announces itself in the
status bar until the real workflow dialogs land in T13.3+.  Icons are
Qt built-in standard pixmaps only — no reference-software icons or visual assets are
reused.
"""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from xinmatch.core.db.multi_db import (
    LibraryNotAvailableError,
    open_library,
    resolve_default,
)
from xinmatch.core.io import load_pattern
from xinmatch.core.model import Entry
from xinmatch.core.model.pattern import Pattern
from xinmatch.core.model.phase import Phase
from xinmatch.core.peak.peak_search import find_peaks
from xinmatch.core.refine.cif_store import export_cifs, match_entry_cifs
from xinmatch.core.report.render import render_text
from xinmatch.core.report.report_model import (
    CandidateEntry,
    CandidateListSection,
    PeakListSection,
    Report,
    SampleInfo,
)
from xinmatch.core.search.fom import CandidateResult
from xinmatch.core.search.fpfm import search_match_fpfm
from xinmatch.core.search.search_match import search_match
from xinmatch.ui.about_dialog import AboutDialog
from xinmatch.ui.busy import run_with_busy
from xinmatch.ui.dialogs.colors_dialog import ColorsDialog
from xinmatch.ui.dialogs.config import load_config, save_config
from xinmatch.ui.dialogs.library_dialog import LibraryDialog
from xinmatch.ui.dialogs.options_dialog import OptionsDialog
from xinmatch.ui.pattern_view import PatternPanel
from xinmatch.ui.periodic_table import PeriodicTablePanel
from xinmatch.ui.refinement_wizard import RefinementWizard
from xinmatch.ui.shortcuts import install_shortcuts
from xinmatch.ui.structure_view import (
    StructureViewDialog,
    resolve_entry_cif,
)
from xinmatch.ui.tables import CandidateListTable, MatchListTable, PeakListTable
from xinmatch.ui.theme import apply_theme, current_theme

# 主题图标（并行任务交付；缺失时回退到 Qt 标准 pixmap）。
try:  # pragma: no cover - 取决于并行任务产物是否落地
    from xinmatch.ui.icons import icon as _themed_icon
except ImportError:  # pragma: no cover
    _themed_icon = None  # type: ignore[assignment]

# PDF-2 源目录注入（并行任务交付；缺失时静默跳过）。
try:  # pragma: no cover
    from xinmatch.core.db.multi_db import library_by_id, set_pdf2_source_dir
except ImportError:  # pragma: no cover
    library_by_id = None  # type: ignore[assignment]
    set_pdf2_source_dir = None  # type: ignore[assignment]


def _asset_path(name: str) -> Path:
    """Resolve a top-level ``assets/`` file (logo.png / splash.png)."""
    return Path(__file__).resolve().parents[2] / "assets" / name

# 15 functional modules (FUNCTION_MAP.md sections 1–15).
# (module id, label, the reference software help anchor this module maps to)
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

# ---------------------------------------------------------------------------
# 统一检索入口：检索模式（峰列表 FoM / FPFM 全谱拟合）
# ---------------------------------------------------------------------------
SEARCH_MODE_PEAKS_FOM = "peaks_fom"
SEARCH_MODE_FPFM_FULL = "fpfm_full"

# 模式下拉框选项：(显示文本, 内部常量)。
_SEARCH_MODE_ITEMS: tuple[tuple[str, str], ...] = (
    ("峰列表 FoM（寻峰）", SEARCH_MODE_PEAKS_FOM),
    ("FPFM 全谱拟合（不寻峰）", SEARCH_MODE_FPFM_FULL),
)


# 工具栏悬停详细说明（v1.3.1）：比单行状态栏提示更完整的"是什么+怎么用"。
_MODULE_TIPS: dict[str, str] = {
    "data_import": "数据导入：打开衍射数据文件，22 种厂商/自由格式自动识别。\n"
    "用法：文件→打开数据…（Ctrl+O）与此等效。",
    "data_export": "数据导出：把当前谱图 / 峰列表导出为 ASCII profile、峰表等格式。",
    "raw_processing": "原始数据处理：背景扣除、平滑、Kα2 剥离、零点校正等预处理流水线入口。",
    "peak_list": "寻峰与峰列表：自动寻峰并维护可编辑峰列表；峰位/强度供检索与报告使用。",
    "profile_fitting": "Profile Fitting：多峰同时最小二乘拟合，输出精确峰位 / FWHM / 面积。",
    "search_match": "Search-Match 物相检索：按工具栏右侧下拉框所选模式执行——\n"
    "峰列表 FoM（先寻峰再匹配）或 FPFM 全谱拟合（不寻峰）。\n"
    "检索前请先打开数据并挂载参考数据库（设置→参考数据库…）。",
    "restraints": "限制条件检索：按元素三态（必含/排除/可选）、晶系等条件过滤候选。\n"
    "元素选择在右侧「检索与数据」坞的「限制条件」页。",
    "reference_db": "参考数据库：挂载 / 切换参考库（COD 无机库、全库、优选库…）。",
    "user_db": "用户数据库：管理自建参考条目（导入 CIF / 导出）。",
    "indexing": "指标化：Treor / Dicvol 晶胞指标化，由峰列表求初始晶胞。",
    "rietveld": "Rietveld 与 Le Bail 精修（计算委托 GSAS-II，XinMatch 不自研精修算法）。",
    "quant_analysis": "定量分析：RIR / 内标法 / Rietveld 定量的物相质量分数。",
    "microstructure": "微结构分析：Scherrer 晶粒尺寸、Williamson-Hall 微观应变。",
    "report_print": "报告与打印：把当前峰列表 + 候选列表渲染为 HTML / 文本报告并预览。",
    "options": "选项与设置：检索、显示、颜色线型等全部设置入口（YAML 持久化）。",
}


def fpfm_results_to_candidates(
    fpfm_results: list[tuple[Entry, dict[str, str | float]]],
) -> list[CandidateResult]:
    """把 FPFM 的 ``(Entry, score_dict)`` 结果转换为 GUI 候选行。

    FPFM 不产出峰相关量（未寻峰、无峰位/强度 P 值、无关联峰对），因此
    ``pairs`` 留空、``i_scale`` 取默认值；剖面拟合质量量（Rwp / Rexp /
    GOF）放进 ``p_values`` 供候选表与下游链路读取。候选表的 P(2θ) /
    P(I/I₀) 两列在 FPFM 模式下自然显示占位符（—），属预期行为。
    """
    out: list[CandidateResult] = []
    for entry, score in fpfm_results:
        out.append(
            CandidateResult(
                entry=entry,
                fom=float(score["fom"]),
                p_values={
                    "rwp": float(score["rwp"]),
                    "rexp": float(score["rexp"]),
                    "gof": float(score["gof"]),
                },
            )
        )
    return out


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
        # Multi-DB mount: registry id of the library last opened for search.
        self._active_library_id: str | None = None
        # 当前已打开数据文件的显示名（文件名），用于状态栏 / 报告。
        self._current_filename: str = ""
        # 统一检索入口模式：默认峰列表 FoM（寻峰）；可在工具栏下拉框切换。
        self._search_mode: str = SEARCH_MODE_PEAKS_FOM

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
        # 图标动作注册表：action → 图标名/模块 id，供主题切换时重着色。
        self._icon_actions: dict[QtGui.QAction, str] = {}
        for mod_id, label, anchor in MODULES:
            action = QtGui.QAction(label, self)
            # 主题图标优先；缺失时回退到 Qt 标准 pixmap。
            themed = _themed_icon(mod_id) if _themed_icon is not None else None
            if themed is not None:
                action.setIcon(themed)
                self._icon_actions[action] = mod_id
            else:
                pix = getattr(
                    QtWidgets.QStyle, _TOOLBAR_ICONS.get(mod_id, ""), None
                )
                if pix is not None:
                    action.setIcon(style.standardIcon(pix))
            action.setStatusTip(f"{label}（参考软件锚点：{anchor}）")
            tip = _MODULE_TIPS.get(mod_id)
            if tip:
                action.setToolTip(tip)
            if mod_id == "options":
                # T13.5 集成：选项模块动作直接打开选项设置对话框（持久化）。
                action.triggered.connect(self._open_options_dialog)
            elif mod_id == "reference_db":
                # 多库挂载：参考数据库模块动作打开库选择对话框（持久化）。
                action.triggered.connect(self._open_library_dialog)
            elif mod_id == "search_match":
                # Search-Match 真实接线：寻峰 → 检索 → 候选列表 / 峰列表。
                action.triggered.connect(self._run_search_match)
            elif mod_id == "report_print":
                # 报告预览：基于当前候选与峰列表渲染文本报告。
                action.triggered.connect(self._run_report_preview)
            else:
                action.triggered.connect(
                    lambda _checked=False, lbl=label: self._placeholder(lbl)
                )
            self.module_actions[mod_id] = action

        # 文件→打开数据（Ctrl+O）：真实导入动作，放在文件菜单顶部。
        self.open_action = QtGui.QAction("打开数据…", self)
        self.open_action.setShortcut(QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Open))
        self.open_action.setStatusTip(
            "打开衍射数据文件（自动识别格式：两列 ASCII / Bruker / Panalytical …）"
        )
        self.open_action.setToolTip(
            "打开衍射数据文件（Ctrl+O）。\n"
            "22 种厂商/自由格式自动识别；打开后谱图区自动适配数据显示范围。"
        )
        open_icon = _themed_icon("open") if _themed_icon is not None else None
        if open_icon is not None:
            self.open_action.setIcon(open_icon)
            self._icon_actions[self.open_action] = "open"
        else:
            self.open_action.setIcon(
                style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogOpenButton)
            )
        self.open_action.triggered.connect(self._open_data_file)

        # ---- 工具栏补充动作（参考同类 XRD 软件工具栏布局；占位/已有接线）----
        self.background_action = self._tool_action(
            "背景扣除", "background",
            lambda _checked=False: self._placeholder("背景扣除"),
            "扣除谱图背景（预处理功能，待接线）",
        )
        self.smooth_action = self._tool_action(
            "平滑", "smooth",
            lambda _checked=False: self._placeholder("平滑"),
            "谱图平滑（预处理功能，待接线）",
        )
        self.ko2_action = self._tool_action(
            "Kα2 剥离", "ko2",
            lambda _checked=False: self._placeholder("Kα2 剥离"),
            "剥离 Kα2 分量（预处理功能，待接线）",
        )
        self.reset_action = self._tool_action(
            "重置", "reset",
            lambda _checked=False: self._placeholder("重置为原始数据"),
            "重置为打开时的原始谱图（撤销全部预处理；待接线）",
        )
        self.peakdetect_action = self._tool_action(
            "峰检测", "peakdetect",
            lambda _checked=False: self._placeholder("峰检测"),
            "自动峰检测（待接线）",
        )
        self.codsearch_action = self._tool_action(
            "COD 搜索", "codsearch",
            lambda _checked=False: self._open_library_dialog(),
            "选择 COD 参考数据库进行检索",
        )

    def _tool_action(
        self,
        label: str,
        icon_name: str,
        slot,
        tip: str,
    ) -> QtGui.QAction:
        """Build a toolbar action with an original SVG icon and status tip."""
        action = QtGui.QAction(label, self)
        action.setStatusTip(tip)
        action.setToolTip(tip)
        if _themed_icon is not None:
            action.setIcon(_themed_icon(icon_name))
            self._icon_actions[action] = icon_name
        action.triggered.connect(slot)
        return action

    def _build_menus(self) -> None:
        """Assemble the menu bar from :data:`MENU_LAYOUT`."""
        menus: dict[str, QtWidgets.QMenu] = {}
        for title, ids in MENU_LAYOUT:
            menu = menus[title] = self.menuBar().addMenu(title)
            for mod_id in ids:
                menu.addAction(self.module_actions[mod_id])
        # 文件菜单顶部插入"打开数据…"（位于"数据导入"模块动作之上）。
        file_menu = menus["文件(&F)"]
        file_menu.insertAction(self.module_actions["data_import"], self.open_action)
        file_menu.insertSeparator(self.module_actions["data_import"])
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
        # 多库挂载：参考数据库选择/切换入口（设置菜单）。
        self.library_action = QtGui.QAction("参考数据库…", self)
        self.library_action.setStatusTip(
            "选择 / 切换 Search-Match 使用的参考数据库"
        )
        self.library_action.triggered.connect(self._open_library_dialog)
        menus["设置(&O)"].addAction(self.library_action)
        self._theme_action = QtGui.QAction("切换主题（当前：浅色）", self)
        self._theme_action.triggered.connect(self._toggle_theme)
        menus["设置(&O)"].addAction(self._theme_action)

        # T13.8 / Phase 16：精修菜单（精修向导 + 3D 结构视图）。
        refine_menu = self.menuBar().addMenu("精修(&E)")
        self.refinement_wizard_action = QtGui.QAction("打开精修向导…", self)
        self.refinement_wizard_action.setShortcut("Ctrl+Shift+W")
        self.refinement_wizard_action.setStatusTip(
            "打开 Rietveld 精修向导（GSAS-II 后端）"
        )
        self.refinement_wizard_action.setToolTip(
            "Rietveld 精修向导（Ctrl+Shift+W，GSAS-II 后端）。\n"
            "四步：选已鉴定相 → 背景处理 → 勾选参数组（Scale/Cell/Profile/Atoms）"
            " → 运行并查看 R 因子与残差谱。"
        )
        if _themed_icon is not None:
            self.refinement_wizard_action.setIcon(_themed_icon("wizard"))
            self._icon_actions[self.refinement_wizard_action] = "wizard"
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

        # 帮助菜单：关于 XinMatch…（独立顶级菜单，不放在设置里）。
        help_menu = self.menuBar().addMenu("帮助(&H)")
        about_action = QtGui.QAction("关于 XinMatch…", self)
        about_action.setStatusTip("查看版本、联系方式与版权信息")
        if _themed_icon is not None:
            about_action.setIcon(_themed_icon("help"))
            self._icon_actions[about_action] = "help"
        about_action.triggered.connect(self._open_about)
        help_menu.addAction(about_action)
        self.about_action = about_action

    def _build_toolbar(self) -> None:
        """Main toolbar mirroring the common XRD-software action layout.

        分组顺序参考同类 XRD 数据分析软件：打开 / 保存导出 / 预处理
        （背景扣除·平滑·Kα2 剥离·重置）/ 峰检测 / Search-Match ·
        Profile Fitting / Rietveld·精修向导 / COD 搜索 / 报告·设置。
        """
        toolbar = self.addToolBar("主工具栏")
        toolbar.setObjectName("mainToolbar")
        toolbar.setMovable(False)
        # 图标按 24×24 设计（并在 16/20/32/48 各预渲染一份，见 ui/icons.py），
        # 显式固定工具按钮尺寸，避免随平台样式缩到 16 px 导致细节糊化。
        toolbar.setIconSize(QtCore.QSize(24, 24))
        # v1.3.1：图标右侧带简洁文字 + 悬停详细说明（用户可读性优先）。
        # 空间不足时 QToolBar 自带 « 溢出折叠，不会截断。
        toolbar.setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        toolbar.addAction(self.open_action)
        toolbar.addAction(self.module_actions["data_export"])
        toolbar.addSeparator()
        toolbar.addAction(self.background_action)
        toolbar.addAction(self.smooth_action)
        toolbar.addAction(self.ko2_action)
        toolbar.addAction(self.reset_action)
        toolbar.addAction(self.peakdetect_action)
        toolbar.addSeparator()
        toolbar.addAction(self.module_actions["search_match"])
        # 检索模式切换下拉框：峰列表 FoM（寻峰）/ FPFM 全谱拟合（不寻峰）。
        # 切换只更新内部状态，不自动触发检索；下次点击 Search-Match 执行新模式。
        self._search_mode_combo = QtWidgets.QComboBox()
        for text, mode in _SEARCH_MODE_ITEMS:
            self._search_mode_combo.addItem(text, userData=mode)
        self._refresh_search_mode_combo_tip()
        self._search_mode_combo.currentIndexChanged.connect(
            self._on_search_mode_combo_changed
        )
        toolbar.addWidget(self._search_mode_combo)
        toolbar.addAction(self.module_actions["profile_fitting"])
        toolbar.addSeparator()
        toolbar.addAction(self.module_actions["rietveld"])
        toolbar.addAction(self.refinement_wizard_action)
        toolbar.addSeparator()
        toolbar.addAction(self.codsearch_action)
        toolbar.addSeparator()
        toolbar.addAction(self.module_actions["report_print"])
        toolbar.addAction(self.module_actions["options"])

    def _build_statusbar(self) -> None:
        """Status bar: transient module messages + permanent cursor readout."""
        self.statusBar().showMessage("就绪")
        self._cursor_label = QtWidgets.QLabel("2θ=—   I=—   d=—")
        self.statusBar().addPermanentWidget(self._cursor_label)

    def _build_central(self) -> None:
        """Central widget: the diffraction pattern graphics panel.

        v1.3.1：谱图区升级为 :class:`PatternPanel`（轴切换控制条 +
        pyqtgraph 视图）；``self.pattern_view`` 指向其中真正的视图，
        下游 API（add_pattern / patterns() / …）不变。
        """
        self.pattern_panel = PatternPanel()
        self.pattern_view = self.pattern_panel.view
        self.setCentralWidget(self.pattern_panel)
        self.pattern_panel.cursor_moved.connect(self._cursor_label.setText)

    def _build_docks(self) -> None:
        """Dock panels mirroring the reference software working area."""
        # Bottom: candidate list (working_area.md).  T13.3 候选列表表格挂载。
        self.candidate_table = CandidateListTable()
        cand = QtWidgets.QDockWidget("候选列表 Candidate List", self)
        cand.setObjectName("candidateDock")
        cand.setWidget(self.candidate_table)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, cand)

        # Upper-right: tabbed restraints / peak list / data sheet.  v1.3.1
        # 周期表改弹出式选择面板（省空间给谱图），T13.3 峰列表进"峰列表"页；
        # 数据表留占位。
        self.periodic_panel = PeriodicTablePanel()
        self.peak_table = PeakListTable()
        tabs = QtWidgets.QTabWidget()
        tabs.addTab(self.periodic_panel, "限制条件")
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
        """Register the full reference-software-style shortcut map (T13.6)."""
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

    def _open_library_dialog(self) -> None:
        """Multi-DB mount — pick / switch the active reference database."""
        config = load_config()
        # PDF-2 源路径配置注入（并行任务交付；函数缺失时静默跳过）。
        if set_pdf2_source_dir is not None:
            set_pdf2_source_dir(
                (config.get("pdf2_source_dir") or "").strip() or None
            )
        current = (config.get("reference_db") or {}).get("selected_library_id")
        dialog = LibraryDialog(current_id=current, parent=self)
        if dialog.exec():
            config.setdefault("reference_db", {})[
                "selected_library_id"
            ] = dialog.selected_id()
            save_config(config)

    def open_search_library(self):
        """Open the selected reference DB for search-match, with safe fallback.

        Reads ``reference_db.selected_library_id`` from the YAML config and
        opens it read-only via
        :func:`~xinmatch.core.db.multi_db.open_library`; the returned
        connection targets the XinMatch schema and can be fed straight to
        :func:`~xinmatch.core.search.search_match.search_match`.

        When the chosen library is unavailable (missing / unbuilt / corrupt)
        a warning box explains why and the default bundled library is used
        instead, so that search-match always has a working connection.  Raises
        only when *both* the selected and the default library are broken.
        """
        config = load_config()
        selected = (config.get("reference_db") or {}).get("selected_library_id")
        selected = selected or resolve_default().id
        try:
            conn = open_library(selected)
        except LibraryNotAvailableError as exc:
            default = resolve_default()
            QtWidgets.QMessageBox.warning(
                self,
                "参考数据库不可用",
                f"所选参考数据库「{selected}」不可用，已自动回退到默认库"
                f"「{default.display_name}」进行检索。\n\n原因：{exc}",
            )
            try:
                conn = open_library(default.id)
            except LibraryNotAvailableError as exc_default:
                QtWidgets.QMessageBox.critical(
                    self,
                    "无可用参考数据库",
                    f"默认参考数据库也不可用，检索无法执行。\n\n{exc_default}",
                )
                raise
            self._active_library_id = default.id
            self.statusBar().showMessage(
                f"已回退到默认参考数据库：{default.display_name}", 8000
            )
            return conn
        self._active_library_id = selected
        return conn

    def _toggle_theme(self) -> None:
        """T13.7 — switch light/dark theme on the main window."""
        target = "dark" if current_theme() == "light" else "light"
        apply_theme(self, target)
        self._theme_action.setText(f"切换主题（当前：{current_theme()}）")
        # 谱图区配色随主题切换（并行任务交付；缺失时静默跳过）。
        getattr(self.pattern_view, "apply_theme_colors", lambda: None)()
        # 工具栏图标按新主题重着色（否则深色主题下图标仍是深色线条，几乎不可见）。
        self._refresh_icons()

    def _refresh_icons(self) -> None:
        """按当前主题重着色全部注册图标（QSS 换肤不波及已烘焙的 pixmap）。"""
        if _themed_icon is None:
            return
        theme = current_theme()
        for action, name in getattr(self, "_icon_actions", {}).items():
            action.setIcon(_themed_icon(name, theme))

    # ------------------------------------------------------------------
    # T13.8 / Phase 16 integration: state feeding + refinement wizard / 3D view
    # ------------------------------------------------------------------
    def set_pattern(self, pattern: Pattern, name: str = "实验谱") -> None:
        """Store the current experimental pattern and plot it centrally."""
        self._current_pattern = pattern
        self.pattern_view.add_pattern(pattern, name=name)

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
            row = proxy.mapToSource(idx).row()  # type: ignore[attr-defined]
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

        The reference software equivalent: ``docs/export_entry_data.md`` (exporting entry
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
        exported = export_cifs(matched, out_dir)  # type: ignore[arg-type]
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
    # v1.0.0 体验修订：打开数据 / Search-Match 真实接线 / 报告预览
    # ------------------------------------------------------------------
    def _open_data_file(self) -> None:
        """文件→打开数据（Ctrl+O）：选择文件并自动嗅探格式后载入谱图。"""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "打开衍射数据文件",
            "",
            "衍射数据文件（自动识别）(*.txt *.dat *.rd *.udf *.uxd "
            "*.xrdml *.brml *.dif *.raw);;所有文件 (*)",
        )
        if not path:
            # 用户取消：不报错、不改动现有谱图。
            return
        try:
            pattern = load_pattern(path)
        except (FileNotFoundError, ValueError, NotImplementedError) as exc:
            QtWidgets.QMessageBox.warning(
                self,
                "无法打开衍射数据文件",
                f"文件：{path}\n\n原因：{exc}\n\n"
                "请确认文件存在且格式受支持（两列 ASCII / Bruker / Panalytical / "
                "Shimadzu .raw 等）。",
            )
            return
        self.pattern_view.clear()
        fname = Path(path).name
        self._current_filename = fname
        self.set_pattern(pattern, name=fname)
        n = len(pattern)
        x0 = float(pattern.two_theta[0]) if n else 0.0
        x1 = float(pattern.two_theta[-1]) if n else 0.0
        self.statusBar().showMessage(
            f"已打开 {fname}：{n} 点，2θ {x0:.2f}–{x1:.2f}°"
        )

    def _on_search_mode_combo_changed(self, _index: int) -> None:
        """检索模式下拉框切换：仅更新内部状态，不自动触发检索。"""
        mode = self._search_mode_combo.currentData()
        if mode:
            self._search_mode = mode
        self._refresh_search_mode_combo_tip()

    def _refresh_search_mode_combo_tip(self) -> None:
        """根据当前模式刷新下拉框 tooltip（说明当前所选检索模式）。"""
        if self._search_mode == SEARCH_MODE_FPFM_FULL:
            ka1, ka2 = self.fpfm_kalpha_wavelengths(self._current_pattern)
            ka_note = (
                f"Kα 双线模型：启用（{ka1:.4f} / {ka2:.4f} Å）"
                if ka2 is not None
                else f"Kα 双线模型：关闭（单线，{ka1:.4f} Å）"
            )
            detail = (
                "当前：FPFM 全谱拟合——直接对整条实验谱做剖面拟合精排，"
                f"不寻峰、不覆盖峰列表。\n{ka_note}"
                "\n（可在 设置→选项…→Search-Match 页调整）"
            )
        else:
            detail = (
                "当前：峰列表 FoM——先自动寻峰，再按峰位/强度匹配参考库。"
            )
        self._search_mode_combo.setToolTip(
            f"{detail}\n切换后不立即检索；下次点击 Search-Match 按所选模式执行。"
        )

    def _run_search_match(self) -> None:
        """统一 Search-Match 入口：按工具栏所选模式检索参考数据库。

        - ``peaks_fom``（默认）：自动寻峰 → 峰列表 FoM 检索（现状行为）；
        - ``fpfm_full``：FPFM 全谱拟合检索（直接拟合原始谱，不寻峰、不覆盖
          峰列表）。
        两模式结果统一为 :class:`CandidateResult` 列表填充候选列表，
        保证精修向导 / 3D 视图 / CIF 导出等下游链路元素类型不变。

        v1.3.1：检索在忙碌窗口 + 工作线程中执行（界面不冻结、不可重复
        触发）。
        """
        if self._current_pattern is None:
            QtWidgets.QMessageBox.information(
                self,
                "尚未打开衍射数据",
                "请先通过 文件→打开数据… 载入衍射谱，再运行 Search-Match。",
            )
            return
        pattern = self._current_pattern
        try:
            conn = self.open_search_library()
        except LibraryNotAvailableError:
            QtWidgets.QMessageBox.critical(
                self,
                "无可用参考数据库",
                "参考数据库不可用，Search-Match 无法执行。\n"
                "请在 设置→参考数据库… 中选择一个可用库后重试。",
            )
            return

        mode = self._search_mode
        mode_desc = (
            "FPFM 全谱拟合检索（逐候选剖面拟合，耗时较长）"
            if mode == SEARCH_MODE_FPFM_FULL
            else "峰列表 FoM 检索"
        )

        run_with_busy(
            self,
            "Search-Match",
            f"正在执行{mode_desc}…\n对参考数据库逐条比对/拟合，请稍候。",
            lambda: self._do_search(pattern, conn, mode),
            on_success=self._apply_search_results,
            on_error=self._show_search_error,
        )

    def _do_search(
        self,
        pattern: Pattern,
        conn,
        mode: str,
    ) -> tuple[list[CandidateResult], str, list | None]:
        """检索工作体（运行在工作线程，禁止触碰 GUI）。

        返回 ``(候选列表, 模式名, 峰列表)``；FPFM 分支峰列表为 ``None``。
        异常直接上抛，由 :func:`run_with_busy` 转交 GUI 线程提示。
        """
        peaks: list | None = None
        if mode == SEARCH_MODE_FPFM_FULL:
            results, mode_label = self._search_fpfm(pattern, conn)
        else:
            peaks = find_peaks(pattern.two_theta, pattern.intensity)
            results = search_match(peaks, conn, pattern.wavelength)
            mode_label = "峰列表 FoM"
        return results, mode_label, peaks

    def _apply_search_results(
        self, payload: tuple[list[CandidateResult], str, list | None]
    ) -> None:
        """把检索结果回填候选列表 / 峰列表并更新状态栏（GUI 线程）。"""
        results, mode_label, peaks = payload
        self.set_candidates(results)
        # FPFM 模式不寻峰：保留上一次峰列表，不覆盖 peak_table。
        if peaks is not None:
            self.peak_table.set_peaks(peaks)
        lib_label = self._active_library_id or "默认库"
        if library_by_id is not None and self._active_library_id:
            rec = library_by_id(self._active_library_id)
            if rec is not None:
                lib_label = rec.display_name
        self.statusBar().showMessage(
            f"检索完成：{len(results)} 个候选（{mode_label}，库：{lib_label}）", 8000
        )

    def _show_search_error(self, message: str) -> None:
        """检索失败提示（GUI 线程回调）。"""
        QtWidgets.QMessageBox.warning(
            self,
            "Search-Match 检索失败",
            f"检索过程中出现错误：\n\n{message}",
        )

    def fpfm_kalpha_wavelengths(
        self, pattern: Pattern | None = None
    ) -> tuple[float, float | None]:
        """解析 FPFM 的 Kα 波长设置 → ``(kalpha1, kalpha2)``。

        读 **设置→选项…→Search-Match** 页持久化的三个旋钮：

        * ``fpfm_kalpha1_angstrom`` <= 0（默认）时回退到图谱自身波长
          ``pattern.wavelength``；这也让 Co / Mo 等非 Cu 靶数据在不动设置
          的情况下自动跟随正确波长。
        * ``fpfm_kalpha2_enabled`` 为假时返回 ``kalpha2=None``（单线模型）。

        返回 ``(kalpha1, kalpha2)``；``kalpha2`` 为 ``None`` 表示单线。
        """
        cfg = load_config().get("searchmatch", {})
        ka1 = float(cfg.get("fpfm_kalpha1_angstrom", 0.0))
        if ka1 <= 0.0:
            ka1 = getattr(pattern, "wavelength", 0.0) or 1.5406
        enabled = bool(cfg.get("fpfm_kalpha2_enabled", True))
        ka2 = float(cfg.get("fpfm_kalpha2_angstrom", 1.5444)) if enabled else None
        return ka1, ka2

    def _search_fpfm(
        self, pattern: Pattern, conn
    ) -> tuple[list[CandidateResult], str]:
        """FPFM 全谱拟合分支（v1.3.1 起为纯计算：异常直接上抛）。

        直接接收原始实验谱（不寻峰、不要求预扣背景）。Kα 双线模型由
        **设置→选项…→Search-Match** 页的三个旋钮控制（v1.3.0）：

        * ``fpfm_kalpha2_enabled`` — 是否叠加 Kα2 伴线（默认开，对应真实
          实验室 Cu Kα 数据）；由 CIF 生成的合成谱应关闭，否则 Kα2 模型
          与数据失配会压低正确相排名（synth_13 ZrO₂ 单线谱曾错排 YSZ）。
        * ``fpfm_kalpha1_angstrom`` — Kα1 波长；<=0 时跟随 ``pattern.wavelength``。
        * ``fpfm_kalpha2_angstrom`` — Kα2 波长（默认 1.5444 Å）。

        返回 ``(候选列表, 模式名)``。本函数可能在工作线程中被
        :meth:`_do_search` 调用，**禁止**在此弹 QMessageBox——异常统一
        上抛，由忙碌窗口的 ``on_error`` 回调在 GUI 线程提示。
        """
        ka1, ka2 = self.fpfm_kalpha_wavelengths(pattern)
        raw = search_match_fpfm(
            pattern,
            conn,
            wavelength_kalpha1=ka1,
            wavelength_kalpha2=ka2,
        )
        mode_label = (
            f"FPFM 全谱拟合（Kα 双线 {ka1:.4f}/{ka2:.4f} Å）"
            if ka2 is not None
            else f"FPFM 全谱拟合（Kα 单线 {ka1:.4f} Å）"
        )
        return fpfm_results_to_candidates(raw), mode_label

    def _run_report_preview(self) -> None:
        """报告与打印：渲染当前候选 + 峰列表为文本报告并弹出只读预览。"""
        if not self._candidates:
            QtWidgets.QMessageBox.information(
                self,
                "尚无候选物相",
                "请先运行 Search-Match 得到候选列表，再生成报告。",
            )
            return
        pattern = self._current_pattern
        wavelength = pattern.wavelength if pattern is not None else 1.5406
        sample_name = self._current_filename or "实验谱"
        peaks: list = []
        if pattern is not None:
            peaks = find_peaks(pattern.two_theta, pattern.intensity)
        report = Report(
            sample_info=SampleInfo(sample_name=sample_name, wavelength=wavelength),
            peak_list=PeakListSection(peaks=peaks),
            candidate_list=CandidateListSection(
                candidates=[
                    CandidateEntry(
                        entry_id=c.entry.entry_id,
                        formula=c.entry.formula,
                        name=c.entry.mineral_name or "",
                        fom=c.fom,
                    )
                    for c in self._candidates
                ]
            ),
        )
        text = render_text(report)
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Search-Match 报告预览")
        dlg.resize(760, 560)
        layout = QtWidgets.QVBoxLayout(dlg)
        view = QtWidgets.QPlainTextEdit(dlg)
        view.setReadOnly(True)
        view.setPlainText(text)
        layout.addWidget(view)
        close_btn = QtWidgets.QPushButton("关闭", dlg)
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn)
        dlg.exec()

    # ------------------------------------------------------------------
    # Placeholder handler
    # ------------------------------------------------------------------
    def _placeholder(self, label: str) -> None:
        """Announce a not-yet-implemented module in the status bar."""
        self.statusBar().showMessage(
            f"[{label}] 模块骨架已就位，具体工作流在后续任务中实现", 5000
        )
