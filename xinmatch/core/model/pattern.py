"""Diffraction pattern data model.

Implements :class:`Pattern`, the core container for a powder diffraction
pattern.  Supports slicing, interpolation (resampling), and unit conversion
between 2θ (degrees), d-spacing (Å), and momentum transfer Q (Å⁻¹).

Corresponds to the reference software's *diffraction pattern* object displayed in the
upper-left graphics panel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class Pattern:
    """A 1-D powder diffraction pattern.

    Parameters
    ----------
    two_theta:
        Scattering angle 2θ in **degrees**.
    intensity:
        Diffracted intensity (counts or arbitrary units).  Must have the same
        length as *two_theta*.
    wavelength:
        Radiation wavelength in **angstroms**.
    step:
        Step width in degrees 2θ.  ``None`` if unknown or non-uniform.
    metadata:
        Free-form dictionary of experiment/sample metadata (instrument,
        sample name, date, …).
    """

    two_theta: np.ndarray
    intensity: np.ndarray
    wavelength: float = 1.5406  # Cu Kα1 default
    step: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.two_theta = np.asarray(self.two_theta, dtype=np.float64)
        self.intensity = np.asarray(self.intensity, dtype=np.float64)
        if self.two_theta.shape != self.intensity.shape:
            raise ValueError(
                f"two_theta and intensity must have the same shape, "
                f"got {self.two_theta.shape} and {self.intensity.shape}"
            )
        if self.two_theta.ndim != 1:
            raise ValueError("two_theta must be a 1-D array")

    # ------------------------------------------------------------------
    # Basic container protocol
    # ------------------------------------------------------------------
    def __len__(self) -> int:
        return int(self.two_theta.size)

    def __getitem__(self, idx) -> Pattern:
        """Slice the pattern by point index or 2θ range.

        Integer / slice indexing selects by point index.  A tuple
        ``(lo, hi)`` selects the 2θ interval ``[lo, hi]``.
        """
        if isinstance(idx, tuple) and len(idx) == 2:
            lo, hi = idx
            mask = (self.two_theta >= lo) & (self.two_theta <= hi)
            return Pattern(
                self.two_theta[mask],
                self.intensity[mask],
                self.wavelength,
                self.step,
                dict(self.metadata),
            )
        return Pattern(
            self.two_theta[idx],
            self.intensity[idx],
            self.wavelength,
            self.step,
            dict(self.metadata),
        )

    # ------------------------------------------------------------------
    # Unit conversions
    # ------------------------------------------------------------------
    @property
    def theta(self) -> np.ndarray:
        """Scattering angle θ in radians."""
        return np.asarray(np.radians(self.two_theta) / 2.0, dtype=np.float64)

    @property
    def d_spacing(self) -> np.ndarray:
        """d-spacing in Å via Bragg's law ``λ = 2 d sin θ``."""
        with np.errstate(divide="ignore", invalid="ignore"):
            d = self.wavelength / (2.0 * np.sin(self.theta))
        return np.asarray(d, dtype=np.float64)

    @property
    def q(self) -> np.ndarray:
        """Momentum transfer ``Q = 4π sin θ / λ = 2π / d`` in Å⁻¹."""
        return 2.0 * np.pi / self.d_spacing

    def two_theta_to_d(self, two_theta: float | np.ndarray) -> float | np.ndarray:
        """Convert 2θ (degrees) to d-spacing (Å)."""
        theta = np.radians(np.asarray(two_theta, dtype=np.float64)) / 2.0
        with np.errstate(divide="ignore", invalid="ignore"):
            return self.wavelength / (2.0 * np.sin(theta))

    def d_to_two_theta(self, d: float | np.ndarray) -> float | np.ndarray:
        """Convert d-spacing (Å) to 2θ (degrees)."""
        d = np.asarray(d, dtype=np.float64)
        with np.errstate(divide="ignore", invalid="ignore"):
            sin_theta = self.wavelength / (2.0 * d)
        sin_theta = np.clip(sin_theta, -1.0, 1.0)
        return np.degrees(2.0 * np.arcsin(sin_theta))

    # ------------------------------------------------------------------
    # Resampling
    # ------------------------------------------------------------------
    def resample(self, new_two_theta: np.ndarray) -> Pattern:
        """Linearly interpolate intensities onto a new 2θ grid.

        Parameters
        ----------
        new_two_theta:
            New 2θ grid (degrees).  Must be monotonically increasing.
        """
        new_two_theta = np.asarray(new_two_theta, dtype=np.float64)
        new_intensity = np.interp(
            new_two_theta, self.two_theta, self.intensity, left=0.0, right=0.0
        )
        step = float(np.diff(new_two_theta).mean()) if new_two_theta.size > 1 else None
        return Pattern(
            new_two_theta,
            new_intensity,
            self.wavelength,
            step,
            dict(self.metadata),
        )

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "two_theta": self.two_theta.tolist(),
            "intensity": self.intensity.tolist(),
            "wavelength": float(self.wavelength),
            "step": self.step,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Pattern:
        return cls(
            two_theta=np.array(d["two_theta"], dtype=np.float64),
            intensity=np.array(d["intensity"], dtype=np.float64),
            wavelength=float(d.get("wavelength", 1.5406)),
            step=d.get("step"),
            metadata=dict(d.get("metadata", {})),
        )
