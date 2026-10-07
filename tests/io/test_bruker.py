"""Tests for Bruker/Siemens readers (T2.4)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pytest

from xinmatch.core.io.bruker import read_brml, read_raw, read_uxd

from ._samples import synth_pattern, write_brml, write_uxd

RTOL = 1e-9


# ---------------------------------------------------------------------------
# .uxd
# ---------------------------------------------------------------------------
def test_uxd_round_trip(tmp_path: Path) -> None:
    """.uxd synthetic sample parses back to the same 2θ/I."""
    pat = synth_pattern(n=40)
    p = tmp_path / "x.uxd"
    write_uxd(p, pat)
    out = read_uxd(p)
    assert np.allclose(out.two_theta, pat.two_theta, rtol=RTOL, atol=RTOL)
    assert np.allclose(out.intensity, pat.intensity, rtol=RTOL, atol=RTOL)
    assert out.step == pytest.approx(pat.step)


def test_uxd_no_2theta_block_raises(tmp_path: Path) -> None:
    """.uxd without a ;_2theta block raises ValueError."""
    p = tmp_path / "x.uxd"
    p.write_text(";_measurement\n;_end\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_uxd(p)


# ---------------------------------------------------------------------------
# .brml
# ---------------------------------------------------------------------------
def test_brml_round_trip(tmp_path: Path) -> None:
    """.brml ZIP+XML container parses back to the same 2θ/I."""
    pat = synth_pattern(n=30)
    p = tmp_path / "x.brml"
    write_brml(p, pat)
    assert zipfile.is_zipfile(p)
    out = read_brml(p)
    assert np.allclose(out.two_theta, pat.two_theta, rtol=RTOL, atol=RTOL)
    assert np.allclose(out.intensity, pat.intensity, rtol=RTOL, atol=RTOL)


def test_brml_no_xml_raises(tmp_path: Path) -> None:
    """A .brml with no XML files raises ValueError."""
    p = tmp_path / "empty.brml"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("readme.txt", "no data")
    with pytest.raises(ValueError):
        read_brml(p)


# ---------------------------------------------------------------------------
# .raw  (TODO / not implemented)
# ---------------------------------------------------------------------------
def test_raw_not_implemented(tmp_path: Path) -> None:
    """Bruker .raw raises NotImplementedError (proprietary binary)."""
    p = tmp_path / "x.raw"
    p.write_bytes(b"\x00" * 64)
    with pytest.raises(NotImplementedError):
        read_raw(p)
