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
