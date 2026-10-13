"""Tests for tools/maud_to_prm.py (#17: measured instrument .prm).

Covers the MAUD ``.par`` -> GSAS-II ``.prm`` extraction without needing
GSAS-II or a real MAUD project: a small representative ``.par`` fragment
is built in-memory and both the extraction and the fixed-column output
layout (the layout GSASIIfiles.py parses) are verified.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.maud_to_prm import build_prm, extract_from_par

_MAUD_FRAGMENT = """\
data_global
_audit_creation_method 'Maud version 2.9998'
_riet_refine_texture_over 0.15
_pd_instr_geometry 'Bragg-Brentano'
_pd_instr_2theta_monochr_post 26.228
_diffrn_measurement_device 'XRD7000-SC-0_3'
_diffrn_radiation_monochromator Monochromator
_diffrn_radiation_type 'X-ray'
_diffrn_radiation_wavelength_id 'CuKa1'
_diffrn_radiation_wavelength 1.5405982 #min 0.1 #max 10.0
_diffrn_radiation_wavelength_wt 1.0 #min 0.0 #max 1.01
_diffrn_radiation_wavelength_id 'CuKa2'
_diffrn_radiation_wavelength 1.5445065 #min 0.1 #max 10.0
_diffrn_radiation_wavelength_wt 0.48983377 #min 0.0 #max 1.01
_diffrn_radiation_detector 'Scintillation'
_diffrn_inst_broadening 'Caglioti PV'
"""


@pytest.fixture
def par_file(tmp_path: Path) -> Path:
    p = tmp_path / "sample.par"
    p.write_text(_MAUD_FRAGMENT, encoding="utf-8")
    return p


def test_extract_values(par_file: Path) -> None:
    v = extract_from_par(par_file)
    assert v["lam1"] == pytest.approx(1.5405982, abs=1e-6)
    assert v["lam2"] == pytest.approx(1.5445065, abs=1e-6)
    assert v["ratio"] == pytest.approx(0.48983377, abs=1e-5)
    assert v["geometry"] == "Bragg-Brentano"
    assert v["mono_2theta"] == pytest.approx(26.228, abs=1e-3)
    assert v["detector"] == "Scintillation"
    assert v["device"] == "XRD7000-SC-0_3"


def test_build_prm_icons_fixed_columns(par_file: Path) -> None:
    """The ICONS line must parse back to the measured values under the
    fixed-column rules used by GSASIIfiles.py:
        lam1=s[0:10], lam2=s[10:20], zero=s[20:30]/100,
        Polariz.=s[40:50], I(L2)/I(L1)=s[55:65]."""
    prm = build_prm(extract_from_par(par_file))
    icons = next(line for line in prm.splitlines() if "ICONS" in line)
    body = icons[len("INS  1 ICONS"):]
    lam1 = float(body[0:10])
    lam2 = float(body[10:20])
    zero = float(body[20:30]) / 100.0
    pola = float(body[40:50])
    ratio = float(body[55:65])
    assert lam1 == pytest.approx(1.5405982, abs=1e-5)
    assert lam2 == pytest.approx(1.5445065, abs=1e-5)
    assert zero == pytest.approx(0.0, abs=1e-6)
    assert pola == pytest.approx(0.5, abs=1e-3)
    assert ratio == pytest.approx(0.48983, abs=1e-3)


def test_build_prm_layout(par_file: Path) -> None:
    prm = build_prm(extract_from_par(par_file))
    assert "INS   BANK      1" in prm
    assert "INS   HTYPE   PXCR" in prm
    assert "INS  1 IRAD     3" in prm
    assert "INS  1PRCF11" in prm
    assert "XRD7000-SC" in prm


def test_missing_par_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        extract_from_par(tmp_path / "nope.par")
