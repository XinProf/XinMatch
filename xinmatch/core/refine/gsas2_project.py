r"""GSAS-II project constructor (T10.8).

Turns a XinMatch :class:`~xinmatch.core.model.pattern.Pattern` plus a list of
selected :class:`~xinmatch.core.model.phase.Phase` (each backed by a CIF) and
a :class:`~xinmatch.core.refine.gsas2_adapter.RefineOptions` into a project that
GSAS-II can run end-to-end.

Match! functionality mapping
-----------------------------
* Match! *Quantify -> Rietveld* (``docs/Rietveld.md``) is the GUI equivalent:
  a full-pattern least-squares fit of observed vs. calculated profile.  Match!
  drives FullProf/GSAS-II as an external engine; XinMatch instead emits a
  self-contained GSAS-II project (``.gpx``) plus a standalone driver script.
* Match! *Rietveld parameter turn-on* (``docs/Rietveld_ParTurnOn.md``,
  ``docs/Rietveld_Auto_Par.md``) decides *which* parameters are refined in
  which order.  The staged protocol here (scale -> background -> cell ->
  zero-shift -> optional atoms) mirrors Match!'s "auto parameter" sequence and
  FullProf's default turn-on (``docs/refinements_FullProf.md``).
* The background model is a Chebyshev polynomial, exactly as in GSAS-II and
  Match!'s Rietveld dialog.

Algorithm / format sources
--------------------------
* B.H. Toby, R.B. Von Dreele, "GSAS-II: The Genesis of a Modern Open-Source
  All Purpose Crystallography Software System", *J. Appl. Cryst.* **46**
  (2013) 544-549.
* GSAS-II scriptable API documentation,
  https://gsas-ii.readthedocs.io/en/latest/GSASIIscriptable.html
  (``G2Project``, ``add_powder_histogram``, ``add_phase``, ``set_refinement``,
  ``refine``, ``save``; residual ``hist.residuals['wR']`` = Rwp).
* The GSAS STD/ESD ``.gss`` powder format is parsed in
  :func:`xinmatch.core.refine.gsas2_adapter.load_gsas_gss`; this module emits a
  compatible ``.gss`` when the input pattern did not come from one.

Design notes
------------
GSAS-II is an **optional** heavy dependency.  This module imports cleanly in
environments that do not have it (the XinMatch dev interpreter has no
GSAS-II).  Real refinement is always performed in a *separate* Python process
(``C:\gsas2main\python.exe`` by default, overridable via ``GSAS2_PYTHON`` /
``GSAS2_HOME``) using a generated, self-contained driver script, so the XinMatch
process never has to link against GSAS-II's compiled binaries.

When GSAS-II cannot be located, :func:`build_gsas2_project` still writes the
driver script + input manifest (so the project can be launched later on a
GSAS-II machine) and then raises :class:`Gsas2NotAvailableError` -- it never
crashes bare.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from xinmatch.core.model.pattern import Pattern
from xinmatch.core.model.phase import Phase

from .gsas2_adapter import RefineOptions

__all__ = [
    "Gsas2NotAvailableError",
    "Gsas2Runtime",
    "Gsas2Project",
    "locate_gsas2",
    "build_gsas2_project",
    "pattern_to_gss",
    "GSAS2_RUNTIME",
    "GSAS2_AVAILABLE",
]


# ---------------------------------------------------------------------------
# Custom error
# ---------------------------------------------------------------------------
class Gsas2NotAvailableError(RuntimeError):
    """Raised when a GSAS-II run was requested but no usable GSAS-II
    installation could be located.

    The driver script + input manifest have already been written to the work
    directory by the time this is raised, so the project can still be launched
    manually on a machine that has GSAS-II.
    """


# ---------------------------------------------------------------------------
# GSAS-II runtime discovery
# ---------------------------------------------------------------------------
@dataclass
class Gsas2Runtime:
    """A located GSAS-II installation.

    Attributes
    ----------
    python:
        Interpreter that can run GSAS-II (must match the compiled-binary ABI).
    source_dir:
        Directory that contains the ``GSASII`` package (added to ``sys.path``
        inside the driver).
    available:
        ``True`` when both files exist.
    """

    python: Path
    source_dir: Path
    available: bool = True

    def driver_env(self) -> dict[str, str]:
        """Environment mapping passed through to the subprocess (PATH etc.)."""
        env = dict(os.environ)
        # Keep the GSAS-II binary dir discoverable even if launched from a
        # stripped environment.
        bin_dir = self.source_dir / "GSASII-bin"
        if bin_dir.is_dir():
            env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
        return env


def _candidate_runtimes() -> list[Gsas2Runtime]:
    """Ordered list of plausible GSAS-II installations.

    Search order:

    1. ``GSAS2_PYTHON`` + ``GSAS2_HOME`` environment overrides.
    2. The default Windows install ``C:\\gsas2main\\python.exe`` with source
       tree ``C:\\gsas2main\\GSAS-II`` (the machine used for T10.8
       validation).
    """
    cands: list[Gsas2Runtime] = []
    env_py = os.environ.get("GSAS2_PYTHON")
    env_home = os.environ.get("GSAS2_HOME")
    if env_py and env_home:
        cands.append(
            Gsas2Runtime(python=Path(env_py), source_dir=Path(env_home))
        )
    default_py = Path(r"C:\gsas2main\python.exe")
    default_home = Path(r"C:\gsas2main\GSAS-II")
    cands.append(Gsas2Runtime(python=default_py, source_dir=default_home))
    return cands


def locate_gsas2() -> Gsas2Runtime:
    """Return the first usable GSAS-II runtime (or an unavailable one).

    A runtime is usable when the interpreter and the ``GSASII`` package
    directory both exist on disk.  No interpreter is launched at discovery time.
    """
    for cand in _candidate_runtimes():
        if cand.python.is_file() and (cand.source_dir / "GSASII").is_dir():
            return cand
    # Nothing usable: return the first candidate flagged unavailable.
    first = _candidate_runtimes()[0]
    return Gsas2Runtime(
        python=first.python, source_dir=first.source_dir, available=False
    )


GSAS2_RUNTIME = locate_gsas2()
GSAS2_AVAILABLE = GSAS2_RUNTIME.available


# ---------------------------------------------------------------------------
# Default instrument parameter (generic Bragg-Brentano Cu Kalpha)
# ---------------------------------------------------------------------------
# A minimal generic X-ray instrument parameter file (Bragg-Brentano, Cu Kalpha
# doublet 1.5405/1.5443 A).  Shipped verbatim from GSAS-II's own test fixture
# INST_XRY.PRM so the constructor is self-contained.  Used when the caller does
# not supply an instrument parameter file.
_DEFAULT_CU_PRM = """\
           123456789012345678901234567890123456789012345678901234567890
INS   BANK      1
INS   HTYPE   PXCR
INS  1 IRAD     3
INS  1 ICONS  1.540500  1.544300       0.0         0       0.7    0       0.5
INS  1I HEAD  XinMatch default Cu Kalpha instrument (Bragg-Brentano)
INS  1I ITYP    0    0.0000  180.0000         1
INS  1PRCF1     3    8      0.01
INS  1PRCF11   2.000000E+00  -2.000000E+00   5.000000E+00   0.100000E+00
INS  1PRCF12   0.000000E+00   0.000000E+00   0.150000E-01   0.150000E-01
"""


# ---------------------------------------------------------------------------
# Pattern -> .gss export (pure python, mirrors load_gsas_gss round-trip)
# ---------------------------------------------------------------------------
def pattern_to_gss(pattern: Pattern, dest: str | Path) -> Path:
    """Write a :class:`Pattern` to a GSAS STD/ESD ``.gss`` file.

    This is the inverse of
    :func:`~xinmatch.core.refine.gsas2_adapter.load_gsas_gss`: 2theta is
    stored in centidegrees, intensities as integer count pairs with an ESD
    multiplier of 1 (Poisson weight ~1/count is applied by GSAS-II on import).

    Parameters
    ----------
    pattern:
        The pattern to export.
    dest:
        Output ``.gss`` path.

    Returns
    -------
    Path
        The written file.
    """
    import numpy as np

    dest = Path(dest)
    tt = np.asarray(pattern.two_theta, dtype=np.float64)
    intensity = np.asarray(pattern.intensity, dtype=np.float64)
    npts = int(tt.size)
    tmin_cdeg = float(tt[0]) * 100.0
    step_cdeg = (
        float(pattern.step) * 100.0
        if pattern.step is not None
        else float((tt[-1] - tt[0]) / max(npts - 1, 1)) * 100.0
    )
    ncards = (npts + 9) // 10  # lines holding 10 ESD/value pairs (20 tokens)

    title = str(pattern.metadata.get("gsas_title", "XinMatch pattern"))
    lines = [f"SampleIdent {title}"]
    # Fixed-column BANK header (80 cols) matching GSAS-II STD/ESD format.
    lines.append(
        "BANK"
        + " " * 4
        + "1"
        + " " * 7
        + f"{npts:>4d}"
        + " " * 7
        + f"{ncards:>3d}"
        + " "
        + "CONST"
        + " " * 8
        + f"{tmin_cdeg:>6.2f}"
        + " " * 6
        + f"{step_cdeg:>4.2f}"
        + " " * 5
        + "0.000"
        + " " * 5
        + "0.000"
    )
    # ESD multiplier 1, then intensity (rounded to integer counts).
    # Each data line is 80 cols: 10 pairs of " 1<intensity:>6d>" (8 chars each).
    for i in range(0, npts, 10):
        chunk = []
        for j in range(i, min(i + 10, npts)):
            val = int(round(max(intensity[j], 0.0)))
            chunk.append(f" 1{val:>6d}")
        lines.append("".join(chunk))
    dest.write_text("\n".join(lines) + "\n", encoding="ascii", errors="replace")
    return dest


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------
@dataclass
class Gsas2Project:
    """Handle to a built (and optionally run) GSAS-II project.

    Attributes
    ----------
    gpx_path:
        Target ``.gpx`` path (exists after a successful run).
    driver_path:
        Self-contained driver script (always written).
    manifest_path:
        JSON input manifest consumed by the driver (always written).
    work_dir:
        Directory holding all generated artifacts.
    phase_names:
        Ordered phase names added to the project.
    runtime:
        The GSAS-II runtime used (or detected as unavailable).
    rwp, rp:
        Residuals after a run (``None`` if not run / not available).
    lst_path:
        GSAS-II output listing (``.lst``) after a run.
    prf_path:
        Residual profile (``.prf``) after a run (``None`` if not produced).
    refined_cifs:
        Refined CIF paths exported for each phase after a run.
    stdout_tail:
        Last lines of the driver stdout (useful for diagnostics).
    """

    gpx_path: Path
    driver_path: Path
    manifest_path: Path
    work_dir: Path
    phase_names: list[str]
    runtime: Gsas2Runtime
    rwp: float | None = None
    rp: float | None = None
    lst_path: Path | None = None
    prf_path: Path | None = None
    refined_cifs: list[Path] = field(default_factory=list)
    stdout_tail: str = ""


# ---------------------------------------------------------------------------
# Driver script (written verbatim into the work directory)
# ---------------------------------------------------------------------------
# This string is executed by the GSAS-II interpreter.  It deliberately uses
# ONLY the standard library + numpy + GSAS-II, because the GSAS-II Python
# (3.13) may not have scipy/gemmi/lmfit installed.  It reads the manifest path
# from argv[1] and writes results JSON to manifest["output_json"].
_DRIVER_SOURCE = '''\
"""Auto-generated GSAS-II driver (T10.8). Do not edit by hand."""
import json
import os
import sys


def main() -> int:
    manifest = json.load(open(sys.argv[1], "r", encoding="utf-8"))
    sys.path.insert(0, manifest["gsas2_source_dir"])
    from GSASII import GSASIIscriptable as G2sc

    gpx = G2sc.G2Project(newgpx=manifest["gpx_path"])
    hist = gpx.add_powder_histogram(
        manifest["data_file"],
        manifest["instrument_file"],
        fmthint="GSAS powder",
    )

    phases = []
    for ph in manifest["phases"]:
        phases.append(
            gpx.add_phase(ph["cif_path"], phasename=ph["name"], histograms=[hist])
        )

    # Turn on per-phase scale-factor refinement (HAP = Histogram Associated
    # Parameters).  Without this the scale factors stay at their initial
    # values and weight fractions are meaningless.
    for p in phases:
        p.set_HAP_refinements({"Scale": True})

    # Optional March-Dollase preferred orientation refinement (helps ZnO
    # and other layered/hexagonal phases with strong texture).
    if manifest["options"].get("refine_po", False):
        for p in phases:
            try:
                p.set_HAP_refinements({"PO": True})
            except Exception:
                pass  # not all phases support PO; ignore

    opts = manifest["options"]
    if opts.get("two_theta_range"):
        lo, hi = opts["two_theta_range"]
        hist.set_refinements({"Limits": [float(lo), float(hi)]})

    # Baseline (0 cycles) so we always have a finite starting Rwp.
    gpx.set_Controls("cycles", 0)
    gpx.refine(makeBack=True)

    cycles = max(int(opts.get("max_iter", 20)), 1)

    # Stage 0: scale-only convergence (no background/cell/profile) so that
    # weak minor phases settle before coupled parameters are turned on.
    # This prevents CaF2-scale from diverging into unstable cell refinement.
    gpx.set_Controls("cycles", max(cycles // 2, 5))
    gpx.refine(makeBack=True)

    # Staged turn-on (mirrors Match! auto parameters / FullProf default):
    #   scale -> background -> cell -> profile(U/V/W) -> atoms(XU) -> zero-shift.
    if opts.get("refine_background", True):
        hist.set_refinements({"Background": {"no. coeffs": 8, "refine": True}})
        gpx.set_Controls("cycles", max(cycles // 2, 5))
        gpx.refine(makeBack=True)

    for p in phases:
        p.set_refinements({"Cell": True})
    gpx.set_Controls("cycles", max(cycles // 2, 2))
    gpx.refine(makeBack=True)

    if opts.get("refine_profile", True):
        hist.set_refinements({"Instrument Parameters": ["U", "V", "W"]})
        gpx.set_Controls("cycles", max(cycles // 2, 2))
        gpx.refine(makeBack=True)

    if opts.get("refine_atoms", False):
        for p in phases:
            p.set_refinements({"Atoms": {"all": "XU"}})
        gpx.set_Controls("cycles", max(cycles // 2, 2))
        gpx.refine(makeBack=True)

    hist.set_refinements({"Sample Parameters": {"Shift": True}})
    gpx.set_Controls("cycles", cycles)
    gpx.refine(makeBack=True)

    gpx.save()

    # ---- Export residual profile (.prf) for downstream parsing -----------
    gpx_root = os.path.splitext(manifest["gpx_path"])[0]
    prf_path = gpx_root + ".prf"
    x_arr = hist.getdata("x")
    yobs_arr = hist.getdata("yobs")
    ycalc_arr = hist.getdata("ycalc")
    resid_arr = hist.getdata("residual")
    with open(prf_path, "w", encoding="ascii") as fh:
        fh.write("# 2theta  Yobs  Ycalc  residual\\n")
        for i in range(len(x_arr)):
            fh.write(
                f"{float(x_arr[i]):10.4f} {float(yobs_arr[i]):12.2f} "
                f"{float(ycalc_arr[i]):12.2f} {float(resid_arr[i]):12.2f}\\n"
            )

    # ---- Export refined CIFs for each phase ------------------------------
    cif_out_paths = []
    for idx, p in enumerate(phases):
        cif_out = f"{gpx_root}_phase{idx + 1}_new.cif"
        try:
            p.export_CIF(cif_out, quickmode=False)
            cif_out_paths.append(cif_out)
        except Exception:
            pass

    res = hist.residuals
    lst = gpx_root + ".lst"
    out = {
        "success": True,
        "rwp": float(res.get("wR", float("nan"))),
        "rp": float(res.get("R", float("nan"))),
        "gpx_path": manifest["gpx_path"],
        "lst_path": lst if os.path.exists(lst) else None,
        "prf_path": prf_path if os.path.exists(prf_path) else None,
        "refined_cifs": cif_out_paths,
        "n_phases": len(phases),
    }
    json.dump(out, open(manifest["output_json"], "w", encoding="utf-8"))
    print("DRIVER_RESULT " + json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------
def build_gsas2_project(
    pattern: Pattern,
    phases: Sequence[Phase],
    cif_paths: dict[str, str | os.PathLike[str]],
    options: RefineOptions | None = None,
    work_dir: str | os.PathLike[str] = ".",
    project_name: str = "xinmatch_gsas2",
    instrument_file: str | os.PathLike[str] | None = None,
    *,
    run: bool = True,
) -> Gsas2Project:
    """Construct (and optionally run) a GSAS-II Rietveld project.

    Match! equivalent: *Quantify -> Rietveld* with auto parameter turn-on
    (``docs/Rietveld.md``, ``docs/Rietveld_Auto_Par.md``,
    ``docs/refinements_FullProf.md``).

    Parameters
    ----------
    pattern:
        Observed pattern.  If it was produced by
        :func:`~xinmatch.core.refine.gsas2_adapter.load_gsas_gss` its original
        ``.gss`` file is reused; otherwise the pattern is exported to a
        freshly written ``.gss`` in *work_dir*.
    phases:
        Phases present in the sample.  Each phase's ``entry.entry_id`` must
        have an entry in *cif_paths*.
    cif_paths:
        Mapping ``entry_id -> CIF file path``.  The :class:`~xinmatch.core.model.entry.Entry`
        data model has no CIF field, so this mapping is supplied explicitly
        by the caller.
    options:
        Refinement options (max_iter, refine_atoms, refine_background,
        wavelength, two_theta_range).  Reuses
        :class:`~xinmatch.core.refine.gsas2_adapter.RefineOptions`.
    work_dir:
        Where artifacts (data file, instrument file, manifest, driver, .gpx,
        .lst) are written.
    project_name:
        Base name for the ``.gpx`` / driver / manifest files.
    instrument_file:
        Optional GSAS-II instrument parameter (``.prm``/``.inst``).  When
        ``None`` a generic Bragg-Brentano Cu Kalpha parameter file is emitted.
    run:
        If ``True`` (default), launch the driver in the GSAS-II interpreter
        after writing artifacts.  If GSAS-II is not available, raise
        :class:`Gsas2NotAvailableError` (artifacts are still written).

    Returns
    -------
    Gsas2Project
        Handle to the built project.

    Raises
    ------
    ValueError
        If *phases* is empty, a phase has no CIF mapping, or a mapped CIF
        file does not exist (the offending phase/entry is named in the
        message).
    Gsas2NotAvailableError
        If ``run=True`` but no usable GSAS-II installation was found.
    RuntimeError
        If the driver subprocess fails (non-zero exit).
    """
    options = options or RefineOptions()
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)

    if not phases:
        raise ValueError("build_gsas2_project: at least one phase is required")

    # ---- Validate CIF mapping and existence (ValueError, naming phase) -----
    cif_map = {str(k): Path(v) for k, v in cif_paths.items()}
    phase_specs: list[dict[str, Any]] = []
    for ph in phases:
        eid = str(ph.entry.entry_id)
        if eid not in cif_map:
            raise ValueError(
                f"build_gsas2_project: no CIF path given for phase "
                f"entry_id={eid!r} (formula={ph.entry.formula!r}); "
                f"cif_paths must contain an entry for every phase"
            )
        cif = cif_map[eid]
        if not cif.is_file():
            raise ValueError(
                f"build_gsas2_project: CIF file not found for phase "
                f"entry_id={eid!r} (formula={ph.entry.formula!r}): {cif}"
            )
        phase_specs.append({"name": ph.entry.mineral_name or eid, "cif_path": str(cif)})

    # ---- Resolve / export the powder data file -----------------------------
    src_gss = pattern.metadata.get("gsas_source_file")
    data_file = work / f"{project_name}.gss"
    if src_gss and Path(src_gss).is_file():
        shutil.copyfile(src_gss, data_file)
    else:
        pattern_to_gss(pattern, data_file)

    # ---- Resolve / write the instrument parameter file ---------------------
    inst_path = work / f"{project_name}_inst.prm"
    if instrument_file is not None:
        shutil.copyfile(Path(instrument_file), inst_path)
    else:
        inst_path.write_text(_DEFAULT_CU_PRM, encoding="ascii")

    # ---- Locate GSAS-II ----------------------------------------------------
    runtime = locate_gsas2()

    gpx_path = work / f"{project_name}.gpx"
    driver_path = work / f"{project_name}_driver.py"
    manifest_path = work / f"{project_name}_manifest.json"
    output_json = work / f"{project_name}_result.json"

    driver_path.write_text(_DRIVER_SOURCE, encoding="utf-8")

    manifest = {
        "gsas2_source_dir": str(runtime.source_dir),
        "gpx_path": str(gpx_path),
        "data_file": str(data_file),
        "instrument_file": str(inst_path),
        "phases": phase_specs,
        "options": {
            "max_iter": int(options.max_iter),
            "refine_atoms": bool(options.refine_atoms),
            "refine_background": bool(options.refine_background),
            "refine_profile": bool(options.refine_profile),
            "refine_po": bool(options.refine_po),
            "wavelength": float(options.wavelength),
            "two_theta_range": (
                list(options.two_theta_range)
                if options.two_theta_range is not None
                else None
            ),
        },
        "output_json": str(output_json),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    result = Gsas2Project(
        gpx_path=gpx_path,
        driver_path=driver_path,
        manifest_path=manifest_path,
        work_dir=work,
        phase_names=[p["name"] for p in phase_specs],
        runtime=runtime,
    )

    if not run:
        return result

    if not runtime.available:
        raise Gsas2NotAvailableError(
            "GSAS-II is not available on this machine.  The driver script "
            f"({driver_path}) and input manifest ({manifest_path}) have been "
            "written; run them with a GSAS-II-capable interpreter, e.g.:\n"
            f'  {runtime.python} "{driver_path}" "{manifest_path}"'
        )

    # ---- Launch the driver subprocess -------------------------------------
    proc = subprocess.run(
        [str(runtime.python), str(driver_path), str(manifest_path)],
        capture_output=True,
        text=True,
        env=runtime.driver_env(),
        timeout=1800,
    )
    tail = "\n".join((proc.stdout or "").splitlines()[-25:])
    result.stdout_tail = tail
    if proc.returncode != 0:
        raise RuntimeError(
            "GSAS-II driver failed (exit "
            f"{proc.returncode}).\n--- stdout ---\n{tail}\n--- stderr ---\n"
            + "\n".join((proc.stderr or "").splitlines()[-40:])
        )

    if output_json.is_file():
        data = json.loads(output_json.read_text(encoding="utf-8"))
        result.rwp = data.get("rwp")
        result.rp = data.get("rp")
        lst = data.get("lst_path")
        result.lst_path = Path(lst) if lst else None
        prf = data.get("prf_path")
        result.prf_path = Path(prf) if prf else None
        result.refined_cifs = [
            Path(c) for c in data.get("refined_cifs", []) if c
        ]
    return result
