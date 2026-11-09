"""四态元素过滤（必有 / 含有 / 可能 / 没有）+ 闭环 —— 口径对齐 PolyXRD。

背景：XinMatch 原本只有三态（``REQUIRED`` / ``EXCLUDE`` / ``OPTIONAL``），
两个真实短板：

* **没有「至少含一个」** —— 用户想表达「样品是 MgO 或 CaO 或 CaCO3 这一族」，
  只能把 Mg/Ca/C/O 全标成 ``REQUIRED``，而那是 AND 语义，只剩 CaMg(CO3)2；
* **没有闭环** —— 「只允许我检出的这几个元素」只能靠「把其余 113 个标红」
  这种补集写法，逐点 118 个按钮不现实（所以才有 v1.4 的快速录入取巧）。

PolyXRD 的四态 + ``closed_world`` 正好补这两块
（``src/polyxrd/utils/formula_parser.py::elements_match_filter``）。
本文件把它的 11 条语义断言逐条搬过来，作为移植是否等价的验收清单。

记 S = 物相元素集，P/H/M/E = 必有 / 含有 / 可能 / 没有：

======  ===============  ==================================================
类别     判定式           含义
======  ===============  ==================================================
必有 P   ``P ⊆ S``        每个都必须出现（AND）
含有 H   ``S ∩ H ≠ ∅``    至少含其中一个（OR）
可能 M   无强制条件        只放宽闭环允许池
没有 E   ``S ∩ E = ∅``    含任一即淘汰
======  ===============  ==================================================

闭环：``P∪H∪M`` 非空时未勾选元素一律视为「没有」，等价于 ``S ⊆ P∪H∪M``。
"""

from __future__ import annotations

import pytest

from xinmatch.core.model import ElementState, Restraints
from xinmatch.core.model.element_symbols import (
    ELEMENT_SYMBOLS,
    LIGHT_ELEMENTS,
    complement_restraints,
    element_constraint_sets,
)


def _r(**groups: list[str]) -> Restraints:
    """``_r(has=["Mg"], maybe=["O"])`` → 对应状态的 Restraints（闭环默认开）。"""
    state_of = {
        "must_have": ElementState.REQUIRED,
        "has": ElementState.HAS,
        "maybe": ElementState.MAYBE,
        "exclude": ElementState.EXCLUDE,
    }
    elements: dict[str, ElementState] = {}
    for key, symbols in groups.items():
        for sym in symbols:
            elements[sym] = state_of[key]
    return Restraints(elements=elements, closed_world=True)


def _passes(formula_elements: set[str], **groups: list[str]) -> bool:
    return _r(**groups).passes_elements(formula_elements, closed_world=True)


def _els(*symbols: str) -> set[str]:
    """物相元素集合（S）的简写。"""
    return set(symbols)


# ---------------------------------------------------------------------------
# 1. PolyXRD 的四个语义示例
# ---------------------------------------------------------------------------
def test_example1_has_only() -> None:
    """含有{Mg,Ca,C,O} → MgO / CaO / CaCO3 / MgCO3 / CaMg(CO3)2 都可。"""
    kw = {"has": ["Mg", "Ca", "C", "O"]}
    for ok in [("Mg", "O"), ("Ca", "O"), ("Ca", "C", "O"),
               ("Mg", "C", "O"), ("Ca", "Mg", "C", "O")]:
        assert _passes(_els(*ok), **kw), ok
    assert not _passes(_els("Zn", "O"), **kw)          # Zn 未勾选 → 闭环淘汰
    assert not _passes(_els("Ca", "S", "O"), **kw)     # S 未勾选 → 闭环淘汰


def test_example2_must_have_plus_has() -> None:
    """必有{Mg} + 含有{Ca,C,O} → MgO / MgCO3 / CaMg(CO3)2，纯 Mg 也可。"""
    kw = {"must_have": ["Mg"], "has": ["Ca", "C", "O"]}
    for ok in [("Mg", "O"), ("Mg", "C", "O"), ("Ca", "Mg", "C", "O"), ("Mg",)]:
        assert _passes(_els(*ok), **kw), ok
    assert not _passes(_els("Ca", "C", "O"), **kw)     # 缺 Mg


def test_example3_must_have_is_and_not_or() -> None:
    """必有{Mg,Ca,C,O} → 只有 CaMg(CO3)2。"""
    kw = {"must_have": ["Mg", "Ca", "C", "O"]}
    assert _passes(_els("Ca", "Mg", "C", "O"), **kw)
    assert not _passes(_els("Mg", "O"), **kw)
    assert not _passes(_els("Ca", "C", "O"), **kw)
    assert not _passes(_els("Ca", "Mg", "C", "O", "H"), **kw)   # H 未勾选


def test_example4_edx_light_element_in_maybe() -> None:
    """EDX 测出 Al/O，H 放「可能」→ Al2O3 / Al / Al(OH)3 都可。"""
    kw = {"has": ["Al", "O"], "maybe": ["H"]}
    for ok in [("Al", "O"), ("Al",), ("Al", "O", "H")]:
        assert _passes(_els(*ok), **kw), ok
    # 不把 H 放进「可能」→ Al(OH)3 被闭环排除
    assert not _passes(_els("Al", "O", "H"), has=["Al", "O"])


# ---------------------------------------------------------------------------
# 2. 边界语义
# ---------------------------------------------------------------------------
def test_maybe_alone_behaves_like_has() -> None:
    """只勾「可能」→ 在可能元素里排列组合（含有为空时可能代行其职）。"""
    kw = {"maybe": ["Si", "O"]}
    assert _passes(_els("Si", "O"), **kw)
    assert _passes(_els("Si"), **kw)
    assert not _passes(_els("Fe", "O"), **kw)


def test_exclude_only_is_open_world() -> None:
    """只勾「没有」→ 开放世界，仅排除这些元素（不触发闭环）。"""
    assert _passes(_els("Ca", "O"), exclude=["S"])
    assert not _passes(_els("Ca", "S", "O"), exclude=["S"])


def test_empty_restraints_is_full_search() -> None:
    assert _r().passes_elements(_els("Fe", "O"), closed_world=True)
    assert _r().passes_elements(set(), closed_world=True)


def test_must_have_does_not_require_has() -> None:
    """勾了必有就不再要求至少含一个含有 —— 否则纯金属相永远进不了候选。"""
    assert _passes(_els("Mg"), has=["Ca"], must_have=["Mg"])
    assert not _passes(_els("Mg"), must_have=["Mg", "Ca"])


def test_priority_must_have_over_exclude() -> None:
    """字典模型里一个元素只能有一个状态：后写覆盖先写。

    PolyXRD 的扁平列表 API 需要按「必有 > 含有 > 可能 > 没有」做重叠去重；
    ``Restraints.elements`` 是 ``{符号: 状态}``，结构上不可能同处两态，
    所以这里只固定「后写生效」这条可观察行为。
    """
    r = Restraints()
    r.exclude("Mg")
    r.require("Mg")
    assert r.get_state("Mg") == ElementState.REQUIRED
    assert r.passes_elements(_els("Mg"), closed_world=True)
    r.has_any("Mg")
    assert r.get_state("Mg") == ElementState.HAS


def test_empty_element_phase_excluded_when_closed() -> None:
    assert not _passes(set(), has=["Mg"])
    assert not _passes(set(), must_have=["Mg"])


def test_closed_world_off_keeps_open_world() -> None:
    """``closed_world=False`` 时未勾选元素不再自动排除（旧三态行为）。"""
    r = _r(has=["Ca"])
    assert not r.passes_elements(_els("Ca", "S", "O"), closed_world=True)
    assert r.passes_elements(_els("Ca", "S", "O"), closed_world=False)


def test_three_state_behaviour_is_bit_identical() -> None:
    """旧三态用法（只有 REQUIRED / EXCLUDE）在闭环关闭时结果不变。"""
    r = Restraints(elements={"O": ElementState.REQUIRED,
                             "Bi": ElementState.EXCLUDE})
    assert r.passes_elements({"O", "Si"})
    assert not r.passes_elements({"Si"})           # 缺 O
    assert not r.passes_elements({"C", "Bi", "O"})  # 含 Bi
    assert r.passes_elements({"C", "Ca", "O"})      # 其它元素不管


# ---------------------------------------------------------------------------
# 3. element_constraint_sets —— 检索池的唯一换算点
# ---------------------------------------------------------------------------
def test_constraint_sets_open_world() -> None:
    r = _r(has=["Si", "Al"], maybe=["H"], exclude=["Bi"])
    required, any_of, excluded = element_constraint_sets(r, closed_world=False)
    assert required == set()
    assert any_of == {"Si", "Al"}
    assert excluded == {"Bi"}


def test_constraint_sets_closed_world_expands_to_complement() -> None:
    """闭环 = 把「允许池之外」全部补进 excluded（``S ∩ 池外 = ∅``）。"""
    r = _r(has=["Si", "O"], maybe=["H"])
    required, any_of, excluded = element_constraint_sets(r, closed_world=True)
    assert required == set()
    assert any_of == {"Si", "O"}
    assert excluded == set(ELEMENT_SYMBOLS) - {"Si", "O", "H"}
    assert len(excluded) == len(ELEMENT_SYMBOLS) - 3


def test_constraint_sets_closed_world_is_a_noop_without_pool() -> None:
    """三者全空 → 闭环不生效（全库检索，不是全盘排除）。"""
    _req, _any, excluded = element_constraint_sets(
        _r(exclude=["Bi"]), closed_world=True
    )
    assert excluded == {"Bi"}


def test_constraint_sets_drops_any_of_when_must_have_present() -> None:
    """必有非空时「含有」整组丢弃 —— 否则预筛会悄悄改成 AND × OR。"""
    required, any_of, _excluded = element_constraint_sets(
        _r(must_have=["Mg"], has=["Ca"]), closed_world=False
    )
    assert required == {"Mg"}
    assert any_of == set()


def test_constraint_sets_keeps_any_of_without_must_have() -> None:
    required, any_of, _excluded = element_constraint_sets(
        _r(has=["Ca", "Mg"]), closed_world=False
    )
    assert required == set()
    assert any_of == {"Ca", "Mg"}


def test_constraint_sets_reads_the_restraints_flag_by_default() -> None:
    r = _r(must_have=["O"])
    assert element_constraint_sets(r)[2] == set(ELEMENT_SYMBOLS) - {"O"}
    r.closed_world = False
    assert element_constraint_sets(r)[2] == set()


def test_constraint_sets_default_does_not_close_the_world() -> None:
    assert Restraints().closed_world is False


# ---------------------------------------------------------------------------
# 4. 与既有补集写法等价
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("detected", [["Zn", "O"], ["O", "F", "Al", "Ca", "Zn"]])
def test_closed_world_equals_the_complement_restraint(detected: list[str]) -> None:
    """「闭环 + 检出元素标可能」与「其余元素全标没有」必须逐位等价。

    这两条路径各自存在于 GUI（快速录入 vs 手工 + 闭环开关）与 CLI
    （``--sample-elements``），口径若有偏差，同一句话会得出两套检索结果。

    唯一例外是**元素集为空**的退化物相：闭环形式还会要求「至少命中一个可能
    元素」，补集形式不会。真实库里不存在零元素物相，所以删补两路在检索上等价
    （PolyXRD 的 ``test_empty_elements_phase_excluded_when_closed`` 也站在闭环
    这一侧）。
    """
    closed = Restraints(
        elements={sym: ElementState.MAYBE for sym in detected},
        closed_world=True,
    )
    complement = complement_restraints(detected)
    assert element_constraint_sets(closed) == element_constraint_sets(complement)
    for entry in ({"Zn", "O"}, {"Ca", "F", "O"}, {"Bi", "Y", "O"}):
        assert closed.passes_elements(entry, closed_world=True) == (
            complement.passes_elements(entry, closed_world=False)
        ), entry


def test_light_elements_match_polyxrd() -> None:
    assert LIGHT_ELEMENTS == ("O", "C", "H", "N", "S")


# ---------------------------------------------------------------------------
# 5. 序列化向后兼容
# ---------------------------------------------------------------------------
def test_closed_world_roundtrips_through_dict() -> None:
    r = _r(must_have=["O"], has=["Si"])
    restored = Restraints.from_dict(r.to_dict())
    assert restored.closed_world is True
    assert restored.elements == r.elements


def test_old_archive_without_closed_world_key_loads_open() -> None:
    """旧 ``.xinm`` 存档没有 ``closed_world`` 键 → 默认开放世界。"""
    old = {"elements": {"O": "green", "Bi": "red"}, "crystal_system": None}
    restored = Restraints.from_dict(old)
    assert restored.closed_world is False
    assert restored.elements["O"] == ElementState.REQUIRED


def test_new_state_values_are_readable_from_strings() -> None:
    r = Restraints.from_dict({"elements": {"Si": "has", "H": "maybe"}})
    assert r.get_state("Si") == ElementState.HAS
    assert r.get_state("H") == ElementState.MAYBE
