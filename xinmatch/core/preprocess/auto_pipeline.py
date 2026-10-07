"""Automatic raw-data processing pipeline.

Implements Match!'s *Automatic raw data processing* (run on pattern import
and via the corresponding options dialog).  The pipeline chains the
preprocessing steps in the order recommended by Match!:

    smoothing → background estimation → background subtraction →
    Kα2 stripping → peak search

Each step can be enabled/disabled and configured via the *config*
dictionary.
"""

from __future__ import annotations

import contextlib
import logging

import numpy as np

from xinmatch.core.model import Pattern, Peak
from xinmatch.core.peak.peak_refine import refine_peak_position
from xinmatch.core.peak.peak_search import find_peaks
from xinmatch.core.preprocess.alpha2 import strip_alpha2
from xinmatch.core.preprocess.background import (
    estimate_background,
    subtract_background,
)
from xinmatch.core.preprocess.smoothing import smooth

logger = logging.getLogger(__name__)

DEFAULT_CONFIG: dict = {
    "smooth": True,
    "smooth_method": "savgol",
    "smooth_window": 11,
    "smooth_polyorder": 3,
    "background": True,
    "background_method": "snip",
    "background_window": 20,
    "strip_alpha2": True,
    "wavelength_kalpha1": 1.5406,
    "wavelength_kalpha2": 1.5444,
    "alpha2_ratio": 0.5,
    "peak_search": True,
    "peak_sensitivity": "medium",
}


def auto_process(
    pattern: Pattern,
    config: dict | None = None,
) -> tuple[Pattern, list[Peak]]:
    """Run the full automatic raw-data processing pipeline.

    Match! feature: *Automatic raw data processing* (on import).  Order:
    smoothing → background → subtract → Kα2 stripping → peak search.

    Parameters
    ----------
    pattern:
        Input diffraction pattern.
    config:
        Optional configuration dict (merged on top of
        :data:`DEFAULT_CONFIG`).  Use boolean flags to toggle steps.

    Returns
    -------
    tuple[Pattern, list[Peak]]
        Processed pattern and the list of detected peaks.
    """
    cfg = dict(DEFAULT_CONFIG)
    if config:
        cfg.update(config)

    two_theta = pattern.two_theta
    intensity = pattern.intensity

    # 1. Smoothing.
    if cfg.get("smooth", True):
        intensity = smooth(
            intensity,
            method=cfg.get("smooth_method", "savgol"),
            window=int(cfg.get("smooth_window", 11)),
            polyorder=int(cfg.get("smooth_polyorder", 3)),
        )

    # 2. Background estimation.
    if cfg.get("background", True):
        bg = estimate_background(
            two_theta,
            intensity,
            method=cfg.get("background_method", "snip"),
            window=int(cfg.get("background_window", 20)),
        )
        intensity = subtract_background(intensity, bg)

    # 3. Kα2 stripping.
    if cfg.get("strip_alpha2", True):
        intensity = strip_alpha2(
            two_theta,
            intensity,
            wavelength_kalpha1=float(cfg.get("wavelength_kalpha1", 1.5406)),
            wavelength_kalpha2=float(cfg.get("wavelength_kalpha2", 1.5444)),
            ratio=float(cfg.get("alpha2_ratio", 0.5)),
        )

    # 4. Peak search + sub-step position refinement.
    peaks: list[Peak] = []
    if cfg.get("peak_search", True):
        peaks = find_peaks(
            two_theta,
            intensity,
            sensitivity=cfg.get("peak_sensitivity", "medium"),
        )
        # Refine each peak position to sub-step accuracy.
        for p in peaks:
            idx = int(np.argmin(np.abs(two_theta - p.two_theta)))
            with contextlib.suppress(ValueError, RuntimeError):
                p.two_theta = refine_peak_position(
                    two_theta, intensity, idx, method="gaussian"
                )

    processed = Pattern(
        two_theta=two_theta,
        intensity=intensity,
        wavelength=pattern.wavelength,
        step=pattern.step,
        metadata=dict(pattern.metadata),
    )
    return processed, peaks
