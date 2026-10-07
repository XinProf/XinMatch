"""Tests for PANalytical/Philips readers (T2.3)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from xinmatch.core.io.panalytical import read_rd, read_udf, read_udi

from ._samples import synth_pattern, write_rd, write_udf, write_udi

RTOL = 1e-9


# ---------------------------------------------------------------------------
# .rd
# ---------------------------------------------------------------------------
def test_rd_round_trip(tmp_path: Path) -> None:
    """.rd synthetic sample parses back to the same 2θ/I."""
    pat = synth_pattern(n=40)
    p = tmp_path / "x.rd"
    write_rd(p, pat)
    out = read_rd(p)
    assert np.allclose(out.two_theta, pat.two_theta, rtol=RTOL, atol=RTOL)
    assert np.allclose(out.intensity, pat.intensity, rtol=RTOL, atol=RTOL)
    assert out.wavelength == pytest.approx(pat.wavelength)
    assert out.step == pytest.approx(pat.step)


def test_rd_missing_data_raises(tmp_path: Path) -> None:
    """.rd without a *DATA section raises ValueError."""
    p = tmp_path / "x.rd"
    p.write_text("*START 5.0\n*STEP 0.02\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_rd(p)


def test_rd_missing_start_raises(tmp_path: Path) -> None:
    """.rd without START/STEP raises ValueError."""
    p = tmp_path / "x.rd"
    p.write_text("*DATA\n1.0\n2.0\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_rd(p)


# ---------------------------------------------------------------------------
# .udf
# ---------------------------------------------------------------------------
def test_udf_round_trip(tmp_path: Path) -> None:
    """.udf synthetic sample parses back to the same 2θ/I."""
    pat = synth_pattern(n=30)
    p = tmp_path / "x.udf"
    write_udf(p, pat)
    out = read_udf(p)
    assert np.allclose(out.two_theta, pat.two_theta, rtol=RTOL, atol=RTOL)
    assert np.allclose(out.intensity, pat.intensity, rtol=RTOL, atol=RTOL)
    assert out.wavelength == pytest.approx(pat.wavelength)


def test_udf_missing_header_raises(tmp_path: Path) -> None:
    """.udf without Start/Step raises ValueError."""
    p = tmp_path / "x.udf"
    p.write_text("[Intensities]\n1.0\n2.0\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_udf(p)


# ---------------------------------------------------------------------------
# .udi
# ---------------------------------------------------------------------------
def test_udi_round_trip(tmp_path: Path) -> None:
    """.udi peak list parses back to the same values."""
    pat = synth_pattern(n=15)
    p = tmp_path / "x.udi"
    write_udi(p, pat)
    out = read_udi(p)
    assert np.allclose(out.two_theta, pat.two_theta, rtol=RTOL, atol=RTOL)
    assert np.allclose(out.intensity, pat.intensity, rtol=RTOL, atol=RTOL)
    assert out.metadata["kind"] == "peaklist"


def test_udi_no_peaks_raises(tmp_path: Path) -> None:
    """.udi without a [Peaks] section raises ValueError."""
    p = tmp_path / "x.udi"
    p.write_text("[Header]\nWavelength = 1.5406\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_udi(p)
