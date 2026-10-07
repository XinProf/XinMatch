"""Readers for the "free" (vendor-neutral) diffraction data formats.

These are the ASCII formats Match! can import regardless of instrument
vendor, documented in Match!'s *Diffraction Data File Formats* help page.

Implemented readers:

* :func:`read_dbws` — DBWS raw data (``*.rfl``, ``*.dat``).
* :func:`read_ascii_profile_3col` — ASCII profile ``start, step, end``
  followed by intensities.
* :func:`read_ascii_profile_2col_header` — ASCII profile ``start, step``
  followed by intensities (no end value).
* :func:`read_ascii_profile_2col` — two-column ``2theta/d, intensity``
  (space / comma / tab separated, comment lines ignored).
* :func:`read_endeavour` — ENDEAVOUR peak list (``*.dif``).

All readers return a :class:`xinmatch.core.model.Pattern`.  2θ is in degrees,
intensities are ``numpy.float64``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from xinmatch.core.model import Pattern


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _read_text(path: str | Path) -> str:
    """Read a text file, sniffing UTF-8 then falling back to latin-1."""
    p = Path(path)
    raw = p.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _parse_numbers(line: str) -> list[float]:
    """Parse floats from a line, skipping non-numeric tokens.

    Whitespace, commas, and tabs are treated as separators.  Tokens that
    cannot be parsed as floats are ignored (useful for trailing titles in
    DBWS headers).
    """
    tokens = line.replace(",", " ").replace("\t", " ").split()
    vals: list[float] = []
    for t in tokens:
        try:
            vals.append(float(t))
        except ValueError:
            continue
    return vals


def _iter_data_lines(text: str) -> list[str]:
    """Return non-empty, non-comment lines."""
    out: list[str] = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith(("#", "!", ";", "//")):
            continue
        out.append(s)
    return out


def _build_two_theta(start: float, step: float, n: int) -> np.ndarray:
    """Build an evenly spaced 2θ grid from start/step/count."""
    return start + step * np.arange(n, dtype=np.float64)


# ---------------------------------------------------------------------------
# DBWS
# ---------------------------------------------------------------------------
def read_dbws(path: str | Path) -> Pattern:
    """Read a DBWS raw-data file (``*.rfl``, ``*.dat``).

    Match! DBWS format: the first line holds ``2theta_start, step,
    2theta_end`` and an optional title.  Subsequent lines contain intensity
    values in Fortran ``8F7.0`` style (8 values per line, 7-char fields).

    Parameters
    ----------
    path:
        Path to the ``.rfl`` / ``.dat`` file.

    Returns
    -------
    Pattern
        Parsed diffraction pattern.  ``step`` is set to the scan step.
    """
    text = _read_text(path)
    lines = _iter_data_lines(text)
    if len(lines) < 1:
        raise ValueError(f"Empty DBWS file: {path}")

    first = lines[0]
    vals = _parse_numbers(first)
    if len(vals) < 3:
        raise ValueError(
            f"DBWS first line must contain start, step, end (got: {first!r})"
        )
    start, step, end = vals[0], vals[1], vals[2]

    intensities: list[float] = []
    for ln in lines[1:]:
        intensities.extend(_parse_numbers(ln))

    n = len(intensities)
    if n == 0:
        raise ValueError(f"DBWS file contains no intensity data: {path}")

    two_theta = _build_two_theta(start, step, n)
    return Pattern(
        two_theta=two_theta,
        intensity=np.asarray(intensities, dtype=np.float64),
        step=float(step),
        metadata={"format": "dbws", "end_two_theta": float(end)},
    )


# ---------------------------------------------------------------------------
# ASCII profile variants
# ---------------------------------------------------------------------------
def read_ascii_profile_3col(path: str | Path) -> Pattern:
    """Read an ASCII profile with ``start, step, end`` header.

    First line: ``2theta_start, step, 2theta_end``.  Following lines:
    intensity values (any number per line).

    Parameters
    ----------
    path:
        Path to the ``.dat`` file.

    Returns
    -------
    Pattern
        Parsed pattern.  The 2θ array is built from start/step; the ``end``
        value is stored in metadata.
    """
    text = _read_text(path)
    lines = _iter_data_lines(text)
    if len(lines) < 1:
        raise ValueError(f"Empty ASCII 3-col file: {path}")

    vals = _parse_numbers(lines[0])
    if len(vals) < 3:
        raise ValueError(
            f"ASCII 3-col first line must be start, step, end (got: {lines[0]!r})"
        )
    start, step, end = vals[0], vals[1], vals[2]

    intensities: list[float] = []
    for ln in lines[1:]:
        intensities.extend(_parse_numbers(ln))

    n = len(intensities)
    if n == 0:
        raise ValueError(f"ASCII 3-col file has no intensity data: {path}")

    two_theta = _build_two_theta(start, step, n)
    return Pattern(
        two_theta=two_theta,
        intensity=np.asarray(intensities, dtype=np.float64),
        step=float(step),
        metadata={"format": "ascii_3col", "end_two_theta": float(end)},
    )


def read_ascii_profile_2col_header(path: str | Path) -> Pattern:
    """Read an ASCII profile with ``start, step`` header (no end value).

    First line: ``2theta_start, step``.  Following lines: intensities.

    Parameters
    ----------
    path:
        Path to the ``.pro`` / ``.dat`` file.

    Returns
    -------
    Pattern
        Parsed pattern.
    """
    text = _read_text(path)
    lines = _iter_data_lines(text)
    if len(lines) < 1:
        raise ValueError(f"Empty ASCII 2-col-header file: {path}")

    vals = _parse_numbers(lines[0])
    if len(vals) < 2:
        raise ValueError(
            f"ASCII 2-col-header first line must be start, step (got: {lines[0]!r})"
        )
    start, step = vals[0], vals[1]

    intensities: list[float] = []
    for ln in lines[1:]:
        intensities.extend(_parse_numbers(ln))

    n = len(intensities)
    if n == 0:
        raise ValueError(f"ASCII 2-col-header file has no intensity data: {path}")

    two_theta = _build_two_theta(start, step, n)
    return Pattern(
        two_theta=two_theta,
        intensity=np.asarray(intensities, dtype=np.float64),
        step=float(step),
        metadata={"format": "ascii_2col_hdr"},
    )


def read_ascii_profile_2col(path: str | Path) -> Pattern:
    """Read a two-column ASCII profile (``2theta/d, intensity``).

    Each data line holds a 2θ (or d-spacing) value and its intensity,
    separated by spaces, commas, or tabs.  Comment lines (``#``, ``!``,
    ``;``) are ignored.

    By default values are interpreted as 2θ in degrees.  If the data are
    monotonically decreasing (typical of d-spacing), they are left as-is
    and the caller is responsible for unit conversion — the pattern's
    ``metadata["x_unit"]`` will be set to ``"d"`` in that case, otherwise
    ``"2theta"``.

    Parameters
    ----------
    path:
        Path to the 2-column file.

    Returns
    -------
    Pattern
        Parsed pattern.
    """
    text = _read_text(path)
    two_theta: list[float] = []
    intensity: list[float] = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith(("#", "!", ";", "//")):
            continue
        vals = _parse_numbers(s)
        if len(vals) >= 2:
            two_theta.append(vals[0])
            intensity.append(vals[1])

    if not two_theta:
        raise ValueError(f"No 2-column data found in {path}")

    tt = np.asarray(two_theta, dtype=np.float64)
    ii = np.asarray(intensity, dtype=np.float64)

    # Heuristic: if x values are monotonically decreasing, they are probably
    # d-spacings (Å), not 2θ.  We store the array as-is and flag the unit.
    x_unit = "2theta"
    if tt.size > 1 and np.all(np.diff(tt) <= 0):
        x_unit = "d"

    step = None
    if tt.size > 1:
        diffs = np.diff(tt)
        if np.allclose(diffs, diffs[0], atol=1e-9, rtol=1e-9):
            step = float(diffs[0])

    return Pattern(
        two_theta=tt,
        intensity=ii,
        step=step,
        metadata={"format": "ascii_2col", "x_unit": x_unit},
    )


# ---------------------------------------------------------------------------
# ENDEAVOUR peak list
# ---------------------------------------------------------------------------
def read_endeavour(path: str | Path) -> Pattern:
    """Read an ENDEAVOUR peak list (``*.dif``).

    Two-column ASCII: ``2theta/d  intensity``, whitespace separated, one
    peak per line.  No header.

    Parameters
    ----------
    path:
        Path to the ``.dif`` file.

    Returns
    -------
    Pattern
        Parsed peak list as a pattern (``metadata["format"] = "endeavour"``).
    """
    text = _read_text(path)
    positions: list[float] = []
    intensities: list[float] = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith(("#", "!", ";", "//")):
            continue
        vals = _parse_numbers(s)
        if len(vals) >= 2:
            positions.append(vals[0])
            intensities.append(vals[1])

    if not positions:
        raise ValueError(f"No peak data found in ENDEAVOUR file {path}")

    pos = np.asarray(positions, dtype=np.float64)
    inten = np.asarray(intensities, dtype=np.float64)

    x_unit = "2theta"
    if pos.size > 1 and np.all(np.diff(pos) <= 0):
        x_unit = "d"

    return Pattern(
        two_theta=pos,
        intensity=inten,
        step=None,
        metadata={"format": "endeavour", "x_unit": x_unit, "kind": "peaklist"},
    )
