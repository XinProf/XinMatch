"""Tests for the Rietveld refinement wizard (T13.8).

Uses the offscreen ``qapp`` fixture.  The wizard can be driven end-to-end
with an injected fake driver (no GSAS-II needed), and the no-GSAS-II
fallback dialog is verified.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from xinmatch.core.model.entry import CellParams, Entry
from xinmatch.core.model.pattern import Pattern
from xinmatch.core.model.phase import Phase
from xinmatch.core.quant.rietveld_quant import RietveldQuantResult  # noqa: F401
from xinmatch.core.refine.gsas2_parse import Gsas2RefineOutcome
from xinmatch.ui.refinement_wizard import RefinementWizard

_FIX = Path(__file__).resolve().parent.parent / "fixtures" / "gsas2_project"
_CIF = {
    "Al2O3": _FIX / "Al2O3.cif",
    "ZnO": _FIX / "ZnO.cif",
    "CaF2": _FIX / "CaF2.cif",
}


def _entry(entry_id: str, formula: str, cell: CellParams) -> Entry:
    return Entry(
        entry_id=entry_id, formula=formula,
        d_spacings=np.array([2.5, 2.0]), intensities=np.array([100.0, 40.0]),
        mineral_name=entry_id, cell=cell,
    )


def _phases() -> list[Phase]:
    return [
        Phase(entry=_entry("Al2O3", "Al2 O3",
                           CellParams(4.7592, 4.7592, 12.9918, 90, 90, 120))),
        Phase(entry=_entry("ZnO", "Zn O", CellParams(3.2494, 3.2494, 5.2054))),
        Phase(entry=_entry("CaF2", "Ca F2", CellParams(5.4632, 5.4632, 5.4632))),
    ]


def _pattern() -> Pattern:
    x = np.linspace(10.0, 80.0, 500)
    y = 100.0 + 50.0 * np.exp(-((x - 35.0) ** 2) / 5.0)
    return Pattern(two_theta=x, intensity=y, wavelength=1.5406, step=0.14)


def _fake_outcome(
    refined_cif_paths: list[Path] | None = None,
) -> Gsas2RefineOutcome:
    """Build a synthetic outcome for wizard testing."""
    from xinmatch.core.refine.gsas2_parse import RefinedPhaseInfo
    from xinmatch.core.report.report_model import RFactorSection

    x = np.linspace(10.0, 80.0, 200)
    obs = Pattern(x, np.full_like(x, 500.0), metadata={"source": "fake"})
    calc = Pattern(x, np.full_like(x, 490.0), metadata={"source": "fake"})
    resid = Pattern(x, np.full_like(x, 10.0), metadata={"source": "fake"})

    refined = []
    for name, wf, cell in [
        ("Al2O3", 0.05, CellParams(4.759, 4.759, 12.99, 90, 90, 120)),
        ("ZnO", 0.93, CellParams(3.249, 3.249, 5.205)),
        ("CaF2", 0.02, CellParams(5.463, 5.463, 5.463)),
    ]:
        ph = Phase(entry=_entry(name, "X", cell), weight_fraction=wf)
        refined.append(RefinedPhaseInfo(phase=ph, atoms=[]))

    return Gsas2RefineOutcome(
        r_factors=RFactorSection(rwp=0.08, rp=0.05, rexp=0.04, chi2=1.2),
        gof=1.1,
        observed_pattern=obs,
        fitted_pattern=calc,
        residual_pattern=resid,
        refined_phases=refined,
        raw=None,  # type: ignore[arg-type]
        refined_cif_paths=refined_cif_paths or [],
    )


class TestRefinementWizard:
    """Wizard flow tests with injected fake driver."""

    def test_wizard_initial_pages(self, qapp):
        wizard = RefinementWizard(
            _phases(), {k: str(v) for k, v in _CIF.items()}, _pattern(),
        )
        assert wizard._stack.count() == 4
        assert wizard._current_index() == 0
        wizard.close()

    def test_navigation_forward_back(self, qapp):
        wizard = RefinementWizard(
            _phases(), {k: str(v) for k, v in _CIF.items()}, _pattern(),
        )
        # Page 1 -> page 2
        wizard._go_next()
        assert wizard._current_index() == 1
        # Page 2 -> page 3
        wizard._go_next()
        assert wizard._current_index() == 2
        # Page 3 -> page 4
        wizard._go_next()
        assert wizard._current_index() == 3
        # Back: page 4 -> page 3
        wizard._go_back()
        assert wizard._current_index() == 2
        wizard.close()

    def test_no_phase_selected_warns(self, qapp):
        wizard = RefinementWizard(
            _phases(), {k: str(v) for k, v in _CIF.items()}, _pattern(),
        )
        # Uncheck all phases
        for cb in wizard._phase_checks.values():
            cb.setChecked(False)
        # Going next should warn and not advance
        # We patch QMessageBox.warning to avoid blocking
        from unittest.mock import patch
        with (
            patch.object(wizard, "_current_index", return_value=0),
            patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn,
        ):
            wizard._go_next()
            mock_warn.assert_called_once()
        wizard.close()

    def test_run_with_injected_driver(self, qapp):
        """With an injected fake driver, the wizard completes and shows results."""
        received: list = []

        def fake_driver(pattern, phases, cif_paths, options, work_dir=None):
            return _fake_outcome()

        wizard = RefinementWizard(
            _phases(), {k: str(v) for k, v in _CIF.items()}, _pattern(),
            driver=fake_driver,
        )
        wizard.refinement_finished.connect(received.append)

        # Navigate to page 4
        wizard._go_next()
        wizard._go_next()
        wizard._go_next()

        # Run refinement
        wizard._run_refinement()

        assert wizard._outcome is not None
        assert len(received) == 1
        assert received[0] is wizard._outcome
        # Result table populated
        assert wizard._table.rowCount() == 3
        # R-factor label visible
        assert "Rwp" in wizard._lbl_rfactors.text()
        # No refined CIFs -> 3D/export actions stay disabled
        assert wizard._btn_view3d.isEnabled() is False
        assert wizard._btn_export_cif.isEnabled() is False
        wizard.close()

    def test_refined_cif_actions_enabled_when_paths_present(self, qapp, tmp_path):
        """With refined_cif_paths on the outcome, 3D / export buttons enable."""
        cif = tmp_path / "ZnO_new.cif"
        cif.write_text("data_ZnO_new\n", encoding="utf-8")

        def fake_driver(pattern, phases, cif_paths, options, work_dir=None):
            return _fake_outcome(refined_cif_paths=[cif])

        wizard = RefinementWizard(
            _phases(), {k: str(v) for k, v in _CIF.items()}, _pattern(),
            driver=fake_driver,
        )
        wizard._go_next()
        wizard._go_next()
        wizard._go_next()
        wizard._run_refinement()

        assert wizard._btn_view3d.isEnabled() is True
        assert wizard._btn_export_cif.isEnabled() is True
        # Refined CIF paths surfaced in same order as refined phases
        assert wizard._outcome.refined_cif_paths == [cif.resolve()]
        wizard.close()

    def test_refined_3d_without_paths_shows_info(self, qapp):
        """3D button without refined CIFs informs the user instead of crashing."""
        from unittest.mock import patch

        def fake_driver(pattern, phases, cif_paths, options, work_dir=None):
            return _fake_outcome()  # no refined_cif_paths

        wizard = RefinementWizard(
            _phases(), {k: str(v) for k, v in _CIF.items()}, _pattern(),
            driver=fake_driver,
        )
        wizard._go_next()
        wizard._go_next()
        wizard._go_next()
        wizard._run_refinement()

        with patch(
            "PySide6.QtWidgets.QMessageBox.information"
        ) as mock_info:
            wizard._show_refined_3d()
            mock_info.assert_called_once()
        wizard.close()

    def test_options_collected(self, qapp):
        wizard = RefinementWizard(
            _phases(), {k: str(v) for k, v in _CIF.items()}, _pattern(),
        )
        wizard._chk_atoms.setChecked(True)
        wizard._chk_bkg.setChecked(False)
        wizard._chk_profile.setChecked(True)
        wizard._spn_max_iter.setValue(50)

        opts = wizard._collect_options()
        assert opts.refine_atoms is True
        assert opts.refine_background is False
        assert opts.refine_profile is True
        assert opts.max_iter == 50
        wizard.close()

    def test_params_page_has_po_and_size_strain_checkboxes(self, qapp):
        """The advanced-parameter page exposes PO and size/strain checkboxes."""
        wizard = RefinementWizard(
            _phases(), {k: str(v) for k, v in _CIF.items()}, _pattern(),
        )
        # Navigate to page 3 (params)
        wizard._go_next()
        wizard._go_next()
        assert wizard._current_index() == 2
        # Both checkboxes exist and default to False (from RefineOptions defaults)
        assert wizard._chk_po.isChecked() is False
        assert wizard._chk_size_strain.isChecked() is False
        wizard.close()

    def test_po_and_size_strain_options_mapped(self, qapp):
        """Checking the new boxes propagates into RefineOptions."""
        wizard = RefinementWizard(
            _phases(), {k: str(v) for k, v in _CIF.items()}, _pattern(),
        )
        wizard._chk_po.setChecked(True)
        wizard._chk_size_strain.setChecked(True)
        opts = wizard._collect_options()
        assert opts.refine_po is True
        assert opts.refine_size_strain is True
        wizard.close()

    def test_injected_driver_receives_po_and_size_strain(self, qapp):
        """End-to-end: with both advanced boxes checked, the fake driver
        receives a RefineOptions with both flags True."""
        received: list = []

        def fake_driver(pattern, phases, cif_paths, options, work_dir=None):
            received.append(options)
            return _fake_outcome()

        wizard = RefinementWizard(
            _phases(), {k: str(v) for k, v in _CIF.items()}, _pattern(),
            driver=fake_driver,
        )
        wizard._go_next()
        wizard._go_next()
        wizard._go_next()
        # Check the advanced boxes on the params page (page index 2)
        wizard._chk_po.setChecked(True)
        wizard._chk_size_strain.setChecked(True)
        wizard._go_next()
        wizard._run_refinement()

        assert len(received) == 1
        opts = received[0]
        assert opts.refine_po is True
        assert opts.refine_size_strain is True
        wizard.close()

    def test_selected_phases_filter(self, qapp):
        wizard = RefinementWizard(
            _phases(), {k: str(v) for k, v in _CIF.items()}, _pattern(),
        )
        # Uncheck CaF2
        wizard._phase_checks["CaF2"].setChecked(False)
        selected = wizard._selected_phases()
        assert len(selected) == 2
        names = [str(p.entry.entry_id) for p in selected]
        assert "CaF2" not in names
        wizard.close()

    def test_run_wizard_convenience(self, qapp):
        """run_wizard() returns the outcome when a driver is injected."""
        def fake_driver(pattern, phases, cif_paths, options, work_dir=None):
            return _fake_outcome()

        # We can't call .exec() in offscreen mode (it blocks), so test
        # the wizard construction directly.
        wizard = RefinementWizard(
            _phases(), {k: str(v) for k, v in _CIF.items()}, _pattern(),
            driver=fake_driver,
        )
        wizard._go_next()
        wizard._go_next()
        wizard._go_next()
        wizard._run_refinement()
        assert wizard._outcome is not None
        wizard.close()

    # ------------------------------------------------------------------
    # 2026-11-08 regression: refinement must not run on the GUI thread
    # ------------------------------------------------------------------
    def test_refinement_runs_off_gui_thread(self, qapp):
        """``_execute_driver`` 必须在工作线程执行，不能独占 GUI 线程。

        回归：旧 ``_run_refinement`` 同步调 driver（GSAS-II 子进程几十秒到
        几分钟），窗口变成「(未响应)」+ 白屏，用户以为程序挂了。
        """
        import threading

        main_ident = threading.get_ident()
        seen: list[int] = []

        def fake_driver(pattern, phases, cif_paths, options, work_dir=None):
            seen.append(threading.get_ident())
            return _fake_outcome()

        wizard = RefinementWizard(
            _phases(), {k: str(v) for k, v in _CIF.items()}, _pattern(),
            driver=fake_driver,
        )
        wizard._go_next()
        wizard._go_next()
        wizard._go_next()
        wizard._run_refinement()

        assert seen, "driver 没有被调用"
        assert seen[0] != main_ident, "driver 仍在 GUI 线程执行（会卡死窗口）"
        assert wizard._outcome is not None
        wizard.close()

    def test_running_state_locks_navigation(self, qapp):
        """运行期间导航与「开始精修」必须锁住，结束后解锁。"""
        wizard = RefinementWizard(
            _phases(), {k: str(v) for k, v in _CIF.items()}, _pattern(),
            driver=lambda *a, **kw: _fake_outcome(),
        )
        wizard._go_next()
        wizard._go_next()
        wizard._go_next()

        wizard._set_running(True)
        assert wizard._btn_run.isEnabled() is False
        assert wizard._btn_next.isEnabled() is False

        wizard._set_running(False)
        assert wizard._btn_run.isEnabled() is True
        assert wizard._btn_next.isEnabled() is True
        wizard.close()

    def test_empty_selection_refuses_to_run(self, qapp):
        """没有勾选任何相时不启动精修（避免把空相列表喂给 GSAS-II）。"""
        from unittest.mock import patch

        calls: list = []

        def fake_driver(*a, **kw):  # pragma: no cover - 不应被调用
            calls.append(1)
            return _fake_outcome()

        wizard = RefinementWizard(
            _phases(), {k: str(v) for k, v in _CIF.items()}, _pattern(),
            driver=fake_driver,
        )
        wizard._go_next()
        wizard._go_next()
        wizard._go_next()
        for cb in wizard._phase_checks.values():
            cb.setChecked(False)

        with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn:
            wizard._run_refinement()
            mock_warn.assert_called_once()
        assert not calls
        assert wizard._outcome is None
        wizard.close()

    def test_failure_is_reported_not_raised(self, qapp):
        """driver 抛异常时给出失败文案，向导不崩、不留「运行中」状态。"""
        from unittest.mock import patch

        def boom(*a, **kw):
            raise RuntimeError("GSAS-II 未找到可用的仪器参数")

        wizard = RefinementWizard(
            _phases(), {k: str(v) for k, v in _CIF.items()}, _pattern(),
            driver=boom,
        )
        wizard._go_next()
        wizard._go_next()
        wizard._go_next()

        with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn:
            wizard._run_refinement()
            mock_warn.assert_called_once()

        assert "精修失败" in wizard._lbl_status.text()
        assert "GSAS-II 未找到可用的仪器参数" in wizard._lbl_status.text()
        # 运行态已解除，可以重试
        assert wizard._btn_run.isEnabled() is True
        assert wizard._outcome is None
        wizard.close()

    def test_run_button_is_not_in_nav_row(self, qapp):
        """「开始精修」必须放在第 4 页内部，不能与「下一步」共用导航条位置。

        回归：旧布局导航条是 ``[上一步] … [下一步][开始精修][完成]``，第 4 页
        「下一步」隐藏后「开始精修」滑到同一位置；用户在第 3 页连点两下
        「下一步」，第三下正好落在滑过来的「开始精修」上，直接触发长时间
        精修 → 看起来就是「点下一步就卡死」。
        """
        wizard = RefinementWizard(
            _phases(), {k: str(v) for k, v in _CIF.items()}, _pattern(),
        )
        # 「开始精修」不在导航条里（导航条只有 back / next / finish）
        assert wizard._btn_run not in {
            wizard._btn_back, wizard._btn_next, wizard._btn_finish,
        }

        def in_current_page(widget) -> bool:
            page = wizard._stack.currentWidget()
            return page is not None and page.isAncestorOf(widget)

        # 第 1 页时它根本不属于当前页，连点「下一步」不可能点到它
        assert wizard._current_index() == 0
        assert in_current_page(wizard._btn_run) is False
        # 导航按钮本身也不在页面内（在对话框底部导航条里）
        assert in_current_page(wizard._btn_next) is False

        wizard._go_next()
        wizard._go_next()
        assert in_current_page(wizard._btn_run) is False

        wizard._go_next()
        assert in_current_page(wizard._btn_run) is True
        assert wizard._btn_run.isEnabled() is True
        wizard.close()

    def test_run_button_disabled_while_running(self, qapp):
        """运行期间「开始精修」禁用，防止重复提交。"""
        wizard = RefinementWizard(
            _phases(), {k: str(v) for k, v in _CIF.items()}, _pattern(),
            driver=lambda *a, **kw: _fake_outcome(),
        )
        wizard._go_next()
        wizard._go_next()
        wizard._go_next()
        assert wizard._btn_run.isEnabled() is True

        wizard._set_running(True)
        assert wizard._btn_run.isEnabled() is False
        assert wizard._btn_next.isEnabled() is False
        assert wizard._progress.isVisibleTo(wizard) is True

        wizard._set_running(False)
        assert wizard._btn_run.isEnabled() is True
        wizard.close()

    def test_plot_uses_theme_background(self, qapp):
        """结果图跟随主题：浅色下不是 pyqtgraph 默认黑底。"""
        from xinmatch.ui.theme import THEMES, apply_theme, current_theme

        apply_theme(qapp, "light")
        wizard = RefinementWizard(
            _phases(), {k: str(v) for k, v in _CIF.items()}, _pattern(),
        )
        bg = wizard._plot.backgroundBrush().color()
        expected = THEMES[current_theme()]["chart_bg"]
        assert bg.name().lower() == expected.lower()
        # 浅色主题下亮度必须够高（严禁黑色背景）
        assert bg.lightness() > 128
        wizard.close()
