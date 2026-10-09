"""Reference database entry data model.

Implements :class:`Entry`, a single reference-database record (e.g. one COD
entry) containing the chemical formula, crystallographic cell, space group,
and the d–I peak table used for search-match.

Corresponds to a row in the reference software's *candidate list* and the reference pattern
database entries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class CellParams:
    """Unit-cell parameters (a, b, c in Å; α, β, γ in degrees)."""

    a: float
    b: float
    c: float
    alpha: float = 90.0
    beta: float = 90.0
    gamma: float = 90.0

    def to_dict(self) -> dict[str, float]:
        return {
            "a": self.a, "b": self.b, "c": self.c,
            "alpha": self.alpha, "beta": self.beta, "gamma": self.gamma,
        }

    @classmethod
    def from_dict(cls, d: dict[str, float]) -> CellParams:
        return cls(
            a=float(d["a"]), b=float(d["b"]), c=float(d["c"]),
            alpha=float(d.get("alpha", 90.0)),
            beta=float(d.get("beta", 90.0)),
            gamma=float(d.get("gamma", 90.0)),
        )


# Regex for parsing a formula sum like "B6 La0.987" or "C Ca O3"
_ELEMENT_RE = re.compile(r"([A-Z][a-z]?)(\d*\.?\d*)")


def parse_formula(formula: str) -> dict[str, float]:
    """Parse a formula string into ``{element: count}``.

    Examples
    --------
    >>> parse_formula("B6 La0.987")
    {'B': 6.0, 'La': 0.987}
    >>> parse_formula("C Ca O3")
    {'C': 1.0, 'Ca': 1.0, 'O': 3.0}
    """
    result: dict[str, float] = {}
    for elem, count in _ELEMENT_RE.findall(formula):
        result[elem] = result.get(elem, 0.0) + (float(count) if count else 1.0)
    return result


@dataclass
class Entry:
    """A reference-database entry.

    Parameters
    ----------
    entry_id:
        Unique identifier (e.g. COD number, or ICDD PDF card number).
    formula:
        Chemical formula sum (e.g. ``"C Ca O3"``).
    d_spacings:
        d-spacings in Å, sorted by **descending intensity** (the reference software
        convention for the reference peak table).
    intensities:
        Relative intensities (I/I₀, max = 1000 in the reference software convention, but we
        store the raw values and normalise on demand).
    mineral_name:
        Trivial / mineral name.
    cell:
        Unit-cell parameters.
    space_group:
        Hermann–Mauguin space-group symbol.
    hkl:
        Miller indices for each (d, I) pair, aligned with *d_spacings*.
    literature:
        Dict with keys ``author``, ``journal``, ``year``, ``volume``,
        ``pages``, ``title``.
    quality:
        Quality flag / mark.
    elements:
        Set of elements present.  Derived from *formula* if not given.
    """

    entry_id: str
    formula: str
    d_spacings: np.ndarray
    intensities: np.ndarray
    mineral_name: str | None = None
    cell: CellParams | None = None
    space_group: str | None = None
    hkl: list[tuple[int, int, int]] | None = None
    literature: dict[str, Any] = field(default_factory=dict)
    quality: str = ""
    elements: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        self.d_spacings = np.asarray(self.d_spacings, dtype=np.float64)
        self.intensities = np.asarray(self.intensities, dtype=np.float64)
        if not self.elements:
            self.elements = frozenset(parse_formula(self.formula).keys())

    @property
    def n_peaks(self) -> int:
        return int(self.d_spacings.size)

    @property
    def intensity_max(self) -> float:
        return float(self.intensities.max()) if self.intensities.size else 0.0

    def normalized_intensities(self, scale: float = 1000.0) -> np.ndarray:
        """Return intensities normalised to *scale* (the reference software uses 1000)."""
        if self.intensities.size == 0:
            return self.intensities.copy()
        imax = self.intensities.max()
        if imax == 0:
            return self.intensities.copy()
        return self.intensities / imax * scale

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "formula": self.formula,
            "mineral_name": self.mineral_name,
            "cell": self.cell.to_dict() if self.cell else None,
            "space_group": self.space_group,
            "d_spacings": self.d_spacings.tolist(),
            "intensities": self.intensities.tolist(),
            "hkl": [list(h) for h in self.hkl] if self.hkl else None,
            "literature": self.literature,
            "quality": self.quality,
            "elements": sorted(self.elements),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Entry:
        hkl = d.get("hkl")
        cell = d.get("cell")
        return cls(
            entry_id=str(d["entry_id"]),
            formula=str(d["formula"]),
            d_spacings=np.array(d["d_spacings"], dtype=np.float64),
            intensities=np.array(d["intensities"], dtype=np.float64),
            mineral_name=d.get("mineral_name"),
            cell=CellParams.from_dict(cell) if cell else None,
            space_group=d.get("space_group"),
            hkl=[tuple(h) for h in hkl] if hkl else None,
            literature=dict(d.get("literature", {})),
            quality=str(d.get("quality", "")),
        )
