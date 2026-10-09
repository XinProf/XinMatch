"""Parse GSAS-II refinement output and back-fill the XinMatch data model (T10.9).

GSAS-II (B.H. Toby, R.B. Von Dreele, *J. Appl. Cryst.* 46 (2013) 544-549)
writes several artefacts at the end of a Rietveld / Le Bail refinement:

* ``<project>.lst``   — human-readable refinement log.  The R-factor summary
  line `` wR = 35.95%, chi**2 = 143413, GOF = 6.19`` and the
  ``Other residuals: R = 29.87%, ... wRmin = 5.81%`` line give the profile
  agreement factors; the per-phase blocks give refined unit cells, atom
  coordinates and weight fractions.
* ``<project>_new.cif`` (phase CIF) — refined structure in CIF form.
* ``<project>.prf``   — residual profile (2θ / Yobs / Ycalc / residual).
* ``<project>.gpx``   — the binary pickle project (scale / zero / cell).

Correspondence with the reference software
--------------------------
This module is the read-back half of the Rietveld loop that the reference software performs
through FullProf:

* ``docs/Rietveld.md`` — *Results viewing*: Rwp / Rp / reduced-chi2 shown in
  the "FP Rietveld" tab (here mapped to
  :class:`xinmatch.core.report.report_model.RFactorSection`).
* ``docs/LeBail.md`` — whole-pattern intensity extraction; the same .lst /
  .prf files are produced.
* ``docs/export_refined_structure.md`` — *File/Export/Refined structure*: the
  refined cell / coordinates / occupancy / Biso are exported to a CIF and
  back-filled onto the selected :class:`~xinmatch.core.model.phase.Phase`.
* ``docs/export_report.md`` — the R-factor chapter of the report.

Notes on reuse
--------------
:mod:`xinmatch.core.refine.residuals` computes R-factors *and* finds unfitted
peaks from (obs − calc).  Here we deliberately **trust GSAS-II's reported**
Rwp/Rp/χ² rather than recomputing them from the parsed arrays: GSAS-II uses
its own per-point ESD weights and degrees of freedom, so a local
Poisson-weighted recomputation would not reproduce the value printed in the
``.lst`` (the task requires numerical agreement with GSAS-II).  The parsed
observed / fitted / residual :class:`~xinmatch.core.model.pattern.Pattern`
objects are exposed on :class:`Gsas2RefineOutcome` so that
:func:`xinmatch.core.refine.residuals.residual_analysis` can be invoked
downstream for unfitted-peak detection.

GSAS-II source references (read-only; formats documented here from):
``GSASIIstrMain.py`` (`` wR = ..., chi**2 = ..., GOF = ...`` summary),
``GSASIIscriptable.py`` (histogram ``getdata`` arrays; ``export_CIF``),
``GSASIIpwd.py`` (profile / R-factor definitions).
"""

from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from xinmatch.core.model.entry import CellParams, Entry
from xinmatch.core.model.pattern import Pattern
from xinmatch.core.model.phase import Phase
from xinmatch.core.report.report_model import RFactorSection

__all__ = [
    "Gsas2RefineOutcome",
    "RefinedPhaseInfo",
    "parse_cif",
    "parse_gpx",
    "parse_lst",
    "parse_prf",
    "parse_refinement",
]


# ---------------------------------------------------------------------------
# .lst parsing
# ---------------------------------------------------------------------------
#: `` wR =   35.95%, chi**2 =       143413, GOF =   6.19``
_WR_LINE = re.compile(
    r"wR\s*=\s*([-+]?\d*\.?\d+)%\s*,\s*chi\*\*2\s*=\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*,"
    r"\s*GOF\s*=\s*([-+]?\d*\.?\d+)"
)
#: `` Other residuals: R = 29.87%, R-bkg = 31.78%, wR-bkg = 35.95% wRmin = 5.81%``
_OTHER_RESID = re.compile(
    r"Other residuals:\s*R\s*=\s*([-+]?\d*\.?\d+)%"
    r"(?:.*?wRmin\s*=\s*([-+]?\d*\.?\d+)%)?"
)
#: `` Number of function calls: 7 No. of observations: 3751 No. of parameters: 13 ...``
_N_OBS = re.compile(r"No\. of observations:\s*(\d+)\s+No\. of parameters:\s*(\d+)")
#: `` New unit cell:`` header followed by a ``values: a b c alpha beta gamma Volume`` row.
_CELL_VALUES = re.compile(
    r"New unit cell:\s*\n\s*names\s*:.*?\n\s*values\s*:\s*"
    r"([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)\s+"
    r"([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)"
)
#: `` Phase fraction  :     6.2951, sig ... Weight fraction  :  0.95814, sig ...``
_WT_FRAC = re.compile(
    r"Phase fraction\s*:\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)[^W]*?"
    r"Weight fraction\s*:\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)"
)
#: `` names :  Scale  Shift ... `` / `` values:  3.8170  18.9295 ...``
_SAMPLE_PARAM = re.compile(
    r"Sample Parameters:\s*\n.*?names?\s*:\s*Scale\s+Shift.*?\n"
    r"\s*values?\s*:\s*([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)",
    re.DOTALL,
)


@dataclass
class LstSummary:
    """Parsed contents of a GSAS-II ``.lst`` refinement log."""

    rwp_pct: float | None = None
    rp_pct: float | None = None
    rexp_pct: float | None = None
    gof: float | None = None
    chi2_sum: float | None = None
    n_obs: int | None = None
    n_params: int | None = None
    scale: float | None = None
    shift: float | None = None
    wavelength: float | None = None
    phases: dict[str, dict[str, Any]] = field(default_factory=dict)


def parse_lst(text: str | Path) -> LstSummary:
    """Parse a GSAS-II ``.lst`` refinement log.

    Parameters
    ----------
    text:
        Path to a ``.lst`` file, or the file contents as a string.

    Returns
    -------
    LstSummary
        Profile R-factors (percent), refined per-phase cells / weight
        fractions, histogram scale / shift.
    """
    content = _read_text(text)
    s = LstSummary()

    m = _WR_LINE.search(content)
    if m:
        s.rwp_pct = float(m.group(1))
        s.chi2_sum = float(m.group(2))
        s.gof = float(m.group(3))

    m = _OTHER_RESID.search(content)
    if m:
        s.rp_pct = float(m.group(1))
        if m.group(2) is not None:
            s.rexp_pct = float(m.group(2))

    m = _N_OBS.search(content)
    if m:
        s.n_obs = int(m.group(1))
        s.n_params = int(m.group(2))

    # Take the LAST Sample-Parameters block: GSAS-II prints an initial
    # (pre-refinement) block early in the log and a final (refined, with
    # esds) block near the end; the latter is what we want to back-fill.
    sp = _SAMPLE_PARAM.findall(content)
    if sp:
        s.scale = float(sp[-1][0])
        s.shift = float(sp[-1][1])

    # wavelength: instrument names/values block.  The names line lists
    # 'Lam1' / 'Lam2' (Cu Kα1/Kα2 tube wavelengths) and the following
    # 'value :' line carries the numbers in the same column order.
    wl = re.search(
        r"Lam1\s+Lam2[^\n]*\n\s*value\s*:\s*"
        r"[-+]?\d*\.?\d+\s+[-+]?\d*\.?\d+\s+"
        r"([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)",
        content,
    )
    if wl:
        s.wavelength = float(wl.group(1))

    # --- per-phase structure blocks: 'Result for phase: <name>' ----------
    for block in re.split(r"Result for phase:\s+", content)[1:]:
        name = block.splitlines()[0].strip()
        info: dict[str, Any] = {}
        cm = _CELL_VALUES.search(block)
        if cm:
            a, b, c, al, be, ga, vol = (float(x) for x in cm.groups())
            info["cell"] = CellParams(a=a, b=b, c=c, alpha=al, beta=be, gamma=ga)
            info["volume"] = vol
        s.phases.setdefault(name, {})
        s.phases[name].update(info)

    # --- per-phase quantitative blocks: 'Phase: <name> in histogram:' -----
    qblocks = re.split(r"Phase:\s+([^:\n]+?)\s+in histogram:", content)
    for i in range(1, len(qblocks) - 1, 2):
        name = qblocks[i].strip()
        body = qblocks[i + 1]
        wm = _WT_FRAC.search(body)
        if wm:
            s.phases.setdefault(name, {})
            s.phases[name]["phase_fraction"] = float(wm.group(1))
            s.phases[name]["weight_fraction"] = float(wm.group(2))

    return s


# ---------------------------------------------------------------------------
# refined CIF parsing
# ---------------------------------------------------------------------------
def parse_cif(text: str | Path) -> dict[str, Any]:
    """Parse a GSAS-II refined CIF (``*_new.cif``).

    Extracts the unit cell, space-group symbol, chemical formula and the
    atom loop (label, element, fractional x/y/z, occupancy, ``U_iso``).

    Returns
    -------
    dict
        Keys: ``cell`` (:class:`CellParams`), ``space_group``, ``formula``,
        ``atoms`` (list of dicts).
    """
    content = _read_text(text)

    def scalar(tag: str) -> str | None:
        m = re.search(rf"_{re.escape(tag)}\s+['\"]?([^'\n#]+?)['\"]?\s*(?:\n|$)", content)
        return m.group(1).strip() if m else None

    def num(tag: str) -> float | None:
        v = scalar(tag)
        return float(v) if v is not None else None

    a = num("cell_length_a")
    cell = CellParams(
        a=a if a is not None else 0.0,
        b=num("cell_length_b") or 0.0,
        c=num("cell_length_c") or 0.0,
        alpha=num("cell_angle_alpha") or 90.0,
        beta=num("cell_angle_beta") or 90.0,
        gamma=num("cell_angle_gamma") or 90.0,
    )
    sg = scalar("symmetry_space_group_name_H-M")
    formula = scalar("chemical_formula_sum") or ""
    phase_name = scalar("pd_phase_name")

    # atom loop: locate the header, then read data rows until a blank/next loop
    atoms: list[dict[str, Any]] = []
    header = re.search(r"loop_\s*\n((?:\s*_atom_site_\w+\s*\n)+)", content)
    if header:
        columns = [c.strip() for c in header.group(1).splitlines() if c.strip()]
        idx = {col: i for i, col in enumerate(columns)}
        start = header.end()
        for line in content[start:].splitlines():
            line = line.strip()
            if not line or line.startswith("loop_") or line.startswith("_"):
                break
            toks = line.split()
            if len(toks) < len(columns):
                continue

            def get(col: str, tokens: list[str] = toks) -> str | None:
                i = idx.get(col)
                return tokens[i] if i is not None and i < len(tokens) else None

            atoms.append(
                {
                    "label": get("_atom_site_label"),
                    "element": get("_atom_site_type_symbol"),
                    "fract_x": float(get("_atom_site_fract_x") or 0.0),
                    "fract_y": float(get("_atom_site_fract_y") or 0.0),
                    "fract_z": float(get("_atom_site_fract_z") or 0.0),
                    "occupancy": float(get("_atom_site_occupancy") or 1.0),
                    "b_iso": float(get("_atom_site_U_iso_or_equiv") or 0.0),
                }
            )

    return {
        "cell": cell,
        "space_group": sg,
        "formula": formula,
        "phase_name": phase_name,
        "atoms": atoms,
    }


# ---------------------------------------------------------------------------
# .prf residual profile parsing
# ---------------------------------------------------------------------------
def parse_prf(text: str | Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Parse a residual profile (2θ / Yobs / Ycalc / residual).

    Parameters
    ----------
    text:
        Path to a ``.prf`` file or its contents.  Lines beginning with ``#``
        are treated as comments.  Whitespace-separated columns are
        ``2θ(deg)  Yobs  Ycalc  residual(obs−calc)``.

    Returns
    -------
    tuple of ndarray
        ``(two_theta, y_obs, y_calc, residual)`` all 1-D float arrays.
    """
    content = _read_text(text)
    cols: list[list[float]] = [[], [], [], []]
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        try:
            vals = [float(x) for x in parts[:4]]
        except ValueError:
            continue
        for i in range(4):
            cols[i].append(vals[i])
    arrays = tuple(np.asarray(c, dtype=np.float64) for c in cols)
    if arrays[0].size == 0:
        raise ValueError("no data rows found in .prf")
    return arrays  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# .gpx parsing (best effort)
# ---------------------------------------------------------------------------
def parse_gpx(path: str | Path) -> dict[str, Any]:
    """Best-effort read of refined scale / cell / shift from a ``.gpx``.

    The ``.gpx`` written by this GSAS-II version is a binary *pickle* (not a
    text dict), so it can only be loaded when GSAS-II's Python package is
    importable.  When it is not, an empty dict is returned and callers fall
    back to the values already present in the ``.lst`` / refined CIF.

    Returns
    -------
    dict
        ``{'scale':..., 'shift':..., 'cell_by_phase':{...}}`` or ``{}`` when
        GSAS-II is unavailable.
    """
    p = Path(path)
    if not p.exists():
        return {}
    try:  # pragma: no cover - only exercised with GSAS-II installed
        import sys

        sys.path.insert(0, r"C:\gsas2main\GSAS-II")
        from GSASII import GSASIIscriptable as G2sc

        proj = G2sc.G2Project(gpxfile=str(p))
        out: dict[str, Any] = {}
        for h in proj.histograms():
            try:
                sp = h["Sample Parameters"]
                out["scale"] = float(sp["Scale"][0])
                out["shift"] = float(sp["Shift"][0])
            except Exception:
                pass
        cells = {}
        for ph in proj.phases():
            with contextlib.suppress(Exception):
                cells[ph.name] = ph.get_cell()
        if cells:
            out["cell_by_phase"] = cells
        return out
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Aggregated outcome
# ---------------------------------------------------------------------------
@dataclass
class RefinedPhaseInfo:
    """A phase back-filled with its refined structure.

    Attributes
    ----------
    phase:
        :class:`~xinmatch.core.model.phase.Phase` whose ``entry.cell`` /
        ``entry.space_group`` have been updated from the refined CIF, and
        whose ``scale_factor`` / ``weight_fraction`` / ``two_theta_shift``
        carry the refined values.
    atoms:
        Parsed atom records (coords / occupancy / ``B_iso``) from the CIF.
    """

    phase: Phase
    atoms: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Gsas2RefineOutcome:
    """Aggregated result of parsing a GSAS-II refinement.

    Attributes
    ----------
    r_factors:
        :class:`~xinmatch.core.report.report_model.RFactorSection`
        (fractions, not percent).
    gof:
        Goodness of fit ``sqrt(reduced χ²)`` as printed by GSAS-II.
    observed_pattern, fitted_pattern, residual_pattern:
        Patterns on the ``.prf`` 2θ grid (intensity = Yobs / Ycalc /
        obs−calc respectively).
    refined_phases:
        Back-filled :class:`RefinedPhaseInfo` list.
    raw:
        The parsed :class:`LstSummary` (for diagnostics).
    refined_cif_paths:
        Paths of the refined phase CIFs (``*_new.cif``) parsed into
        :attr:`refined_phases`, in the same order.  Empty when no CIFs were
        supplied to :func:`parse_refinement`.  Downstream consumers (e.g. the
        3D structure viewer) load these files to show the *refined* structure
        rather than the pre-refinement COD entry.
    """

    r_factors: RFactorSection
    gof: float | None
    observed_pattern: Pattern
    fitted_pattern: Pattern
    residual_pattern: Pattern
    refined_phases: list[RefinedPhaseInfo]
    raw: LstSummary
    refined_cif_paths: list[Path] = field(default_factory=list)


def _read_text(text: str | Path) -> str:
    if isinstance(text, (str, Path)) and Path(text).exists():
        return Path(text).read_text(encoding="utf-8", errors="replace")
    return str(text)


def _build_patterns(
    two_theta: np.ndarray,
    y_obs: np.ndarray,
    y_calc: np.ndarray,
    residual: np.ndarray,
    wavelength: float | None,
) -> tuple[Pattern, Pattern, Pattern]:
    step = float(np.diff(two_theta).mean()) if two_theta.size > 1 else None
    wl = wavelength if wavelength else 1.5406
    common = dict(wavelength=wl, step=step)
    observed = Pattern(two_theta.copy(), y_obs.copy(), metadata={"source": "gsas2_prf"})
    fitted = Pattern(
        two_theta.copy(), y_calc.copy(), metadata={"source": "gsas2_prf_calc"}, **common
    )
    residual_pat = Pattern(
        two_theta.copy(), residual.copy(), metadata={"source": "gsas2_prf_diff"}, **common
    )
    return observed, fitted, residual_pat


def parse_refinement(
    lst: str | Path,
    prf: str | Path,
    *,
    cifs: list[str | Path] | None = None,
    gpx: str | Path | None = None,
) -> Gsas2RefineOutcome:
    """Top-level API: aggregate all GSAS-II outputs into an outcome object.

    Parameters
    ----------
    lst:
        Path to the ``.lst`` refinement log (or its text).
    prf:
        Path to the ``.prf`` residual profile (or its text).
    cifs:
        Optional iterable of refined-CIF paths (``*_new.cif``).  Each is
        parsed and matched to a phase block in the ``.lst`` by formula /
        name.
    gpx:
        Optional path to the ``.gpx`` (best-effort; used only to refine the
        histogram scale / shift when GSAS-II is importable).
    """
    summary = parse_lst(lst)
    two_theta, y_obs, y_calc, residual = parse_prf(prf)
    observed, fitted, residual_pat = _build_patterns(
        two_theta, y_obs, y_calc, residual, summary.wavelength
    )

    # RFactors (percent -> fraction)
    rwp = summary.rwp_pct / 100.0 if summary.rwp_pct is not None else None
    rp = summary.rp_pct / 100.0 if summary.rp_pct is not None else None
    rexp = summary.rexp_pct / 100.0 if summary.rexp_pct is not None else None
    # RFactorSection.chi2 follows residuals.py: reduced chi^2 = GOF^2.
    chi2 = summary.gof**2 if summary.gof is not None else None
    r_factors = RFactorSection(rwp=rwp, rp=rp, rexp=rexp, chi2=chi2)

    gpx_info = parse_gpx(gpx) if gpx else {}
    scale = gpx_info.get("scale", summary.scale)
    shift = gpx_info.get("shift", summary.shift) or 0.0

    # --- build refined phases from CIFs, enriched by .lst per-phase data ----
    refined_phases: list[RefinedPhaseInfo] = []
    cif_list = list(cifs or [])
    for cif_path in cif_list:
        cif = parse_cif(cif_path)
        cell = cif["cell"]
        # override cell with the (more precise) value from the .lst if present
        phase_lst = _match_lst_phase(summary.phases, cif)
        if phase_lst and "cell" in phase_lst:
            cell = phase_lst["cell"]
        entry = Entry(
            entry_id=Path(cif_path).stem,
            formula=cif["formula"],
            d_spacings=np.empty(0),
            intensities=np.empty(0),
            mineral_name=_cif_phase_name(cif_path),
            cell=cell,
            space_group=cif["space_group"],
        )
        wf = phase_lst.get("weight_fraction") if phase_lst else None
        refined_phases.append(
            RefinedPhaseInfo(
                phase=Phase(
                    entry=entry,
                    scale_factor=float(scale) if scale is not None else 1.0,
                    two_theta_shift=float(shift),
                    weight_fraction=float(wf) if wf is not None else None,
                ),
                atoms=cif["atoms"],
            )
        )

    return Gsas2RefineOutcome(
        r_factors=r_factors,
        gof=summary.gof,
        observed_pattern=observed,
        fitted_pattern=fitted,
        residual_pattern=residual_pat,
        refined_phases=refined_phases,
        raw=summary,
        refined_cif_paths=[Path(c) for c in cif_list],
    )


def _match_lst_phase(phases: dict[str, dict[str, Any]], cif: dict[str, Any]) -> dict[str, Any]:
    """Best-effort match of a parsed CIF to a .lst phase block.

    Prefers an exact match on ``_pd_phase_name`` (e.g. ``ZnO`` vs
    ``Result for phase: ZnO``).  Falls back to element-token overlap between
    the CIF formula and the phase name, then to the first phase block.
    """
    name = (cif.get("phase_name") or "").strip()
    if name and name in phases:
        return phases[name]
    formula_tokens = set(re.findall(r"[A-Z][a-z]?", cif.get("formula", "")))
    for pname, info in phases.items():
        name_tokens = set(re.findall(r"[A-Z][a-z]?", pname))
        if formula_tokens and formula_tokens & name_tokens:
            return info
    return next(iter(phases.values()), {})


def _cif_phase_name(cif_path: str | Path) -> str | None:
    stem = Path(cif_path).stem
    return stem.replace("_new", "")
