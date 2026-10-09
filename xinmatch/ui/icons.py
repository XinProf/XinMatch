"""原创自绘 SVG 图标库（净室实现）。

所有图标均为抽象线条图形（文件夹 / 放大镜 / 齿轮 / 晶格 / 试管 / 谱图线 /
立方体等），**完全原创**，不复制、也不近似任何商业软件的图标或视觉资源。

实现选型
--------
渲染走 :class:`PySide6.QtSvg.QSvgRenderer` → ``QPainter`` → ``QPixmap``
（在 ``QT_QPA_PLATFORM=offscreen`` 环境下已验证渲染结果非空、像素正确）。
PySide6 6.11 的 ``QIcon`` 不接受裸 SVG 字节构造（仅支持文件名 / pixmap /
QIconEngine），因此不采用 ``QIcon(svg_bytes)`` 路线。

契约（并行任务按此调用）
------------------------
* :data:`ICON_NAMES` — 支持的图标名集合（frozenset）。
* :func:`icon` — 按名字取 ``QIcon``；``theme`` 选浅 / 深配色；未知名回退
  通用图标，**绝不为空**。
* :func:`is_svg_icon` — 名字是否在 :data:`ICON_NAMES` 中。
* :data:`MODULE_ICON_NAMES` — 主窗口模块 id → 图标名映射，保证工具栏 12 个
  动作全部有对应图标。
"""

from __future__ import annotations

from PySide6 import QtGui, QtSvg

# ---------------------------------------------------------------------------
# 配色（浅 / 深两套）。fg = 主线条色，accent = 强调点缀色。
# ---------------------------------------------------------------------------
_PALETTES: dict[str, dict[str, str]] = {
    "light": {"fg": "#3a4656", "accent": "#0b6bcb"},
    "dark": {"fg": "#dbe4ee", "accent": "#5aa9ff"},
}

# ---------------------------------------------------------------------------
# SVG 内联图形（24x24 viewBox，stroke 风格；{fg}/{accent} 在渲染时替换）。
# 所有图形为原创抽象符号，无语义上的商业资产复制。
# ---------------------------------------------------------------------------
_BODIES: dict[str, str] = {
    # 文件 / 文件夹
    "open": (
        '<path d="M3.5 7.5a2 2 0 0 1 2-2h3.6l1.8 1.8h7.6a2 2 0 0 1 2 2v8'
        'a2 2 0 0 1-2 2H5.5a2 2 0 0 1-2-2z"/>'
    ),
    "import": (
        '<path d="M4 5.5A1.5 1.5 0 0 1 5.5 4h3l1.5 1.5h5.5A1.5 1.5 0 0 1 17 7v1"/>'
        '<path d="M12 10v6m0 0l-3-3m3 3l3-3" stroke="{accent}"/>'
        '<path d="M4 19.5h16"/>'
    ),
    "export": (
        '<path d="M4 13.5A1.5 1.5 0 0 1 5.5 12h13A1.5 1.5 0 0 1 20 13.5v5'
        'A1.5 1.5 0 0 1 18.5 20h-13A1.5 1.5 0 0 1 4 18.5z"/>'
        '<path d="M12 14V8m0 0l-3 3m3-3l3 3" stroke="{accent}"/>'
    ),
    "save": (
        '<path d="M5 3.5h10L19.5 8v12.5H5z"/>'
        '<path d="M8 3.5V9h8V3.5"/>'
        '<path d="M8 20.5v-6.5h8v6.5"/>'
    ),
    "new": (
        '<path d="M6 3.5h8.5L19 8v12.5H6z"/>'
        '<path d="M9 13h6M12 10v6" stroke="{accent}"/>'
    ),
    "print": (
        '<path d="M7 8V3.5h10V8"/>'
        '<path d="M5 8h14v6H5z"/>'
        '<path d="M7 14v6.5h10V14"/>'
    ),
    # 谱图 / 数据处理
    "process": (
        '<path d="M4 7h9M17 7h3M4 12h3M13 12h7M4 17h11M19 17h1"/>'
        '<circle cx="15.5" cy="7" r="1.6" stroke="{accent}"/>'
        '<circle cx="10.5" cy="12" r="1.6" stroke="{accent}"/>'
        '<circle cx="17.5" cy="17" r="1.6" stroke="{accent}"/>'
    ),
    "peaklist": (
        '<path d="M3.5 20.5h17"/>'
        '<path d="M4.5 20.5l2.5-11 3 7 3-10 3 6 3-4 2.5 12" stroke="{accent}"/>'
    ),
    "profile": (
        '<path d="M3.5 19.5c4 0 4.2-14 8.5-14s4.5 14 8.5 14"/>'
        '<path d="M3.5 19.5h17"/>'
    ),
    "run": (
        '<path d="M7 4.5l12 7.5-12 7.5z" stroke="{accent}"/>'
    ),
    "reset": (
        '<path d="M4.5 12a7.5 7.5 0 1 1-2 5"/>'
        '<path d="M3.5 4v5.5H9" stroke="{accent}"/>'
    ),
    # 检索 / 数据库
    "search": (
        '<circle cx="10.5" cy="10.5" r="6.5"/>'
        '<path d="M20 20l-4.2-4.2" stroke="{accent}"/>'
    ),
    "restraints": (
        '<path d="M3.5 5h17l-6.5 7v5.5l-4 2.5V12z"/>'
    ),
    "database": (
        '<ellipse cx="12" cy="6" rx="7.5" ry="3"/>'
        '<path d="M4.5 6v12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3V6"/>'
        '<path d="M4.5 12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3"/>'
    ),
    "userdb": (
        '<ellipse cx="9" cy="5.5" rx="5.5" ry="2.4"/>'
        '<path d="M3.5 5.5v11c0 1.3 2.5 2.4 5.5 2.4s5.5-1.1 5.5-2.4v-4"/>'
        '<circle cx="17" cy="15" r="2.6" stroke="{accent}"/>'
        '<path d="M21 20.5c-.4-1.6-1.8-2.6-4-2.6s-3.6 1-4 2.6" stroke="{accent}"/>'
    ),
    # 计算 / 精修
    "build": (
        '<path d="M14.5 5.5a4.3 4.3 0 0 0-5.7 5.4L4 15.7 8.3 20l4.8-4.8'
        'a4.3 4.3 0 0 0 5.4-5.7l-3 3-2.7-2.7z"/>'
    ),
    "indexing": (
        '<path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4z" stroke-width="1.2"/>'
        '<path d="M15.5 15.5l4 4M19 15.5h.5v.5" stroke="{accent}"/>'
    ),
    "rietveld": (
        '<path d="M3.5 19.5h17"/>'
        '<path d="M5 19v-3M9 19v-5M13 19v-4M17 19v-6"/>'
        '<path d="M4 14c3-1 4.5-6 8-6.5s5 3.5 8 4.5" stroke="{accent}"/>'
    ),
    "quant": (
        '<circle cx="12" cy="12" r="8.5"/>'
        '<path d="M12 3.5V12l6 3.5" stroke="{accent}"/>'
    ),
    "microstructure": (
        '<path d="M12 3l7.8 4.5v9L12 21l-7.8-4.5v-9z"/>'
        '<circle cx="12" cy="12" r="1.4" fill="{accent}" stroke="{accent}"/>'
        '<circle cx="7.5" cy="9.5" r="1" fill="{fg}" stroke="{fg}"/>'
        '<circle cx="16.5" cy="9.5" r="1" fill="{fg}" stroke="{fg}"/>'
        '<circle cx="7.5" cy="14.5" r="1" fill="{fg}" stroke="{fg}"/>'
        '<circle cx="16.5" cy="14.5" r="1" fill="{fg}" stroke="{fg}"/>'
    ),
    "refine": (
        '<path d="M4 7h16M4 12h16M4 17h16"/>'
        '<circle cx="9" cy="7" r="1.7" stroke="{accent}"/>'
        '<circle cx="15" cy="12" r="1.7" stroke="{accent}"/>'
        '<circle cx="8" cy="17" r="1.7" stroke="{accent}"/>'
    ),
    # 输出 / 设置
    "report": (
        '<path d="M6 3.5h8.5L19 8v12.5H6z"/>'
        '<path d="M14.5 3.5V8H19"/>'
        '<path d="M9.5 12h5M9.5 15.5h5" stroke-width="1.2"/>'
    ),
    "options": (
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M12 2.8v2.6M12 18.6v2.6M2.8 12h2.6M18.6 12h2.6"'
        'M5.2 5.2l1.8 1.8M17 17l1.8 1.8M18.8 5.2L17 7M7 17l-1.8 1.8"'
        ' stroke-width="1.2"/>'
    ),
    "view3d": (
        '<path d="M12 2.5l8 4.6v9.8l-8 4.6-8-4.6V7.1z"/>'
        '<path d="M12 11l8-4.6M12 11L4 6.4M12 11v10.5" stroke-width="1.2"/>'
    ),
    "theme": (
        '<circle cx="12" cy="12" r="4"/>'
        '<path d="M12 3v2.2M12 18.8V21M3 12h2.2M18.8 12H21M5.6 5.6l1.6 1.6"'
        'M16.8 16.8l1.6 1.6M18.4 5.6l-1.6 1.6M7.2 16.8l-1.6 1.6"'
        ' stroke-width="1.2"/>'
    ),
    "pdf2": (
        '<path d="M6 3.5h8.5L19 8v12.5H6z"/>'
        '<path d="M8.5 15.5l2.5-5 2.5 5M9.2 14.3h3.6" stroke="{accent}" stroke-width="1.2"/>'
    ),
    "colors": (
        '<circle cx="8.5" cy="9" r="3" stroke="{accent}"/>'
        '<circle cx="15.5" cy="9" r="3"/>'
        '<circle cx="12" cy="15.5" r="3" stroke-width="1.2"/>'
    ),
    "help": (
        '<circle cx="12" cy="12" r="8.5"/>'
        '<path d="M9.6 9.2a2.5 2.5 0 1 1 3.4 2.4c-.8.4-1 .9-1 1.7"/>'
        '<path d="M12 17.2h.01" stroke-width="2.2"/>'
    ),
    "undo": ('<path d="M8 6L3 12l5 6"/><path d="M3.5 12H14a5.5 5.5 0 0 1 5.5 5.5V18"/>'),
    "redo": ('<path d="M16 6l5 6-5 6"/><path d="M20.5 12H10a5.5 5.5 0 0 0-5.5 5.5V18"/>'),
    "delete": (
        '<path d="M4.5 6h15M9.5 6V4h5v2M6.5 6l1 14h9l1-14"/>'
    ),
    "quit": ('<circle cx="12" cy="12" r="8.5"/><path d="M9 9l6 6M15 9l-6 6"/>'),
}

#: 未知名回退的通用图标（立方体轮廓）。
_FALLBACK_BODY = (
    '<path d="M12 3l7.5 4.3v9.4L12 21l-7.5-4.3V7.3z"/>'
    '<path d="M12 11.5l7.5-4.3M12 11.5L4.5 7.3" stroke-width="1.2"/>'
)

# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------

#: 全部受支持的图标名（frozenset，只读）。
ICON_NAMES: frozenset[str] = frozenset(_BODIES)

#: 主窗口模块 id → 图标名映射（覆盖全部 15 个 MODULES；工具栏 12 个在内）。
MODULE_ICON_NAMES: dict[str, str] = {
    "data_import": "import",
    "data_export": "export",
    "raw_processing": "process",
    "peak_list": "peaklist",
    "profile_fitting": "profile",
    "search_match": "search",
    "restraints": "restraints",
    "reference_db": "database",
    "user_db": "userdb",
    "indexing": "indexing",
    "rietveld": "rietveld",
    "quant_analysis": "quant",
    "microstructure": "microstructure",
    "report_print": "report",
    "options": "options",
}

#: 渲染尺寸（逻辑像素）。
_RENDER_SIZE = 48


def _build_svg(body: str, theme: str) -> bytes:
    """把图标内联图形套进模板并按主题着色，返回 SVG 字节。"""
    pal = _PALETTES.get(theme, _PALETTES["light"])
    colored = body.replace("{fg}", pal["fg"]).replace("{accent}", pal["accent"])
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'width="{_RENDER_SIZE}" height="{_RENDER_SIZE}" fill="none" '
        f'stroke="{pal["fg"]}" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round">'
        f"{colored}</svg>"
    )
    return svg.encode("utf-8")


def _render_pixmap(body: str, theme: str, size: int = _RENDER_SIZE) -> QtGui.QPixmap:
    """离屏把 SVG 渲染成 QPixmap（offscreen 安全）。"""
    svg_bytes = _build_svg(body, theme)
    renderer = QtSvg.QSvgRenderer(svg_bytes)
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtGui.QColor(0, 0, 0, 0))  # 透明底
    painter = QtGui.QPainter(pm)
    renderer.render(painter)
    painter.end()
    return pm


def is_svg_icon(name: str) -> bool:
    """``name`` 是否为受支持的 SVG 图标名。"""
    return name in _BODIES


def icon(name: str, theme: str = "light") -> QtGui.QIcon:
    """按图标名返回原创 ``QIcon``。

    Args:
        name: 图标名（见 :data:`ICON_NAMES`）；未知名回退通用立方体图标，
            绝不返回空图标。
        theme: ``"light"`` 或 ``"dark"``，选择线条 / 点缀配色。
    """
    body = _BODIES.get(name, _FALLBACK_BODY)
    pm = _render_pixmap(body, theme)
    return QtGui.QIcon(pm)
