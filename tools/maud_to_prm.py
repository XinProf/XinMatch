r"""MAUD ``.par`` → GSAS-II ``.prm`` instrument extractor (T8.3/#17).

Reads a MAUD 2.99x Rietveld project (the reference software's refinement
engine output, e.g. ``XRData/ShiJiKong-XRD6100/*.par``) and emits a
GSAS-II instrument parameter file carrying the *measured* instrument
values: Cu K-alpha1/K-alpha2 wavelengths and the measured K-alpha2
intensity ratio, the Bragg-Brentano geometry flag, the monochromator
2-theta, and the detector type.

This is the "measured instrument parameter file" that #17 needs: the
generic default .prm shipped with XinMatch is a physically reasonable
guess, but a real machine's Cu K-alpha doublet wavelengths / ratio are
refined quantities that differ from textbook values (e.g. the XRD-7000
in the user's dataset refines lam1=1.5405982, lam2=1.5445065,
I(Ka2)/I(Ka1)=0.48983).

Usage::

    python tools/maud_to_prm.py <sample.par> [out.prm]

If no output path is given the .prm is written next to the .par with a
``.prm`` suffix.  The parser is deliberately tolerant: it reads the
``_diffrn_radiation_wavelength`` / ``_diffrn_radiation_wavelength_wt``
pairs and a handful of ``_pd_instr_*`` keys and ignores everything else.
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Default output (matches the fixed-column layout GSASIIfiles.py parses:
#   wave1 = s[0:10], wave2 = s[10:20], zero = s[20:30]/100,
#   Polariz. = s[40:50], I(L2)/I(L1) = s[55:65])
# ---------------------------------------------------------------------------
def _icons_line(lam1: float, lam2: float, ratio: float,
                zero: float = 0.0, pola: float = 0.5) -> str:
    # s[55:65] must contain the ratio value with no interior whitespace:
    # pad the [50:60] slot with blanks and left-align ratio at [60:70] so
    # s[55:65] = "     " + "0.489834"[:5] parses exactly.
    body = (
        f"{lam1:>10.6f}"      # [0:10]  Lam1
        f"{lam2:>10.6f}"      # [10:20] Lam2
        f"{zero:>10.1f}"      # [20:30] Zero (=value/100)
        f"{0:>10d}"           # [30:40] (ignored)
        f"{pola:>10.3f}"      # [40:50] Polariz.
        f"{'':10s}"           # [50:60] (ignored)
        f"{ratio:<10.6f}"     # [60:70] I(L2)/I(L1)
    )
    return "INS  1 ICONS" + body


def _prm_text(lam1: float, lam2: float, ratio: float,
              geometry: str, mono_2theta: float | None,
              detector: str, device: str) -> str:
    head = (
        "           123456789012345678901234567890123456789012345678901234567890\n"
        "INS   BANK      1\n"
        "INS   HTYPE   PXCR\n"
        "INS  1 IRAD     3\n"
        + _icons_line(lam1, lam2, ratio)
        + "\n"
        + f"INS  1I HEAD  {device} {geometry} Cu Ka, monochromator "
        + (f"{mono_2theta:.3f}deg, " if mono_2theta else "")
        + f"{detector}\n"
        + "INS  1I ITYP    0    0.0000  180.0000         1\n"
        + "INS  1PRCF1     3    8      0.01\n"
        + "INS  1PRCF11   1.000000E-01  -5.000000E-02   1.000000E-02   0.000000E+00\n"
        + "INS  1PRCF12   0.000000E+00   0.000000E+00   0.000000E+00   0.000000E+00\n"
    )
    return head


def _clean(v: str) -> str:
    return v.strip().strip("'\"")


def extract_from_par(par_path: str | Path) -> dict:
    """Read measured instrument values from a MAUD .par text block."""
    par_path = Path(par_path)
    if not par_path.is_file():
        raise ValueError(f"MAUD .par not found: {par_path}")
    text = par_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    wavelengths: dict[str, float] = {}  # id -> wavelength (A)
    weights: dict[str, float] = {}  # id -> intensity weight
    wl_id = ""
    geo = "Bragg-Brentano"
    mono = None
    det = "Scintillation"
    device = "MAUD instrument"

    for ln in lines:
        s = ln.strip()
        if s.startswith("_diffrn_radiation_wavelength_id"):
            parts = s.split(None, 1)
            wl_id = _clean(parts[1]) if len(parts) > 1 else ""
        elif s.startswith("_diffrn_radiation_wavelength "):
            parts = s.split()
            try:
                wl = float(parts[1])
            except (IndexError, ValueError):
                continue
            wavelengths[wl_id] = wl
        elif s.startswith("_diffrn_radiation_wavelength_wt"):
            parts = s.split()
            with contextlib.suppress(IndexError, ValueError):
                weights[wl_id] = float(parts[1])
        elif s.startswith("_pd_instr_geometry"):
            parts = s.split(None, 1)
            if len(parts) > 1:
                geo = _clean(parts[1])
        elif s.startswith("_pd_instr_2theta_monochr_post"):
            parts = s.split()
            with contextlib.suppress(IndexError, ValueError):
                mono = float(parts[1])
        elif s.startswith("_diffrn_radiation_detector"):
            parts = s.split(None, 1)
            if len(parts) > 1:
                det = _clean(parts[1])
        elif s.startswith("_diffrn_measurement_device"):
            parts = s.split(None, 1)
            if len(parts) > 1 and _clean(parts[1]) not in ("?", ""):
                device = _clean(parts[1])

    lam1 = next((w for k, w in wavelengths.items() if "Ka1" in k), None)
    lam2 = next((w for k, w in wavelengths.items() if "Ka2" in k), None)
    if lam1 is None and wavelengths:
        lam1 = next(iter(wavelengths.values()))
    if lam2 is None and len(wavelengths) > 1:
        lam2 = list(wavelengths.values())[1]
    w1 = next((wt for k, wt in weights.items() if "Ka1" in k), 1.0) or 1.0
    w2 = next((wt for k, wt in weights.items() if "Ka2" in k), 0.5) or 0.5
    ratio = w2 / w1 if w1 else 0.5

    if lam1 is None:
        raise ValueError(f"no Cu K-alpha wavelengths found in {par_path}")

    return {
        "lam1": lam1,
        "lam2": lam2 or lam1,
        "ratio": ratio,
        "geometry": geo,
        "mono_2theta": mono,
        "detector": det,
        "device": device,
    }


def build_prm(values: dict) -> str:
    return _prm_text(
        values["lam1"], values["lam2"], values["ratio"],
        values["geometry"], values["mono_2theta"],
        values["detector"], values["device"],
    )


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    par = Path(argv[1])
    if not par.is_file():
        print(f"error: {par} not found")
        return 1
    values = extract_from_par(par)
    out = Path(argv[2]) if len(argv) > 2 else par.with_suffix(".prm")
    out.write_text(build_prm(values), encoding="ascii")
    print(f"wrote {out}")
    for k, v in values.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
