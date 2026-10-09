"""Reader for Shimadzu XRD binary ``.raw`` files.

The format is a fixed-layout binary container written by Shimadzu XRD
software (``Ver 0.00`` block).  Layout (all integers little-endian):

============  =======  =============================================
offset        type     meaning
============  =======  =============================================
0x000–0x05F   ASCII    header text: ``Shimadzu XRD`` magic, version,
                       sample label, target element ("Cu" etc.)
0x12C (300)   int32    2θ start  × 10_000
0x130 (304)   int32    2θ end    × 10_000
0x134 (308)   int32    step      × 10_000
0x144 (324)   float32  preset time (s/point)
0x15C (348)   float32  receiving slit (mm)
0x270 (624)   int32    declared point count
0x278 (632)   int32    maximum intensity (mirrors data max)
0x3C8 (968)   int32[]  intensities (``npts`` little-endian int32)
============  =======  =============================================

The 2θ grid is ``start + step * arange(npts)``; the data block always
begins at offset 968 and spans ``npts * 4`` bytes to the end of file.
Wavelength defaults to Cu Kα (1.5406 Å) and is refined from the target
token in the header text when a recognised element appears.

Truncated files (declared ``npts`` larger than the remaining bytes) are
read defensively: the available points are returned and the truncation
is recorded in ``metadata["truncated"]``.
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
DATA_OFFSET = 968

OFF_START = 300   # int32, 2θ start × 1e4
OFF_END = 304     # int32, 2θ end × 1e4
OFF_STEP = 308    # int32, step × 1e4
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


def _header_text(raw: bytes) -> str:
    """Extract printable header text (ASCII range) up to the data block."""
    return "".join(chr(b) if 32 <= b < 127 else "" for b in raw[:DATA_OFFSET])


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


def read_shimadzu_raw(path: str | Path) -> Pattern:
    """Read a Shimadzu XRD binary ``.raw`` file.

    Parameters
    ----------
    path:
        Path to the ``.raw`` file.

    Returns
    -------
    Pattern
        Parsed diffraction pattern with a uniform 2θ axis.

    Raises
    ------
    ValueError
        If the file is not a Shimadzu ``.raw`` container, or the header
        axis/point-count fields are inconsistent.
    """
    p = Path(path)
    raw = p.read_bytes()

    if not is_shimadzu_raw(raw):
        raise ValueError(f"Not a Shimadzu XRD .raw file: {p}")

    if len(raw) < DATA_OFFSET + 4:
        raise ValueError(f"Shimadzu .raw file too short: {p}")

    start = _i32(raw, OFF_START) / _SCALE
    end = _i32(raw, OFF_END) / _SCALE
    step = _i32(raw, OFF_STEP) / _SCALE
    npts = _i32(raw, OFF_NPTS)

    # -- header sanity ---------------------------------------------------
    if not (0.0 <= start < end <= 180.0):
        raise ValueError(f"Shimadzu .raw has invalid 2θ range ({start}, {end}): {p}")
    if not (0.0 < step <= 10.0):
        raise ValueError(f"Shimadzu .raw has invalid step {step}: {p}")
    if npts <= 0:
        raise ValueError(f"Shimadzu .raw has invalid point count {npts}: {p}")

    # -- data block (defensive against truncated files) ------------------
    avail = (len(raw) - DATA_OFFSET) // 4
    n_read = min(npts, max(avail, 0))
    if n_read <= 0:
        raise ValueError(f"Shimadzu .raw has no intensity data: {p}")

    try:
        intensities = np.asarray(
            struct.unpack(f"<{n_read}i", raw[DATA_OFFSET : DATA_OFFSET + n_read * 4]),
            dtype=np.float64,
        )
    except struct.error as exc:  # pragma: no cover - guarded by n_read
        raise ValueError(f"Shimadzu .raw data block unreadable: {p}") from exc

    truncated = n_read < npts
    two_theta = start + step * np.arange(n_read, dtype=np.float64)

    header = _header_text(raw)
    wavelength, target_name = _target_wavelength(header)

    metadata: dict = {
        "format": "shimadzu_raw",
        "vendor": "Shimadzu",
        "target": target_name,
        "scan_start_deg": float(start),
        "scan_end_deg": float(end),
        "npts_declared": int(npts),
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
