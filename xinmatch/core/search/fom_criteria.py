"""Figure-of-Merit (FoM) criteria for peak-based search-match (T6.2).

Implements the FoM model documented in ``FOM_MODEL.md``::

    FoM = 1 − w1·(1−P_peakpos) − w2·(1−P_intensity) − w3·(1−P_npeaks)
          − w4·(1−P_ncorr) − w5·|ln(I_scale)|

The default weights were obtained by non-negative least-squares fit of
3640 candidate entries exported from Match! 4.3 Build 360 (R² = 0.9913,
Kendall τ = 0.9105 — see ``FOM_MODEL.md`` §2).  They correspond to
Match!'s **default** search-match options; if the user changes the
"2theta window for peak correlation" or related options, the internal
weight derivation in Match! produces different values — XinMatch
exposes them via :class:`FomWeights`.

The five agreement criteria (the *P* values and *I_scale*) are computed
as follows (this is the **working** definition; the precise definition
used internally by Match! is not documented and is to be reverse-
engineered in T0.8 / T6.10):

``P_peakpos`` = exp(−mean(Δ2θ²) / σ_pos²)
    Gaussian penalty on the 2θ mismatch of correlated peak pairs;
    ``σ_pos`` defaults to 0.1°.  Δ2θ = (2θ_exp − 2θ_ref) for each
    matched pair (reference 2θ derived from *d* and the wavelength
    via :func:`~xinmatch.core.search.correlate.d_to_two_theta`).

``P_intensity`` = exp(−mean(ΔI_norm²) / σ_intensity²)
    Gaussian penalty on intensity mismatch.  Both experimental and
    reference intensities are normalised so that the maximum on each
    side equals 100, then ``ΔI_norm = I_exp_norm − I_ref_norm`` per
    matched pair.  ``σ_intensity`` defaults to 10.

``P_npeaks``
    Fraction of experimental peaks that got correlated,
    ``n_matched_exp / n_exp_total``.  Favours entries that explain
    *most* of the unknown pattern (single-phase bias — Match! warns
    about reducing this weight for multi-phase samples).

``P_ncorr``
    Fraction of *should-have-been-correlated* reference peaks that were
    actually correlated, ``n_matched_ref / min(n_exp, n_ref)``.  The
    denominator follows Match!'s notion that the smaller pattern sets
    the upper bound on possible correlations.

``I_scale``
    Least-squares intensity scaling factor that maps the reference
    pattern onto the experimental pattern.  Computed on
    intensity-normalised values (max = 100) so the FoM penalises
    *shape* mismatch rather than absolute count scale:
    ``I_scale = Σ(I_exp·I_ref) / Σ(I_ref²)``.  Falls back to
    ``Σ(I_exp) / Σ(I_ref)`` (the simple ratio from the FoM spec) when
    the LSQ denominator collapses to zero.  ``|ln(I_scale)|`` then
    gives the multiplicative mismatch (2× and ½× cost the same).

.. todo:: T0.8 粗推（lab6 / LaB6, 1 行真实数据）

    Match! 4.3 导出的 lab6 LaB6 Top1 行给出 ``I_scale = 1.0348``。
    用我们的 ``max=100`` LSQ 实现 + 完整 LaB6 参考表（14 个匹配峰），
    复现值 ≈ ``0.9998``（delta ``−0.035``，即 3.4 % 偏差）。  ``sum=100``
    LSQ 给出 ``1.0004``（delta ``−0.034``），与 ``max=100`` 在数据形状
    接近相同时数值几乎相同。  ``raw`` LSQ 和 ``raw`` ratio 给出 ~50 的
    量纲错误，因此 **归一化方式一定是 ``max=100`` 或 ``sum=100`` LSQ**，
    与当前的 ``max=100`` 实现一致。  偏差 −0.035 来源目前最可能的是
    参考强度表不完整（Match! 内部 LaB6 条目含更多反射）。

    **结论**：``I_scale`` 归一化方向已确认（``max=100`` LSQ），但精确值
    需要 N>3 个候选 CSV 才能定论。  待用户从 Match! 导出更多 CSV 后，
    用 ``tools/build_baseline.py`` 反推后定稿。  不要根据 1 行数据修改
    ``compute_p_values`` 的算法实现。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from xinmatch.core.model import Peak
from xinmatch.core.search.correlate import correlate_peaks, d_to_two_theta

# --------------------------------------------------------------------- #
# Weights
# --------------------------------------------------------------------- #


@dataclass(frozen=True)
class FomWeights:
    """Weights for the five agreement criteria in the FoM formula.

    Defaults are the empirical values reverse-engineered from
    Match! 4.3 (see ``FOM_MODEL.md`` §2, R² = 0.9913,
    Kendall τ = 0.9105).  Override per-instance to tune the
    search-match behaviour.

    All weights must be non-negative; the FoM formula treats each as a
    penalty and the sum need not be normalised.
    """

    peakpos: float = 0.2275
    intensity: float = 0.1112
    npeaks: float = 0.2306
    ncorr: float = 0.1152
    i_scale: float = 0.0454

    def as_dict(self) -> dict[str, float]:
        """Return the weights as a plain ``{name: value}`` dict."""
        return {
            "peakpos": self.peakpos,
            "intensity": self.intensity,
            "npeaks": self.npeaks,
            "ncorr": self.ncorr,
            "i_scale": self.i_scale,
        }


#: Module-level instance of the default Match! 4.3 weights.
DEFAULT_WEIGHTS = FomWeights()


# --------------------------------------------------------------------- #
# P-value computation
# --------------------------------------------------------------------- #


def compute_p_values(
    exp_peaks: list[Peak],
    ref_peaks_d_intensity: list[tuple[float, float]],
    pairs: list[tuple[int, int]],
    wavelength: float,
    *,
    sigma_pos: float = 0.1,
    sigma_intensity: float = 10.0,
) -> dict[str, float]:
    """Compute the five FoM agreement criteria (the *P* values + *I_scale*).

    Parameters
    ----------
    exp_peaks:
        Experimental peaks (must carry ``two_theta`` and ``intensity``).
    ref_peaks_d_intensity:
        Reference peaks as ``(d_spacing_Å, intensity)`` tuples.
    pairs:
        ``(exp_idx, ref_idx)`` correlations as returned by
        :func:`~xinmatch.core.search.correlate.correlate_peaks`.
    wavelength:
        Wavelength (Å) used to convert reference d-spacings to 2θ for
        the positional criterion.
    sigma_pos:
        Width (degrees 2θ) of the Gaussian positional-error model.
        Default 0.1°.
    sigma_intensity:
        Width (normalised-to-100 intensity units) of the Gaussian
        intensity-error model.  Default 10.

    Returns
    -------
    dict[str, float]
        Keys: ``peakpos``, ``intensity``, ``npeaks``, ``ncorr``,
        ``i_scale``.  When *pairs* is empty all P values are 0 and
        ``i_scale`` defaults to 1.0 (no information, no multiplicative
        penalty).

    Raises
    ------
    ValueError
        If *sigma_pos* or *sigma_intensity* is non-positive.
    """
    if sigma_pos <= 0.0:
        raise ValueError(f"sigma_pos must be positive, got {sigma_pos}")
    if sigma_intensity <= 0.0:
        raise ValueError(f"sigma_intensity must be positive, got {sigma_intensity}")

    n_exp = len(exp_peaks)
    n_ref = len(ref_peaks_d_intensity)

    matched_exp = {ei for ei, _ in pairs}
    matched_ref = {ri for _, ri in pairs}

    # Coverage ratios are well-defined even with no pairs.
    p_npeaks = float(len(matched_exp) / n_exp) if n_exp > 0 else 0.0
    denom_ncorr = min(n_exp, n_ref)
    p_ncorr = float(len(matched_ref) / denom_ncorr) if denom_ncorr > 0 else 0.0

    if not pairs:
        return {
            "peakpos": 0.0,
            "intensity": 0.0,
            "npeaks": p_npeaks,
            "ncorr": p_ncorr,
            "i_scale": 1.0,
        }

    # Intensity normalisation factors (max → 100 on each side).
    exp_intensities = np.fromiter(
        (p.intensity for p in exp_peaks), dtype=np.float64, count=n_exp
    )
    ref_intensities = np.fromiter(
        (intensity for _, intensity in ref_peaks_d_intensity),
        dtype=np.float64,
        count=n_ref,
    )
    exp_max = float(exp_intensities.max()) if n_exp > 0 else 0.0
    ref_max = float(ref_intensities.max()) if n_ref > 0 else 0.0

    delta_2th = np.empty(len(pairs), dtype=np.float64)
    delta_intensity = np.empty(len(pairs), dtype=np.float64)
    intensity_exp_norm = np.empty(len(pairs), dtype=np.float64)
    intensity_ref_norm = np.empty(len(pairs), dtype=np.float64)

    for k, (ei, ri) in enumerate(pairs):
        exp_tt = exp_peaks[ei].two_theta
        ref_d, ref_intensity = ref_peaks_d_intensity[ri]
        ref_tt = d_to_two_theta(ref_d, wavelength)
        # If the reference 2θ is unreachable (inf), Δ2θ is enormous and
        # P_peakpos collapses to ~0 — the natural penalty for trying to
        # correlate an impossible peak.
        delta_2th[k] = exp_tt - ref_tt if ref_tt != math.inf else math.inf

        e_norm = (
            (exp_peaks[ei].intensity / exp_max * 100.0) if exp_max > 0 else 0.0
        )
        r_norm = (ref_intensity / ref_max * 100.0) if ref_max > 0 else 0.0
        delta_intensity[k] = e_norm - r_norm
        intensity_exp_norm[k] = e_norm
        intensity_ref_norm[k] = r_norm

    # Guard against infinite Δ2θ poisoning the mean.
    finite_2th = delta_2th[np.isfinite(delta_2th)]
    mean_sq_pos = (
        float(np.mean(finite_2th ** 2)) if finite_2th.size else math.inf
    )
    p_peakpos = float(math.exp(-mean_sq_pos / (sigma_pos ** 2)))
    p_intensity = float(
        math.exp(-np.mean(delta_intensity ** 2) / (sigma_intensity ** 2))
    )

    # I_scale (LSQ on normalised intensities): I_exp ≈ I_scale · I_ref.
    denom = float(np.sum(intensity_ref_norm ** 2))
    if denom > 0.0:
        i_scale = float(np.sum(intensity_exp_norm * intensity_ref_norm) / denom)
    else:
        # Fallback to simple ratio (FoM spec) when ref intensities are
        # all zero / identical.
        sum_ref = float(np.sum(intensity_ref_norm))
        i_scale = (
            float(np.sum(intensity_exp_norm) / sum_ref) if sum_ref > 0 else 1.0
        )

    return {
        "peakpos": p_peakpos,
        "intensity": p_intensity,
        "npeaks": p_npeaks,
        "ncorr": p_ncorr,
        "i_scale": i_scale,
    }


# --------------------------------------------------------------------- #
# FoM assembly
# --------------------------------------------------------------------- #


def compute_fom(
    p: dict[str, float],
    weights: dict[str, float] | FomWeights | None = None,
) -> float:
    """Assemble the FoM from P values and weights.

    Parameters
    ----------
    p:
        Dict with keys ``peakpos``, ``intensity``, ``npeaks``,
        ``ncorr``, ``i_scale`` (as returned by :func:`compute_p_values`).
    weights:
        Optional :class:`FomWeights` instance or dict.  ``None`` uses
        :data:`DEFAULT_WEIGHTS`.  A partial dict is filled with the
        corresponding defaults.

    Returns
    -------
    float
        The FoM value.  Not clamped — values can drift slightly below
        0 or above 1 in degenerate cases, mirroring Match!'s raw FoM
        (its display clamps to [0, 1] but the internal value does not).
    """
    if weights is None:
        w = DEFAULT_WEIGHTS.as_dict()
    elif isinstance(weights, FomWeights):
        w = weights.as_dict()
    else:
        defaults = DEFAULT_WEIGHTS.as_dict()
        w = {k: float(weights.get(k, defaults[k])) for k in defaults}

    i_scale = max(float(p.get("i_scale", 1.0)), 1e-12)
    fom = (
        1.0
        - w["peakpos"] * (1.0 - float(p.get("peakpos", 0.0)))
        - w["intensity"] * (1.0 - float(p.get("intensity", 0.0)))
        - w["npeaks"] * (1.0 - float(p.get("npeaks", 0.0)))
        - w["ncorr"] * (1.0 - float(p.get("ncorr", 0.0)))
        - w["i_scale"] * abs(math.log(i_scale))
    )
    return float(fom)


# --------------------------------------------------------------------- #
# One-step scoring
# --------------------------------------------------------------------- #


def score_candidate(
    exp_peaks: list[Peak],
    ref_peaks_d_intensity: list[tuple[float, float]],
    wavelength: float,
    *,
    window_deg: float = 0.3,
    weights: dict[str, float] | FomWeights | None = None,
    sigma_pos: float = 0.1,
    sigma_intensity: float = 10.0,
    method: str = "greedy",
) -> tuple[float, dict[str, float]]:
    """One-step FoM scoring for a single candidate reference entry.

    Convenience pipeline: correlate → compute P values → compute FoM.

    Match! feature: *peak-based search-match* per-candidate scoring
    (T6.1 + T6.2 combined).

    Parameters
    ----------
    exp_peaks:
        Experimental peaks.
    ref_peaks_d_intensity:
        Reference peaks as ``(d_spacing_Å, intensity)`` tuples.
    wavelength:
        Wavelength in Å (used both for d→2θ conversion).
    window_deg:
        Correlation window width in degrees 2θ (default 0.3).
    weights:
        Optional :class:`FomWeights` or dict override.
    sigma_pos, sigma_intensity:
        Gaussian widths for the positional / intensity error models.
    method:
        Correlation method: ``'greedy'`` (default) or ``'hungarian'``.

    Returns
    -------
    tuple[float, dict[str, float]]
        ``(FoM, p_dict)`` where *p_dict* has keys ``peakpos``,
        ``intensity``, ``npeaks``, ``ncorr``, ``i_scale``.
    """
    pairs = correlate_peaks(
        exp_peaks,
        ref_peaks_d_intensity,
        wavelength,
        window_deg,
        method=method,
    )
    p = compute_p_values(
        exp_peaks,
        ref_peaks_d_intensity,
        pairs,
        wavelength,
        sigma_pos=sigma_pos,
        sigma_intensity=sigma_intensity,
    )
    fom = compute_fom(p, weights)
    return fom, p
