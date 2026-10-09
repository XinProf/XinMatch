"""浅色 / 深色主题与语义图标。

T13.7 — 浅/深两套主题（``QPalette`` + 全局 QSS）与 Qt 标准图标封装。

设计要点
--------
* 所有颜色集中在 :data:`THEMES` 的语义令牌 dict 中（bg/base/text/accent/
  selection/border/button 等），表格、周期表、对话框等后续控件一律从这里
  取色，不在各控件散落硬编码。
* :func:`apply_theme` 同时设置 ``QPalette`` 与 QSS，保证基础控件
  （QWidget/QTableView/QDockWidget/QTabWidget/QMenu/QDialog/QPushButton/
  QTableWidget 等）在两主题下前景/背景对比度达标。
* 图标 :func:`icon` 一律使用 Qt 内置 ``QStyle.StandardPixmap``（LGPL，随
  Qt 分发），**不复制 Match! 的任何图标或视觉资源**。``theme`` 参数为后续
  引入自绘/SVG 图标预留，当前标准图标随系统 palette 自适应。
"""

from __future__ import annotations

from PySide6 import QtGui, QtWidgets

#: 语义令牌：浅/深两套集中定义。key 为语义角色，value 为 #RRGGBB。
THEMES: dict[str, dict[str, str]] = {
    "light": {
        "bg": "#ffffff",            # 窗口背景
        "base": "#ffffff",          # 输入/视图控件底色
        "alt_base": "#f0f0f0",       # 交替行 / 停靠区标题
        "text": "#1f1f1f",          # 主文本
        "secondary_text": "#555555",  # 次要文本
        "accent": "#0b6bcb",        # 强调色
        "selection": "#0b6bcb",     # 高亮/选中背景
        "selection_text": "#ffffff",  # 高亮上的文本
        "border": "#c8c8c8",        # 边框
        "button": "#e6e6e6",        # 按钮面
        "tooltip_bg": "#ffffe0",
        "tooltip_text": "#000000",
    },
    "dark": {
        "bg": "#1e1e1e",
        "base": "#252526",
        "alt_base": "#2d2d30",
        "text": "#e8e8e8",
        "secondary_text": "#b8b8b8",
        "accent": "#3da9fc",
        "selection": "#3da9fc",
        "selection_text": "#101418",
        "border": "#3c3c3c",
        "button": "#333337",
        "tooltip_bg": "#333333",
        "tooltip_text": "#e8e8e8",
    },
}

#: 当前主题名（模块级状态；由 apply_theme 更新）。
_CURRENT_THEME: str = "light"

#: 动作名 → Qt 标准图标枚举（无 Match! 资源）。
_STANDARD_ICONS: dict[str, QtWidgets.QStyle.StandardPixmap] = {
    "new": QtWidgets.QStyle.SP_FileIcon,
    "open": QtWidgets.QStyle.SP_DialogOpenButton,
    "save": QtWidgets.QStyle.SP_DialogSaveButton,
    "save_as": QtWidgets.QStyle.SP_DialogSaveButton,
    "print": QtWidgets.QStyle.SP_FileDialogDetailedView,
    "run": QtWidgets.QStyle.SP_MediaPlay,
    "reset": QtWidgets.QStyle.SP_DialogResetButton,
    "search": QtWidgets.QStyle.SP_BrowserReload,
    "undo": QtWidgets.QStyle.SP_ArrowBack,
    "redo": QtWidgets.QStyle.SP_ArrowForward,
    "delete": QtWidgets.QStyle.SP_DialogDiscardButton,
    "help": QtWidgets.QStyle.SP_DialogHelpButton,
    "quit": QtWidgets.QStyle.SP_DialogCloseButton,
}


def _build_palette(t: dict[str, str]) -> QtGui.QPalette:
    """由语义令牌构造 QPalette。"""
    pal = QtGui.QPalette()
    pal.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(t["bg"]))
    pal.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(t["text"]))
    pal.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(t["base"]))
    pal.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor(t["alt_base"]))
    pal.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(t["text"]))
    pal.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(t["button"]))
    pal.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(t["text"]))
    pal.setColor(QtGui.QPalette.ColorRole.PlaceholderText, QtGui.QColor(t["secondary_text"]))
    pal.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(t["selection"]))
    pal.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor(t["selection_text"]))
    pal.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor(t["tooltip_bg"]))
    pal.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtGui.QColor(t["tooltip_text"]))
    pal.setColor(QtGui.QPalette.ColorRole.Link, QtGui.QColor(t["accent"]))
    pal.setColor(QtGui.QPalette.ColorRole.BrightText, QtGui.QColor("#ff5f5f"))
    return pal


def _build_qss(t: dict[str, str]) -> str:
    """由语义令牌构造全局 QSS，覆盖常见基础控件。"""
    return f"""
QWidget {{ color: {t['text']}; }}
QMainWindow, QDialog {{ background: {t['bg']}; }}
QToolTip {{ background: {t['tooltip_bg']}; color: {t['tooltip_text']};
            border: 1px solid {t['border']}; }}
QMenuBar {{ background: {t['bg']}; color: {t['text']}; }}
QMenuBar::item:selected {{ background: {t['selection']}; color: {t['selection_text']}; }}
QMenu {{ background: {t['bg']}; color: {t['text']}; border: 1px solid {t['border']}; }}
QMenu::item:selected {{ background: {t['selection']}; color: {t['selection_text']}; }}
QPushButton {{ background: {t['button']}; color: {t['text']};
               border: 1px solid {t['border']}; padding: 4px 12px; border-radius: 3px; }}
QPushButton:pressed {{ background: {t['border']}; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {t['base']}; color: {t['text']}; border: 1px solid {t['border']};
}}
QTableView, QTableWidget {{
    background: {t['base']}; color: {t['text']}; gridline-color: {t['border']};
    selection-background-color: {t['selection']}; selection-color: {t['selection_text']};
}}
QHeaderView::section {{
    background: {t['button']}; color: {t['text']}; border: 1px solid {t['border']};
}}
QTabWidget::pane {{ border: 1px solid {t['border']}; }}
QTabBar::tab {{ background: {t['button']}; color: {t['text']}; padding: 4px 10px; }}
QTabBar::tab:selected {{ background: {t['base']}; }}
QDockWidget::title {{ background: {t['alt_base']}; color: {t['text']}; }}
QStatusBar {{ background: {t['alt_base']}; color: {t['text']}; }}
"""


def apply_theme(target: QtWidgets.QApplication | QtWidgets.QWidget, name: str) -> None:
    """对 ``target`` 应用指定主题（QPalette + QSS）。

    Args:
        target: ``QApplication``（全局生效）或某个 ``QWidget``（如主窗口）。
        name: ``"light"`` 或 ``"dark"``；其他值抛 :class:`ValueError`。
    """
    global _CURRENT_THEME
    if name not in THEMES:
        raise ValueError(f"未知主题: {name!r}（可选: {sorted(THEMES)}）")
    tokens = THEMES[name]
    target.setPalette(_build_palette(tokens))
    target.setStyleSheet(_build_qss(tokens))
    _CURRENT_THEME = name


def current_theme() -> str:
    """返回最近一次 :func:`apply_theme` 设置的主题名（默认 ``"light"``）。"""
    return _CURRENT_THEME


def icon(name: str, theme: str = "light") -> QtGui.QIcon:
    """按动作名返回图标（Qt 内置标准图标，无外部资源）。

    Args:
        name: 动作名，如 ``"open"/"save"/"run"/"reset"/"search"`` 等；
            未知名回退到文件图标。
        theme: 预留参数（浅/深）；当前标准图标随 palette 自适应，不区分。
    """
    del theme  # 标准图标自适应 palette；保留参数以备 SVG 自绘扩展
    style = QtWidgets.QApplication.style()
    pix = _STANDARD_ICONS.get(name, QtWidgets.QStyle.SP_FileIcon)
    return style.standardIcon(pix)
