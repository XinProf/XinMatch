"""Tests for pattern figure exporters (T12.3)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from xinmatch.core.model import Pattern, Peak
from xinmatch.core.report.figure_export import (
    export_multi_pattern_png,
    export_pattern_png,
    export_pattern_svg,
    export_peaks_png,
)


# ---------------------------------------------------------------------------
# Synthetic data
# ---------------------------------------------------------------------------
def _synth_pattern(n: int = 200) -> Pattern:
    """A simple synthetic pattern with two Gaussian peaks on a flat baseline."""
    tt = np.linspace(10.0, 80.0, n)
    base = np.full_like(tt, 5.0)
    peak1 = 100.0 * np.exp(-((tt - 28.5) ** 2) / (2 * 0.3**2))
    peak2 = 60.0 * np.exp(-((tt - 45.2) ** 2) / (2 * 0.4**2))
    return Pattern(
        two_theta=tt,
        intensity=base + peak1 + peak2,
        wavelength=1.5406,
        step=float(tt[1] - tt[0]),
    )


def _synth_peaks() -> list[Peak]:
    return [
        Peak(two_theta=28.5, intensity=100.0, fwhm=0.3, d=3.131,
             hkl=(1, 1, 1)),
        Peak(two_theta=45.2, intensity=60.0, fwhm=0.4, d=2.006,
             hkl=(2, 0, 0)),
    ]


# ---------------------------------------------------------------------------
# export_pattern_png
# ---------------------------------------------------------------------------
def test_export_pattern_png_writes_nonempty_file(tmp_path: Path):
    pytest.importorskip("matplotlib")
    pat = _synth_pattern()
    out = tmp_path / "pat.png"
    export_pattern_png(pat, out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_export_pattern_png_with_title(tmp_path: Path):
    pytest.importorskip("matplotlib")
    pat = _synth_pattern(n=50)
    out = tmp_path / "pat_title.png"
    export_pattern_png(pat, out, dpi=100, title="Test Pattern")
    assert out.exists() and out.stat().st_size > 0


def test_export_pattern_png_respects_dpi(tmp_path: Path):
    """Higher dpi should produce a larger file (very rough heuristic)."""
    pytest.importorskip("matplotlib")
    pat = _synth_pattern(n=100)
    low = tmp_path / "low.png"
    high = tmp_path / "high.png"
    export_pattern_png(pat, low, dpi=72)
    export_pattern_png(pat, high, dpi=300)
    # 300 dpi should produce a larger bitmap than 72 dpi — sanity check.
    assert high.stat().st_size > low.stat().st_size


# ---------------------------------------------------------------------------
# export_pattern_svg
# ---------------------------------------------------------------------------
def test_export_pattern_svg_writes_nonempty_file(tmp_path: Path):
    pytest.importorskip("matplotlib")
    pat = _synth_pattern(n=80)
    out = tmp_path / "pat.svg"
    export_pattern_svg(pat, out)
    assert out.exists()
    assert out.stat().st_size > 0
    # SVG files start with an XML declaration or an SVG tag
    head = out.read_text(encoding="utf-8", errors="ignore")[:200]
    assert "<svg" in head.lower() or "<?xml" in head.lower()


def test_export_pattern_svg_with_title(tmp_path: Path):
    pytest.importorskip("matplotlib")
    pat = _synth_pattern(n=50)
    out = tmp_path / "pat_title.svg"
    export_pattern_svg(pat, out, title="SVG Title")
    assert out.exists() and out.stat().st_size > 0


# ---------------------------------------------------------------------------
# export_multi_pattern_png
# ---------------------------------------------------------------------------
def test_export_multi_pattern_png_stacked(tmp_path: Path):
    pytest.importorskip("matplotlib")
    p1 = _synth_pattern(n=100)
    p2 = _synth_pattern(n=100)  # identical shape — fine for stacked test
    out = tmp_path / "multi.png"
    export_multi_pattern_png([p1, p2], out, labels=["A", "B"])
    assert out.exists() and out.stat().st_size > 0


def test_export_multi_pattern_png_overlay(tmp_path: Path):
    pytest.importorskip("matplotlib")
    p1 = _synth_pattern(n=80)
    p2 = _synth_pattern(n=80)
    out = tmp_path / "overlay.png"
    export_multi_pattern_png([p1, p2], out,
                            labels=None, offset_mode="overlay")
    assert out.exists() and out.stat().st_size > 0


def test_export_multi_pattern_png_three_patterns(tmp_path: Path):
    pytest.importorskip("matplotlib")
    pats = [_synth_pattern(n=60) for _ in range(3)]
    out = tmp_path / "triple.png"
    export_multi_pattern_png(pats, out)
    assert out.exists() and out.stat().st_size > 0


def test_export_multi_pattern_png_empty_raises(tmp_path: Path):
    pytest.importorskip("matplotlib")
    with pytest.raises(ValueError, match="at least one"):
        export_multi_pattern_png([], tmp_path / "empty.png")


def test_export_multi_pattern_png_label_count_mismatch_raises(tmp_path: Path):
    pytest.importorskip("matplotlib")
    pats = [_synth_pattern(n=20)]
    with pytest.raises(ValueError, match="labels length"):
        export_multi_pattern_png(pats, tmp_path / "x.png", labels=["A", "B"])


def test_export_multi_pattern_png_invalid_offset_mode_raises(tmp_path: Path):
    pytest.importorskip("matplotlib")
    pat = _synth_pattern(n=20)
    with pytest.raises(ValueError, match="unknown offset_mode"):
        export_multi_pattern_png([pat], tmp_path / "x.png",
                                 offset_mode="banana")


# ---------------------------------------------------------------------------
# export_peaks_png
# ---------------------------------------------------------------------------
def test_export_peaks_png_writes_nonempty_file(tmp_path: Path):
    pytest.importorskip("matplotlib")
    pat = _synth_pattern()
    out = tmp_path / "peaks.png"
    export_peaks_png(pat, _synth_peaks(), out)
    assert out.exists() and out.stat().st_size > 0


def test_export_peaks_png_with_no_peaks(tmp_path: Path):
    """Pattern alone (no peak markers) still produces a valid PNG."""
    pytest.importorskip("matplotlib")
    pat = _synth_pattern(n=100)
    out = tmp_path / "peaks_empty.png"
    export_peaks_png(pat, [], out, dpi=100)
    assert out.exists() and out.stat().st_size > 0


def test_export_peaks_png_high_dpi(tmp_path: Path):
    pytest.importorskip("matplotlib")
    pat = _synth_pattern(n=120)
    out = tmp_path / "peaks_hi.png"
    export_peaks_png(pat, _synth_peaks(), out, dpi=200)
    assert out.exists() and out.stat().st_size > 0
