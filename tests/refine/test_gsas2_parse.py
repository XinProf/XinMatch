"""Tests for :mod:`xinmatch.core.refine.gsas2_parse` (T10.9).

Two layers:

1. **Synthetic** inline ``.lst`` / ``.prf`` / CIF strings — fast, hermetic,
   exercise every parser branch without needing GSAS-II.
2. **Real** GSAS-II output captured from an actual small Rietveld run
   (``tests/fixtures/gsas2_parse/``) — guarded by ``skipif`` so the suite
   still passes on machines without those fixtures.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from xinmatch.core.model.entry import CellParams
from xinmatch.core.model.pattern import Pattern
from xinmatch.core.refine.gsas2_parse import (
    Gsas2RefineOutcome,
    parse_cif,
    parse_gpx,
    parse_lst,
    parse_prf,
    parse_refinement,
)
from xinmatch.core.report.report_model import RFactorSection

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "gsas2_parse"
LST = FIXTURE_DIR / "capture.lst"
PRF = FIXTURE_DIR / "capture.prf"
ZNO_CIF = FIXTURE_DIR / "ZnO_new.cif"
CAF2_CIF = FIXTURE_DIR / "CaF2_new.cif"
GPX = FIXTURE_DIR / "capture.gpx"

# Values asserted against the real capture (see delivery notes).
REAL_RWP_PCT = 35.95
REAL_RP_PCT = 29.87
REAL_GOF = 6.19
REAL_ZNO_A = 3.249043
REAL_ZNO_C = 5.205279
REAL_ZNO_WT = 0.95814
REAL_CAF2_WT = 0.04186
REAL_PRF_ROWS = 376

_HAVE_REAL = all(p.exists() for p in (LST, PRF, ZNO_CIF, CAF2_CIF))


# ---------------------------------------------------------------------------
# Synthetic .lst
# ---------------------------------------------------------------------------
_SYN_LST = """\
********************************************************************************
   General Structure Analysis System-II Crystal Structure Refinement
********************************************************************************
 Least squares controls:
 Refinement type: analytic Hessian
 Maximum number of cycles: 3

 Sample Parameters:
 Goniometer omega = 0.00, chi = 0.00, phi = 0.00
 name  :         Scale         Shift  Transparency    SurfRoughA    SurfRoughB
 value :        3.8072        0.0000        0.0000        0.0000        0.0000

 Instrument Parameters:
 name  :     Azimuth I(L2)/I(L1)        Lam1        Lam2    Polariz.
 value :    0.000000    0.500000    1.540500    1.544300    0.700000

 Refinement results:
---------------------------------------------------------------------
 Number of function calls: 7 No. of observations: 1000 No. of parameters: 5 \
User rejected: 0 Sp. gp. extinct: 0
 wR =    8.50%, chi**2 =         1234, GOF =   1.11
---------------------------------------------------------------------
 Result for phase: Fake
=====================================================================
 New unit cell:
  names :           a           b           c       alpha        beta    \
   gamma      Volume
  values:    4.000000    4.000000    4.000000     90.0000     90.0000 \
   90.0000     64.000
 Density: 5.0000 g/cm**3

 Phase: Fake in histogram: PWDR fake.gss Bank 1
=====================================================================
 Final refinement RF, RF^2 = 5.00%, 25.00% on 10 reflections
 Phase fraction  :     1.0000, sig   0.010000 Weight fraction  :  1.000, sig \
0.00100

 Histogram: PWDR fake.gss Bank 1 histogram Id: 0
=====================================================================
 Final refinement wR = 8.50% on 1000 observations in this histogram
 Other residuals: R = 6.00%, R-bkg = 7.00%, wR-bkg = 8.50% wRmin = 5.20%
"""


def test_synthetic_lst_rfactors():
    s = parse_lst(_SYN_LST)
    assert s.rwp_pct == pytest.approx(8.50)
    assert s.rp_pct == pytest.approx(6.00)
    assert s.rexp_pct == pytest.approx(5.20)
    assert s.gof == pytest.approx(1.11)
    assert s.chi2_sum == pytest.approx(1234.0)
    assert s.n_obs == 1000
    assert s.n_params == 5
    assert s.scale == pytest.approx(3.8072)
    assert s.wavelength == pytest.approx(1.5405)


def test_synthetic_lst_phase_cell_and_weight():
    s = parse_lst(_SYN_LST)
    assert "Fake" in s.phases
    cell = s.phases["Fake"]["cell"]
    assert isinstance(cell, CellParams)
    assert cell.a == pytest.approx(4.0)
    assert cell.alpha == pytest.approx(90.0)
    assert s.phases["Fake"]["weight_fraction"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Synthetic .prf
# ---------------------------------------------------------------------------
_SYN_PRF = """\
# 2theta(deg)  Yobs  Ycalc  Residual(obs-calc)
      10.00000        100.000         90.000         10.000
      10.02000        200.000        195.000          5.000
      10.04000        150.000        160.000        -10.000
"""


def test_synthetic_prf_arrays_and_residual_consistency():
    x, yo, yc, res = parse_prf(_SYN_PRF)
    assert x.size == 3
    assert yo[0] == pytest.approx(100.0)
    assert yc[-1] == pytest.approx(160.0)
    # residual must equal obs - calc
    assert np.allclose(res, yo - yc)
    assert x[1] - x[0] == pytest.approx(0.02)


def test_synthetic_prf_skips_comments_and_bad_rows():
    text = "# header\n\nnot a number\n  1.0 2.0 1.5 0.5\n"
    x, yo, yc, res = parse_prf(text)
    assert x.size == 1
    assert yo[0] == pytest.approx(2.0)


def test_parse_prf_empty_raises():
    with pytest.raises(ValueError):
        parse_prf("# only comments\n")


# ---------------------------------------------------------------------------
# Synthetic CIF
# ---------------------------------------------------------------------------
_SYN_CIF = """\
data_capture
_pd_phase_name  Fake
_cell_length_a  4.0000
_cell_length_b  4.0000
_cell_length_c  4.0000
_cell_angle_alpha  90.0000
_cell_angle_beta  90.0000
_cell_angle_gamma  90.0000
_symmetry_space_group_name_H-M "F m -3 m"
_chemical_formula_sum  "X Y"
loop_
 _atom_site_label
 _atom_site_type_symbol
 _atom_site_fract_x
 _atom_site_fract_y
 _atom_site_fract_z
 _atom_site_occupancy
 _atom_site_adp_type
 _atom_site_U_iso_or_equiv
x      X   0.00000   0.00000   0.00000   1.0000     Uiso 0.010   1
y      Y   0.25000   0.25000   0.25000   0.5000     Uiso 0.020   3
"""


def test_synthetic_cif_cell_sg_and_atoms():
    cif = parse_cif(_SYN_CIF)
    assert cif["phase_name"] == "Fake"
    assert cif["space_group"] == "F m -3 m"
    assert cif["formula"] == "X Y"
    assert cif["cell"].a == pytest.approx(4.0)
    assert len(cif["atoms"]) == 2
    assert cif["atoms"][0]["element"] == "X"
    assert cif["atoms"][1]["occupancy"] == pytest.approx(0.5)
    assert cif["atoms"][1]["b_iso"] == pytest.approx(0.020)
    assert cif["atoms"][1]["fract_x"] == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# Aggregator + RFactorSection mapping
# ---------------------------------------------------------------------------
def test_parse_refinement_maps_rfactors_to_fractions():
    out = parse_refinement(_SYN_LST, _SYN_PRF)
    assert isinstance(out, Gsas2RefineOutcome)
    rf = out.r_factors
    assert isinstance(rf, RFactorSection)
    # percent -> fraction
    assert rf.rwp == pytest.approx(0.085)
    assert rf.rp == pytest.approx(0.06)
    assert rf.rexp == pytest.approx(0.052)
    # reduced chi^2 = GOF^2
    assert rf.chi2 == pytest.approx(1.11**2)
    assert out.gof == pytest.approx(1.11)


def test_parse_refinement_builds_patterns():
    out = parse_refinement(_SYN_LST, _SYN_PRF)
    assert isinstance(out.fitted_pattern, Pattern)
    assert isinstance(out.residual_pattern, Pattern)
    assert len(out.fitted_pattern) == 3
    assert np.allclose(
        out.residual_pattern.intensity,
        out.observed_pattern.intensity - out.fitted_pattern.intensity,
    )


def test_parse_refinement_backfills_phase_from_cif(tmp_path):
    cif = tmp_path / "Fake_new.cif"
    cif.write_text(_SYN_CIF, encoding="utf-8")
    out = parse_refinement(_SYN_LST, _SYN_PRF, cifs=[cif])
    assert len(out.refined_phases) == 1
    phase = out.refined_phases[0].phase
    assert phase.entry.cell.a == pytest.approx(4.0)
    assert phase.entry.space_group == "F m -3 m"
    assert phase.weight_fraction == pytest.approx(1.0)
    # atoms carried alongside the back-filled entry
    assert len(out.refined_phases[0].atoms) == 2


# ---------------------------------------------------------------------------
# .gpx best-effort
# ---------------------------------------------------------------------------
def test_parse_gpx_missing_file_returns_empty():
    assert parse_gpx("does/not/exist.gpx") == {}


@pytest.mark.skipif(not GPX.exists(), reason="real .gpx fixture missing")
def test_parse_gpx_real_is_dict():
    # When GSAS-II is importable this reads the pickle project; otherwise it
    # degrades to {} without raising.  Either outcome is acceptable.
    res = parse_gpx(GPX)
    assert isinstance(res, dict)


# ---------------------------------------------------------------------------
# Real GSAS-II capture
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _HAVE_REAL, reason="real GSAS-II fixtures missing")
class TestRealCapture:
    def test_rwp_matches_lst_reported_value(self):
        s = parse_lst(LST)
        assert s.rwp_pct == pytest.approx(REAL_RWP_PCT, abs=0.01)
        assert s.rp_pct == pytest.approx(REAL_RP_PCT, abs=0.01)
        assert s.gof == pytest.approx(REAL_GOF, abs=0.01)

    def test_rfactors_fraction_mapping(self):
        out = parse_refinement(LST, PRF)
        assert out.r_factors.rwp == pytest.approx(REAL_RWP_PCT / 100.0, abs=1e-6)

    def test_prf_row_count_matches_array_length(self):
        x, yo, yc, res = parse_prf(PRF)
        assert x.size == REAL_PRF_ROWS
        assert yo.size == REAL_PRF_ROWS
        assert yc.size == REAL_PRF_ROWS
        assert res.size == REAL_PRF_ROWS
        assert np.allclose(res, yo - yc, atol=1e-3)

    def test_refined_cell_backfilled(self):
        out = parse_refinement(LST, PRF, cifs=[ZNO_CIF, CAF2_CIF])
        zno = next(r for r in out.refined_phases if "ZnO" in r.phase.entry.entry_id)
        assert zno.phase.entry.cell.a == pytest.approx(REAL_ZNO_A, abs=1e-4)
        assert zno.phase.entry.cell.c == pytest.approx(REAL_ZNO_C, abs=1e-4)
        assert zno.phase.entry.cell.gamma == pytest.approx(120.0, abs=1e-3)

    def test_weight_fractions_from_lst(self):
        out = parse_refinement(LST, PRF, cifs=[ZNO_CIF, CAF2_CIF])
        wf = {r.phase.entry.entry_id: r.phase.weight_fraction for r in out.refined_phases}
        assert wf["ZnO_new"] == pytest.approx(REAL_ZNO_WT, abs=1e-4)
        assert wf["CaF2_new"] == pytest.approx(REAL_CAF2_WT, abs=1e-4)

    def test_atoms_parsed_from_refined_cif(self):
        out = parse_refinement(LST, PRF, cifs=[ZNO_CIF])
        atoms = out.refined_phases[0].atoms
        labels = {a["element"] for a in atoms}
        assert labels == {"Zn", "O"}
