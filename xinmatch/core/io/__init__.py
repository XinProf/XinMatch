"""XinMatch diffraction data I/O.

Provides a unified entry point :func:`load_pattern` that auto-detects the
file format and dispatches to the appropriate reader.

Submodules:

* :mod:`detect` — format auto-detection.
* :mod:`free` — free (vendor-neutral) ASCII formats.
* :mod:`panalytical` — PANalytical/Philips ``.rd``/``.udf``/``.udi``.
* :mod:`bruker` — Bruker/Siemens ``.uxd``/``.brml`` (``.raw`` TODO).
* :mod:`exporters` — ASCII profile & peak-list writers.
"""

from __future__ import annotations

from pathlib import Path

from xinmatch.core.io import detect
from xinmatch.core.io.bruker import read_brml, read_raw, read_uxd
from xinmatch.core.io.detect import detect_format
from xinmatch.core.io.free import (
    read_ascii_profile_2col,
    read_ascii_profile_2col_header,
    read_ascii_profile_3col,
    read_dbws,
    read_endeavour,
)
from xinmatch.core.io.panalytical import read_rd, read_udf, read_udi
from xinmatch.core.model import Pattern

# Reader dispatch table: format identifier -> callable
_READERS = {
    detect.FMT_DBWS: read_dbws,
    detect.FMT_ASCII_3COL: read_ascii_profile_3col,
    detect.FMT_ASCII_2COL_HDR: read_ascii_profile_2col_header,
    detect.FMT_ASCII_2COL: read_ascii_profile_2col,
    detect.FMT_ENDEAVOUR: read_endeavour,
    detect.FMT_RD: read_rd,
    detect.FMT_UDF: read_udf,
    detect.FMT_UDI: read_udi,
    detect.FMT_UXD: read_uxd,
    detect.FMT_BRML: read_brml,
    detect.FMT_RAW: read_raw,
}

__all__ = [
    "detect_format",
    "load_pattern",
    "read_ascii_profile_2col",
    "read_ascii_profile_2col_header",
    "read_ascii_profile_3col",
    "read_dbws",
    "read_endeavour",
    "read_rd",
    "read_udi",
    "read_udf",
    "read_uxd",
    "read_brml",
    "read_raw",
]


def load_pattern(path: str | Path) -> Pattern:
    """Auto-detect format and load a diffraction pattern.

    Implements Match!'s "All files (automatic detection)" import.

    Parameters
    ----------
    path:
        Path to a supported diffraction data file.

    Returns
    -------
    Pattern
        Parsed diffraction pattern.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If the format cannot be detected or is unsupported.
    NotImplementedError
        If the detected format has no reader yet (e.g. Bruker ``.raw``).
    """
    p = Path(path)
    fmt = detect_format(p)
    reader = _READERS.get(fmt)
    if reader is None:
        raise ValueError(
            f"Detected format {fmt!r} for {p} has no registered reader."
        )
    return reader(p)
