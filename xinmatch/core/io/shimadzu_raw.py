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

The intensity block is the trailing ``npts`` little-endian int32 values;
its start offset is therefore ``file_size - 4 * npts``.  Header lengths of
968 / 976 / 1608 bytes have all been observed across the XRData Shimadzu
collection, so the offset is inferred from the file size rather than
hard-coded (a fixed 968 fallback is used only when the file is
self-inconsistent, e.g. truncated).

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
DATA_OFFSET = 968   # standard-subtype header length (fallback reference)

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
    return struct.unpack_from("<i", raw, off)[0]


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

    # -- intensity block: trailing npts int32 ----------------------------
    # Infer the data offset from the file size (variable-length header;
    # 968 / 976 / 1608-byte headers observed).  A self-consistent size
    # check alone is not enough: a truncated file still satisfies
    # ``data_off + 4*npts == len(raw)`` for *any* data_off, so the offset
    # is only trusted when it is also >= the minimum header length (968).
    # Otherwise fall back to the standard 968 offset and read whatever
    # points remain (defensive truncation handling).
    data_off = len(raw) - 4 * npts
    if data_off < DATA_OFFSET or data_off + 4 * npts != len(raw):
        data_off = DATA_OFFSET
    if data_off < 0 or data_off + 4 * npts > len(raw):
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
