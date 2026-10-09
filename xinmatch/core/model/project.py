"""Project data model.

Implements :class:`Project`, the top-level container holding all the state of
an analysis session: diffraction patterns, peak list, candidate list, selected
phases, restraints, parameters, and an undo/redo stack.

Corresponds to a reference-software project file.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from .entry import Entry
from .pattern import Pattern
from .peak import Peak
from .phase import Phase
from .restraints import Restraints

MAX_UNDO = 200


@dataclass
class Project:
    """A XinMatch analysis project.

    Attributes
    ----------
    patterns:
        Experimental diffraction patterns (the first is the *anchor* pattern).
    peaks:
        Peak list extracted from the anchor pattern.
    candidates:
        Current candidate list (reference entries ranked by FoM).
    selected_phases:
        Phases the user has accepted as present.
    restraints:
        Active search-match restraints.
    parameters:
        Free-form parameters / options snapshot.
    """

    patterns: list[Pattern] = field(default_factory=list)
    peaks: list[Peak] = field(default_factory=list)
    candidates: list[tuple[Entry, float]] = field(default_factory=list)
    selected_phases: list[Phase] = field(default_factory=list)
    restraints: Restraints = field(default_factory=Restraints)
    parameters: dict[str, Any] = field(default_factory=dict)

    _undo_stack: list[bytes] = field(default_factory=list, repr=False)
    _redo_stack: list[bytes] = field(default_factory=list, repr=False)

    # ------------------------------------------------------------------
    # Undo / redo
    # ------------------------------------------------------------------
    def snapshot(self) -> None:
        """Push the current state onto the undo stack (call before a change)."""
        import pickle

        state = pickle.dumps(self._state_tuple())
        self._undo_stack.append(state)
        if len(self._undo_stack) > MAX_UNDO:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo(self) -> bool:
        """Restore the previous state.  Returns ``False`` if nothing to undo."""
        import pickle

        if not self._undo_stack:
            return False
        current = pickle.dumps(self._state_tuple())
        self._redo_stack.append(current)
        self._restore(pickle.loads(self._undo_stack.pop()))
        return True

    def redo(self) -> bool:
        """Re-apply the last undone change.  Returns ``False`` if nothing."""
        import pickle

        if not self._redo_stack:
            return False
        current = pickle.dumps(self._state_tuple())
        self._undo_stack.append(current)
        self._restore(pickle.loads(self._redo_stack.pop()))
        return True

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    # ------------------------------------------------------------------
    # Internal state helpers
    # ------------------------------------------------------------------
    def _state_tuple(self) -> tuple:
        return (
            copy.deepcopy(self.patterns),
            copy.deepcopy(self.peaks),
            copy.deepcopy(self.candidates),
            copy.deepcopy(self.selected_phases),
            copy.deepcopy(self.restraints),
            copy.deepcopy(self.parameters),
        )

    def _restore(self, state: tuple) -> None:
        (
            self.patterns,
            self.peaks,
            self.candidates,
            self.selected_phases,
            self.restraints,
            self.parameters,
        ) = state

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "patterns": [p.to_dict() for p in self.patterns],
            "peaks": [p.to_dict() for p in self.peaks],
            "candidates": [
                {"entry": e.to_dict(), "fom": float(fom)} for e, fom in self.candidates
            ],
            "selected_phases": [p.to_dict() for p in self.selected_phases],
            "restraints": self.restraints.to_dict(),
            "parameters": self.parameters,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Project:
        return cls(
            patterns=[Pattern.from_dict(p) for p in d.get("patterns", [])],
            peaks=[Peak.from_dict(p) for p in d.get("peaks", [])],
            candidates=[
                (Entry.from_dict(c["entry"]), float(c["fom"]))
                for c in d.get("candidates", [])
            ],
            selected_phases=[Phase.from_dict(p) for p in d.get("selected_phases", [])],
            restraints=Restraints.from_dict(d.get("restraints", {})),
            parameters=dict(d.get("parameters", {})),
        )

    def save(self, path: str) -> None:
        """Serialise the project to a JSON file."""
        import json

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> Project:
        """Load a project from a JSON file."""
        import json

        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))
