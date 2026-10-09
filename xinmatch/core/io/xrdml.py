"""Reader for PANalytical XRDML (``.xrdml``) XML diffraction data.

XRDML is the XML container used by PANalytical/Bruker instruments.  The
pattern lives in ``xrdMeasurements/xrdMeasurement/scan/dataPoints``:
``positions`` (per-axis, ``axisName="2Theta"``) and ``intensities``, with
``startPosition``/``endPosition`` and ``step@size`` describing the axis.
Namespace is matched by local name so both the 2.0 and 2.1 schemas work.

When explicit axis fields are missing, the reader falls back to scanning
all numeric tokens and splitting them into a leading 2θ column and a
trailing intensity column (same fallback as the PolyXRD loader).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from xinmatch.core.model import Pattern


def _localname(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _first_text(root: ET.Element, local: str) -> str | None:
    for el in root.iter():
        if _localname(el.tag) == local and el.text and el.text.strip():
            return el.text.strip()
    return None


def _axis_from_scan(root: ET.Element) -> tuple[float | None, float | None, int]:
    """Return ``(start, step, n)`` from the scan axis fields, or ``None``s."""
    start = _first_text(root, "startPosition")
    end = _first_text(root, "endPosition")
    step = None
    for el in root.iter():
        if _localname(el.tag) == "step":
            step = el.get("size")
            break
    positions: str | None = None
    for el in root.iter():
        if _localname(el.tag) == "positions":
            for child in el.iter():
                if _localname(child.tag) == "axis" and child.get("axisName") == "2Theta":
                    if child.text and child.text.strip():
                        positions = child.text.strip()
    if positions:
        vals = [float(v) for v in positions.split()]
        if vals:
            n = len(vals)
            st = vals[0]
            sp = vals[1] - vals[0] if n > 1 else (float(step) if step else None)
            return st, sp, n
    if start and end and step:
        try:
            st, en, sp = float(start), float(end), float(step)
        except ValueError:
            return None, None, 0
        if sp > 0 and en > st:
            n = int(round((en - st) / sp)) + 1
            return st, sp, n
    return None, None, 0


def read_xrdml(path: str | Path) -> Pattern:
    """Read an XRDML XML diffraction file.

    Parameters
    ----------
    path:
        Path to the ``.xrdml`` file.

    Returns
    -------
    Pattern
        Parsed diffraction pattern.

    Raises
    ------
    ValueError
        If the XML cannot be parsed or no 2θ/intensity pair can be found.
    """
    p = Path(path)
    try:
        root = ET.parse(str(p)).getroot()
    except ET.ParseError as exc:
        raise ValueError(f"XRDML XML parse error: {p}") from exc

    intensity: np.ndarray | None = None
    for el in root.iter():
        if _localname(el.tag) == "intensities" and el.text and el.text.strip():
            try:
                vals = [float(v) for v in el.text.split()]
            except ValueError:
                continue
            if len(vals) > 1:
                intensity = np.asarray(vals, dtype=np.float64)
                break

    if intensity is None:
        # fallback: scan all numeric tokens, assume leading 2θ half
        numbers: list[float] = []
        for el in root.iter():
            if el.text and el.text.strip():
                for t in el.text.split():
                    try:
                        numbers.append(float(t))
                    except ValueError:
                        pass
        if len(numbers) < 6:
            raise ValueError(f"Unable to extract 2θ/intensity from XRDML: {p}")
        n = len(numbers) // 2
        two_theta = np.asarray(numbers[:n], dtype=np.float64)
        intensity = np.asarray(numbers[n : n * 2], dtype=np.float64)
    else:
        start, step, n_axis = _axis_from_scan(root)
        n = len(intensity)
        if start is not None and step is not None and step > 0:
            if n_axis and n_axis != n:
                # positions column length disagrees with intensities: trust
                # the intensities and rebuild the axis from start/step
                pass
            two_theta = start + step * np.arange(n, dtype=np.float64)
        else:
            # no trustworthy axis: linear default on the intensity length
            two_theta = np.arange(n, dtype=np.float64)

    if len(two_theta) != len(intensity):
        m = min(len(two_theta), len(intensity))
        two_theta, intensity = two_theta[:m], intensity[:m]
    if len(two_theta) < 2:
        raise ValueError(f"XRDML data too short: {p}")

    step = float(two_theta[1] - two_theta[0]) if len(two_theta) > 1 else 0.0
    return Pattern(
        two_theta=two_theta,
        intensity=intensity,
        wavelength=1.5406,
        step=step,
        metadata={"format": "xrdml", "vendor": "PANalytical"},
    )
