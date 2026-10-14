"""Tests for Bruker RAW ver. 3 / ver. 4 readers (T2.4).

Synthetic round-trips run everywhere; a real RAW1.01 sample (hard-metal WC
residual-stress scan) is verified when the csuHJW data set is present.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from xinmatch.core.io import detect_format, load_pattern
from xinmatch.core.io.bruker_raw import (
    read_bruker_raw_v3,
    read_bruker_raw_v4,
)
from xinmatch.core.io.detect import FMT_RAW3, FMT_RAW4

from ._samples import synth_pattern, write_raw3, write_raw4


# ---------------------------------------------------------------------------
# Synthetic round-trips — RAW ver. 3
# ---------------------------------------------------------------------------
def test_raw3_round_trip(tmp_path: Path) -> None:
    pat = synth_pattern(n=60, start=20.0, step=0.05)
    p = tmp_path / "x.raw"
    write_raw3(p, pat)
    out = read_bruker_raw_v3(p)
    assert np.allclose(out.two_theta, pat.two_theta, rtol=1e-9, atol=1e-9)
    assert np.allclose(out.intensity, pat.intensity, rtol=1e-5, atol=1e-5)
    assert out.step == pytest.approx(pat.step, abs=1e-9)
    assert out.metadata["format"] == "raw3"
    assert out.metadata["bruker_raw_version"] == 3
    assert out.metadata["anode"] == "Cu"
    assert out.metadata["ka1_angstrom"] == pytest.approx(1.5406)
    assert out.wavelength == pytest.approx(1.5406)


def test_raw3_multi_block(tmp_path: Path) -> None:
    """Multi-block files: every block shares the axis, reader selects one."""
    pat = synth_pattern(n=40, start=57.75, step=0.03)
    p = tmp_path / "x.raw"
    write_raw3(p, pat, n_blocks=10)
    for block in (0, 3, 9):
        out = read_bruker_raw_v3(p, block=block)
        assert len(out) == 40
        assert out.metadata["block"] == block
        assert out.metadata["n_blocks"] == 10
        assert out.two_theta[0] == pytest.approx(57.75, abs=1e-9)
        assert out.step == pytest.approx(0.03, abs=1e-9)


def test_raw3_block_out_of_range(tmp_path: Path) -> None:
    pat = synth_pattern(n=10)
    p = tmp_path / "x.raw"
    write_raw3(p, pat, n_blocks=2)
    with pytest.raises(ValueError, match="out of range"):
        read_bruker_raw_v3(p, block=5)


def test_raw3_rejects_bad_magic(tmp_path: Path) -> None:
    p = tmp_path / "x.raw"
    p.write_bytes(b"RAW4.00" + b"\x00" * 400)
    with pytest.raises(ValueError, match="Not a Bruker RAW ver. 3"):
        read_bruker_raw_v3(p)


def test_detect_raw3_magic(tmp_path: Path) -> None:
    pat = synth_pattern(n=10)
    p = tmp_path / "x.raw"
    write_raw3(p, pat)
    assert detect_format(p) == FMT_RAW3


def test_load_pattern_dispatch_raw3(tmp_path: Path) -> None:
    pat = synth_pattern(n=40, start=20.0, step=0.02)
    p = tmp_path / "x.raw"
    write_raw3(p, pat)
    out = load_pattern(p)
    assert len(out) == 40
    assert out.metadata["format"] == "raw3"


# ---------------------------------------------------------------------------
# Synthetic round-trips — RAW ver. 4
# ---------------------------------------------------------------------------
def test_raw4_round_trip(tmp_path: Path) -> None:
    pat = synth_pattern(n=50, start=10.0, step=0.02)
    p = tmp_path / "x.raw"
    write_raw4(p, pat)
    out = read_bruker_raw_v4(p)
    assert np.allclose(out.two_theta, pat.two_theta, rtol=1e-9, atol=1e-9)
    assert np.allclose(out.intensity, pat.intensity, rtol=1e-5, atol=1e-5)
    assert out.metadata["format"] == "raw4"
    assert out.metadata["bruker_raw_version"] == 4
    assert out.metadata["scan_type"] == "Locked Coupled"
    assert out.metadata["generator_kv"] == pytest.approx(40.0)
    assert out.wavelength == pytest.approx(1.5406)


def test_detect_raw4_magic(tmp_path: Path) -> None:
    pat = synth_pattern(n=10)
    p = tmp_path / "x.raw"
    write_raw4(p, pat)
    assert detect_format(p) == FMT_RAW4


def test_load_pattern_dispatch_raw4(tmp_path: Path) -> None:
    pat = synth_pattern(n=30)
    p = tmp_path / "x.raw"
    write_raw4(p, pat)
    out = load_pattern(p)
    assert len(out) == 30
    assert out.metadata["format"] == "raw4"


def test_raw4_rejects_bad_magic(tmp_path: Path) -> None:
    p = tmp_path / "x.raw"
    p.write_bytes(b"RAW1.01" + b"\x00" * 400)
    with pytest.raises(ValueError, match="Not a Bruker RAW ver. 4"):
        read_bruker_raw_v4(p)


def test_raw4_no_powder_bank(tmp_path: Path) -> None:
    """A v4 file with only metadata segments must fail loudly."""
    p = tmp_path / "x.raw"
    buf = bytearray(b"RAW4.00" + b"\x00" * 54)
    buf += struct_pack_seg30()
    p.write_bytes(bytes(buf))
    with pytest.raises(ValueError, match="No readable powder-data bank"):
        read_bruker_raw_v4(p)


def struct_pack_seg30() -> bytes:
    import struct

    seg30_len = 120
    body = b"\x00" * 64
    body += struct.pack("<5d", 1.5406, 1.5406, 1.54439, 1.492, 0.5)
    body += b"\x00" * 4
    body += b"Cu\x00\x00"
    body += b"\x00" * (seg30_len - 120)
    return struct.pack("<II", 30, seg30_len) + body


# ---------------------------------------------------------------------------
# Real RAW1.01 sample (skipped when data set absent)
# ---------------------------------------------------------------------------
_CSuHJW = Path(r"D:\Project\XRD\XRData\csuHJW")


def test_real_raw3_wc_residual_stress() -> None:
    """csuHJW data035 — RAW1.01, 10 blocks × 147 pts, 57.75–62.13°.

    The file is a hard-metal (WC) residual-stress scan: each block is one
    ψ-tilted segment of the same 2θ window; every block must parse and the
    block-0 pattern must show the WC(200)/(102) region peak near 59.6–60°.
    """
    path = _CSuHJW / "data035：硬质合金深冷处理后WC相的残余应力.raw"
    if not path.exists():
        pytest.skip("csuHJW data set not present")
    out = read_bruker_raw_v3(path)
    assert out.metadata["bruker_raw_version"] == 3
    assert out.metadata["n_blocks"] == 10
    assert out.metadata["block"] == 0
    assert len(out) == 147
    assert out.two_theta[0] == pytest.approx(57.75, abs=1e-9)
    assert out.two_theta[-1] == pytest.approx(62.13, abs=1e-9)
    assert out.step == pytest.approx(0.03, abs=1e-9)
    i_max = int(np.argmax(out.intensity))
    # strongest reflection in this window: WC(200)/(102) region ≈ 59.6–60.0°
    assert 59.4 <= out.two_theta[i_max] <= 60.2
    # every block shares the same axis
    for block in (1, 5, 9):
        b = read_bruker_raw_v3(path, block=block)
        assert len(b) == 147
        assert b.two_theta[0] == pytest.approx(57.75, abs=1e-9)
