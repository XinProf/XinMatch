"""浅色 / 深色主题与语义图标（现代化重写）。

T13.7 — 浅/深两套主题（``QPalette`` + 全局 QSS）；图标转发至
:mod:`xinmatch.ui.icons` 的原创 SVG 图标库。

设计要点
--------
* 所有颜色集中在 :data:`THEMES` 的语义令牌 dict 中（bg/base/text/accent/
  selection/border/button 等 + 图谱区 chart_bg/chart_grid/chart_axis/
  chart_cursor/chart_text），表格、周期表、对话框、谱图视图等后续控件一律
  从这里取色，不在各控件散落硬编码。
* :func:`apply_theme` 同时设置 ``QPalette`` 与 QSS，保证基础控件在两主题下
  前景 / 背景对比度达标；QSS 采用现代扁平圆角风格（border-radius、
  hover / pressed 态、统一字体栈与控件密度）。
* 图标 :func:`icon` 转发到 :func:`xinmatch.ui.icons.icon`（原创自绘 SVG，
  净室实现，不复制任何商业软件的图标或视觉资源）。
"""

from __future__ import annotations

from PySide6 import QtGui, QtWidgets

#: 语义令牌：浅/深两套集中定义。key 为语义角色，value 为 #RRGGBB。
THEMES: dict[str, dict[str, str]] = {
    "light": {
        # —— 通用 UI ——
        "bg": "#f5f7fa",            # 窗口背景（近白浅灰）
        "base": "#ffffff",          # 输入/视图控件底色
        "alt_base": "#e9edf2",      # 交替行 / 停靠区标题
        "text": "#1f2733",          # 主文本
        "secondary_text": "#5b6675",  # 次要文本
        "accent": "#0b6bcb",        # 强调色（现代蓝）
        "accent_hover": "#1a7add",  # 强调色 hover
        "selection": "#0b6bcb",     # 高亮/选中背景
        "selection_text": "#ffffff",  # 高亮上的文本
        "border": "#cdd5df",        # 边框
        "button": "#ffffff",        # 按钮面
        "button_hover": "#eaf2fb",  # 按钮 hover
        "button_pressed": "#d7e6f5",  # 按钮 pressed
        "tooltip_bg": "#fffbe6",    # 工具提示
        "tooltip_text": "#3a3a2a",
        # —— 谱图区（pattern_view 取色）——
        "chart_bg": "#ffffff",      # 谱图背景（近白，严禁黑）
        "chart_grid": "#e2e8f0",    # 网格
        "chart_axis": "#8a94a3",    # 坐标轴 / 刻度文本
        "chart_cursor": "#5b6675",  # crosshair 虚线
        "chart_text": "#334155",    # 读数标注
    },
    "dark": {
        # —— 通用 UI ——
        "bg": "#1e2128",            # 窗口背景（深灰，非纯黑）
        "base": "#262a33",          # 输入/视图控件底色
        "alt_base": "#2f343f",      # 交替行 / 停靠区标题
        "text": "#e6eaf0",          # 主文本
        "secondary_text": "#9aa4b2",  # 次要文本
        "accent": "#5aa9ff",        # 强调色（亮蓝，深底上醒目）
        "accent_hover": "#7abaff",
        "selection": "#2b5d99",     # 高亮/选中背景（深底上的蓝）
        "selection_text": "#f2f7ff",
        "border": "#3a404c",        # 边框
        "button": "#2a2f3a",        # 按钮面
        "button_hover": "#353c49",
        "button_pressed": "#404856",
        "tooltip_bg": "#3a3520",
        "tooltip_text": "#f0ead0",
        # —— 谱图区（深灰但非纯黑）——
        "chart_bg": "#2a2e37",
        "chart_grid": "#3d434f",
        "chart_axis": "#7d8794",
        "chart_cursor": "#a7b0bc",
        "chart_text": "#d7dee8",
    },
}

#: 当前主题名（模块级状态；由 apply_theme 更新）。
_CURRENT_THEME: str = "light"

#: 统一字体栈（现代无衬线）。
_FONT_FAMILY = '"Microsoft YaHei UI", "Segoe UI", "PingFang SC", sans-serif'


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
    pal.setColor(QtGui.QPalette.ColorRole.BrightText, QtGui.QColor("#ff6b6b"))
    return pal


def _build_qss(t: dict[str, str]) -> str:
    """由语义令牌构造全局 QSS（现代扁平圆角风格，覆盖常见基础控件）。"""
    return f"""
* {{ font-family: {_FONT_FAMILY}; font-size: 9pt; }}
QWidget {{ color: {t['text']}; background: transparent; }}
QMainWindow, QDialog, QMessageBox {{ background: {t['bg']}; }}

/* 工具提示 */
QToolTip {{
    background: {t['tooltip_bg']}; color: {t['tooltip_text']};
    border: 1px solid {t['border']}; border-radius: 4px; padding: 3px 6px;
}}

/* 菜单栏 / 菜单 */
QMenuBar {{ background: {t['bg']}; color: {t['text']}; padding: 2px; }}
QMenuBar::item {{
    background: transparent; padding: 5px 10px; border-radius: 4px;
}}
QMenuBar::item:selected {{ background: {t['button_hover']}; }}
QMenu {{
    background: {t['base']}; color: {t['text']};
    border: 1px solid {t['border']}; border-radius: 6px; padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px 6px 20px; border-radius: 4px;
}}
QMenu::item:selected {{ background: {t['button_hover']}; color: {t['text']}; }}
QMenu::separator {{ height: 1px; background: {t['border']}; margin: 4px 8px; }}

/* 按钮 */
QPushButton {{
    background: {t['button']}; color: {t['text']};
    border: 1px solid {t['border']}; border-radius: 5px;
    padding: 5px 14px; min-height: 20px;
}}
QPushButton:hover {{ background: {t['button_hover']}; border-color: {t['accent']}; }}
QPushButton:pressed {{ background: {t['button_pressed']}; }}
QPushButton:disabled {{ color: {t['secondary_text']}; background: {t['bg']}; }}
QPushButton[default="true"] {{ border-color: {t['accent']}; color: {t['accent']}; }}

/* 输入控件 */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit {{
    background: {t['base']}; color: {t['text']};
    border: 1px solid {t['border']}; border-radius: 4px; padding: 3px 6px;
    selection-background-color: {t['selection']}; selection-color: {t['selection_text']};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {t['accent']};
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background: {t['base']}; color: {t['text']};
    border: 1px solid {t['border']}; selection-background-color: {t['button_hover']};
}}

/* 表格 */
QTableView, QTableWidget, QListView, QTreeView {{
    background: {t['base']}; color: {t['text']};
    gridline-color: {t['border']}; border: 1px solid {t['border']};
    border-radius: 4px;
    selection-background-color: {t['selection']}; selection-color: {t['selection_text']};
}}
QTableView::item, QTableWidget::item {{ padding: 2px 4px; }}
QTableView::item:selected, QTableWidget::item:selected {{
    background: {t['selection']}; color: {t['selection_text']};
}}
QHeaderView::section {{
    background: {t['alt_base']}; color: {t['text']};
    border: none; border-right: 1px solid {t['border']};
    border-bottom: 1px solid {t['border']}; padding: 5px 8px;
}}
QHeaderView::section:hover {{ background: {t['button_hover']}; }}

/* 选项卡 */
QTabWidget::pane {{
    border: 1px solid {t['border']}; border-radius: 4px; top: -1px;
    background: {t['base']};
}}
QTabBar::tab {{
    background: {t['alt_base']}; color: {t['secondary_text']};
    border: 1px solid {t['border']}; border-bottom: none;
    border-top-left-radius: 5px; border-top-right-radius: 5px;
    padding: 6px 14px; margin-right: 2px;
}}
QTabBar::tab:selected {{ background: {t['base']}; color: {t['accent']}; }}
QTabBar::tab:hover {{ color: {t['text']}; }}

/* 停靠面板 / 状态栏 */
QDockWidget {{
    color: {t['text']}; titleBarShown: true;
}}
QDockWidget::title {{
    background: {t['alt_base']}; color: {t['text']};
    border: 1px solid {t['border']}; border-radius: 4px;
    padding: 5px 8px; margin-bottom: 2px;
}}
QStatusBar {{ background: {t['alt_base']}; color: {t['secondary_text']}; }}
QStatusBar::item {{ border: none; }}

/* 工具栏 */
QToolBar {{
    background: {t['bg']}; border: none; spacing: 4px; padding: 4px;
}}
QToolBar::separator {{ background: {t['border']}; width: 1px; margin: 4px 6px; }}
QToolBar QToolButton {{
    background: transparent; border: none; border-radius: 5px; padding: 4px 6px;
}}
QToolBar QToolButton:hover {{ background: {t['button_hover']}; }}
QToolBar QToolButton:pressed {{ background: {t['button_pressed']}; }}
QToolBar QToolButton:checked {{ background: {t['button_pressed']}; }}

/* 分组框 */
QGroupBox {{
    border: 1px solid {t['border']}; border-radius: 6px;
    margin-top: 10px; padding-top: 8px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top left;
    left: 8px; padding: 0 4px; color: {t['accent']};
}}

/* 滚动条 */
QScrollBar:vertical {{
    background: transparent; width: 12px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {t['border']}; border-radius: 6px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {t['secondary_text']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent; height: 12px; margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {t['border']}; border-radius: 6px; min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: {t['secondary_text']}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
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
    """按动作名返回原创 SVG 图标（转发到 :func:`xinmatch.ui.icons.icon`）。

    Args:
        name: 图标名，如 ``"open"/"save"/"run"/"reset"/"search"/"help"`` 等；
            未知名回退通用图标，绝不返回空图标。
        theme: ``"light"``（默认）或 ``"dark"``，透传以选择图标配色。
    """
    from xinmatch.ui.icons import icon as _svg_icon

    return _svg_icon(name, theme)
