"""图标预览工具：把 :mod:`xinmatch.ui.icons` 的图标按真实显示尺寸渲染成 PNG。

用途
----
图标库（``xinmatch/ui/icons.py``）是手写 SVG 路径，改动后需要**目视验证**
小尺寸下的可读性。本脚本用离屏 Qt 渲染下列对照图，输出到 ``build/``：

* ``build/icons_toolbar.png`` —— 主工具栏用到的 14 个图标（16 / 24 / 48 px 三行）；
* ``build/icons_all.png``     —— 其余图标（同上三行）；
* ``build/toolbar_light.png`` / ``build/toolbar_dark.png``
  —— 真实 ``MainWindow`` 工具栏在浅 / 深主题下的截图（验证尺寸与配色）。

用法（在项目根目录下）::

    QT_QPA_PLATFORM=offscreen python tools/render_icons.py

说明：仅用于开发期目视核对，不参与打包与测试。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtGui, QtWidgets  # noqa: E402

from xinmatch.ui import icons  # noqa: E402

#: 主工具栏实际使用的图标（顺序与 ``MainWindow._build_toolbar`` 一致）。
TOOLBAR_ICONS: tuple[str, ...] = (
    "open", "export", "background", "smooth", "ko2", "reset", "peakdetect",
    "search", "profile", "rietveld", "wizard", "codsearch", "report", "options",
)

#: 其余图标（菜单 / 对话框用）。
OTHER_ICONS: tuple[str, ...] = tuple(
    name for name in sorted(icons.ICON_NAMES) if name not in TOOLBAR_ICONS
)

#: 对照图配色（浅色主题；深色主题由工具栏截图覆盖）。
_SHEET_THEME = "light"
_SHEET_SIZES = (16, 24, 48)


def render_sheet(names: tuple[str, ...], out_path: Path) -> None:
    """把 ``names`` 按 :data:`_SHEET_SIZES` 各渲染一行，拼成对照图。"""
    cell_w, cell_h = 58, 66
    img = QtGui.QImage(
        cell_w * len(names), cell_h * len(_SHEET_SIZES), QtGui.QImage.Format.Format_ARGB32
    )
    img.fill(QtGui.QColor("#ffffff"))
    painter = QtGui.QPainter(img)
    for row, size in enumerate(_SHEET_SIZES):
        base = row * cell_h
        for col, name in enumerate(names):
            body = icons._BODIES.get(icons.resolve_icon_name(name), icons._FALLBACK_BODY)
            pixmap = icons._render_pixmap(body, _SHEET_THEME, size)
            painter.drawPixmap(col * cell_w + (cell_w - size) // 2, base + 6, pixmap)
    painter.end()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out_path))
    print(f"已输出 {out_path}")


def render_toolbar_shots(out_dir: Path) -> None:
    """截取真实主窗口工具栏（浅 / 深两主题）。"""
    from xinmatch.ui.main_window import MainWindow

    win = MainWindow()
    win.show()
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()
    toolbar = win.findChild(QtWidgets.QToolBar, "mainToolbar")
    if toolbar is None:  # pragma: no cover - 结构性兜底
        print("未找到 mainToolbar，跳过工具栏截图", file=sys.stderr)
        return
    toolbar.grab().save(str(out_dir / "toolbar_light.png"))
    win._toggle_theme()
    if app is not None:
        app.processEvents()
    toolbar.grab().save(str(out_dir / "toolbar_dark.png"))
    print(f"已输出 {out_dir / 'toolbar_light.png'} 与 toolbar_dark.png")


def main() -> None:
    app = QtWidgets.QApplication([])  # noqa: F841
    out_dir = Path(__file__).resolve().parents[1] / "build"
    render_sheet(TOOLBAR_ICONS, out_dir / "icons_toolbar.png")
    render_sheet(OTHER_ICONS, out_dir / "icons_all.png")
    render_toolbar_shots(out_dir)


if __name__ == "__main__":
    main()
