"""Diffraction data file format auto-detection.

Implements the *automatic format detection* used by the reference software's
"All files (automatic detection)" import mode.

Detection combines three signals, in order:

1. **File extension** — fast path for unambiguous extensions (``.brml``,
   ``.xrdml``, ``.ras``, ``.uxd``, ``.plv``, ``.cpi``, ``.mdi``, ``.esg``,
   ``.gdf``).
2. **Magic numbers / header signatures** — disambiguate binary containers
   (``.brml`` is a ZIP archive; ``.raw`` vendors differ) and text formats
   with distinctive first tokens.
3. **Content sniffing** — for ambiguous extensions (``.dat``, ``.txt``,
   ``.dif``, ``.raw``, ``.rd``) the first non-comment lines are parsed to
   decide between DBWS, ASCII profile, 2-column, ENDEAVOUR, etc.

The returned string is a canonical format identifier that maps directly to
the reader in :mod:`xinmatch.core.io`.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Canonical format identifiers
# ---------------------------------------------------------------------------
# Free / generic formats
FMT_DBWS = "dbws"            # DBWS raw data (.rfl, .dat)
FMT_ASCII_3COL = "ascii_3col"   # start, step, end + intensities
FMT_ASCII_2COL_HDR = "ascii_2col_hdr"  # start, step + intensities
FMT_ASCII_2COL = "ascii_2col"  # 2 columns: 2theta/d, intensity
FMT_ENDEAVOUR = "endeavour"  # ENDEAVOUR peak list (.dif)

# Vendor formats
FMT_RD = "rd"                # PANalytical/Philips raw (.rd)
FMT_UDF = "udf"              # PANalytical/Philips raw (.udf)
FMT_UDI = "udi"              # PANalytical/Philips peak (.udi)
FMT_UXD = "uxd"              # Siemens/Bruker UXD text (.uxd)
FMT_BRML = "brml"            # Bruker BRML (.brml)
FMT_XRDML = "xrdml"          # PANalytical XRDML (.xrdml)
FMT_RAS = "ras"              # Rigaku RAS (.ras)
FMT_CPI = "cpi"              # Sietronics CPI (.cpi)
FMT_PLV = "plv"              # XPowder (.plv)
FMT_MDI = "mdi"              # Jade/MDI (.mdi)
FMT_ESG = "esg"              # GNR/Ital Structures (.esg)
FMT_GDF = "gdf"              # G670 (.gdf)
FMT_RAW = "raw"              # Generic / vendor raw (.raw)
FMT_SHIMADZU_RAW = "shimadzu_raw"  # Shimadzu XRD binary (.raw)
FMT_SHIMADZU_TXT = "shimadzu_txt"  # Shimadzu XRD ASCII export (.txt/.smz)
FMT_RAW2 = "raw2"            # RAW2 fixed-header binary (.raw)
FMT_RAW3 = "raw3"            # RAW1.01 fixed-header multi-block (.raw)
FMT_RAW4 = "raw4"            # RAW4.00 segmented container (.raw)
FMT_RIGAKU_RAW = "rigaku_raw"  # Rigaku RINT-2000 binary (.raw)

# Extensions that map 1:1 to a format
_EXTENSION_MAP: dict[str, str] = {
    ".rd": FMT_RD,
    ".udf": FMT_UDF,
    ".udi": FMT_UDI,
    ".uxd": FMT_UXD,
    ".brml": FMT_BRML,
    ".xrdml": FMT_XRDML,
    ".ras": FMT_RAS,
    ".cpi": FMT_CPI,
    ".plv": FMT_PLV,
    ".mdi": FMT_MDI,
    ".esg": FMT_ESG,
    ".gdf": FMT_GDF,
    ".rfl": FMT_DBWS,
}


def detect_format(path: str | Path) -> str:
    """Detect the diffraction-data format of *path*.

    Implements the reference software's automatic file-format identification.

    Parameters
    ----------
    path:
        Path to the diffraction data file.

    Returns
    -------
    str
        Canonical format identifier (see module-level ``FMT_*`` constants).

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If the format cannot be determined.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)

    ext = p.suffix.lower()

    # 1. Unambiguous extension mapping
    if ext in _EXTENSION_MAP:
        return _EXTENSION_MAP[ext]

    # 2. Binary container checks (need a few bytes)
    if ext in (".brml",):
        return FMT_BRML

    # Peek at the first chunk of the file for magic / signature detection
    try:
        raw = p.read_bytes()
    except OSError:
        raw = b""

    # ZIP archive signature -> almost certainly .brml (or another XML container)
    if raw.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(p) as zf:
                names = zf.namelist()
            if any(n.lower().endswith(".xml") for n in names):
                return FMT_BRML
        except zipfile.BadZipFile:
            pass

    # XML root -> XRDML
    head = raw[:512].lstrip()
    if head.startswith(b"<?xml") or head.lower().startswith(b"<xrdml"):
        return FMT_XRDML

    # Vendor binary magic checks apply to .raw containers only; a text file
    # whose banner happens to start with "Shimadzu XRD" (or "RAW2") must
    # stay on the text path.
    if ext == ".raw":
        # Shimadzu XRD binary .raw magic
        if raw.startswith(b"Shimadzu XRD"):
            return FMT_SHIMADZU_RAW
        # RAW2 fixed-header binary (IUCr round-robin .raw etc.)
        if raw.startswith(b"RAW2"):
            return FMT_RAW2
        # Bruker RAW ver. 3 (RAW1.01) / ver. 4 (RAW4.00) — "RAW " (ver. 1)
        # is undocumented and unsupported (see bruker_raw module docstring).
        if raw.startswith(b"RAW1.01"):
            return FMT_RAW3
        if raw.startswith(b"RAW4.00"):
            return FMT_RAW4
        # Rigaku RINT-2000 binary .raw
        if raw.startswith(b"FI\x00\x00"):
            return FMT_RIGAKU_RAW
        # otherwise fall through to text signature checks below, and finally
        # to the generic FMT_RAW fallback

    # Decode text for content sniffing (latin-1 never fails)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="replace")

    lines = [ln for ln in text.splitlines() if ln.strip()]

    # 3. Format-specific header signatures ---------------------------------
    # Bruker UXD: blocks start with ";_<axis>"
    if any(ln.lstrip().startswith(";_") for ln in lines[:20]):
        return FMT_UXD

    # Sietronics CPI: starts with "SIETRONICS" or "[Scan1]" / "FileVersion"
    first = lines[0].strip() if lines else ""
    if first.upper().startswith("SIETRONICS") or first.startswith("["):
        return FMT_CPI

    # PANalytical .rd: header lines start with "*"
    if first.startswith("*"):
        return FMT_RD

    # PANalytical .udf / .udi: INI-style "[Section]" headers
    if first.startswith("[") and "]" in first:
        section = first.strip("[]").lower()
        if "peak" in section:
            return FMT_UDI
        return FMT_UDF

    # Rigaku RAS: starts with "[" + "RAS" keyword
    if first.startswith("[") and "ras" in first.lower():
        return FMT_RAS

    # XPowder .plv: distinctive first token
    if first.upper().startswith("XPOWDER") or "XPOWDER" in first.upper():
        return FMT_PLV

    # Jade/MDI .mdi: starts with "JAD" or "MDI"
    if first.upper().startswith(("JAD", "MDI")):
        return FMT_MDI

    # GNR .esg / G670 .gdf: vendor banner
    if "GNR" in first.upper() or "ITAL" in first.upper():
        return FMT_ESG
    if "G670" in first.upper() or "STOE" in first.upper():
        return FMT_GDF

    # 4. Ambiguous extensions: content sniffing ----------------------------
    if ext == ".dat":
        fmt = _sniff_dat(lines)
        if fmt is not None:
            return fmt
    if ext == ".txt":
        fmt = _sniff_txt(lines)
        if fmt is not None:
            return fmt
    if ext == ".dif":
        # ENDEAVOUR is 2-column 2theta/d + I; Bruker .dif has a header
        return _sniff_dif(lines)
    if ext == ".raw":
        return FMT_RAW

    # Fallback: try to sniff as a generic two-column / profile file
    fmt = _sniff_dat(lines)
    if fmt is not None:
        return fmt

    raise ValueError(f"Unable to determine diffraction data format for {p}")


# ---------------------------------------------------------------------------
# Content sniffers for ambiguous extensions
# ---------------------------------------------------------------------------
def _first_data_lines(lines: list[str], max_lines: int = 5) -> list[str]:
    """Return the first non-comment, non-empty lines."""
    out = []
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith(("#", "!", ";", "//")):
            continue
        out.append(s)
        if len(out) >= max_lines:
            break
    return out


def _parse_numbers(line: str) -> list[float]:
    """Split a line on whitespace/comma/tab and parse floats.

    Non-numeric tokens are skipped (e.g. a trailing DBWS title token).
    """
    tokens = line.replace(",", " ").replace("\t", " ").split()
    vals: list[float] = []
    for t in tokens:
        try:
            vals.append(float(t))
        except ValueError:
            continue
    return vals


def _sniff_dat(lines: list[str]) -> str | None:
    """Sniff a ``.dat`` file: DBWS, ASCII 3-col, ASCII 2-col header, or 2-col."""
    data = _first_data_lines(lines, max_lines=3)
    if not data:
        return None
    first_vals = _parse_numbers(data[0])
    if not first_vals:
        return None

    # DBWS / ASCII start-step-end: 3 numbers on first line (start, step, end)
    # DBWS allows an optional 4th title token.
    if len(first_vals) >= 3 and first_vals[1] > 0 and first_vals[2] > first_vals[0]:
        # If there are exactly 3 numeric tokens, it's ASCII 3-col or DBWS.
        # Distinguish: DBWS intensities follow in groups of 8 (8F7).  We can't
        # reliably tell from one line, so default to ASCII 3-col; the reader
        # also accepts the DBWS layout.
        return FMT_ASCII_3COL

    # ASCII start-step (no end): exactly 2 numbers on line 1, step > 0,
    # and the second line contains *many* intensity values (more than 2).
    if len(first_vals) == 2 and first_vals[1] > 0 and len(data) >= 2:
        second_vals = _parse_numbers(data[1])
        if second_vals and len(second_vals) > 2:
            return FMT_ASCII_2COL_HDR

    # Otherwise treat as 2-column (2theta/d, intensity)
    if len(first_vals) >= 2:
        return FMT_ASCII_2COL

    return None


def _sniff_txt(lines: list[str]) -> str | None:
    """Sniff a ``.txt`` file — Shimadzu instrument export, JEOL/TXRD dump,
    or generic 2-column.

    A Shimadzu instrument export carries a metadata header with
    ``target``/``voltage`` and ``<2Theta>`` column captions; when those
    tokens are present the file is routed to the Shimadzu text reader so
    the radiation metadata is preserved.  Otherwise the file is scanned
    forward past header / metadata blocks until a line with at least two
    numeric values is found — that is the first data row of a 2-column
    profile.
    """
    head = "\n".join(lines[:60]).lower()
    if ("target" in head and "voltage" in head) or "<2theta>" in head:
        return FMT_SHIMADZU_TXT
    for ln in lines[:60]:
        s = ln.strip()
        if not s or s.startswith(("#", "!", ";", "//")):
            continue
        vals = _parse_numbers(s)
        if len(vals) >= 2:
            return FMT_ASCII_2COL
    return None


def _sniff_dif(lines: list[str]) -> str:
    """Sniff a ``.dif`` file: ENDEAVOUR 2-column or Bruker dif header."""
    data = _first_data_lines(lines, max_lines=3)
    if not data:
        return FMT_ENDEAVOUR
    first_vals = _parse_numbers(data[0])
    if first_vals and len(first_vals) == 2:
        return FMT_ENDEAVOUR
    return FMT_ENDEAVOUR
