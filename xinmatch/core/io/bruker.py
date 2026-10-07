"""Readers for Bruker/Siemens diffraction data formats.

Implements:

* :func:`read_uxd` — Siemens/Bruker UXD text format (``*.uxd``).  A
  block-structured ASCII format using ``;_<axis>`` delimiters.
* :func:`read_brml` — Bruker AXS BRML container (``*.brml``).  A ZIP
  archive holding XML files with intensities and scan-axis metadata.
* :func:`read_raw` — placeholder for Bruker ``.raw`` binary; **not
  implemented** (proprietary binary format, no public sample available).

BRML parsing uses only the standard library (``zipfile`` +
``xml.etree.ElementTree``).
"""

from __future__ import annotations

import contextlib
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np

from xinmatch.core.model import Pattern


# ---------------------------------------------------------------------------
# .uxd  —  Siemens/Bruker UXD text
# ---------------------------------------------------------------------------
def _read_text(path: str | Path) -> str:
    """Read text with UTF-8 then latin-1 fallback."""
    p = Path(path)
    raw = p.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _parse_numbers(line: str) -> list[float]:
    """Parse floats from a line, skipping non-numeric tokens."""
    tokens = line.replace(",", " ").replace("\t", " ").split()
    vals: list[float] = []
    for t in tokens:
        with contextlib.suppress(ValueError):
            vals.append(float(t))
    return vals


def read_uxd(path: str | Path) -> Pattern:
    """Read a Siemens/Bruker ``.uxd`` text data file.

    UXD is a block-structured format.  A powder scan is stored in a
    ``;_2theta`` block whose first three lines are *start*, *step*, and
    *number of points*, followed by the intensity values.

    Parameters
    ----------
    path:
        Path to the ``.uxd`` file.

    Returns
    -------
    Pattern
        Parsed diffraction pattern.
    """
    text = _read_text(path)
    lines = text.splitlines()

    # Find the ;_2theta block
    block_start = -1
    for i, ln in enumerate(lines):
        stripped = ln.strip()
        if stripped.lower().startswith(";_2theta"):
            block_start = i
            break
    if block_start < 0:
        raise ValueError(f"UXD file has no ;_2theta block: {path}")

    # Collect non-empty lines after the block marker
    block_lines: list[str] = []
    for ln in lines[block_start + 1 :]:
        s = ln.strip()
        if not s:
            continue
        # A new ;_ block ends this one
        if s.startswith(";_"):
            break
        block_lines.append(s)

    if len(block_lines) < 3:
        raise ValueError(f"UXD ;_2theta block too short: {path}")

    start = float(_parse_numbers(block_lines[0])[0])
    step = float(_parse_numbers(block_lines[1])[0])
    n_points = int(_parse_numbers(block_lines[2])[0])

    intensities: list[float] = []
    for ln in block_lines[3:]:
        intensities.extend(_parse_numbers(ln))
        if len(intensities) >= n_points:
            break
    intensities = intensities[:n_points]

    if len(intensities) != n_points:
        raise ValueError(
            f"UXD expected {n_points} intensities, got {len(intensities)}: {path}"
        )

    two_theta = start + step * np.arange(n_points, dtype=np.float64)
    return Pattern(
        two_theta=two_theta,
        intensity=np.asarray(intensities, dtype=np.float64),
        step=float(step),
        metadata={"format": "uxd", "vendor": "Bruker/Siemens"},
    )


# ---------------------------------------------------------------------------
# .brml  —  Bruker AXS BRML (ZIP + XML)
# ---------------------------------------------------------------------------
def _split_intensities(text: str) -> list[float]:
    """Split an intensity string (comma or whitespace separated) to floats."""
    tokens = re.split(r"[,\s]+", text.strip())
    vals: list[float] = []
    for t in tokens:
        if not t:
            continue
        with contextlib.suppress(ValueError):
            vals.append(float(t))
    return vals


def read_brml(path: str | Path) -> Pattern:
    """Read a Bruker AXS ``.brml`` container.

    ``.brml`` is a ZIP archive containing XML files.  The scan intensities
    and axis (2θ start/step/end) are read from the first XML document that
    contains an ``<Intensities>`` element and a 2θ ``<Axis>``.

    Parameters
    ----------
    path:
        Path to the ``.brml`` file.

    Returns
    -------
    Pattern
        Parsed diffraction pattern.
    """
    p = Path(path)
    with zipfile.ZipFile(p) as zf:
        xml_names = [n for n in zf.namelist() if n.lower().endswith(".xml")]
        if not xml_names:
            raise ValueError(f"BRML archive contains no XML files: {path}")

        for name in xml_names:
            try:
                data = zf.read(name)
            except KeyError:
                continue
            try:
                root = ET.fromstring(data)
            except ET.ParseError:
                continue

            intensities = _find_intensities(root)
            if intensities is None:
                continue

            start, step = _find_axis(root)
            if start is None or step is None:
                continue

            two_theta = start + step * np.arange(
                len(intensities), dtype=np.float64
            )
            return Pattern(
                two_theta=two_theta,
                intensity=np.asarray(intensities, dtype=np.float64),
                step=float(step),
                metadata={
                    "format": "brml",
                    "vendor": "Bruker",
                    "xml_file": name,
                },
            )

    raise ValueError(
        f"BRML archive has no usable scan data (Intensities + 2θ axis): {path}"
    )


def _find_intensities(root: ET.Element) -> list[float] | None:
    """Find the first ``<Intensities>`` element and return its values."""
    for elem in root.iter():
        tag = _localname(elem.tag)
        if tag.lower() == "intensities" and elem.text:
            vals = _split_intensities(elem.text)
            if vals:
                return vals
    return None


def _find_axis(root: ET.Element) -> tuple[float | None, float | None]:
    """Find a 2θ axis and return ``(start, step)``.

    Searches ``<Axis>`` elements whose ``<Name>`` is 2θ-related; falls back
    to the first axis with ``<Start>`` and ``<Step>`` children.
    """
    axes: list[ET.Element] = []
    for elem in root.iter():
        if _localname(elem.tag).lower() == "axis":
            axes.append(elem)

    start: float | None = None
    step: float | None = None

    for axis in axes:
        name = ""
        for child in axis:
            ctag = _localname(child.tag).lower()
            if ctag == "name" and child.text:
                name = child.text.strip().lower()
        if "2theta" in name or "2θ" in name or "two theta" in name:
            s, st = _axis_start_step(axis)
            if s is not None and st is not None:
                return s, st

    # Fallback: first axis with start & step
    for axis in axes:
        s, st = _axis_start_step(axis)
        if s is not None and st is not None and start is None:
            start, step = s, st
    return start, step


def _axis_start_step(axis: ET.Element) -> tuple[float | None, float | None]:
    """Extract ``<Start>`` and ``<Step>`` (or ``<Increment>``) from an axis."""
    start: float | None = None
    step: float | None = None
    for child in axis:
        ctag = _localname(child.tag).lower()
        if ctag in ("start", "startposition") and child.text:
            with contextlib.suppress(ValueError):
                start = float(child.text)
        elif ctag in ("step", "increment", "stepsize") and child.text:
            with contextlib.suppress(ValueError):
                step = float(child.text)
    return start, step


def _localname(tag: str) -> str:
    """Strip XML namespace prefix from a tag."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


# ---------------------------------------------------------------------------
# .raw  —  Bruker binary (NOT IMPLEMENTED)
# ---------------------------------------------------------------------------
def read_raw(path: str | Path) -> Pattern:
    """Read a Bruker ``.raw`` binary file.

    .. warning::

        **Not implemented.**  The Bruker ``.raw`` format is a proprietary
        binary container with no public specification.  Implementing it
        requires real sample files for reverse-engineering the byte layout.
        A TODO is left for a future task once samples are available.

    Parameters
    ----------
    path:
        Path to the ``.raw`` file.

    Raises
    ------
    NotImplementedError
        Always; the format is not supported yet.
    """
    raise NotImplementedError(
        f"Bruker .raw binary format is not supported (proprietary, no public "
        f"spec/sample). Cannot read {path}. "
        f"TODO: implement once real .raw samples are available."
    )
