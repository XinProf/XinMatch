"""Search-match restraints data model.

Implements :class:`Restraints`, the filter conditions applied before / during
search-match.  Element composition uses the reference software's colour coding,
extended to the **four-state** filter of PolyXRD (``element_periodic_table.py``
+ ``formula_parser.elements_match_filter``):

* 🔴 **red / EXCLUDE**（没有）— element must be **absent**.
* 🟡 **yellow / OPTIONAL**（不限制）— no filtering effect; under
  :attr:`Restraints.closed_world` it is treated as *absent*.
* 🟢 **green / REQUIRED**（必有）— element must be **present** (AND: every
  required element must occur).
* 🟩 **HAS**（含有）— the phase must contain **at least one** of them (OR).
* 🟨 **MAYBE**（可能）— no hard condition; it only widens the closed-world
  allowed pool (and earns the same weak presence bonus as OPTIONAL).

The value carried by each member is the historic colour key (``red`` /
``yellow`` / ``green``); the two newer states use their own names, so old
``.xinm`` archives and YAML files keep loading unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ElementState(str, Enum):
    """Element restraint state (four filtering states + "unset")."""

    EXCLUDE = "red"      # 没有：含任一即淘汰
    OPTIONAL = "yellow"  # 不限制：不过滤（闭环开启时视同「没有」）
    REQUIRED = "green"   # 必有：每个都必须出现（AND）
    HAS = "has"          # 含有：至少含一个（OR）
    MAYBE = "maybe"      # 可能：无强制条件，只放宽闭环允许池


@dataclass
class Restraints:
    """Search-match restraint conditions.

    Only non-default values are stored; missing keys imply *optional*.
    """

    elements: dict[str, ElementState] = field(default_factory=dict)
    #: 闭环元素约束：未勾选（OPTIONAL）元素一律视为「没有」，等价于
    #: ``S ⊆ 必有 ∪ 含有 ∪ 可能``。仅在「必有 / 含有 / 可能」至少勾中一项时
    #: 生效；三者全空 = 全库检索，只勾「没有」= 开放世界（只排除这些元素）。
    closed_world: bool = False
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
        """Mark *element* as required (必有, AND)."""
        self.set_element(element, ElementState.REQUIRED)

    def exclude(self, element: str) -> None:
        """Mark *element* as excluded (没有)."""
        self.set_element(element, ElementState.EXCLUDE)

    def has_any(self, element: str) -> None:
        """Mark *element* as "contains" (含有, OR: at least one of them)."""
        self.set_element(element, ElementState.HAS)

    def maybe(self, element: str) -> None:
        """Mark *element* as "maybe" (可能, widens the closed-world pool)."""
        self.set_element(element, ElementState.MAYBE)

    def get_state(self, element: str) -> ElementState:
        return self.elements.get(element, ElementState.OPTIONAL)

    def passes_elements(
        self, entry_elements: set[str], *, closed_world: bool = False
    ) -> bool:
        """Return ``True`` if *entry_elements* satisfies the element restraints.

        With ``S`` the entry's element set and ``P`` / ``H`` / ``M`` / ``E`` the
        required / has / maybe / excluded element sets:

        ======  ===============  =================================================
        类别     判定式           含义
        ======  ===============  =================================================
        必有 P   ``P ⊆ S``        每个都必须出现（AND）
        含有 H   ``S ∩ H ≠ ∅``    至少含其中一个（OR）
        可能 M   无强制条件        只放宽闭环允许池
        没有 E   ``S ∩ E = ∅``    含任一即淘汰
        ======  ===============  =================================================

        当 ``closed_world=True`` 且 ``P∪H∪M`` 非空时，未指定元素一律当作
        「没有」，等价于 ``S ⊆ P∪H∪M``。勾了「必有」时不再要求至少含一个
        「含有」（纯金属等单元素相仍可作为候选）；「含有」为空时「可能」代行
        其职。

        PolyXRD 侧还有一条「同一元素出现在多类时 必有 > 含有 > 可能 > 没有」
        的优先级规则；这里不需要 —— ``elements`` 是 ``{符号: 状态}`` 字典，
        一个元素结构上只能有一个状态，:meth:`set_element` 后写覆盖先写。
        """
        required: set[str] = set()
        any_of: set[str] = set()
        maybe: set[str] = set()
        banned: set[str] = set()
        for element, state in self.elements.items():
            if state == ElementState.REQUIRED:
                required.add(element)
            elif state == ElementState.HAS:
                any_of.add(element)
            elif state == ElementState.MAYBE:
                maybe.add(element)
            elif state == ElementState.EXCLUDE:
                banned.add(element)

        s = set(entry_elements or ())
        if banned and (s & banned):
            return False
        pool = required | any_of | maybe
        if closed_world and pool and not s <= pool:
            return False
        if required and not required <= s:
            return False
        if not required:
            expect = any_of or maybe
            if expect and not (s & expect):
                return False
        return True

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "elements": {e: s.value for e, s in self.elements.items()},
            "closed_world": self.closed_world,
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
            # 旧存档没有这个键 → 默认开放世界，行为与旧版本逐位一致。
            closed_world=bool(d.get("closed_world", False)),
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
