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
"""

from __future__ import annotations

from typing import Any

from PySide6 import QtCore, QtWidgets

from xinmatch.core.model.restraints import ElementState

__all__ = ["PeriodicTableWidget"]

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

# Cycle order on click: default -> required -> excluded -> default.
_CYCLE: tuple[ElementState, ...] = (
    ElementState.OPTIONAL,
    ElementState.REQUIRED,
    ElementState.EXCLUDE,
)

# Background colours per state; overridable by Organizer / theme.
STATE_BACKGROUNDS: dict[ElementState, str] = {
    ElementState.OPTIONAL: "#f0f0f0",
    ElementState.REQUIRED: "#b8e6b8",  # green
    ElementState.EXCLUDE: "#f2b8b8",   # red
}


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

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        # Toggle: one-click enable / disable of three-state filtering.
        self._toggle = QtWidgets.QCheckBox("启用元素过滤")
        self._toggle.setChecked(True)
        self._toggle.toggled.connect(self._on_toggled)
        layout.addWidget(self._toggle)

        grid_holder = QtWidgets.QWidget()
        self._grid = QtWidgets.QGridLayout(grid_holder)
        self._grid.setSpacing(2)
        layout.addWidget(grid_holder)

        self._build_buttons()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_buttons(self) -> None:
        for symbol, row, col in _ELEMENTS:
            btn = QtWidgets.QPushButton(symbol)
            btn.setObjectName(f"elem_{symbol}")
            btn.setFixedSize(38, 30)
            btn.setCheckable(False)
            btn.clicked.connect(lambda _checked=False, s=symbol: self._cycle(s))
            self._grid.addWidget(btn, row, col)
            self._buttons[symbol] = btn
            self._states[symbol] = ElementState.OPTIONAL
            self._restyle(symbol)

        # Row labels for the pulled-out f-block rows.
        for row, label in ((8, "镧系"), (9, "锕系")):
            lbl = QtWidgets.QLabel(label)
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self._grid.addWidget(lbl, row, 1)

    def _restyle(self, symbol: str) -> None:
        """Paint *symbol* button according to its current state."""
        state = self._states[symbol]
        btn = self._buttons[symbol]
        btn.setProperty("elemState", state.value)
        color = STATE_BACKGROUNDS.get(state, "#f0f0f0")
        btn.setStyleSheet(f"background-color: {color};")
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
        return self._toggle.isChecked()

    def reset(self) -> None:
        """Reset every element to OPTIONAL."""
        self.set_states({})
