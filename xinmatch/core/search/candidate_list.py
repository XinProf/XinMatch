"""Candidate list container for search-match results (Phase 6 / T6.7).

Implements :class:`CandidateList`, the ordered container of FoM-ranked
candidates that backs the Match! *candidate list* GUI panel.  The container
keeps the ranked results, tracks which entries the user has accepted as
"matching" phases, and answers the introspection queries the GUI needs
(sort by column, filter by min FoM, find a candidate by entry id, list
unassociated experimental peaks for a candidate).

The class is GUI-free: it exposes plain Python methods that the GUI layer
(PySide6, Phase 14) will wrap into table-model / view operations.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from xinmatch.core.search.fom import CandidateResult

__all__ = ["CandidateList"]


# Sortable column names exposed by Match!'s candidate list.  "fom" is the
# default; the others correspond to the visible columns in Match!'s GUI
# (entry id, formula, mineral name, FoM, I scale).
_SORT_KEYS: set[str] = {"fom", "entry_id", "formula", "mineral_name", "i_scale"}


@dataclass
class CandidateList:
    """Ordered, mutable list of search-match candidates.

    Match! feature: the *candidate list* panel (bottom-left of the Match!
    GUI) holds the ranked reference entries produced by a search-match
    run.  This container wraps that list plus the "selected phases" set
    (entries the user has double-clicked as matching).

    Attributes
    ----------
    candidates:
        Ranked :class:`CandidateResult` list (sorted by FoM desc by
        default).  The list is mutated in place by :meth:`sort_by_fom`
        and :meth:`sort_by`.
    selected_ids:
        Set of entry ids the user has accepted as matching phases
        (double-click action in Match!).  Tracked separately from the
        ranking so that re-sorting / re-running search-match preserves
        the selection.
    n_exp_peaks:
        Number of experimental peaks the search-match was run against.
        Used by :meth:`show_unassociated_peaks` to enumerate the
        ``[0, n_exp_peaks)`` index range.
    """

    candidates: list[CandidateResult] = field(default_factory=list)
    selected_ids: set[str] = field(default_factory=set)
    n_exp_peaks: int = 0

    # ------------------------------------------------------------------ #
    # Container protocol
    # ------------------------------------------------------------------ #
    def __len__(self) -> int:
        return len(self.candidates)

    def __iter__(self) -> Iterator[CandidateResult]:
        return iter(self.candidates)

    def __getitem__(self, idx: int) -> CandidateResult:
        return self.candidates[idx]

    # ------------------------------------------------------------------ #
    # Sorting / filtering
    # ------------------------------------------------------------------ #
    def sort_by_fom(self) -> None:
        """Re-sort the candidate list by descending FoM (in place).

        Match! feature: clicking the "FoM" column header in the
        candidate list.  Stable sort — ties preserve the current order.
        """
        self.candidates.sort(key=lambda r: r.fom, reverse=True)

    def sort_by(self, name: str) -> None:
        """Sort by a named column (in place).

        Match! feature: clicking any column header in the candidate
        list.  Supported keys: ``fom``, ``entry_id``, ``formula``,
        ``mineral_name``, ``i_scale``.

        Parameters
        ----------
        name:
            Column name (case-insensitive).

        Raises
        ------
        ValueError
            If *name* is not a recognised sort key.
        """
        key = name.lower()
        if key not in _SORT_KEYS:
            raise ValueError(
                f"unknown sort key {name!r}; expected one of {sorted(_SORT_KEYS)}"
            )
        if key == "fom":
            self.sort_by_fom()
        elif key == "entry_id":
            self.candidates.sort(key=lambda r: r.entry.entry_id)
        elif key == "formula":
            self.candidates.sort(key=lambda r: r.entry.formula)
        elif key == "mineral_name":
            self.candidates.sort(
                key=lambda r: (r.entry.mineral_name or "", r.entry.entry_id)
            )
        elif key == "i_scale":
            self.candidates.sort(key=lambda r: r.i_scale, reverse=True)

    def filter(self, min_fom: float = 0.0) -> CandidateList:
        """Return a new list keeping only candidates with ``fom >= min_fom``.

        Match! feature: the *Min. FoM* search-match option (default 0.6)
        restricts the candidate list to entries above a threshold.

        The selection state is preserved: any selected entry that fails
        the filter is still dropped from the new list's ``candidates``
        (it can no longer be displayed), but its id stays in
        ``selected_ids`` so a re-filter with a lower threshold can show
        it again.

        Parameters
        ----------
        min_fom:
            Minimum FoM threshold (default 0.0 — no filtering).

        Returns
        -------
        CandidateList
            A new instance; the original is not mutated.
        """
        kept = [c for c in self.candidates if c.fom >= min_fom]
        return CandidateList(
            candidates=kept,
            selected_ids=set(self.selected_ids),
            n_exp_peaks=self.n_exp_peaks,
        )

    # ------------------------------------------------------------------ #
    # Lookup / selection
    # ------------------------------------------------------------------ #
    def get_entry(self, entry_id: str) -> CandidateResult | None:
        """Return the candidate with *entry_id*, or ``None`` if absent."""
        for c in self.candidates:
            if c.entry.entry_id == entry_id:
                return c
        return None

    def select(self, entry_id: str) -> bool:
        """Mark *entry_id* as a selected (matching) phase.

        Match! feature: double-clicking a candidate row in the candidate
        list to accept it as a matching phase.

        Returns
        -------
        bool
            ``True`` if the entry was present and is now selected;
            ``False`` if the entry is not in the candidate list (the
            selection is left unchanged in that case).
        """
        if self.get_entry(entry_id) is None:
            return False
        self.selected_ids.add(entry_id)
        return True

    def unselect(self, entry_id: str) -> bool:
        """Remove *entry_id* from the selected-phase set.

        Match! feature: right-click → "Remove from selection" in the
        candidate list.

        Returns
        -------
        bool
            ``True`` if the id was previously selected and is now
            removed; ``False`` if it was not selected.
        """
        if entry_id not in self.selected_ids:
            return False
        self.selected_ids.discard(entry_id)
        return True

    def get_selected(self) -> list[CandidateResult]:
        """Return all currently-selected candidates in candidate-list order.

        Match! feature: the "selected phases" subset shown highlighted
        in the candidate list and feeding into quantitative analysis
        (Phase 8) and Rietveld refinement (Phase 10).
        """
        return [c for c in self.candidates if c.entry.entry_id in self.selected_ids]

    # ------------------------------------------------------------------ #
    # Peak introspection
    # ------------------------------------------------------------------ #
    def show_unassociated_peaks(self, entry_id: str) -> list[int]:
        """Return experimental peak indices not associated with *entry_id*.

        Match! feature: the *Show uncorrelated peaks* option
        (``Ctrl+Shift+K``) highlights experimental peaks that have not
        been correlated to the candidate's reference pattern.  This
        method returns the integer indices into the original
        ``exp_peaks`` list so the GUI can highlight them in the pattern
        graphics.

        Parameters
        ----------
        entry_id:
            Candidate entry id whose correlation pairs are inspected.

        Returns
        -------
        list[int]
            Indices in ``[0, n_exp_peaks)`` that are not present as the
            ``exp_idx`` of any ``(exp_idx, ref_idx)`` pair for that
            candidate.  Returns an empty list if the candidate is not
            found or if ``n_exp_peaks`` is unset.
        """
        if self.n_exp_peaks <= 0:
            return []
        candidate = self.get_entry(entry_id)
        if candidate is None:
            return []
        associated = {ei for ei, _ in candidate.pairs}
        return [i for i in range(self.n_exp_peaks) if i not in associated]

    # ------------------------------------------------------------------ #
    # Serialisation
    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict (project file / JSON export)."""
        return {
            "candidates": [c.to_dict() for c in self.candidates],
            "selected_ids": sorted(self.selected_ids),
            "n_exp_peaks": int(self.n_exp_peaks),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CandidateList:
        """Reconstruct from :meth:`to_dict` output."""
        return cls(
            candidates=[CandidateResult.from_dict(c) for c in d.get("candidates", [])],
            selected_ids=set(d.get("selected_ids", [])),
            n_exp_peaks=int(d.get("n_exp_peaks", 0)),
        )

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialise to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> CandidateList:
        """Reconstruct from :meth:`to_json` output."""
        return cls.from_dict(json.loads(text))


# TODO(T6.7): Project.candidates is currently list[tuple[Entry, float]]; the
# long-term plan is to migrate it to CandidateList so the candidate-list
# state (selection, sort order, n_exp_peaks) lives in the project file.
# Left as a follow-up so Phase 6 lands without churning the Project API
# (which is consumed by Phase 8 quant / Phase 14 GUI).
