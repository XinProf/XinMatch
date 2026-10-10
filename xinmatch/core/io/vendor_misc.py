"""Minimal readers for small vendor text/binary formats.

These formats are recognised by the auto-detection layer but previously had
no registered readers (a "no registered reader" dead-end).  Each reader here
covers the common layout described by the format documentation and exercised
by the synthetic samples in ``tests/io/_samples.py``:

* ``read_ras``  — Rigaku RAS: ``[RAS_INT_START]`` … ``*BEGIN`` block of
  2θ/intensity rows … ``*END`` ``[RAS_INT_END]``.
* ``read_cpi``  — Sietronics CPI: banner ``SIETRONICS``, then a
  ``start step end`` axis line, then intensity values.
* ``read_plv``  — XPowder ``.plv``: banner ``XPOWDER``, then 2θ/intensity
  rows.
* ``read_esg``  — GNR/Ital Structures ``.esg``: banner ``GNR``, then
  2θ/intensity rows.
* ``read_gdf``  — STOE G670 ``.gdf``: banner ``STOE``/``G670``, then
  2θ/intensity rows.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from xinmatch.core.model import Pattern


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def _parse_numbers(line: str) -> list[float]:
    vals: list[float] = []
    for t in line.replace(",", " ").split():
        try:
            vals.append(float(t))
        except ValueError:
            continue
    return vals


def _two_column_pattern(path: Path, fmt: str, vendor: str) -> Pattern:
    """Shared 2θ/intensity column parser (skips banners/comments)."""
    rows: list[tuple[float, float]] = []
    for ln in _read_text(path).splitlines():
        s = ln.strip()
        if not s or s.startswith(("#", "!", ";", "//", "*")):
            continue
        vals = _parse_numbers(s)
        if len(vals) >= 2:
            rows.append((vals[0], vals[1]))
    if len(rows) < 2:
        raise ValueError(f"{vendor} file has no data rows: {path}")
    two_theta = np.asarray([r[0] for r in rows], dtype=np.float64)
    intensity = np.asarray([r[1] for r in rows], dtype=np.float64)
    step = float(two_theta[1] - two_theta[0]) if len(two_theta) > 1 else 0.0
    return Pattern(
        two_theta=two_theta,
        intensity=intensity,
        wavelength=1.5406,
        step=step,
        metadata={"format": fmt, "vendor": vendor},
    )


def read_ras(path: str | Path) -> Pattern:
    """Read a Rigaku RAS file (banner + ``*BEGIN`` 2θ/intensity rows)."""
    rows: list[tuple[float, float]] = []
    in_block = False
    for ln in _read_text(Path(path)).splitlines():
        s = ln.strip()
        if s.upper().startswith("*BEGIN"):
            in_block = True
            continue
        if s.upper().startswith("*END"):
            break
        if not in_block or not s or s.startswith(("#", "!", ";", "//", "*")):
            continue
        vals = _parse_numbers(s)
        if len(vals) >= 2:
            rows.append((vals[0], vals[1]))
    if len(rows) < 2:
        raise ValueError(f"Rigaku RAS file has no *BEGIN data rows: {path}")
    two_theta = np.asarray([r[0] for r in rows], dtype=np.float64)
    intensity = np.asarray([r[1] for r in rows], dtype=np.float64)
    step = float(two_theta[1] - two_theta[0]) if len(two_theta) > 1 else 0.0
    return Pattern(
        two_theta=two_theta,
        intensity=intensity,
        wavelength=1.5406,
        step=step,
        metadata={"format": "ras", "vendor": "Rigaku"},
    )


def read_cpi(path: str | Path) -> Pattern:
    """Read a Sietronics CPI file: ``start step end`` axis + intensity rows."""
    p = Path(path)
    lines = [ln for ln in _read_text(p).splitlines() if ln.strip()]
    if len(lines) < 2:
        raise ValueError(f"Sietronics CPI file too short: {p}")
    axis: list[float] | None = None
    data_start = 0
    for i, ln in enumerate(lines[:6]):
        vals = _parse_numbers(ln)
        if len(vals) >= 3 and vals[1] > 0 and vals[2] > vals[0]:
            axis = vals[:3]
            data_start = i + 1
            break
    if axis is None:
        raise ValueError(f"Sietronics CPI axis line not found: {p}")
    start, step, _end = axis
    intensity: list[float] = []
    for ln in lines[data_start:]:
        intensity.extend(_parse_numbers(ln))
    if len(intensity) < 2:
        raise ValueError(f"Sietronics CPI has no intensity data: {p}")
    intensity_arr = np.asarray(intensity, dtype=np.float64)
    two_theta = start + step * np.arange(len(intensity_arr), dtype=np.float64)
    return Pattern(
        two_theta=two_theta,
        intensity=intensity_arr,
        wavelength=1.5406,
        step=float(step),
        metadata={"format": "cpi", "vendor": "Sietronics"},
    )


def read_plv(path: str | Path) -> Pattern:
    """Read an XPowder ``.plv`` file (2θ/intensity rows)."""
    return _two_column_pattern(Path(path), "plv", "XPowder")


def read_esg(path: str | Path) -> Pattern:
    """Read a GNR/Ital Structures ``.esg`` file (2θ/intensity rows)."""
    return _two_column_pattern(Path(path), "esg", "GNR")


def read_gdf(path: str | Path) -> Pattern:
    """Read a STOE G670 ``.gdf`` file (2θ/intensity rows)."""
    return _two_column_pattern(Path(path), "gdf", "STOE")
