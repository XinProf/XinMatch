"""Readers for Bruker RAW v3 / v4 binary diffraction files (T2.4).

The Bruker ``.raw`` family has four documented versions, distinguished by
the first bytes of the file:

* ``RAW ``  (ver. 1) — pre-versioned legacy container; **no public format
  documentation exists and reference implementations (GSAS-II) explicitly
  refuse it**, so it is intentionally not implemented here.
* ``RAW2``  (ver. 2) — fixed-header container, implemented in
  :mod:`xinmatch.core.io.rigaku` (``read_raw2``).
* ``RAW1.01`` (ver. 3) — fixed-header multi-block container (this module).
* ``RAW4.00`` (ver. 4) — segmented container with typed metadata blocks
  (this module; only the first powder-data bank is returned).

Layout facts are documented in the Bruker GADDS reference manual and are
independently documented by the GSAS-II project (BSD-3-Clause,
``GSASII/imports/G2pwd_BrukerRAW``); this implementation was written from
those public layout descriptions, verified against a real RAW1.01 file
(hard-metal WC residual-stress scan, 10 blocks × 147 points, 57.75–62.13°,
full file consumed exactly).
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

import numpy as np

from xinmatch.core.model import Pattern

__all__ = ["read_bruker_raw_v3", "read_bruker_raw_v4"]

_MAGIC_V3 = b"RAW1.01"
_MAGIC_V4 = b"RAW4.00"

#: Wavelengths by anode name (Å), fallback when a v3 file has no metadata.
_ANODE_WAVELENGTH: dict[str, float] = {
    "CU": 1.5406,
    "CO": 1.7902,
    "FE": 1.9374,
    "CR": 2.2910,
    "MO": 0.7107,
    "AG": 0.5609,
}

#: Scan types that carry powder data in a v4 file.
_V4_SCAN_TYPES = ("Locked Coupled", "Unlocked Coupled", "Detector Scan")


def _anode_wavelength(anode: str) -> float:
    return _ANODE_WAVELENGTH.get(anode.strip().upper(), 1.5406)


def read_bruker_raw_v3(
    path: str | Path, *, block: int = 0
) -> Pattern:
    """Read a Bruker RAW ver. 3 (``RAW1.01``) powder file.

    Parameters
    ----------
    path:
        Path to the ``.raw`` file.
    block:
        Which scan block to return (0-based).  Multi-block files are
        typically stress / texture series where every block shares the
        same angular range; block 0 is the default.

    Returns
    -------
    Pattern
        Pattern with two_theta / intensity arrays, Cu Kα1 wavelength by
        default (or the anode wavelength stored in the file), and metadata
        carrying the parsed header fields.

    Raises
    ------
    ValueError
        If the file is not a RAW1.01 container, or *block* is out of range.
    """
    p = Path(path)
    raw = p.read_bytes()
    if not raw.startswith(_MAGIC_V3):
        raise ValueError(f"Not a Bruker RAW ver. 3 file: {p}")

    n_block = struct.unpack("<i", raw[12:16])[0]
    if not 0 <= block < n_block:
        raise ValueError(
            f"block {block} out of range (file has {n_block} blocks)"
        )

    # Fixed metadata (offsets from the GADDS / GSAS-II documentation).
    radius = struct.unpack("<f", raw[564:568])[0]
    anode = raw[608:612].decode("latin-1", errors="replace").strip("\x00")
    ka_mean, ka1, ka2, kb, ka2_ka1 = struct.unpack("<5d", raw[616:656])

    pos = 712
    for _ in range(block):
        head_len = struct.unpack("<i", raw[pos : pos + 4])[0]
        n_steps = struct.unpack("<i", raw[pos + 4 : pos + 8])[0]
        if n_block > 1:
            head_len += struct.unpack("<i", raw[pos + 256 : pos + 260])[0]
        else:
            head_len += 40
        pos += head_len + 4 * n_steps

    head_len = struct.unpack("<i", raw[pos : pos + 4])[0]
    n_steps = struct.unpack("<i", raw[pos + 4 : pos + 8])[0]
    if n_block > 1:
        head_len += struct.unpack("<i", raw[pos + 256 : pos + 260])[0]
    else:
        head_len += 40

    start2th = struct.unpack("<d", raw[pos + 8 : pos + 16])[0]
    step = struct.unpack("<d", raw[pos + 176 : pos + 184])[0]
    if n_steps <= 0 or step <= 0:
        raise ValueError(f"Unusable axis in RAW v3 block {block}: {p}")

    data_off = pos + head_len
    y = np.frombuffer(raw[data_off : data_off + 4 * n_steps], dtype="<f4")
    if len(y) != n_steps:
        raise ValueError(
            f"RAW v3 block {block} truncated: {len(y)} of {n_steps} points"
        )
    y = y.astype(np.float64)
    x = start2th + step * np.arange(n_steps)

    return Pattern(
        two_theta=x,
        intensity=y,
        wavelength=_anode_wavelength(anode),
        step=float(step),
        metadata={
            "format": "raw3",
            "bruker_raw_version": 3,
            "block": block,
            "n_blocks": n_block,
            "anode": anode,
            "ka1_angstrom": float(ka1),
            "ka2_angstrom": float(ka2),
            "ka2_ka1_ratio": float(ka2_ka1),
            "kb_angstrom": float(kb),
            "ka_mean_angstrom": float(ka_mean),
            "gonio_radius_mm": float(radius),
        },
    )


def read_bruker_raw_v4(path: str | Path) -> Pattern:
    """Read a Bruker RAW ver. 4 (``RAW4.00``) powder file.

    v4 is the segmented container used by current Bruker D8-class
    instruments.  A file may hold several banks; this reader returns the
    **first** powder-data bank (``Locked Coupled`` / ``Unlocked Coupled`` /
    ``Detector Scan``), matching the single-pattern semantics of
    :func:`load_pattern`.

    Returns
    -------
    Pattern
        Pattern with two_theta / intensity, wavelength from the file's
        ``usedWave`` (or anode-based fallback), and header metadata.

    Raises
    ------
    ValueError
        If the file is not a RAW4.00 container or contains no readable
        powder-data bank.
    """
    p = Path(path)
    raw = p.read_bytes()
    if not raw.startswith(_MAGIC_V4):
        raise ValueError(f"Not a Bruker RAW ver. 4 file: {p}")

    date = raw[12:24].decode("latin-1", errors="replace").strip("\x00")
    time_ = raw[24:34].decode("latin-1", errors="replace").strip("\x00")

    meta: dict[str, Any] = {
        "format": "raw4",
        "bruker_raw_version": 4,
        "date": date,
        "time": time_,
    }

    pos = 61
    anode = ""
    ka1 = ka2 = ka_mean = 0.0
    used_wave = 0.0
    while pos < len(raw):
        if pos + 8 > len(raw):
            break
        seg_type, seg_len = struct.unpack("<II", raw[pos : pos + 8])
        seg_len = max(seg_len, 8)
        body = pos + 8

        if seg_type == 0 or seg_type == 160:
            # --- powder data bank -------------------------------------
            if body + 28 > len(raw):
                break
            scan_type = raw[body + 28 : body + 52].decode(
                "latin-1", errors="replace"
            ).strip("\x00")
            if scan_type not in _V4_SCAN_TYPES:
                pos = body + seg_len
                continue
            start_angle = struct.unpack("<d", raw[body + 68 : body + 76])[0]
            step_size = struct.unpack("<d", raw[body + 76 : body + 84])[0]
            n_steps = struct.unpack("<I", raw[body + 84 : body + 88])[0]
            step_time_ms = struct.unpack("<f", raw[body + 88 : body + 92])[0]
            kv = struct.unpack("<f", raw[body + 96 : body + 100])[0]
            ma = struct.unpack("<f", raw[body + 100 : body + 104])[0]
            used_wave = struct.unpack("<d", raw[body + 108 : body + 116])[0]
            datum_size = struct.unpack("<I", raw[body + 132 : body + 136])[0]
            hdr_size = struct.unpack("<I", raw[body + 136 : body + 140])[0]
            if n_steps <= 0 or step_size <= 0:
                raise ValueError(f"Unusable axis in RAW v4 bank: {p}")
            data_off = body + 156 + hdr_size
            y = np.frombuffer(
                raw[data_off : data_off + datum_size * n_steps],
                dtype="<f4",
            )
            if len(y) < n_steps:
                raise ValueError(
                    f"RAW v4 bank truncated: {len(y)} of {n_steps} points"
                )
            y = y[:n_steps].astype(np.float64)
            x = start_angle + step_size * np.arange(n_steps)
            meta.update(
                {
                    "scan_type": scan_type,
                    "start_angle": float(start_angle),
                    "step_size": float(step_size),
                    "n_steps": int(n_steps),
                    "step_time_ms": float(step_time_ms),
                    "generator_kv": float(kv),
                    "generator_ma": float(ma),
                    "used_wave_angstrom": float(used_wave),
                }
            )
            wave = used_wave if used_wave > 0 else _anode_wavelength(anode)
            return Pattern(
                two_theta=x,
                intensity=y,
                wavelength=float(wave),
                step=float(step_size),
                metadata=meta,
            )

        if seg_type == 10:
            # text metadata pair
            name = raw[body + 8 : body + 32].decode(
                "latin-1", errors="replace"
            ).strip("\x00")
            value = raw[body + 36 : body + seg_len].decode(
                "latin-1", errors="replace"
            ).strip("\x00")
            if name and value:
                meta[f"meta_{name}"] = value
        elif seg_type == 30:
            # X-ray source info
            ka_mean = struct.unpack("<d", raw[body + 64 : body + 72])[0]
            ka1 = struct.unpack("<d", raw[body + 72 : body + 80])[0]
            ka2 = struct.unpack("<d", raw[body + 80 : body + 88])[0]
            anode = raw[body + 96 : body + 100].decode(
                "latin-1", errors="replace"
            ).strip("\x00")
            meta["ka_mean_angstrom"] = float(ka_mean)
            meta["ka1_angstrom"] = float(ka1)
            meta["ka2_angstrom"] = float(ka2)
        # segtype 60 (drive info) and others: skip payload
        pos = body + seg_len

    raise ValueError(f"No readable powder-data bank in RAW v4 file: {p}")
