"""Diffraction peak data model.

Implements :class:`Peak`, a single diffraction peak with position, intensity,
FWHM, optional d-spacing and Miller indices, and bookkeeping flags used by the
search-match correlation engine.

Corresponds to a row in Match!'s *peak list* (2θ / intensity / FWHM columns).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Peak:
    """A single diffraction peak.

    Parameters
    ----------
    two_theta:
        Peak position in degrees 2θ.
    intensity:
        Peak intensity.  Normally the **integrated** intensity (area), not
        the height — see Match!'s peak list documentation.
    fwhm:
        Full width at half maximum in degrees 2θ.  ``None`` if not fitted.
    d:
        d-spacing in Å.  Derived from *two_theta* and the pattern wavelength
        if not provided.
    hkl:
        Miller indices ``(h, k, l)``.  ``None`` for experimental peaks before
        indexing.
    correlated:
        ``True`` if this peak has been correlated to a reference-database
        peak during search-match.
    marked:
        ``True`` if the user has explicitly marked this peak (used by
        *search-match (marked peaks only)*).
    excluded:
        ``True`` if this peak is excluded from FoM calculation (area
        exclusion).
    """

    two_theta: float
    intensity: float
    fwhm: float | None = None
    d: float | None = None
    hkl: tuple[int, int, int] | None = None
    correlated: bool = False
    marked: bool = False
    excluded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "two_theta": float(self.two_theta),
            "intensity": float(self.intensity),
            "fwhm": self.fwhm,
            "d": self.d,
            "hkl": list(self.hkl) if self.hkl is not None else None,
            "correlated": self.correlated,
            "marked": self.marked,
            "excluded": self.excluded,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Peak:
        hkl = d.get("hkl")
        return cls(
            two_theta=float(d["two_theta"]),
            intensity=float(d["intensity"]),
            fwhm=d.get("fwhm"),
            d=d.get("d"),
            hkl=tuple(hkl) if hkl is not None else None,
            correlated=bool(d.get("correlated", False)),
            marked=bool(d.get("marked", False)),
            excluded=bool(d.get("excluded", False)),
        )


def sort_peaks(peaks: list[Peak], key: str = "two_theta") -> list[Peak]:
    """Return a new list of peaks sorted by *key* (``two_theta`` or ``d``)."""
    if key == "two_theta":
        return sorted(peaks, key=lambda p: p.two_theta)
    if key == "d":
        return sorted(peaks, key=lambda p: p.d if p.d is not None else float("inf"))
    raise ValueError(f"unknown sort key: {key!r}")
