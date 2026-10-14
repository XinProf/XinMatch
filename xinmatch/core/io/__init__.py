"""XinMatch diffraction data I/O.

Provides a unified entry point :func:`load_pattern` that auto-detects the
file format and dispatches to the appropriate reader.

Submodules:

* :mod:`detect` — format auto-detection.
* :mod:`free` — free (vendor-neutral) ASCII formats.
* :mod:`panalytical` — PANalytical/Philips ``.rd``/``.udf``/``.udi``.
* :mod:`bruker` — Bruker/Siemens ``.uxd``/``.brml``.
* :mod:`bruker_raw` — Bruker RAW ver. 3/4 binary (``.raw``).
* :mod:`exporters` — ASCII profile & peak-list writers.
"""

from __future__ import annotations

from pathlib import Path

from xinmatch.core.io import detect
from xinmatch.core.io.bruker import read_brml, read_raw, read_uxd
from xinmatch.core.io.bruker_raw import read_bruker_raw_v3, read_bruker_raw_v4
from xinmatch.core.io.detect import detect_format
from xinmatch.core.io.free import (
    read_ascii_profile_2col,
    read_ascii_profile_2col_header,
    read_ascii_profile_3col,
    read_dbws,
    read_endeavour,
)
from xinmatch.core.io.mdi import read_mdi
from xinmatch.core.io.panalytical import read_rd, read_udf, read_udi
from xinmatch.core.io.rigaku import read_raw2, read_rigaku_raw
from xinmatch.core.io.shimadzu_raw import read_shimadzu_raw
from xinmatch.core.io.shimadzu_txt import read_shimadzu_txt
from xinmatch.core.io.vendor_misc import read_cpi, read_esg, read_gdf, read_plv, read_ras
from xinmatch.core.io.xrdml import read_xrdml
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
    detect.FMT_XRDML: read_xrdml,
    detect.FMT_RAS: read_ras,
    detect.FMT_CPI: read_cpi,
    detect.FMT_PLV: read_plv,
    detect.FMT_MDI: read_mdi,
    detect.FMT_ESG: read_esg,
    detect.FMT_GDF: read_gdf,
    detect.FMT_SHIMADZU_RAW: read_shimadzu_raw,
    detect.FMT_SHIMADZU_TXT: read_shimadzu_txt,
    detect.FMT_RAW2: read_raw2,
    detect.FMT_RAW3: read_bruker_raw_v3,
    detect.FMT_RAW4: read_bruker_raw_v4,
    detect.FMT_RIGAKU_RAW: read_rigaku_raw,
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
    "read_xrdml",
    "read_ras",
    "read_cpi",
    "read_plv",
    "read_mdi",
    "read_esg",
    "read_gdf",
    "read_shimadzu_raw",
    "read_shimadzu_txt",
    "read_raw2",
    "read_bruker_raw_v3",
    "read_bruker_raw_v4",
    "read_rigaku_raw",
    "read_raw",
]


def load_pattern(path: str | Path) -> Pattern:
    """Auto-detect format and load a diffraction pattern.

    Implements the reference software's "All files (automatic detection)" import.

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
