"""MAUD 风格 Rietveld 精修向导（T13.8）。

分步引导用户完成：选相 → 背景 → 参数组 → 运行 → 结果展示。

设计参照 *Quantify → Rietveld* 工作流（``docs/Rietveld.md``）和 MAUD 的
向导式设计。精修全部委托 GSAS-II 子进程执行，本模块只负责参数收集、
进度显示和结果可视化。

Steps
-----
1. **选相**：从已鉴定相列表勾选参与精修的相，每相对应一个 CIF。
2. **背景**：是否精修背景多项式、阶数选择。
3. **参数组**：勾选要精修的参数组（Scale / Cell / Profile / Atoms）。
4. **运行与结果**：启动精修 → 显示 R 因子、残差谱（obs/calc/residual）、
   精修后晶胞参数表。

API
---
::

    wizard = RefinementWizard(phases, cif_paths, pattern, options=opts)
    wizard.refinement_finished.connect(on_done)
    wizard.exec()

无 GSAS-II 环境时弹出友好提示而非崩溃。运行后端（driver 函数）可注入，
便于在无 GSAS-II 的 CI 环境测试向导全流程。
"""

from __future__ import annotations

import traceback
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pyqtgraph as pg
from PySide6 import QtCore, QtWidgets

from xinmatch.core.model.pattern import Pattern
from xinmatch.core.model.phase import Phase
from xinmatch.core.refine.gsas2_adapter import RefineOptions
from xinmatch.core.refine.gsas2_parse import Gsas2RefineOutcome

__all__ = ["RefinementWizard", "run_wizard"]


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------
class RefinementWizard(QtWidgets.QDialog):
    """Rietveld 精修向导对话框。

    Parameters
    ----------
    phases:
        已鉴定相列表。
    cif_paths:
        ``entry_id -> CIF 文件路径`` 映射。
    pattern:
        实验衍射谱。
    options:
        初始 :class:`RefineOptions`（默认值可在向导中修改）。
    parent:
        父控件。
    driver:
        可注入的精修驱动函数。签名::

            driver(pattern, phases, cif_paths, options, work_dir) -> outcome

        其中 ``outcome`` 是 :class:`Gsas2RefineOutcome`。``None`` 时使用
        默认的 GSAS-II 子进程驱动。
    """

    #: 精修完成信号，参数为 :class:`Gsas2RefineOutcome`。
    refinement_finished = QtCore.Signal(object)

    def __init__(
        self,
        phases: Sequence[Phase],
        cif_paths: Mapping[str, str | Path],
        pattern: Pattern,
        options: RefineOptions | None = None,
        parent: QtWidgets.QWidget | None = None,
        *,
        driver: Callable[..., Gsas2RefineOutcome] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Rietveld 精修向导")
        self.setMinimumSize(720, 560)

        self._phases = list(phases)
        self._cif_paths = {str(k): str(v) for k, v in cif_paths.items()}
        self._pattern = pattern
        self._options = options or RefineOptions()
        self._injected_driver = driver
        self._outcome: Gsas2RefineOutcome | None = None

        # ---- Stacked pages ------------------------------------------------
        self._stack = QtWidgets.QStackedWidget()
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._stack)

        self._page1 = self._build_phase_page()
        self._page2 = self._build_background_page()
        self._page3 = self._build_params_page()
        self._page4 = self._build_result_page()

        for page in (self._page1, self._page2, self._page3, self._page4):
            self._stack.addWidget(page)

        # ---- Navigation buttons -------------------------------------------
        self._btn_back = QtWidgets.QPushButton("< 上一步")
        self._btn_next = QtWidgets.QPushButton("下一步 >")
        self._btn_run = QtWidgets.QPushButton("开始精修")
        self._btn_finish = QtWidgets.QPushButton("完成")
        self._btn_finish.setEnabled(False)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(self._btn_back)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_next)
        btn_row.addWidget(self._btn_run)
        btn_row.addWidget(self._btn_finish)
        layout.addLayout(btn_row)

        self._btn_back.clicked.connect(self._go_back)
        self._btn_next.clicked.connect(self._go_next)
        self._btn_run.clicked.connect(self._run_refinement)
        self._btn_finish.clicked.connect(self.accept)

        self._update_nav()

    # ------------------------------------------------------------------
    # Page 1: phase selection
    # ------------------------------------------------------------------
    def _build_phase_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(page)
        v.addWidget(QtWidgets.QLabel(
            "<b>步骤 1：选择参与精修的相</b><br>"
            "勾选需要纳入 Rietveld 全谱拟合的物相。"
        ))
        self._phase_checks: dict[str, QtWidgets.QCheckBox] = {}
        for ph in self._phases:
            eid = str(ph.entry.entry_id)
            name = ph.entry.mineral_name or eid
            formula = ph.entry.formula or ""
            cb = QtWidgets.QCheckBox(f"{name}  ({formula})")
            cb.setChecked(True)
            self._phase_checks[eid] = cb
            v.addWidget(cb)
        v.addStretch()
        return page

    # ------------------------------------------------------------------
    # Page 2: background
    # ------------------------------------------------------------------
    def _build_background_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(page)
        v.addWidget(QtWidgets.QLabel(
            "<b>步骤 2：背景处理</b><br>"
            "选择是否精修背景多项式及其阶数。"
        ))
        self._chk_bkg = QtWidgets.QCheckBox("精修背景（Chebyshev 多项式）")
        self._chk_bkg.setChecked(self._options.refine_background)
        v.addWidget(self._chk_bkg)

        v.addWidget(QtWidgets.QLabel("背景阶数："))
        self._spn_bkg_order = QtWidgets.QSpinBox()
        self._spn_bkg_order.setRange(3, 16)
        self._spn_bkg_order.setValue(8)
        v.addWidget(self._spn_bkg_order)
        v.addStretch()
        return page

    # ------------------------------------------------------------------
    # Page 3: parameter groups
    # ------------------------------------------------------------------
    def _build_params_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(page)
        v.addWidget(QtWidgets.QLabel(
            "<b>步骤 3：选择精修参数组</b><br>"
            "勾选需要打开的精修参数。Scale（尺度因子）由 GSAS-II 自动精修。"
        ))
        # Scale — always on in GSAS-II, shown as info
        lb_scale = QtWidgets.QLabel("☑ Scale factor（尺度因子，自动精修）")
        lb_scale.setStyleSheet("color: #555;")
        v.addWidget(lb_scale)

        self._chk_cell = QtWidgets.QCheckBox("☑ Unit cell（晶胞参数）")
        self._chk_cell.setChecked(True)
        self._chk_cell.setEnabled(False)  # always on in driver
        v.addWidget(self._chk_cell)

        self._chk_profile = QtWidgets.QCheckBox("Peak profile（峰形 U/V/W）")
        self._chk_profile.setChecked(self._options.refine_profile)
        v.addWidget(self._chk_profile)

        self._chk_atoms = QtWidgets.QCheckBox(
            "Atomic coordinates + Uiso（原子坐标 + 热参数）"
        )
        self._chk_atoms.setChecked(self._options.refine_atoms)
        v.addWidget(self._chk_atoms)

        v.addWidget(QtWidgets.QLabel("最大迭代次数："))
        self._spn_max_iter = QtWidgets.QSpinBox()
        self._spn_max_iter.setRange(5, 500)
        self._spn_max_iter.setValue(self._options.max_iter)
        v.addWidget(self._spn_max_iter)

        v.addStretch()
        return page

    # ------------------------------------------------------------------
    # Page 4: run / result
    # ------------------------------------------------------------------
    def _build_result_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(page)

        self._lbl_status = QtWidgets.QLabel("准备就绪，点击「开始精修」运行。")
        self._lbl_status.setWordWrap(True)
        v.addWidget(self._lbl_status)

        self._progress = QtWidgets.QProgressBar()
        self._progress.setRange(0, 0)  # busy indicator
        self._progress.setVisible(False)
        v.addWidget(self._progress)

        # R-factors summary
        self._lbl_rfactors = QtWidgets.QLabel("")
        self._lbl_rfactors.setVisible(False)
        v.addWidget(self._lbl_rfactors)

        # Residual profile plot
        self._plot = pg.PlotWidget()
        self._plot.setLabel("bottom", "2θ", units="°")
        self._plot.setLabel("left", "Intensity", units="counts")
        self._plot.showGrid(x=True, y=True, alpha=0.25)
        self._plot.addLegend(offset=(12, 12))
        v.addWidget(self._plot)

        # Refined cell table
        self._table = QtWidgets.QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            ["相", "a (Å)", "c (Å)", "wt%"]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        v.addWidget(self._table)

        # Refined-CIF actions (3D view / export) — enabled after a run that
        # produced refined CIFs.
        btn_row = QtWidgets.QHBoxLayout()
        self._btn_view3d = QtWidgets.QPushButton("查看精修后 3D 结构…")
        self._btn_view3d.setEnabled(False)
        self._btn_view3d.setToolTip(
            "用 3Dmol.js 显示 GSAS-II 导出的精修后晶体结构（*_new.cif）"
        )
        self._btn_export_cif = QtWidgets.QPushButton("导出精修 CIF…")
        self._btn_export_cif.setEnabled(False)
        self._btn_export_cif.setToolTip(
            "把精修后 CIF 复制到用户选择的目录（供外部工具复用）"
        )
        btn_row.addWidget(self._btn_view3d)
        btn_row.addWidget(self._btn_export_cif)
        btn_row.addStretch()
        v.addLayout(btn_row)

        self._btn_view3d.clicked.connect(self._show_refined_3d)
        self._btn_export_cif.clicked.connect(self._export_refined_cifs)

        return page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def _current_index(self) -> int:
        return self._stack.currentIndex()

    def _go_back(self) -> None:
        if self._current_index() > 0:
            self._stack.setCurrentIndex(self._current_index() - 1)
            self._update_nav()

    def _go_next(self) -> None:
        idx = self._current_index()
        if idx == 0:
            # Validate at least one phase selected
            selected = [
                eid for eid, cb in self._phase_checks.items() if cb.isChecked()
            ]
            if not selected:
                QtWidgets.QMessageBox.warning(
                    self, "未选相", "请至少选择一个相进行精修。"
                )
                return
        if idx < 3:
            self._stack.setCurrentIndex(idx + 1)
        self._update_nav()

    def _update_nav(self) -> None:
        idx = self._current_index()
        self._btn_back.setEnabled(idx > 0)
        self._btn_next.setVisible(idx < 3)
        self._btn_run.setVisible(idx == 3)
        self._btn_finish.setVisible(idx == 3 and self._outcome is not None)

    # ------------------------------------------------------------------
    # Run refinement
    # ------------------------------------------------------------------
    def _collect_options(self) -> RefineOptions:
        return RefineOptions(
            max_iter=self._spn_max_iter.value(),
            refine_atoms=self._chk_atoms.isChecked(),
            refine_background=self._chk_bkg.isChecked(),
            refine_profile=self._chk_profile.isChecked(),
            wavelength=self._options.wavelength,
            two_theta_range=self._options.two_theta_range,
        )

    def _selected_phases(self) -> list[Phase]:
        selected_ids = {
            eid for eid, cb in self._phase_checks.items() if cb.isChecked()
        }
        return [ph for ph in self._phases if str(ph.entry.entry_id) in selected_ids]

    def _run_refinement(self) -> None:
        self._lbl_status.setText("正在运行 GSAS-II 精修，请稍候…")
        self._progress.setVisible(True)
        self._btn_run.setEnabled(False)
        self._btn_next.setEnabled(False)
        QtWidgets.QApplication.processEvents()

        # Check GSAS-II availability
        from xinmatch.core.refine.gsas2_project import GSAS2_AVAILABLE

        if not GSAS2_AVAILABLE and self._injected_driver is None:
            self._progress.setVisible(False)
            self._btn_run.setEnabled(True)
            QtWidgets.QMessageBox.information(
                self,
                "未检测到 GSAS-II",
                "未检测到 GSAS-II 运行环境。\n\n"
                "可先生成项目文件（.gpx / driver / manifest），"
                "稍后在装有 GSAS-II 的机器上手动运行。",
            )
            self._lbl_status.setText(
                "未检测到 GSAS-II。可在命令行使用 "
                "build_gsas2_project(run=False) 生成项目文件。"
            )
            return

        options = self._collect_options()
        phases = self._selected_phases()

        try:
            outcome = self._execute_driver(phases, options)
            self._outcome = outcome
            self._show_result(outcome)
        except Exception as exc:
            self._progress.setVisible(False)
            self._btn_run.setEnabled(True)
            self._lbl_status.setText(f"精修失败：{exc}")
            traceback.print_exc()

    def _execute_driver(
        self, phases: list[Phase], options: RefineOptions
    ) -> Gsas2RefineOutcome:
        """Run the refinement (injected driver or default GSAS-II path)."""
        if self._injected_driver is not None:
            return self._injected_driver(
                self._pattern, phases, self._cif_paths, options
            )

        # Default: call build_gsas2_project + parse_refinement
        import tempfile

        from xinmatch.core.refine.gsas2_parse import parse_refinement
        from xinmatch.core.refine.gsas2_project import build_gsas2_project

        work_dir = Path(tempfile.mkdtemp(prefix="xinmatch_wizard_"))
        proj = build_gsas2_project(
            self._pattern,
            phases,
            self._cif_paths,  # type: ignore[arg-type]
            options=options,
            work_dir=work_dir,
            project_name="wizard",
            run=True,
        )
        cifs = [str(c) for c in proj.refined_cifs] if proj.refined_cifs else None
        if proj.lst_path is None or proj.prf_path is None:
            raise RuntimeError("精修工程缺少 .lst/.prf 产物路径")
        outcome = parse_refinement(
            proj.lst_path,
            proj.prf_path,
            cifs=cifs,  # type: ignore[arg-type]
            gpx=proj.gpx_path,
        )
        return outcome

    # ------------------------------------------------------------------
    # Display results
    # ------------------------------------------------------------------
    def _show_result(self, outcome: Gsas2RefineOutcome) -> None:
        self._progress.setVisible(False)
        self._btn_run.setEnabled(True)

        rf = outcome.r_factors
        rwp_pct = rf.rwp * 100 if rf.rwp is not None else float("nan")
        rp_pct = rf.rp * 100 if rf.rp is not None else float("nan")
        chi2 = rf.chi2 if rf.chi2 is not None else float("nan")
        gof = outcome.gof if outcome.gof is not None else float("nan")

        self._lbl_status.setText("精修完成。")
        self._lbl_rfactors.setVisible(True)
        self._lbl_rfactors.setText(
            f"<b>Rwp = {rwp_pct:.2f}%</b>　"
            f"Rp = {rp_pct:.2f}%　"
            f"χ² = {chi2:.2f}　"
            f"GoF = {gof:.2f}"
        )

        # Plot observed / fitted / residual
        self._plot.clear()
        colors = {"obs": "#1f77b4", "calc": "#d62728", "resid": "#2ca02c"}
        for pat, label, color in [
            (outcome.observed_pattern, "Observed", colors["obs"]),
            (outcome.fitted_pattern, "Calculated", colors["calc"]),
            (outcome.residual_pattern, "Residual", colors["resid"]),
        ]:
            curve = pg.PlotDataItem(
                pat.two_theta, pat.intensity,
                pen=pg.mkPen(color, width=1.0), name=label,
                autoDownsample=True, connect="all",
            )
            self._plot.addItem(curve)
            curve.opts["clipToView"] = True

        # Refined cell table
        self._table.setRowCount(len(outcome.refined_phases))
        for row, rph in enumerate(outcome.refined_phases):
            ph = rph.phase
            cell = ph.entry.cell
            if cell is None:
                continue
            name = ph.entry.mineral_name or ph.entry.entry_id
            wf = ph.weight_fraction
            wt_pct = f"{wf * 100:.2f}" if wf is not None else "—"
            self._table.setItem(row, 0, QtWidgets.QTableWidgetItem(name))
            self._table.setItem(row, 1, QtWidgets.QTableWidgetItem(f"{cell.a:.4f}"))
            self._table.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{cell.c:.4f}"))
            self._table.setItem(row, 3, QtWidgets.QTableWidgetItem(wt_pct))

        # Enable refined-CIF actions when GSAS-II exported phase CIFs.
        has_cifs = bool(getattr(outcome, "refined_cif_paths", None))
        self._btn_view3d.setEnabled(has_cifs)
        self._btn_export_cif.setEnabled(has_cifs)

        self._update_nav()
        self.refinement_finished.emit(outcome)

    # ------------------------------------------------------------------
    # Refined-CIF actions (Phase 16 integration)
    # ------------------------------------------------------------------
    def _refined_cif_paths(self) -> list[Path]:
        return list(getattr(self._outcome, "refined_cif_paths", None) or [])

    def _show_refined_3d(self) -> None:
        """Open the 3D viewer on the GSAS-II refined CIF of the chosen phase."""
        from xinmatch.ui.structure_view import StructureViewDialog

        paths = self._refined_cif_paths()
        if not paths:
            QtWidgets.QMessageBox.information(
                self, "无精修 CIF", "本次精修没有生成精修后 CIF。"
            )
            return
        if self._outcome is None:
            return
        idx = 0
        if len(paths) > 1:
            names = [
                (rph.phase.entry.mineral_name or rph.phase.entry.entry_id)
                for rph in self._outcome.refined_phases
            ]
            names = [n if n else f"相 {i + 1}" for i, n in enumerate(names)]
            choice, ok = QtWidgets.QInputDialog.getItem(
                self, "选择相", "查看精修后结构的相：", names, 0, False
            )
            if not ok:
                return
            idx = names.index(choice)
        dialog = StructureViewDialog(self)
        dialog.load_cif(paths[idx])  # friendly page if parse fails
        dialog.setWindowTitle(
            f"3D 结构视图 — 精修后（{Path(paths[idx]).name}）"
        )
        dialog.exec()

    def _export_refined_cifs(self) -> None:
        """Copy the refined CIFs into a user-chosen directory."""
        from xinmatch.core.refine.cif_store import export_cifs

        paths = self._refined_cif_paths()
        if not paths:
            QtWidgets.QMessageBox.information(
                self, "无精修 CIF", "本次精修没有生成精修后 CIF。"
            )
            return
        out_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self, "选择导出目录（精修后 CIF）"
        )
        if not out_dir:
            return
        exported = export_cifs(
            {f"phase{i + 1}": p for i, p in enumerate(paths)}, out_dir
        )
        QtWidgets.QMessageBox.information(
            self,
            "导出完成",
            f"已导出 {len(exported)} 个精修后 CIF：\n{Path(out_dir)}\n"
            + "\n".join(f"• {name}.cif" for name in exported),
        )


# ---------------------------------------------------------------------------
# Convenience entry
# ---------------------------------------------------------------------------
def run_wizard(
    phases: Sequence[Phase],
    cif_paths: dict[str, str | Path],
    pattern: Pattern,
    options: RefineOptions | None = None,
    parent: QtWidgets.QWidget | None = None,
) -> Gsas2RefineOutcome | None:
    """创建并模态运行 :class:`RefinementWizard`，返回精修结果。

    Parameters
    ----------
    phases:
        已鉴定相列表。
    cif_paths:
        ``entry_id -> CIF 路径`` 映射。
    pattern:
        实验衍射谱。
    options:
        初始精修选项。
    parent:
        父控件。

    Returns
    -------
    Gsas2RefineOutcome or None
        精修结果；用户取消或未运行时返回 ``None``。
    """
    wizard = RefinementWizard(phases, cif_paths, pattern, options, parent)
    wizard.exec()
    return wizard._outcome
