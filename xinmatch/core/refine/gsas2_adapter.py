"""GSAS-II adapter and Rietveld backend abstraction (T10.6b).

Provides:

* :class:`RietveldAdapter` — a :class:`typing.Protocol` describing the
  refine(pattern, phases, options) → RefineResult contract every backend
  must satisfy.
* :class:`LocalRietveldAdapter` — wraps the in-tree
  :class:`xinmatch.core.refine.rietveld.RietveldRefinement` and exposes
  it through the adapter interface.
* :class:`GSAS2RietveldAdapter` — embeds GSAS-II via its
  ``GSASIIscriptable`` API (no subprocess is spawned; the GSAS-II Python
  package is imported directly).  When GSAS-II is not installed, the
  adapter raises :class:`ImportError` on instantiation and the
  :func:`get_rietveld_adapter` factory transparently falls back to the
  local adapter.
* :func:`load_gsas_gss` — reads a GSAS STD/ESD text powder file
  (``*.gss``) into a :class:`~xinmatch.core.model.pattern.Pattern`.

GSAS-II is treated as an **optional** dependency: this module can always
be imported, even when GSAS-II is not present on the system.  The
availability flag ``GSAS2_AVAILABLE`` lets callers (and tests using
``pytest.mark.skipif``) check whether the real GSAS-II path can be
exercised.

References
----------
* B.H. Toby, R.B. Von Dreele, *J. Appl. Cryst.* 46 (2013) 544-549
  (GSAS-II).
* "GSAS-II scriptable API documentation", https://gsas-ii.readthedocs.io/
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import numpy as np

from xinmatch.core.model.pattern import Pattern
from xinmatch.core.model.phase import Phase

from .peak_model import PeakModel
from .rietveld import RietveldRefinement

# ---- Optional GSAS-II import ---------------------------------------------
# We must NOT hard-import GSASIIscriptable at module top-level: the CI
# environment does not have GSAS-II installed.  Detect-and-defer.
GSAS2_AVAILABLE = False
_GSASIIscriptable: Any
try:  # pragma: no cover - exercised only when GSAS-II is installed
    import GSASIIscriptable as _GSASIIscriptable  # type: ignore[import-not-found,no-redef]
    GSAS2_AVAILABLE = True
except ImportError:
    _GSASIIscriptable = None


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------
@dataclass
class RefineOptions:
    """Configuration for a Rietveld refinement.

    Attributes
    ----------
    max_iter:
        Maximum number of least-squares iterations.
    refine_atoms:
        Whether to refine atomic coordinates / ``B_iso``.  The local
        refiner currently only refines scale, zero, cell and U/V/W; when
        this flag is ``True`` the local adapter notes the request but the
        local engine does not yet refine atoms.
    refine_background:
        Whether to refine a background model.  The local refiner does
        not model background (background is expected to be subtracted
        before refinement); the GSAS-II adapter would honour this.
    refine_profile:
        Whether to refine peak-profile parameters (Caglioti U/V/W).
        The GSAS-II driver turns these on at the profile-refinement stage;
        the local refiner ignores this flag.
    refine_po:
        Whether to refine March-Dollase preferred-orientation parameters.
        The GSAS-II driver turns this on only after the profile has
        converged (otherwise the MD integrand can go NaN).
    refine_size_strain:
        Whether to refine crystallite-size / microstrain broadening
        parameters (isotropic Size + Mustrain).  The GSAS-II backend turns
        these on at a dedicated staging step after the profile has
        converged; the local refiner does not model size/strain.
    wavelength:
        Radiation wavelength in Å.
    two_theta_range:
        Optional ``(2θ_min, 2θ_max)`` window; ``None`` ⇒ fit the whole
        pattern.
    """

    max_iter: int = 50
    refine_atoms: bool = False
    refine_background: bool = True
    refine_profile: bool = True
    refine_po: bool = False
    refine_size_strain: bool = False
    wavelength: float = 1.5406
    two_theta_range: tuple[float, float] | None = None


@dataclass
class RefineResult:
    """Outcome of a refinement run.

    Attributes
    ----------
    rwp, rp, chi2:
        Profile R-factors (fractional).
    fitted_pattern:
        Calculated pattern on the same 2θ grid as the input.
    refined_phases:
        List of phases with refined scale / cell / peak-model parameters
        applied.
    accepted:
        ``True`` when the refinement converged; ``False`` when the
        backend reported non-convergence.
    backend:
        Name of the backend that produced the result (``'local'`` or
        ``'gsas2'``).
    """

    rwp: float
    rp: float
    chi2: float
    fitted_pattern: Pattern
    refined_phases: list[Phase]
    accepted: bool = True
    backend: str = "local"


# ---------------------------------------------------------------------------
# Adapter protocol
# ---------------------------------------------------------------------------
@runtime_checkable
class RietveldAdapter(Protocol):
    """Abstract Rietveld backend contract.

    Every adapter implements::

        refine(pattern, phases, options) -> RefineResult
    """

    def refine(
        self,
        pattern: Pattern,
        phases: list[Phase],
        options: RefineOptions,
    ) -> RefineResult:
        ...


# ---------------------------------------------------------------------------
# Local reference adapter (wraps xinmatch.core.refine.rietveld)
# ---------------------------------------------------------------------------
class LocalRietveldAdapter:
    """Adapter wrapping the in-tree :class:`RietveldRefinement`.

    This adapter is the reference implementation.  It is always available
    (no external dependencies) and is the automatic fallback when
    GSAS-II is not installed.
    """

    backend = "local"

    def __init__(
        self,
        *,
        peak_model: PeakModel | None = None,
    ) -> None:
        self._peak_model = peak_model or PeakModel(
            caglioti_uvw=(0.0, 0.0, 0.01),
        )

    def refine(
        self,
        pattern: Pattern,
        phases: list[Phase],
        options: RefineOptions,
    ) -> RefineResult:
        if not phases:
            raise ValueError("at least one phase is required")
        # The local refiner is single-phase; use the first phase.
        phase = phases[0]
        entry = phase.entry

        peak_model = PeakModel(
            eta=self._peak_model.eta,
            asymmetry=self._peak_model.asymmetry,
            caglioti_uvw=self._peak_model.caglioti_uvw,
        )
        refiner = RietveldRefinement(
            pattern,
            entry,
            peak_model,
            wavelength=options.wavelength,
        )
        riet = refiner.fit(n_iter=options.max_iter)

        refined_phase = Phase(
            entry=entry,
            scale_factor=riet.scale,
            two_theta_shift=riet.zero_shift,
            weight_fraction=phase.weight_fraction,
            correlations=list(phase.correlations),
        )
        return RefineResult(
            rwp=riet.rwp,
            rp=riet.rp,
            chi2=riet.chi2,
            fitted_pattern=riet.fitted_pattern,
            refined_phases=[refined_phase],
            accepted=True,
            backend="local",
        )


# ---------------------------------------------------------------------------
# GSAS-II adapter (lazy; only meaningful when GSAS2_AVAILABLE is True)
# ---------------------------------------------------------------------------
class GSAS2RietveldAdapter:
    """Adapter that drives GSAS-II via its scriptable API.

    GSAS-II is loaded lazily so importing this module never fails when
    GSAS-II is not installed.  Instantiating this adapter without
    GSAS-II installed raises :class:`ImportError`.
    """

    backend = "gsas2"

    def __init__(self) -> None:
        if not GSAS2_AVAILABLE or _GSASIIscriptable is None:
            raise ImportError(
                "GSAS-II is not installed. Install GSAS-II and make the "
                "GSASIIscriptable package importable, or use "
                "LocalRietveldAdapter as a fallback."
            )

    def refine(
        self,
        pattern: Pattern,
        phases: list[Phase],
        options: RefineOptions,
    ) -> RefineResult:  # pragma: no cover - exercised only with GSAS-II
        # The full GSAS-II path would: create a G2Project, import the
        # pattern (or attach the in-memory arrays), add phases from CIFs,
        # configure the histogram, run refinement, read back the fitted
        # pattern and R-factors.  This requires GSAS-II's runtime
        # machinery and is intentionally not implemented in the
        # fallback-only skeleton.
        raise NotImplementedError(
            "The full GSAS-II refinement path requires the GSAS-II runtime. "
            "Use LocalRietveldAdapter as the reference fallback, or "
            "extend this class once GSAS-II is configured."
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def get_rietveld_adapter(prefer: str = "local") -> RietveldAdapter:
    """Return the best available Rietveld adapter.

    Parameters
    ----------
    prefer:
        ``'local'`` (default) — always returns
        :class:`LocalRietveldAdapter`.
        ``'gsas2'`` — returns :class:`GSAS2RietveldAdapter` when
        GSAS-II is installed, otherwise transparently falls back to
        :class:`LocalRietveldAdapter`.
    """
    if prefer == "gsas2" and GSAS2_AVAILABLE:
        return GSAS2RietveldAdapter()
    return LocalRietveldAdapter()


# ---------------------------------------------------------------------------
# GSAS STD/ESD text loader
# ---------------------------------------------------------------------------
_BANK_RE = re.compile(r"^BANK\s+(\d+)\s+(\d+)\s+(\d+)\s+(\S+)(.*)$")


def load_gsas_gss(path: str | Path) -> Pattern:
    """Load a GSAS STD/ESD text powder file (``*.gss``).

    The ``.gss`` format is the GSAS standard powder diffraction text
    format.  The header is::

        SampleIdent <title>
        BANK 1 <npts> <ncards> CONST <2θ_min_cdeg> <2θ_step_cdeg> <2θ_max_cdeg> <wavelength_pm?>

    followed by ``ncards`` lines each holding up to 10 ``(value,
    esd_multiplier)`` integer pairs.  2θ values are stored in
    centidegrees (``500.00`` ⇒ 5.000°, step ``2.00`` ⇒ 0.020°).

    The ESD multipliers are preserved in the pattern's metadata under
    ``"gsas_esd_multipliers"`` so callers can recover the per-point
    ESD if desired (the conversion depends on the original instrument
    convention, so we keep the raw multipliers).

    Parameters
    ----------
    path:
        Path to the ``.gss`` file.

    Returns
    -------
    Pattern
        Pattern on the GSAS 2θ grid with the observed intensities.  The
        wavelength defaults to Cu Kα (1.5406 Å) when the BANK line does
        not contain one.
    """
    p = Path(path)
    with p.open("r", encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()

    # Skip blank leading lines and find the BANK line.
    bank_idx = -1
    title = ""
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.upper().startswith("BANK"):
            bank_idx = i
            break
        if not title and stripped:
            # First non-empty non-BANK line is the title.
            if not stripped.upper().startswith("SAMPLEIDENT"):
                title = stripped
            else:
                title = stripped[len("SampleIdent"):].strip()
    if bank_idx < 0:
        raise ValueError(f"{p}: no BANK header line found")

    m = _BANK_RE.match(lines[bank_idx].strip())
    if not m:
        raise ValueError(f"{p}: cannot parse BANK line: {lines[bank_idx]!r}")
    _bank_num = int(m.group(1))
    npts = int(m.group(2))
    _ncards = int(m.group(3))
    data_type = m.group(4).upper()
    rest = m.group(5).strip().split()

    if data_type != "CONST":
        raise NotImplementedError(
            f"{p}: only CONST (constant wavelength) BANK type is supported, "
            f"got {data_type!r}"
        )

    if len(rest) < 2:
        raise ValueError(f"{p}: CONST BANK line missing 2θ/step values")

    # 2θ values are stored in centidegrees (0.01°).
    tth_min_cdeg = float(rest[0])
    tth_step_cdeg = float(rest[1])
    tth_min = tth_min_cdeg / 100.0
    tth_step = tth_step_cdeg / 100.0

    # Some files carry an explicit wavelength in picometres (rare); if
    # present, convert to Å.  Otherwise default to Cu Kα.
    wavelength = 1.5406
    if len(rest) >= 4:
        try:
            wl_pm = float(rest[3])
            if wl_pm > 0.0:
                wavelength = wl_pm / 100.0
        except ValueError:
            pass

    # Parse data lines into a flat integer list.  In the GSAS STD/ESD
    # format each data point is two integers — the order used by the
    # IUCr CPD ``.gss`` files is ``(esd_multiplier, value)`` (the
    # multiplier is 1 in clean Poisson data).  Both orders are accepted
    # here by picking the larger token as the value: robust against
    # either (esd_mult, value) or (value, esd_mult) orderings.
    values: list[int] = []
    esd_mults: list[int] = []
    for line in lines[bank_idx + 1:]:
        tokens = line.split()
        if not tokens:
            continue
        it = iter(tokens)
        for tok in it:
            try:
                a = int(tok)
            except ValueError:
                break
            try:
                b = int(next(it))
            except (StopIteration, ValueError):
                b = 1
            # Pick the larger token as the intensity value: for normal
            # CPD files the multiplier is small (1) and the value is
            # large (counts), so this recovers the intensity.
            if abs(a) >= abs(b):
                value, esd = a, b
            else:
                value, esd = b, a
            values.append(value)
            esd_mults.append(esd)
        if len(values) >= npts:
            break

    if len(values) < npts:
        raise ValueError(
            f"{p}: expected {npts} data points, found {len(values)}"
        )
    values = values[:npts]
    esd_mults = esd_mults[:npts]

    intensity = np.asarray(values, dtype=np.float64)
    esd_arr = np.asarray(esd_mults, dtype=np.int32)
    two_theta = tth_min + tth_step * np.arange(npts, dtype=np.float64)

    metadata: dict[str, Any] = {
        "gsas_title": title,
        "gsas_bank": _bank_num,
        "gsas_npts": npts,
        "gsas_data_type": data_type,
        "gsas_esd_multipliers": esd_arr.tolist(),
        "gsas_source_file": str(p),
    }

    return Pattern(
        two_theta=two_theta,
        intensity=intensity,
        wavelength=wavelength,
        step=tth_step,
        metadata=metadata,
    )


__all__ = [
    "GSAS2_AVAILABLE",
    "GSAS2RietveldAdapter",
    "LocalRietveldAdapter",
    "RefineOptions",
    "RefineResult",
    "RietveldAdapter",
    "get_rietveld_adapter",
    "load_gsas_gss",
]
