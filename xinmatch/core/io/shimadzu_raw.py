"""Reader for Shimadzu XRD binary ``.raw`` files.

The format is a binary container written by Shimadzu XRD software
(``Ver 0.00`` block, 12-byte ASCII magic ``Shimadzu XRD``).  Layout (all
integers little-endian):

============  =======  =============================================
offset        type     meaning
============  =======  =============================================
0x000–0x05F   ASCII    header text: magic, version, sample label,
                       target element ("Cu" etc.)
0x12C (300)   int32    2θ start  × 10_000
0x130 (304)   int32    2θ end    × 10_000
0x134 (308)   int32    step      × 10_000 (cross-check; see below)
0x144 (324)   float32  preset time (s/point)
0x15C (348)   float32  receiving slit (mm)
0x270 (624)   int32    declared point count
0x278 (632)   int32    maximum intensity (mirrors data max)
============  =======  =============================================

The intensity block is the trailing ``npts`` little-endian int32 values.
Its start offset is declared in the header itself: a base address (u32 at
0x30) with the data beginning at ``base + 56`` — this reproduces all three
header lengths observed across the XRData Shimadzu collection (968 / 976 /
1608 bytes) without inferring anything from the file size.  Inferring the
offset as ``file_size - 4*npts`` was deliberately removed: the accompanying
self-consistency check ``data_off + 4*npts == file_size`` is a mathematical
identity (``data_off`` is defined by that very equation), so a truncated
file always looked "self-consistent" and the read window slid into the
header, silently misreading header bytes as intensity.  With the declared
offset a truncated file is handled defensively: the available points are
returned and the truncation is recorded in ``metadata["truncated"]``.

The 2θ grid is ``start + step * arange(npts)`` where the step is derived
from the axis span ``(end - start) / (npts - 1)`` — this is more accurate
than the ``×10_000`` step field for instruments that sample at
non-round steps.  The header step is kept in the metadata for reference.
Wavelength defaults to Cu Kα (1.5406 Å) and is refined from the target
token in the header text when a recognised element appears.

Non-powder scans (rocking curves, pole figures) store axes outside the
powder 2θ range (e.g. θ=-1..1 or azimuth 0..360) and are rejected with a
clear error.  A ``theta_mode`` switch doubles a θ axis into 2θ for the
rare single-axis recording mode.  Truncated files (declared ``npts``
larger than the remaining bytes) are read defensively: the available
points are returned and the truncation is recorded in
``metadata["truncated"]``.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

from xinmatch.core.model import Pattern

# ---------------------------------------------------------------------------
# Binary layout constants
# ---------------------------------------------------------------------------
MAGIC = b"Shimadzu XRD"
DATA_OFFSET = 968   # smallest observed header length; fallback when the
                    # base field at 0x30 is missing or implausible
OFF_HDR_BASE = 48   # u32 header base address; data starts at base + 56

OFF_START = 300   # int32, 2θ start × 1e4
OFF_END = 304     # int32, 2θ end × 1e4
OFF_STEP = 308    # int32, step × 1e4 (cross-check only)
OFF_NPTS = 624    # int32, point count
OFF_MAXI = 632    # int32, max intensity (informational)
OFF_PRESET = 324  # float32, preset time (s/point)
OFF_SLIT = 348    # float32, receiving slit (mm)

_SCALE = 10_000.0

# Target element -> (Kα wavelength Å, name).  Header stores the element
# token in the header text (e.g. "Cu", "Cr", "Fe", "Co", "Mo", "Ag").
_TARGET_WAVELENGTH: dict[str, tuple[float, str]] = {
    "CU": (1.5406, "Cu Kα"),
    "CR": (2.2897, "Cr Kα"),
    "FE": (1.9373, "Fe Kα"),
    "CO": (1.7903, "Co Kα"),
    "MO": (0.7093, "Mo Kα"),
    "AG": (0.5609, "Ag Kα"),
}


def is_shimadzu_raw(raw: bytes) -> bool:
    """Return ``True`` if *raw* starts with the Shimadzu XRD magic."""
    return raw.startswith(MAGIC)


def _header_text(raw: bytes, limit: int) -> str:
    """Extract printable header text (ASCII range)."""
    return "".join(chr(b) if 32 <= b < 127 else "" for b in raw[:limit])


def _target_wavelength(header: str) -> tuple[float, str]:
    """Resolve radiation wavelength from the target token in the header."""
    for token, (wl, name) in _TARGET_WAVELENGTH.items():
        if token in header.upper():
            return wl, name
    return 1.5406, "Cu Kα (assumed)"


def _i32(raw: bytes, off: int) -> int:
    return int(struct.unpack_from("<i", raw, off)[0])


def _u32(raw: bytes, off: int) -> int | None:
    try:
        return int(struct.unpack_from("<I", raw, off)[0])
    except struct.error:
        return None


def _f32(raw: bytes, off: int) -> float | None:
    try:
        (v,) = struct.unpack_from("<f", raw, off)
    except struct.error:
        return None
    if not np.isfinite(v):
        return None
    return float(v)


def read_shimadzu_raw(path: str | Path, theta_mode: bool = False) -> Pattern:
    """Read a Shimadzu XRD binary ``.raw`` file.

    Parameters
    ----------
    path:
        Path to the ``.raw`` file.
    theta_mode:
        Set ``True`` when the recorded axis is θ (single-axis rocking
        mode); the grid is then doubled to 2θ.  Defaults to ``False``
        (2θ-recording Theta-2Theta / Theta-Theta instruments).

    Returns
    -------
    Pattern
        Parsed diffraction pattern with a uniform 2θ axis.

    Raises
    ------
    ValueError
        If the file is not a Shimadzu ``.raw`` container, the axis is a
        non-powder scan (rocking/pole figure), or the intensity block is
        invalid.
    """
    p = Path(path)
    raw = p.read_bytes()

    if not is_shimadzu_raw(raw):
        raise ValueError(f"Not a Shimadzu XRD .raw file: {p}")

    if len(raw) < DATA_OFFSET + 4:
        raise ValueError(f"Shimadzu .raw file too short: {p}")

    start = _i32(raw, OFF_START) / _SCALE
    end = _i32(raw, OFF_END) / _SCALE
    step_hdr = _i32(raw, OFF_STEP) / _SCALE
    npts = _i32(raw, OFF_NPTS)

    # -- header sanity ---------------------------------------------------
    if npts <= 1 or not (np.isfinite(start) and np.isfinite(end)):
        raise ValueError(
            f"Shimadzu .raw has invalid axis parameters "
            f"(npts={npts}, start={start}, end={end}): {p}"
        )
    # Non-powder scans (rocking curves θ=-1..1, pole-figure azimuths
    # 0..360°) record an axis outside the powder 2θ range; they must not
    # be fed into phase analysis as if they were diffraction patterns.
    if not (0.0 <= start < end <= 180.0):
        raise ValueError(
            f"Shimadzu .raw axis is not a standard 2θ scan "
            f"(start={start}, end={end}); likely a rocking/pole-figure "
            f"scan, skipping: {p}"
        )

    # -- intensity block: header-declared offset + truncation clamp ------
    # Data starts at the declared header base (u32@0x30) + 56.  This handles
    # the variable-length header (968/976/1608-byte subtypes) directly and
    # replaces the old ``len(raw) - 4*npts`` inference, whose size
    # self-consistency check ``data_off + 4*npts == len(raw)`` was a
    # mathematical identity (data_off was defined by that very equation) and
    # therefore masked truncated files: the read window slid into the header
    # and header bytes were silently misread as intensity.
    base = _u32(raw, OFF_HDR_BASE)
    # base field missing/zero (not written by every writer): fall back to
    # the smallest observed header length
    data_off = base + 56 if base is not None and base + 56 >= DATA_OFFSET else DATA_OFFSET
    if data_off + 4 * npts > len(raw):
        # Truncated: the declared data region extends past EOF.  Keep the
        # real header offset and clamp to the points actually present —
        # never slide the read window into the header.
        avail = (len(raw) - data_off) // 4
        n_read = min(npts, max(avail, 0))
        if n_read < 2:
            raise ValueError(f"Shimadzu .raw has no usable intensity data: {p}")
    else:
        n_read = npts

    try:
        intensities = np.asarray(
            struct.unpack(f"<{n_read}i", raw[data_off : data_off + n_read * 4]),
            dtype=np.float64,
        )
    except struct.error as exc:  # pragma: no cover - guarded by n_read
        raise ValueError(f"Shimadzu .raw data block unreadable: {p}") from exc

    # intensity sanity guard: negatives / NaN mean the offset or dtype
    # guess is wrong — report instead of returning garbage
    if not np.all(np.isfinite(intensities)) or float(intensities.min()) < 0:
        raise ValueError(
            f"Shimadzu .raw intensity block invalid "
            f"(min={float(intensities.min()):.0f}), unsupported subtype: {p}"
        )

    # -- 2θ axis: derive the step from the span (more accurate than the
    #    ×1e4 step field for non-round sampling steps)
    step = (end - start) / (npts - 1)
    two_theta = start + step * np.arange(n_read, dtype=np.float64)
    if theta_mode:
        two_theta = 2.0 * two_theta

    truncated = n_read < npts
    header = _header_text(raw, data_off)
    wavelength, target_name = _target_wavelength(header)

    metadata: dict = {
        "format": "shimadzu_raw",
        "vendor": "Shimadzu",
        "target": target_name,
        "scan_start_deg": float(start),
        "scan_end_deg": float(end),
        "npts_declared": int(npts),
        "step_header_deg": float(step_hdr),
        "data_offset": int(data_off),
        "truncated": truncated,
    }
    # informational header fields when present
    preset = _f32(raw, OFF_PRESET)
    if preset is not None and preset > 0:
        metadata["preset_time_s"] = preset
    slit = _f32(raw, OFF_SLIT)
    if slit is not None and slit > 0:
        metadata["receiving_slit_mm"] = slit

    return Pattern(
        two_theta=two_theta,
        intensity=intensities,
        wavelength=wavelength,
        step=float(step),
        metadata=metadata,
    )
