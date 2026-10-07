"""Tests for ASCII exporters (T2.8) and the unified load_pattern (T2.9)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from xinmatch.core.io import load_pattern
from xinmatch.core.io.exporters import (
    export_ascii_2col,
    export_ascii_profile,
    export_peak_list,
)
from xinmatch.core.io.free import (
    read_ascii_profile_2col,
    read_ascii_profile_3col,
    read_endeavour,
)

from ._samples import (
    synth_pattern,
    write_ascii_3col,
    write_dbws,
    write_rd,
)

RTOL = 1e-9


# ---------------------------------------------------------------------------
# Exporters round-trip
# ---------------------------------------------------------------------------
def test_export_ascii_profile_round_trip(tmp_path: Path) -> None:
    """ASCII profile export → read_ascii_profile_3col yields identical data."""
    pat = synth_pattern(n=30)
    p = tmp_path / "out.dat"
    export_ascii_profile(pat, p)
    out = read_ascii_profile_3col(p)
    assert np.allclose(out.two_theta, pat.two_theta, rtol=RTOL, atol=RTOL)
    assert np.allclose(out.intensity, pat.intensity, rtol=RTOL, atol=RTOL)


def test_export_ascii_2col_round_trip(tmp_path: Path) -> None:
    """2-column export → read_ascii_profile_2col yields identical data."""
    pat = synth_pattern(n=25)
    p = tmp_path / "out.dat"
    export_ascii_2col(pat, p)
    out = read_ascii_profile_2col(p)
    assert np.allclose(out.two_theta, pat.two_theta, rtol=RTOL, atol=RTOL)
    assert np.allclose(out.intensity, pat.intensity, rtol=RTOL, atol=RTOL)


def test_export_peak_list_round_trip(tmp_path: Path) -> None:
    """Peak list export → read_endeavour yields identical data."""
    pat = synth_pattern(n=12)
    p = tmp_path / "out.dif"
    export_peak_list(pat.two_theta, pat.intensity, p)
    out = read_endeavour(p)
    assert np.allclose(out.two_theta, pat.two_theta, rtol=RTOL, atol=RTOL)
    assert np.allclose(out.intensity, pat.intensity, rtol=RTOL, atol=RTOL)


def test_export_peak_list_shape_mismatch(tmp_path: Path) -> None:
    """Mismatched arrays raise ValueError."""
    with pytest.raises(ValueError):
        export_peak_list(
            np.array([1.0, 2.0]), np.array([1.0]), tmp_path / "x.dif"
        )


def test_export_creates_parent_dir(tmp_path: Path) -> None:
    """Exporter creates missing parent directories."""
    pat = synth_pattern(n=5)
    p = tmp_path / "nested" / "deep" / "out.dat"
    export_ascii_2col(pat, p)
    assert p.exists()


# ---------------------------------------------------------------------------
# Unified entry point load_pattern
# ---------------------------------------------------------------------------
def test_load_pattern_dbws(tmp_path: Path) -> None:
    """load_pattern auto-detects DBWS and reads it."""
    pat = synth_pattern(n=20)
    p = tmp_path / "x.rfl"
    write_dbws(p, pat)
    out = load_pattern(p)
    assert np.allclose(out.two_theta, pat.two_theta, rtol=RTOL, atol=RTOL)
    assert np.allclose(out.intensity, pat.intensity, rtol=RTOL, atol=RTOL)


def test_load_pattern_ascii_3col(tmp_path: Path) -> None:
    """load_pattern auto-detects ASCII 3-col profile."""
    pat = synth_pattern(n=20)
    p = tmp_path / "x.dat"
    write_ascii_3col(p, pat)
    out = load_pattern(p)
    assert np.allclose(out.two_theta, pat.two_theta, rtol=RTOL, atol=RTOL)


def test_load_pattern_rd(tmp_path: Path) -> None:
    """load_pattern auto-detects .rd and reads it."""
    pat = synth_pattern(n=20)
    p = tmp_path / "x.rd"
    write_rd(p, pat)
    out = load_pattern(p)
    assert np.allclose(out.two_theta, pat.two_theta, rtol=RTOL, atol=RTOL)
    assert out.metadata["format"] == "rd"


def test_load_pattern_unknown_raises(tmp_path: Path) -> None:
    """load_pattern raises for an unrecognized file."""
    p = tmp_path / "x.xyz"
    p.write_bytes(b"not a diffraction file")
    with pytest.raises(ValueError):
        load_pattern(p)
