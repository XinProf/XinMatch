"""Exporters for diffraction patterns to common ASCII formats.

Implements writers that round-trip with the readers in :mod:`free.py`:

* :func:`export_ascii_profile` — write a ``start, step, end`` ASCII profile
  followed by intensities (compatible with :func:`read_ascii_profile_3col`).
* :func:`export_ascii_2col` — write a two-column ``2theta intensity`` file
  (compatible with :func:`read_ascii_profile_2col`).
* :func:`export_peak_list` — write a two-column peak list
  (compatible with :func:`read_endeavour`).

All writers use UTF-8 and LF newlines (per ``docs/CONVENTIONS.md``).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from xinmatch.core.model import Pattern


def _ensure_parent(path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def export_ascii_profile(
    pattern: Pattern,
    path: str | Path,
    values_per_line: int = 9,
) -> Path:
    """Export a pattern as an ASCII profile (start, step, end + intensities).

    The first line contains ``start step end``.  Subsequent lines contain
    intensity values, *values_per_line* per line.  This is the inverse of
    :func:`xinmatch.core.io.free.read_ascii_profile_3col`.

    Parameters
    ----------
    pattern:
        Pattern to export.  Must have a uniform ``step``; if ``step`` is
        ``None`` the median spacing is used.
    path:
        Output file path.
    values_per_line:
        Number of intensity values per data line.

    Returns
    -------
    Path
        The path written.
    """
    p = _ensure_parent(path)
    tt = np.asarray(pattern.two_theta, dtype=np.float64)
    ii = np.asarray(pattern.intensity, dtype=np.float64)

    if tt.size == 0:
        raise ValueError("Cannot export an empty pattern")

    step = pattern.step
    if step is None:
        diffs = np.diff(tt)
        step = float(np.median(diffs)) if diffs.size else 0.0

    start = float(tt[0])
    end = float(tt[-1])

    lines = [f"{start:.10f}  {step:.10f}  {end:.10f}"]
    for i in range(0, ii.size, values_per_line):
        chunk = ii[i : i + values_per_line]
        lines.append("  ".join(f"{v:.10f}" for v in chunk))

    p.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return p


def export_ascii_2col(pattern: Pattern, path: str | Path) -> Path:
    """Export a pattern as a two-column ``2theta intensity`` ASCII file.

    Inverse of :func:`xinmatch.core.io.free.read_ascii_profile_2col`.

    Parameters
    ----------
    pattern:
        Pattern to export.
    path:
        Output file path.

    Returns
    -------
    Path
        The path written.
    """
    p = _ensure_parent(path)
    tt = np.asarray(pattern.two_theta, dtype=np.float64)
    ii = np.asarray(pattern.intensity, dtype=np.float64)

    lines = [f"{t:.10f}  {v:.10f}" for t, v in zip(tt, ii, strict=True)]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return p


def export_peak_list(
    two_theta: np.ndarray,
    intensity: np.ndarray,
    path: str | Path,
) -> Path:
    """Export a peak list as a two-column ENDEAVOUR-style ``.dif`` file.

    Inverse of :func:`xinmatch.core.io.free.read_endeavour`.

    Parameters
    ----------
    two_theta:
        Peak positions in degrees 2θ.
    intensity:
        Peak intensities.
    path:
        Output file path.

    Returns
    -------
    Path
        The path written.
    """
    p = _ensure_parent(path)
    tt = np.asarray(two_theta, dtype=np.float64)
    ii = np.asarray(intensity, dtype=np.float64)
    if tt.shape != ii.shape:
        raise ValueError("two_theta and intensity must have the same shape")

    lines = [f"{t:.10f}  {v:.10f}" for t, v in zip(tt, ii, strict=True)]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return p
