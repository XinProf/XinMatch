"""微结构分析对话框（Scherrer 晶粒尺寸 / Williamson-Hall 微应变）。

输入：主窗口当前谱图（提供波长）+ 峰列表（``peak_table.peaks()``）。FWHM
必须来自 Profile Fitting（F5）精修——峰检测本身不给宽度。无 FWHM 的峰
被逐条跳过（``core.micro`` 的既有语义）。

计算全委托 :mod:`xinmatch.core.micro`，不重写算法：

* Scherrer 页 —— :func:`xinmatch.core.micro.crystallite_size.scherrer_from_peaks`
  逐峰给 ``D = K λ / (β cos θ)``，另报算术平均；
* Williamson-Hall 页 ——
  :func:`xinmatch.core.micro.microstrain.williamson_hall_from_peaks`
  对 ``β cos θ / λ = K / D + ε · 4 sin θ / λ`` 做最小二乘，给出 D、ε、R²、
  参与峰数，并把回归用的 (x, y) 逐峰列出以便复核。

**本版不做仪器宽化校正**（``β_sample² = β_obs² − β_inst²`` 需要 LaB₆ / Si
标样表，属后续版本）；提示文字常显，避免用户把仪器宽化误读成小晶粒。

结果是报告性数值，不回写峰列表（与参考软件一致：微结构分析只产出结论）。
"""

from __future__ import annotations

import logging

from PySide6 import QtWidgets

from xinmatch.core.micro.crystallite_size import scherrer_from_peaks
from xinmatch.core.micro.microstrain import williamson_hall_from_peaks

logger = logging.getLogger(__name__)

_SCHERRER_HEADERS = ("2θ (°)", "FWHM (°)", "D (nm)")
_WH_HEADERS = ("2θ (°)", "4sinθ/λ (Å⁻¹)", "βcosθ/λ (Å⁻¹)")


class MicrostructureDialog(QtWidgets.QDialog):
    """Scherrer / Williamson-Hall 微结构分析对话框。"""

    def __init__(
        self,
        pattern,
        peaks: list,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("微结构分析 (Scherrer / Williamson-Hall)")
        self.setMinimumWidth(560)
        self._pattern = pattern
        self._peaks = list(peaks)
        n_valid = sum(
            1 for p in self._peaks if p.fwhm is not None and p.fwhm > 0
        )

        layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QFormLayout()
        self._lambda_spin = QtWidgets.QDoubleSpinBox()
        self._lambda_spin.setRange(0.1, 5.0)
        self._lambda_spin.setDecimals(4)
        self._lambda_spin.setSingleStep(0.0001)
        self._lambda_spin.setValue(float(getattr(pattern, "wavelength", 1.5406)))
        form.addRow("波长 λ (Å)", self._lambda_spin)

        self._k_spin = QtWidgets.QDoubleSpinBox()
        self._k_spin.setRange(0.1, 2.0)
        self._k_spin.setDecimals(3)
        self._k_spin.setSingleStep(0.01)
        self._k_spin.setValue(0.9)
        form.addRow("Scherrer 常数 K", self._k_spin)
        layout.addLayout(form)

        info = QtWidgets.QLabel(
            f"峰列表 {len(self._peaks)} 个峰，其中 {n_valid} 个带 FWHM"
            "（FWHM 来自 Profile Fitting 精修，峰检测本身不给宽度）。\n"
            "本版不做仪器宽化校正 —— 若未扣除仪器宽化，算出的 D 会偏小。"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self._tabs = QtWidgets.QTabWidget()

        # --- Scherrer 页：逐峰 D + 平均 ------------------------------
        scherrer_page = QtWidgets.QWidget()
        scherrer_layout = QtWidgets.QVBoxLayout(scherrer_page)
        self._scherrer_table = QtWidgets.QTableWidget(0, 3)
        self._scherrer_table.setHorizontalHeaderLabels(_SCHERRER_HEADERS)
        self._scherrer_table.verticalHeader().setVisible(False)
        self._scherrer_table.horizontalHeader().setStretchLastSection(True)
        self._scherrer_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        scherrer_layout.addWidget(self._scherrer_table, 1)
        self._scherrer_summary = QtWidgets.QLabel("（未计算）")
        self._scherrer_summary.setWordWrap(True)
        scherrer_layout.addWidget(self._scherrer_summary)
        self._tabs.addTab(scherrer_page, "Scherrer")

        # --- Williamson-Hall 页：结果 + 回归数据 ----------------------
        wh_page = QtWidgets.QWidget()
        wh_layout = QtWidgets.QVBoxLayout(wh_page)
        self._wh_result = QtWidgets.QLabel("（未计算）")
        self._wh_result.setWordWrap(True)
        wh_layout.addWidget(self._wh_result)
        self._wh_table = QtWidgets.QTableWidget(0, 3)
        self._wh_table.setHorizontalHeaderLabels(_WH_HEADERS)
        self._wh_table.verticalHeader().setVisible(False)
        self._wh_table.horizontalHeader().setStretchLastSection(True)
        self._wh_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        wh_layout.addWidget(self._wh_table, 1)
        self._tabs.addTab(wh_page, "Williamson-Hall")

        layout.addWidget(self._tabs, 1)

        buttons = QtWidgets.QHBoxLayout()
        self._calc_button = QtWidgets.QPushButton("计算")
        self._calc_button.clicked.connect(self._run_calc)
        buttons.addWidget(self._calc_button)
        buttons.addStretch(1)
        close = QtWidgets.QPushButton("关闭")
        close.clicked.connect(self.reject)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    # ------------------------------------------------------------------
    def _run_calc(self) -> None:
        """两页一起算：Scherrer 失败只影响本页，W-H 同理（不互相阻断）。"""
        wavelength = float(self._lambda_spin.value())
        k = float(self._k_spin.value())
        valid = [
            p for p in self._peaks if p.fwhm is not None and p.fwhm > 0
        ]
        if not valid:
            QtWidgets.QMessageBox.information(
                self,
                "没有可用的 FWHM",
                "峰列表里没有带 FWHM 的峰。\n"
                "微结构分析需要峰的半高宽：请先寻峰，再用 Profile Fitting"
                "（F5）精修出 FWHM。",
            )
            return
        self._fill_scherrer(valid, wavelength, k)
        self._fill_wh(valid, wavelength, k)

    def _fill_scherrer(self, valid: list, wavelength: float, k: float) -> None:
        try:
            results = scherrer_from_peaks(valid, wavelength, k=k)
        except ValueError as exc:
            self._scherrer_table.setRowCount(0)
            self._scherrer_summary.setText(f"Scherrer 计算失败：{exc}")
            return
        self._scherrer_table.setRowCount(len(results))
        for row, (peak, size_nm) in enumerate(results):
            for col, text in enumerate((
                f"{peak.two_theta:.4f}",
                f"{peak.fwhm:.4f}" if peak.fwhm is not None else "—",
                f"{size_nm:.2f}",
            )):
                self._scherrer_table.setItem(
                    row, col, QtWidgets.QTableWidgetItem(text)
                )
        if results:
            mean = sum(d for _p, d in results) / len(results)
            self._scherrer_summary.setText(
                f"平均晶粒尺寸 D = {mean:.2f} nm"
                f"（{len(results)} 个峰，算术平均；单峰值随 hkl 各向异性会分散）"
            )
        else:
            self._scherrer_summary.setText("没有可计算的峰。")

    def _fill_wh(self, valid: list, wavelength: float, k: float) -> None:
        try:
            result = williamson_hall_from_peaks(valid, wavelength, k=k)
        except ValueError as exc:
            self._wh_table.setRowCount(0)
            self._wh_result.setText(f"无法做 Williamson-Hall 拟合：{exc}")
            return
        size_text = (
            f"{result.crystallite_size_nm:.2f} nm"
            if result.crystallite_size_nm is not None
            else "—（截距非正，无法给出 D）"
        )
        self._wh_result.setText(
            f"晶粒尺寸 D = {size_text}　　微应变 ε = "
            f"{result.microstrain:.3e}\n"
            f"R² = {result.r_squared:.4f}　　参与拟合峰数 n = "
            f"{result.n_peaks}"
        )
        n = len(result.x_values)
        self._wh_table.setRowCount(n)
        for row in range(n):
            two_theta = valid[row].two_theta
            for col, text in enumerate((
                f"{two_theta:.4f}",
                f"{float(result.x_values[row]):.6f}",
                f"{float(result.y_values[row]):.6f}",
            )):
                self._wh_table.setItem(
                    row, col, QtWidgets.QTableWidgetItem(text)
                )
