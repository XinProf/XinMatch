"""``xinmatch.core.model.element_symbols`` 的纯函数与元素表一致性。

这一层是 GUI / CLI 共用的「样品元素 → 补集约束」实现，刻意不依赖
PySide6。最要紧的两条不变量：

1. 元素表必须和建库链路的权威表 ``cif_meta.IUPAC_ELEMENTS`` 集合一致
   （那边定义了 ``elem_mask`` 位号并绑定 ``meta.element_mask_scheme`` 哈希）；
2. 检出的元素**只能保持 OPTIONAL**，绝不能标 REQUIRED —— 次相未必含
   主相的每个元素，而且 ``prescreen(elements_allowed=...)`` 是「必须全部含有」
   的语义，按字面传允许集合会把池缩到几十张卡、连真值都 MISS（§20.5）。

GUI 按钮网格 ``_ELEMENTS`` 与这张表逐项一致由
``xinmatch.ui.periodic_table`` 的 import 期校验守住；本文件不 import PySide6。
"""

from __future__ import annotations

import pytest

from xinmatch.core.db.cif_meta import IUPAC_ELEMENTS
from xinmatch.core.model.element_symbols import (
    ELEMENT_SYMBOLS,
    complement_restraints,
    parse_element_symbols,
    restraints_from_sample_elements,
)
from xinmatch.core.model.restraints import ElementState

SAMPLE = "Zn Al Ca O F"
EXPECTED = ["O", "F", "Al", "Ca", "Zn"]


# ---------------------------------------------------------------------------
# 元素表
# ---------------------------------------------------------------------------

def test_symbol_table_matches_iupac_authority():
    """共享表与建库位表只是顺序不同，集合必须完全相同。"""
    assert len(ELEMENT_SYMBOLS) == 118
    assert len(set(ELEMENT_SYMBOLS)) == 118
    assert set(ELEMENT_SYMBOLS) == set(IUPAC_ELEMENTS)
    assert len(IUPAC_ELEMENTS) == 118


def test_symbol_table_has_no_case_collisions():
    lookup = {sym.lower(): sym for sym in ELEMENT_SYMBOLS}
    assert len(lookup) == len(ELEMENT_SYMBOLS)


def test_every_symbol_is_parseable():
    """整张表逐个喂回解析器，不能有哪个符号解析不出来。"""
    known, unknown = parse_element_symbols(" ".join(ELEMENT_SYMBOLS))
    assert unknown == []
    assert known == list(ELEMENT_SYMBOLS)


# ---------------------------------------------------------------------------
# parse_element_symbols
# ---------------------------------------------------------------------------

def test_parse_normalises_case_and_deduplicates():
    assert parse_element_symbols("zn, O o F, al Ca ZN") == (EXPECTED, [])


def test_parse_accepts_common_separators():
    assert parse_element_symbols("Zn;Al、Ca，O/F")[0] == EXPECTED


def test_parse_returns_periodic_table_order():
    """输入顺序不影响摘要，UI 文案稳定。"""
    assert parse_element_symbols("Zn F Ca Al O")[0] == EXPECTED


def test_parse_reports_unknown_instead_of_guessing():
    known, unknown = parse_element_symbols("Zn Xx Al2O3 Xx")
    assert known == ["Zn"]
    assert unknown == ["Xx", "Al2O3"]


def test_parse_does_not_interpret_formula_subscripts():
    """化学式不是元素符号串；猜成分会静默漏掉轻元素。"""
    known, unknown = parse_element_symbols("Al2O3")
    assert known == []
    assert unknown == ["Al2O3"]


def test_parse_empty():
    assert parse_element_symbols("   ") == ([], [])
    assert parse_element_symbols("") == ([], [])


# ---------------------------------------------------------------------------
# complement_restraints
# ---------------------------------------------------------------------------

def test_complement_excludes_every_other_element():
    restraints = complement_restraints(EXPECTED)
    assert len(restraints.elements) == 118 - len(EXPECTED)
    assert set(restraints.elements.values()) == {ElementState.EXCLUDE}
    for sym in EXPECTED:
        assert sym not in restraints.elements
    assert "Bi" in restraints.elements
    assert "Pb" in restraints.elements
    assert "C" in restraints.elements  # 有机卡的主要排除目标（§23）


def test_complement_never_requires_detected_elements():
    restraints = complement_restraints(EXPECTED)
    assert ElementState.REQUIRED not in set(restraints.elements.values())
    assert all(
        restraints.get_state(sym) == ElementState.OPTIONAL for sym in EXPECTED
    )


def test_complement_is_idempotent_under_duplicates():
    assert (
        complement_restraints(["Zn", "Zn", "O"]).elements
        == complement_restraints(["O", "Zn"]).elements
    )


def test_complement_semantics_passes_only_sample_chemistry():
    """含未检出元素的假卡必须被挡掉，真卡不能被挡。"""
    restraints = complement_restraints(EXPECTED)
    assert restraints.passes_elements({"Zn", "O"})
    assert restraints.passes_elements({"Ca", "F"})
    assert restraints.passes_elements(set(EXPECTED))
    assert not restraints.passes_elements({"Bi", "Y", "O"})
    assert not restraints.passes_elements(set(EXPECTED) | {"C"})


# ---------------------------------------------------------------------------
# restraints_from_sample_elements（CLI 入口）
# ---------------------------------------------------------------------------

def test_cli_entry_returns_complement():
    restraints = restraints_from_sample_elements(SAMPLE)
    assert len(restraints.elements) == 113
    assert set(restraints.elements.values()) == {ElementState.EXCLUDE}


def test_cli_entry_rejects_unknown_symbols():
    with pytest.raises(ValueError, match="无法识别的元素符号"):
        restraints_from_sample_elements("Zn Xx")


def test_cli_entry_rejects_formula():
    with pytest.raises(ValueError, match="不要填化学式"):
        restraints_from_sample_elements("Al2O3")


def test_cli_entry_rejects_empty():
    with pytest.raises(ValueError, match="样品元素为空"):
        restraints_from_sample_elements("  ,  ")


def test_cli_entry_rejects_all_unknown_with_actionable_hint():
    with pytest.raises(ValueError, match="Zn Al Ca O F"):
        restraints_from_sample_elements("Al2O3")
