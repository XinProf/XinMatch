"""Experimental-details dialog (T13.5).

Implements the *Experimental Details* dialog
(``docs/import_diffraction-data_exp_details.md``): radiation type,
wavelength, and whether the file holds 2θ or d-values, plus sample
metadata (sample name, date, instrument) used for the data sheet and
reporting.
"""

from __future__ import annotations

from typing import Any

from PySide6 import QtCore, QtWidgets

__all__ = ["ExperimentDetailsDialog"]


class ExperimentDetailsDialog(QtWidgets.QDialog):
    """Edit experimental metadata / radiation parameters.

    Populated from *config* (the ``"experiment"`` section) and returning
    the edited section through :meth:`values`.
    """

    def __init__(self, config: dict[str, Any] | None = None,
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("实验详情")
        self.resize(420, 300)
        cfg = config or {}

        form = QtWidgets.QFormLayout()

        self._sample = QtWidgets.QLineEdit(cfg.get("sample_name", ""))
        form.addRow("样品名:", self._sample)

        self._date = QtWidgets.QDateEdit()
        self._date.setCalendarPopup(True)
        self._date.setDisplayFormat("yyyy-MM-dd")
        self._date.setDate(QtCore.QDate.fromString(cfg.get("date", ""), "yyyy-MM-dd")
                           if cfg.get("date") else QtCore.QDate.currentDate())
        form.addRow("日期:", self._date)

        self._instrument = QtWidgets.QLineEdit(cfg.get("instrument", ""))
        form.addRow("仪器:", self._instrument)

        self._radiation_type = QtWidgets.QComboBox()
        self._radiation_type.addItems(["X-rays", "neutrons", "electrons"])
        idx = self._radiation_type.findText(cfg.get("radiation_type", "X-rays"))
        self._radiation_type.setCurrentIndex(max(idx, 0))
        form.addRow("辐射类型:", self._radiation_type)

        self._wavelength = QtWidgets.QDoubleSpinBox()
        self._wavelength.setRange(0.0, 100.0)
        self._wavelength.setDecimals(5)
        self._wavelength.setSuffix(" Å")
        self._wavelength.setValue(float(cfg.get("wavelength", 1.54056)))
        form.addRow("波长:", self._wavelength)

        self._axis = QtWidgets.QComboBox()
        self._axis.addItems(["2θ", "d"])
        self._axis.setCurrentText(cfg.get("axis", "2θ"))
        form.addRow("数据横轴:", self._axis)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            accepted=self.accept, rejected=self.reject,
        ))

    def values(self) -> dict[str, Any]:
        """Return the edited metadata section."""
        return {
            "sample_name": self._sample.text(),
            "date": self._date.date().toString("yyyy-MM-dd"),
            "instrument": self._instrument.text(),
            "radiation_type": self._radiation_type.currentText(),
            "wavelength": float(self._wavelength.value()),
            "axis": self._axis.currentText(),
        }
