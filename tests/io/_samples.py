"""Synthetic sample-file generators for I/O tests.

Since no real vendor sample files are available, each helper builds a
small, self-consistent file in the target format from synthetic 2θ/intensity
data.  These are used by ``tests/io/test_*.py`` for round-trip and
detection checks.
"""

from __future__ import annotations

import struct
import zipfile
from pathlib import Path

import numpy as np

from xinmatch.core.model import Pattern


def synth_pattern(n: int = 50, start: float = 10.0, step: float = 0.02) -> Pattern:
    """Create a synthetic Pattern with a few Gaussian peaks."""
    rng = np.random.default_rng(42)
    two_theta = start + step * np.arange(n, dtype=np.float64)
    intensity = 100.0 + rng.normal(0.0, 5.0, size=n)
    # Add a couple of peaks
    for center, amp in [(20.0, 500.0), (35.0, 800.0)]:
        intensity += amp * np.exp(-((two_theta - center) ** 2) / (2 * 0.3**2))
    return Pattern(two_theta=two_theta, intensity=intensity, step=step)


# ---------------------------------------------------------------------------
# Free formats
# ---------------------------------------------------------------------------
def write_dbws(path: Path, pat: Pattern, title: str = "synth") -> None:
    """Write a DBWS-format file."""
    start = float(pat.two_theta[0])
    step = float(pat.step) if pat.step else 0.02
    end = float(pat.two_theta[-1])
    lines = [f"{start:.10f}   {step:.10f}  {end:.10f}    {title}"]
    vals = pat.intensity
    for i in range(0, vals.size, 8):
        chunk = vals[i : i + 8]
        lines.append("  ".join(f"{v:.10f}" for v in chunk))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_ascii_3col(path: Path, pat: Pattern) -> None:
    """Write an ASCII profile (start, step, end + intensities)."""
    start = float(pat.two_theta[0])
    step = float(pat.step) if pat.step else 0.02
    end = float(pat.two_theta[-1])
    lines = [f"{start:.10f}   {step:.10f}  {end:.10f}"]
    vals = pat.intensity
    for i in range(0, vals.size, 9):
        chunk = vals[i : i + 9]
        lines.append("  ".join(f"{v:.10f}" for v in chunk))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_ascii_2col_hdr(path: Path, pat: Pattern) -> None:
    """Write an ASCII profile (start, step + intensities)."""
    start = float(pat.two_theta[0])
    step = float(pat.step) if pat.step else 0.02
    lines = [f"{start:.10f}   {step:.10f}"]
    vals = pat.intensity
    for i in range(0, vals.size, 9):
        chunk = vals[i : i + 9]
        lines.append("  ".join(f"{v:.10f}" for v in chunk))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_ascii_2col(
    path: Path, pat: Pattern, sep: str = " ", with_comments: bool = False
) -> None:
    """Write a 2-column (2theta intensity) file with configurable separator."""
    lines = []
    if with_comments:
        lines.append("# synthetic 2-column data")
        lines.append("# 2theta  intensity")
    for t, v in zip(pat.two_theta, pat.intensity, strict=True):
        lines.append(f"{t:.10f}{sep}{v:.10f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_endeavour(path: Path, pat: Pattern) -> None:
    """Write an ENDEAVOUR 2-column peak list."""
    lines = [f"{t:.10f}    {v:.10f}" for t, v in zip(pat.two_theta, pat.intensity, strict=True)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# PANalytical
# ---------------------------------------------------------------------------
def write_rd(path: Path, pat: Pattern) -> None:
    """Write a Philips/PANalytical .rd text file."""
    start = float(pat.two_theta[0])
    step = float(pat.step) if pat.step else 0.02
    end = float(pat.two_theta[-1])
    lines = [
        "*TYPE 1",
        "*IDENTIFICATION synthetic",
        f"*WAVELENGTH {pat.wavelength:.10f}",
        f"*START {start:.10f}",
        f"*STEP {step:.10f}",
        f"*STEPS {len(pat)}",
        f"*END {end:.10f}",
        "*DATA",
    ]
    for v in pat.intensity:
        lines.append(f"{v:.10f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_udf(path: Path, pat: Pattern) -> None:
    """Write a PANalytical .udf INI-style file."""
    start = float(pat.two_theta[0])
    step = float(pat.step) if pat.step else 0.02
    end = float(pat.two_theta[-1])
    lines = [
        "[Header]",
        f"Wavelength = {pat.wavelength:.10f}",
        f"Start = {start:.10f}",
        f"Step = {step:.10f}",
        f"End = {end:.10f}",
        "[Intensities]",
    ]
    for v in pat.intensity:
        lines.append(f"{v:.10f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_udi(path: Path, pat: Pattern) -> None:
    """Write a PANalytical .udi peak-data file."""
    lines = [
        "[Header]",
        f"Wavelength = {pat.wavelength:.10f}",
        "[Peaks]",
    ]
    for t, v in zip(pat.two_theta, pat.intensity, strict=True):
        lines.append(f"{t:.10f} {v:.10f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Bruker
# ---------------------------------------------------------------------------
def write_uxd(path: Path, pat: Pattern) -> None:
    """Write a Bruker/Siemens .uxd text file."""
    start = float(pat.two_theta[0])
    step = float(pat.step) if pat.step else 0.02
    n = len(pat)
    lines = [
        ";_measurement",
        ";_scan",
        ";_2theta",
        f"   {start:.10f}",
        f"   {step:.10f}",
        f"    {n}",
    ]
    for v in pat.intensity:
        lines.append(f"    {v:.10f}")
    lines.append(";_end")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_brml(path: Path, pat: Pattern) -> None:
    """Write a Bruker .brml ZIP+XML container."""
    start = float(pat.two_theta[0])
    step = float(pat.step) if pat.step else 0.02
    end = float(pat.two_theta[-1])
    intensities = " ".join(f"{v:.10f}" for v in pat.intensity)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<Measurement>\n"
        "  <Data1>\n"
        f"    <Intensities>{intensities}</Intensities>\n"
        '    <Axis number="1">\n'
        "      <Name>2Theta</Name>\n"
        f"      <Start>{start:.10f}</Start>\n"
        f"      <Step>{step:.10f}</Step>\n"
        f"      <End>{end:.10f}</End>\n"
        "    </Axis>\n"
        "  </Data1>\n"
        "</Measurement>\n"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Data1.xml", xml)


# ---------------------------------------------------------------------------
# Other vendor formats (for detection only)
# ---------------------------------------------------------------------------
def write_xrdml(path: Path, pat: Pattern) -> None:
    """Write a minimal PANalytical XRDML file."""
    start = float(pat.two_theta[0])
    step = float(pat.step) if pat.step else 0.02
    intensities = " ".join(f"{v:.10f}" for v in pat.intensity)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<xrdml xmlns=\"http://www.xrdml.com/XRDMeasurement/2.1\">\n"
        "  <xrdMeasurements><xrdMeasurement>\n"
        "    <scan>\n"
        f"      <startPosition>{start:.10f}</startPosition>\n"
        f"      <endPosition>{float(pat.two_theta[-1]):.10f}</endPosition>\n"
        "      <dataPoints>\n"
        f"        <step size=\"{step:.10f}\" />\n"
        f"        <intensities>{intensities}</intensities>\n"
        "      </dataPoints>\n"
        "    </scan>\n"
        "  </xrdMeasurement></xrdMeasurements>\n"
        "</xrdml>\n"
    )
    path.write_text(xml, encoding="utf-8", newline="\n")


def write_ras(path: Path) -> None:
    """Write a minimal Rigaku RAS header."""
    lines = [
        "[RAS_INT_START]",
        "*SAMPLE_NAME sample",
        "*BEGIN",
        "5.0 100.0",
        "5.02 101.0",
        "*END",
        "[RAS_INT_END]",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_cpi(path: Path) -> None:
    """Write a minimal Sietronics CPI file."""
    lines = [
        "SIETRONICS XRD",
        "10.000 0.020 80.000",
        "100 200 300",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_plv(path: Path) -> None:
    """Write a minimal XPowder .plv file."""
    lines = [
        "XPOWDER file",
        "10.0 100.0",
        "20.0 200.0",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_mdi(path: Path) -> None:
    """Write a minimal Jade/MDI .mdi file."""
    lines = [
        "JAD5.0",
        "10.0 100.0",
        "20.0 200.0",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_esg(path: Path) -> None:
    """Write a minimal GNR .esg file."""
    lines = ["GNR EXPORT", "10.0 100.0", "20.0 200.0"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_gdf(path: Path) -> None:
    """Write a minimal G670 .gdf file."""
    lines = ["STOE G670 DATA", "10.0 100.0", "20.0 200.0"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Shimadzu binary .raw
# ---------------------------------------------------------------------------
def write_shimadzu_raw(path: Path, pat: Pattern, header_len: int = 968) -> None:
    """Write a Shimadzu XRD binary ``.raw`` file.

    Mirrors the layout read by
    :func:`xinmatch.core.io.shimadzu_raw.read_shimadzu_raw`: ASCII magic
    header, header base (data start = base + 56) at 0x30, declared data
    byte count at 0x34, int32 ×1e4 axis fields at 300/304/308, preset-time/
    slit floats at 324/348, point count at 624, max intensity at 632, and
    the int32 intensity block from ``header_len`` (968/976/1608 subtypes,
    matching the real collection).
    """
    start = float(pat.two_theta[0])
    step = float(pat.step) if pat.step else 0.02
    end = float(pat.two_theta[-1])
    n = len(pat)

    buf = bytearray(b"Shimadzu XRD\x00\x00\x00\x00Ver 0.00")
    buf = buf.ljust(0x30, b"\x00")
    buf += struct.pack("<I", header_len - 56)   # 0x30: header base -> data start
    buf += struct.pack("<I", n * 4)             # 0x34: declared data byte count
    buf += b"\x00" * (0x4C - len(buf))          # pad to the label offset
    buf += b"Synthetic sample          Cu".ljust(32, b"\x00")   # 0x4C: label
    buf = buf.ljust(header_len, b"\x00")
    assert len(buf) == header_len

    def put_i32(off: int, val: int) -> None:
        buf[off : off + 4] = struct.pack("<i", val)

    def put_f32(off: int, val: float) -> None:
        buf[off : off + 4] = struct.pack("<f", val)

    put_i32(300, int(round(start * 10_000)))
    put_i32(304, int(round(end * 10_000)))
    put_i32(308, int(round(step * 10_000)))
    put_f32(324, 0.6)
    put_f32(348, 0.15)
    put_i32(624, n)
    put_i32(632, int(round(float(max(pat.intensity)))))
    buf += struct.pack(f"<{n}i", *[int(round(float(v))) for v in pat.intensity])
    path.write_bytes(bytes(buf))


# ---------------------------------------------------------------------------
# RAW2 fixed-header binary
# ---------------------------------------------------------------------------
def write_raw2(path: Path, pat: Pattern) -> None:
    """Write a RAW2 fixed-header binary file (magic ``RAW2``).

    Mirrors the layout read by :func:`xinmatch.core.io.rigaku.read_raw2`:
    magic + padded header, int16 point count at 0x102, float32 step/start
    at 0x10C/0x110, and float32 intensities after a 316-byte header.
    """
    start = float(pat.two_theta[0])
    step = float(pat.step) if pat.step else 0.02
    n = len(pat)

    buf = bytearray(b"RAW2" + b"CPD-1C.DAT" + b" " * 120 + b"Cu")
    buf = buf.ljust(316, b"\x00")
    assert len(buf) == 316
    buf[0x102 : 0x104] = struct.pack("<h", n)
    buf[0x10C : 0x110] = struct.pack("<f", step)
    buf[0x110 : 0x114] = struct.pack("<f", start)
    buf += struct.pack(f"<{n}f", *[float(v) for v in pat.intensity])
    path.write_bytes(bytes(buf))


# ---------------------------------------------------------------------------
# Bruker RAW ver. 3 (RAW1.01)
# ---------------------------------------------------------------------------
def write_raw3(path: Path, pat: Pattern, *, n_blocks: int = 1) -> None:
    """Write a Bruker RAW ver. 3 binary file (magic ``RAW1.01``).

    Mirrors the layout read by :func:`xinmatch.core.io.bruker_raw.
    read_bruker_raw_v3`: 712-byte fixed header, then one or more blocks
    each with headLen/nSteps at +0/+4, start double at +8, step double at
    +176, and float32 intensities after the headLen-prefixed data area.
    """
    start = float(pat.two_theta[0])
    step = float(pat.step) if pat.step else 0.02
    n = len(pat)

    buf = bytearray(b"RAW1.01")
    buf += b"\x00" * 5
    buf += struct.pack("<i", n_blocks)
    buf = buf.ljust(564, b"\x00")
    buf[564:568] = struct.pack("<f", 250.0)          # gonio radius
    buf = buf.ljust(608, b"\x00")
    buf[608:612] = b"Cu\x00\x00"                     # anode @608
    buf = buf.ljust(616, b"\x00")                    # pad to the Ka block
    buf[616:656] = struct.pack(
        "<5d", 1.5406, 1.5406, 1.54439, 1.492, 0.5
    )
    buf = buf.ljust(712, b"\x00")
    assert len(buf) == 712

    # Real RAW1.01 header field: 304 for multi-block files, but single-block
    # files store 304−40 in the field (readers add 40 back for block==1).
    field_head_len = 304 if n_blocks > 1 else 304 - 40
    for _ in range(n_blocks):
        buf += struct.pack("<ii", field_head_len, n)  # +0/+4
        buf += struct.pack("<d", start)            # +8 start2Th
        buf += b"\x00" * (176 - 16)
        buf += struct.pack("<d", step)             # +176 step
        buf += b"\x00" * (256 - 184)
        buf += struct.pack("<i", 0)                # +256 extra word
        buf += b"\x00" * (304 - 260)               # rest of block header
        buf += struct.pack(f"<{n}f", *[float(v) for v in pat.intensity])
    path.write_bytes(bytes(buf))


# ---------------------------------------------------------------------------
# Bruker RAW ver. 4 (RAW4.00)
# ---------------------------------------------------------------------------
def write_raw4(path: Path, pat: Pattern) -> None:
    """Write a minimal Bruker RAW ver. 4 segmented file (magic ``RAW4.00``).

    Layout follows the GSAS-II-documented v4 reader: 61-byte preamble,
    an X-ray-source segment (type 30), and one powder-data bank with a
    scan-header segment (type 50) followed by float32 intensities.
    """
    start = float(pat.two_theta[0])
    step = float(pat.step) if pat.step else 0.02
    n = len(pat)

    buf = bytearray(b"RAW4.00")
    buf += b"\x00" * 5
    buf += b"01/01/2026\x00\x00"[:12].ljust(12, b"\x00")   # date @12
    buf += b"12:00:00\x00\x00"[:10].ljust(10, b"\x00")     # time @24
    buf = buf.ljust(61, b"\x00")

    # Segment 30: X-ray source (body must be exactly seg30_len bytes)
    seg30_len = 120
    buf += struct.pack("<II", 30, seg30_len)
    buf += b"\x00" * 64
    buf += struct.pack("<5d", 1.5406, 1.5406, 1.54439, 1.492, 0.5)
    buf += b"\x00" * 4
    buf += b"Cu\x00\x00"
    buf += b"\x00" * (seg30_len - 112)  # 64 + 40 + 4 + 4 = 112 already written

    # Powder data bank: fixed field layout (offsets per GSAS-II reader).
    # The scan-header segment (type 50) is skipped by the reader, so its
    # payload is arbitrary padding of the right length.
    hdr_seg = b"\x00" * 64
    hdr_size = len(hdr_seg)
    datum_size = 4

    # segtype 0 marks the bank; payload has the fixed field layout.
    bank_len = 156 + hdr_size + datum_size * n
    buf += struct.pack("<II", 0, bank_len)
    buf += b"\x00" * 28
    buf += b"Locked Coupled\x00".ljust(24, b"\x00")
    buf += b"\x00" * 16
    buf += struct.pack("<d", start)       # startAngle @ +68
    buf += struct.pack("<d", step)        # stepSize   @ +76
    buf += struct.pack("<I", n)           # Nsteps     @ +84
    buf += struct.pack("<f", 1.0)         # stepTime   @ +88
    buf += b"\x00" * 4
    buf += struct.pack("<f", 40.0)        # kV         @ +96
    buf += struct.pack("<f", 40.0)        # mA         @ +100
    buf += b"\x00" * 4
    buf += struct.pack("<d", 1.5406)      # usedWave   @ +108
    buf += b"\x00" * 16
    buf += struct.pack("<I", datum_size)  # datumSize  @ +132
    buf += struct.pack("<I", hdr_size)    # hdrSize    @ +136
    buf += b"\x00" * 16
    buf += hdr_seg
    buf += struct.pack(f"<{n}f", *[float(v) for v in pat.intensity])
    path.write_bytes(bytes(buf))
def write_rigaku_raw(path: Path, pat: Pattern) -> None:
    """Write a Rigaku RINT-2000 binary file (magic ``FI\\x00\\x00``).

    Mirrors the layout read by :func:`xinmatch.core.io.rigaku.
    read_rigaku_raw`: magic, header text padded to offset 0xC5A, float32
    (start, end, step) at 0xB92, then float32 intensities to the end of
    file.
    """
    start = float(pat.two_theta[0])
    step = float(pat.step) if pat.step else 0.02
    n = len(pat)
    # the header stores the *nominal* end 2θ (last point + step); the
    # reader derives n = round((end - start) / step)
    end = start + step * n

    buf = bytearray(b"FI\x00\x00" + b"RINT2000 vertical goniometer Cu" + b"\x00" * 64)
    buf = buf.ljust(0xC5A, b"\x00")
    buf[0xB92 : 0xB96] = struct.pack("<f", start)
    buf[0xB96 : 0xB9A] = struct.pack("<f", end)
    buf[0xB9A : 0xB9E] = struct.pack("<f", step)
    buf += struct.pack(f"<{n}f", *[float(v) for v in pat.intensity])
    path.write_bytes(bytes(buf))
