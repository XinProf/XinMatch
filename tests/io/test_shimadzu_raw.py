"""Tests for the Shimadzu XRD binary ``.raw`` reader.

Synthetic round-trip tests run everywhere; real-sample verification tests
run only when the Shimadzu data set is present on this machine (skipped
otherwise), asserting exact axis parameters and known standard peaks.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from xinmatch.core.io import detect_format, load_pattern
from xinmatch.core.io.detect import FMT_SHIMADZU_RAW
from xinmatch.core.io.shimadzu_raw import read_shimadzu_raw

from ._samples import synth_pattern, write_shimadzu_raw


# ---------------------------------------------------------------------------
# Synthetic round-trip
# ---------------------------------------------------------------------------
def test_round_trip(tmp_path: Path) -> None:
    pat = synth_pattern(n=60, start=20.0, step=0.05)
    p = tmp_path / "x.raw"
    write_shimadzu_raw(p, pat)
    out = read_shimadzu_raw(p)
    assert np.allclose(out.two_theta, pat.two_theta, rtol=1e-6, atol=1e-6)
    # binary int32 storage quantises intensities to integers
    assert np.array_equal(out.intensity, np.round(pat.intensity))
    assert out.step == pytest.approx(pat.step)
    assert out.metadata["format"] == "shimadzu_raw"
    assert out.metadata["vendor"] == "Shimadzu"
    assert "Cu" in out.metadata["target"]
    assert out.wavelength == pytest.approx(1.5406)


def test_detect_magic(tmp_path: Path) -> None:
    pat = synth_pattern(n=40)
    p = tmp_path / "x.raw"
    write_shimadzu_raw(p, pat)
    assert detect_format(p) == FMT_SHIMADZU_RAW


def test_load_pattern_dispatch(tmp_path: Path) -> None:
    pat = synth_pattern(n=40)
    p = tmp_path / "x.raw"
    write_shimadzu_raw(p, pat)
    out = load_pattern(p)
    assert out.step == pytest.approx(pat.step)
    assert len(out) == 40


# ---------------------------------------------------------------------------
# Defensive / error cases
# ---------------------------------------------------------------------------
def test_rejects_non_shimadzu_magic(tmp_path: Path) -> None:
    p = tmp_path / "x.raw"
    p.write_bytes(b"totally different binary content" + b"\x00" * 1200)
    with pytest.raises(ValueError, match="Not a Shimadzu"):
        read_shimadzu_raw(p)


def test_rejects_bad_range(tmp_path: Path) -> None:
    pat = synth_pattern(n=30)
    p = tmp_path / "x.raw"
    write_shimadzu_raw(p, pat)
    raw = bytearray(p.read_bytes())
    # corrupt start field -> end < start
    raw[300:304] = (9_999_999).to_bytes(4, "little", signed=True)
    p.write_bytes(bytes(raw))
    with pytest.raises(ValueError, match="2θ range"):
        read_shimadzu_raw(p)


def test_rejects_bad_step(tmp_path: Path) -> None:
    pat = synth_pattern(n=30)
    p = tmp_path / "x.raw"
    write_shimadzu_raw(p, pat)
    raw = bytearray(p.read_bytes())
    raw[308:312] = (0).to_bytes(4, "little", signed=True)
    p.write_bytes(bytes(raw))
    with pytest.raises(ValueError, match="step"):
        read_shimadzu_raw(p)


def test_truncated_file_reads_available_points(tmp_path: Path) -> None:
    """A file shorter than npts*4 returns the available points, flagged."""
    pat = synth_pattern(n=100)
    p = tmp_path / "x.raw"
    write_shimadzu_raw(p, pat)
    data = p.read_bytes()
    # truncate the tail by 40 points
    p.write_bytes(data[: len(data) - 40 * 4])
    out = read_shimadzu_raw(p)
    assert len(out) == 60
    assert out.metadata["truncated"] is True
    assert out.metadata["npts_declared"] == 100


def test_too_short_raises(tmp_path: Path) -> None:
    p = tmp_path / "x.raw"
    p.write_bytes(b"Shimadzu XRD" + b"\x00" * 100)
    with pytest.raises(ValueError, match="too short"):
        read_shimadzu_raw(p)


# ---------------------------------------------------------------------------
# Real Shimadzu samples (skipped when the data set is absent)
# ---------------------------------------------------------------------------
_XRDATA = Path(r"D:\Project\XRD\XRData\Shimadzu Data")
REAL_SAMPLES = [
    (_XRDATA / "CRYSIZE" / "CeO" / "CeO.RAW", 1440, 10.0313, 0.0625, 3213),
    (_XRDATA / "Austenite" / "007" / "007.RAW", 960, 39.9666, 0.0626, 9282),
    (_XRDATA / "Std" / "Si" / "Si.RAW", 5751, 25.0, 0.02, 5232),
]


@pytest.mark.parametrize(
    "path,npts,start,step,imax",
    REAL_SAMPLES,
)
def test_real_file_axis(path: Path, npts, start, step, imax) -> None:
    if not path.exists():
        pytest.skip("Shimadzu data set not present")
    out = read_shimadzu_raw(path)
    assert len(out) == npts
    assert out.metadata["scan_start_deg"] == pytest.approx(start, abs=1e-3)
    assert out.metadata["scan_end_deg"] > out.metadata["scan_start_deg"]
    assert out.step == pytest.approx(step, abs=1e-4)
    assert float(out.intensity.max()) == pytest.approx(imax)
    assert out.metadata["truncated"] is False
    # axis monotonic
    assert np.all(np.diff(out.two_theta) > 0)


def test_real_ceo2_peaks() -> None:
    """CeO2 standard peaks land at their theoretical positions."""
    path = _XRDATA / "CRYSIZE" / "CeO" / "CeO.RAW"
    if not path.exists():
        pytest.skip("Shimadzu data set not present")
    out = read_shimadzu_raw(path)
    # CeO2 (fluorite, a=5.411, Cu Kα1): 111/200/220/311 ≈ 28.5/33.1/47.5/56.3°
    expected = {28.55: 111, 33.08: 200, 47.49: 220, 56.35: 311}
    for tth, hkl in expected.items():
        idx = int(round((tth - out.two_theta[0]) / out.step))
        lo, hi = max(0, idx - 8), min(len(out), idx + 9)
        win = out.intensity[lo:hi]
        assert win.max() > 200, f"no intensity near CeO2 {hkl} at {tth:.2f}°"
        at = lo + int(np.argmax(win))
        assert abs(out.two_theta[at] - tth) < 0.4


def test_real_si_peaks() -> None:
    """Si standard peaks land at their theoretical positions."""
    path = _XRDATA / "Std" / "Si" / "Si.RAW"
    if not path.exists():
        pytest.skip("Shimadzu data set not present")
    out = read_shimadzu_raw(path)
    expected = {28.44: "111", 47.30: "220", 56.12: "311", 69.13: "400", 76.38: "331"}
    for tth, hkl in expected.items():
        idx = int(round((tth - out.two_theta[0]) / out.step))
        lo, hi = max(0, idx - 8), min(len(out), idx + 9)
        win = out.intensity[lo:hi]
        assert win.max() > 150, f"no intensity near Si {hkl} at {tth:.2f}°"
        at = lo + int(np.argmax(win))
        assert abs(out.two_theta[at] - tth) < 0.2


def test_real_007_ferrite_peak() -> None:
    """Austenite 007: the strongest peak is bcc-Fe (110) ≈ 44.7°."""
    path = _XRDATA / "Austenite" / "007" / "007.RAW"
    if not path.exists():
        pytest.skip("Shimadzu data set not present")
    out = read_shimadzu_raw(path)
    i_max = int(np.argmax(out.intensity))
    assert abs(out.two_theta[i_max] - 44.67) < 0.6
