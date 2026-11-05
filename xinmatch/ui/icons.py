"""原创自绘 SVG 图标库（净室实现）。

所有图标均为抽象图形（文件夹 / 放大镜 / 齿轮 / 晶格 / 试管 / 谱图线 / 立方体等），
**完全原创**，不复制、也不近似任何商业软件的图标或视觉资源。

设计约定（v1.2.0 起重绘，v1.3.1 增加视觉归一化）
------------------------------------------------
* **填充主体 + accent 点缀**：物件类图标（文件夹 / 软盘 / 打印机 / 齿轮 / 数据库…）
  用实心填充剪影；仅"数据特征"类图标（谱线 / 拟合曲线 / 基线）保留粗描边
  （stroke-width 2.2–2.6），因为曲线语义上线稿更清晰。
* **视觉归一化**（v1.3.1）：透明背景下各图标原始画幅不一，工具栏上显得大小参差。
  ``_normalized_pixmap`` 以 8× 高清渲染 → ``_alpha_bbox`` 测 alpha 包围盒 →
  按长边等比缩放到 ``_CONTENT_RATIO`` × 画布 → 居中，保证所有图标视觉尺寸一致。
* **多尺寸预渲染**：``_ICON_PIXMAP_SIZES=(16,20,24,32,48)`` 每个尺寸各出一张
  归一化 pixmap 塞进 QIcon，避免 16 px 糊化。
* **模块 id 解析**：``resolve_icon_name`` 先查图标名、再查
  :data:`MODULE_ICON_NAMES`，调用方可以直接传模块 id（``search_match``）。

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
* :func:`is_svg_icon` — 名字（或模块 id）是否受支持。
* :data:`MODULE_ICON_NAMES` — 主窗口模块 id → 图标名映射，保证工具栏动作
  全部有对应图标。
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtSvg

# ---------------------------------------------------------------------------
# 配色（浅 / 深两套）。fg = 主体填充色，accent = 强调点缀色。
# light 的 fg 比早期版本稍深：填充风需要更足的面重。
# ---------------------------------------------------------------------------
_PALETTES: dict[str, dict[str, str]] = {
    "light": {"fg": "#3c4a5c", "accent": "#0b6bcb"},
    "dark": {"fg": "#dbe4ee", "accent": "#5aa9ff"},
}

# ---------------------------------------------------------------------------
# SVG 内联图形（24x24 viewBox）。{fg}/{accent} 在渲染时替换。
# 物件类 = 实心填充剪影；数据特征类（谱线/曲线/基线）= 粗描边。
# 所有图形为原创抽象符号，无语义上的商业资产复制。
# ---------------------------------------------------------------------------
_BODIES: dict[str, str] = {
    # 文件 / 文件夹
    "open": (
        '<path fill="{fg}" stroke="{fg}" stroke-width="1" '
        'd="M3.5 7.5a2 2 0 0 1 2-2h3.6l1.8 1.8h7.6a2 2 0 0 1 2 2v8'
        'a2 2 0 0 1-2 2H5.5a2 2 0 0 1-2-2z"/>'
    ),
    "import": (
        '<rect x="3.5" y="18" width="17" height="3.2" rx="1.4" '
        'fill="{fg}" stroke="{fg}" stroke-width="1"/>'
        '<path fill="{accent}" stroke="{accent}" stroke-width="1" '
        'd="M12 16.8L8.6 13.2l1.5-1.4 1.2 1.3V8.5h1.4v4.6l1.2-1.3 1.5 1.4z"/>'
    ),
    "export": (
        '<rect x="3.5" y="13.5" width="17" height="6.5" rx="1.4" '
        'fill="{fg}" stroke="{fg}" stroke-width="1"/>'
        '<path fill="{accent}" stroke="{accent}" stroke-width="1" '
        'd="M12 8.2l3.4 3.6-1.5 1.4-1.2-1.3v4.6h-1.4v-4.6l-1.2 1.3-1.5-1.4z"/>'
    ),
    "save": (
        '<path fill="{fg}" stroke="{fg}" stroke-width="1" '
        'd="M5 3.5h10L19.5 8v12.5H5z"/>'
        '<path fill="{accent}" stroke="{accent}" stroke-width="1" '
        'd="M8 3.5h6.8V8H8z"/>'
        '<path fill="{accent}" stroke="{accent}" stroke-width="1" '
        'd="M8 12.5h8v8H8z"/>'
    ),
    "new": (
        '<path fill="{fg}" stroke="{fg}" stroke-width="1" '
        'd="M6 3.5h8.5L19 8v12.5H6z"/>'
        '<path fill="{accent}" stroke="{accent}" stroke-width="1" '
        'd="M9.4 12.6h5.2v1.6H9.4z"/>'
        '<path fill="{accent}" stroke="{accent}" stroke-width="1" '
        'd="M11.2 10.8h1.6v5.2h-1.6z"/>'
    ),
    "print": (
        '<rect x="7.5" y="13" width="9" height="7.5" rx="0.8" '
        'fill="{accent}" stroke="{accent}" stroke-width="1"/>'
        '<rect x="4.5" y="7.5" width="15" height="7" rx="1.2" '
        'fill="{fg}" stroke="{fg}" stroke-width="1"/>'
        '<rect x="7" y="3" width="10" height="4.5" rx="0.8" '
        'fill="{fg}" stroke="{fg}" stroke-width="1"/>'
    ),
    # 谱图 / 数据处理（数据特征类：粗描边）
    "process": (
        '<rect x="3.5" y="6.3" width="17" height="1.5" '
        'fill="{fg}" stroke="{fg}" stroke-width="1"/>'
        '<rect x="3.5" y="11.25" width="17" height="1.5" '
        'fill="{fg}" stroke="{fg}" stroke-width="1"/>'
        '<rect x="3.5" y="16.2" width="17" height="1.5" '
        'fill="{fg}" stroke="{fg}" stroke-width="1"/>'
        '<circle cx="15.2" cy="7.05" r="2.3" fill="{accent}" stroke="{accent}"/>'
        '<circle cx="9.3" cy="12" r="2.3" fill="{accent}" stroke="{accent}"/>'
        '<circle cx="17.2" cy="16.95" r="2.3" fill="{accent}" stroke="{accent}"/>'
    ),
    "peaklist": (
        '<path d="M3.5 20.5h17" stroke-width="2.2"/>'
        '<path d="M4.5 20.5l2.5-11 3 7 3-10 3 6 3-4 2.5 12" '
        'stroke="{accent}" stroke-width="2.2"/>'
    ),
    "profile": (
        '<path d="M3.5 19.5c4 0 4.2-14 8.5-14s4.5 14 8.5 14" stroke-width="2.4"/>'
        '<path d="M3.5 19.5h17" stroke-width="2.2"/>'
    ),
    "run": (
        '<path fill="{accent}" stroke="{accent}" stroke-width="1" '
        'd="M7 4.5l12 7.5-12 7.5z"/>'
    ),
    "reset": (
        '<path fill="{fg}" stroke="{fg}" stroke-width="1" '
        'd="M18.9 7.2A8.4 8.4 0 1 0 18.9 16.8L16.9 15.4A6 6 0 0 1 16.9 8.6Z"/>'
        '<path fill="{accent}" stroke="{accent}" stroke-width="1" '
        'd="M18.9 16.8L16.2 13h5.4z"/>'
    ),
    # 检索 / 数据库
    "search": (
        '<path fill="{fg}" stroke="{fg}" stroke-width="1" fill-rule="evenodd" '
        'd="M10.5 3.7a6.8 6.8 0 1 0 0 13.6 6.8 6.8 0 0 0 0-13.6z'
        'M10.5 7.3a3.2 3.2 0 1 1 0 6.4 3.2 3.2 0 0 1 0-6.4z"/>'
        '<path d="M15.2 15.2l5.4 5.4" stroke="{accent}" stroke-width="3" '
        'stroke-linecap="round"/>'
    ),
    "restraints": (
        '<path fill="{fg}" stroke="{fg}" stroke-width="1" '
        'd="M3.5 5h17l-6.5 7.2v5.6l-4 2.4v-8z"/>'
    ),
    "database": (
        '<path fill="{fg}" stroke="{fg}" stroke-width="1" '
        'd="M4.5 6v12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3V6'
        'c0 1.7-3.4 3-7.5 3S4.5 7.7 4.5 6z"/>'
        '<ellipse cx="12" cy="6" rx="7.5" ry="3" '
        'fill="{accent}" stroke="{accent}" stroke-width="1"/>'
        '<path d="M4.5 12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3" fill="none" '
        'stroke="{accent}" stroke-width="1.4"/>'
    ),
    "userdb": (
        '<path fill="{fg}" stroke="{fg}" stroke-width="1" '
        'd="M3.2 5.2v9.6c0 1.2 2.2 2.1 4.8 2.1s4.8-0.9 4.8-2.1V5.2'
        'c0 1.2-2.2 2.1-4.8 2.1s-4.8-0.9-4.8-2.1z"/>'
        '<ellipse cx="8" cy="5.2" rx="4.8" ry="2.1" '
        'fill="{accent}" stroke="{accent}" stroke-width="1"/>'
        '<circle cx="16.8" cy="8.6" r="2.5" fill="{accent}" stroke="{accent}"/>'
        '<path fill="{accent}" stroke="{accent}" stroke-width="1" '
        'd="M12.6 19.6c0.3-2.6 1.8-4 4.2-4s3.9 1.4 4.2 4z"/>'
    ),
    # 计算 / 精修
    "build": (
        '<path fill="{fg}" stroke="{fg}" stroke-width="1" '
        'd="M14.5 5.5a4.3 4.3 0 0 0-5.7 5.4L4 15.7 8.3 20l4.8-4.8'
        'a4.3 4.3 0 0 0 5.4-5.7l-3 3-2.7-2.7z"/>'
    ),
    "indexing": (
        '<rect x="3.5" y="3.5" width="7" height="7" rx="1" '
        'fill="{fg}" stroke="{fg}" stroke-width="1"/>'
        '<rect x="13.5" y="3.5" width="7" height="7" rx="1" '
        'fill="{fg}" stroke="{fg}" stroke-width="1"/>'
        '<rect x="3.5" y="13.5" width="7" height="7" rx="1" '
        'fill="{fg}" stroke="{fg}" stroke-width="1"/>'
        '<circle cx="16.8" cy="16.8" r="3.6" fill="{accent}" stroke="{accent}"/>'
        '<path d="M19.4 19.4l2.4 2.4" stroke="{accent}" stroke-width="2.6" '
        'stroke-linecap="round"/>'
    ),
    "rietveld": (
        '<path d="M3.5 19.5h17" stroke-width="2.2"/>'
        '<path d="M5 19v-3M9 19v-5M13 19v-4M17 19v-6" stroke-width="2.4"/>'
        '<path d="M4 14c3-1 4.5-6 8-6.5s5 3.5 8 4.5" '
        'stroke="{accent}" stroke-width="2.4"/>'
    ),
    "quant": (
        '<circle cx="12" cy="12" r="8.5" fill="{fg}" stroke="{fg}"/>'
        '<path fill="{accent}" stroke="{accent}" stroke-width="1" '
        'd="M12 12L12 3.5A8.5 8.5 0 0 1 18 15.5z"/>'
    ),
    "microstructure": (
        '<path fill="{fg}" stroke="{fg}" stroke-width="1" '
        'd="M12 3l7.8 4.5v9L12 21l-7.8-4.5v-9z"/>'
        '<circle cx="12" cy="12" r="1.5" fill="{accent}" stroke="{accent}"/>'
        '<circle cx="7.5" cy="9.5" r="1.1" fill="{accent}" stroke="{accent}"/>'
        '<circle cx="16.5" cy="9.5" r="1.1" fill="{accent}" stroke="{accent}"/>'
        '<circle cx="7.5" cy="14.5" r="1.1" fill="{accent}" stroke="{accent}"/>'
        '<circle cx="16.5" cy="14.5" r="1.1" fill="{accent}" stroke="{accent}"/>'
    ),
    "refine": (
        '<rect x="3.5" y="5.5" width="17" height="1.4" '
        'fill="{fg}" stroke="{fg}" stroke-width="1"/>'
        '<rect x="3.5" y="11.3" width="17" height="1.4" '
        'fill="{fg}" stroke="{fg}" stroke-width="1"/>'
        '<rect x="3.5" y="17.1" width="17" height="1.4" '
        'fill="{fg}" stroke="{fg}" stroke-width="1"/>'
        '<circle cx="12" cy="12" r="3.2" fill="{accent}" stroke="{accent}"/>'
    ),
    # 输出 / 设置
    "report": (
        '<path fill="{fg}" stroke="{fg}" stroke-width="1" '
        'd="M6 3.5h8.5L19 8v12.5H6z"/>'
        '<path fill="{accent}" stroke="{accent}" stroke-width="1" '
        'd="M14.5 3.5L19 8h-4.5z"/>'
        '<rect x="9" y="11.8" width="6" height="1.2" '
        'fill="{accent}" stroke="{accent}" stroke-width="1"/>'
        '<rect x="9" y="15" width="6" height="1.2" '
        'fill="{accent}" stroke="{accent}" stroke-width="1"/>'
    ),
    "options": (
        '<circle cx="12" cy="12" r="6.2" fill="{fg}" stroke="{fg}"/>'
        '<g fill="{fg}" stroke="{fg}" stroke-width="1">'
        '<rect x="10.8" y="1.8" width="2.4" height="3.4"/>'
        '<rect x="10.8" y="18.8" width="2.4" height="3.4"/>'
        '<rect x="1.8" y="10.8" width="3.4" height="2.4"/>'
        '<rect x="18.8" y="10.8" width="3.4" height="2.4"/>'
        '<rect x="10.8" y="1.8" width="2.4" height="3.4" '
        'transform="rotate(45 12 12)"/>'
        '<rect x="10.8" y="18.8" width="2.4" height="3.4" '
        'transform="rotate(45 12 12)"/>'
        '<rect x="1.8" y="10.8" width="3.4" height="2.4" '
        'transform="rotate(45 12 12)"/>'
        '<rect x="18.8" y="10.8" width="3.4" height="2.4" '
        'transform="rotate(45 12 12)"/>'
        '</g>'
        '<circle cx="12" cy="12" r="2.6" fill="{accent}" stroke="{accent}"/>'
    ),
    "view3d": (
        '<path fill="{fg}" stroke="{fg}" stroke-width="1" '
        'd="M4 7.1v9.8L12 21.5l8-4.6V7.1L12 11.7z"/>'
        '<path fill="{accent}" stroke="{accent}" stroke-width="1" '
        'd="M12 2.5l8 4.6-8 4.6-8-4.6z"/>'
    ),
    "theme": (
        '<circle cx="12" cy="12" r="4.6" fill="{accent}" stroke="{accent}"/>'
        '<g stroke="{fg}" stroke-width="2" stroke-linecap="round" fill="none">'
        '<path d="M12 2.6v2.4M12 19v2.4M2.6 12h2.4M19 12h2.4"/>'
        '<path d="M5.3 5.3l1.7 1.7M17 17l1.7 1.7M18.7 5.3L17 7M7 17l-1.7 1.7"/>'
        '</g>'
    ),
    "colors": (
        '<circle cx="8.5" cy="9" r="3.4" fill="{accent}" stroke="{accent}"/>'
        '<circle cx="15.5" cy="9" r="3.4" fill="{fg}" stroke="{fg}"/>'
        '<circle cx="12" cy="15.3" r="3.4" fill="{accent}" stroke="{accent}" '
        'fill-opacity="0.72"/>'
    ),
    "help": (
        '<circle cx="12" cy="12" r="8.6" fill="{fg}" stroke="{fg}"/>'
        '<path d="M9.4 9.2a2.6 2.6 0 1 1 4.6 1.5" fill="none" '
        'stroke="{accent}" stroke-width="1.6"/>'
        '<rect x="11.2" y="10.6" width="1.6" height="3.4" '
        'fill="{accent}" stroke="{accent}" stroke-width="1"/>'
        '<circle cx="12" cy="15.8" r="1.05" fill="{accent}" stroke="{accent}"/>'
    ),
    "undo": (
        '<path fill="{fg}" stroke="{fg}" stroke-width="1" '
        'd="M18.93 16A8 8 0 1 1 18.93 8L17.11 9.05A5.9 5.9 0 0 0 17.11 14.95Z"/>'
        '<path fill="{accent}" stroke="{accent}" stroke-width="1" '
        'd="M18.93 8L21.8 6.2v3.6z"/>'
    ),
    "redo": (
        '<path fill="{fg}" stroke="{fg}" stroke-width="1" '
        'd="M5.07 16A8 8 0 0 0 5.07 8L6.89 9.05A5.9 5.9 0 0 1 6.89 14.95Z"/>'
        '<path fill="{accent}" stroke="{accent}" stroke-width="1" '
        'd="M5.07 8L2.2 6.2v3.6z"/>'
    ),
    "delete": (
        '<rect x="4.5" y="4.5" width="15" height="1.8" rx="0.9" '
        'fill="{fg}" stroke="{fg}" stroke-width="1"/>'
        '<rect x="9.5" y="2.5" width="5" height="2" rx="0.8" '
        'fill="{fg}" stroke="{fg}" stroke-width="1"/>'
        '<path fill="{fg}" stroke="{fg}" stroke-width="1" '
        'd="M6.8 6.3l1.1 13.4a1.6 1.6 0 0 0 1.6 1.5h5a1.6 1.6 0 0 0 '
        '1.6-1.5l1.1-13.4z"/>'
        '<rect x="10.1" y="9.2" width="1.1" height="7.6" '
        'fill="{accent}" stroke="{accent}" stroke-width="1"/>'
        '<rect x="12.8" y="9.2" width="1.1" height="7.6" '
        'fill="{accent}" stroke="{accent}" stroke-width="1"/>'
    ),
    "quit": (
        '<circle cx="12" cy="12" r="8.6" fill="{fg}" stroke="{fg}"/>'
        '<path fill="{accent}" stroke="{accent}" stroke-width="1" '
        'd="M8 7.5L12 11.5l4-4 1.5 1.5-4 4 4 4L16 18.5 12 14.5l-4 4-1.5-1.5 '
        '4-4-4-4z"/>'
    ),
    # ---- 数据处理（参考同类 XRD 软件工具栏常用符号语义，原创绘制）----
    "background": (
        '<path d="M3.5 19.5h17" stroke-width="2.2"/>'
        '<path d="M4.5 19.5l2.5-8 3 6 3-10 3 6 2.5-5 2 4" '
        'stroke="{accent}" stroke-width="2.2"/>'
        '<path d="M3 8.5L21 17" stroke="{fg}" stroke-dasharray="2 1.6" '
        'stroke-width="1.2"/>'
    ),
    "smooth": (
        '<path d="M3.5 15.5c3-5.5 4.5 3.5 8.5 3.5s5.5-9 8.5-3.5" '
        'stroke="{accent}" stroke-width="2.6"/>'
        '<path d="M3.5 19.5h17" stroke-width="2.2"/>'
    ),
    "ko2": (
        '<path d="M4 19.5h16" stroke-width="2.2"/>'
        '<path d="M6.5 19.5c.3-2.5 1.3-5 2.4-6.8M12.5 19.5c.3-3 1.4-6 2.6-8.4" '
        'stroke="{accent}" stroke-width="2.2"/>'
        '<path d="M17.5 19.5c.3-2.5 1.4-5.4 2.6-7.6" stroke-width="2.2"/>'
    ),
    "peakdetect": (
        '<path d="M4 19.5h16" stroke-width="2.2"/>'
        '<path d="M4.5 19.5l2.8-8 3.4 6.5 3-12 3.4 6.5 2.4-5 1.5 3" '
        'stroke="{accent}" stroke-width="2.2"/>'
        '<circle cx="13.7" cy="6" r="2.1" fill="{accent}" stroke="{accent}"/>'
    ),
    "wizard": (
        '<path d="M4.8 19.2L14.8 9.2" stroke="{fg}" stroke-width="2.8" '
        'stroke-linecap="round" fill="none"/>'
        '<path fill="{accent}" stroke="{accent}" stroke-width="1" '
        'd="M16.8 3.4l1.3 3.5 3.5 1.3-3.5 1.3-1.3 3.5-1.3-3.5-3.5-1.3 '
        '3.5-1.3z"/>'
        '<path fill="{accent}" stroke="{accent}" stroke-width="1" '
        'd="M18.6 14.2l0.7 1.9 1.9 0.7-1.9 0.7-0.7 1.9-0.7-1.9-1.9-0.7 '
        '1.9-0.7z"/>'
    ),
    "codsearch": (
        '<path fill="{fg}" stroke="{fg}" stroke-width="1" '
        'd="M3.6 6.8v8.2c0 1.4 2.4 2.5 5.4 2.5s5.4-1.1 5.4-2.5V6.8'
        'c0 1.4-2.4 2.5-5.4 2.5s-5.4-1.1-5.4-2.5z"/>'
        '<ellipse cx="9" cy="6.8" rx="5.4" ry="2.5" '
        'fill="{accent}" stroke="{accent}" stroke-width="1"/>'
        '<circle cx="16.3" cy="15.7" r="3.1" fill="none" '
        'stroke="{accent}" stroke-width="2.2"/>'
        '<path d="M18.6 18l2.8 2.8" stroke="{accent}" stroke-width="2.4" '
        'stroke-linecap="round" fill="none"/>'
    ),
}

#: 未知名回退的通用图标（实心立方体 + 顶面）。
_FALLBACK_BODY = (
    '<path fill="{fg}" stroke="{fg}" stroke-width="1" '
    'd="M4.5 7.3v9.4L12 21l7.5-4.3V7.3L12 11.5z"/>'
    '<path fill="{accent}" stroke="{accent}" stroke-width="1" '
    'd="M12 3l7.5 4.3L12 11.5 4.5 7.3z"/>'
)

# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------

#: 全部受支持的图标名（frozenset，只读）。
ICON_NAMES: frozenset[str] = frozenset(_BODIES)

#: 主窗口模块 id → 图标名映射（覆盖全部 15 个 MODULES；工具栏动作在内）。
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

#: 每个图标预渲染的像素尺寸（避免单一 48px 被缩到 16px 时糊化）。
_ICON_PIXMAP_SIZES: tuple[int, ...] = (16, 20, 24, 32, 48)

#: 归一化目标：内容包围盒长边占画布的比例（v1.3.1 统一视觉尺寸）。
_CONTENT_RATIO = 0.74

#: 高清渲染倍率：先按 8× 渲染测包围盒，再缩回目标尺寸，边缘更精确。
_HI_DPI = 8


def resolve_icon_name(name: str) -> str | None:
    """把图标名或模块 id 解析为受支持的图标名。

    Returns:
        解析后的图标名；既不是图标名也不是模块 id 时返回 ``None``
        （调用方应回退到通用图标）。
    """
    if name in _BODIES:
        return name
    mapped = MODULE_ICON_NAMES.get(name)
    if mapped is not None and mapped in _BODIES:
        return mapped
    return None


def _build_svg(body: str, theme: str) -> bytes:
    """把图标内联图形套进模板并按主题着色，返回 SVG 字节。"""
    pal = _PALETTES.get(theme, _PALETTES["light"])
    colored = body.replace("{fg}", pal["fg"]).replace("{accent}", pal["accent"])
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'width="48" height="48" fill="none" '
        f'stroke="{pal["fg"]}" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round">'
        f"{colored}</svg>"
    )
    return svg.encode("utf-8")


def _render_pixmap(body: str, theme: str, size: int) -> QtGui.QPixmap:
    """离屏把 SVG 渲染成 *size*×*size* 的 QPixmap（offscreen 安全）。"""
    svg_bytes = _build_svg(body, theme)
    renderer = QtSvg.QSvgRenderer(svg_bytes)
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtGui.QColor(0, 0, 0, 0))  # 透明底
    painter = QtGui.QPainter(pm)
    renderer.render(painter, QtCore.QRectF(0.0, 0.0, float(size), float(size)))
    painter.end()
    return pm


def _alpha_bbox(img: QtGui.QImage) -> QtCore.QRect | None:
    """返回 *img* 中 alpha>0 像素的包围盒；全透明返回 ``None``。

    逐行扫描 alpha 通道（ARGB32 内存布局下 alpha 位于每 4 字节的第 4 个），
    只记录占用的行与每行首尾列，避免逐像素 Python 调用。
    """
    if img.isNull():
        return None
    if img.format() not in (
        QtGui.QImage.Format.Format_ARGB32,
        QtGui.QImage.Format.Format_ARGB32_Premultiplied,
    ):
        img = img.convertToFormat(QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    width, height = img.width(), img.height()
    if width <= 0 or height <= 0:
        return None
    data = bytes(img.constBits())
    stride = img.bytesPerLine()
    row_len = width * 4
    min_x, min_y = width, height
    max_x = max_y = -1
    for y in range(height):
        base = y * stride
        row = data[base : base + row_len]
        alpha = row[3::4]
        if not any(alpha):
            continue
        if y < min_y:
            min_y = y
        max_y = y
        xs = [i for i, a in enumerate(alpha) if a]
        if xs[0] < min_x:
            min_x = xs[0]
        if xs[-1] > max_x:
            max_x = xs[-1]
    if max_x < 0 or max_y < 0:
        return None
    return QtCore.QRect(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)


def _normalized_pixmap(body: str, theme: str, size: int) -> QtGui.QPixmap:
    """渲染并归一化：内容包围盒长边等比缩放到 ``_CONTENT_RATIO`` 后居中。

    透明背景下各图标原始画幅不一（有的顶天立地、有的只占中间），直接渲染到
    工具栏上显得大小参差。这里先按 8× 高清渲染测出实际内容包围盒，再把内容
    等比缩放到统一占比并居中，保证所有图标视觉尺寸一致。
    """
    hi = _render_pixmap(body, theme, size * _HI_DPI)
    img = hi.toImage()
    bbox = _alpha_bbox(img)
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtGui.QColor(0, 0, 0, 0))
    if bbox is None or bbox.isEmpty():
        return pm
    painter = QtGui.QPainter(pm)
    try:
        painter.setRenderHint(
            QtGui.QPainter.RenderHint.SmoothPixmapTransform, True
        )
        span = max(bbox.width(), bbox.height())
        target = _CONTENT_RATIO * size
        scale = target / span
        w = bbox.width() * scale
        h = bbox.height() * scale
        dst = QtCore.QRectF((size - w) / 2.0, (size - h) / 2.0, w, h)
        painter.drawImage(dst, img, QtCore.QRectF(bbox))
    finally:
        painter.end()
    return pm


def is_svg_icon(name: str) -> bool:
    """``name`` 是否为受支持的图标名或模块 id。"""
    return resolve_icon_name(name) is not None


def icon(name: str, theme: str = "light") -> QtGui.QIcon:
    """按图标名（或模块 id）返回原创 ``QIcon``。

    Args:
        name: 图标名（见 :data:`ICON_NAMES`）或主窗口模块 id
            （见 :data:`MODULE_ICON_NAMES`）；未知名回退通用立方体图标，
            绝不返回空图标。
        theme: ``"light"`` 或 ``"dark"``，选择主体 / 点缀配色。

    Returns:
        内置多尺寸（16/20/24/32/48）归一化 pixmap 的 ``QIcon``。
    """
    resolved = resolve_icon_name(name)
    body = _BODIES[resolved] if resolved is not None else _FALLBACK_BODY
    ic = QtGui.QIcon()
    for size in _ICON_PIXMAP_SIZES:
        ic.addPixmap(_normalized_pixmap(body, theme, size))
    return ic
