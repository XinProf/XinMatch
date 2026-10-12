"""Peak searching.

Implements the reference software's *Peak search* command (Pattern menu) and the automatic
peak search during raw-data processing.

The reference software uses the first- (and optionally second-) derivative method.  Here we
detect local maxima via the first derivative (sign change from positive to
negative) and accept a candidate only if its height exceeds a local
signal-to-noise ratio (SNR) threshold derived from the median absolute
deviation (MAD) of the data.  A second-derivative (curvature) check is also
applied: a true peak has negative second derivative at the top.

Three sensitivity presets (``low`` / ``medium`` / ``high``) adjust the SNR
threshold and the minimum prominence.
"""

from __future__ import annotations

import numpy as np

from xinmatch.core.model import Peak

# Sensitivity presets: (snr_threshold, min_prominence_factor).
# `min_prominence_factor` is in units of the noise estimate (MAD).
_SENSITIVITY = {
    "low": (5.0, 5.0),
    "medium": (3.0, 3.0),
    "high": (1.5, 1.5),
}


def _noise_estimate(intensity: np.ndarray) -> float:
    """Robust noise estimate via the median absolute deviation (MAD)."""
    # Use first differences to remove broad background / peak trends, then
    # take the MAD of the residuals.
    diff = np.diff(intensity)
    mad = np.median(np.abs(diff - np.median(diff)))
    # 1.4826 converts MAD to σ for Gaussian noise; divide by sqrt(2) because
    # differencing doubles the variance.
    return float(1.4826 * mad / np.sqrt(2.0))


def _key_col_prominence(intensity: np.ndarray, idx: int, half_win: int) -> float:
    """Topographic prominence of the local maximum at *idx*.

    Peak prominence is the height above the highest of the two surrounding
    *key cols* — the lowest point on the path from the peak to the next
    higher peak on each side (searched at most *half_win* points out; the
    same definition ``scipy.signal.find_peaks`` uses).  Unlike a plain
    windowed minimum this is what separates a real peak from a noise bump
    riding on a broad structure: on the rising tail of a strong peak (or on
    background-estimation residue) the uphill key col stays close to the
    bump, so its prominence collapses to the noise level, while a genuine
    reflection keeps a large prominence above the surrounding valleys.

    *idx* must point at a local maximum (see the candidate snapping in
    :func:`find_peaks`).
    """
    height = float(intensity[idx])
    n = intensity.size
    left_col = height
    i = idx - 1
    while i >= 0 and idx - i <= half_win:
        value = float(intensity[i])
        if value > height:
            break
        if value < left_col:
            left_col = value
        i -= 1
    right_col = height
    i = idx + 1
    while i < n and i - idx <= half_win:
        value = float(intensity[i])
        if value > height:
            break
        if value < right_col:
            right_col = value
        i += 1
    return height - max(left_col, right_col)


def find_peaks(
    two_theta: np.ndarray,
    intensity: np.ndarray,
    sensitivity: str = "medium",
    min_distance: int = 1,
    snr_threshold: float | None = None,
) -> list[Peak]:
    """Find diffraction peaks in a 1-D pattern.

    The reference software feature: *Peak search* (Pattern menu, automatic in raw-data
    processing).  Algorithm: first-derivative zero-crossing with SNR and
    second-derivative (curvature) filtering.

    Parameters
    ----------
    two_theta:
        1-D array of scattering angles (degrees 2θ).
    intensity:
        1-D array of (background-subtracted) intensities.
    sensitivity:
        One of ``'low'``, ``'medium'`` (default), ``'high'``.  Controls the
        SNR threshold and minimum prominence.
    min_distance:
        Minimum number of data points between accepted peaks.
    snr_threshold:
        Override the SNR threshold from the sensitivity preset.

    Returns
    -------
    list[Peak]
        Detected peaks sorted by 2θ.  ``intensity`` is set to the peak
        height; ``fwhm`` is estimated from the second derivative at the
        apex (Gaussian approximation) if possible, else ``None``.
    """
    two_theta = np.asarray(two_theta, dtype=np.float64)
    intensity = np.asarray(intensity, dtype=np.float64)
    if two_theta.shape != intensity.shape:
        raise ValueError("two_theta and intensity must have the same shape")
    if two_theta.ndim != 1 or two_theta.size < 3:
        return []

    if sensitivity not in _SENSITIVITY:
        raise ValueError(
            f"sensitivity must be one of {list(_SENSITIVITY)}, got {sensitivity!r}"
        )
    preset_snr, preset_prom = _SENSITIVITY[sensitivity]
    if snr_threshold is None:
        snr_threshold = preset_snr
    min_prominence = preset_prom

    noise = _noise_estimate(intensity)
    # The MAD estimate collapses on (near-)noiseless data — synthetic
    # patterns, heavily smoothed data, or background-subtracted flat
    # regions that are exactly zero.  Every numerical residue (SNIP
    # overshoot, smoothing ringing) then passes the SNR / prominence tests
    # and the peak list fills with artifacts, which in turn poisons the
    # search-match FoM scoring (P_npeaks rewards dense junk reference
    # cards that happen to correlate with the artifacts).  Guard: when the
    # estimate is negligible relative to the signal scale, fall back to a
    # signal-relative floor (1% of the pattern std, which is peak-dominated
    # for diffraction patterns).
    signal = float(intensity.std())
    if noise <= max(1e-9, 1e-3 * signal):
        noise = max(signal * 0.01, 1e-12)

    # First derivative (central differences, interior points).
    dy = np.gradient(intensity)
    # Second derivative.
    d2y = np.gradient(dy)

    candidates: list[tuple[int, float]] = []
    # A peak is where the first derivative crosses from + to - and the
    # second derivative is negative (concave down).  The crossing can land
    # one point off the apex (central differences), so snap each candidate
    # to the local maximum first — this also collapses flank crossings of
    # the same summit into one candidate.
    for i in range(1, two_theta.size - 1):
        zero_crossing = (dy[i - 1] > 0.0 >= dy[i]) or (
            dy[i - 1] >= 0.0 and dy[i] < 0.0
        )
        if zero_crossing and d2y[i] < 0.0:
            j = i
            while j + 1 < two_theta.size and intensity[j + 1] > intensity[j]:
                j += 1
            while j - 1 >= 0 and intensity[j - 1] > intensity[j]:
                j -= 1
            candidates.append((j, float(intensity[j])))

    if not candidates:
        return []

    # Sort by descending height to greedily pick the strongest peaks first.
    candidates.sort(key=lambda c: c[1], reverse=True)

    # Prominence search half-window in points.  The search must reach the
    # valley around a reflection of the candidate's own width — a broad
    # weak line (FWHM 0.3° ≈ 15 points at 0.02°/step) would otherwise show
    # only a noise-level prominence and be dropped — while staying narrow
    # for sharp noise bumps riding on broad tails (their uphill key col
    # then collapses the prominence to the noise level).  Floor 5 points
    # (0.1° at the typical step); cap 50 points (1°) bounds the walk.
    step = float(two_theta[1] - two_theta[0]) if two_theta.size > 1 else 1.0
    if step <= 0.0:
        step = 1.0

    accepted: list[Peak] = []
    used_indices: list[int] = []
    for idx, height in candidates:
        # Minimum distance constraint.
        if any(abs(idx - u) < min_distance for u in used_indices):
            continue
        # SNR threshold.
        if height < snr_threshold * noise:
            continue
        # Width-adaptive prominence half-window (points).
        fwhm_pts = 0.0
        if d2y[idx] < 0.0 and height > 0.0:
            d2y_deg = float(d2y[idx]) / (step ** 2)
            if d2y_deg < 0.0:
                sigma = np.sqrt(-height / d2y_deg)
                fwhm_pts = 2.0 * np.sqrt(2.0 * np.log(2.0)) * sigma / step
        prom_half_win = int(min(50, max(5, round(fwhm_pts / 2.0))))
        # Prominence above the surrounding key cols.
        prominence = _key_col_prominence(intensity, idx, prom_half_win)
        if prominence < min_prominence * noise:
            continue

        # Estimate FWHM from the second derivative (Gaussian apex):
        # For a Gaussian G(x), G''(c) = -A / σ^2, and FWHM = 2√(2 ln2) σ.
        # => FWHM = 2√(2 ln2) * sqrt(-A / G''(c)).  Here A ≈ height.
        # (d2y is per-point; d2y_deg converts to per-degree.)
        fwhm = None
        if d2y[idx] < 0.0 and height > 0.0:
            d2y_deg = float(d2y[idx]) / (step ** 2)
            if d2y_deg < 0.0:
                sigma = np.sqrt(-height / d2y_deg)
                fwhm = float(2.0 * np.sqrt(2.0 * np.log(2.0)) * sigma)

        accepted.append(
            Peak(
                two_theta=float(two_theta[idx]),
                intensity=height,
                fwhm=fwhm,
            )
        )
        used_indices.append(idx)

    # Sort by 2θ.
    accepted.sort(key=lambda p: p.two_theta)
    return accepted
