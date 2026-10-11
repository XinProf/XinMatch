"""Tests for the GSAS-II adapter module (T10.6b)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from xinmatch.core.model.entry import CellParams, Entry
from xinmatch.core.model.pattern import Pattern
from xinmatch.core.model.phase import Phase
from xinmatch.core.refine.gsas2_adapter import (
    GSAS2_AVAILABLE,
    GSAS2RietveldAdapter,
    LocalRietveldAdapter,
    RefineOptions,
    RefineResult,
    RietveldAdapter,
    get_rietveld_adapter,
    load_gsas_gss,
)

_GSS_DIR = Path(r"D:\Project\XRD\XRData\IUCr\gsas")
_CORUNDUM_GSS = _GSS_DIR / "corundum.gss"

# Approximate corundum (α-Al2O3) cell: trigonal R-3c, a=4.7558, c=12.991.
# A handful of the strongest reflections (2θ, I_rel) from the PDF.
_CORUNDUM_STRONG_PEAKS_2T = (
    25.572, 35.150, 37.776, 43.362, 52.544, 57.501, 61.298, 66.522, 68.210,
)
_CORUNDUM_CELL = CellParams(a=4.7558, b=4.7558, c=12.991,
                            alpha=90.0, beta=90.0, gamma=120.0)


def _make_corundum_entry() -> Entry:
    """Build a minimal corundum entry with the strongest d/I pairs."""
    wavelength = 1.5406
    d_spacings = np.array([
        wavelength / (2.0 * np.sin(np.radians(t / 2.0)))
        for t in _CORUNDUM_STRONG_PEAKS_2T
    ])
    intensities = np.array([1000.0, 999.0, 500.0, 350.0, 250.0, 800.0, 300.0, 220.0, 180.0])
    return Entry(
        entry_id="corundum-test",
        formula="Al2 O3",
        d_spacings=d_spacings,
        intensities=intensities,
        mineral_name="Corundum",
        cell=_CORUNDUM_CELL,
        space_group="R -3 c",
    )


# ---------------------------------------------------------------------------
# Import-time safety
# ---------------------------------------------------------------------------
def test_module_imports_without_gsas2():
    """Importing the module never fails when GSAS-II is absent."""
    import xinmatch.core.refine.gsas2_adapter as mod
    assert hasattr(mod, "GSAS2_AVAILABLE")
    # In CI environment GSAS-II is typically absent.
    assert isinstance(mod.GSAS2_AVAILABLE, bool)


def test_gsas2_adapter_unavailable_when_not_installed():
    """If GSAS-II is not installed, GSAS2RietveldAdapter raises on init."""
    if GSAS2_AVAILABLE:
        pytest.skip("GSAS-II is installed — skipping the unavailable-path test")
    with pytest.raises(ImportError):
        GSAS2RietveldAdapter()


# ---------------------------------------------------------------------------
# Protocol / factory
# ---------------------------------------------------------------------------
def test_local_adapter_is_rietveld_adapter():
    adapter = LocalRietveldAdapter()
    assert isinstance(adapter, RietveldAdapter)
    assert adapter.backend == "local"


def test_factory_returns_local_when_gsas2_unavailable():
    if GSAS2_AVAILABLE:
        pytest.skip("GSAS-II is installed — skipping the fallback test")
    adapter = get_rietveld_adapter(prefer="gsas2")
    assert isinstance(adapter, LocalRietveldAdapter)
    assert adapter.backend == "local"


def test_factory_default_returns_local():
    adapter = get_rietveld_adapter()
    assert isinstance(adapter, LocalRietveldAdapter)


# ---------------------------------------------------------------------------
# .gss loader
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _CORUNDUM_GSS.exists(),
                    reason=f"missing test data: {_CORUNDUM_GSS}")
def test_load_gsas_gss_corundum_shape_and_grid():
    pattern = load_gsas_gss(_CORUNDUM_GSS)
    assert isinstance(pattern, Pattern)
    assert len(pattern) == 7251
    assert pattern.step == pytest.approx(0.02, abs=1e-6)
    assert pattern.two_theta[0] == pytest.approx(5.0, abs=1e-6)
    # 5° + 7251 * 0.02° → up to ~150.02° on the last point.
    assert pattern.two_theta[-1] == pytest.approx(5.0 + 7250 * 0.02, abs=1e-6)
    assert pattern.wavelength == pytest.approx(1.5406, abs=1e-4)
    assert "gsas_esd_multipliers" in pattern.metadata
    assert len(pattern.metadata["gsas_esd_multipliers"]) == 7251


@pytest.mark.skipif(not _CORUNDUM_GSS.exists(),
                    reason=f"missing test data: {_CORUNDUM_GSS}")
def test_load_gsas_gss_intensities_are_positive_integers():
    pattern = load_gsas_gss(_CORUNDUM_GSS)
    # Raw GSAS counts are non-negative integers.
    assert (pattern.intensity >= 0).all()
    # The strongest corundum peak (104) at ~35° should be visible above
    # the noise floor.
    mask = (pattern.two_theta >= 34.5) & (pattern.two_theta <= 36.0)
    assert mask.sum() > 0
    assert pattern.intensity[mask].max() > pattern.intensity.mean()


def test_load_gsas_gss_rejects_non_const(tmp_path):
    p = tmp_path / "fake.gss"
    p.write_text(
        "SampleIdent fake\n"
        "BANK 1 10 1 XYDATA 1.0 2.0 0.0 0.0\n"
        "1 1\n",
        encoding="utf-8",
    )
    with pytest.raises(NotImplementedError):
        load_gsas_gss(p)


def test_load_gsas_gss_missing_bank_raises(tmp_path):
    p = tmp_path / "noheader.gss"
    p.write_text("Just a title, no BANK line here\n1 1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_gsas_gss(p)


# ---------------------------------------------------------------------------
# Local Rietveld fallback path on real corundum data
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _CORUNDUM_GSS.exists(),
                    reason=f"missing test data: {_CORUNDUM_GSS}")
def test_local_adapter_runs_rietveld_on_corundum_gss():
    """The fallback path loads corundum.gss, runs the local refiner, and
    returns a :class:`RefineResult` with finite R-factors.
    """
    pattern = load_gsas_gss(_CORUNDUM_GSS)
    # Restrict the fitted range to the typical corundum Bragg region;
    # the local engine cannot handle 7000+ points quickly.
    sub = pattern[(20.0, 90.0)]
    assert len(sub) > 100
    phase = Phase(entry=_make_corundum_entry())
    options = RefineOptions(
        max_iter=5,
        refine_atoms=False,
        refine_background=False,
        wavelength=pattern.wavelength,
    )
    adapter = get_rietveld_adapter(prefer="gsas2")  # falls back to local
    assert isinstance(adapter, LocalRietveldAdapter)
    result = adapter.refine(sub, [phase], options)
    assert isinstance(result, RefineResult)
    assert result.backend == "local"
    assert np.isfinite(result.rwp)
    assert np.isfinite(result.rp)
    assert np.isfinite(result.chi2)
    assert len(result.fitted_pattern) == len(sub)
    assert len(result.refined_phases) == 1
    assert result.refined_phases[0].entry.entry_id == "corundum-test"


@pytest.mark.skipif(not _CORUNDUM_GSS.exists(),
                    reason=f"missing test data: {_CORUNDUM_GSS}")
def test_local_adapter_empty_phases_raises():
    pattern = load_gsas_gss(_CORUNDUM_GSS)
    adapter = LocalRietveldAdapter()
    with pytest.raises(ValueError):
        adapter.refine(pattern, [], RefineOptions())


# ---------------------------------------------------------------------------
# Real GSAS-II path (only runs when GSAS-II is installed)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not GSAS2_AVAILABLE,
                    reason="GSAS-II not installed")
def test_gsas2_adapter_can_be_constructed_when_installed():  # pragma: no cover
    adapter = GSAS2RietveldAdapter()
    assert adapter.backend == "gsas2"
    assert isinstance(adapter, RietveldAdapter)


# ---------------------------------------------------------------------------
# RefineOptions fields (new in T13.x: refine_size_strain)
# ---------------------------------------------------------------------------
def test_refine_options_size_strain_default_false():
    opts = RefineOptions()
    assert opts.refine_size_strain is False


def test_refine_options_size_strain_settable():
    opts = RefineOptions(refine_size_strain=True)
    assert opts.refine_size_strain is True


def test_refine_options_po_default_false():
    opts = RefineOptions()
    assert opts.refine_po is False
