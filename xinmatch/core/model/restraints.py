"""Search-match restraints data model.

Implements :class:`Restraints`, the filter conditions applied before / during
search-match.  Element composition uses Match!'s three-state colour coding:

* 🔴 **red**    — element must be **absent** (exclude entries containing it)
* 🟡 **yellow** — element is **optional** (no filtering effect)
* 🟢 **green**  — element must be **present** (require entries containing it)

Corresponds to the *Restraints* tab / periodic table in Match!.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ElementState(str, Enum):
    """Three-state element restraint (Match! colour coding)."""

    EXCLUDE = "red"      # must be absent
    OPTIONAL = "yellow"  # no effect
    REQUIRED = "green"   # must be present


@dataclass
class Restraints:
    """Search-match restraint conditions.

    Only non-default values are stored; missing keys imply *optional*.
    """

    elements: dict[str, ElementState] = field(default_factory=dict)
    crystal_system: str | None = None
    space_group: str | None = None
    density_range: tuple[float, float] | None = None
    color: str | None = None
    year_range: tuple[int, int] | None = None
    author: str | None = None
    mineral_name: str | None = None
    # Sub-file / quality flags (inorganic / organic / quality marks)
    inorganic_only: bool | None = None
    organic_only: bool | None = None
    quality_flags: set[str] = field(default_factory=set)

    # ------------------------------------------------------------------
    # Element state helpers
    # ------------------------------------------------------------------
    def set_element(self, element: str, state: ElementState) -> None:
        """Set the restraint state for *element*.

        Passing :attr:`ElementState.OPTIONAL` removes the entry (optional is
        the default and needs no storage).
        """
        if state == ElementState.OPTIONAL:
            self.elements.pop(element, None)
        else:
            self.elements[element] = state

    def require(self, element: str) -> None:
        """Mark *element* as required (green)."""
        self.set_element(element, ElementState.REQUIRED)

    def exclude(self, element: str) -> None:
        """Mark *element* as excluded (red)."""
        self.set_element(element, ElementState.EXCLUDE)

    def get_state(self, element: str) -> ElementState:
        return self.elements.get(element, ElementState.OPTIONAL)

    def passes_elements(self, entry_elements: set[str]) -> bool:
        """Return ``True`` if *entry_elements* satisfies element restraints."""
        for elem, state in self.elements.items():
            present = elem in entry_elements
            if state == ElementState.REQUIRED and not present:
                return False
            if state == ElementState.EXCLUDE and present:
                return False
        return True

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "elements": {e: s.value for e, s in self.elements.items()},
            "crystal_system": self.crystal_system,
            "space_group": self.space_group,
            "density_range": self.density_range,
            "color": self.color,
            "year_range": self.year_range,
            "author": self.author,
            "mineral_name": self.mineral_name,
            "inorganic_only": self.inorganic_only,
            "organic_only": self.organic_only,
            "quality_flags": sorted(self.quality_flags),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Restraints:
        return cls(
            elements={e: ElementState(s) for e, s in d.get("elements", {}).items()},
            crystal_system=d.get("crystal_system"),
            space_group=d.get("space_group"),
            density_range=tuple(d["density_range"]) if d.get("density_range") else None,
            color=d.get("color"),
            year_range=tuple(d["year_range"]) if d.get("year_range") else None,
            author=d.get("author"),
            mineral_name=d.get("mineral_name"),
            inorganic_only=d.get("inorganic_only"),
            organic_only=d.get("organic_only"),
            quality_flags=set(d.get("quality_flags", [])),
        )
