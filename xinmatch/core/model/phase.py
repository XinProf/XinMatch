"""Selected phase data model.

Implements :class:`Phase`, a reference-database :class:`Entry` that has been
selected as present in the sample, together with a scale factor, an optional
2θ offset, and the peak-correlation table linking experimental peaks to the
entry's reference peaks.

Corresponds to a row in Match!'s *match list*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .entry import Entry


@dataclass
class Phase:
    """A phase selected as present in the sample.

    Parameters
    ----------
    entry:
        The reference-database entry for this phase.
    scale_factor:
        Intensity scale factor applied to the reference pattern.
    two_theta_shift:
        Global 2θ offset (degrees) applied to all reference peaks of this
        phase.
    weight_fraction:
        Quantitative weight fraction (0–1).  ``None`` if not yet quantified.
    correlations:
        List of ``(exp_peak_index, ref_peak_index)`` tuples recording which
        experimental peak was correlated to which reference peak.
    """

    entry: Entry
    scale_factor: float = 1.0
    two_theta_shift: float = 0.0
    weight_fraction: float | None = None
    correlations: list[tuple[int, int]] = field(default_factory=list)

    def shifted_two_theta(self, wavelength: float) -> Any:
        """Return the reference d-spacings converted to 2θ with the shift.

        Uses *wavelength* (Å) for the d → 2θ conversion.  The result is
        ``d_to_two_theta(d) + two_theta_shift``.
        """
        import numpy as np

        d = self.entry.d_spacings
        with np.errstate(divide="ignore", invalid="ignore"):
            sin_theta = np.clip(wavelength / (2.0 * d), -1.0, 1.0)
        two_theta = np.degrees(2.0 * np.arcsin(sin_theta))
        return two_theta + self.two_theta_shift

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry": self.entry.to_dict(),
            "scale_factor": float(self.scale_factor),
            "two_theta_shift": float(self.two_theta_shift),
            "weight_fraction": self.weight_fraction,
            "correlations": [list(c) for c in self.correlations],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Phase:
        return cls(
            entry=Entry.from_dict(d["entry"]),
            scale_factor=float(d.get("scale_factor", 1.0)),
            two_theta_shift=float(d.get("two_theta_shift", 0.0)),
            weight_fraction=d.get("weight_fraction"),
            correlations=[tuple(c) for c in d.get("correlations", [])],
        )
