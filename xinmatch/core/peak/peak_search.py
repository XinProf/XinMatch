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
    if noise <= 0.0:
        noise = max(intensity.std() * 0.01, 1e-12)

    # First derivative (central differences, interior points).
    dy = np.gradient(intensity)
    # Second derivative.
    d2y = np.gradient(dy)

    candidates: list[tuple[int, float]] = []
    # A peak is where the first derivative crosses from + to - and the
    # second derivative is negative (concave down).
    for i in range(1, two_theta.size - 1):
        zero_crossing = (dy[i - 1] > 0.0 >= dy[i]) or (
            dy[i - 1] >= 0.0 and dy[i] < 0.0
        )
        if zero_crossing and d2y[i] < 0.0:
            candidates.append((i, float(intensity[i])))

    if not candidates:
        return []

    # Sort by descending height to greedily pick the strongest peaks first.
    candidates.sort(key=lambda c: c[1], reverse=True)

    accepted: list[Peak] = []
    used_indices: list[int] = []
    for idx, height in candidates:
        # Minimum distance constraint.
        if any(abs(idx - u) < min_distance for u in used_indices):
            continue
        # SNR threshold.
        if height < snr_threshold * noise:
            continue
        # Prominence: height above the local minimum in a window.
        half_win = max(min_distance, 3)
        lo = max(0, idx - half_win)
        hi = min(two_theta.size, idx + half_win + 1)
        local_min = float(intensity[lo:hi].min())
        prominence = height - local_min
        if prominence < min_prominence * noise:
            continue

        # Estimate FWHM from the second derivative (Gaussian apex):
        # For a Gaussian G(x), G''(c) = -A / σ^2, and FWHM = 2√(2 ln2) σ.
        # => FWHM = 2√(2 ln2) * sqrt(-A / G''(c)).  Here A ≈ height.
        fwhm = None
        if d2y[idx] < 0.0:
            step = float(two_theta[1] - two_theta[0]) if two_theta.size > 1 else 1.0
            # d2y is per-point; convert to per-degree.
            d2y_deg = d2y[idx] / (step ** 2)
            sigma = np.sqrt(-height / d2y_deg) if height > 0 else 0.0
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
