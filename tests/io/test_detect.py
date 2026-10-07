"""Tests for the format auto-detector (T2.1)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from xinmatch.core.io import detect
from xinmatch.core.io.detect import detect_format

from ._samples import (
    synth_pattern,
    write_ascii_2col,
    write_ascii_2col_hdr,
    write_ascii_3col,
    write_brml,
    write_cpi,
    write_dbws,
    write_endeavour,
    write_esg,
    write_gdf,
    write_mdi,
    write_plv,
    write_ras,
    write_rd,
    write_udf,
    write_udi,
    write_uxd,
    write_xrdml,
)


@pytest.fixture
def sample_dir(tmp_path: Path) -> Path:
    """Create a directory and populate it with one sample per format."""
    pat = synth_pattern(n=20)
    # free formats
    write_dbws(tmp_path / "dbws.rfl", pat)
    write_ascii_3col(tmp_path / "ascii3.dat", pat)
    write_ascii_2col_hdr(tmp_path / "ascii2h.dat", pat)
    write_ascii_2col(tmp_path / "ascii2.dat", pat)
    write_endeavour(tmp_path / "endeavour.dif", pat)
    # panalytical
    write_rd(tmp_path / "scan.rd", pat)
    write_udf(tmp_path / "scan.udf", pat)
    write_udi(tmp_path / "scan.udi", pat)
    # bruker
    write_uxd(tmp_path / "scan.uxd", pat)
    write_brml(tmp_path / "scan.brml", pat)
    # other vendor (detection only)
    write_xrdml(tmp_path / "scan.xrdml", pat)
    write_ras(tmp_path / "scan.ras")
    write_cpi(tmp_path / "scan.cpi")
    write_plv(tmp_path / "scan.plv")
    write_mdi(tmp_path / "scan.mdi")
    write_esg(tmp_path / "scan.esg")
    write_gdf(tmp_path / "scan.gdf")
    return tmp_path


def test_detect_all_formats(sample_dir: Path) -> None:
    """Every supported extension is detected correctly."""
    cases = {
        "dbws.rfl": detect.FMT_DBWS,
        "ascii3.dat": detect.FMT_ASCII_3COL,
        "ascii2h.dat": detect.FMT_ASCII_2COL_HDR,
        "ascii2.dat": detect.FMT_ASCII_2COL,
        "endeavour.dif": detect.FMT_ENDEAVOUR,
        "scan.rd": detect.FMT_RD,
        "scan.udf": detect.FMT_UDF,
        "scan.udi": detect.FMT_UDI,
        "scan.uxd": detect.FMT_UXD,
        "scan.brml": detect.FMT_BRML,
        "scan.xrdml": detect.FMT_XRDML,
        "scan.ras": detect.FMT_RAS,
        "scan.cpi": detect.FMT_CPI,
        "scan.plv": detect.FMT_PLV,
        "scan.mdi": detect.FMT_MDI,
        "scan.esg": detect.FMT_ESG,
        "scan.gdf": detect.FMT_GDF,
    }
    for fname, expected in cases.items():
        assert detect_format(sample_dir / fname) == expected, fname


def test_detect_dbws_by_extension(tmp_path: Path) -> None:
    """A .rfl file is detected as DBWS even without full content parse."""
    pat = synth_pattern(n=10)
    p = tmp_path / "x.rfl"
    write_dbws(p, pat)
    assert detect_format(p) == detect.FMT_DBWS


def test_detect_unknown_file_raises(tmp_path: Path) -> None:
    """An unrecognized file raises ValueError."""
    p = tmp_path / "weird.bin"
    p.write_bytes(b"\x00\x01\x02 not a diffraction file")
    with pytest.raises(ValueError):
        detect_format(p)


def test_detect_nonexistent_raises(tmp_path: Path) -> None:
    """A missing path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        detect_format(tmp_path / "nope.dat")


def test_detect_brml_via_zip_magic(tmp_path: Path) -> None:
    """A .brml file is detected via the ZIP magic bytes."""
    pat = synth_pattern(n=10)
    p = tmp_path / "data.brml"
    write_brml(p, pat)
    assert detect_format(p) == detect.FMT_BRML
    # Verify it's actually a zip
    assert zipfile.is_zipfile(p)
