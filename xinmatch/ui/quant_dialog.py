"""定量分析对话框（RIR 绝热法，参考软件 quant_analysis_RIR）。

输入：已确认物相（匹配列表）+ 当前峰列表。每相主峰强度取其
``Phase.correlations`` 指向的实验峰的最大积分强度（重叠分解由上游
Search-Match 的相关记录承担，本对话框不做分解）。

计算：全委托 :func:`xinmatch.core.quant.rir.rir_quantify`（Hill–Howard
绝热法，wt% 归一到 1.0），不重写算法。RIR 值默认 1.0、逐相可编辑
（参考软件同样由用户按 PDF 卡片填写 I/Ic）。

「应用到匹配列表」把 wt% 写回 ``Phase.weight_fraction`` 并刷新匹配列表
（之后可用「数据导出 → 导出匹配列表 (CSV)…」带走 weight_pct 列）。
"""

from __future__ import annotations

import logging

from PySide6 import QtCore, QtWidgets

from xinmatch.core.model.phase import Phase
from xinmatch.core.quant.rir import rir_quantify

logger = logging.getLogger(__name__)

_HEADERS = ("物相", "主峰强度", "RIR (I/Ic)", "wt %")
_COL_NAME, _COL_INT, _COL_RIR, _COL_WT = range(4)


def _phase_label(phase: Phase) -> str:
    e = phase.entry
    return e.mineral_name or e.formula or e.entry_id


class QuantDialog(QtWidgets.QDialog):
    """RIR 定量分析对话框（已确认物相 → wt%）。"""

    #: 「应用到匹配列表」：携带写回 weight_fraction 后的 :class:`Phase` 列表。
    quant_applied = QtCore.Signal(list)

    def __init__(
        self,
        phases: list[Phase],
        peaks: list,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("定量分析 (RIR)")
        self.setMinimumWidth(560)
        self._phases = list(phases)
        self._peaks = list(peaks)
        self._main_intensity = self._compute_intensities()

        layout = QtWidgets.QVBoxLayout(self)
        note = QtWidgets.QLabel(
            "绝热法（Hill–Howard）：wt% = (Iᵢ/RIRᵢ) / Σ(Iⱼ/RIRⱼ)。\n"
            "主峰强度取该相已匹配实验峰的最大积分强度；RIR 默认 1.0，"
            "请按 PDF 卡片的 I/Ic 逐相修改。"
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        self._table = QtWidgets.QTableWidget(len(self._phases), 4)
        self._table.setHorizontalHeaderLabels(_HEADERS)
        self._table.verticalHeader().setVisible(False)
        # 相名 / 强度 / wt% 只读；RIR 列可编辑（双击或键入）。
        self._table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked
            | QtWidgets.QAbstractItemView.EditTrigger.SelectedClicked
            | QtWidgets.QAbstractItemView.EditTrigger.EditKeyPressed
        )
        for row, phase in enumerate(self._phases):
            intensity = self._main_intensity[phase.entry.entry_id]
            name_item = QtWidgets.QTableWidgetItem(_phase_label(phase))
            name_item.setData(
                QtCore.Qt.ItemDataRole.UserRole, phase.entry.entry_id
            )
            self._table.setItem(row, _COL_NAME, name_item)
            self._table.setItem(
                row, _COL_INT,
                QtWidgets.QTableWidgetItem(f"{intensity:.4f}"),
            )
            rir_item = QtWidgets.QTableWidgetItem("1.0")
            rir_item.setFlags(
                rir_item.flags() | QtCore.Qt.ItemFlag.ItemIsEditable
            )
            self._table.setItem(row, _COL_RIR, rir_item)
            self._table.setItem(row, _COL_WT, QtWidgets.QTableWidgetItem("—"))
        self._table.resizeColumnsToContents()
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table, 1)

        buttons = QtWidgets.QHBoxLayout()
        self._calc_button = QtWidgets.QPushButton("计算 wt%")
        self._calc_button.clicked.connect(self._run_calc)
        buttons.addWidget(self._calc_button)
        self._apply_button = QtWidgets.QPushButton("应用到匹配列表")
        self._apply_button.setEnabled(False)
        self._apply_button.clicked.connect(self._apply)
        buttons.addWidget(self._apply_button)
        buttons.addStretch(1)
        close = QtWidgets.QPushButton("关闭")
        close.clicked.connect(self.reject)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    # ------------------------------------------------------------------
    def _compute_intensities(self) -> dict[str, float]:
        """每相主峰强度 = correlations 指向的实验峰最大积分强度。"""
        out: dict[str, float] = {}
        for phase in self._phases:
            best = 0.0
            for exp_idx, _ref_idx in phase.correlations:
                if 0 <= exp_idx < len(self._peaks):
                    best = max(best, float(self._peaks[exp_idx].intensity))
            out[phase.entry.entry_id] = best
        return out

    def _run_calc(self) -> None:
        """读取 RIR 列 → rir_quantify → 回填 wt% 列（GUI 线程）。"""
        usable: dict[str, float] = {}
        rir_values: dict[str, float] = {}
        for row, phase in enumerate(self._phases):
            eid = phase.entry.entry_id
            if self._main_intensity[eid] <= 0:
                continue  # 无已匹配实验峰的相不参与计算
            try:
                rir = float(self._table.item(row, _COL_RIR).text())
            except (TypeError, ValueError):
                QtWidgets.QMessageBox.warning(
                    self, "RIR 无效",
                    f"第 {row + 1} 行的 RIR 不是数字，请修正后再计算。",
                )
                return
            usable[eid] = self._main_intensity[eid]
            rir_values[eid] = rir
        if not usable:
            QtWidgets.QMessageBox.information(
                self, "无可计算物相",
                "所有物相都没有已匹配的实验峰（强度为 0），无法定量。\n"
                "请先在候选列表确认物相（产生峰关联）。",
            )
            return
        try:
            fractions = rir_quantify(usable, rir_values)
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "计算失败", str(exc))
            return
        for row, phase in enumerate(self._phases):
            eid = phase.entry.entry_id
            text = (
                f"{fractions[eid] * 100.0:.2f}"
                if eid in fractions else "—"
            )
            self._table.setItem(
                row, _COL_WT, QtWidgets.QTableWidgetItem(text)
            )
        self._last_fractions = fractions
        self._apply_button.setEnabled(True)
        self._result_fractions: dict[str, float] = fractions

    def _apply(self) -> None:
        """把 wt% 写回 Phase.weight_fraction 并发信号刷新匹配列表。"""
        fractions = getattr(self, "_result_fractions", None)
        if not fractions:
            return
        updated: list[Phase] = []
        for phase in self._phases:
            eid = phase.entry.entry_id
            phase.weight_fraction = fractions.get(eid)
            updated.append(phase)
        self.quant_applied.emit(updated)
