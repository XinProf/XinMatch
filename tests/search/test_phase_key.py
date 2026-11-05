"""Unit tests for phase-level identity (v3.2.0)."""

from __future__ import annotations

import numpy as np
import pytest

from xinmatch.core.model import CellParams, Entry
from xinmatch.core.search.phase_key import (
    families,
    group_same_phase,
    normalize_formula,
    parse_composition,
    same_phase,
)


def _entry(
    eid: str,
    formula: str,
    *,
    a: float = 4.0,
    b: float | None = None,
    c: float | None = None,
    space_group: str | None = "F m -3 m",
) -> Entry:
    b = a if b is None else b
    c = a if c is None else c
    return Entry(
        entry_id=eid,
        formula=formula,
        d_spacings=np.array([3.0, 2.0, 1.5]),
        intensities=np.array([1000.0, 500.0, 250.0]),
        mineral_name=None,
        cell=CellParams(a=a, b=b, c=c, alpha=90.0, beta=90.0, gamma=90.0),
        space_group=space_group,
        hkl=None,
        literature={},
        quality="",
        elements=frozenset(parse_composition(formula)),
    )


# ---------------------------------------------------------------------------
# composition parsing
# ---------------------------------------------------------------------------


def test_parse_composition_counts_and_order():
    assert parse_composition("Al2 Mg O4") == {"Al": 2.0, "Mg": 1.0, "O": 4.0}
    assert parse_composition("Ca O3 C") == parse_composition("C Ca O3")
    assert parse_composition("Mg O") == {"Mg": 1.0, "O": 1.0}


def test_parse_composition_decimal_occupancy():
    comp = parse_composition("H0.95 Ni Ti")
    assert comp["H"] == pytest.approx(0.95)
    assert comp["Ni"] == 1.0 and comp["Ti"] == 1.0


def test_parse_composition_empty():
    assert parse_composition("") == {}
    assert parse_composition(None) == {}


def test_normalize_formula_is_canonical():
    assert normalize_formula("Al2 Mg O4") == "Al2MgO4"
    assert normalize_formula("Al1.50 Mg O4") == normalize_formula("Al1.5MgO4")
    # 元素顺序无关
    assert normalize_formula("O4 Mg Al2") == normalize_formula("Al2 Mg O4")


# ---------------------------------------------------------------------------
# same_phase
# ---------------------------------------------------------------------------


def test_same_entry_is_same_phase():
    e = _entry("96-210-0858", "Ba O3 Ti")
    assert same_phase(e, e)


def test_sibling_cards_of_same_phase_match():
    """同相异卡（BaTiO3 0858/0859 那类）必须判为同相。"""
    a = _entry("96-210-0858", "Ba O3 Ti", a=4.006)
    b = _entry("96-210-0859", "Ba O3 Ti", a=4.010)
    assert same_phase(a, b)


def test_occupancy_variants_within_tolerance_match():
    a = _entry("96-901-7558", "Al1.499 Be2.49 Ca3.953 O28 Si9.011", a=9.2, c=9.2)
    b = _entry("96-900-7487", "Al2 Be2 Ca4 O28 Si9", a=9.21, c=9.21)
    assert same_phase(a, b)


def test_polymorphs_differ_by_cell():
    """同组成不同晶胞（锐钛矿 vs 金红石）不能合并。"""
    anatase = _entry("96-500-0223", "O2 Ti", a=3.785, c=9.514)
    rutile = _entry("96-231-0486", "O2 Ti", a=4.594, c=2.959)
    assert not same_phase(anatase, rutile)


def test_different_elements_never_match():
    a = _entry("a", "Mg O")
    b = _entry("b", "Ca O")
    assert not same_phase(a, b)


def test_space_group_conflict_blocks_match():
    a = _entry("a", "O2 Ti", a=4.6, c=2.96, space_group="P 42/m n m")
    b = _entry("b", "O2 Ti", a=4.6, c=2.96, space_group="I 41/a m d")
    assert not same_phase(a, b)


def test_missing_cell_is_not_a_mismatch():
    a = _entry("a", "Mg O")
    b = _entry("b", "Mg O")
    object.__setattr__(b, "cell", None) if not isinstance(b, Entry) else setattr(b, "cell", None)
    assert same_phase(a, b)


def test_missing_cell_compares_formula_ratios_not_counts():
    """库内化学式按晶胞给出（Z 不同），同相会写成 O2 Si / O4 Si2 —— 比值相等即同相。"""
    a = _entry("96-500-0035", "O2 Si")   # Z=3 quartz
    b = _entry("96-900-1571", "O4 Si2")  # Z=6 quartz
    a.cell = b.cell = None
    assert same_phase(a, b)

    c = _entry("c", "O2 Si")
    d = _entry("d", "O2 Ti")
    c.cell = d.cell = None
    assert not same_phase(c, d)


# ---------------------------------------------------------------------------
# NULL 式卡：没有化学式就不能断言「同相」（v3.4.1 修复）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("null_formula", ["", "   ", "\n"])
def test_null_formula_card_never_matches_a_known_phase(null_formula):
    """一侧有可解析组成、另一侧解析为空 → 不能判同相。

    COD-Inorg 里 416/78,035 条 ``formula`` 为 NULL/空（库读出时归一成 ``""``）。
    旧实现把「无证据」当成「不反对」，于是这些卡能假匹配**任何**真值相：基准的
    真值匹配被虚高，候选折叠时它们还会被折进任意相位族
    （``docs/检索基准-31-次相诊断-20261105.md``）。
    """
    known = _entry("96-230-0448", "Al2 O3")
    blank = _entry("96-999-0001", null_formula, space_group=None)
    known.cell = blank.cell = None
    assert not same_phase(known, blank)
    assert not same_phase(blank, known)


def test_two_formulaless_entries_are_not_asserted_same_phase():
    """两侧都无化学式、又都无晶胞 → 没有任何正向证据，不得判同（保守：各自成族）。"""
    a = _entry("96-999-0002", "", space_group=None)
    b = _entry("96-999-0003", "", space_group=None)
    a.cell = b.cell = None
    assert not same_phase(a, b)


def test_formulaless_card_with_matching_cell_still_matches():
    """晶胞是更强的证据：式为空但晶胞吻合时仍判同相（修复只收紧「组成回退」这条路）。"""
    a = _entry("96-230-0448", "Al2 O3", a=4.759, c=12.99)
    b = _entry("96-999-0004", "", a=4.762, c=13.00, space_group=None)
    assert same_phase(a, b)


def test_null_formula_card_forms_its_own_family():
    """折叠候选时，NULL 式卡不能并进第一个族——否则会把真族的代表位置顶掉。"""
    calcite = _entry("96-210-0992", "C Ca O3", a=4.99, c=17.06)
    blank = _entry("96-999-0005", "", space_group=None)
    blank.cell = None
    groups = group_same_phase([calcite, blank])
    assert groups == [[0], [1]]


# ---------------------------------------------------------------------------
# grouping
# ---------------------------------------------------------------------------


def test_group_keeps_rank_order_and_representatives():
    beryl1 = _entry("96-900-7487", "Al2 Be2 Ca4 O28 Si9", a=9.20, c=9.20)
    beryl2 = _entry("96-901-7558", "Al1.499 Be2.49 Ca3.953 O28 Si9.011", a=9.21, c=9.21)
    calcite = _entry("96-210-0992", "C Ca O3", a=4.99, c=17.06)
    quartz = _entry("96-500-0035", "O2 Si", a=4.913, c=5.405)

    groups = group_same_phase([beryl1, beryl2, calcite, quartz])
    assert groups == [[0, 1], [2], [3]]

    fams = families([beryl1, beryl2, calcite, quartz])
    assert [f.representative for f in fams] == [0, 2, 3]
    assert fams[0].size == 2


def test_group_empty_input():
    assert group_same_phase([]) == []
    assert families([]) == []
