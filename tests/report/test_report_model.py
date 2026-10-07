"""Tests for the report data model (T12.1)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from xinmatch.core.model import Entry, Peak, Phase
from xinmatch.core.report.report_model import (
    CandidateEntry,
    CandidateListSection,
    PeakListSection,
    QuantResultSection,
    Report,
    RFactorSection,
    SampleInfo,
    SelectedPhasesSection,
)


# ---------------------------------------------------------------------------
# Synthetic fixtures
# ---------------------------------------------------------------------------
def _make_peaks() -> list[Peak]:
    return [
        Peak(two_theta=20.0, intensity=120.0, fwhm=0.15, d=4.414, hkl=(1, 0, 0)),
        Peak(two_theta=28.5, intensity=80.0, fwhm=0.18, d=3.131, hkl=(1, 1, 1)),
        Peak(two_theta=45.2, intensity=50.0, fwhm=0.20, d=2.006),
    ]


def _make_phase(entry_id: str = "COD:9001234", formula: str = "Si O2",
               name: str = "Quartz") -> Phase:
    entry = Entry(
        entry_id=entry_id,
        formula=formula,
        d_spacings=np.array([3.131, 4.414, 2.006]),
        intensities=np.array([100.0, 80.0, 50.0]),
        mineral_name=name,
        space_group="P 31 2 1",
    )
    return Phase(entry=entry, scale_factor=1.05, weight_fraction=0.42)


def _make_report() -> Report:
    return Report(
        sample_info=SampleInfo(
            sample_name="Sample-A",
            operator="J. Doe",
            date="2026-10-07",
            instrument="Bruker D8",
            wavelength=1.5406,
            sample_preparation="Front-packed powder",
            comments="Test sample",
        ),
        peak_list=PeakListSection(peaks=_make_peaks()),
        candidate_list=CandidateListSection(
            candidates=[
                CandidateEntry(
                    entry_id="COD:9001234",
                    formula="Si O2",
                    name="Quartz",
                    fom=0.823,
                    p_values=[0.91, 0.85, 0.79],
                ),
                CandidateEntry(
                    entry_id="COD:9009999",
                    formula="Al2 O3",
                    name="Corundum",
                    fom=0.612,
                    p_values=[0.70, 0.68],
                ),
            ]
        ),
        selected_phases=SelectedPhasesSection(phases=[_make_phase()]),
        quant_result=QuantResultSection(
            weight_fractions={"Quartz": 0.42, "Corundum": 0.58}
        ),
        r_factors=RFactorSection(rwp=0.0543, rp=0.0410, rexp=0.0395, chi2=1.88),
        timestamp="2026-10-07T08:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# Section dataclasses
# ---------------------------------------------------------------------------
def test_sample_info_to_from_dict_round_trip():
    s = SampleInfo(
        sample_name="A", operator="B", date="2026-10-07",
        instrument="C", wavelength=1.5406,
        sample_preparation="D", comments="E",
    )
    s2 = SampleInfo.from_dict(s.to_dict())
    assert s == s2


def test_sample_info_defaults_empty():
    s = SampleInfo()
    assert s.sample_name == ""
    assert s.wavelength is None


def test_candidate_entry_to_from_dict_round_trip():
    c = CandidateEntry(
        entry_id="X", formula="Fe2 O3", name="Hematite",
        fom=0.55, p_values=[0.7, 0.8, 0.9],
    )
    c2 = CandidateEntry.from_dict(c.to_dict())
    assert c == c2
    assert c2.p_values == [0.7, 0.8, 0.9]


def test_candidate_entry_default_p_values_empty():
    c = CandidateEntry(entry_id="X", formula="Fe", fom=0.1)
    assert c.p_values == []


def test_peak_list_section_round_trip():
    pl = PeakListSection(peaks=_make_peaks())
    pl2 = PeakListSection.from_dict(pl.to_dict())
    assert len(pl2.peaks) == len(pl.peaks)
    assert pl2.peaks[0].two_theta == pl.peaks[0].two_theta
    assert pl2.peaks[0].hkl == (1, 0, 0)


def test_selected_phases_section_round_trip():
    sp = SelectedPhasesSection(phases=[_make_phase()])
    sp2 = SelectedPhasesSection.from_dict(sp.to_dict())
    assert len(sp2.phases) == 1
    p = sp2.phases[0]
    assert p.entry.entry_id == "COD:9001234"
    assert p.entry.formula == "Si O2"
    assert abs(p.scale_factor - 1.05) < 1e-12
    assert abs(p.weight_fraction - 0.42) < 1e-12


def test_quant_result_section_round_trip():
    q = QuantResultSection(weight_fractions={"A": 0.5, "B": 0.5})
    q2 = QuantResultSection.from_dict(q.to_dict())
    assert q2.weight_fractions == q.weight_fractions


def test_r_factor_section_round_trip_with_nones():
    r = RFactorSection(rwp=0.05, rp=None, rexp=0.04, chi2=None)
    r2 = RFactorSection.from_dict(r.to_dict())
    assert r2.rwp == 0.05
    assert r2.rp is None
    assert r2.rexp == 0.04
    assert r2.chi2 is None


# ---------------------------------------------------------------------------
# Report top-level container
# ---------------------------------------------------------------------------
def test_report_to_from_dict_round_trip():
    r = _make_report()
    d = r.to_dict()
    assert "sample_info" in d and "peak_list" in d
    assert "candidate_list" in d and "selected_phases" in d
    assert "quant_result" in d and "r_factors" in d
    assert d["timestamp"] == r.timestamp

    r2 = Report.from_dict(d)
    assert r2.timestamp == r.timestamp
    assert r2.sample_info.sample_name == "Sample-A"
    assert len(r2.peak_list.peaks) == 3
    assert len(r2.candidate_list.candidates) == 2
    assert len(r2.selected_phases.phases) == 1
    assert r2.quant_result.weight_fractions == {"Quartz": 0.42, "Corundum": 0.58}
    assert abs(r2.r_factors.rwp - 0.0543) < 1e-12


def test_report_to_json_from_json_round_trip(tmp_path: Path):
    r = _make_report()
    p = tmp_path / "report.json"
    r.to_json(p)
    assert p.exists() and p.stat().st_size > 0
    # Verify the JSON is parseable
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert raw["sample_info"]["sample_name"] == "Sample-A"
    # Round-trip via to_dict (== on Report compares Entry arrays, which
    # raises on multi-element arrays — compare the JSON-serialisable form
    # instead, which converts arrays to lists).
    r2 = Report.from_json(p)
    assert r2.to_dict() == r.to_dict()
    # Spot-check a few key fields
    assert r2.sample_info == r.sample_info
    assert r2.r_factors == r.r_factors
    assert r2.quant_result == r.quant_result
    np.testing.assert_allclose(
        r2.selected_phases.phases[0].entry.d_spacings,
        r.selected_phases.phases[0].entry.d_spacings,
    )


def test_report_now_adds_utc_timestamp():
    r = Report.now()
    assert r.timestamp is not None
    assert r.timestamp.endswith("+00:00")


def test_report_now_accepts_overrides():
    r = Report.now(
        sample_info=SampleInfo(sample_name="X"),
        r_factors=RFactorSection(rwp=0.1),
    )
    assert r.sample_info.sample_name == "X"
    assert r.r_factors.rwp == 0.1
    assert r.timestamp is not None


def test_report_empty_default():
    """A freshly-defaulted Report must still round-trip JSON cleanly."""
    r = Report()
    d = r.to_dict()
    assert d["peak_list"]["peaks"] == []
    assert d["quant_result"]["weight_fractions"] == {}
    r2 = Report.from_dict(d)
    assert r2 == r


def test_report_to_json_unicode_safe(tmp_path: Path):
    """Non-ASCII comments must be preserved (UTF-8 written without escapes)."""
    r = Report(
        sample_info=SampleInfo(comments="α β γ — 中文"),
        timestamp="2026-10-07T08:00:00+00:00",
    )
    p = tmp_path / "u.json"
    r.to_json(p)
    txt = p.read_text(encoding="utf-8")
    assert "中文" in txt  # not escaped to \uXXXX
    r2 = Report.from_json(p)
    assert r2.sample_info.comments == r.sample_info.comments


# ---------------------------------------------------------------------------
# Path acceptance
# ---------------------------------------------------------------------------
def test_report_to_json_accepts_str_and_path(tmp_path: Path):
    r = _make_report()
    p1 = tmp_path / "a.json"
    r.to_json(str(p1))
    assert p1.exists()
    p2 = tmp_path / "b.json"
    r.to_json(p2)
    assert p2.exists()
