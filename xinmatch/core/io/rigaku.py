"""Readers for Rigaku and RAW2 binary diffraction data.

Implements:

* :func:`read_raw2` — RAW2 fixed-header container (``RAW2`` magic).
  A short binary header holds the 2θ axis (start/step) and point count;
  intensities follow as little-endian float32.  This is the format used by
  the IUCr round-robin sample set (``*.raw`` files converted from UXD).
* :func:`read_rigaku_raw` — Rigaku RINT-2000 binary (``FI\\x00\\x00``
  magic).  The 2θ axis (start/end/step) is stored as three consecutive
  little-endian float32 at offset ``0xB92``; intensities are the trailing
  ``n`` little-endian float32 values, ``n = round((end-start)/step)``.

Both parsers mirror the byte layout that has been verified against real
instrument files (IUCr CPD-* / csuHJW teaching set).  Wavelength defaults
to Cu Kα and is refined from a target token in the header text when a
recognised element appears.
"""

from __future__ import annotations

import math
import struct
from pathlib import Path

import numpy as np

from xinmatch.core.model import Pattern

MAGIC_RAW2 = b"RAW2"
MAGIC_RIGAKU = b"FI\x00\x00"

#: Target element -> Kα wavelength (Å).  The binary/header keeps only a
#: short token such as "Cu"/"Co"; matching it is more reliable than
#: guessing 1.54 among the raw numeric fields.
_ANODE_WAVELENGTHS: dict[str, float] = {
    "CU": 1.5406,
    "CO": 1.78897,
    "CR": 2.28970,
    "FE": 1.93604,
    "MN": 2.10314,
    "NI": 1.65791,
    "MO": 0.70930,
    "AG": 0.55941,
}


def wavelength_from_anode(text: str) -> float | None:
    """Return the Kα wavelength for the first target token found in *text*."""
    upper = text.upper()
    for symbol, wl in _ANODE_WAVELENGTHS.items():
        if symbol in upper:
            return wl
    return None


def _printable(raw: bytes, limit: int) -> str:
    return "".join(chr(b) if 32 <= b < 127 else "" for b in raw[:limit])


# ---------------------------------------------------------------------------
# RAW2
# ---------------------------------------------------------------------------
# Fixed offsets (verified on the IUCr round-robin .raw files):
_RAW2_COUNT_OFF = 0x102   # int16 LE: point count
_RAW2_STEP_OFF = 0x10C    # float32 LE: step (°)
_RAW2_START_OFF = 0x110   # float32 LE: start 2θ (°)
_RAW2_HDR_LEN = 316       # fallback header length when count is unusable


def read_raw2(path: str | Path) -> Pattern:
    """Read a RAW2 fixed-header binary file.

    The point count is read from offset ``0x102`` (int16) and validated
    against the file size; when it is implausible the header length is
    assumed to be 316 bytes.  The 2θ axis comes from the float32 start/step
    fields at ``0x110``/``0x10C``.

    Parameters
    ----------
    path:
        Path to the ``.raw`` file.

    Returns
    -------
    Pattern
        Parsed diffraction pattern.
    """
    p = Path(path)
    raw = p.read_bytes()

    if not raw.startswith(MAGIC_RAW2):
        raise ValueError(f"Not a RAW2 binary file: {p}")

    offset = None
    n = 0
    if len(raw) >= _RAW2_COUNT_OFF + 2:
        n_hdr = struct.unpack_from("<h", raw, _RAW2_COUNT_OFF)[0]
        cand = len(raw) - n_hdr * 4
        # header length must land in a plausible range, else this int16 is
        # not the point count
        if n_hdr >= 16 and 64 <= cand <= 4096:
            offset, n = cand, n_hdr
    if offset is None:
        offset = _RAW2_HDR_LEN
        n = (len(raw) - offset) // 4
    if n < 2:
        raise ValueError(f"RAW2 file data segment too short: {p}")

    start, step = _raw2_axis(raw)
    if start is None:
        raise ValueError(f"RAW2 header has no trustworthy start/step: {p}")

    intensity = np.frombuffer(
        raw[offset : offset + n * 4], dtype="<f4"
    ).astype(np.float64)
    two_theta = start + step * np.arange(n, dtype=np.float64)

    metadata: dict = {"format": "raw2", "vendor": "RAW2", "header_len": offset}
    wl = wavelength_from_anode(_printable(raw, offset))
    if wl is not None:
        metadata["wavelength"] = wl
        metadata["target"] = _printable(raw, offset).strip().split()[-1][:8]

    return Pattern(
        two_theta=two_theta,
        intensity=intensity,
        wavelength=float(wl) if wl else 1.5406,
        step=float(step),
        metadata=metadata,
    )


def _raw2_axis(raw: bytes) -> tuple[float | None, float | None]:
    """Return the RAW2 ``(start, step)``.

    Fixed offsets are preferred; if they fail, adjacent float32 pairs in the
    header are scanned for a step-like value followed by a start-like value.
    """
    def _f(off: int) -> float | None:
        try:
            return struct.unpack_from("<f", raw, off)[0]
        except struct.error:
            return None

    step = _f(_RAW2_STEP_OFF)
    start = _f(_RAW2_START_OFF)
    ok = (
        step is not None
        and start is not None
        and math.isfinite(step)
        and math.isfinite(start)
        and 0.0 < step <= 1.0
        and 0.0 <= start < 180.0
    )
    if not ok:
        step = start = None
        for off in range(64, max(72, min(len(raw) - 8, 4096)), 4):
            s, t = _f(off), _f(off + 4)
            if s is None or t is None:
                continue
            if not (math.isfinite(s) and math.isfinite(t)):
                continue
            # the step must look like a step (excludes stray floats such as
            # 0.000169 in the header)
            if 0.001 <= s <= 0.5 and 0.1 <= t < 90.0:
                step, start = s, t
                break
    if step is None:
        return None, None
    # The header stores start/step as float32: 0.02 becomes
    # 0.019999999552965164, which drifts by up to ~3e-6° over thousands of
    # points (150.000 reads as 149.999997).  Normalise to 8 significant
    # digits: removes float32 noise while keeping genuine sub-degree steps.
    return float(f"{start:.8g}"), float(f"{step:.8g}")


# ---------------------------------------------------------------------------
# Rigaku RINT-2000
# ---------------------------------------------------------------------------
# Verified structure (csuHJW teaching set, consistent across Rigaku RINT
# instruments):
#   - 0x000 : 4-byte magic b"FI\x00\x00"
#   - 0xB92 (2962): three consecutive little-endian float32 =
#     (start 2θ, end 2θ, step)
#   - data: trailing n little-endian float32 intensities,
#     n = round((end - start) / step); i.e. a fixed 3162-byte header plus a
#     variable float32 intensity block.  The header carries no explicit
#     wavelength (defaults to Cu Kα).
_RIGAKU_AXIS_OFF = 0xB92      # 2962: start, end, step (3 × float32)
_RIGAKU_HDR_FIXED = 0xC5A     # 3162: degenerate fallback header length


def read_rigaku_raw(path: str | Path) -> Pattern:
    """Read a Rigaku RINT-2000 binary ``.raw`` (``FI\\x00\\x00`` magic).

    Parameters
    ----------
    path:
        Path to the ``.raw`` file.

    Returns
    -------
    Pattern
        Parsed diffraction pattern.
    """
    p = Path(path)
    raw = p.read_bytes()

    if not raw.startswith(MAGIC_RIGAKU):
        raise ValueError(f"Not a Rigaku RINT-2000 binary file: {p}")

    if len(raw) < _RIGAKU_AXIS_OFF + 12:
        raise ValueError(f"Rigaku RAW file too short for axis: {p}")
    start = struct.unpack_from("<f", raw, _RIGAKU_AXIS_OFF)[0]
    end = struct.unpack_from("<f", raw, _RIGAKU_AXIS_OFF + 4)[0]
    step = struct.unpack_from("<f", raw, _RIGAKU_AXIS_OFF + 8)[0]
    if not (0.0 < step <= 2.0 and 0.0 <= start < end < 180.0):
        raise ValueError(
            f"Rigaku RAW axis invalid (start={start}, end={end}, "
            f"step={step}): {p}"
        )
    # normalise float32 noise (0.02 reads as 0.019999999552965164)
    start = float(f"{start:.8g}")
    end = float(f"{end:.8g}")
    step = float(f"{step:.8g}")
    n = int(round((end - start) / step))
    if n < 2:
        raise ValueError(f"Rigaku RAW point count invalid (n={n}): {p}")

    # data = trailing n float32 values; fall back to the fixed header length
    offset = len(raw) - n * 4
    if offset < 0 or offset + n * 4 > len(raw) or offset & 3:
        offset = _RIGAKU_HDR_FIXED
        n = (len(raw) - offset) // 4
    if n < 2:
        raise ValueError(f"Rigaku RAW data segment too short: {p}")

    intensity = np.frombuffer(
        raw[offset : offset + n * 4], dtype="<f4"
    ).astype(np.float64)
    two_theta = start + step * np.arange(n, dtype=np.float64)

    metadata: dict = {
        "format": "rigaku_raw",
        "vendor": "Rigaku",
        "header_len": offset,
    }
    wl = wavelength_from_anode(_printable(raw, offset))
    if wl is not None:
        metadata["wavelength"] = wl

    return Pattern(
        two_theta=two_theta,
        intensity=intensity,
        wavelength=float(wl) if wl else 1.5406,
        step=float(step),
        metadata=metadata,
    )
