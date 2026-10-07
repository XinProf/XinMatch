"""Tests for report renderers (T12.2): HTML / text / Markdown / PDF."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from xinmatch.core.model import Entry, Peak, Phase
from xinmatch.core.report.render import (
    render_html,
    render_markdown,
    render_pdf,
    render_text,
)
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
# Synthetic report fixture
# ---------------------------------------------------------------------------
def _synth_report() -> Report:
    peaks = [
        Peak(two_theta=20.0, intensity=120.0, fwhm=0.15, d=4.414,
             hkl=(1, 0, 0)),
        Peak(two_theta=28.5, intensity=80.0, fwhm=0.18, d=3.131,
             hkl=(1, 1, 1)),
    ]
    entry = Entry(
        entry_id="COD:9001234",
        formula="Si O2",
        d_spacings=np.array([3.131, 4.414]),
        intensities=np.array([100.0, 80.0]),
        mineral_name="Quartz",
        space_group="P 31 2 1",
    )
    phase = Phase(entry=entry, scale_factor=1.05, weight_fraction=0.42)
    return Report(
        sample_info=SampleInfo(
            sample_name="Sample-A",
            operator="J. Doe",
            date="2026-10-07",
            instrument="Bruker D8",
            wavelength=1.5406,
            sample_preparation="Front-packed",
            comments="Test sample",
        ),
        peak_list=PeakListSection(peaks=peaks),
        candidate_list=CandidateListSection(
            candidates=[
                CandidateEntry(entry_id="COD:9001234", formula="Si O2",
                              name="Quartz", fom=0.823, p_values=[0.9]),
                CandidateEntry(entry_id="COD:999", formula="Al2 O3",
                              name="Corundum", fom=0.5, p_values=[0.7]),
            ]
        ),
        selected_phases=SelectedPhasesSection(phases=[phase]),
        quant_result=QuantResultSection(
            weight_fractions={"Quartz": 0.42, "Corundum": 0.58}
        ),
        r_factors=RFactorSection(rwp=0.0543, rp=0.0410, rexp=0.0395,
                                 chi2=1.88),
        timestamp="2026-10-07T08:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
def test_render_html_non_empty():
    html = render_html(_synth_report())
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html
    # Inline CSS present
    assert "<style>" in html


def test_render_html_contains_key_fields():
    html = render_html(_synth_report())
    # Sample info
    assert "Sample-A" in html
    assert "Bruker D8" in html
    # Peaks
    assert "20.000" in html or "20.00" in html
    # Candidates
    assert "Si O2" in html
    assert "Quartz" in html
    # Phases (selected) — same formula but check the table is present
    assert "P 31 2 1" in html
    # Quant
    assert "0.4200" in html
    # R factors
    assert "0.0543" in html


def test_render_html_handles_empty_sections():
    """Empty report (no peaks/candidates/phases/quant/r-factors) renders."""
    r = Report()
    html = render_html(r)
    assert "(none)" in html  # placeholder for empty tables
    assert "(no R factors computed)" in html


def test_render_html_escapes_unsafe_chars():
    """Angle brackets in sample comments must be HTML-escaped."""
    r = Report(
        sample_info=SampleInfo(comments="<script>alert(1)</script>"),
    )
    html = render_html(r)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------
def test_render_text_non_empty():
    txt = render_text(_synth_report())
    assert "XinMatch — Phase Analysis Report" in txt
    assert "Sample Information" in txt
    assert "Peak List" in txt
    assert "Candidate List" in txt
    assert "Selected Phases" in txt
    assert "Quantitative Result" in txt
    assert "Profile Agreement Factors" in txt


def test_render_text_contains_key_fields():
    txt = render_text(_synth_report())
    assert "Sample-A" in txt
    assert "Si O2" in txt
    assert "0.0543" in txt
    # Peak positions present
    assert "20.000" in txt
    # Quant wt %
    assert "58.00" in txt


def test_render_text_handles_empty_sections():
    txt = render_text(Report())
    assert "(no peaks)" in txt
    assert "(no candidates)" in txt
    assert "(no phases selected)" in txt
    assert "(no quantitative result)" in txt
    assert "(no R factors computed)" in txt


def test_render_text_handles_partial_r_factors():
    """Mix of present / None R-factors renders cleanly."""
    r = Report(r_factors=RFactorSection(rwp=0.07, rp=None, rexp=0.04,
                                        chi2=None))
    txt = render_text(r)
    assert "Rwp" in txt and "0.0700" in txt
    assert "Rexp" in txt and "0.0400" in txt


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------
def test_render_markdown_non_empty():
    md = render_markdown(_synth_report())
    assert "# XinMatch Phase Analysis Report" in md
    assert "## Sample Information" in md
    assert "## Peak List" in md
    assert "## Candidate List" in md
    assert "## Selected Phases" in md
    assert "## Quantitative Result" in md
    assert "## R Factors" in md


def test_render_markdown_contains_key_fields():
    md = render_markdown(_synth_report())
    assert "Sample-A" in md
    assert "Si O2" in md
    assert "0.0543" in md
    assert "58.00" in md
    # Tables present
    assert "|---|" in md


def test_render_markdown_handles_empty_sections():
    md = render_markdown(Report())
    assert "_(no peaks)_" in md
    assert "_(no candidates)_" in md
    assert "_(no phases selected)_" in md
    assert "_(no quantitative result)_" in md
    assert "_(no R factors computed)_" in md


# ---------------------------------------------------------------------------
# PDF — optional weasyprint
# ---------------------------------------------------------------------------
def test_render_pdf_skipped_when_weasyprint_missing(tmp_path: Path):
    """If weasyprint is unavailable, the test is skipped (not failed)."""
    pytest.importorskip("weasyprint")
    out = tmp_path / "report.pdf"
    render_pdf(_synth_report(), out)
    assert out.exists() and out.stat().st_size > 0


def test_render_pdf_raises_import_error_without_weasyprint(
    monkeypatch, tmp_path: Path
):
    """When weasyprint is missing, render_pdf raises ImportError with hint."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "weasyprint" or name.startswith("weasyprint."):
            raise ImportError("simulated missing module")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    # Also remove any cached weasyprint module so the import path triggers
    import sys

    sys.modules.pop("weasyprint", None)

    with pytest.raises(ImportError, match="weasyprint"):
        render_pdf(_synth_report(), tmp_path / "x.pdf")
