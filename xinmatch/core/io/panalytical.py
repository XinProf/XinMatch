"""Readers for PANalytical/Philips diffraction data formats.

Implements readers for three text-based PANalytical/Philips formats:

* :func:`read_rd` — Philips/PANalytical raw data (``*.rd``).  A keyword
  header (lines prefixed with ``*``) describing the scan, followed by a
  ``*DATA`` block of intensities.
* :func:`read_udf` — PANalytical Universal Data Format (``*.udf``).  An
  INI-style text container with ``[Header]`` and ``[Intensities]``
  sections.
* :func:`read_udi` — PANalytical peak data (``*.udi``).  INI-style with a
  ``[Peaks]`` section of ``2theta intensity`` pairs.

These are clean-room implementations based on publicly documented format
conventions; proprietary binary variants are not handled.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import numpy as np

from xinmatch.core.model import Pattern


def _read_text(path: str | Path) -> str:
    """Read a text file, UTF-8 with latin-1 fallback."""
    p = Path(path)
    raw = p.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _parse_numbers(line: str) -> list[float]:
    """Parse all floats from a line (whitespace/comma/tab separated)."""
    tokens = line.replace(",", " ").replace("\t", " ").split()
    vals: list[float] = []
    for t in tokens:
        with contextlib.suppress(ValueError):
            vals.append(float(t))
    return vals


# ---------------------------------------------------------------------------
# .rd  —  Philips/PANalytical raw text
# ---------------------------------------------------------------------------
def read_rd(path: str | Path) -> Pattern:
    """Read a Philips/PANalytical ``.rd`` raw-data file.

    The file consists of ``*KEYWORD value`` header lines and a ``*DATA``
    section with one intensity per line (or whitespace-separated).
    Recognised keywords: ``START``, ``STEP``, ``STEPS`` (point count),
    ``END``, ``WAVELENGTH``.

    Parameters
    ----------
    path:
        Path to the ``.rd`` file.

    Returns
    -------
    Pattern
        Parsed diffraction pattern.
    """
    text = _read_text(path)
    lines = text.splitlines()

    start: float | None = None
    step: float | None = None
    steps: int | None = None
    end: float | None = None
    wavelength = 1.5406
    in_data = False
    intensities: list[float] = []

    for raw in lines:
        ln = raw.strip()
        if not ln:
            continue
        if in_data:
            intensities.extend(_parse_numbers(ln))
            continue
        if not ln.startswith("*"):
            continue
        # Keyword line: *KEY [value...]
        parts = ln[1:].split(None, 1)
        key = parts[0].upper()
        rest = parts[1] if len(parts) > 1 else ""
        if key == "DATA":
            in_data = True
            continue
        nums = _parse_numbers(rest)
        if key == "START" and nums:
            start = nums[0]
        elif key == "STEP" and nums:
            step = nums[0]
        elif key == "STEPS" and nums:
            steps = int(nums[0])
        elif key == "END" and nums:
            end = nums[0]
        elif key == "WAVELENGTH" and nums:
            wavelength = nums[0]

    if start is None or step is None:
        raise ValueError(f".rd file missing START/STEP keywords: {path}")

    if not intensities:
        raise ValueError(f".rd file has no DATA section: {path}")

    n = len(intensities)
    two_theta = start + step * np.arange(n, dtype=np.float64)

    metadata: dict = {
        "format": "rd",
        "vendor": "PANalytical/Philips",
    }
    if end is not None:
        metadata["end_two_theta"] = float(end)
    if steps is not None:
        metadata["declared_steps"] = steps

    return Pattern(
        two_theta=two_theta,
        intensity=np.asarray(intensities, dtype=np.float64),
        wavelength=float(wavelength),
        step=float(step),
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# .udf  —  PANalytical Universal Data Format (INI-style text)
# ---------------------------------------------------------------------------
def _parse_ini_sections(text: str) -> dict[str, list[str]]:
    """Parse a simple INI-style text into ``{section: [lines]}``."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        ln = raw.strip()
        if not ln or ln.startswith(("#", ";")):
            continue
        if ln.startswith("[") and ln.endswith("]"):
            current = ln[1:-1].strip().lower()
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(ln)
    return sections


def read_udf(path: str | Path) -> Pattern:
    """Read a PANalytical ``.udf`` (Universal Data Format) text file.

    INI-style layout::

        [Header]
        Wavelength = 1.5406
        Start = 5.0
        Step = 0.02
        End = 90.0
        [Intensities]
        100.0
        200.0
        ...

    Parameters
    ----------
    path:
        Path to the ``.udf`` file.

    Returns
    -------
    Pattern
        Parsed diffraction pattern.
    """
    text = _read_text(path)
    sections = _parse_ini_sections(text)

    header: dict[str, str] = {}
    for line in sections.get("header", []):
        key, _, val = line.partition("=")
        if key:
            header[key.strip().lower()] = val.strip()

    try:
        start = float(header.get("start", "nan"))
        step = float(header.get("step", "nan"))
    except ValueError as exc:
        raise ValueError(f".udf header missing Start/Step: {path}") from exc
    if np.isnan(start) or np.isnan(step):
        raise ValueError(f".udf header missing Start/Step: {path}")

    wavelength = float(header.get("wavelength", "1.5406"))
    end = header.get("end")
    end_val = float(end) if end else None

    intensities: list[float] = []
    for ln in sections.get("intensities", []):
        intensities.extend(_parse_numbers(ln))

    if not intensities:
        raise ValueError(f".udf file has no [Intensities] data: {path}")

    n = len(intensities)
    two_theta = start + step * np.arange(n, dtype=np.float64)

    metadata: dict = {"format": "udf", "vendor": "PANalytical"}
    if end_val is not None:
        metadata["end_two_theta"] = end_val

    return Pattern(
        two_theta=two_theta,
        intensity=np.asarray(intensities, dtype=np.float64),
        wavelength=wavelength,
        step=float(step),
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# .udi  —  PANalytical peak data
# ---------------------------------------------------------------------------
def read_udi(path: str | Path) -> Pattern:
    """Read a PANalytical ``.udi`` peak-data file.

    INI-style layout with a ``[Peaks]`` section of ``2theta intensity``
    pairs::

        [Header]
        Wavelength = 1.5406
        [Peaks]
        10.0 100.0
        20.0 200.0

    Parameters
    ----------
    path:
        Path to the ``.udi`` file.

    Returns
    -------
    Pattern
        Parsed peak list as a pattern.
    """
    text = _read_text(path)
    sections = _parse_ini_sections(text)

    header: dict[str, str] = {}
    for line in sections.get("header", []):
        key, _, val = line.partition("=")
        if key:
            header[key.strip().lower()] = val.strip()
    wavelength = float(header.get("wavelength", "1.5406"))

    positions: list[float] = []
    intensities: list[float] = []
    for ln in sections.get("peaks", []):
        vals = _parse_numbers(ln)
        if len(vals) >= 2:
            positions.append(vals[0])
            intensities.append(vals[1])

    if not positions:
        raise ValueError(f".udi file has no [Peaks] data: {path}")

    return Pattern(
        two_theta=np.asarray(positions, dtype=np.float64),
        intensity=np.asarray(intensities, dtype=np.float64),
        wavelength=wavelength,
        step=None,
        metadata={"format": "udi", "vendor": "PANalytical", "kind": "peaklist"},
    )
