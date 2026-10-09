"""Diffraction-data import dialog (T13.5).

Implements the *Select diffraction data* / *import* workflow described in
``docs/import_diffraction-data.md``,
``docs/import_diffraction-data_exp_details.md`` and
``docs/import_diffraction-data_file-formats.md``: a file-format picker plus
the experimental parameters (radiation / wavelength, 2θ range, step size)
that the importer needs when the file itself does not carry them.
"""

from __future__ import annotations

from typing import Any

from PySide6 import QtWidgets

__all__ = ["ImportDialog"]

#: File formats listed in ``docs/import_diffraction-data_file-formats.md``.
FILE_FORMATS: tuple[tuple[str, str], ...] = (
    ("自动检测 (*.*)", "auto"),
    ("Bruker/Siemens raw (*.raw)", "bruker_raw"),
    ("Bruker DIFFRAC peak (*.dif)", "dif"),
    ("PANalytical raw (*.rd *.udf)", "panalytical"),
    ("Rigaku raw (*.ras *.raw)", "rigaku"),
    ("ASCII 2-col (2θ/d I) (*.dat)", "ascii2col"),
    ("ASCII profile (start step end) (*.dat)", "ascii_profile"),
    ("XRDML scan (*.xrdml)", "xrdml"),
    ("Stoe peak file (*.pks)", "stoe_pks"),
)

#: Common radiation wavelengths (Å) offered in the combo box.
RADIATIONS: tuple[tuple[str, float], ...] = (
    ("Cu Kα", 1.54056),
    ("Cu Kα1", 1.54056),
    ("Cu Kα2", 1.54439),
    ("Co Kα", 1.78897),
    ("Mo Kα", 0.71073),
    ("Fe Kα", 1.93604),
    ("Cr Kα", 2.29093),
    ("用户自定义", 0.0),
)


class ImportDialog(QtWidgets.QDialog):
    """File-format + experimental-parameters dialog for data import.

    Populated from *config* (the ``"import"`` section of the YAML file)
    and exposing :meth:`values` so the caller can persist the choice.
    """

    def __init__(self, config: dict[str, Any] | None = None,
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("导入衍射数据")
        self.resize(420, 320)
        cfg = config or {}

        form = QtWidgets.QFormLayout()

        self._format = QtWidgets.QComboBox()
        for label, _key in FILE_FORMATS:
            self._format.addItem(label)
        if (fmt := cfg.get("format", "auto")):
            for i, (_label, key) in enumerate(FILE_FORMATS):
                if key == fmt:
                    self._format.setCurrentIndex(i)
                    break
        form.addRow("文件格式:", self._format)

        self._radiation = QtWidgets.QComboBox()
        for label, _wl in RADIATIONS:
            self._radiation.addItem(label)
        self._radiation.currentIndexChanged.connect(self._on_radiation_changed)
        form.addRow("辐射源:", self._radiation)

        self._wavelength = QtWidgets.QDoubleSpinBox()
        self._wavelength.setRange(0.1, 100.0)
        self._wavelength.setDecimals(5)
        self._wavelength.setSingleStep(0.0001)
        self._wavelength.setSuffix(" Å")
        self._wavelength.setValue(float(cfg.get("wavelength", 1.54056)))
        form.addRow("波长:", self._wavelength)

        self._two_theta = QtWidgets.QCheckBox("指定 2θ 范围")
        form.addRow("", self._two_theta)
        self._range_lo = QtWidgets.QDoubleSpinBox()
        self._range_lo.setRange(0.0, 180.0)
        self._range_lo.setValue(float(cfg.get("range_lo", 5.0)))
        self._range_hi = QtWidgets.QDoubleSpinBox()
        self._range_hi.setRange(0.0, 180.0)
        self._range_hi.setValue(float(cfg.get("range_hi", 80.0)))
        range_row = QtWidgets.QHBoxLayout()
        range_row.addWidget(self._range_lo)
        range_row.addWidget(QtWidgets.QLabel("—"))
        range_row.addWidget(self._range_hi)
        form.addRow("2θ 范围 (°):", range_row)

        self._step = QtWidgets.QDoubleSpinBox()
        self._step.setRange(0.001, 5.0)
        self._step.setDecimals(4)
        self._step.setValue(float(cfg.get("step", 0.02)))
        self._step.setSuffix(" °")
        form.addRow("步长:", self._step)

        self._is_d_values = QtWidgets.QCheckBox("数据为 d 值（非 2θ）")
        self._is_d_values.setChecked(bool(cfg.get("is_d_values", False)))
        form.addRow("", self._is_d_values)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            accepted=self.accept, rejected=self.reject,
        ))

    def _on_radiation_changed(self, index: int) -> None:
        """Pick the wavelength when a preset radiation is chosen."""
        _label, wl = RADIATIONS[index]
        if wl > 0.0:
            self._wavelength.setValue(wl)

    def values(self) -> dict[str, Any]:
        """Return the current widget state as a plain config section."""
        fmt_key = FILE_FORMATS[self._format.currentIndex()][1]
        return {
            "format": fmt_key,
            "radiation": RADIATIONS[self._radiation.currentIndex()][0],
            "wavelength": float(self._wavelength.value()),
            "specify_range": self._two_theta.isChecked(),
            "range_lo": float(self._range_lo.value()),
            "range_hi": float(self._range_hi.value()),
            "step": float(self._step.value()),
            "is_d_values": self._is_d_values.isChecked(),
        }
