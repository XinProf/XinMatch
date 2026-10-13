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
   (±``shift_bound``), profile width, pseudo-Voigt mixing η, and a quadratic
   background basis.  The width model is selectable: a single global FWHM
   or the Caglioti angle-dependent form
   ``H²(θ) = U·tan²θ + V·tanθ + W`` (v1.4 default, clamped into
   ``fwhm_bounds``), which tracks the genuine high-angle broadening of
   laboratory data.  An optional global cell refinement (``d → d·(1+Δ)``,
   |Δ| ≤ ``cell_bound``) absorbs small reference-card cell mismatches: the
   induced 2θ shift grows as tanθ, so it stays identifiable against the
   constant zero-point shift.

   **Why fit the background on the raw spectrum instead of pre-subtracting
   it?**  The Rwp weights points by ``w = 1/y``.  Pre-subtracting a
   (necessarily imperfect) background leaves low-intensity residual points
   that ``w = 1/y`` penalises disproportionately, inflating Rwp and
   collapsing the separation between true and wrong phases.  Carrying a
   quadratic background basis inside the least-squares lets the fit absorb
   the smooth background self-consistently, so the low-intensity points
   keep their natural (large) ``y`` and contribute only their (small)
   Poisson/noise weight.  This is the standard profile-fitting choice.

   A global (single) FWHM was the v1.2 default: on typical laboratory Cu
   data the Caglioti width is close to constant over the scanned range,
   and one width is far cheaper than a 3-parameter U/V/W fit.  v1.4 keeps
   both models selectable via :attr:`SmpfConfig.caglioti` (Caglioti on by
   default): on synthetic data generated with a *floored* Caglioti width
   the two are indistinguishable (the floor dominates), while on real
   laboratory patterns the angle-dependent form removes the systematic
   high-angle misfit.
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

from xinmatch.core.model import CellParams, Entry, Pattern
from xinmatch.core.preprocess.auto_pipeline import auto_process
from xinmatch.core.search.search_match import search_match

logger = logging.getLogger(__name__)

__all__ = [
    "SmpfConfig",
    "expand_reflections",
    "expand_reflections_po",
    "march_dollase_cos",
    "march_dollase_weight",
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

#: 2θ offset (degrees) induced by a relative cell scale Δ on one reflection:
#: Bragg's law gives ``Δ2θ ≈ −2·(Δd/d)·tanθ`` (radians) → the degree factor.
_CELL_TTH_FACTOR = 360.0 / math.pi


def _caglioti_fwhm(
    tan_theta: np.ndarray,
    u: float,
    v: float,
    w: float,
    fwhm_bounds: tuple[float, float],
) -> np.ndarray:
    """Caglioti width ``H(θ) = sqrt(U·tan²θ + V·tanθ + W)`` per reflection.

    ``H²`` is clamped at zero before the square root (the box bounds on
    U/V/W do not by themselves guarantee positivity over the whole angular
    range) and ``H`` is clamped into ``fwhm_bounds`` so the profile model
    stays inside its documented width range.  ``tan_theta`` is the tangent
    of each reflection's Bragg angle (2θ/2).
    """
    h2 = u * tan_theta * tan_theta + v * tan_theta + w
    h = np.sqrt(np.maximum(h2, 0.0))
    out: np.ndarray = np.clip(h, fwhm_bounds[0], fwhm_bounds[1])
    return out


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
    caglioti:
        Use the Caglioti angle-dependent width
        ``H²(θ) = U·tan²θ + V·tanθ + W`` (clamped into ``fwhm_bounds``)
        instead of a single global FWHM.  Default on; ``False`` restores
        the v1.2 single-FWHM behaviour (fewer parameters, marginally
        faster).
    caglioti_u_init / caglioti_v_init:
        Initial U / V (deg²) of the Caglioti width.  W is derived so the
        starting width equals ``fwhm_init`` at the scan mid-angle.
    caglioti_u_bounds / caglioti_v_bounds / caglioti_w_bounds:
        Box bounds on U / V / W (deg²).  The bounds need not keep
        ``H² > 0`` over the whole angular range — :func:`_caglioti_fwhm`
        clamps ``H²`` at zero and ``H`` into ``fwhm_bounds``.
    cell_refine:
        Fit a global relative cell scale ``d → d·(1+Δ)`` (default on).
        Absorbs small reference-card cell mismatches; the induced 2θ
        shift grows as tanθ, so it is identifiable against the constant
        zero-point shift.  ``False`` disables the parameter.
    cell_bound:
        Symmetric bound on the relative cell scale Δ (default ±0.5%).
    march_po:
        Fit a per-candidate March-Dollase preferred-orientation parameter
        ``r`` (default off — the legacy profile is restored).  When on and
        the candidate carries per-peak Miller indices (``Entry.hkl``) plus
        a unit cell (``Entry.cell``), every reflection's intensity is
        multiplied by the March-Dollase factor
        ``(r²·cos²α + sin²α/r)^(-3/2)`` where α is the angle between the
        reflection's reciprocal vector and the PO axis
        (``po_axis``, default [001]).  r < 1 models a platy texture that
        enhances the PO-axis reflections; r > 1 models a needle texture.
        Requires the hkl-backfilled reference library (HANDOVER §5.2).
    po_axis:
        March-Dollase preferred-orientation axis (h, k, l) in reciprocal
        space (default [001] = basal / platy texture).
    march_r_init:
        Initial March-Dollase r (default 1.0 = no texture; the fit starts
        isotropic and only moves when the pattern demands it).
    march_r_bounds:
        Box bounds on the fitted March r (default (0.3, 3.0)).
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
    caglioti: bool = True
    caglioti_u_init: float = 0.006
    caglioti_v_init: float = -0.004
    caglioti_u_bounds: tuple[float, float] = (0.0, 0.05)
    caglioti_v_bounds: tuple[float, float] = (-0.02, 0.02)
    caglioti_w_bounds: tuple[float, float] = (0.001, 0.5)
    cell_refine: bool = True
    cell_bound: float = 0.005
    march_po: bool = False
    po_axis: tuple[int, int, int] = (0, 0, 1)
    march_r_init: float = 1.0
    march_r_bounds: tuple[float, float] = (0.3, 3.0)
    fom_sigma: float = 0.25
    window_half_deg: float = 1.5
    max_nfev: int = 60


# --------------------------------------------------------------------------- #
# March-Dollase preferred orientation (per-peak Miller-index texture model)
# --------------------------------------------------------------------------- #
def _reciprocal_metric(cell: CellParams) -> tuple[float, float, float,
                                                  float, float, float]:
    """Reciprocal-space metric from a direct-space cell.

    Returns ``(a*, b*, c*, cosα*, cosβ*, cosγ*)`` — the standard crystallo-
    graphic reciprocal-lattice parameters derived from the direct cell.
    """
    a, b, c = float(cell.a), float(cell.b), float(cell.c)
    ca, cb, cg = (math.cos(math.radians(float(v))) for v in
                  (cell.alpha, cell.beta, cell.gamma))
    sa, sb, sg = (math.sin(math.radians(float(v))) for v in
                  (cell.alpha, cell.beta, cell.gamma))
    if min(sa, sb, sg) <= 1e-12:
        return 1.0 / a, 1.0 / b, 1.0 / c, 0.0, 0.0, 0.0
    vol = a * b * c * math.sqrt(max(
        0.0,
        1.0 - ca * ca - cb * cb - cg * cg + 2.0 * ca * cb * cg,
    ))
    if vol <= 0.0:
        return 1.0 / a, 1.0 / b, 1.0 / c, 0.0, 0.0, 0.0
    astar = b * c * sa / vol
    bstar = a * c * sb / vol
    cstar = a * b * sg / vol
    cos_astar = (cb * cg - ca) / (sb * sg)
    cos_bstar = (ca * cg - cb) / (sa * sg)
    cos_gstar = (ca * cb - cg) / (sa * sb)
    return (astar, bstar, cstar, cos_astar, cos_bstar, cos_gstar)


def _rec_dot(hkl1: tuple[int, int, int], hkl2: tuple[int, int, int],
             metric: tuple[float, float, float, float, float, float]) -> float:
    """Dot product of two reciprocal vectors in the metric of the cell."""
    astar, bstar, cstar, cos_astar, cos_bstar, cos_gstar = metric
    h1, k1, l1 = hkl1
    h2, k2, l2 = hkl2
    return (
        h1 * h2 * astar * astar
        + k1 * k2 * bstar * bstar
        + l1 * l2 * cstar * cstar
        + (h1 * k2 + k1 * h2) * astar * bstar * cos_gstar
        + (h1 * l2 + l1 * h2) * astar * cstar * cos_bstar
        + (k1 * l2 + l1 * k2) * bstar * cstar * cos_astar
    )


def march_dollase_cos(
    entry: Entry,
    po_axis: tuple[int, int, int] = (0, 0, 1),
) -> np.ndarray | None:
    """Per-peak cos α between each reflection's reciprocal vector and the PO
    axis, aligned with ``entry.d_spacings``.

    ``None`` is returned when the entry lacks the Miller indices or the cell
    needed for the geometry (the caller then falls back to the un-textured
    profile).  Peaks whose hkl row is missing (the reference library's hkl
    backfill is ~73 % complete) carry ``nan`` — the profile builder treats
    ``nan`` as "no texture" (weight 1.0), so a partially-annotated card is
    textured only on its annotated reflections.
    """
    if not entry.hkl or entry.cell is None:
        return None
    metric = _reciprocal_metric(entry.cell)
    p_norm = math.sqrt(_rec_dot(po_axis, po_axis, metric))
    if p_norm <= 0.0:
        return None
    out = np.full(entry.n_peaks, np.nan, dtype=np.float64)
    for i, hkl in enumerate(entry.hkl):
        if hkl is None:
            continue
        g_norm = math.sqrt(_rec_dot(hkl, hkl, metric))
        if g_norm <= 0.0:
            continue
        cos = _rec_dot(hkl, po_axis, metric) / (g_norm * p_norm)
        out[i] = min(1.0, max(-1.0, cos))
    return out


def march_dollase_weight(r: float, cos: float | np.ndarray) -> float | np.ndarray:
    """March-Dollase intensity factor ``(r²cos²α + sin²α/r)^(-3/2)``.

    r = 1 (isotropy) gives 1 everywhere; r < 1 enhances the PO-axis
    reflections (cos ≈ 1) and suppresses the rest.  ``nan`` input (missing
    hkl) maps to 1.0.
    """
    if r <= 0.0:
        return 1.0
    c = np.asarray(cos, dtype=np.float64)
    w = (r * r * c * c + (1.0 - c * c) / r) ** -1.5
    # nan (missing hkl) maps to the isotropic weight 1.
    w = np.where(np.isnan(c), 1.0, w)
    return float(w) if np.ndim(w) == 0 else w


# --------------------------------------------------------------------------- #
# Reflection expansion (Bragg + Kα1/Kα2 doublet)
# --------------------------------------------------------------------------- #
def _expand_core(
    ds: np.ndarray,
    ints: np.ndarray,
    po_cos: np.ndarray | None,
    wavelength_kalpha1: float,
    wavelength_kalpha2: float | None,
    tth_lo: float,
    tth_hi: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    """Shared d–I–(cos) → 2θ expansion; see :func:`expand_reflections`."""
    sin_t1 = wavelength_kalpha1 / (2.0 * ds)
    ok1 = (sin_t1 >= -1.0) & (sin_t1 <= 1.0)
    c1 = 2.0 * np.degrees(np.arcsin(sin_t1[ok1]))
    a1 = ints[ok1]
    pc1 = po_cos[ok1] if po_cos is not None else None

    if wavelength_kalpha2 is not None:
        sin_t2 = wavelength_kalpha2 / (2.0 * ds)
        ok2 = (sin_t2 >= -1.0) & (sin_t2 <= 1.0)
        c2 = 2.0 * np.degrees(np.arcsin(sin_t2[ok2]))
        a2 = ints[ok2] * 0.5
        centres = np.concatenate([c1, c2])
        amps = np.concatenate([a1, a2])
        if po_cos is not None:
            pc = np.concatenate([pc1, po_cos[ok2]])
        else:
            pc = None
    else:
        centres, amps = c1, a1
        pc = pc1

    in_range = (centres >= tth_lo - 1.0) & (centres <= tth_hi + 1.0)
    if pc is not None:
        pc = pc[in_range]
    return centres[in_range], amps[in_range], pc


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
    centres, amps, _ = _expand_core(
        np.asarray(entry.d_spacings, dtype=np.float64),
        np.asarray(entry.intensities, dtype=np.float64),
        None,
        wavelength_kalpha1, wavelength_kalpha2, tth_lo, tth_hi,
    )
    return centres, amps


def expand_reflections_po(
    entry: Entry,
    wavelength_kalpha1: float,
    wavelength_kalpha2: float | None,
    tth_lo: float,
    tth_hi: float,
    po_cos: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    """Like :func:`expand_reflections` but also propagates the per-peak
    March-Dollase cos α array (aligned with ``entry.d_spacings``) through the
    same Kα1/Kα2 doubling and 2θ-range filtering.  Returns
    ``(centres, amps, po_cos_expanded)`` (``None`` when ``po_cos`` is
    ``None``).
    """
    if entry.n_peaks == 0:
        return np.empty(0), np.empty(0), None
    return _expand_core(
        np.asarray(entry.d_spacings, dtype=np.float64),
        np.asarray(entry.intensities, dtype=np.float64),
        po_cos,
        wavelength_kalpha1, wavelength_kalpha2, tth_lo, tth_hi,
    )


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
    uvw: tuple[float, float, float] | None = None,
    cell_delta: float = 0.0,
    tan_theta: np.ndarray | None = None,
    fwhm_bounds: tuple[float, float] = (0.08, 0.6),
    march_cos: np.ndarray | None = None,
    march_r: float = 1.0,
) -> np.ndarray:
    """Calculate a full profile on grid ``x`` for pre-expanded reflections.

    The profile is ``scale · Σ_i amp_i · pv(x − (c_i+shift); fwhm_i, η)``
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
        Global profile parameters.  ``fwhm`` is the constant width, used
        only when ``uvw`` is ``None``.
    bg0, bg1, bg2:
        Quadratic background coefficients.
    x_mid:
        Centre for the background basis.
    uvw:
        Optional Caglioti ``(U, V, W)`` triple.  When given, each reflection
        gets its own angle-dependent width
        ``H_i = sqrt(U·tan²θ_i + V·tanθ_i + W)`` (clamped, see
        :func:`_caglioti_fwhm`) instead of the constant ``fwhm``.
        Requires ``tan_theta``.
    cell_delta:
        Optional global relative cell scale Δ (``d → d·(1+Δ)``).  Shifts
        each reflection by ``−Δ·(360/π)·tanθ_i`` degrees (first order in
        Δ from Bragg's law).  Requires ``tan_theta``.
    tan_theta:
        Tangent of each reflection's Bragg angle, shape ``(M,)``.  Needed
        by ``uvw`` and ``cell_delta``.
    fwhm_bounds:
        Width clamp for the Caglioti model.
    march_cos:
        Per-reflection March-Dollase cos α, shape ``(M,)``, aligned with
        ``centres``/``amps`` (see :func:`expand_reflections_po`).  When
        given, each amplitude is multiplied by the March-Dollase factor
        ``(r²cos²α + sin²α/r)^(-3/2)`` for the current ``march_r``.  ``nan``
        entries (reflections without Miller indices) get weight 1.
    march_r:
        March-Dollase parameter; 1.0 = isotropic (no texture).
    """
    t = x - x_mid
    yc = bg0 + bg1 * t + bg2 * t * t
    if centres.size == 0 or scale == 0.0:
        return yc
    tt: np.ndarray = tan_theta if tan_theta is not None else np.empty(0)
    if (uvw is not None or cell_delta != 0.0) and tan_theta is None:
        raise ValueError("uvw / cell_delta require tan_theta")
    if march_cos is not None:
        if march_cos.size != centres.size:
            raise ValueError("march_cos must be aligned with centres/amps")
        amps = amps * march_dollase_weight(march_r, march_cos)

    # Per-reflection width (Caglioti array or constant) and effective centres.
    if uvw is not None:
        fw = _caglioti_fwhm(tt, uvw[0], uvw[1], uvw[2], fwhm_bounds)
    else:
        fw = np.full(centres.size, float(fwhm), dtype=np.float64)
    fw_col = fw[:, None]
    gh = (_GAUSS_H / fw)[:, None]
    lh = (_LORENTZ_H / fw)[:, None]
    centres_eff = centres + shift
    if cell_delta != 0.0:
        centres_eff = centres_eff - cell_delta * _CELL_TTH_FACTOR * tt

    # Uniform-width index matrix over all reflection windows: entries past
    # a window's ``hi`` are masked out.  One vectorised pass replaces the
    # per-reflection Python loop (its small-array numpy overhead dominated
    # the refinement cost for M ~ 50-200 reflections).
    widths = windows[:, 1] - windows[:, 0]
    w_max = int(widths.max()) if widths.size else 0
    if w_max <= 0:
        return yc
    n = x.size
    idx = windows[:, 0:1] + np.arange(w_max, dtype=np.intp)[None, :]
    valid = idx < windows[:, 1:2]
    np.clip(idx, 0, n - 1, out=idx)
    dx = x[idx] - centres_eff[:, None]
    q = (dx / fw_col) ** 2
    g = np.exp(-4.0 * _LN2 * q)
    lor = 1.0 / (1.0 + 4.0 * q)
    pv = eta * lh * lor + (1.0 - eta) * gh * g
    contrib = np.where(valid, (scale * amps)[:, None] * pv, 0.0)
    yc += np.bincount(idx.ravel(), weights=contrib.ravel(), minlength=n)
    return yc


def _reflection_windows(
    x: np.ndarray,
    centres: np.ndarray,
    half_deg: float,
    extra_deg: np.ndarray | None = None,
) -> np.ndarray:
    """Build ``(M, 2)`` index windows into ``x`` around each centre.

    ``extra_deg`` optionally widens each reflection's window by a
    per-reflection margin (degrees) — used to keep a peak that the cell
    refinement may push away from its theoretical centre fully inside its
    evaluation window.
    """
    n = x.size
    out = np.zeros((centres.size, 2), dtype=np.intp)
    if centres.size == 0:
        return out
    # Grid step (uniform experimental grid).
    step = float(np.median(np.diff(x))) if n > 1 else 0.02
    half_pts = max(5, int(round(half_deg / step)))
    for i, c in enumerate(centres):
        pad = half_pts
        if extra_deg is not None:
            pad += int(math.ceil(max(0.0, float(extra_deg[i])) / step))
        idx = int(np.searchsorted(x, c))
        lo = max(0, idx - pad)
        hi = min(n, idx + pad + 1)
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
    #: Caglioti U/V/W (deg²).  When the single-FWHM model is used, U=V=0
    #: and W=fwhm² (the identity encoding H ≡ fwhm).
    u: float = 0.0
    v: float = 0.0
    w: float = 0.0
    #: Fitted global relative cell scale Δ (``d → d·(1+Δ)``); 0 when the
    #: cell refinement is disabled.
    cell_delta: float = 0.0
    #: Fitted March-Dollase r (1.0 = no texture; only meaningful when
    #: ``SmpfConfig.march_po`` is on and the entry has hkl + cell).
    march_r: float = 1.0
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

    The free-parameter vector depends on the config switches:

    * always ``scale, shift, eta, bg0, bg1, bg2``;
    * width: a single ``fwhm`` (``cfg.caglioti=False``) or the Caglioti
      triple ``u, v, w`` (``cfg.caglioti=True``, default);
    * ``cell_delta`` when ``cfg.cell_refine=True`` (default): a global
      relative cell scale whose 2θ signature grows as tanθ and is hence
      identifiable against the constant zero-point shift;
    * ``march_r`` when ``cfg.march_po=True`` **and** the entry carries
      per-peak Miller indices plus a cell (partial hkl coverage is fine:
      un-annotated reflections keep weight 1).
    """
    lo, hi = float(x.min()), float(x.max())
    po_cos = (
        march_dollase_cos(entry, cfg.po_axis)
        if cfg.march_po
        else None
    )
    centres, amps, po_cos_exp = expand_reflections_po(
        entry, wavelength_kalpha1, wavelength_kalpha2, lo, hi, po_cos
    )
    use_march = cfg.march_po and po_cos_exp is not None
    out = CandidateFit(entry_id=entry.entry_id, formula=entry.formula)
    if centres.size == 0:
        out.fom = 0.0
        return out

    mask = y > 0.0
    if not np.any(mask):
        out.fom = 0.0
        return out

    x_mid = 0.5 * (lo + hi)
    # tan of each reflection's Bragg angle (clip guards the 2θ→180° edge).
    tan_theta = np.clip(np.tan(np.radians(centres / 2.0)), 0.0, 8.0)

    # Caglioti init: reproduce fwhm_init at the scan mid-angle so the
    # starting profile matches the legacy single-FWHM behaviour there.
    tm = math.tan(math.radians(0.25 * (lo + hi)))
    u0 = cfg.caglioti_u_init
    v0 = cfg.caglioti_v_init
    w0 = cfg.fwhm_init ** 2 - u0 * tm * tm - v0 * tm
    w0 = min(max(w0, cfg.caglioti_w_bounds[0]), cfg.caglioti_w_bounds[1])

    use_uvw = bool(cfg.caglioti)
    use_cell = bool(cfg.cell_refine)
    if use_cell:
        # Widen each window by the largest 2θ offset the cell refinement
        # can induce at that angle (|Δ|·360/π·tanθ), so a peak pushed to
        # the bound is never clipped by its evaluation window.
        extra = cfg.cell_bound * _CELL_TTH_FACTOR * tan_theta
        windows = _reflection_windows(x, centres, cfg.window_half_deg,
                                      extra_deg=extra)
    else:
        windows = _reflection_windows(x, centres, cfg.window_half_deg)

    # --- initial scale: match the strongest calculated stick to raw max. ---
    theory0 = generate_theory_profile(
        x, centres, amps, windows,
        fwhm=cfg.fwhm_init, eta=cfg.eta_init, shift=0.0, scale=1.0,
        x_mid=x_mid,
        uvw=(u0, v0, w0) if use_uvw else None,
        tan_theta=tan_theta, fwhm_bounds=cfg.fwhm_bounds,
    )
    tmax = float(theory0.max())
    scale0 = float(y.max()) / tmax if tmax > 0.0 else 1.0
    # Initial background: low-intensity envelope of the raw spectrum.
    bg0_0 = float(np.percentile(y, 5))
    ymax = float(y.max())

    # Parameter vector (order matters — mirrored in ``residuals``):
    #   [scale, shift, (fwhm | u, v, w), eta, bg0, bg1, bg2, (cell_delta)]
    p0 = [scale0, 0.0]
    lo_b = [0.0, -cfg.shift_bound]
    hi_b = [scale0 * 10.0, cfg.shift_bound]
    if use_uvw:
        p0 += [u0, v0, w0]
        lo_b += [cfg.caglioti_u_bounds[0], cfg.caglioti_v_bounds[0],
                 cfg.caglioti_w_bounds[0]]
        hi_b += [cfg.caglioti_u_bounds[1], cfg.caglioti_v_bounds[1],
                 cfg.caglioti_w_bounds[1]]
    else:
        p0 += [cfg.fwhm_init]
        lo_b += [cfg.fwhm_bounds[0]]
        hi_b += [cfg.fwhm_bounds[1]]
    p0 += [cfg.eta_init, bg0_0, 0.0, 0.0]
    lo_b += [cfg.eta_bounds[0], -ymax, -ymax, -ymax]
    hi_b += [cfg.eta_bounds[1], ymax, ymax, ymax]
    if use_cell:
        p0 += [0.0]
        lo_b += [-cfg.cell_bound]
        hi_b += [cfg.cell_bound]
    if use_march:
        p0 += [cfg.march_r_init]
        lo_b += [cfg.march_r_bounds[0]]
        hi_b += [cfg.march_r_bounds[1]]

    def residuals(p: np.ndarray) -> np.ndarray:
        scale, shift = p[0], p[1]
        k = 2
        if use_uvw:
            uvw = (p[2], p[3], p[4])
            fwhm = cfg.fwhm_init  # unused when uvw is given
            k = 5
        else:
            fwhm = p[2]
            uvw = None
            k = 3
        eta, bg0, bg1, bg2 = p[k], p[k + 1], p[k + 2], p[k + 3]
        k += 4
        cell_delta = p[k] if use_cell else 0.0
        k += int(use_cell)
        march_r = p[k] if use_march else 1.0
        yc = generate_theory_profile(
            x, centres, amps, windows,
            fwhm=fwhm, eta=eta, shift=shift, scale=scale,
            bg0=bg0, bg1=bg1, bg2=bg2, x_mid=x_mid,
            uvw=uvw, cell_delta=cell_delta, tan_theta=tan_theta,
            fwhm_bounds=cfg.fwhm_bounds,
            march_cos=po_cos_exp if use_march else None,
            march_r=march_r,
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
    scale, shift = p[0], p[1]
    k = 2
    if use_uvw:
        u, v, w = p[2], p[3], p[4]
        k = 5
    else:
        fwhm = p[2]
        k = 3
    eta, bg0, bg1, bg2 = p[k], p[k + 1], p[k + 2], p[k + 3]
    k += 4
    cell_delta = p[k] if use_cell else 0.0
    k += int(use_cell)
    march_r = p[k] if use_march else 1.0
    yc = generate_theory_profile(
        x, centres, amps, windows,
        fwhm=cfg.fwhm_init if use_uvw else fwhm,
        eta=eta, shift=shift, scale=scale,
        bg0=bg0, bg1=bg1, bg2=bg2, x_mid=x_mid,
        uvw=(u, v, w) if use_uvw else None,
        cell_delta=cell_delta, tan_theta=tan_theta,
        fwhm_bounds=cfg.fwhm_bounds,
        march_cos=po_cos_exp if use_march else None,
        march_r=march_r,
    )
    rwp, rexp, gof = compute_rwp(y, yc)
    out.scale = float(scale)
    out.shift_deg = float(shift)
    if use_uvw:
        out.u = float(u)
        out.v = float(v)
        out.w = float(w)
        # Representative width at the scan mid-angle (for reporting).
        out.fwhm = float(_caglioti_fwhm(np.array([tm]), u, v, w,
                                        cfg.fwhm_bounds)[0])
    else:
        out.fwhm = float(fwhm)
        out.w = float(fwhm * fwhm)  # identity encoding: H ≡ fwhm
    out.eta = float(eta)
    out.bg0 = float(bg0)
    out.bg1 = float(bg1)
    out.bg2 = float(bg2)
    out.cell_delta = float(cell_delta)
    out.march_r = float(march_r)
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
        bg0, bg1, bg2, rwp, rexp, gof, fom`` plus the v1.4 extension keys
        ``caglioti_u, caglioti_v, caglioti_w, cell_delta`` (identity
        values — U=V=0, W=fwhm², Δ=0 — when the respective switch is off).
        ``fwhm`` is the representative width at the scan mid-angle when the
        Caglioti model is active.
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
            "caglioti_u": f.u,
            "caglioti_v": f.v,
            "caglioti_w": f.w,
            "cell_delta": f.cell_delta,
            "march_r": f.march_r,
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
