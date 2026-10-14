"""Colors / line-styles dialog (T13.5).

Implements the *Colors and line styles* window
(``docs/colors_linestyles.md`` and the ``colors_linestyles_*.md`` series:
graphics / exp / reference / defaults / spectra / others).  Each page
holds color editors (a hex field + a colour-picker button), a line-style
combo and a line-width spin where the help documents them.
"""

from __future__ import annotations

from typing import Any

from PySide6 import QtGui, QtWidgets

__all__ = ["ColorsDialog"]

_LINE_STYLES = ("solid", "dash", "dot", "dashdot")


class _ColorRow(QtWidgets.QWidget):
    """A labelled hex field + colour-picker button."""

    def __init__(self, label: str, color: str,
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QtWidgets.QLabel(label))
        self._hex = QtWidgets.QLineEdit(color)
        self._hex.setMaxLength(7)
        layout.addWidget(self._hex)
        btn = QtWidgets.QPushButton("选择...")
        btn.clicked.connect(self._pick)
        layout.addWidget(btn)

    def _pick(self) -> None:
        current = QtGui.QColor(self._hex.text())
        chosen = QtWidgets.QColorDialog.getColor(current, self)
        if chosen.isValid():
            self._hex.setText(chosen.name())

    def color(self) -> str:
        return self._hex.text()  # type: ignore[no-any-return]

    def set_color(self, value: str) -> None:
        self._hex.setText(value)


class ColorsDialog(QtWidgets.QDialog):
    """Tabbed colour / line-style editor populated from the ``colors`` section."""

    def __init__(self, config: dict[str, Any] | None = None,
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("颜色与线型")
        self.resize(520, 420)
        cfg = config or {}

        self._tabs = QtWidgets.QTabWidget()

        # -- Experimental pattern --------------------------------------
        exp = cfg.get("experimental", {})
        exp_page = QtWidgets.QWidget()
        exp_form = QtWidgets.QFormLayout(exp_page)
        self._exp_color = _ColorRow("颜色", exp.get("color", "#0000ff"))
        exp_form.addRow(self._exp_color)
        self._exp_ls = QtWidgets.QComboBox()
        self._exp_ls.addItems(_LINE_STYLES)
        self._exp_ls.setCurrentText(exp.get("line_style", "solid"))
        exp_form.addRow("线型:", self._exp_ls)
        self._exp_lw = QtWidgets.QDoubleSpinBox()
        self._exp_lw.setRange(0.1, 10.0)
        self._exp_lw.setValue(float(exp.get("line_width", 1.0)))
        exp_form.addRow("线宽:", self._exp_lw)
        self._tabs.addTab(exp_page, "实验谱")

        # -- Default reference palette ----------------------------------
        defaults = cfg.get("reference_defaults", [])
        def_page = QtWidgets.QWidget()
        def_form = QtWidgets.QFormLayout(def_page)
        self._default_rows: list[_ColorRow] = []
        for i in range(max(3, len(defaults))):
            entry = defaults[i] if i < len(defaults) else {}
            row = _ColorRow(f"默认颜色 {i + 1}", entry.get("color", "#ff0000"))
            self._default_rows.append(row)
            def_form.addRow(row)
        self._tabs.addTab(def_page, "默认参考谱")

        # -- Element states ---------------------------------------------
        elems = cfg.get("elements", {})
        el_page = QtWidgets.QWidget()
        el_form = QtWidgets.QFormLayout(el_page)
        self._el_required = _ColorRow("必须含", elems.get("required", "#b8e6b8"))
        self._el_excluded = _ColorRow("必须不含", elems.get("excluded", "#f2b8b8"))
        self._el_optional = _ColorRow("可选", elems.get("optional", "#f0f0f0"))
        el_form.addRow(self._el_required)
        el_form.addRow(self._el_excluded)
        el_form.addRow(self._el_optional)
        self._tabs.addTab(el_page, "元素")

        # -- X-ray spectra ----------------------------------------------
        spectra = cfg.get("spectra", {})
        sp_page = QtWidgets.QWidget()
        sp_form = QtWidgets.QFormLayout(sp_page)
        self._sp_k1 = _ColorRow("Kα1", spectra.get("k_alpha1", "#000000"))
        self._sp_k2 = _ColorRow("Kα2", spectra.get("k_alpha2", "#888888"))
        sp_form.addRow(self._sp_k1)
        sp_form.addRow(self._sp_k2)
        self._tabs.addTab(sp_page, "X射线谱")

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._tabs)
        layout.addWidget(QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            accepted=self.accept, rejected=self.reject,
        ))  # type: ignore[call-overload]

    def values(self) -> dict[str, Any]:
        """Return the ``colors`` section reflecting the current widgets."""
        return {
            "experimental": {
                "color": self._exp_color.color(),
                "line_style": self._exp_ls.currentText(),
                "line_width": self._exp_lw.value(),
            },
            "reference_defaults": [
                {"color": row.color(), "line_style": "solid", "line_width": 1.0}
                for row in self._default_rows
            ],
            "elements": {
                "required": self._el_required.color(),
                "excluded": self._el_excluded.color(),
                "optional": self._el_optional.color(),
            },
            "spectra": {
                "k_alpha1": self._sp_k1.color(),
                "k_alpha2": self._sp_k2.color(),
            },
        }
