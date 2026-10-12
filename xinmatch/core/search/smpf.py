"""SMPF — Search-Match with Profile Fitting (全谱拟合检索).

SMPF is XinMatch's **full-pattern** retrieval.  Instead of correlating a
discrete peak list (the classical peak-based search-match), SMPF draws a
continuous calculated diffraction profile for each candidate reference
entry, fits an intensity scale + a small set of instrumental / profile
parameters against the *whole* experimental pattern, and ranks candidates
by the resulting goodness of fit (Rwp / GOF).

This is the same conceptual family as the full-pattern search-match offered
by the mainstream commercial XRD packages (hereafter "参考软件" / "对标产品").
The implementation below is a clean-room, from-first-principles build: it
uses only the standard Rietveld / profile-fitting criteria (Rwp, Rexp, GOF;
Young, *The Rietveld Method*) and the analytical pseudo-Voigt profile from
:mod:`xinmatch.core.peak.shapes`.  No proprietary algorithm or code is
reproduced.

Pipeline (top-level :func:`search_match_smpf`)
----------------------------------------------
1. **Candidate pre-screen** (performance-critical): the full COD-scale
   reference DB (~70 k entries) cannot be fitted one-by-one.  We run the
   existing peak-based search (:func:`~xinmatch.core.search.search_match.search_match`)
   on an auto-processed peak list to recall the top ``prescreen_top_n``
   entries; only this subset (~150) goes to the full-pattern refinement.
   The peak-list recall already keeps the truth in its Top-20, so the truth
   survives pre-screening.
2. **Theoretical profile**: each entry's d–I table is converted to 2θ via
   Bragg's law and rendered as area-normalised pseudo-Voigt peaks on the
   experimental grid.  When ``wavelength_kalpha2`` is supplied (real Cu
   data), every reflection is doubled into a Kα1 / Kα2 pair (2:1 intensity).
3. **Per-candidate refinement**: a bounded least-squares fit of
   ``scale · profile(2θ) + b0 + b1·(2θ−50) + b2·(2θ−50)²`` to the *raw*
   experimental spectrum.  Free parameters: scale (≥0), global 2θ shift
   (±``shift_bound``), global FWHM, pseudo-Voigt mixing η, and a quadratic
   background basis.

   **Why fit the background on the raw spectrum instead of pre-subtracting
   it?**  The Rwp weights points by ``w = 1/y``.  Pre-subtracting a
   (necessarily imperfect) background leaves low-intensity residual points
   that ``w = 1/y`` penalises disproportionately, inflating Rwp and
   collapsing the separation between true and wrong phases.  Carrying a
   quadratic background basis inside the least-squares lets the fit absorb
   the smooth background self-consistently, so the low-intensity points
   keep their natural (large) ``y`` and contribute only their (small)
   Poisson/noise weight.  This is the standard profile-fitting choice.

   A global (single) FWHM is used: on typical laboratory Cu data the
   Caglioti width is close to constant over the scanned range, and one
   width is far cheaper / more stable than a 3-parameter U/V/W fit.
4. **Scoring**: Rwp (w = 1/y on positive-intensity points), Rexp, GOF, and a
   monotonic FoM = ``exp(−Rwp/σ_fom)`` mapped into (0, 1].

Determinism: the module is fully deterministic (no random source, no Monte
Carlo).  See ``docs/smpf_mechanism.md`` for the parameter-decision table,
scoring definitions, performance and validation tables.
"""

from __future__ import annotations

import logging
import math
import sqlite3
import time
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import least_squares

from xinmatch.core.model import Entry, Pattern
from xinmatch.core.preprocess.auto_pipeline import auto_process
from xinmatch.core.search.search_match import search_match

logger = logging.getLogger(__name__)

__all__ = [
    "SmpfConfig",
    "expand_reflections",
    "generate_theory_profile",
    "compute_rwp",
    "compute_fom",
    "fit_candidate",
    "search_match_smpf",
]

# Area-normalised pseudo-Voigt peak-height prefactors (identical to the
# analytical shape in xinmatch.core.peak.shapes).  Gaussian height =
# (2/fwhm)·sqrt(ln2/π); Lorentzian height = 2/(π·fwhm).
_LN2 = math.log(2.0)
_GAUSS_H = 2.0 * math.sqrt(_LN2 / math.pi)
_LORENTZ_H = 2.0 / math.pi


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
@dataclass
class SmpfConfig:
    """Tunable knobs for :func:`search_match_smpf`.

    Attributes
    ----------
    prescreen_top_n:
        Number of peak-list-recalled candidates that enter full-pattern
        refinement (default 150; 100–300 practical range).
    top_n:
        Number of final FoM-ranked candidates to return.
    shift_bound:
        Symmetric bound on the fitted global 2θ shift (degrees).
    fwhm_init / fwhm_bounds:
        Initial FWHM and its search bounds (degrees 2θ).
    eta_init / eta_bounds:
        Initial pseudo-Voigt Lorentzian fraction and its bounds in [0, 1].
    fom_sigma:
        σ in the FoM mapping ``FoM = exp(−Rwp/σ)``.  Calibrated so a clean
        synthetic fit (Rwp ≈ 0.08–0.12) gives FoM ≈ 0.6–0.8 while a poor
        fit (Rwp > 0.5) is strongly suppressed (< 0.08).
    window_half_deg:
        Half-width (degrees 2θ) of the local evaluation window around each
        reflection centre.  Bounds the vectorised peak sum to the region
        where a peak actually contributes (≈ shift_bound + a few FWHM),
        which keeps per-candidate refinement fast.
    max_nfev:
        Cap on least-squares function evaluations per candidate.
    """

    prescreen_top_n: int = 150
    top_n: int = 20
    shift_bound: float = 0.3
    fwhm_init: float = 0.2
    fwhm_bounds: tuple[float, float] = (0.08, 0.6)
    eta_init: float = 0.5
    eta_bounds: tuple[float, float] = (0.05, 0.95)
    fom_sigma: float = 0.25
    window_half_deg: float = 1.5
    max_nfev: int = 60


# --------------------------------------------------------------------------- #
# Reflection expansion (Bragg + Kα1/Kα2 doublet)
# --------------------------------------------------------------------------- #
def expand_reflections(
    entry: Entry,
    wavelength_kalpha1: float,
    wavelength_kalpha2: float | None,
    tth_lo: float,
    tth_hi: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Expand an entry's d–I table into (centres, amplitudes) on 2θ.

    Each reflection is placed by Bragg's law using ``wavelength_kalpha1``.
    When ``wavelength_kalpha2`` is not ``None`` the reflection is doubled:
    a Kα1 line at λ1 (full intensity) and a Kα2 line at λ2 (half intensity,
    the conventional 2:1 Kα1:Kα2 ratio).  Reflections whose 2θ falls
    outside ``[tth_lo, tth_hi]`` are dropped.
    """
    if entry.n_peaks == 0:
        return np.empty(0), np.empty(0)
    ds = np.asarray(entry.d_spacings, dtype=np.float64)
    ints = np.asarray(entry.intensities, dtype=np.float64)

    sin_t1 = wavelength_kalpha1 / (2.0 * ds)
    ok1 = (sin_t1 >= -1.0) & (sin_t1 <= 1.0)
    c1 = 2.0 * np.degrees(np.arcsin(sin_t1[ok1]))
    a1 = ints[ok1]

    if wavelength_kalpha2 is not None:
        sin_t2 = wavelength_kalpha2 / (2.0 * ds)
        ok2 = (sin_t2 >= -1.0) & (sin_t2 <= 1.0)
        c2 = 2.0 * np.degrees(np.arcsin(sin_t2[ok2]))
        a2 = ints[ok2] * 0.5
        centres = np.concatenate([c1, c2])
        amps = np.concatenate([a1, a2])
    else:
        centres, amps = c1, a1

    in_range = (centres >= tth_lo - 1.0) & (centres <= tth_hi + 1.0)
    return centres[in_range], amps[in_range]


# --------------------------------------------------------------------------- #
# Theoretical profile (local-window, vectorised per reflection)
# --------------------------------------------------------------------------- #
def generate_theory_profile(
    x: np.ndarray,
    centres: np.ndarray,
    amps: np.ndarray,
    windows: np.ndarray,
    *,
    fwhm: float,
    eta: float,
    shift: float = 0.0,
    scale: float = 1.0,
    bg0: float = 0.0,
    bg1: float = 0.0,
    bg2: float = 0.0,
    x_mid: float = 50.0,
) -> np.ndarray:
    """Calculate a full profile on grid ``x`` for pre-expanded reflections.

    The profile is ``scale · Σ_i amp_i · pv(x − (c_i+shift); fwhm, η)``
    plus a quadratic background ``bg0 + bg1·(x−x_mid) + bg2·(x−x_mid)²``.
    Each reflection is summed only over its precomputed local index window
    ``windows[i] = (lo, hi)``, which keeps the inner loop O(M·W) rather than
    O(M·N).

    Parameters
    ----------
    x:
        2θ grid (degrees), shape ``(N,)``.
    centres, amps:
        Reflection centres (degrees 2θ) and relative integrated intensities.
    windows:
        ``(M, 2)`` int array of ``(lo, hi)`` index slices into ``x``.
    fwhm, eta, shift, scale:
        Global profile parameters.
    bg0, bg1, bg2:
        Quadratic background coefficients.
    x_mid:
        Centre for the background basis.
    """
    t = x - x_mid
    yc = bg0 + bg1 * t + bg2 * t * t
    if centres.size == 0 or scale == 0.0:
        return yc
    gauss_h = _GAUSS_H / fwhm
    lor_h = _LORENTZ_H / fwhm
    for i in range(centres.size):
        lo, hi = int(windows[i, 0]), int(windows[i, 1])
        if hi <= lo:
            continue
        dx = x[lo:hi] - (centres[i] + shift)
        g = np.exp(-4.0 * _LN2 * (dx / fwhm) ** 2)
        lor = 1.0 / (1.0 + 4.0 * (dx / fwhm) ** 2)
        pv = eta * lor_h * lor + (1.0 - eta) * gauss_h * g
        yc[lo:hi] += scale * amps[i] * pv
    return yc


def _reflection_windows(
    x: np.ndarray,
    centres: np.ndarray,
    half_deg: float,
) -> np.ndarray:
    """Build ``(M, 2)`` index windows into ``x`` around each centre."""
    n = x.size
    out = np.zeros((centres.size, 2), dtype=np.intp)
    if centres.size == 0:
        return out
    # Grid step (uniform experimental grid).
    step = float(np.median(np.diff(x))) if n > 1 else 0.02
    half_pts = max(5, int(round(half_deg / step)))
    for i, c in enumerate(centres):
        idx = int(np.searchsorted(x, c))
        lo = max(0, idx - half_pts)
        hi = min(n, idx + half_pts + 1)
        out[i] = (lo, hi)
    return out


# --------------------------------------------------------------------------- #
# Goodness-of-fit metrics
# --------------------------------------------------------------------------- #
def compute_rwp(
    observed: np.ndarray,
    calculated: np.ndarray,
) -> tuple[float, float, float]:
    """Compute (Rwp, Rexp, GOF) on positive-intensity points.

    .. math::

        R_{wp} = \\sqrt{\\frac{\\sum w_i (y_i-y_{c,i})^2}{\\sum w_i y_i^2}},
        \\qquad w_i = 1/y_i

        R_{exp} = \\sqrt{\\frac{N}{\\sum w_i y_i^2}}
                 = \\sqrt{\\frac{N}{\\sum y_i}},
        \\qquad \\mathrm{GOF} = R_{wp}/R_{exp}

    Only points with ``y_i > 0`` are used.  Returns ``(inf, inf, inf)`` when
    no positive points remain.
    """
    y = np.asarray(observed, dtype=np.float64)
    yc = np.asarray(calculated, dtype=np.float64)
    mask = y > 0.0
    if not np.any(mask):
        return float("inf"), float("inf"), float("inf")
    ym = y[mask]
    ycm = yc[mask]
    w = 1.0 / ym
    num = float(np.sum(w * (ym - ycm) ** 2))
    den = float(np.sum(w * ym ** 2))
    if den <= 0.0:
        return float("inf"), float("inf"), float("inf")
    rwp = math.sqrt(num / den)
    n = int(mask.sum())
    rexp = math.sqrt(n / den)
    gof = rwp / rexp if rexp > 0.0 else float("inf")
    return rwp, rexp, gof


def compute_fom(rwp: float, sigma: float) -> float:
    """Map Rwp → FoM ∈ (0, 1] via ``exp(−Rwp/σ)``."""
    if not math.isfinite(rwp) or sigma <= 0.0:
        return 0.0
    return float(math.exp(-rwp / sigma))


# --------------------------------------------------------------------------- #
# Per-candidate refinement
# --------------------------------------------------------------------------- #
@dataclass
class CandidateFit:
    """Result of refining one candidate entry."""

    entry_id: str
    formula: str
    scale: float = 0.0
    shift_deg: float = 0.0
    fwhm: float = 0.0
    eta: float = 0.0
    bg0: float = 0.0
    bg1: float = 0.0
    bg2: float = 0.0
    rwp: float = float("inf")
    rexp: float = float("inf")
    gof: float = float("inf")
    fom: float = 0.0
    extra: dict = field(default_factory=dict)


def fit_candidate(
    entry: Entry,
    x: np.ndarray,
    y: np.ndarray,
    *,
    wavelength_kalpha1: float,
    wavelength_kalpha2: float | None,
    cfg: SmpfConfig,
) -> CandidateFit:
    """Refine the profile parameters for one candidate entry.

    Fits ``scale·profile + quadratic bg`` to the *raw* spectrum ``y`` and
    returns a :class:`CandidateFit` with all fitted parameters and the
    resulting Rwp / Rexp / GOF / FoM.
    """
    lo, hi = float(x.min()), float(x.max())
    centres, amps = expand_reflections(
        entry, wavelength_kalpha1, wavelength_kalpha2, lo, hi
    )
    out = CandidateFit(entry_id=entry.entry_id, formula=entry.formula)
    if centres.size == 0:
        out.fom = 0.0
        return out

    mask = y > 0.0
    if not np.any(mask):
        out.fom = 0.0
        return out

    x_mid = 0.5 * (lo + hi)
    windows = _reflection_windows(x, centres, cfg.window_half_deg)

    # --- initial scale: match the strongest calculated stick to raw max. ---
    theory0 = generate_theory_profile(
        x, centres, amps, windows,
        fwhm=cfg.fwhm_init, eta=cfg.eta_init, shift=0.0, scale=1.0,
        x_mid=x_mid,
    )
    tmax = float(theory0.max())
    scale0 = float(y.max()) / tmax if tmax > 0.0 else 1.0
    # Initial background: low-intensity envelope of the raw spectrum.
    bg0_0 = float(np.percentile(y, 5))

    # Parameter vector: [scale, shift, fwhm, eta, bg0, bg1, bg2]
    p0 = [scale0, 0.0, cfg.fwhm_init, cfg.eta_init, bg0_0, 0.0, 0.0]
    lo_b = [0.0, -cfg.shift_bound, cfg.fwhm_bounds[0], cfg.eta_bounds[0],
            -float(y.max()), -float(y.max()), -float(y.max())]
    hi_b = [scale0 * 10.0, cfg.shift_bound,
            cfg.fwhm_bounds[1], cfg.eta_bounds[1],
            float(y.max()), float(y.max()), float(y.max())]

    def residuals(p: np.ndarray) -> np.ndarray:
        scale, shift, fwhm, eta = p[0], p[1], p[2], p[3]
        bg0, bg1, bg2 = p[4], p[5], p[6]
        yc = generate_theory_profile(
            x, centres, amps, windows,
            fwhm=fwhm, eta=eta, shift=shift, scale=scale,
            bg0=bg0, bg1=bg1, bg2=bg2, x_mid=x_mid,
        )
        r = np.zeros_like(y)
        ym = y[mask]
        r[mask] = (ym - yc[mask]) / np.sqrt(ym)
        return r

    try:
        sol = least_squares(
            residuals,
            np.array(p0, dtype=np.float64),
            bounds=(np.array(lo_b, dtype=np.float64),
                    np.array(hi_b, dtype=np.float64)),
            method="trf",
            xtol=1e-6,
            ftol=1e-8,
            max_nfev=cfg.max_nfev,
        )
    except Exception:  # noqa: BLE001 — a diverging candidate must not crash search.
        out.fom = 0.0
        return out

    p = sol.x
    scale, shift, fwhm, eta = p[0], p[1], p[2], p[3]
    bg0, bg1, bg2 = p[4], p[5], p[6]
    yc = generate_theory_profile(
        x, centres, amps, windows,
        fwhm=fwhm, eta=eta, shift=shift, scale=scale,
        bg0=bg0, bg1=bg1, bg2=bg2, x_mid=x_mid,
    )
    rwp, rexp, gof = compute_rwp(y, yc)
    out.scale = float(scale)
    out.shift_deg = float(shift)
    out.fwhm = float(fwhm)
    out.eta = float(eta)
    out.bg0 = float(bg0)
    out.bg1 = float(bg1)
    out.bg2 = float(bg2)
    out.rwp = float(rwp)
    out.rexp = float(rexp)
    out.gof = float(gof)
    out.fom = float(compute_fom(rwp, cfg.fom_sigma))
    return out


# --------------------------------------------------------------------------- #
# Top-level entry point
# --------------------------------------------------------------------------- #
def search_match_smpf(
    exp_pattern: Pattern,
    conn: sqlite3.Connection,
    *,
    wavelength_kalpha1: float = 1.5406,
    wavelength_kalpha2: float | None = None,
    cfg: SmpfConfig | None = None,
    prescreen_top_n: int | None = None,
    top_n: int | None = None,
    timing: dict | None = None,
) -> list[tuple[Entry, dict[str, str | float]]]:
    """Run the full SMPF (full-pattern) retrieval.

    Parameters
    ----------
    exp_pattern:
        Raw experimental diffraction pattern (background NOT required to be
        pre-subtracted).
    conn:
        Open SQLite connection to the reference database.
    wavelength_kalpha1:
        Kα1 wavelength in Å (Bragg reference).
    wavelength_kalpha2:
        Kα2 wavelength in Å.  ``None`` = single-line (synthetic Cu Kα1
        data); a value (e.g. 1.5444) enables the Kα1/Kα2 doublet for real
        Cu patterns.
    cfg:
        Optional :class:`SmpfConfig` (overrides all knobs).
    prescreen_top_n:
        Override ``cfg.prescreen_top_n``.
    top_n:
        Override ``cfg.top_n``.
    timing:
        Optional dict; when given, per-stage timings (seconds) are written
        into it for performance reporting.

    Returns
    -------
    list[tuple[Entry, dict[str, str | float]]]
        ``(entry, score_dict)`` pairs sorted by descending FoM.  The score
        dict carries ``entry_id, formula, scale, shift_deg, fwhm, eta,
        bg0, bg1, bg2, rwp, rexp, gof, fom``.
    """
    t0 = time.perf_counter()
    cfg = cfg or SmpfConfig()
    if prescreen_top_n is not None:
        cfg.prescreen_top_n = int(prescreen_top_n)
    if top_n is not None:
        cfg.top_n = int(top_n)

    x = np.asarray(exp_pattern.two_theta, dtype=np.float64)
    y = np.asarray(exp_pattern.intensity, dtype=np.float64)

    # Stage 1 — peak-list pre-screen (recall candidate ids → Entry objects).
    _proc, peaks = auto_process(
        exp_pattern,
        config={
            "wavelength_kalpha1": wavelength_kalpha1,
            "wavelength_kalpha2": wavelength_kalpha2 or 1.5444,
            "peak_sensitivity": "medium",
        },
    )
    t_prescreen = time.perf_counter()

    recalled = search_match(
        peaks,
        conn,
        wavelength=wavelength_kalpha1,
        top_n=cfg.prescreen_top_n,
        recall_strongest_peak=True,
    )

    # Deduplicate by entry_id (recall may repeat ids across strong peaks).
    seen: set[str] = set()
    entries: list[Entry] = []
    for c in recalled:
        eid = c.entry.entry_id
        if eid in seen:
            continue
        seen.add(eid)
        entries.append(c.entry)

    t_recall = time.perf_counter()
    if not entries:
        if timing is not None:
            timing.update(prescreen=0.0, recall=0.0, refine=0.0, total=0.0,
                          n_candidates=0)
        return []

    # Stage 2 — full-pattern refinement of the pre-screened subset.
    fits: list[CandidateFit] = []
    for entry in entries:
        fits.append(
            fit_candidate(
                entry, x, y,
                wavelength_kalpha1=wavelength_kalpha1,
                wavelength_kalpha2=wavelength_kalpha2,
                cfg=cfg,
            )
        )
    t_refine = time.perf_counter()

    # Stage 3 — assemble (Entry, score) and rank by FoM descending.
    entry_by_id = {e.entry_id: e for e in entries}
    results: list[tuple[Entry, dict[str, str | float]]] = []
    for f in fits:
        e = entry_by_id.get(f.entry_id)
        if e is None:
            continue
        results.append((e, {
            "entry_id": f.entry_id,
            "formula": f.formula,
            "scale": f.scale,
            "shift_deg": f.shift_deg,
            "fwhm": f.fwhm,
            "eta": f.eta,
            "bg0": f.bg0,
            "bg1": f.bg1,
            "bg2": f.bg2,
            "rwp": f.rwp,
            "rexp": f.rexp,
            "gof": f.gof,
            "fom": f.fom,
        }))
    results.sort(key=lambda kv: float(kv[1]["fom"]), reverse=True)

    if timing is not None:
        timing.update({
            "prescreen": t_prescreen - t0,
            "recall": t_recall - t_prescreen,
            "refine": t_refine - t_recall,
            "n_candidates": len(entries),
            "total": t_refine - t0,
        })
    return results[: cfg.top_n]
