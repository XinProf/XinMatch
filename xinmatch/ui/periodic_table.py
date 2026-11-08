"""118-element periodic-table selector for composition restraints (T13.4).

Implements :class:`PeriodicTableWidget`, the element-composition panel on
the *Restraints* tab (``docs/restraints.md``).  Every element button cycles
through the same three states used by
:class:`~xinmatch.core.model.restraints.Restraints`:

* 🟢 **REQUIRED** (green) — element **must be present** in the entry.
* 🔴 **EXCLUDE**  (red)   — element **must be absent** from the entry.
* ⚪ **OPTIONAL** (default/neutral) — no filtering effect.

The mapping above is taken verbatim from
:class:`~xinmatch.core.model.restraints.ElementState`
(``EXCLUDE="red"``, ``OPTIONAL="yellow"``, ``REQUIRED="green"``) and the
element-filtering logic in
:func:`~xinmatch.core.search.restraints_apply.apply_restraints` — the GUI
never invents its own semantics.  A *Toggle* check box enables / disables
the whole three-state filter without losing the chosen states.

Layout / styling notes (2026-11-08 rewrite)
-------------------------------------------
* 按钮尺寸**由字体度量算**（``_cell_w`` / ``_cell_h``），不要写死像素：
  写死 38×30 时，全局 QSS 的 ``padding: 5px 14px`` 会把内容区压到 8 px，
  两字母符号（He / Og）被裁。
* 每个按钮的 QSS **必须完整覆盖**全局 ``QPushButton`` 的 ``padding`` 与
  ``min-width`` / ``min-height``：QSS 的 min-* 优先级高于 ``setFixedSize()``，
  漏写会让布局把按钮压到 25 px 高（大字体下贴边裁切）；写成 0 又会反过来
  让 18 列被压扁。
* 三态**不只靠颜色**区分（红绿色盲友好）：必含 = 绿底 + 2 px 实线 + 加粗，
  排除 = 红底 + 2 px 虚线 + 加粗，不限制 = 灰底细实线常规字；表上方常显图例。
"""

from __future__ import annotations

from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from xinmatch.core.model.element_symbols import (
    ELEMENT_SYMBOLS,
    complement_restraints,
    parse_element_symbols,
)
from xinmatch.core.model.restraints import ElementState

__all__ = [
    "ELEMENT_SYMBOLS",
    "PeriodicTablePanel",
    "PeriodicTableWidget",
    "parse_element_symbols",
]

# ---------------------------------------------------------------------------
# Element grid: (symbol, grid_row, grid_col) in an 18-column table.
# Periods 1..7 occupy rows 0..6; the lanthanides / actinides are pulled out
# into rows 8 / 9 (with La / Ac staying in the main table at group 3).
# ---------------------------------------------------------------------------
_ELEMENTS: tuple[tuple[str, int, int], ...] = (
    ("H", 0, 0), ("He", 0, 17),
    ("Li", 1, 0), ("Be", 1, 1), ("B", 1, 12), ("C", 1, 13),
    ("N", 1, 14), ("O", 1, 15), ("F", 1, 16), ("Ne", 1, 17),
    ("Na", 2, 0), ("Mg", 2, 1), ("Al", 2, 12), ("Si", 2, 13),
    ("P", 2, 14), ("S", 2, 15), ("Cl", 2, 16), ("Ar", 2, 17),
    ("K", 3, 0), ("Ca", 3, 1), ("Sc", 3, 2), ("Ti", 3, 3), ("V", 3, 4),
    ("Cr", 3, 5), ("Mn", 3, 6), ("Fe", 3, 7), ("Co", 3, 8), ("Ni", 3, 9),
    ("Cu", 3, 10), ("Zn", 3, 11), ("Ga", 3, 12), ("Ge", 3, 13),
    ("As", 3, 14), ("Se", 3, 15), ("Br", 3, 16), ("Kr", 3, 17),
    ("Rb", 4, 0), ("Sr", 4, 1), ("Y", 4, 2), ("Zr", 4, 3), ("Nb", 4, 4),
    ("Mo", 4, 5), ("Tc", 4, 6), ("Ru", 4, 7), ("Rh", 4, 8), ("Pd", 4, 9),
    ("Ag", 4, 10), ("Cd", 4, 11), ("In", 4, 12), ("Sn", 4, 13),
    ("Sb", 4, 14), ("Te", 4, 15), ("I", 4, 16), ("Xe", 4, 17),
    ("Cs", 5, 0), ("Ba", 5, 1), ("La", 5, 2), ("Hf", 5, 3), ("Ta", 5, 4),
    ("W", 5, 5), ("Re", 5, 6), ("Os", 5, 7), ("Ir", 5, 8), ("Pt", 5, 9),
    ("Au", 5, 10), ("Hg", 5, 11), ("Tl", 5, 12), ("Pb", 5, 13),
    ("Bi", 5, 14), ("Po", 5, 15), ("At", 5, 16), ("Rn", 5, 17),
    ("Fr", 6, 0), ("Ra", 6, 1), ("Ac", 6, 2), ("Rf", 6, 3), ("Db", 6, 4),
    ("Sg", 6, 5), ("Bh", 6, 6), ("Hs", 6, 7), ("Mt", 6, 8), ("Ds", 6, 9),
    ("Rg", 6, 10), ("Cn", 6, 11), ("Nh", 6, 12), ("Fl", 6, 13),
    ("Mc", 6, 14), ("Lv", 6, 15), ("Ts", 6, 16), ("Og", 6, 17),
    # Lanthanides (Ce..Lu) pulled out to row 8.
    ("Ce", 8, 3), ("Pr", 8, 4), ("Nd", 8, 5), ("Pm", 8, 6), ("Sm", 8, 7),
    ("Eu", 8, 8), ("Gd", 8, 9), ("Tb", 8, 10), ("Dy", 8, 11), ("Ho", 8, 12),
    ("Er", 8, 13), ("Tm", 8, 14), ("Yb", 8, 15), ("Lu", 8, 16),
    # Actinides (Th..Lr) pulled out to row 9.
    ("Th", 9, 3), ("Pa", 9, 4), ("U", 9, 5), ("Np", 9, 6), ("Pu", 9, 7),
    ("Am", 9, 8), ("Cm", 9, 9), ("Bk", 9, 10), ("Cf", 9, 11), ("Es", 9, 12),
    ("Fm", 9, 13), ("Md", 9, 14), ("No", 9, 15), ("Lr", 9, 16),
)

# 符号表 / 解析函数已下沉到 core.model.element_symbols —— CLI 也要用，
# 不能让命令行进程依赖 PySide6。这里 re-export 同名接口保持既有 import 不破，
# 并校验按钮网格与 core 的 118 元素表没有漂移：补集约束必须精确覆盖每个
# 按钮，否则某个元素会既不在允许集、也没被排除。
if tuple(sym for sym, _row, _col in _ELEMENTS) != ELEMENT_SYMBOLS:
    raise RuntimeError("周期表按钮与 core 元素符号表不一致，补集约束不可用")


# Cycle order on click: default -> required -> excluded -> default.
_CYCLE: tuple[ElementState, ...] = (
    ElementState.OPTIONAL,
    ElementState.REQUIRED,
    ElementState.EXCLUDE,
)

#: 三态视觉：背景 / 边框色 / 边框线型 / 字色 / 字重。
#:
#: **不只靠颜色区分**（红绿色盲友好）：必含用 2 px 实线、排除用 2 px 虚线；
#: 两者的字都加粗。线型差异在缩小截图或打印时仍然可分。
_STATE_STYLES: dict[ElementState, dict[str, str]] = {
    ElementState.OPTIONAL: {
        "bg": "#f7f8f9", "border": "#c3c8cd", "style": "solid",
        "fg": "#2b2f33", "weight": "normal",
    },
    ElementState.REQUIRED: {
        "bg": "#d8f0de", "border": "#2f7d4a", "style": "solid",
        "fg": "#14532d", "weight": "bold",
    },
    ElementState.EXCLUDE: {
        "bg": "#fbdede", "border": "#b03a3a", "style": "dashed",
        "fg": "#7f1d1d", "weight": "bold",
    },
}

#: 兼容旧接口（Organizer / 老文档按背景色取材）。
STATE_BACKGROUNDS: dict[ElementState, str] = {
    state: style["bg"] for state, style in _STATE_STYLES.items()
}

_STATE_LABELS: dict[ElementState, str] = {
    ElementState.OPTIONAL: "不限制",
    ElementState.REQUIRED: "必含",
    ElementState.EXCLUDE: "排除",
}

#: 按钮内边距（内容区到边框，单位 px）。尺寸计算与 QSS 必须共用这两个数，
#: 否则又会算出「文字放不下」。
_CELL_PAD_X = 8
_CELL_PAD_Y = 6
#: 边框宽度（QSS 里的 2px 实线/虚线）。QSS 的 min-width / min-height 作用于
#: **内容矩形**，不含 border，所以换算最小尺寸时要各减 2×2。
_BORDER_PX = 2
# 全局 QSS 给 QPushButton 设了 `padding: 5px 14px; min-height: 20px`。
# 本项目的小按钮必须把它们全部在自己的 QSS 里覆盖掉，理由有两条，且都实测踩过：
#   ① padding 不归零 → 38 px 宽里只剩 8 px 放字，"He" 直接裁掉；
#   ② min-height 不覆盖 → QSS 的 20px 优先级高于 setFixedSize()，按钮被压到
#      25 px（字高 21 px 时贴边），大字体（13pt）下必裁。
_BUTTON_QSS_TEMPLATE = """
QPushButton {{
    background: {bg};
    color: {fg};
    border: {border}px {style} {border_color};
    border-radius: 4px;
    padding: 0px;
    margin: 0px;
    min-width: {min_w}px;
    min-height: {min_h}px;
    font-size: {font_pt:g}pt;
    font-weight: {weight};
}}
QPushButton:hover {{ border-color: #2f6fdb; }}
QPushButton:disabled {{
    color: #9aa0a6; background: #f0f0f0; border-color: #d8d8d8;
}}
"""


class PeriodicTableWidget(QtWidgets.QWidget):
    """118-button periodic table with three-state element restraints.

    Signals
    -------
    state_changed(str, ElementState):
        Emitted whenever an element button is cycled to a new state.
    enabled_changed(bool):
        Emitted when the Toggle filter switch is flipped.
    """

    state_changed = QtCore.Signal(str, object)
    enabled_changed = QtCore.Signal(bool)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._buttons: dict[str, QtWidgets.QPushButton] = {}
        self._states: dict[str, ElementState] = {}

        # 尺寸按字体度量算，不写死 —— 写死 38×30 时符号被裁（2026-11-08 修）：
        # 全局 QSS 的 `padding: 5px 14px` 会吃掉 28 px，剩 8 px 放不下 "He"。
        font = QtGui.QFont(self.font())
        point_size = font.pointSizeF()
        if point_size <= 0:  # 字体用像素指定时 pointSizeF() 返回 -1
            point_size = 9.0
        font.setPointSizeF(point_size)
        bold_font = QtGui.QFont(font)
        bold_font.setBold(True)
        metrics = QtGui.QFontMetrics(bold_font)  # 加粗态更宽，按它留余量
        self._font_pt = point_size
        self._cell_w = max(
            30, metrics.horizontalAdvance("Og") + 2 * _CELL_PAD_X + 2 * _BORDER_PX
        )
        self._cell_h = max(26, metrics.height() + 2 * _CELL_PAD_Y)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Toggle: one-click enable / disable of three-state filtering.
        self._toggle = QtWidgets.QCheckBox("启用元素过滤")
        self._toggle.setChecked(True)
        self._toggle.toggled.connect(self._on_toggled)
        layout.addWidget(self._toggle)

        layout.addLayout(self._build_legend())

        grid_holder = QtWidgets.QWidget()
        self._grid = QtWidgets.QGridLayout(grid_holder)
        self._grid.setSpacing(3)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setColumnStretch(18, 1)  # 右侧留白，整表靠左
        self._grid.setRowMinimumHeight(7, 10)  # 主表与 f 区之间的视觉间隔
        layout.addWidget(grid_holder)

        self._build_buttons()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_legend(self) -> QtWidgets.QHBoxLayout:
        """三态图例（色块 + 线型 + 文字），常显在网格上方。"""
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        for state in _CYCLE:
            style = _STATE_STYLES[state]
            swatch = QtWidgets.QLabel()
            swatch.setFixedSize(14, 14)
            swatch.setStyleSheet(
                f"background: {style['bg']};"
                f"border: 2px {style['style']} {style['border']};"
                "border-radius: 3px;"
            )
            row.addWidget(swatch)
            text = QtWidgets.QLabel(_STATE_LABELS[state])
            row.addWidget(text)
            if state is not _CYCLE[-1]:
                row.addSpacing(8)
        row.addStretch(1)
        return row

    def _build_buttons(self) -> None:
        for symbol, row, col in _ELEMENTS:
            btn = QtWidgets.QPushButton(symbol)
            btn.setObjectName(f"elem_{symbol}")
            btn.setFixedSize(self._cell_w, self._cell_h)
            btn.setCheckable(False)
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, s=symbol: self._cycle(s))
            self._grid.addWidget(btn, row, col)
            self._buttons[symbol] = btn
            self._states[symbol] = ElementState.OPTIONAL
            self._restyle(symbol)

        # Row labels for the pulled-out f-block rows（占 col 0–2，右对齐贴近
        # 镧系首列，避免与主表第 3 列的元素挤在一起）。
        for row, label in ((8, "镧系"), (9, "锕系")):
            lbl = QtWidgets.QLabel(label)
            lbl.setAlignment(
                QtCore.Qt.AlignmentFlag.AlignRight
                | QtCore.Qt.AlignmentFlag.AlignVCenter
            )
            self._grid.addWidget(lbl, row, 0, 1, 3)

    def _restyle(self, symbol: str) -> None:
        """Paint *symbol* button according to its current state + refresh tooltip."""
        state = self._states[symbol]
        btn = self._buttons[symbol]
        style = _STATE_STYLES[state]
        btn.setProperty("elemState", state.value)
        # 完整覆盖全局 QPushButton 规则（padding / min-height）——只写
        # background-color 会让全局的 `padding: 5px 14px; min-height: 20px`
        # 继续生效，符号被裁 / 按钮被压扁。min-* 作用于内容矩形，故减 border。
        btn.setStyleSheet(_BUTTON_QSS_TEMPLATE.format(
            bg=style["bg"],
            fg=style["fg"],
            style=style["style"],
            border_color=style["border"],
            border=_BORDER_PX,
            min_w=self._cell_w - 2 * _BORDER_PX,
            min_h=self._cell_h - 2 * _BORDER_PX,
            weight=style["weight"],
            font_pt=self._font_pt,
        ))
        btn.setToolTip(
            f"{symbol}｜当前：{_STATE_LABELS[state]}\n"
            "点击循环切换：必含（绿实线）→ 排除（红虚线）→ 不限制"
        )
        # Re-polish so dynamic properties take effect under QSS.
        btn.style().unpolish(btn)
        btn.style().polish(btn)

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------
    def _cycle(self, symbol: str) -> None:
        """Advance *symbol* to the next state in :data:`_CYCLE`."""
        current = self._states[symbol]
        idx = _CYCLE.index(current)
        nxt = _CYCLE[(idx + 1) % len(_CYCLE)]
        self._states[symbol] = nxt
        self._restyle(symbol)
        self.state_changed.emit(symbol, nxt)

    def _on_toggled(self, enabled: bool) -> None:
        for btn in self._buttons.values():
            btn.setEnabled(enabled)
        self.enabled_changed.emit(enabled)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def states(self) -> dict[str, ElementState]:
        """Return the active (non-default) element states.

        Mirrors :attr:`Restraints.elements`: only elements whose state is
        *not* OPTIONAL are returned, so the dict can be fed straight into
        a :class:`~xinmatch.core.model.restraints.Restraints` object.
        """
        return {s: st for s, st in self._states.items() if st != ElementState.OPTIONAL}

    def set_states(self, states: dict[str, Any]) -> None:
        """Set element states from a ``{symbol: ElementState | str}`` mapping.

        Missing elements are reset to OPTIONAL.  Accepts either
        :class:`ElementState` members or their string values (``"red"`` /
        ``"yellow"`` / ``"green"``) for convenience when round-tripping
        from YAML.
        """
        wanted: dict[str, ElementState] = {}
        for symbol, state in states.items():
            wanted[symbol] = state if isinstance(state, ElementState) else ElementState(state)
        for symbol in self._buttons:
            self._states[symbol] = wanted.get(symbol, ElementState.OPTIONAL)
            self._restyle(symbol)

    def set_enabled(self, enabled: bool) -> None:
        """Programmatically flip the Toggle (mirrors user click)."""
        self._toggle.setChecked(enabled)

    def is_enabled(self) -> bool:
        """Return whether three-state filtering is currently active."""
        return self._toggle.isChecked()  # type: ignore[no-any-return]

    def set_toggle_visible(self, visible: bool) -> None:
        """显示 / 隐藏内置"启用元素过滤"开关。

        弹出式选择器（:class:`PeriodicTablePanel`）由外层面板提供开关，
        弹窗内隐藏周期表自带的那个，避免两处开关状态不一致。
        """
        self._toggle.setVisible(visible)

    def reset(self) -> None:
        """Reset every element to OPTIONAL."""
        self.set_states({})


class PeriodicTablePanel(QtWidgets.QWidget):
    """元素周期表弹出式选择面板（v1.3.1）。

    替代原来常驻主工作区的整张周期表：面板只占一行摘要 + 开关 + 按钮，
    点击「选择元素…」弹出模态对话框（内嵌 :class:`PeriodicTableWidget`
    实例，状态跨弹窗保留），选完关闭弹窗后页面只展示选择结果——
    省下的显示空间留给谱图。

    ``states`` / ``set_states`` / ``set_enabled`` / ``is_enabled`` /
    ``reset`` 与原 :class:`PeriodicTableWidget` 同名同义，主窗口 /
    测试可按 drop-in 使用。

    Signals
    -------
    selection_changed():
        元素状态或过滤开关变化时发出（供检索链路刷新限制条件）。
    """

    selection_changed = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        # 持久周期表实例：平时隐藏，弹窗时临时移入对话框。
        self._table = PeriodicTableWidget(self)
        self._table.hide()
        self._table.set_toggle_visible(False)
        self._table.state_changed.connect(self._on_table_state_changed)

        self._summary = QtWidgets.QLabel()
        self._summary.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self._summary.setWordWrap(True)

        self._enabled_cb = QtWidgets.QCheckBox("启用元素过滤")
        self._enabled_cb.setChecked(True)
        self._enabled_cb.setToolTip("关闭后保留已选元素但不参与检索过滤")
        self._enabled_cb.toggled.connect(self._on_enabled_toggled)

        self._pick_button = QtWidgets.QPushButton("选择元素…")
        self._pick_button.setToolTip(
            "弹出元素周期表选择必含 / 排除元素（点击元素循环三态），"
            "关闭弹窗后仅展示选择结果"
        )
        self._pick_button.clicked.connect(self._open_picker)
        self._clear_button = QtWidgets.QPushButton("清除")
        self._clear_button.setToolTip("清除全部已选元素状态")
        self._clear_button.clicked.connect(self._clear_all)

        # ── 样品元素快速录入（2026-11-06）─────────────────────────────
        # 基准报告 §20：给足化学信息时真实谱相召回 20/43 → 30/43，
        # 3-1 的 Al2O3 / CaF2 由 MISS 变成 Top-20 第 13 / 11 位。但"只允许
        # 这几个元素"在预筛层只能表达成「其余 113 个元素全部标红」，
        # 让用户在 118 个按钮上逐个点是不现实的 —— 所以给一行文本框 + 一个按钮。
        self._detected_edit = QtWidgets.QLineEdit()
        self._detected_edit.setObjectName("sampleElementsEdit")
        self._detected_edit.setPlaceholderText("样品检出元素，空格分隔，如：Zn Al Ca O F")
        self._detected_edit.setToolTip(
            "来自 XRF/EDS 或配方的元素符号；不区分大小写，可用空格 / 逗号 / 分号分隔。\n"
            "右侧按钮会把**其余元素全部标为排除**。\n"
            "注意：轻元素（O/F/C/N）常常测不到，漏填会把氧化物 / 氟化物整类排除。"
        )
        self._detected_edit.returnPressed.connect(self._on_exclude_rest_clicked)

        self._exclude_rest_button = QtWidgets.QPushButton("其余元素排除")
        self._exclude_rest_button.setObjectName("excludeRestButton")
        self._exclude_rest_button.setToolTip(
            "把未列出的元素全部标为「必须不含」（走 element_inv 倒排硬过滤）。\n"
            "已列出的元素保持「可选」—— 次相未必含每一个主相元素，"
            "绝不能标成「必含」（prescreen.elements_allowed 是必须全含语义）。\n"
            "实测：真实谱相召回 20/43 → 30/43，3-1 的次相 1/3 → 3/3。"
        )
        self._exclude_rest_button.clicked.connect(self._on_exclude_rest_clicked)

        quick = QtWidgets.QHBoxLayout()
        quick.setContentsMargins(0, 0, 0, 0)
        quick.addWidget(QtWidgets.QLabel("样品元素："))
        quick.addWidget(self._detected_edit, 1)
        quick.addWidget(self._exclude_rest_button)

        self._quick_hint = QtWidgets.QLabel(
            "填 XRF/EDS 检出的元素，其余自动排除；实测多相样品相召回 "
            "<b>20/43 → 30/43</b>。轻元素漏填会误杀氧化物。"
        )
        self._quick_hint.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self._quick_hint.setWordWrap(True)
        self._quick_hint.setToolTip(
            "30/43 是上界口径（元素由真值反推）；实际效果取决于外部元素测量是否完整。"
        )

        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self._enabled_cb)
        row.addWidget(self._pick_button)
        row.addWidget(self._clear_button)
        row.addStretch(1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addLayout(quick)
        layout.addWidget(self._quick_hint)
        layout.addWidget(self._summary)
        layout.addLayout(row)

        self._quick_mode = False
        self._detected: tuple[str, ...] = ()
        self._refresh_summary()

    # ------------------------------------------------------------------
    # Drop-in API（与 PeriodicTableWidget 同名同义）
    # ------------------------------------------------------------------
    def states(self) -> dict[str, ElementState]:
        """Return the active (non-default) element states."""
        return self._table.states()

    def set_states(self, states: dict[str, Any]) -> None:
        """Set element states from a ``{symbol: ElementState | str}`` mapping.

        An explicit state map supersedes the quick-entry complement, so the
        quick mode is dropped and listeners are notified (the toolbar button
        must not keep advertising a stale "仅 O F …" constraint).
        """
        self._table.set_states(states)
        self._quick_mode = False
        self._detected = ()
        self._refresh_summary()
        self.selection_changed.emit()

    def set_enabled(self, enabled: bool) -> None:
        """Programmatically flip the enable switch (mirrors user click)."""
        self._enabled_cb.setChecked(enabled)

    def is_enabled(self) -> bool:
        """Return whether three-state filtering is currently active."""
        return self._enabled_cb.isChecked()  # type: ignore[no-any-return]

    def reset(self) -> None:
        """Reset every element to OPTIONAL."""
        self._table.reset()
        self._quick_mode = False
        self._detected = ()
        self._refresh_summary()
        self.selection_changed.emit()

    def quick_elements(self) -> tuple[str, ...]:
        """Elements supplied through the quick-entry box (empty = manual mode)."""
        return self._detected

    def focus_detected_input(self) -> None:
        """Focus the quick-entry box (used by the toolbar jump action)."""
        self._detected_edit.setFocus()
        self._detected_edit.selectAll()

    def apply_detected_elements(self, text: str) -> tuple[list[str], list[str]]:
        """Turn "these elements were detected" into a complement restraint.

        Detected elements stay **OPTIONAL**; every other element becomes
        ``EXCLUDE``.  Marking them REQUIRED would be wrong twice over: a minor
        phase need not contain the major phase's elements, and
        ``prescreen(elements_allowed=...)`` means "must contain *all* of them"
        (benchmark report §20.5).  Returns ``(detected, unknown)``; on unknown
        tokens or empty input nothing is changed so the caller can warn.
        """
        detected, unknown = parse_element_symbols(text)
        if unknown or not detected:
            return detected, unknown
        # 与 CLI --sample-elements 共用同一个补集实现：语义只有一个来源，
        # 将来改「检出元素该不该 REQUIRED」时两边不会各走各的。
        self._table.set_states(complement_restraints(detected).elements)
        self._detected = tuple(detected)
        self._quick_mode = True
        if not self.is_enabled():
            self._enabled_cb.setChecked(True)
        self._refresh_summary()
        self.selection_changed.emit()
        return detected, []

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _on_exclude_rest_clicked(self) -> None:
        """Quick-entry button: validate, then apply the complement restraint."""
        detected, unknown = self.apply_detected_elements(self._detected_edit.text())
        if unknown:
            QtWidgets.QMessageBox.warning(
                self,
                "样品元素无法识别",
                "以下符号不是元素符号：\n  " + "、".join(unknown)
                + "\n\n请填写元素符号（如 Zn Al Ca O F），不要填化学式。",
            )
            self.focus_detected_input()
            return
        if not detected:
            QtWidgets.QMessageBox.information(
                self, "样品元素", "请先填写样品中检出的元素符号，例如：Zn Al Ca O F"
            )
            self.focus_detected_input()

    def _clear_all(self) -> None:
        """清除全部已选状态并发出 ``selection_changed``。"""
        self._table.reset()
        self._quick_mode = False
        self._detected = ()
        self._detected_edit.clear()
        self._refresh_summary()
        self.selection_changed.emit()

    def _on_table_state_changed(self, symbol: str, state: ElementState) -> None:
        """弹窗内元素状态变化 → 刷新摘要并转发信号。"""
        # 手工改过任何一个按钮，就不再是"其余元素排除"的补集口径。
        self._quick_mode = False
        self._detected = ()
        self._refresh_summary()
        self.selection_changed.emit()

    def _on_enabled_toggled(self, enabled: bool) -> None:
        """开关翻转 → 同步内嵌周期表按钮可用性 + 摘要。"""
        self._table.set_enabled(enabled)
        self._refresh_summary()
        self.selection_changed.emit()

    def _refresh_summary(self) -> None:
        """刷新摘要行：未选择 / 必含·排除（富文本着色）/ 过滤已关闭。"""
        states = self._table.states()
        required = [s for s, st in states.items() if st == ElementState.REQUIRED]
        excluded = [s for s, st in states.items() if st == ElementState.EXCLUDE]
        if self._quick_mode and self._detected:
            body = (
                "仅允许：<b>" + "、".join(self._detected) + "</b>"
                f"（其余 {len(excluded)} 个元素标为排除）"
            )
        elif not states:
            body = "未选择元素"
        else:
            parts: list[str] = []
            if required:
                parts.append(
                    "必含：<font color=\"#1a7f37\">"
                    + "、".join(sorted(required))
                    + "</font>"
                )
            if excluded:
                parts.append(
                    "排除：<font color=\"#c0392b\">"
                    + "、".join(sorted(excluded))
                    + "</font>"
                )
            body = "　".join(parts)
        if not self.is_enabled():
            body = f"<b>过滤已关闭</b>（{body}）"
        self._summary.setText(body)

    def _open_picker(self) -> None:
        """弹出模态元素选择对话框（复用持久周期表实例）。"""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("选择元素")
        v = QtWidgets.QVBoxLayout(dlg)
        hint = QtWidgets.QLabel(
            "点击元素按钮循环切换：必含（绿底实线）→ 排除（红底虚线）→ 不限制；"
            "关闭窗口后仅展示选择结果。"
        )
        hint.setWordWrap(True)
        v.addWidget(hint)
        # 滚动区兜底：小屏 / 大字体下 18 列可能放不下，宁可滚动也不裁字。
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setWidget(self._table)
        v.addWidget(scroll, 1)
        # 把持久实例临时移入对话框；关闭时移回面板隐藏。
        self._table.set_toggle_visible(False)
        self._table.show()
        # 尺寸按表格实际 sizeHint 定（原先写死 760×420，大字体下会裁字）。
        want_w = max(720, self._table.sizeHint().width() + 48)
        want_h = max(320, self._table.sizeHint().height() + 88)
        screen = dlg.screen()
        if screen is not None:
            avail = screen.availableGeometry()
            want_w = min(want_w, max(480, avail.width() - 80))
            want_h = min(want_h, max(320, avail.height() - 80))
        dlg.resize(want_w, want_h)
        dlg.exec()
        scroll.takeWidget()  # 解绑，避免滚动区析构时连带删掉持久实例
        self._table.setParent(self)
        self._table.hide()
        self._refresh_summary()
