"""Tests for the XRDML, MDI, Shimadzu-text, RAS/CPI/PLV/ESG/GDF readers.

Synthetic round-trip tests run everywhere; real-sample verification tests
run only when the corresponding sample files exist on this machine.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from xinmatch.core.io import (
    detect_format,
    load_pattern,
    read_cpi,
    read_esg,
    read_gdf,
    read_mdi,
    read_plv,
    read_ras,
    read_shimadzu_txt,
    read_xrdml,
)
from xinmatch.core.io.detect import (
    FMT_CPI,
    FMT_ESG,
    FMT_GDF,
    FMT_MDI,
    FMT_PLV,
    FMT_RAS,
    FMT_SHIMADZU_TXT,
    FMT_XRDML,
)
from xinmatch.core.model import Pattern

from ._samples import (
    synth_pattern,
    write_cpi,
    write_esg,
    write_gdf,
    write_mdi,
    write_plv,
    write_ras,
    write_xrdml,
)


# ---------------------------------------------------------------------------
# XRDML
# ---------------------------------------------------------------------------
def test_xrdml_round_trip(tmp_path: Path) -> None:
    pat = synth_pattern(n=50, start=10.0, step=0.02)
    p = tmp_path / "x.xrdml"
    write_xrdml(p, pat)
    out = read_xrdml(p)
    assert np.allclose(out.two_theta, pat.two_theta, rtol=1e-6, atol=1e-6)
    assert np.allclose(out.intensity, pat.intensity, rtol=1e-6, atol=1e-6)
    assert out.metadata["format"] == "xrdml"
    assert detect_format(p) == FMT_XRDML


def test_xrdml_namespace_variant(tmp_path: Path) -> None:
    """A 2.0-namespace file with positions/intensities parses identically."""
    pat = synth_pattern(n=20, start=5.0, step=0.05)
    xml = (
        '<?xml version="1.0"?>\n'
        "<xrdMeasurements xmlns=\"http://www.xrdml.com/XRDMeasurement/2.0\">\n"
        "  <xrdMeasurement><scan><dataPoints>\n"
        "    <positions>\n"
        "      <axis axisName=\"2Theta\">"
        + " ".join(f"{t:.6f}" for t in pat.two_theta)
        + "</axis>\n    </positions>\n"
        "    <intensities>"
        + " ".join(f"{v:.6f}" for v in pat.intensity)
        + "</intensities>\n"
        "  </dataPoints></scan></xrdMeasurement>\n</xrdMeasurements>\n"
    )
    p = tmp_path / "x.xrdml"
    p.write_text(xml, encoding="utf-8")
    out = read_xrdml(p)
    assert len(out) == 20
    assert np.allclose(out.two_theta, pat.two_theta, atol=1e-4)
    assert out.intensity.max() == pytest.approx(pat.intensity.max())


def test_xrdml_load_pattern_dispatch(tmp_path: Path) -> None:
    pat = synth_pattern(n=30)
    p = tmp_path / "x.xrdml"
    write_xrdml(p, pat)
    out = load_pattern(p)
    assert len(out) == 30


# ---------------------------------------------------------------------------
# MDI
# ---------------------------------------------------------------------------
def test_mdi_round_trip(tmp_path: Path) -> None:
    pat = synth_pattern(n=40, start=10.0, step=0.02)
    lines = ["01/01/26 Synthetic", f"{pat.two_theta[0]:.5f}  {pat.step:.6f}  1.0  Cu  1.540560  {pat.two_theta[-1]:.5f}  {len(pat)}"]
    vals = [str(int(round(v))) for v in pat.intensity]
    for i in range(0, len(vals), 8):
        lines.append(" ".join(vals[i : i + 8]))
    p = tmp_path / "x.mdi"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = read_mdi(p)
    assert len(out) == 40
    assert np.array_equal(out.intensity, np.round(pat.intensity))
    assert out.wavelength == pytest.approx(1.5406)
    assert out.metadata["anode"] == "Cu"
    assert detect_format(p) == FMT_MDI


def test_mdi_lost_first_channel_correction(tmp_path: Path) -> None:
    """count=n with an n-1-step span: axis rebuilt from the header stop."""
    n = 50
    step = 0.02
    stop = 150.0
    start_hdr = stop - step * (n - 1)  # the *real* first point after the drop
    lines = ["01/01/26 Synthetic", f"{start_hdr:.5f}  {step:.6f}  1.0  Cu  1.540560  {stop:.5f}  {n}"]
    for i in range(n):
        lines.append(str(100 + i))
    p = tmp_path / "x.mdi"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = read_mdi(p)
    assert len(out) == n
    assert out.two_theta[-1] == pytest.approx(stop, abs=1e-6)
    # monotonic rising from the rebuilt start
    assert out.two_theta[0] == pytest.approx(start_hdr, abs=1e-6)


def test_mdi_real_4_1() -> None:
    """Real geshi/4-1.mdi: 7250 pts, axis aligned with sibling .dat/.txt/.xy."""
    p = Path(r"D:\Project\XRD\test_xrd\geshi\4-1.mdi")
    if not p.exists():
        pytest.skip("test_xrd/geshi sample not present")
    out = read_mdi(p)
    assert len(out) == 7250
    # last point must land on the header stop (150.0) — lost-first-channel fix
    assert out.two_theta[-1] == pytest.approx(150.0, abs=1e-4)
    assert out.step == pytest.approx(0.02, abs=1e-6)
    assert out.wavelength == pytest.approx(1.54056, abs=1e-4)
    # strongest peak near the same position as the .dat export
    dat = Path(r"D:\Project\XRD\test_xrd\geshi\4-1.dat")
    if dat.exists():
        dlines = [ln for ln in dat.read_text(encoding="utf-8-sig", errors="ignore").splitlines() if ln.strip()]
        rows = []
        for ln in dlines:
            toks = ln.replace(",", " ").split()
            if len(toks) >= 2:
                try:
                    rows.append((float(toks[0]), float(toks[1])))
                except ValueError:
                    continue
        dat_imax = max(rows, key=lambda r: r[1])[0]
        mdi_imax = float(out.two_theta[int(np.argmax(out.intensity))])
        assert abs(mdi_imax - dat_imax) < 0.02


# ---------------------------------------------------------------------------
# Shimadzu text export
# ---------------------------------------------------------------------------
def _write_shimadzu_txt(path: Path, pat: Pattern) -> None:
    text = (
        "Shimadzu XRD\n"
        "target: Cu\n"
        "voltage: 40\n"
        "current: 40\n"
        "scan range: 10.0 - 20.0\n"
        "sampling pitch: 0.02\n"
        "preset time: 0.6\n"
        "wavelength: 1.54056\n"
        "<2Theta> <Intensity>\n"
    )
    rows = "\n".join(f"{t:.5f} {i:.1f}" for t, i in zip(pat.two_theta, pat.intensity, strict=True))
    path.write_text(text + rows + "\n", encoding="utf-8")


def test_shimadzu_txt_round_trip(tmp_path: Path) -> None:
    pat = synth_pattern(n=40, start=10.0, step=0.02)
    p = tmp_path / "x.txt"
    _write_shimadzu_txt(p, pat)
    assert detect_format(p) == FMT_SHIMADZU_TXT
    out = read_shimadzu_txt(p)
    assert len(out) == 40
    assert out.two_theta[0] == pytest.approx(10.0, abs=1e-4)
    assert out.wavelength == pytest.approx(1.54056, abs=1e-4)
    assert out.metadata["target"] == "Cu"
    assert out.metadata["voltage"] == pytest.approx(40.0)
    assert out.metadata["format"] == "shimadzu_txt"


def test_shimadzu_txt_target_wavelength(tmp_path: Path) -> None:
    pat = synth_pattern(n=20)
    p = tmp_path / "x.txt"
    _write_shimadzu_txt(p, pat)
    raw = p.read_text(encoding="utf-8")
    p.write_text(raw.replace("target: Cu", "target: Fe"), encoding="utf-8")
    out = read_shimadzu_txt(p)
    assert out.wavelength == pytest.approx(1.9373, abs=1e-4)


def test_plain_txt_still_ascii_2col(tmp_path: Path) -> None:
    """Text files without Shimadzu header tokens stay on the generic path."""
    pat = synth_pattern(n=20)
    p = tmp_path / "plain.txt"
    p.write_text(
        "\n".join(f"{t:.4f} {i:.1f}" for t, i in zip(pat.two_theta, pat.intensity, strict=True)),
        encoding="utf-8",
    )
    assert detect_format(p) != FMT_SHIMADZU_TXT
    out = load_pattern(p)
    assert len(out) == 20


# ---------------------------------------------------------------------------
# RAS / CPI / PLV / ESG / GDF (synthetic round-trips)
# ---------------------------------------------------------------------------
def test_ras_round_trip(tmp_path: Path) -> None:
    p = tmp_path / "x.ras"
    write_ras(p)
    assert detect_format(p) == FMT_RAS
    out = read_ras(p)
    assert len(out) == 2
    assert out.two_theta[0] == pytest.approx(5.0)
    assert out.intensity[1] == pytest.approx(101.0)


def test_cpi_round_trip(tmp_path: Path) -> None:
    p = tmp_path / "x.cpi"
    write_cpi(p)
    assert detect_format(p) == FMT_CPI
    out = read_cpi(p)
    assert len(out) == 3
    assert out.two_theta[0] == pytest.approx(10.0, abs=1e-3)
    assert out.step == pytest.approx(0.02, abs=1e-6)
    assert np.array_equal(out.intensity, [100.0, 200.0, 300.0])


def test_plv_round_trip(tmp_path: Path) -> None:
    p = tmp_path / "x.plv"
    write_plv(p)
    assert detect_format(p) == FMT_PLV
    out = read_plv(p)
    assert len(out) == 2
    assert out.two_theta[0] == pytest.approx(10.0)


def test_esg_round_trip(tmp_path: Path) -> None:
    p = tmp_path / "x.esg"
    write_esg(p)
    assert detect_format(p) == FMT_ESG
    out = read_esg(p)
    assert len(out) == 2


def test_gdf_round_trip(tmp_path: Path) -> None:
    p = tmp_path / "x.gdf"
    write_gdf(p)
    assert detect_format(p) == FMT_GDF
    out = read_gdf(p)
    assert len(out) == 2


def test_all_vendor_formats_dispatch(tmp_path: Path) -> None:
    """Every detected vendor format now has a working load_pattern path."""
    pat = synth_pattern(n=30)
    p = tmp_path / "x.xrdml"
    write_xrdml(p, pat)
    assert len(load_pattern(p)) == 30
    for maker, name in [
        (write_ras, "a.ras"),
        (write_cpi, "a.cpi"),
        (write_plv, "a.plv"),
        (write_mdi, "a.mdi"),
        (write_esg, "a.esg"),
        (write_gdf, "a.gdf"),
    ]:
        q = tmp_path / name
        maker(q)
        assert len(load_pattern(q)) >= 2
