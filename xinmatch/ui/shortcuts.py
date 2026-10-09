"""全局快捷键映射与主窗口注册。

T13.6 — 对照 ``docs/function_keys.md`` 的 "Table of Key Combinations and
Commands"（命令型快捷键）建立全量映射，并可在主窗口上生效。

映射方式说明
------------
本模块采用 **QAction 方式** 而非裸 ``QShortcut``：为每条快捷键创建一个
``QAction``（``setShortcut`` + ``WindowShortcut`` 上下文），再
``window.addAction(action)``。这样既与 :class:`~xinmatch.ui.main_window.MainWindow`
既有的 ``module_actions`` 体系自然融合，也使"触发快捷键"等价于
``action.trigger()``——便于 offscreen 测试确定性验证回调生效。

默认行为
--------
``install_shortcuts(window, callbacks)`` 注册每条快捷键时：

* 若该条目在 ``callbacks`` 中注入了回调，则触发时执行注入回调（测试与后续
  接线均走此通道）；
* 否则默认尝试触发 ``window.module_actions[entry.module_id]``（若存在），
  即与 ``main_window.MODULES`` 的模块占位动作直接联动；
* ``module_id == ""`` 的条目（全局/视图/编辑类命令，如 New/Quit/Undo/
  光标竖线开关/列表方向键等）默认无动作，等待 Organizer 注入回调。

键序列冲突
----------
按文档逐条核对，全部命令型键序列彼此不重复（无冲突需特殊处理）。
注意 ``Ctrl+X`` 在文档的"鼠标+键"表与"命令"表中均出现，效果一致
（切换光标处竖线），此处只注册一次。Mac 平台的 Ctrl→Cmd 替换由 Qt 原生
处理，本文件不重复维护。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import NamedTuple

from PySide6 import QtCore, QtGui, QtWidgets


class Shortcut(NamedTuple):
    """一条快捷键映射。

    Attributes:
        name: 短横线小写下的稳定标识（dict key / 测试引用）。
        sequence: ``QKeySequence`` 可解析的键序列字符串，如 ``"Ctrl+M"``。
        description: 功能中文简述（取自文档 Effect 列）。
        menu: 对应 Match! 菜单命令路径（取自文档 Menu command 列）。
        module_id: 关联的 ``main_window.MODULES`` 模块 id；``""`` 表示
            全局/视图/编辑类命令，无对应模块动作。
    """

    name: str
    sequence: str
    description: str
    menu: str
    module_id: str


#: 全量快捷键映射，逐条对照 docs/function_keys.md 命令表。
SHORTCUTS: tuple[Shortcut, ...] = (
    # ---- 文件 / 全局 ----
    Shortcut("new_session", "Ctrl+N", "新建（空）文档/会话", "File/New", ""),
    Shortcut("open_session", "Ctrl+O", "打开文档或导入第一张图谱", "File/Open", "data_import"),
    Shortcut("save_session", "Ctrl+S", "保存当前会话", "File/Save", "data_export"),
    Shortcut("save_session_as", "Ctrl+Shift+S", "另存会话为新文件", "File/Save as...", "data_export"),
    Shortcut("print_dialog", "Ctrl+P", "打开打印对话框", "File/Print...", "report_print"),
    Shortcut("quit", "Ctrl+Q", "退出 XinMatch", "File/Quit", ""),
    Shortcut("import_predefined_selection", "Ctrl+Shift+O",
             "从 .mta 文件直接载入预定义匹配物相", "File/Import/Predefined phase selection", "data_import"),
    Shortcut("finish_batch", "Ctrl+W", "执行批处理收尾动作并退出", "Entry/Finish", ""),
    # ---- 编辑 ----
    Shortcut("undo", "Ctrl+Z", "撤销上一步", "Edit/Undo", ""),
    Shortcut("redo", "Ctrl+Y", "重做撤销的操作", "Edit/Redo", ""),
    Shortcut("copy_pattern", "Ctrl+C", "复制当前图谱到剪贴板", "Edit/Copy", "data_export"),
    Shortcut("paste_pattern", "Ctrl+V", "将剪贴板文本数据作为新实验图谱粘贴", "Edit/Paste diffraction pattern", "data_import"),
    Shortcut("delete_marked", "Del", "删除当前选中项（峰/候选条目等）", "Edit/Delete", ""),
    # ---- 原始数据处理 / 背景 / 平滑 ----
    Shortcut("auto_raw_data_processing", "Ctrl+A", "自动原始数据处理", "Pattern/Automatic/Autom. raw data proc.", "raw_processing"),
    Shortcut("configure_auto_processing", "Ctrl+Alt+A", "配置自动原始数据处理各步骤", "Pattern/Automatic/Configure...", "raw_processing"),
    Shortcut("edit_background", "Ctrl+Shift+B", "编辑背景（背景控制点）", "Pattern/Background/Edit background", "raw_processing"),
    Shortcut("background_flexibility_up", "Ctrl+F2", "提高自动背景曲线跟随性", "Pattern/Background/Increase flexibility", "raw_processing"),
    Shortcut("background_flexibility_down", "Ctrl+F3", "降低自动背景曲线跟随性", "Pattern/Background/Decrease flexibility", "raw_processing"),
    Shortcut("background_intensity_up", "Ctrl+Shift+F2", "抬升背景强度（+0.5）", "Pattern/Background/Raise background intensity", "raw_processing"),
    Shortcut("background_intensity_down", "Ctrl+Shift+F3", "降低背景强度（-0.5）", "Pattern/Background/Lower background intensity", "raw_processing"),
    Shortcut("smooth_raw_data", "Ctrl+F4", "平滑原始数据", "Pattern/Smooth raw data", "raw_processing"),
    Shortcut("correct_zero_point", "Ctrl+Shift+C", "校正零点误差（2θ 偏移）", "Pattern/Correct zero-point error", "raw_processing"),
    Shortcut("import_overlay", "Ctrl+I", "导入（叠加）另一张衍射图谱", "Pattern/Insert/overlay...", "data_import"),
    # ---- 寻峰 / 峰列表 ----
    Shortcut("peak_search", "Ctrl+K", "常规寻峰（二阶导数法）", "Pattern/Peak searching/Peak search", "peak_list"),
    Shortcut("add_peaks_manually", "Alt+K", "手动输入峰参数添加峰", "Peaks/Add peak(s)", "peak_list"),
    Shortcut("delete_all_peaks", "Shift+Del", "删除当前实验图谱的全部峰", "Peaks/Delete all peaks", "peak_list"),
    Shortcut("peak_sensitivity_up", "F2", "提高寻峰灵敏度", "Pattern/Peak searching/Increase sensitivity", "peak_list"),
    Shortcut("peak_sensitivity_down", "F3", "降低寻峰灵敏度", "Pattern/Peak searching/Reduce sensitivity", "peak_list"),
    Shortcut("optimize_sensitivity", "F4", "优化寻峰灵敏度使重叠最佳", "Pattern/Peak searching/Optimize sensitivity", "peak_list"),
    Shortcut("peak_list_view", "Ctrl+L", "以表格查看全部实验/参考峰", "View/Peak list", "peak_list"),
    # ---- Profile Fitting ----
    Shortcut("profile_fit", "F5", "执行 profile fitting", "Pattern/Profile fitting/Profile fit", "profile_fitting"),
    Shortcut("fit_2theta", "F6", "开关拟合 2θ", "Pattern/Profile fitting/Fit 2theta", "profile_fitting"),
    Shortcut("fit_intensities", "F7", "开关拟合强度", "Pattern/Profile fitting/Fit intensities", "profile_fitting"),
    Shortcut("fit_fwhm", "F8", "开关拟合 FWHM", "Pattern/Profile fitting/Fit FWHM", "profile_fitting"),
    # ---- Search-Match / 候选与匹配列表 ----
    Shortcut("find_entry", "Ctrl+F", "按限制条件查找最佳物相", "Search/Find phase/entry(s)", "search_match"),
    Shortcut("find_next", "Ctrl+G", "查找下一个最佳候选", "Search/Find next", "search_match"),
    Shortcut("find_previous", "Ctrl+Shift+G", "查找上一个候选", "Search/Find previous", "search_match"),
    Shortcut("hanawalt_search", "Ctrl+H", "Hanawalt 强线检索", "-", "search_match"),
    Shortcut("add_entry_to_match_list", "Ctrl+E", "按名称/化学式/编号直接加入匹配列表", "Search/Add entry to match list directly", "search_match"),
    Shortcut("search_match", "Ctrl+M", "运行 Search-Match（基于峰的常规法）", "Search/Search-Match", "search_match"),
    Shortcut("search_match_profile", "Ctrl+Alt+M", "运行 profile-fitting 型 Search-Match", "Search/Search-match using profile fitting", "search_match"),
    Shortcut("search_match_marked", "Ctrl+Shift+M", "仅基于当前标记峰运行 Search-Match", "Search/Search-Match (marked peaks only)", "search_match"),
    Shortcut("reset_restraints", "Ctrl+B", "清空当前选择条件（限制）", "Search/Reset restraints/additional entries", "restraints"),
    Shortcut("internal_standard", "Ctrl+T", "内标法平移实验图谱对齐参考", "Entries/Internal standard", "search_match"),
    Shortcut("load_as_experimental", "Ctrl+Shift+T", "把候选参考条目作为新实验图谱载入", "Entries/Load as experimental", "data_import"),
    Shortcut("unify_phases", "Ctrl+U", "每相仅保留最佳 FoM 条目", "Entries/Unify phases", "search_match"),
    Shortcut("select_as_matching", "Space", "把当前候选条目选为匹配物相", "Entries/Select as matching", ""),
    Shortcut("select_copy_as_matching", "Alt+Space", "复制为手动匹配条目并选中", "Entries/Select/add copy as manual matching entry", ""),
    Shortcut("list_cursor_up", "Up", "候选/匹配列表中向上移动行标记", "-", ""),
    Shortcut("list_cursor_down", "Down", "候选/匹配列表中向下移动行标记", "-", ""),
    # ---- 数据库 ----
    Shortcut("add_to_reference_db", "Ctrl+Shift+A", "直接向参考数据库添加条目", "Database/Add to reference database", "reference_db"),
    # ---- Rietveld / 定量 ----
    Shortcut("rietveld_turn_on", "Ctrl+Shift+R", "打开参数开关对话框以运行 Rietveld", "Tools/Rietveld (FullProf)", "rietveld"),
    Shortcut("auto_quant_analysis", "Ctrl+Alt+Q", "自动定量分析（默认 RIR/Rietveld）", "-", "quant_analysis"),
    Shortcut("quant_rietveld", "Ctrl+Alt+R", "自动 Rietveld 精修并显示组成饼图", "Quantify/Rietveld (FullProf)", "quant_analysis"),
    # ---- 视图 / 显示开关 ----
    Shortcut("view_data_sheet", "Ctrl+D", "查看当前条目数据表", "View/Data sheet", "report_print"),
    Shortcut("report_view", "Ctrl+R", "显示物相分析报告", "View/Report", "report_print"),
    Shortcut("toggle_cursor_line", "Ctrl+X", "开关光标处竖线（峰位对比）", "View/Pattern/Cursor position", ""),
    Shortcut("toggle_xray_spectral_lines", "Ctrl+Shift+X", "开关 X 射线谱线竖线显示", "View/Pattern/X-ray spectral lines", ""),
    Shortcut("toggle_uncorrelated_peaks", "Ctrl+Shift+U", "开关显示未归属峰（浅橙底）", "View/Pattern/Uncorrelated peaks", "options"),
    Shortcut("decrease_vertical_distance", "Ctrl+-", "减小堆叠图谱纵向间距", "View/Pattern distance (3D)/Reduce vertical distance", ""),
    Shortcut("increase_vertical_distance", "Ctrl++", "增大堆叠图谱纵向间距", "View/Pattern distance (3D)/Increase vertical distance", ""),
    Shortcut("decrease_horizontal_distance", "Ctrl+Shift+-", "减小堆叠图谱横向间距", "View/Pattern distance (3D)/Reduce horizontal distance", ""),
    Shortcut("increase_horizontal_distance", "Ctrl+Shift++", "增大堆叠图谱横向间距", "View/Pattern distance (3D)/Increase horizontal distance", ""),
    Shortcut("previous_zoom", "Ctrl+<", "返回上一次缩放", "View/Previous zoom", ""),
    Shortcut("pattern_options", "Ctrl+Alt+G", "衍射图谱选项对话框", "Options/Diffraction pattern options...", "options"),
    # ---- 帮助 ----
    Shortcut("help_shortcuts", "Ctrl+J", "在线帮助：鼠标与快捷键操作", "Help/Keyboard shortcuts and mouse operations", ""),
    Shortcut("help_index", "F1", "打开帮助索引", "Help/Index", ""),
)


def _make_handler(
    window: QtWidgets.QMainWindow,
    entry: Shortcut,
    callback: Callable[[], None] | None,
) -> Callable[[bool], None]:
    """构造单个快捷键的触发槽：优先注入回调，否则联动模块占位动作。"""

    def handler(_checked: bool = False) -> None:
        if callback is not None:
            callback()
            return
        actions = getattr(window, "module_actions", None)
        if actions and entry.module_id in actions:
            actions[entry.module_id].trigger()

    return handler


def install_shortcuts(
    window: QtWidgets.QMainWindow,
    callbacks: Mapping[str, Callable[[], None]] | None = None,
) -> dict[str, QtGui.QAction]:
    """把 :data:`SHORTCUTS` 全部注册到 ``window`` 上并生效。

    Args:
        window: 目标主窗口（通常为 :class:`~xinmatch.ui.main_window.MainWindow`，
            任何 ``QMainWindow`` 均可，便于测试）。
        callbacks: 可选的 ``{条目名: 无参回调}`` 注入表；未注入的条目按
            :func:`_make_handler` 的默认规则联动模块动作。若包含未知条目名，
            抛 :class:`KeyError`。

    Returns:
        ``{条目名: 已注册的 QAction}`` 字典；触发其中任一 action 即等价于
        按下对应快捷键。
    """
    known = {entry.name for entry in SHORTCUTS}
    if callbacks:
        unknown = set(callbacks) - known
        if unknown:
            raise KeyError(f"未知快捷键条目: {sorted(unknown)}（合法名见 SHORTCUTS）")

    registered: dict[str, QtGui.QAction] = {}
    for entry in SHORTCUTS:
        action = QtGui.QAction(entry.description, window)
        action.setObjectName(f"shortcut_{entry.name}")
        action.setShortcut(QtGui.QKeySequence(entry.sequence))
        action.setShortcutContext(QtCore.Qt.WindowShortcut)
        action.setStatusTip(entry.menu)
        callback = callbacks.get(entry.name) if callbacks else None
        action.triggered.connect(_make_handler(window, entry, callback))
        window.addAction(action)
        registered[entry.name] = action
    return registered
