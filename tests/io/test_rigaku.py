"""Tests for RAW2 and Rigaku RINT-2000 binary readers.

Synthetic round-trip tests run everywhere; real-sample verification tests
run only when the IUCr / csuHJW data sets are present on this machine
(skipped otherwise), asserting exact axis parameters and known peaks.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest

from xinmatch.core.io import detect_format, load_pattern
from xinmatch.core.io.detect import FMT_RAW2, FMT_RIGAKU_RAW
from xinmatch.core.io.rigaku import read_raw2, read_rigaku_raw

from ._samples import synth_pattern, write_raw2, write_rigaku_raw


# ---------------------------------------------------------------------------
# Synthetic round-trips
# ---------------------------------------------------------------------------
def test_raw2_round_trip(tmp_path: Path) -> None:
    pat = synth_pattern(n=60, start=5.0, step=0.02)
    p = tmp_path / "x.raw"
    write_raw2(p, pat)
    out = read_raw2(p)
    assert np.allclose(out.two_theta, pat.two_theta, rtol=1e-6, atol=1e-6)
    assert np.allclose(out.intensity, pat.intensity, rtol=1e-6, atol=1e-6)
    assert out.step == pytest.approx(pat.step, abs=1e-6)
    assert out.metadata["format"] == "raw2"
    assert out.wavelength == pytest.approx(1.5406)


def test_rigaku_round_trip(tmp_path: Path) -> None:
    pat = synth_pattern(n=60, start=20.0, step=0.02)
    p = tmp_path / "x.raw"
    write_rigaku_raw(p, pat)
    out = read_rigaku_raw(p)
    assert np.allclose(out.two_theta, pat.two_theta, rtol=1e-6, atol=1e-6)
    assert np.allclose(out.intensity, pat.intensity, rtol=1e-6, atol=1e-6)
    assert out.step == pytest.approx(pat.step, abs=1e-6)
    assert out.metadata["format"] == "rigaku_raw"
    assert out.wavelength == pytest.approx(1.5406)


def test_detect_raw2_magic(tmp_path: Path) -> None:
    pat = synth_pattern(n=40)
    p = tmp_path / "x.raw"
    write_raw2(p, pat)
    assert detect_format(p) == FMT_RAW2


def test_detect_rigaku_magic(tmp_path: Path) -> None:
    pat = synth_pattern(n=40)
    p = tmp_path / "x.raw"
    write_rigaku_raw(p, pat)
    assert detect_format(p) == FMT_RIGAKU_RAW


def test_load_pattern_dispatch_raw2(tmp_path: Path) -> None:
    pat = synth_pattern(n=40)
    p = tmp_path / "x.raw"
    write_raw2(p, pat)
    out = load_pattern(p)
    assert out.step == pytest.approx(pat.step, abs=1e-6)
    assert len(out) == 40


def test_load_pattern_dispatch_rigaku(tmp_path: Path) -> None:
    pat = synth_pattern(n=40)
    p = tmp_path / "x.raw"
    write_rigaku_raw(p, pat)
    out = load_pattern(p)
    assert out.step == pytest.approx(pat.step, abs=1e-6)
    assert len(out) == 40


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------
def test_raw2_rejects_bad_magic(tmp_path: Path) -> None:
    p = tmp_path / "x.raw"
    p.write_bytes(b"NOTRAW2" + b"\x00" * 400)
    with pytest.raises(ValueError, match="Not a RAW2"):
        read_raw2(p)


def test_rigaku_rejects_bad_magic(tmp_path: Path) -> None:
    p = tmp_path / "x.raw"
    p.write_bytes(b"NOTRIGAKU" + b"\x00" * 400)
    with pytest.raises(ValueError, match="Not a Rigaku"):
        read_rigaku_raw(p)


def test_rigaku_rejects_bad_axis(tmp_path: Path) -> None:
    pat = synth_pattern(n=40)
    p = tmp_path / "x.raw"
    write_rigaku_raw(p, pat)
    data = bytearray(p.read_bytes())
    data[0xB96 : 0xB9A] = struct.pack("<f", 0.0)  # end=0 < start
    p.write_bytes(bytes(data))
    with pytest.raises(ValueError, match="axis"):
        read_rigaku_raw(p)


# ---------------------------------------------------------------------------
# Real samples (skipped when data sets absent)
# ---------------------------------------------------------------------------
_IUCr = Path(r"D:\Project\XRD\XRData\IUCr")
_CSUHJW = Path(r"D:\Project\XRD\XRData\csuHJW")


def test_real_iucr_cpd1c_raw2() -> None:
    """IUCr round-robin .raw (RAW2): 7251 pts, 5–150°, strongest peak ZnO(101)."""
    path = _IUCr / "CPD-1C.RAW"
    if not path.exists():
        pytest.skip("IUCr data set not present")
    out = read_raw2(path)
    assert len(out) == 7251
    assert out.two_theta[0] == pytest.approx(5.0, abs=1e-3)
    assert out.two_theta[-1] == pytest.approx(150.0, abs=1e-2)
    assert out.step == pytest.approx(0.02, abs=1e-4)
    assert float(out.intensity.max()) == pytest.approx(24180.0, rel=1e-3)
    i_max = int(np.argmax(out.intensity))
    # strongest peak = ZnO (101) ≈ 36.25°
    assert abs(out.two_theta[i_max] - 36.25) < 0.3


def test_real_iucr_brucite_raw2() -> None:
    path = _IUCr / "BRUCITE.RAW"
    if not path.exists():
        pytest.skip("IUCr data set not present")
    out = read_raw2(path)
    assert len(out) == 7251
    # Brucite (001) ≈ 18.6°, (101) ≈ 38.0°, (102) ≈ 50.7°
    for tth in (18.6, 38.0, 50.7):
        idx = int(round((tth - out.two_theta[0]) / out.step))
        lo, hi = max(0, idx - 10), min(len(out), idx + 11)
        win = out.intensity[lo:hi]
        assert win.max() > 200, f"no intensity near Brucite peak at {tth:.1f}°"
        at = lo + int(np.argmax(win))
        assert abs(out.two_theta[at] - tth) < 0.5


def test_real_csuhjw_si_rigaku() -> None:
    """csuHJW standard Si (Rigaku FI): 4000 pts, 20–100°, Si 111/220 aligned."""
    path = _CSUHJW / "data002：标准Si.raw"
    if not path.exists():
        pytest.skip("csuHJW data set not present")
    out = read_rigaku_raw(path)
    assert len(out) == 4000
    assert out.two_theta[0] == pytest.approx(20.0, abs=1e-2)
    assert out.two_theta[-1] == pytest.approx(99.98, abs=1e-2)
    assert out.step == pytest.approx(0.02, abs=1e-4)
    i_max = int(np.argmax(out.intensity))
    # Si 111 ≈ 28.44° (instrument offset ~ -0.1°)
    assert abs(out.two_theta[i_max] - 28.44) < 0.3
    # second strongest = Si 220 ≈ 47.30°
    idx220 = int(round((47.30 - out.two_theta[0]) / out.step))
    lo, hi = max(0, idx220 - 10), min(len(out), idx220 + 11)
    win = out.intensity[lo:hi]
    assert win.max() > 5000, "no intensity near Si 220"


def test_real_csuhjw_copper_rigaku() -> None:
    """csuHJW copper series (Rigaku FI): fcc Cu peaks aligned."""
    path = _CSUHJW / "Data007：铜衍射谱系列.raw"
    if not path.exists():
        pytest.skip("csuHJW data set not present")
    out = read_rigaku_raw(path)
    assert len(out) > 1000
    # fcc Cu (Cu Kα): 111 ≈ 43.3°, 200 ≈ 50.4°, 220 ≈ 74.1°
    for tth in (43.3, 50.4, 74.1):
        idx = int(round((tth - out.two_theta[0]) / out.step))
        if not (0 <= idx < len(out)):
            continue
        lo, hi = max(0, idx - 12), min(len(out), idx + 13)
        win = out.intensity[lo:hi]
        assert win.max() > 1000, f"no intensity near Cu peak at {tth:.1f}°"
        at = lo + int(np.argmax(win))
        assert abs(out.two_theta[at] - tth) < 0.6
