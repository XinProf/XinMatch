"""第四把尺子的元素上界口径：纯函数回归（不依赖 .xinDB 库）。

钉住两件容易漂移的事：

1. ``match_entry_id`` 的「七位数字减 1」换算；
2. ``oracle_restraints`` 必须表达成**补集 EXCLUDE**（"只允许这些元素"），
   而不是 ``elements_allowed``（"必须全部含有"）—— 后者语义完全不同。
"""

from __future__ import annotations

from tools import bench_shijk as bs
from xinmatch.core.model.element_symbols import (
    ELEMENT_SYMBOLS,
    element_constraint_sets,
)
from xinmatch.core.model.restraints import ElementState


def _truth(formula: str) -> bs.Truth:
    return bs.Truth(
        entry_id="96-000-0001", formula=formula, cell=None, cif="dummy.cif"
    )


def test_match_entry_id_subtracts_one_from_the_seven_digits() -> None:
    assert bs.match_entry_id("1-quartz-Entry_96-101-1177.cif") == "96-101-1176"
    assert bs.match_entry_id("1-kaolinite-Entry_96-900-9231.cif") == "96-900-9230"
    assert bs.match_entry_id("no-id.cif") is None


def test_sample_elements_unions_and_sorts() -> None:
    truths = [_truth("O2 Si"), _truth("C Ca Mg O3"), _truth("Al2 O3")]
    assert bs.sample_elements(truths) == ["Al", "C", "Ca", "Mg", "O", "Si"]


def test_oracle_restraints_is_a_complement_not_a_required_set() -> None:
    truths = [_truth("O2 Si"), _truth("C Ca Mg O3")]
    allowed = set(bs.sample_elements(truths))
    complement = set(ELEMENT_SYMBOLS) - allowed

    restraints = bs.oracle_restraints(truths)
    assert restraints is not None
    # 允许池本身保持 OPTIONAL（不写进 elements），只有池外元素被 EXCLUDE。
    assert set(restraints.elements) == complement
    assert set(restraints.elements.values()) == {ElementState.EXCLUDE}

    required, any_of, excluded = element_constraint_sets(restraints)
    assert required == set()
    assert any_of == set()
    assert excluded == complement
    assert allowed.isdisjoint(excluded)


def test_oracle_restraints_empty_truth_returns_none() -> None:
    assert bs.oracle_restraints([]) is None
