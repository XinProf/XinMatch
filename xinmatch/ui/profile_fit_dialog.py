"""Profile Fitting 对话框（参考软件 F5）。

输入：主窗口当前谱图 + 峰列表初始猜测（``peak_table.peaks()``）。
选项：谱形（Gaussian / Lorentzian / pseudo-Voigt / Pearson VII）。
计算：全委托 :func:`xinmatch.core.peak.profile_fit.fit_profile`
（多峰最小二乘，不重写算法），在工作线程经 :func:`run_with_busy` 执行。

输出：

* 结果表——每峰的精修 2θ / FWHM / 面积 / 相对强度 I-I₀（按最强峰归一）；
* Rwp（加权剖面 R 因子）标签；
* 拟合曲线叠加到主窗口谱图区（对话框关闭时移除）；
* 「应用到峰列表」把精修后的峰写回峰列表（:attr:`fit_applied` 信号，
  由主窗口接 ``peak_table.set_peaks``）。
"""

from __future__ import annotations

import logging

import numpy as np
from PySide6 import QtCore, QtWidgets

from xinmatch.core.model.pattern import Pattern
from xinmatch.core.peak.profile_fit import fit_profile
from xinmatch.ui.busy import run_with_busy

logger = logging.getLogger(__name__)

_SHAPES = (
    ("pseudo-Voigt（默认）", "pseudo_voigt"),
    ("Gaussian", "gaussian"),
    ("Lorentzian", "lorentzian"),
    ("Pearson VII", "pearson_vii"),
)


class ProfileFitDialog(QtWidgets.QDialog):
    """多峰 Profile Fitting 对话框（结果表 + Rwp + 曲线叠加）。"""

    #: 用户点「应用到峰列表」；携带精修后的 :class:`Peak` 列表。
    fit_applied = QtCore.Signal(list)

    def __init__(
        self,
        pattern,
        peaks: list,
        pattern_view,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Profile Fitting")
        self.setMinimumWidth(460)
        self._pattern = pattern
        self._initial_peaks = list(peaks)
        self._view = pattern_view
        self._fit_curve_key: str | None = None
        self._result = None

        layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QFormLayout()
        self._shape_combo = QtWidgets.QComboBox()
        for label, value in _SHAPES:
            self._shape_combo.addItem(label, userData=value)
        form.addRow("谱形", self._shape_combo)
        self._info_label = QtWidgets.QLabel(
            f"初始猜测：{len(self._initial_peaks)} 个峰（来自峰列表）\n"
            "拟合精修每峰的 2θ / FWHM / 面积；强度按面积（积分强度）报告。"
        )
        self._info_label.setWordWrap(True)
        form.addRow(self._info_label)
        layout.addLayout(form)

        self._run_button = QtWidgets.QPushButton("拟合")
        self._run_button.clicked.connect(self._run_fit)
        layout.addWidget(self._run_button)

        self._rwp_label = QtWidgets.QLabel("")
        self._rwp_label.setVisible(False)
        layout.addWidget(self._rwp_label)

        self._table = QtWidgets.QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(("2θ (°)", "FWHM (°)", "面积", "I-I₀ (%)"))
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        layout.addWidget(self._table, 1)

        buttons = QtWidgets.QHBoxLayout()
        self._apply_button = QtWidgets.QPushButton("应用到峰列表")
        self._apply_button.setEnabled(False)
        self._apply_button.clicked.connect(self._apply_to_peak_list)
        buttons.addWidget(self._apply_button)
        buttons.addStretch(1)
        close = QtWidgets.QPushButton("关闭")
        close.clicked.connect(self.reject)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    # ------------------------------------------------------------------
    def _run_fit(self) -> None:
        """拟合（工作线程）→ 结果表 / Rwp / 曲线叠加（GUI 线程）。"""
        shape = self._shape_combo.currentData()
        pattern = self._pattern
        peaks = self._initial_peaks
        started = run_with_busy(
            self,
            "Profile Fitting",
            f"正在对 {len(peaks)} 个峰做 {shape} 多峰最小二乘拟合…",
            lambda: fit_profile(
                np.asarray(pattern.two_theta, dtype=float),
                np.asarray(pattern.intensity, dtype=float),
                peaks,
                shape=shape,
            ),
            on_success=self._show_result,
            on_error=self._show_error,
        )
        if not started:
            return

    def _show_result(self, result) -> None:
        """回填结果表 + Rwp + 叠加拟合曲线（GUI 线程）。"""
        self._result = result
        fitted = result.fitted_peaks
        self._rwp_label.setText(f"Rwp = {result.rwp * 100:.2f} %")
        self._rwp_label.setVisible(True)
        self._table.setRowCount(len(fitted))
        i_max = max((p.intensity for p in fitted), default=0.0)
        for row, peak in enumerate(fitted):
            rel = f"{peak.intensity / i_max * 100.0:.2f}" if i_max > 0 else "0.00"
            for col, text in enumerate((
                f"{peak.two_theta:.4f}",
                "" if peak.fwhm is None else f"{peak.fwhm:.4f}",
                f"{peak.intensity:.4f}",
                rel,
            )):
                self._table.setItem(
                    row, col, QtWidgets.QTableWidgetItem(text)
                )
        self._apply_button.setEnabled(bool(fitted))
        # 拟合曲线叠加（替换上一条，不叠加多条）。
        self._remove_fit_curve()
        if self._view is not None and len(result.fitted_intensity):
            self._fit_curve_key = self._view.add_pattern(
                Pattern(np.asarray(self._pattern.two_theta, dtype=float),
                        np.asarray(result.fitted_intensity, dtype=float)),
                name=f"Profile Fit (Rwp {result.rwp * 100:.2f} %)",
            )

    def _show_error(self, message: str) -> None:
        QtWidgets.QMessageBox.warning(self, "拟合失败", message)

    def _apply_to_peak_list(self) -> None:
        """把精修后的峰写回主窗口峰列表（由主窗口接峰表 set_peaks）。"""
        if self._result is None:
            return
        self.fit_applied.emit(list(self._result.fitted_peaks))

    # ------------------------------------------------------------------
    def _remove_fit_curve(self) -> None:
        if self._fit_curve_key is not None and self._view is not None:
            try:
                self._view.remove_pattern(self._fit_curve_key)
            except Exception:  # pragma: no cover — 曲线已被外层清空
                logger.debug("remove fit curve failed", exc_info=True)
            self._fit_curve_key = None

    def closeEvent(self, event) -> None:  # noqa: N802 — Qt 命名
        self._remove_fit_curve()
        super().closeEvent(event)
