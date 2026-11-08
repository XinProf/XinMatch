"""指标化向导（Treor90 / DicVol06）。

参考软件 *Tools → Indexing* 的 GUI 封装。计算全委托

* :func:`xinmatch.core.index.treor.index_treor`（试错法，Werner 1964/1985）
* :func:`xinmatch.core.index.dicvol.index_dicvol`（逐次二分法，Boultif & Louër 2004）

输入：峰列表（跳过用户标记为 ``excluded`` 的峰）。**d 值一律由 2θ 与当前波长
换算**（``d = λ / 2sinθ``），不用 ``Peak.d``——后者可能来自别的波长或参考卡。
core 内部会按 d 降序取前 20 条峰（Treor 1985 §3），本对话框不重复裁剪。

参数：算法、波长、容差（|Δ2θ|）、晶体系统。默认勾选高对称四系
（立方 / 四方 / 六方 / 正交），与 core 的默认一致；三方 / 单斜 / 三斜默认
不勾——低对称的试错空间大、耗时明显上升。

输出：候选解表（晶体系统 / a,b,c / α,β,γ / FoM / 已指标化峰数 / 程序），
按 FoM 降序（:func:`rank_solutions`），同胞解先经 :func:`deduplicate` 合并。
选中一行可把单胞参数复制到剪贴板（指标化结果暂无自动去处：精修向导需要
已鉴定相 + CIF，单胞不能直接注入）。
"""

from __future__ import annotations

import logging
import math

from PySide6 import QtWidgets

from xinmatch.core.index.dicvol import index_dicvol
from xinmatch.core.index.solutions import deduplicate, rank_solutions
from xinmatch.core.index.treor import index_treor
from xinmatch.ui.busy import run_with_busy

logger = logging.getLogger(__name__)

#: (key, 中文标签) —— 按高对称优先排列，勾选项按此顺序传给引擎。
_SYSTEMS = (
    ("cubic", "立方"),
    ("tetragonal", "四方"),
    ("hexagonal", "六方"),
    ("trigonal", "三方"),
    ("orthorhombic", "正交"),
    ("monoclinic", "单斜"),
    ("triclinic", "三斜"),
)
#: core 的默认集合（Treor 标准流程：高对称先试）。
_DEFAULT_CHECKED = ("cubic", "tetragonal", "hexagonal", "orthorhombic")

_HEADERS = (
    "晶体系统", "a (Å)", "b (Å)", "c (Å)",
    "α (°)", "β (°)", "γ (°)", "FoM", "已指标化峰", "程序",
)

#: 指标化至少需要几条线（立方 2 条即可定，其余系统要更多）。
_MIN_PEAKS = 4


def _d_from_two_theta(two_theta_deg: float, wavelength: float) -> float:
    """Bragg：d = λ / (2 sinθ)，θ = 2θ/2。"""
    theta = math.radians(two_theta_deg / 2.0)
    sin_theta = math.sin(theta)
    if sin_theta <= 0:
        raise ValueError(
            f"2θ must be in (0, 180), got {two_theta_deg}"
        )
    return wavelength / (2.0 * sin_theta)


class IndexingWizard(QtWidgets.QDialog):
    """Treor90 / DicVol06 指标化向导。"""

    def __init__(
        self,
        pattern,
        peaks: list,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("指标化 (Treor90 / DicVol06)")
        self.setMinimumWidth(780)
        self._pattern = pattern
        self._peaks = list(peaks)
        self._solutions: list = []

        layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QFormLayout()
        self._algo_combo = QtWidgets.QComboBox()
        self._algo_combo.addItem("Treor90（试错法）", userData="treor")
        self._algo_combo.addItem("DicVol06（逐次二分）", userData="dicvol")
        form.addRow("算法", self._algo_combo)

        self._lambda_spin = QtWidgets.QDoubleSpinBox()
        self._lambda_spin.setRange(0.1, 5.0)
        self._lambda_spin.setDecimals(4)
        self._lambda_spin.setSingleStep(0.0001)
        self._lambda_spin.setValue(float(getattr(pattern, "wavelength", 1.5406)))
        form.addRow("波长 λ (Å)", self._lambda_spin)

        self._tol_spin = QtWidgets.QDoubleSpinBox()
        self._tol_spin.setRange(0.001, 1.0)
        self._tol_spin.setDecimals(3)
        self._tol_spin.setSingleStep(0.005)
        self._tol_spin.setValue(0.05)
        form.addRow("容差 |Δ2θ| (°)", self._tol_spin)
        layout.addLayout(form)

        systems_box = QtWidgets.QGroupBox("晶体系统（按勾选顺序高对称优先尝试）")
        systems_layout = QtWidgets.QHBoxLayout(systems_box)
        self._system_checks: dict[str, QtWidgets.QCheckBox] = {}
        for key, label in _SYSTEMS:
            box = QtWidgets.QCheckBox(f"{label} ({key})")
            box.setChecked(key in _DEFAULT_CHECKED)
            systems_layout.addWidget(box)
            self._system_checks[key] = box
        layout.addWidget(systems_box)

        n_used = sum(1 for p in self._peaks if not p.excluded)
        n_skip = len(self._peaks) - n_used
        self._info_label = QtWidgets.QLabel(
            f"峰列表 {len(self._peaks)} 个峰，参与指标化 {n_used} 个"
            + (f"（跳过已排除 {n_skip} 个）" if n_skip else "")
            + "。\nd 值由 2θ 与当前波长换算；引擎内部按 d 降序取前 20 条线。\n"
            "三方 / 单斜 / 三斜的试错空间大，勾选后耗时明显增加。\n"
            "注意：同 FoM 的解按体积小优先排序，等效低对称胞（例如立方的"
            " a/2 四方描述）可能排在真对称之前 —— 请结合化学信息判断，"
            "不要只看第一行。"
        )
        self._info_label.setWordWrap(True)
        layout.addWidget(self._info_label)

        self._run_button = QtWidgets.QPushButton("指标化")
        self._run_button.clicked.connect(self._run_index)
        layout.addWidget(self._run_button)

        self._summary = QtWidgets.QLabel("（未计算）")
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)

        self._table = QtWidgets.QTableWidget(0, len(_HEADERS))
        self._table.setHorizontalHeaderLabels(_HEADERS)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        layout.addWidget(self._table, 1)

        buttons = QtWidgets.QHBoxLayout()
        self._copy_button = QtWidgets.QPushButton("复制选中单胞")
        self._copy_button.setEnabled(False)
        self._copy_button.clicked.connect(self._copy_selected)
        buttons.addWidget(self._copy_button)
        buttons.addStretch(1)
        close = QtWidgets.QPushButton("关闭")
        close.clicked.connect(self.reject)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    # ------------------------------------------------------------------
    def _selected_systems(self) -> list[str]:
        return [
            key for key, _label in _SYSTEMS
            if self._system_checks[key].isChecked()
        ]

    def _peak_d_values(self, wavelength: float) -> list[float]:
        """参与指标化的 d 值（跳过 excluded 峰，按 2θ 换算）。"""
        return [
            _d_from_two_theta(p.two_theta, wavelength)
            for p in self._peaks
            if not p.excluded
        ]

    def _run_index(self) -> None:
        """按当前参数求解（工作线程）→ 结果表（GUI 线程）。"""
        wavelength = float(self._lambda_spin.value())
        systems = self._selected_systems()
        if not systems:
            QtWidgets.QMessageBox.information(
                self,
                "未选择晶体系统",
                "请至少勾选一个晶体系统再指标化。",
            )
            return
        try:
            peak_d = self._peak_d_values(wavelength)
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "峰位非法", str(exc))
            return
        if len(peak_d) < _MIN_PEAKS:
            QtWidgets.QMessageBox.information(
                self,
                "峰太少",
                f"只有 {len(peak_d)} 个峰参与指标化（已排除的峰不计）。\n"
                f"至少需要 {_MIN_PEAKS} 个峰才能定出单胞，"
                "请增加峰或在峰列表里取消排除。",
            )
            return

        tolerance = float(self._tol_spin.value())
        algo = self._algo_combo.currentData()
        engine = index_treor if algo == "treor" else index_dicvol
        algo_label = self._algo_combo.currentText()

        started = run_with_busy(
            self,
            "指标化",
            f"正在用 {algo_label} 在 {len(systems)} 个晶体系统里搜索"
            f"（{len(peak_d)} 条线，容差 {tolerance}°）…",
            lambda: engine(
                peak_d,
                crystal_systems=systems,
                tolerance=tolerance,
                wavelength=wavelength,
            ),
            on_success=self._show_solutions,
            on_error=self._show_error,
        )
        if not started:
            return

    def _show_solutions(self, solutions: list) -> None:
        """去重 + 排序后填表（GUI 线程）。"""
        merged = deduplicate(solutions) if solutions else []
        ranked = rank_solutions(merged)
        self._solutions = ranked

        self._table.setRowCount(len(ranked))
        for row, sol in enumerate(ranked):
            cell = sol.cell
            values = (
                sol.crystal_system,
                f"{cell.a:.4f}",
                f"{cell.b:.4f}",
                f"{cell.c:.4f}",
                f"{cell.alpha:.3f}",
                f"{cell.beta:.3f}",
                f"{cell.gamma:.3f}",
                f"{sol.fom:.2f}",
                f"{sol.n_indexed}/{len(sol.hkl_assignments)}",
                sol.program,
            )
            for col, text in enumerate(values):
                self._table.setItem(
                    row, col, QtWidgets.QTableWidgetItem(text)
                )
        self._table.resizeColumnsToContents()
        self._copy_button.setEnabled(bool(ranked))

        if not ranked:
            self._summary.setText(
                "未找到候选解 —— 可放宽容差、增加晶体系统或换算法重试。"
            )
            return
        if len(ranked) == len(solutions):
            detail = f"得到 {len(ranked)} 个候选解（已按 FoM 降序）"
        else:
            detail = (
                f"得到 {len(solutions)} 个解，同胞合并后 {len(ranked)} 个"
                "（已按 FoM 降序）"
            )
        self._summary.setText(detail)

    def _show_error(self, message: str) -> None:
        QtWidgets.QMessageBox.warning(self, "指标化失败", message)

    def _copy_selected(self) -> None:
        """把选中行的单胞参数复制到剪贴板。"""
        row = self._table.currentRow()
        if row < 0 or row >= len(self._solutions):
            return
        cell = self._solutions[row].cell
        text = (
            f"a={cell.a:.5f} b={cell.b:.5f} c={cell.c:.5f} "
            f"alpha={cell.alpha:.3f} beta={cell.beta:.3f} "
            f"gamma={cell.gamma:.3f}"
        )
        QtWidgets.QApplication.clipboard().setText(text)
        self._summary.setText(f"已复制单胞参数到剪贴板：{text}")
