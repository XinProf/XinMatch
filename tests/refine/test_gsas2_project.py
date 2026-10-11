"""Tests for the GSAS-II project constructor (T10.8).

Covers:

* CIF-missing validation (ValueError naming the offending phase).
* No-GSAS-II environment (monkeypatched detection -> Gsas2NotAvailableError,
  driver + manifest still written, no bare crash).
* Option combinations (two_theta_range / refine_background / max_iter /
  wavelength) propagated into the input manifest.
* The real GSAS-II refinement path, guarded by ``pytest.mark.skipif`` on
  :data:`GSAS2_AVAILABLE` (file-based runtime detection).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from xinmatch.core.model.entry import CellParams, Entry
from xinmatch.core.model.pattern import Pattern
from xinmatch.core.model.phase import Phase
from xinmatch.core.refine import gsas2_project as gp
from xinmatch.core.refine.gsas2_adapter import RefineOptions, load_gsas_gss

_FIX = Path(__file__).resolve().parent.parent / "fixtures" / "gsas2_project"
_GSS = _FIX / "cpd-1c.gss"
_CIF = {
    "Al2O3": _FIX / "Al2O3.cif",
    "ZnO": _FIX / "ZnO.cif",
    "CaF2": _FIX / "CaF2.cif",
}


def _entry(entry_id: str, formula: str, cell: CellParams) -> Entry:
    return Entry(
        entry_id=entry_id,
        formula=formula,
        d_spacings=np.array([2.5, 2.0]),
        intensities=np.array([100.0, 40.0]),
        mineral_name=entry_id,
        cell=cell,
    )


def _phases() -> list[Phase]:
    return [
        Phase(entry=_entry("Al2O3", "Al2 O3",
                           CellParams(4.7592, 4.7592, 12.9918, 90, 90, 120))),
        Phase(entry=_entry("ZnO", "Zn O", CellParams(3.2494, 3.2494, 5.2054))),
        Phase(entry=_entry("CaF2", "Ca F2", CellParams(5.4632, 5.4632, 5.4632))),
    ]


def _pattern() -> Pattern:
    return load_gsas_gss(_GSS)


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------
def test_empty_phases_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least one phase"):
        gp.build_gsas2_project(_pattern(), [], {}, work_dir=tmp_path, run=False)


def test_missing_cif_mapping_names_phase(tmp_path: Path) -> None:
    """A phase with no cif_paths entry -> ValueError naming that phase."""
    phases = _phases()
    # Only Al2O3 is mapped; ZnO / CaF2 are missing.
    partial = {"Al2O3": str(_CIF["Al2O3"])}
    with pytest.raises(ValueError) as exc:
        gp.build_gsas2_project(_pattern(), phases, partial,
                                work_dir=tmp_path, run=False)
    msg = str(exc.value)
    assert "no CIF path" in msg
    # The offending phase (first unmapped = ZnO) is named.
    assert "ZnO" in msg


def test_missing_cif_file_names_phase_and_path(tmp_path: Path) -> None:
    """A mapped CIF that does not exist -> ValueError naming phase + path."""
    phases = _phases()
    bad = {
        "Al2O3": r"D:\no\such\corundum.cif",
        "ZnO": str(_CIF["ZnO"]),
        "CaF2": str(_CIF["CaF2"]),
    }
    with pytest.raises(ValueError) as exc:
        gp.build_gsas2_project(_pattern(), phases, bad,
                                work_dir=tmp_path, run=False)
    msg = str(exc.value)
    assert "CIF file not found" in msg
    assert "Al2O3" in msg
    assert r"D:\no\such\corundum.cif" in msg


# ---------------------------------------------------------------------------
# No GSAS-II environment
# ---------------------------------------------------------------------------
def test_no_gsas2_raises_but_writes_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With detection forced unavailable, run=True raises
    Gsas2NotAvailableError, yet driver + manifest are written and nothing
    crashes bare.
    """
    unavailable = gp.Gsas2Runtime(
        python=Path(r"C:\ghost\python.exe"),
        source_dir=Path(r"C:\ghost\GSAS-II"),
        available=False,
    )
    monkeypatch.setattr(gp, "locate_gsas2", lambda: unavailable)

    with pytest.raises(gp.Gsas2NotAvailableError):
        gp.build_gsas2_project(
            _pattern(), _phases(), {k: str(v) for k, v in _CIF.items()},
            RefineOptions(max_iter=5), work_dir=tmp_path, project_name="ghost",
            run=True,
        )

    # Artifacts must still be present (the "independent driver script +
    # input manifest" fallback).
    driver = tmp_path / "ghost_driver.py"
    manifest = tmp_path / "ghost_manifest.json"
    data = tmp_path / "ghost.gss"
    assert driver.is_file(), "driver script not written"
    assert manifest.is_file(), "input manifest not written"
    assert data.is_file(), "powder data file not written"

    man = json.loads(manifest.read_text(encoding="utf-8"))
    assert man["output_json"] == str(tmp_path / "ghost_result.json")
    assert [p["name"] for p in man["phases"]] == ["Al2O3", "ZnO", "CaF2"]


# ---------------------------------------------------------------------------
# Option combinations propagated into the manifest (no run)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "options, expect",
    [
        (RefineOptions(max_iter=7), {"max_iter": 7, "refine_background": True}),
        (RefineOptions(refine_background=False), {"refine_background": False}),
        (RefineOptions(refine_atoms=True), {"refine_atoms": True}),
        (RefineOptions(wavelength=0.71073), {"wavelength": 0.71073}),
        (RefineOptions(two_theta_range=(15.0, 120.0)),
         {"two_theta_range": [15.0, 120.0]}),
        (RefineOptions(refine_po=True), {"refine_po": True}),
        (RefineOptions(refine_size_strain=True),
         {"refine_size_strain": True}),
    ],
)
def test_options_propagate_to_manifest(
    tmp_path: Path, options: RefineOptions, expect: dict
) -> None:
    proj = gp.build_gsas2_project(
        _pattern(), _phases(), {k: str(v) for k, v in _CIF.items()},
        options, work_dir=tmp_path, project_name="opt", run=False,
    )
    man = json.loads(proj.manifest_path.read_text(encoding="utf-8"))
    for key, val in expect.items():
        assert man["options"][key] == val, key
    # Driver + data + instrument files always written.
    assert proj.driver_path.is_file()
    assert proj.gpx_path.with_suffix(".gss").is_file()


def test_pattern_export_when_no_gss_source(tmp_path: Path) -> None:
    """A pattern not originating from a .gss is exported to a .gss."""
    pat = Pattern(
        two_theta=np.linspace(10.0, 80.0, 350),
        intensity=100.0 + 50.0 * np.exp(-((np.linspace(10, 80, 350) - 30.0) ** 2) / 5.0),
        wavelength=1.5406,
        step=0.2,
    )
    proj = gp.build_gsas2_project(
        pat, _phases(), {k: str(v) for k, v in _CIF.items()},
        work_dir=tmp_path, project_name="synth", run=False,
    )
    data_file = proj.gpx_path.with_suffix(".gss")
    text = data_file.read_text()
    assert "BANK" in text and "CONST" in text


# ---------------------------------------------------------------------------
# Real GSAS-II refinement (guarded)
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.skipif(
    not gp.GSAS2_AVAILABLE,
    reason="GSAS-II runtime not found on this machine",
)


def test_real_refinement_cpd1c(tmp_path: Path) -> None:
    """Drive one Rietveld round on the IUCr CPD-1c benchmark (Al2O3/ZnO/CaF2).

    Asserts a finite Rwp and that .gpx / .lst products exist.
    """
    proj = gp.build_gsas2_project(
        _pattern(), _phases(), {k: str(v) for k, v in _CIF.items()},
        RefineOptions(max_iter=15, two_theta_range=(10.0, 140.0)),
        work_dir=tmp_path, project_name="cpd1c", run=True,
    )
    assert proj.rwp is not None and np.isfinite(proj.rwp)
    assert 0.0 < proj.rwp < 100.0
    assert proj.rp is not None and np.isfinite(proj.rp)
    assert proj.gpx_path.is_file(), ".gpx not produced"
    assert proj.lst_path is not None and proj.lst_path.is_file(), ".lst not produced"


def test_real_refinement_with_size_strain(tmp_path: Path) -> None:
    """Real refinement with isotropic size/strain broadening turned on.

    Guards against driver crashes and confirms .lst/.prf products are still
    produced.  Note: March-Dollase PO is not enabled here because the [0,0,1]
    texture axis is physically specific to layered/wurtzite structures and
    drives the MD integrand NaN on the cubic/trigonal benchmark phases; that
    is a pre-existing PO-stage limitation, not a size/strain issue.
    """
    proj = gp.build_gsas2_project(
        _pattern(), _phases(), {k: str(v) for k, v in _CIF.items()},
        RefineOptions(
            max_iter=25,
            two_theta_range=(10.0, 140.0),
            refine_size_strain=True,
        ),
        work_dir=tmp_path, project_name="cpd1c_sz", run=True,
    )
    assert proj.rwp is not None and np.isfinite(proj.rwp)
    assert 0.0 < proj.rwp < 100.0
    assert proj.gpx_path.is_file(), ".gpx not produced"
    assert proj.lst_path is not None and proj.lst_path.is_file(), ".lst not produced"
    assert proj.prf_path is not None and proj.prf_path.is_file(), ".prf not produced"
