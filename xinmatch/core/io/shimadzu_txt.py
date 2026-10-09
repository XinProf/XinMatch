"""Reader for Shimadzu XRD instrument ASCII export (``.txt``/``.smz``).

Shimadzu instrument exports carry a metadata header — ``target``,
``voltage``, ``current``, ``scan range``, ``sampling pitch``/``sampling
interval``, ``preset time``, ``wavelength``, ``tube`` — followed by
``<2Theta>``/``<Intensity>`` columns.  The header is parsed into the
pattern metadata and the radiation wavelength is resolved from the target
token (the column captions themselves are skipped).
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from xinmatch.core.model import Pattern

_HEADER_PATTERNS: dict[str, str] = {
    "target": r"target\s*[:=]\s*(\S+)",
    "voltage": r"voltage\s*[:=]\s*([\d.]+)",
    "current": r"current\s*[:=]\s*([\d.]+)",
    "scan_start": r"scan range\s*[:=]\s*([\d.]+)",
    "scan_end": r"scan range\s*[:=]\s*[\d.]+\s*-\s*([\d.]+)",
    "scan_speed": r"scan speed\s*[:=]\s*([\d.]+)",
    "sampling_pitch": r"(?:sampling\s+pitch|sampling interval)\s*[:=]\s*([\d.]+)",
    "preset_time": r"(?:preset\s+time|counting time)\s*[:=]\s*([\d.]+)",
    "wavelength": r"wavelength\s*[:=]\s*([\d.]+)",
    "tube": r"tube\s*[:=]\s*(\S+)",
}

_TARGET_WAVELENGTH: dict[str, float] = {
    "CU": 1.5406,
    "FE": 1.9373,
    "CO": 1.7903,
    "NI": 1.6516,
    "MO": 0.7107,
    "AG": 0.5608,
    "AL": 1.4398,
}


def is_shimadzu_txt(text: str) -> bool:
    """Return ``True`` when the text looks like a Shimadzu instrument export."""
    head = text[:8192].lower()
    return ("target" in head and "voltage" in head) or "<2theta>" in head


def read_shimadzu_txt(path: str | Path) -> Pattern:
    """Read a Shimadzu XRD ASCII export.

    Parameters
    ----------
    path:
        Path to the ``.txt`` / ``.smz`` file.

    Returns
    -------
    Pattern
        Parsed diffraction pattern with radiation metadata.

    Raises
    ------
    ValueError
        If no two-column data rows are found.
    """
    p = Path(path)
    content = p.read_text(encoding="utf-8-sig", errors="ignore")

    metadata: dict = {"format": "shimadzu_txt", "vendor": "Shimadzu"}
    for key, pattern in _HEADER_PATTERNS.items():
        m = re.search(pattern, content, re.IGNORECASE)
        if m:
            try:
                metadata[key] = float(m.group(1))
            except ValueError:
                metadata[key] = m.group(1)

    target = str(metadata.get("target", "")).replace("-", "").replace(" ", "").upper()
    wavelength = 1.5406
    resolved_by = None
    for symbol, wl in _TARGET_WAVELENGTH.items():
        if symbol in target:
            wavelength = wl
            resolved_by = f"target:{symbol}"
            break
    if resolved_by is None and isinstance(metadata.get("wavelength"), float):
        wavelength = metadata["wavelength"]
        resolved_by = "header"
    if resolved_by is not None:
        metadata["wavelength_source"] = resolved_by

    data: list[tuple[float, float]] = []
    in_data = False
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "%", "//", ";", "!")):
            continue
        if "<" in stripped and ">" in stripped:
            in_data = True
            continue
        parts = stripped.split()
        if len(parts) < 2:
            continue
        try:
            x, y = float(parts[0]), float(parts[1])
        except ValueError:
            continue
        if in_data or len(data) < 1:
            data.append((x, y))
        else:
            # tolerate a header line carrying numbers before the columns
            data.append((x, y))

    if len(data) < 2:
        raise ValueError(f"Shimadzu text file has no data rows: {p}")

    two_theta = np.asarray([d[0] for d in data], dtype=np.float64)
    intensity = np.asarray([d[1] for d in data], dtype=np.float64)
    step = float(two_theta[1] - two_theta[0]) if len(two_theta) > 1 else 0.0

    return Pattern(
        two_theta=two_theta,
        intensity=intensity,
        wavelength=wavelength,
        step=step,
        metadata=metadata,
    )
