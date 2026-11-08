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

import logging
import math
from pathlib import Path
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from xinmatch.core.db.library_scale import (
    LARGE_LIBRARY_PHASE_THRESHOLD as LARGE_LIBRARY_PHASE_THRESHOLD,
)
from xinmatch.core.db.library_scale import (
    is_large_library as is_large_library,
)
from xinmatch.core.db.multi_db import (
    LibraryNotAvailableError,
    open_library,
    resolve_default,
)
from xinmatch.core.io import load_pattern
from xinmatch.core.io.exporters import (
    export_ascii_2col,
    export_ascii_profile,
)
from xinmatch.core.model import Entry, Peak, Restraints
from xinmatch.core.model.pattern import Pattern
from xinmatch.core.model.phase import Phase
from xinmatch.core.peak.peak_search import find_peaks
from xinmatch.core.preprocess.alpha2 import strip_alpha2
from xinmatch.core.preprocess.background import (
    estimate_background,
    subtract_background,
)
from xinmatch.core.preprocess.smoothing import smooth
from xinmatch.core.refine.cif_store import export_cifs, match_entry_cifs
from xinmatch.core.report.render import render_text
from xinmatch.core.report.report_model import (
    CandidateEntry,
    CandidateListSection,
    PeakListSection,
    Report,
    SampleInfo,
)
from xinmatch.core.search.correlate import d_to_two_theta
from xinmatch.core.search.fom import CandidateResult
from xinmatch.core.search.fpfm import search_match_fpfm
from xinmatch.core.search.fpfm import to_candidates as fpfm_to_candidates
from xinmatch.core.search.search_match import search_match
from xinmatch.core.search.sequential import (
    ResidualSearchResult,
    SequentialIdentifier,
    search_residual,
)
from xinmatch.ui.about_dialog import AboutDialog
from xinmatch.ui.busy import run_with_busy
from xinmatch.ui.dialogs.colors_dialog import ColorsDialog
from xinmatch.ui.dialogs.config import (
    DEFAULTS,
    app_config_dir,
    load_config,
    save_config,
)
from xinmatch.ui.dialogs.library_dialog import LibraryDialog
from xinmatch.ui.dialogs.options_dialog import OptionsDialog
from xinmatch.ui.pattern_view import PATTERN_COLORS, PatternPanel
from xinmatch.ui.periodic_table import PeriodicTablePanel
from xinmatch.ui.profile_fit_dialog import ProfileFitDialog
from xinmatch.ui.quant_dialog import QuantDialog
from xinmatch.ui.refinement_wizard import RefinementWizard
from xinmatch.ui.shortcuts import install_shortcuts
from xinmatch.ui.structure_view import (
    StructureViewDialog,
    resolve_entry_cif,
)
from xinmatch.ui.tables import CandidateListTable, MatchListTable, PeakListTable
from xinmatch.ui.theme import apply_theme, current_theme
from xinmatch.utils import build_variant
from xinmatch.utils.registration import RegistrationManager

# 主题图标（并行任务交付；缺失时回退到 Qt 标准 pixmap）。
try:  # pragma: no cover - 取决于并行任务产物是否落地
    from xinmatch.ui.icons import icon as _themed_icon
except ImportError:  # pragma: no cover
    _themed_icon = None  # type: ignore[assignment]

# 库名回填（状态栏文案要用 display_name）。
try:  # pragma: no cover
    from xinmatch.core.db.multi_db import library_by_id
except ImportError:  # pragma: no cover
    library_by_id = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)


def _asset_path(name: str) -> Path:
    """Resolve a top-level ``assets/`` file (logo.png / splash.png)."""
    return Path(__file__).resolve().parents[2] / "assets" / name


# 检索侧返回的候选卡数上界（§35）：``candidate_limit`` 的最大可配值，
# 换算出的 fetch 不会超过它，避免无谓放大检索池。
_ROW_BUDGET_FETCH_CEILING = 1000


def _candidate_row_budget(config: dict[str, Any] | None = None) -> tuple[int, int]:
    """把「候选列表行数上限」换算成 ``(fetch, max_rows)``（§35 方案 B）。

    * ``max_rows`` — 候选表显示行数上限（折叠时一行 ≈ 一个相族，所以它
      同时是族数上限；展开时按卡计）。取自
      ``candidate_list.max_display_rows``，脏值（非正数 / 非整数）回退到
      :data:`DEFAULTS` 里的默认值。
    * ``fetch`` — 三处检索入口实际要引擎返回的卡数。族合并只减行数，
      显示 N 行需要引擎返回多于 N 张卡，按 4 倍余量换算并钳位到
      ``[200, _ROW_BUDGET_FETCH_CEILING]``；检索侧 ``top_n`` 只影响最终
      切片、不影响打分成本（§35）。

    *config* 可注入（单测用）；缺省时读持久化配置。可在工作线程调用
    （只读 YAML，不触碰 GUI）。
    """
    if config is None:
        config = load_config()
    default_rows = int(
        (DEFAULTS.get("candidate_list") or {}).get("max_display_rows", 50)
    )
    raw = (config.get("candidate_list") or {}).get("max_display_rows", default_rows)
    try:
        max_rows = int(raw)
    except (TypeError, ValueError):
        max_rows = default_rows
    if max_rows <= 0:
        max_rows = default_rows
    fetch = min(
        _ROW_BUDGET_FETCH_CEILING, max(200, 4 * max_rows)
    )
    return fetch, max_rows

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

# ---------------------------------------------------------------------------
# 覆盖性大库的元素约束提示（基准报告 §23 / §24）
# ---------------------------------------------------------------------------
# 阈值与纯判据已下沉到 ``xinmatch.core.db.library_scale``：CLI 也要用同一份，
# 不能让命令行进程依赖 PySide6。这里 re-export 同名接口保持既有 import 不破，
# 两个入口（GUI 工具栏 / CLI stderr 提示）永远只有一个阈值。

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
    "推荐先填「样品元素」（XRF/EDS 或配方），其余元素自动标为排除——\n"
    "实测多相样品相召回 20/43 → 30/43（上界口径）。\n"
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

    薄封装：真正的转换逻辑已统一到
    :func:`xinmatch.core.search.fpfm.to_candidates`，GUI / 批处理 / CLI
    共用同一实现（v1.7.x 去重，避免两处 FoM 映射漂移）。此函数保留为
    模块级公开名，供既有测试与外部脚本调用。
    """
    return fpfm_to_candidates(fpfm_results)


class MainWindow(QtWidgets.QMainWindow):
    """Top-level application window; see module docstring for layout."""

    def __init__(self, parent=None) -> None:
        """Build actions, menus, toolbar, status bar, central view and docks."""
        super().__init__(parent)
        self.setWindowTitle("XinMatch")
        self.resize(1280, 800)

        # Application icon — 256 px plate from assets/icons/ (v3.2.0 起的新品牌标志),
        # 回退到整张 logo.png；都缺失时用 Qt 默认图标。
        for _icon_name in ("icons/logo_256.png", "logo.png"):
            _icon_path = _asset_path(_icon_name)
            if _icon_path.is_file():
                self.setWindowIcon(QtGui.QIcon(str(_icon_path)))
                break

        # State fed by the controller layer: current experimental pattern and
        # the latest search-match candidate list.
        self._current_pattern: Pattern | None = None
        self._candidates: list[CandidateResult] = []
        self._last_outcome = None
        # Multi-DB mount: registry id of the library last opened for search.
        self._active_library_id: str | None = None
        # 当前库是否覆盖性大库（≥20 万相）：大库需要显式元素约束，见 §23。
        # 初值 False，由选库 / 打开检索两个时机同步；启动时不去读用户配置，
        # 避免测试与真实环境配置串味。
        self._active_library_is_large = False
        # 当前已打开数据文件的显示名（文件名），用于状态栏 / 报告。
        self._current_filename: str = ""
        # 打开时的原始谱（「重置」回到这里；预处理只改 _current_pattern）。
        self._raw_pattern: Pattern | None = None
        # 谱图区当前曲线的句柄（预处理后替换曲线，避免叠加多条）。
        self._pattern_key: str | None = None
        # 统一检索入口模式：默认峰列表 FoM（寻峰）；可在工具栏下拉框切换。
        self._search_mode: str = SEARCH_MODE_PEAKS_FOM

        # ---- v3.1.0 序贯物相鉴定（逐相确认 → 剩余峰再检索）----
        #: 本次分析的原始峰列表（序贯鉴定的基准，后续只做残差，不重新寻峰）。
        self._exp_peaks: list[Peak] = []
        #: 序贯鉴定状态机（已确认相 + 残差峰）；None 表示尚未建立。
        self._seq: SequentialIdentifier | None = None
        #: 谱图区已叠加的参考线条句柄（按确认顺序，与 PATTERN_COLORS 对齐）。
        self._stick_keys: list[str] = []
        #: 最近一次整谱检索的模式标签（残差检索沿用同一文档口径）。
        self._last_mode_label: str = ""
        #: 最近一次确认的提示语（并入随后那条状态栏消息，否则会被覆盖）。
        self._confirm_note: str = ""

        self.module_actions: dict[str, QtGui.QAction] = {}

        # v1.7.0 注册机制：仅正式版（release）接入；内部评估版不弹提示、
        # 不出现「输入注册码」菜单，状态栏右端固定显示「内部评估版本」。
        self._registration: RegistrationManager | None = None
        self._registration_label: QtWidgets.QLabel | None = None
        if build_variant.is_release():
            self._registration = RegistrationManager(
                "XinMatch", app_config_dir() / "registration.json"
            )

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
        # v1.7.0：启动注册检查（QTimer 保证先完成窗口显示、不阻塞冒烟测试；
        # 离屏/显式禁用时模块内部自动跳过弹窗）。
        registration = self._registration
        if registration is not None:
            QtCore.QTimer.singleShot(0, lambda: registration.startup_check(self))

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
            elif mod_id == "data_import":
                # 批次 1 接线：与工具栏「打开数据…」（Ctrl+O）同一入口。
                action.triggered.connect(self._open_data_file)
            elif mod_id == "data_export":
                # 批次 2 接线：聚合菜单在 _build_menus 里挂载（依赖该阶段
                # 才创建的 .xinm / CIF 导出动作），这里不接占位播报。
                pass
            elif mod_id == "raw_processing":
                # 批次 1 接线：预处理已拆成工具栏四个真实动作（背景 / 平滑 /
                # Kα2 剥离 / 重置）。菜单动作聚合同一组 QAction（无新逻辑）；
                # 子菜单在这四个动作创建之后挂载（见本方法末尾）。
                pass
            elif mod_id == "peak_list":
                # 批次 1 接线：与工具栏「峰检测」同一入口。
                action.triggered.connect(self._detect_peaks)
            elif mod_id == "restraints":
                # 批次 1 接线：限制条件页（周期表三态 + 样品元素）已挂在
                # 右侧坞，菜单动作把它翻到最前。
                action.triggered.connect(self._focus_restraints)
            elif mod_id == "rietveld":
                # 批次 1 接线：与「精修向导…」（Ctrl+Shift+W）同一入口，
                # 计算全委托 core.refine。
                action.triggered.connect(self._open_refinement_wizard)
            elif mod_id == "profile_fitting":
                # 批次 3 接线：Profile Fitting 对话框（F5），计算全委托
                # core.peak.profile_fit.fit_profile。
                action.triggered.connect(self._open_profile_fit)
            elif mod_id == "quant_analysis":
                # 批次 4 接线：RIR 定量分析对话框，计算全委托
                # core.quant.rir.rir_quantify。
                action.triggered.connect(self._open_quant_dialog)
            else:
                action.triggered.connect(
                    lambda _checked=False, lbl=label: self._placeholder(lbl)
                )
            self.module_actions[mod_id] = action

        # 「样品元素」快捷入口（2026-11-06）。基准报告 §20 实测：元素信息是
        # 多相次相召回的决定性条件，而原来它藏在右侧坞的第二个页签里。
        # 工具栏按钮常显当前状态，点击直接跳到快速录入框。
        self.sample_elements_action = QtGui.QAction("样品元素：未设置", self)
        self.sample_elements_action.setObjectName("sampleElementsAction")
        self.sample_elements_action.setStatusTip(
            "填样品检出元素并把其余元素标为排除；实测相召回 20/43 → 30/43"
        )
        self.sample_elements_action.setToolTip(
            "样品元素约束（推荐多相样品填写）\n"
            "来源：XRF/EDS 或配方；点击后跳到「限制条件」页的快速录入框。\n"
            "实测：真实谱相召回 20/43 → 30/43、3-1 次相 1/3 → 3/3（上界口径）。\n"
            "注意：30/43 是元素由真值反推的上界，实际值取决于元素测量是否完整。"
        )
        self.sample_elements_action.triggered.connect(self.focus_sample_elements)

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

        # ---- 工具栏补充动作（v1.7.x：预处理动作已接线到 core.preprocess）----
        self.background_action = self._tool_action(
            "背景扣除", "background",
            lambda _checked=False: self._apply_background(),
            "扣除谱图背景（SNIP 估计后相减，负值截零）",
        )
        self.smooth_action = self._tool_action(
            "平滑", "smooth",
            lambda _checked=False: self._apply_smoothing(),
            "谱图平滑（Savitzky-Golay，窗口 11 / 3 阶）",
        )
        self.ko2_action = self._tool_action(
            "Kα2 剥离", "ko2",
            lambda _checked=False: self._apply_alpha2_strip(),
            "剥离 Kα2 分量（Rachinger，波长跟随谱图设置）",
        )
        self.reset_action = self._tool_action(
            "重置", "reset",
            lambda _checked=False: self._reset_pattern(),
            "重置为打开时的原始谱图（撤销全部预处理）",
        )
        self.peakdetect_action = self._tool_action(
            "峰检测", "peakdetect",
            lambda _checked=False: self._detect_peaks(),
            "自动峰检测（medium 灵敏度，结果填入峰列表）",
        )
        self.codsearch_action = self._tool_action(
            "COD 搜索", "codsearch",
            lambda _checked=False: self._open_library_dialog(),
            "选择 COD 参考数据库进行检索",
        )

        # 「原始数据处理」菜单动作聚合这四个预处理 QAction（批次 1 接线；
        # 同一批对象，工具栏与菜单永远同步）。
        _raw_menu = QtWidgets.QMenu(self)
        for _act in (self.background_action, self.smooth_action,
                     self.ko2_action, self.reset_action):
            _raw_menu.addAction(_act)
        self.module_actions["raw_processing"].setMenu(_raw_menu)

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
        tail_sep = menus["文件(&F)"].addSeparator()
        menus["文件(&F)"].addAction(exit_action)
        # v3.4.0 联合计划 X-3：导出物相分析状态（.xinm，供 XinRefinement 导入）。
        self.export_xinm_action = QtGui.QAction("导出物相分析（.xinm）…", self)
        self.export_xinm_action.setStatusTip(
            "打包谱图 + 已选物相 CIF 为 .xinm 文件，供 XinRefinement 导入做全谱精修"
        )
        self.export_xinm_action.triggered.connect(self._export_xinm)
        menus["文件(&F)"].insertAction(tail_sep, self.export_xinm_action)

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

        # 批次 2 接线：「数据导出」模块动作聚合全部导出能力（谱图 / 峰列表 /
        # 候选 / 匹配 + 既有的 .xinm 项目与 CIF）。四个新动作在这里创建，
        # 因为聚合菜单要同时引用本方法上方才创建的 export_xinm_action /
        # export_cifs_action（_build_actions 循环阶段它们还不存在）。
        self.export_profile_action = self._tool_action(
            "导出谱图 (ASCII profile)…", "export",
            lambda _checked=False: self._export_pattern_ascii("profile"),
            "导出 start/step/end 头 + 强度序列的 ASCII profile（可被再次读回）",
        )
        self.export_2col_action = self._tool_action(
            "导出谱图 (两列 2θ–I)…", "export",
            lambda _checked=False: self._export_pattern_ascii("2col"),
            "导出两列 2θ–I ASCII（通用交换格式）",
        )
        self.export_peaks_csv_action = self._tool_action(
            "导出峰列表 (CSV)…", "export",
            lambda _checked=False: self._export_peak_list_csv(),
            "把峰列表导出为 CSV（2θ / d / I / I-I₀ / FWHM / hkl）",
        )
        self.export_candidates_csv_action = self._tool_action(
            "导出候选列表 (CSV)…", "export",
            lambda _checked=False: self._export_candidates_csv(),
            "把候选列表（与界面显示同源的行）导出为 CSV",
        )
        self.export_matches_csv_action = self._tool_action(
            "导出匹配列表 (CSV)…", "export",
            lambda _checked=False: self._export_matches_csv(),
            "把已确认物相列表导出为 CSV",
        )
        _export_menu = QtWidgets.QMenu(self)
        for _act in (self.export_profile_action, self.export_2col_action,
                     self.export_peaks_csv_action,
                     self.export_candidates_csv_action,
                     self.export_matches_csv_action):
            _export_menu.addAction(_act)
        _export_menu.addSeparator()
        _export_menu.addAction(self.export_xinm_action)
        _export_menu.addAction(self.export_cifs_action)
        self.module_actions["data_export"].setMenu(_export_menu)
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
        # v1.7.0：帮助菜单固定提供「输入注册码 (&R)…」（仅正式版）。
        if self._registration is not None:
            self._registration.add_help_action(help_menu, self)

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
        toolbar.addAction(self.sample_elements_action)
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
        """Status bar: transient module messages + permanent cursor readout.

        v1.7.0：最右侧（右对齐）再加一排注册状态——正式版显示
        「已注册：<单位部门名称>」/「未注册」，内部评估版显示
        「内部评估版本」。
        """
        self.statusBar().showMessage("就绪")
        self._cursor_label = QtWidgets.QLabel("2θ=—   I=—   d=—")
        self.statusBar().addPermanentWidget(self._cursor_label)
        if self._registration is not None:
            # stretch=1 让标签吃掉剩余空白，单位名始终贴住状态栏右端。
            self._registration_label = self._registration.attach_status_label(
                self.statusBar(), self
            )
        else:
            label = QtWidgets.QLabel(build_variant.INTERNAL_STATUS_TEXT)
            label.setObjectName("internalBuildLabel")
            label.setAlignment(
                QtCore.Qt.AlignmentFlag.AlignRight
                | QtCore.Qt.AlignmentFlag.AlignVCenter
            )
            label.setToolTip("内部评估版：未启用注册机制，仅供内部测试与评估使用。")
            # v3.0.0：内部评估版本改成**红色加粗**（需求原文）。用控件自带
            # stylesheet 而不是全局 QSS —— 状态栏会被主题重新刷一遍样式，
            # 挂在控件上的规则优先级更高，换主题也不会掉色。
            label.setStyleSheet(
                "color: #d32f2f; font-weight: bold; padding: 0 6px;"
            )
            self.statusBar().addPermanentWidget(label, 1)
            self._registration_label = label

    def registration_status_text(self) -> str:
        """状态栏最右一排的注册文案（供冒烟/自测读取，不弹窗）。"""
        if self._registration is not None:
            return self._registration.state.status_text
        return build_variant.INTERNAL_STATUS_TEXT

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
        # v3.1.0：表格上方加一行序贯操作条（确认该相 / 撤销 / 残差状态），
        # 让"选中 → 确认 → 剩余峰再检索"的循环有明确入口。
        self.candidate_table = CandidateListTable()
        cand = QtWidgets.QDockWidget("候选列表 Candidate List", self)
        cand.setObjectName("candidateDock")
        cand.setWidget(self._build_candidate_panel())
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
        # 「样品元素」工具栏按钮需要能把这个页签翻到最前面。
        self._restraints_tabs = tabs
        self._restraints_dock = right
        self.periodic_panel.selection_changed.connect(
            self._refresh_sample_elements_action
        )
        self._refresh_sample_elements_action()

        # Lower-right: match list, tabified with the right dock.  T13.3 匹配表挂载。
        self.match_table = MatchListTable()
        match = QtWidgets.QDockWidget("匹配物相 Match List", self)
        match.setObjectName("matchDock")
        match.setWidget(self.match_table)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, match)
        self.tabifyDockWidget(right, match)

        # 序贯流程信号（v3.1.0）：候选双击 / 回车 / 右键"确认为匹配物相"；
        # 匹配列表双击 / 右键移除 → 回滚该相并重算剩余峰。
        self.candidate_table.candidate_activated.connect(self.confirm_candidate)
        self.match_table.phase_activated.connect(self.remove_matched_phase)
        self.match_table.remove_phase.connect(self.remove_matched_phase)

        # 批次 2：三张数据表的「导出 (CSV)…」右键项此前是悬空信号（无 handler），
        # 统一接到导出方法——与「数据导出」聚合菜单的 CSV 动作同一入口。
        self.peak_table.export_requested.connect(self._export_peak_list_csv)
        self.candidate_table.export_requested.connect(self._export_candidates_csv)
        self.match_table.export_requested.connect(self._export_matches_csv)

    def _build_candidate_panel(self) -> QtWidgets.QWidget:
        """候选列表坞内容：序贯操作条 + 候选表格（v3.1.0）。

        操作条从左到右：确认该相 → 撤销上一相 → 清空匹配列表 → 残差状态
        标签。状态标签常显"已确认 N 相 / 剩余 M 峰 / 已解释 X% 强度"，
        是判断"还剩什么没匹配上"的唯一读数。
        """
        panel = QtWidgets.QWidget()
        panel.setObjectName("candidatePanel")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        bar = QtWidgets.QHBoxLayout()
        bar.setContentsMargins(4, 2, 4, 2)
        bar.setSpacing(6)
        self.confirm_phase_button = QtWidgets.QPushButton("确认该相（加入匹配列表）")
        self.confirm_phase_button.setToolTip(
            "把当前选中的候选确认为匹配物相，然后用**剩余的未解释峰**重新检索。\n"
            "等价操作：候选列表双击 / 回车 / 右键「确认为匹配物相」。\n"
            "适用场景：多相样品——先确认主相，再逐相确认次相。"
        )
        self.undo_phase_button = QtWidgets.QPushButton("撤销上一相")
        self.undo_phase_button.setToolTip(
            "撤回最近一次确认（或双击匹配列表中的行），已解释的峰会归还，"
            "候选列表按新的剩余峰重新检索。"
        )
        self.clear_phases_button = QtWidgets.QPushButton("清空匹配列表")
        self.clear_phases_button.setToolTip(
            "撤销全部确认，回到整谱检索状态（峰列表保持不变）。"
        )
        self.residual_label = QtWidgets.QLabel("尚未检索")
        self.residual_label.setObjectName("residualBadge")
        self.residual_label.setToolTip(
            "剩余峰 = 尚未被任何已确认物相解释的实验峰。\n"
            "剩余峰检索只在这些峰上做匹配，因此不会再被主相的强线主导。"
        )

        bar.addWidget(self.confirm_phase_button)
        bar.addWidget(self.undo_phase_button)
        bar.addWidget(self.clear_phases_button)
        bar.addSpacing(10)
        bar.addWidget(self.residual_label, 1)

        self.confirm_phase_button.clicked.connect(self.confirm_selected_candidate)
        self.undo_phase_button.clicked.connect(self.undo_last_phase)
        self.clear_phases_button.clicked.connect(self.clear_matched_phases)

        layout.addLayout(bar)
        layout.addWidget(self.candidate_table, 1)
        self._refresh_sequential_controls()
        return panel

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
        current = (config.get("reference_db") or {}).get("selected_library_id")
        dialog = LibraryDialog(current_id=current, parent=self)
        if dialog.exec():
            selected = dialog.selected_id()
            config.setdefault("reference_db", {})[
                "selected_library_id"
            ] = selected
            save_config(config)
            rec = self._set_active_library_scale(selected)
            if self._active_library_is_large:
                panel = getattr(self, "periodic_panel", None)
                if panel is None or not (panel.quick_elements() or panel.states()):
                    # 非阻塞引导：只写状态栏，不弹模态框、不强制用户填写。
                    # 已经设了元素约束的用户不再打扰。
                    name = getattr(rec, "display_name", None) or selected
                    count = getattr(rec, "entry_count", 0) or 0
                    self.statusBar().showMessage(
                        f"已挂载大库「{name}」（{count:,} 相）：大量无关相会稀释候选池，"
                        "建议先点工具栏「样品元素」填检出元素"
                        "（全库合成谱 Top-1 7/13 → 12/13，见基准报告 §23）。",
                        15000,
                    )

    def _open_library_with_index(self, library_id: str):
        """Open *library_id* and return its :class:`XinDBReader`.

        v3.0.0 的库是自包含的列存文件，**不需要**任何转换/建索引步骤，所以这里
        只是一层薄封装（名字保留，免得调用点全改）。返回的 reader 由调用方
        负责 ``close()``。
        """
        return open_library(library_id)

    def open_search_library(self):
        """Open the selected reference DB for search-match, with safe fallback.

        Reads ``reference_db.selected_library_id`` from the YAML config and
        opens it read-only via
        :func:`~xinmatch.core.db.multi_db.open_library`; the returned
        :class:`~xinmatch.core.db.reader_v3.XinDBReader` can be fed straight to
        :func:`~xinmatch.core.search.search_match.search_match` (which
        dispatches to the v3 columnar path).

        When the chosen library is unavailable (missing / unbuilt / corrupt)
        a warning box explains why and the default bundled library is used
        instead, so that search-match always has a working connection.  Raises
        only when *both* the selected and the default library are broken.
        """
        config = load_config()
        selected = (config.get("reference_db") or {}).get("selected_library_id")
        selected = selected or resolve_default().id
        try:
            conn = self._open_library_with_index(selected)
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
            self._set_active_library_scale(default.id)
            self.statusBar().showMessage(
                f"已回退到默认参考数据库：{default.display_name}", 8000
            )
            return conn
        self._active_library_id = selected
        # 配置里可能直接写了大库而用户没走过选库对话框：检索时再同步一次。
        self._set_active_library_scale(selected)
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
        self._pattern_key = self.pattern_view.add_pattern(pattern, name=name)

    def set_candidates(self, results: list[CandidateResult],
                       *, anchored_ids: list[str] | None = None) -> None:
        """Store the latest search-match results and fill the candidate dock.

        *anchored_ids* marks the rows the residual search flagged as
        strong-line anchored (v3.3.0): sparse phases whose strongest
        reference line sits on a strong leftover peak.  The order is not
        changed — the mark only tells the user where to look.
        """
        self._candidates = list(results)
        # 行数上限（§35 方案 B）：表格在模型层截断显示，``self._candidates``
        # 仍持全量（项目存档 .xinm 与报告预览的同源口径见各处注释）。
        # 折叠（族合并）时前 N 行 = 前 N 个族；展开时 = 前 N 张卡。
        _, max_rows = _candidate_row_budget()
        self.candidate_table.set_max_rows(max_rows)
        self.candidate_table.set_candidates(
            self._candidates, anchored_ids=anchored_ids
        )
        # 新候选到达即刷新「确认该相」的可用状态（v3.1.0）。
        if hasattr(self, "confirm_phase_button"):
            self._refresh_sequential_controls()

    def _selected_candidate_results(self) -> list[CandidateResult]:
        """Candidate rows selected in the dock; fall back to all candidates.

        Goes through :meth:`CandidateListTable.selected_results` because the
        candidate list folds same-phase variants (v3.2.0), so a display row is
        no longer a candidate index.
        """
        selected = self.candidate_table.selected_results()
        return selected or list(self._candidates)

    def _open_profile_fit(self) -> None:
        """批次 3 — 打开 Profile Fitting 对话框（参考软件 F5）。

        输入：当前谱图 + 峰列表初始猜测（`peak_table.peaks()`）。峰列表为空
        或无谱图时提示而不打开对话框。计算全委托
        :func:`xinmatch.core.peak.profile_fit.fit_profile`；「应用到峰列表」
        把精修后的峰写回峰表（此后可重新 Search-Match）。
        """
        if self._current_pattern is None:
            QtWidgets.QMessageBox.information(
                self,
                "尚无谱图",
                "请先打开衍射数据，再做 Profile Fitting。",
            )
            return
        peaks = self.peak_table.peaks()
        if not peaks:
            QtWidgets.QMessageBox.information(
                self,
                "峰列表为空",
                "Profile Fitting 以峰列表为初始猜测。\n"
                "请先寻峰（工具栏「峰检测」），再打开本对话框。",
            )
            return
        dlg = ProfileFitDialog(
            self._current_pattern, peaks, self.pattern_view, parent=self
        )

        def _apply(fitted: list) -> None:
            self.peak_table.set_peaks(fitted)
            self.statusBar().showMessage(
                f"已把 {len(fitted)} 个精修峰写回峰列表（2θ / FWHM / 面积）",
                10000,
            )

        dlg.fit_applied.connect(_apply)
        dlg.exec()

    def _open_quant_dialog(self) -> None:
        """批次 4 — 打开 RIR 定量分析对话框（绝热法）。

        输入：已确认物相（匹配列表）+ 当前峰列表；主峰强度取每相
        ``Phase.correlations`` 指向的实验峰最大积分强度。计算全委托
        :func:`xinmatch.core.quant.rir.rir_quantify`；「应用到匹配列表」
        把 wt% 写回 ``Phase.weight_fraction`` 并刷新匹配表（之后可用
        「数据导出 → 导出匹配列表 (CSV)…」带走 weight_pct 列）。
        """
        phases = self.match_table.phases()
        if not phases:
            QtWidgets.QMessageBox.information(
                self,
                "无已确认物相",
                "请先在候选列表中确认物相（双击 / 回车），再做定量分析。",
            )
            return
        dlg = QuantDialog(phases, self.peak_table.peaks(), parent=self)

        def _apply(updated: list) -> None:
            self.match_table.set_phases(updated)
            n = sum(1 for p in updated if p.weight_fraction is not None)
            self.statusBar().showMessage(
                f"已把 RIR 定量结果（{n} 相 wt%）写回匹配列表；"
                "可用「数据导出 → 导出匹配列表 (CSV)…」导出",
                10000,
            )

        dlg.quant_applied.connect(_apply)
        dlg.exec()

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

    # ------------------------------------------------------------------
    # 批次 2：数据导出（谱图 ASCII / 三张表 CSV）。聚合菜单见 _build_menus。
    # ------------------------------------------------------------------
    @staticmethod
    def _write_csv(path: str, headers: list[str], rows: list[list[str]]) -> Path:
        """Write *rows* as UTF-8 (BOM) CSV — Excel 双击打开不乱码。"""
        import csv

        out = Path(path)
        with out.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh, lineterminator="\n")
            writer.writerow(headers)
            writer.writerows(rows)
        return out

    def _export_pattern_ascii(self, fmt: str) -> None:
        """导出当前谱图为 ASCII profile（start/step/end 头）或两列 2θ–I。"""
        pattern = self._current_pattern
        if pattern is None:
            QtWidgets.QMessageBox.information(
                self, "尚无谱图", "请先打开衍射数据，再导出。"
            )
            return
        if fmt == "2col":
            caption = "导出谱图（两列 2θ–I）"
            filt = "两列 ASCII (*.txt *.xy);;所有文件 (*)"
            writer = export_ascii_2col
        else:
            caption = "导出谱图（ASCII profile）"
            filt = "ASCII profile (*.txt *.prd);;所有文件 (*)"
            writer = export_ascii_profile
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, caption, "", filt)
        if not path:
            return
        try:
            out = writer(pattern, path)
        except Exception as exc:  # noqa: BLE001 — GUI 动作边界
            logger.exception("pattern export failed")
            QtWidgets.QMessageBox.critical(self, "导出失败", f"谱图导出未完成：\n{exc}")
            return
        self.statusBar().showMessage(f"已导出谱图：{out}", 10000)

    def _export_peak_list_csv(self) -> None:
        """把峰列表导出为 CSV（2θ / d / I / I-I₀ / FWHM / hkl）。"""
        peaks = self.peak_table.peaks()
        if not peaks:
            QtWidgets.QMessageBox.information(
                self, "峰列表为空", "请先寻峰（工具栏「峰检测」），再导出峰列表。"
            )
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出峰列表 (CSV)", "peaks.csv", "CSV (*.csv);;所有文件 (*)"
        )
        if not path:
            return
        i_max = max((p.intensity for p in peaks), default=0.0)
        rows = []
        for p in peaks:
            rows.append([
                f"{p.two_theta:.4f}",
                "" if p.d is None else f"{p.d:.4f}",
                f"{p.intensity:.4f}",
                f"{(p.intensity / i_max * 100.0):.2f}" if i_max > 0 else "0.00",
                "" if p.fwhm is None else f"{p.fwhm:.4f}",
                "" if p.hkl is None else " ".join(str(v) for v in p.hkl),
            ])
        try:
            out = self._write_csv(path, ["2theta_deg", "d_A", "intensity",
                                         "relative_pct", "fwhm_deg", "hkl"], rows)
        except Exception as exc:  # noqa: BLE001 — GUI 动作边界
            logger.exception("peak list export failed")
            QtWidgets.QMessageBox.critical(self, "导出失败", f"峰列表导出未完成：\n{exc}")
            return
        self.statusBar().showMessage(f"已导出 {len(rows)} 个峰：{out}", 10000)

    def _export_candidates_csv(self) -> None:
        """把候选列表导出为 CSV（与界面显示同源：visible_results 截断口径）。"""
        results = self.candidate_table.visible_results() or list(self._candidates)
        if not results:
            QtWidgets.QMessageBox.information(
                self, "候选列表为空", "请先运行 Search-Match，再导出候选列表。"
            )
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出候选列表 (CSV)", "candidates.csv", "CSV (*.csv);;所有文件 (*)"
        )
        if not path:
            return
        rows = []
        for c in results:
            e = c.entry
            rows.append([
                e.entry_id,
                e.mineral_name or "",
                e.formula,
                e.space_group or "",
                f"{c.fom:.4f}",
            ])
        try:
            out = self._write_csv(path, ["entry_id", "mineral_name", "formula",
                                         "space_group", "fom"], rows)
        except Exception as exc:  # noqa: BLE001 — GUI 动作边界
            logger.exception("candidate list export failed")
            QtWidgets.QMessageBox.critical(self, "导出失败", f"候选列表导出未完成：\n{exc}")
            return
        self.statusBar().showMessage(f"已导出 {len(rows)} 个候选：{out}", 10000)

    def _export_matches_csv(self) -> None:
        """把已确认物相（匹配列表）导出为 CSV。"""
        phases = self.match_table.phases()
        if not phases:
            QtWidgets.QMessageBox.information(
                self, "匹配列表为空", "请先在候选列表中确认物相，再导出匹配列表。"
            )
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出匹配列表 (CSV)", "matches.csv", "CSV (*.csv);;所有文件 (*)"
        )
        if not path:
            return
        rows = []
        for ph in phases:
            e = ph.entry
            rows.append([
                e.entry_id,
                e.mineral_name or "",
                e.formula,
                f"{ph.scale_factor:.6g}",
                "" if ph.weight_fraction is None else f"{ph.weight_fraction * 100.0:.2f}",
            ])
        try:
            out = self._write_csv(path, ["entry_id", "mineral_name", "formula",
                                         "scale_factor", "weight_pct"], rows)
        except Exception as exc:  # noqa: BLE001 — GUI 动作边界
            logger.exception("match list export failed")
            QtWidgets.QMessageBox.critical(self, "导出失败", f"匹配列表导出未完成：\n{exc}")
            return
        self.statusBar().showMessage(f"已导出 {len(rows)} 个已确认相：{out}", 10000)

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

    def _export_xinm(self) -> None:
        """v3.4.0 联合计划 X-3：导出物相分析状态（.xinm）。

        打包锚点谱图 + 已选候选相（回取 COD CIF）+ 峰列表，供
        XinRefinement「导入 XinMatch 物相分析」一键装载。
        个别相 CIF 回取失败不阻断导出（manifest 里标记 structural=false）。
        """
        from xinmatch.core.io.xinm import export_xinm
        from xinmatch.core.model.phase import Phase
        from xinmatch.core.model.project import Project

        if self._current_pattern is None:
            QtWidgets.QMessageBox.information(
                self, "无实验衍射谱",
                "尚未载入实验衍射谱。\n请先导入衍射数据，再导出 .xinm。",
            )
            return
        candidates = self._selected_candidate_results()
        if not candidates:
            QtWidgets.QMessageBox.information(
                self, "无已鉴定相",
                "当前没有候选物相。\n请先运行 Search-Match 并选择相，再导出 .xinm。",
            )
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出物相分析状态",
            "analysis.xinm",
            "XinMatch 物相分析 (*.xinm);;所有文件 (*)",
        )
        if not path:
            return
        project = Project(
            patterns=[self._current_pattern],
            peaks=list(getattr(self, "_exp_peaks", []) or []),
            candidates=[(c.entry, float(c.fom)) for c in self._candidates],
            selected_phases=[
                Phase(entry=c.entry, scale_factor=float(c.i_scale))
                for c in candidates
            ],
        )
        from xinmatch import __version__ as app_version
        report = export_xinm(project, path, app_version=app_version)
        QtWidgets.QMessageBox.information(self, "导出完成", report.summary)

    def _open_about(self) -> None:
        """Show the About box; version read dynamically from xinmatch.__version__."""
        AboutDialog(self).exec()

    # ------------------------------------------------------------------
    # v1.0.0 体验修订：打开数据 / Search-Match 真实接线 / 报告预览
    # ------------------------------------------------------------------
    def _open_data_file(self) -> None:
        """文件→打开数据（Ctrl+O）：选择文件并自动嗅探格式后载入谱图。

        v1.7.x：解析放进忙碌窗口的工作线程。Bruker ``.brml`` 是 zip+XML、
        ``.raw`` 是分段二进制，几十万点的 ASCII 也要上百毫秒——此前在 GUI
        线程同步解析，大文件表现为「点了没反应」。GUI 线程只负责选择文件
        与结果显示。
        """
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
        fname = Path(path).name
        started = run_with_busy(
            self,
            "打开数据",
            f"正在读取并解析 {fname}…",
            lambda: load_pattern(path),
            on_success=lambda pattern: self._apply_loaded_pattern(pattern, path),
            on_error=lambda message: self._show_open_error(path, message),
        )
        if not started:
            self.statusBar().showMessage("上一份数据仍在读取，请稍候…", 5000)

    def _apply_loaded_pattern(self, pattern: Pattern, path: str) -> None:
        """接载入结果：谱图区 / 原始谱备份 / 状态栏（GUI 线程回调）。"""
        fname = Path(path).name
        self.pattern_view.clear()
        self._pattern_key = None  # clear() 已移除全部曲线
        self._current_filename = fname
        self._raw_pattern = pattern
        # 换数据 = 换分析：峰列表 / 候选 / 已确认相 / 参考线条全部作废，否则
        # 序贯确认会拿着上一个样品的峰继续算。
        self._stick_keys.clear()  # clear() 已一并移除参考线条
        self._exp_peaks = []
        self._seq = None
        self._confirm_note = ""
        self.set_candidates([])
        self.match_table.set_phases([])
        self.peak_table.set_peaks([])
        self._refresh_sequential_controls()
        self.set_pattern(pattern, name=fname)
        n = len(pattern)
        x0 = float(pattern.two_theta[0]) if n else 0.0
        x1 = float(pattern.two_theta[-1]) if n else 0.0
        self.statusBar().showMessage(
            f"已打开 {fname}：{n} 点，2θ {x0:.2f}–{x1:.2f}°"
        )

    def _show_open_error(self, path: str, message: str) -> None:
        """打开失败提示（GUI 线程回调）。"""
        QtWidgets.QMessageBox.warning(
            self,
            "无法打开衍射数据文件",
            f"文件：{path}\n\n原因：{message}\n\n"
            "请确认文件存在且格式受支持（两列 ASCII / Bruker / Panalytical / "
            "Shimadzu .raw 等）。",
        )

    # ------------------------------------------------------------------
    # 预处理动作（v1.7.x：把工具栏占位菜单接线到 core.preprocess）
    # ------------------------------------------------------------------
    def _require_loaded_pattern(self, action_label: str) -> Pattern | None:
        """Return the current pattern, or inform the user and return ``None``."""
        if self._current_pattern is None:
            QtWidgets.QMessageBox.information(
                self,
                "尚未打开衍射数据",
                f"请先通过 文件→打开数据… 载入衍射谱，再执行「{action_label}」。",
            )
            return None
        return self._current_pattern

    def _replace_processed(self, intensity, label: str) -> None:
        """Replace the displayed curve with *intensity* (never stacks curves).

        原始谱保存在 ``_raw_pattern``，「重置」可随时回到它；这里只替换
        ``_current_pattern`` 与谱图区对应的那一条曲线。
        """
        current = self._current_pattern
        if current is None:
            return
        processed = Pattern(
            two_theta=current.two_theta,
            intensity=intensity,
            wavelength=current.wavelength,
            step=current.step,
            metadata=dict(current.metadata),
        )
        if self._pattern_key is not None:
            self.pattern_view.remove_pattern(self._pattern_key)
            self._pattern_key = None
        base = self._current_filename or "实验谱"
        self._pattern_key = self.pattern_view.add_pattern(
            processed, name=f"{base}（{label}）"
        )
        self._current_pattern = processed
        self.statusBar().showMessage(f"已应用到当前谱：{label}", 6000)

    def _apply_smoothing(self) -> None:
        """平滑：Savitzky-Golay（窗口 11，3 阶），与自动处理管线默认一致。"""
        pattern = self._require_loaded_pattern("平滑")
        if pattern is None:
            return
        n = len(pattern.intensity)
        window = 11 if n >= 11 else (n if n % 2 else n - 1)
        if window < 5:
            QtWidgets.QMessageBox.information(
                self, "数据点过少", f"当前谱只有 {n} 个点，无法平滑。",
            )
            return
        intensity = smooth(
            pattern.intensity, method="savgol", window=window, polyorder=3
        )
        self._replace_processed(intensity, f"平滑 Savitzky-Golay({window},3)")

    def _apply_background(self) -> None:
        """背景扣除：SNIP 估计 + 相减（负值截零）。"""
        pattern = self._require_loaded_pattern("背景扣除")
        if pattern is None:
            return
        bg = estimate_background(
            pattern.two_theta, pattern.intensity, method="snip", window=20
        )
        self._replace_processed(
            subtract_background(pattern.intensity, bg), "背景扣除 SNIP"
        )

    def _apply_alpha2_strip(self) -> None:
        """Kα2 剥离：Rachinger 算法；波长跟随谱图自身波长与 Kα2 设置。"""
        pattern = self._require_loaded_pattern("Kα2 剥离")
        if pattern is None:
            return
        ka1 = float(pattern.wavelength or 1.5406)
        _ka1, ka2 = self.fpfm_kalpha_wavelengths(pattern)
        # Kα2/Kα1 = 0.5 的强度比由 ratio 参数表达；波长比按 Kα2/Kα1 ≈ 1.0025。
        ka2_value = float(ka2) if ka2 is not None else ka1 * 1.0025
        intensity = strip_alpha2(
            pattern.two_theta,
            pattern.intensity,
            wavelength_kalpha1=ka1,
            wavelength_kalpha2=ka2_value,
            ratio=0.5,
        )
        self._replace_processed(intensity, "Kα2 剥离 Rachinger")

    def _reset_pattern(self) -> None:
        """重置：丢弃全部预处理，回到打开时的原始谱。"""
        if self._raw_pattern is None:
            QtWidgets.QMessageBox.information(
                self, "无可重置的数据", "请先通过 文件→打开数据… 载入衍射谱。",
            )
            return
        self.pattern_view.clear()
        self._pattern_key = None
        self._current_pattern = None
        self.set_pattern(self._raw_pattern, name=self._current_filename or "实验谱")
        self.statusBar().showMessage("已重置为原始谱（撤销全部预处理）", 6000)

    def _detect_peaks(self) -> None:
        """峰检测：medium 灵敏度寻峰并填入峰列表（不改动谱图数据）。"""
        pattern = self._require_loaded_pattern("峰检测")
        if pattern is None:
            return
        peaks = find_peaks(
            pattern.two_theta, pattern.intensity, sensitivity="medium"
        )
        self.peak_table.set_peaks(peaks)
        # v3.1.0：新峰列表即序贯鉴定的新基准（清空上一轮已确认相）。
        self._start_sequential(peaks)
        self.statusBar().showMessage(
            f"峰检测完成：识别到 {len(peaks)} 个峰（medium 灵敏度）", 6000
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
        except Exception as exc:  # noqa: BLE001 — GUI 动作边界，见下
            # 库里登记的文件在探测之后被删/被占用/损坏（Windows 上很常见：
            # 用户一边检索一边替换库），或配置文件损坏等，都可能让
            # open_search_library 抛出 LibraryNotAvailableError 之外的异常。
            # 这是 Qt 槽函数，异常逃出去只会留下 traceback、用户看不到原因，
            # 所以在动作边界统一转成可读错误框。
            logger.exception("failed to open reference library for search")
            QtWidgets.QMessageBox.critical(
                self,
                "参考数据库打开失败",
                "无法打开参考数据库，Search-Match 未执行。\n"
                f"请在 设置→参考数据库… 中检查库是否可用。\n\n原因：{exc}",
            )
            return

        mode = self._search_mode
        mode_desc = (
            "FPFM 全谱拟合检索（逐候选剖面拟合，耗时较长）"
            if mode == SEARCH_MODE_FPFM_FULL
            else "峰列表 FoM 检索"
        )

        # 限制条件必须在这里（GUI 线程）读出来再带进工作线程：周期表面板是
        # QWidget，从 worker 里碰它属于跨线程访问控件，Windows 上会随机崩。
        restraints = self._current_restraints()
        if restraints is not None and mode == SEARCH_MODE_FPFM_FULL:
            # FPFM 的检索链（core/search/fpfm.py）没有 restraints 形参，元素
            # 三态到不了预筛。宁可在这里明说，也不要让用户以为红色元素生效了。
            self.statusBar().showMessage(
                "提示：元素限制条件不参与 FPFM 全谱拟合检索（仅峰列表 FoM 生效）",
                8000,
            )

        started = run_with_busy(
            self,
            "Search-Match",
            f"正在执行{mode_desc}…\n对参考数据库逐条比对/拟合，请稍候。",
            lambda: self._do_search(pattern, conn, mode, restraints),
            on_success=self._apply_search_results,
            on_error=self._show_search_error,
        )
        if not started:
            # Re-entrant call rejected by the busy guard: the worker never ran,
            # so nobody will close the connection we just opened.
            conn.close()

    def _set_active_library_scale(self, library_id: str | None) -> object | None:
        """按当前库规模同步大库提示（GUI 线程，静默，不弹状态栏）。

        两个调用时机：选库对话框确认后、``open_search_library`` 打开库后。
        后者覆盖「配置里直接写了大库、没走对话框」的情况；每次检索多一次
        注册表查询，开销可忽略。注册表损坏时保守当作小库，不打断检索。
        """
        rec = None
        if library_id and library_by_id is not None:
            try:
                rec = library_by_id(library_id)
            except Exception:  # noqa: BLE001 — 注册表损坏不该打断检索
                rec = None
        self._active_library_is_large = is_large_library(rec)
        self._refresh_sample_elements_action()
        return rec

    def _refresh_sample_elements_action(self) -> None:
        """工具栏按钮常显当前元素约束状态（GUI 线程，由面板信号驱动）。"""
        panel = getattr(self, "periodic_panel", None)
        action = getattr(self, "sample_elements_action", None)
        if panel is None or action is None:
            return
        if not panel.is_enabled():
            text = "样品元素：已关闭"
        elif panel.quick_elements():
            syms = panel.quick_elements()
            shown = " ".join(syms[:5]) + ("…" if len(syms) > 5 else "")
            text = f"样品元素：仅 {shown}"
        elif panel.states():
            text = f"样品元素：自定义 {len(panel.states())} 项"
        elif self._active_library_is_large:
            # §23：大库没有化学先验，候选池被有机/无关相稀释。只在「尚未
            # 设任何约束」时提醒；已有约束或过滤已关闭时保持原状态文案。
            text = "样品元素：大库建议填写"
        else:
            text = "样品元素：未设置"
        action.setText(text)

    def _focus_restraints(self) -> None:
        """「限制条件检索」菜单动作：把右侧坞的限制条件页翻到最前（批次 1）。"""
        dock = getattr(self, "_restraints_dock", None)
        tabs = getattr(self, "_restraints_tabs", None)
        if dock is not None:
            dock.show()
            dock.raise_()
        if tabs is not None:
            tabs.setCurrentIndex(0)
        self.statusBar().showMessage(
            "在周期表上标元素（绿=必须含 / 黄=必须不含），多相样品建议再填「样品元素」",
            10000,
        )

    def focus_sample_elements(self) -> None:
        """把「限制条件」页翻到最前并聚焦快速录入框。"""
        dock = getattr(self, "_restraints_dock", None)
        tabs = getattr(self, "_restraints_tabs", None)
        if dock is not None:
            dock.show()
            dock.raise_()
        if tabs is not None:
            tabs.setCurrentIndex(0)
        panel = getattr(self, "periodic_panel", None)
        if panel is not None:
            panel.focus_detected_input()
        self.statusBar().showMessage(
            "填 XRF/EDS 检出的元素（如 Zn Al Ca O F），点「其余元素排除」；"
            "实测相召回 20/43 → 30/43",
            10000,
        )

    def _current_restraints(self) -> Restraints | None:
        """把「限制条件」面板的元素三态转成 :class:`Restraints`（GUI 线程调用）。

        面板关掉或没选任何元素时返回 ``None``，调用方据此走原来的无约束检索，
        保证「不用这个面板」的用户行为逐位不变。

        为什么需要这一步：三态里的「排除」长期没有任何下游消费者 —— 面板能标红、
        摘要会显示「排除：Bi」，但检索链一路到预筛都没读过它。于是「样品里没有
        Bi」这条化学上最硬的先验进不了召回，基准报告 §11.5 的 ``3-2``
        ``Bi-Y-O`` 假卡只能靠肉眼剔。
        """
        panel = getattr(self, "periodic_panel", None)
        if panel is None or not panel.is_enabled():
            return None
        states = panel.states()
        if not states:
            return None
        return Restraints(elements=dict(states))

    def _do_search(
        self,
        pattern: Pattern,
        conn,
        mode: str,
        restraints: Restraints | None = None,
    ) -> tuple[list[CandidateResult], str, list | None]:
        """检索工作体（运行在工作线程，禁止触碰 GUI）。

        返回 ``(候选列表, 模式名, 峰列表)``；FPFM 分支峰列表为 ``None``。
        异常直接上抛，由 :func:`run_with_busy` 转交 GUI 线程提示。

        连接生命周期：:meth:`open_search_library` 每次检索打开一个只读 reader，
        **必须在本方法内关闭**——Windows 上打开的库文件句柄会阻止用户替换/重建
        参考库（v1.7.x 缺陷修复；v3 的 ``XinDBReader.close()`` 语义相同）。
        """
        peaks: list | None = None
        try:
            if mode == SEARCH_MODE_FPFM_FULL:
                results, mode_label = self._search_fpfm(pattern, conn)
            else:
                peaks = find_peaks(pattern.two_theta, pattern.intensity)
                # §35：候选行数上限换算 fetch，检索多返回一些卡，
                # 供表格族合并后仍能显示满 N 行（打分成本与 top_n 无关）。
                fetch, _ = _candidate_row_budget()
                results = search_match(peaks, conn, pattern.wavelength,
                                       restraints=restraints, top_n=fetch)
                mode_label = "峰列表 FoM"
        finally:
            conn.close()
        return results, mode_label, peaks

    def _apply_search_results(
        self, payload: tuple[list[CandidateResult], str, list | None]
    ) -> None:
        """把检索结果回填候选列表 / 峰列表并更新状态栏（GUI 线程）。"""
        results, mode_label, peaks = payload
        self._last_mode_label = mode_label
        self.set_candidates(results)
        # FPFM 模式不寻峰：保留上一次峰列表，不覆盖 peak_table。
        if peaks is not None:
            self.peak_table.set_peaks(peaks)
        # 整谱检索视为**新一轮分析**：峰列表更新、已确认相清空、参考线移除，
        # 否则匹配列表会残留上一轮结论、与新的候选列表对不上。
        self._start_sequential(peaks)
        lib_label = self._active_library_id or "默认库"
        if library_by_id is not None and self._active_library_id:
            rec = library_by_id(self._active_library_id)
            if rec is not None:
                lib_label = rec.display_name
        self.statusBar().showMessage(
            f"检索完成：{len(results)} 个候选（{mode_label}，库：{lib_label}）"
            f" ｜ 双击/回车可确认为匹配物相，再对剩余峰继续检索",
            10000,
        )

    def _show_search_error(self, message: str) -> None:
        """检索失败提示（GUI 线程回调）。"""
        QtWidgets.QMessageBox.warning(
            self,
            "Search-Match 检索失败",
            f"检索过程中出现错误：\n\n{message}",
        )

    # ------------------------------------------------------------------
    # v3.1.0 序贯物相鉴定：确认一相 → 剩余峰再检索 → 再确认
    # ------------------------------------------------------------------
    def sequential_identifier(self) -> SequentialIdentifier | None:
        """当前序贯鉴定状态（供面板/测试读取，可能为 ``None``）。"""
        return self._seq

    def matched_phases(self) -> list[Phase]:
        """已确认的匹配物相（按确认顺序）。"""
        return self._seq.phases if self._seq is not None else []

    def _start_sequential(self, peaks: list[Peak] | None) -> None:
        """以 *peaks* 为基准重建序贯上下文（清空已确认相）。

        *peaks* 为 ``None`` 时保留既有峰列表、只清空已确认相 —— FPFM 全谱
        检索不寻峰，但它不应该抹掉"哪些峰"这件事，只是把确认进度归零。
        """
        if peaks is not None:
            self._exp_peaks = list(peaks)
        if self._exp_peaks:
            wavelength = (
                float(self._current_pattern.wavelength)
                if self._current_pattern is not None
                else 1.5406
            )
            self._seq = SequentialIdentifier(
                self._exp_peaks, wavelength=wavelength
            )
        else:
            self._seq = None
        self._sync_phase_views()

    def _ensure_sequential(self) -> bool:
        """确保序贯上下文可用；必要时惰性寻峰（FPFM 模式 / 仅手动寻峰后）。"""
        if self._seq is not None and self._seq.n_peaks > 0:
            return True
        pattern = self._current_pattern
        if pattern is None:
            QtWidgets.QMessageBox.information(
                self,
                "尚未打开衍射数据",
                "请先载入衍射谱并完成寻峰，再确认匹配物相。",
            )
            return False
        peaks = find_peaks(pattern.two_theta, pattern.intensity)
        if not peaks:
            QtWidgets.QMessageBox.information(
                self,
                "没有可用峰",
                "当前谱图未识别到峰，无法建立剩余峰检索。\n"
                "请先执行「峰检测」，或调整数据后重试。",
            )
            return False
        self._start_sequential(peaks)
        self.peak_table.set_peaks(self._exp_peaks)
        self.statusBar().showMessage(
            f"已按当前谱图建立峰列表（{len(peaks)} 个峰）用于逐相确认", 6000
        )
        return True

    def confirm_selected_candidate(self) -> None:
        """「确认该相」按钮：确认候选列表中高亮的那一行。"""
        eid = self.candidate_table.current_entry_id()
        if eid is None:
            QtWidgets.QMessageBox.information(
                self,
                "未选中候选",
                "请先在候选列表中选中一个物相，再点击「确认该相」。",
            )
            return
        self.confirm_candidate(eid)

    def confirm_candidate(self, entry_id: str) -> None:
        """把 *entry_id* 确认为匹配物相，并对**剩余未解释峰**重新检索。

        这是序贯鉴定的核心一步（v3.1.0）：

        1. 在 :class:`SequentialIdentifier` 里登记该相（重算相关峰、比例因子
           与逐峰残差）；
        2. 刷新匹配列表 / 峰列表关联标记 / 谱图参考线条；
        3. 用剩余峰再跑一次检索，候选列表换成"还剩下什么"的答案。

        重复确认同一相是幂等的（双击 / 连按回车不会重复入表）。
        """
        candidate = next(
            (c for c in self._candidates if c.entry.entry_id == entry_id), None
        )
        if candidate is None:
            self.statusBar().showMessage(f"候选列表中找不到 {entry_id}", 5000)
            return
        if not self._ensure_sequential():
            return
        seq = self._seq
        if seq is None:  # pragma: no cover - _ensure_sequential 已保证
            return
        if seq.is_selected(entry_id):
            self.statusBar().showMessage(
                f"{entry_id} 已在匹配列表中（如需重选请先撤销）", 5000
            )
            return

        covered_before = seq.covered_fraction
        selection = seq.select(candidate)
        self._sync_phase_views()
        entry = selection.phase.entry
        label = f"{entry.formula}" + (f"（{entry.mineral_name}）" if entry.mineral_name else "")
        # 增量提示：确认错相时它会"顺手"扣掉别人的峰（残差是减法，不会自我校验）。
        # 一旦某相几乎不解释新强度，多半是重复条目或假相，必须让用户看到。
        gain = selection.covered_fraction - covered_before
        note = ""
        if len(seq) > 1 and gain < 0.01:
            note = " ｜ 提示：本相几乎未解释新峰，可能是重复条目或假相，可撤销"
        self._confirm_note = note
        self.statusBar().showMessage(
            f"已确认第 {len(seq)} 相：{label} {entry_id}"
            f"（解释 {selection.covered_fraction * 100:.1f}% 强度，"
            f"本相 +{gain * 100:.1f}%，剩余 {selection.n_residual_peaks} 峰）{note}",
            10000,
        )
        self._search_residual_peaks()

    def undo_last_phase(self) -> None:
        """撤销最近一次确认，并按归还后的剩余峰重新检索。"""
        if self._seq is None or len(self._seq) == 0:
            self.statusBar().showMessage("匹配列表为空，无可撤销", 5000)
            return
        phase = self._seq.undo()
        self._sync_phase_views()
        if phase is not None:
            self.statusBar().showMessage(
                f"已撤销：{phase.entry.formula} {phase.entry.entry_id}", 6000
            )
        self._search_residual_peaks()

    def remove_matched_phase(self, entry_id: str) -> None:
        """从匹配列表移除指定相（双击 / 右键），按其位置回滚残差。"""
        if self._seq is None or not self._seq.remove(entry_id):
            return
        self._sync_phase_views()
        self.statusBar().showMessage(f"已移出匹配列表：{entry_id}", 6000)
        self._search_residual_peaks()

    def clear_matched_phases(self) -> None:
        """清空匹配列表：回到整谱检索状态（峰列表不变）。"""
        if self._seq is None or len(self._seq) == 0:
            self.statusBar().showMessage("匹配列表已经为空", 5000)
            return
        self._seq.clear()
        self._sync_phase_views()
        self.statusBar().showMessage("已清空匹配列表（峰列表保持不变）", 6000)
        self._search_residual_peaks()

    def _sync_phase_views(self) -> None:
        """把序贯状态同步到三个视图：匹配列表 / 峰列表标记 / 谱图参考线。"""
        seq = self._seq
        phases = seq.phases if seq is not None else []
        self.match_table.set_phases(phases)
        if seq is not None and self._exp_peaks:
            mask = seq.correlated_mask
            for peak, flag in zip(self._exp_peaks, mask, strict=True):
                peak.correlated = bool(flag)
            self.peak_table.set_peaks(self._exp_peaks)
        self._rebuild_reference_sticks()
        self._refresh_sequential_controls()

    def _refresh_sequential_controls(self) -> None:
        """更新序贯操作条的可用状态与残差读数（不触碰其他视图）。"""
        seq = self._seq
        has_phases = seq is not None and len(seq) > 0
        self.undo_phase_button.setEnabled(has_phases)
        self.clear_phases_button.setEnabled(has_phases)
        self.confirm_phase_button.setEnabled(
            bool(self._candidates) and (seq is not None or self._current_pattern is not None)
        )
        if seq is None or seq.n_peaks == 0:
            self.residual_label.setText("尚未检索")
            return
        text = (
            f"已确认 {len(seq)} 相 ｜ 剩余 {seq.n_residual_peaks}/{seq.n_peaks} 峰 ｜ "
            f"已解释 {seq.covered_fraction * 100:.1f}% 强度"
        )
        if seq.n_ignored:
            text += f" ｜ {seq.n_ignored} 个低强度峰不计"
        if seq.n_residual_peaks == 0:
            text += " ｜ 无剩余待解释峰"
        self.residual_label.setText(text)

    def _rebuild_reference_sticks(self) -> None:
        """按已确认相重画谱图参考线条（与候选行配色一致，便于目视核对）。

        线高 = 该相的比例因子 × 参考相对强度（即它**声称**贡献的计数），
        因此线条应与实测峰高度大致吻合；明显矮一截说明该相只解释了峰的
        一部分（重叠峰的另一相还没确认）。
        """
        for key in self._stick_keys:
            self.pattern_view.remove_stick_pattern(key)
        self._stick_keys.clear()
        seq = self._seq
        if seq is None:
            return
        wavelength = seq.wavelength
        for index, selection in enumerate(seq.selections):
            entry = selection.phase.entry
            ref_max = float(entry.intensity_max)
            if selection.scale <= 0.0 or ref_max <= 0.0:
                continue
            positions: list[float] = []
            heights: list[float] = []
            for d, intensity in zip(entry.d_spacings, entry.intensities, strict=True):
                two_theta = d_to_two_theta(float(d), wavelength)
                if not math.isfinite(two_theta):
                    continue
                positions.append(two_theta)
                heights.append(selection.scale * float(intensity) / ref_max)
            if not positions:
                continue
            label = f"{entry.entry_id} {entry.formula}".strip()
            key = self.pattern_view.add_stick_pattern(
                label,
                positions,
                heights,
                PATTERN_COLORS[index % len(PATTERN_COLORS)],
            )
            self._stick_keys.append(key)

    def _search_residual_peaks(self) -> None:
        """用剩余未解释峰重新检索（工作线程 + 忙碌窗口）。

        与整谱检索一样，每次打开一个只读库句柄并在工作体内关闭：Windows 上
        残留句柄会阻止用户替换参考库。
        """
        seq = self._seq
        if seq is None:
            return
        if seq.n_residual_peaks == 0:
            self.set_candidates([])
            self._refresh_sequential_controls()
            self.statusBar().showMessage(
                "全部有效峰已被确认的物相解释，没有剩余峰需要检索"
                + self._confirm_note,
                10000,
            )
            self._confirm_note = ""
            return
        try:
            conn = self.open_search_library()
        except LibraryNotAvailableError:
            QtWidgets.QMessageBox.critical(
                self,
                "无可用参考数据库",
                "参考数据库不可用，无法对剩余峰继续检索。\n"
                "已确认的物相与峰标记仍保留，可在 设置→参考数据库… 修复后重试。",
            )
            return
        except Exception as exc:  # noqa: BLE001 — GUI 动作边界
            logger.exception("failed to open reference library for residual search")
            QtWidgets.QMessageBox.critical(
                self,
                "参考数据库打开失败",
                "无法打开参考数据库，剩余峰检索未执行。\n"
                f"请检查 设置→参考数据库…\n\n原因：{exc}",
            )
            return

        started = run_with_busy(
            self,
            "剩余峰检索",
            f"正在用 {seq.n_residual_peaks} 个未解释峰重新检索参考库…",
            lambda: self._do_residual_search(conn),
            on_success=self._apply_residual_results,
            on_error=self._show_search_error,
        )
        if not started:
            conn.close()

    def _do_residual_search(self, conn) -> ResidualSearchResult:
        """剩余峰检索工作体（工作线程，禁止触碰 GUI）。"""
        seq = self._seq
        if seq is None:  # pragma: no cover - 调用前已保证
            raise RuntimeError("sequential state is not available")
        try:
            # §35：与整谱检索同一 fetch 口径（剩余峰候选也按行数上限放大）。
            fetch, _ = _candidate_row_budget()
            return search_residual(seq, conn, top_n=fetch)
        finally:
            conn.close()

    def _apply_residual_results(self, result: ResidualSearchResult) -> None:
        """回填剩余峰检索结果（GUI 线程）。"""
        self.set_candidates(result.candidates, anchored_ids=result.anchored_ids)
        self._refresh_sequential_controls()
        note = self._confirm_note
        self._confirm_note = ""
        if result.excluded_ids:
            note += f"；已排除已确认的 {len(result.excluded_ids)} 条"
        if result.anchored_ids:
            note += (
                f"；★ {len(result.anchored_ids)} 条最强线命中强残差峰"
                "（少线相，排名靠后也值得核对）"
            )
        # 高覆盖度提示：剩余峰往往只是卡片未收录的弱反射或噪声鼓包，此时排行榜
        # 前排容易是"凑巧命中两三个弱峰"的卡片（实测 synth_02 第 3 轮 FoM≈0.71
        # 命中 Ca2KNb3O10，全部峰已解释 95.5%）。给一句判据，别让用户以为那是
        # 一个真物相。
        if result.covered_fraction >= 0.90:
            note += "；已解释 ≥90% 强度，剩余多为弱峰，无明确命中即可结束鉴定"
        if not result.candidates:
            message = (
                f"剩余 {result.n_residual_peaks} 个峰中没有可匹配的候选{note}"
            )
        else:
            message = (
                f"剩余峰检索完成：{result.n_residual_peaks} 个未解释峰 → "
                f"{len(result.candidates)} 个候选"
                f"（已解释 {result.covered_fraction * 100:.1f}% 强度）{note}"
            )
        self.statusBar().showMessage(message, 12000)

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
        # §35：候选行数上限换算 fetch（FPFM 侧 prescreen 名额不动，
        # 只放大最终返回切片，成本增量≈0）。
        fetch, _ = _candidate_row_budget()
        raw = search_match_fpfm(
            pattern,
            conn,
            wavelength_kalpha1=ka1,
            wavelength_kalpha2=ka2,
            top_n=fetch,
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
        # §35：报告渲染与表格显示同源——候选表按行数上限截断（折叠时
        # 一行 ≈ 一个相族），报告里也应只出现用户能看到的行；
        # visible_results() 为空（理论不可达，截断上限 ≥1）时回退全量。
        report_candidates = (
            self.candidate_table.visible_results() or list(self._candidates)
        )
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
                    for c in report_candidates
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
