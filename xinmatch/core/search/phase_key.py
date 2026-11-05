"""Phase-level identity for candidate lists (v3.2.0).

Why this exists
---------------
A reference library holds **many cards for the same phase**: COD has dozens of
BaTiO₃ entries (``96-210-0858`` / ``96-210-0859`` …), several anatase TiO₂ cards,
and a whole family of beryl-type structures.  Two independent problems follow:

* **Benchmarks**: scoring by ``entry_id`` records "found the right phase but a
  sibling card" as a miss — Top-1 reads 7/13 where phase-level Top-1 is 10/13
  (``docs/基准报告-物相检索-v3.md`` §4).
* **Candidate list**: 30+ near-identical cards occupy every Top-N slot.  For
  ``synth_02`` the beryl family takes 7 of the Top-10 while calcite — 0.0017 FoM
  behind the leader — never appears in the Top-60.

Both need the same judgement: *are these two entries the same phase?*  This
module answers that from the entry metadata only (no peak-table comparison, so
it is cheap enough to run over a full candidate list).

Identity rule (all must hold):
1. same element set (``frozenset``);
2. unit-cell axes within ``cell_tol`` (relative) and angles within
   ``angle_tol`` degrees when **both** sides carry a cell — this is what
   separates polymorphs (anatase vs rutile share composition and element set)
   and what makes occupancy-refined variants (``Al1.499`` vs ``Al2``) match:
   their cells are identical, their stoichiometry is not.  Composition is only
   compared (within ``formula_tol``) when a cell is missing on either side;
3. space group agrees when both sides carry one (symbols normalised by
   stripping spaces / case).

Anything missing on either side is treated as "no evidence" and skipped, never
as a mismatch — libraries legitimately lack a cell or a space group for a few
entries.

**Exception (v3.4.1)**: a missing *composition* is **not** skipped when it is the
only evidence available.  When neither side carries a cell, composition is the
sole basis for the judgement, and a card with a NULL/empty formula cannot be
asserted to be the same phase as anything — "no evidence" is not "no
disagreement".  COD-Inorg holds 416/78,035 such cards; letting them match
anything inflated benchmark truth matching and folded them into arbitrary phase
families (``docs/检索基准-31-次相诊断-20261105.md``).  A null-formula card that
*does* carry a cell is still matched on the cell — that is positive evidence.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from xinmatch.core.model import Entry

#: Element token: leading capital, optional lowercase, optional count (incl. decimal).
_ELEMENT_RE = re.compile(r"([A-Z][a-z]?)(\d*\.?\d*)")

DEFAULT_CELL_TOL = 0.01
DEFAULT_ANGLE_TOL = 1.5
DEFAULT_FORMULA_TOL = 0.25


def parse_composition(formula: str | None) -> dict[str, float]:
    """``"Al2 Mg O4"`` → ``{"Al": 2.0, "Mg": 1.0, "O": 4.0}``; ``{}`` when empty.

    A bare element without a count means 1.  Repeated tokens accumulate, so
    ``"Ca O3 C"`` and ``"Ca C O3"`` give the same dict.
    """
    out: dict[str, float] = {}
    if not formula:
        return out
    for element, count in _ELEMENT_RE.findall(formula):
        try:
            value = float(count) if count else 1.0
        except ValueError:  # pragma: no cover - regex already guards the shape
            value = 1.0
        if value <= 0:
            continue
        out[element] = out.get(element, 0.0) + value
    return out


def normalize_formula(formula: str | None) -> str:
    """Canonical formula string: elements sorted, counts trimmed.

    ``"Al1.50 Mg O4"`` → ``"Al1.5MgO4"``.  Two entries with the same canonical
    string are, compositionally, the same phase.
    """
    comp = parse_composition(formula)
    if not comp:
        return (formula or "").replace(" ", "").upper()
    parts: list[str] = []
    for element in sorted(comp):
        count = comp[element]
        text = f"{count:.3f}".rstrip("0").rstrip(".")
        parts.append(element if text == "1" else f"{element}{text}")
    return "".join(parts)


def _cell_of(entry: Entry) -> tuple[float, float, float, float, float, float] | None:
    cell = getattr(entry, "cell", None)
    if cell is None:
        return None
    try:
        values = (
            float(cell.a), float(cell.b), float(cell.c),
            float(cell.alpha), float(cell.beta), float(cell.gamma),
        )
    except (AttributeError, TypeError, ValueError):
        return None
    if any(v <= 0 for v in values[:3]):
        return None
    return values


def _space_group_of(entry: Entry) -> str:
    sg = getattr(entry, "space_group", None) or ""
    return re.sub(r"\s+", "", str(sg)).lower()


def _normalized_composition(comp: dict[str, float]) -> dict[str, float]:
    """Divide through by the smallest count → ratio form (``Z``-independent).

    Library formulas are quoted per **unit cell**, so the same phase appears as
    ``O2 Si`` (Z=3 quartz) and ``O4 Si2`` (Z=6) depending on the card.  Absolute
    counts would call those two different phases; the ratio does not.
    """
    if not comp:
        return {}
    base = min(comp.values())
    if base <= 0:
        return dict(comp)
    return {el: v / base for el, v in comp.items()}


def _composition_agrees(
    a: dict[str, float], b: dict[str, float], tol: float
) -> bool:
    """Ratio-level composition agreement — **requires positive evidence**.

    Called only when a cell is missing on at least one side, i.e. composition is
    the only evidence left.  ``True`` therefore demands that **both** sides carry
    a parseable composition: a NULL/empty formula proves nothing, and answering
    ``True`` for it would let that card match every phase in the library.
    """
    if not a or not b:
        return False
    if set(a) != set(b):
        return False
    norm_a, norm_b = _normalized_composition(a), _normalized_composition(b)
    for element, count in norm_a.items():
        other = norm_b[element]
        if abs(count - other) > max(tol, tol * max(count, other)):
            return False
    return True


def same_phase(
    a: Entry,
    b: Entry,
    *,
    cell_tol: float = DEFAULT_CELL_TOL,
    angle_tol: float = DEFAULT_ANGLE_TOL,
    formula_tol: float = DEFAULT_FORMULA_TOL,
) -> bool:
    """True when *a* and *b* describe the same crystalline phase."""
    if a.entry_id == b.entry_id:
        return True
    comp_a, comp_b = parse_composition(a.formula), parse_composition(b.formula)
    if comp_a and comp_b and set(comp_a) != set(comp_b):
        return False

    cell_a, cell_b = _cell_of(a), _cell_of(b)
    if cell_a is not None and cell_b is not None:
        # 有晶胞就以晶胞为准：它天然区分多晶型与不同相，而且对占位度精修
        # （Al1.499 vs Al2 这类）不敏感——同一结构的占位度变体晶胞几乎相同，
        # 严格比化学计量数反而会把它判成两相。
        for i in range(3):
            if abs(cell_a[i] - cell_b[i]) > max(1e-6, cell_tol * max(cell_a[i], cell_b[i])):
                return False
        for i in range(3, 6):
            if abs(cell_a[i] - cell_b[i]) > angle_tol:
                return False
    elif not _composition_agrees(comp_a, comp_b, formula_tol):
        # 缺晶胞时才退回化学计量比较（此时它是唯一可用证据）。
        return False

    sg_a, sg_b = _space_group_of(a), _space_group_of(b)
    return not (sg_a and sg_b and sg_a != sg_b)


def group_same_phase(
    entries: Sequence[Entry],
    *,
    cell_tol: float = DEFAULT_CELL_TOL,
    angle_tol: float = DEFAULT_ANGLE_TOL,
    formula_tol: float = DEFAULT_FORMULA_TOL,
) -> list[list[int]]:
    """Cluster *entries* (already ranked) into phase families.

    Returns groups of indices, **ordered by their best-ranked member**, so
    ``groups[0][0] == 0`` for a non-empty input.  Grouping is greedy and
    order-preserving: an entry joins the first group whose representative it
    matches, which keeps the strongest card as each family's representative.
    """
    groups: list[list[int]] = []
    reps: list[int] = []
    for idx, entry in enumerate(entries):
        placed = False
        for gi, rep_idx in enumerate(reps):
            if same_phase(entry, entries[rep_idx],
                          cell_tol=cell_tol, angle_tol=angle_tol,
                          formula_tol=formula_tol):
                groups[gi].append(idx)
                placed = True
                break
        if not placed:
            groups.append([idx])
            reps.append(idx)
    return groups


@dataclass(frozen=True)
class PhaseFamily:
    """One phase family inside a ranked candidate list."""

    representative: int
    """Index (into the original ranked list) of the family's best candidate."""

    members: tuple[int, ...]
    """All indices belonging to the family, best first."""

    @property
    def size(self) -> int:
        return len(self.members)


def families(
    entries: Sequence[Entry],
    **kwargs: object,
) -> list[PhaseFamily]:
    """Convenience wrapper around :func:`group_same_phase` → :class:`PhaseFamily`."""
    groups = group_same_phase(entries, **kwargs)  # type: ignore[arg-type]
    return [
        PhaseFamily(representative=g[0], members=tuple(g))
        for g in groups
        if g
    ]


def iter_family_representatives(
    entries: Sequence[Entry], **kwargs: object
) -> Iterable[int]:
    """Yield the index of each family's best-ranked member, in rank order."""
    for family in families(entries, **kwargs):
        yield family.representative
