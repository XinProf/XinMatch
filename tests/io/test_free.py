"""Tests for the free-format readers (T2.2)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from xinmatch.core.io.free import (
    read_ascii_profile_2col,
    read_ascii_profile_2col_header,
    read_ascii_profile_3col,
    read_dbws,
    read_endeavour,
)

from ._samples import (
    synth_pattern,
    write_ascii_2col,
    write_ascii_2col_hdr,
    write_ascii_3col,
    write_dbws,
    write_endeavour,
)

RTOL = 1e-9


# ---------------------------------------------------------------------------
# DBWS
# ---------------------------------------------------------------------------
def test_dbws_round_trip(tmp_path: Path) -> None:
    """DBWS write→read preserves 2θ and intensity (< 1e-9 rel error)."""
    pat = synth_pattern(n=60)
    p = tmp_path / "x.rfl"
    write_dbws(p, pat)
    out = read_dbws(p)
    assert np.allclose(out.two_theta, pat.two_theta, rtol=RTOL, atol=RTOL)
    assert np.allclose(out.intensity, pat.intensity, rtol=RTOL, atol=RTOL)
    assert out.step == pytest.approx(pat.step)


def test_dbws_title_ignored(tmp_path: Path) -> None:
    """The optional 4th title token on the first line is ignored."""
    p = tmp_path / "x.rfl"
    p.write_text(
        "5.000   0.020  10.000    my_title\n"
        "100.0  100.0  100.0  100.0  100.0  100.0  100.0  100.0\n"
        "100.0  100.0  100.0  100.0  100.0  100.0  100.0  100.0\n"
        "100.0  100.0  100.0  100.0\n",
        encoding="utf-8",
    )
    out = read_dbws(p)
    assert out.two_theta[0] == pytest.approx(5.0)
    assert out.step == pytest.approx(0.02)
    assert len(out) == 20


# ---------------------------------------------------------------------------
# ASCII 3-column
# ---------------------------------------------------------------------------
def test_ascii_3col_round_trip(tmp_path: Path) -> None:
    """ASCII profile (start, step, end) round-trips."""
    pat = synth_pattern(n=40)
    p = tmp_path / "x.dat"
    write_ascii_3col(p, pat)
    out = read_ascii_profile_3col(p)
    assert np.allclose(out.two_theta, pat.two_theta, rtol=RTOL, atol=RTOL)
    assert np.allclose(out.intensity, pat.intensity, rtol=RTOL, atol=RTOL)


def test_ascii_3col_end_in_metadata(tmp_path: Path) -> None:
    """The end 2θ is stored in metadata."""
    pat = synth_pattern(n=10)
    p = tmp_path / "x.dat"
    write_ascii_3col(p, pat)
    out = read_ascii_profile_3col(p)
    assert out.metadata["end_two_theta"] == pytest.approx(float(pat.two_theta[-1]))


# ---------------------------------------------------------------------------
# ASCII 2-column header (start, step)
# ---------------------------------------------------------------------------
def test_ascii_2col_hdr_round_trip(tmp_path: Path) -> None:
    """ASCII profile (start, step) round-trips."""
    pat = synth_pattern(n=30)
    p = tmp_path / "x.dat"
    write_ascii_2col_hdr(p, pat)
    out = read_ascii_profile_2col_header(p)
    assert np.allclose(out.two_theta, pat.two_theta, rtol=RTOL, atol=RTOL)
    assert np.allclose(out.intensity, pat.intensity, rtol=RTOL, atol=RTOL)


# ---------------------------------------------------------------------------
# ASCII 2-column (2theta intensity)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("sep", [" ", ",", "\t"])
def test_ascii_2col_separators(tmp_path: Path, sep: str) -> None:
    """2-column reader handles space, comma, and tab separators."""
    pat = synth_pattern(n=25)
    p = tmp_path / "x.dat"
    write_ascii_2col(p, pat, sep=sep)
    out = read_ascii_profile_2col(p)
    assert np.allclose(out.two_theta, pat.two_theta, rtol=RTOL, atol=RTOL)
    assert np.allclose(out.intensity, pat.intensity, rtol=RTOL, atol=RTOL)


def test_ascii_2col_comments_ignored(tmp_path: Path) -> None:
    """Comment lines are skipped."""
    pat = synth_pattern(n=10)
    p = tmp_path / "x.dat"
    write_ascii_2col(p, pat, with_comments=True)
    out = read_ascii_profile_2col(p)
    assert len(out) == len(pat)
    assert np.allclose(out.intensity, pat.intensity, rtol=RTOL, atol=RTOL)


def test_ascii_2col_dspacing_flag(tmp_path: Path) -> None:
    """Monotonically decreasing x is flagged as d-spacing."""
    p = tmp_path / "x.dat"
    p.write_text(
        "5.0 100.0\n4.0 90.0\n3.0 80.0\n2.0 70.0\n", encoding="utf-8"
    )
    out = read_ascii_profile_2col(p)
    assert out.metadata["x_unit"] == "d"


# ---------------------------------------------------------------------------
# ENDEAVOUR
# ---------------------------------------------------------------------------
def test_endeavour_round_trip(tmp_path: Path) -> None:
    """ENDEAVOUR peak list round-trips."""
    pat = synth_pattern(n=15)
    p = tmp_path / "x.dif"
    write_endeavour(p, pat)
    out = read_endeavour(p)
    assert np.allclose(out.two_theta, pat.two_theta, rtol=RTOL, atol=RTOL)
    assert np.allclose(out.intensity, pat.intensity, rtol=RTOL, atol=RTOL)
    assert out.metadata["kind"] == "peaklist"


def test_endeavour_no_data_raises(tmp_path: Path) -> None:
    """An empty ENDEAVOUR file raises ValueError."""
    p = tmp_path / "empty.dif"
    p.write_text("# nothing here\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_endeavour(p)
