"""预筛层的「至少含一个」元素过滤（``ElementState.HAS``）与闭环约束。

背景：v3.6.3 把元素约束从三态扩到**四态 + 闭环**（口径对齐 PolyXRD）。
其中两块需要预筛层配合，而预筛原来只有两条通路：

* ``elements_allowed`` —— 「必须**全部**含有」（AND，``element_filter``）；
* ``elements_excluded`` —— 「含任一即淘汰」（OR-of-absence，
  ``element_exclude_filter``）。

补上的第三条是 ``elements_any`` —— 「**至少含一个**」（OR，``HAS``）。
没有它，「样品是 MgO 或 CaO 或 CaCO3 这一族」只能写成「四个元素全部必含」，
而那是 AND 语义，只剩 CaMg(CO3)2。

闭环不新增通路：它把「允许池之外的 118−n 个元素」直接补进
``elements_excluded``（``S ⊆ 池`` ⟺ ``S ∩ 池外 = ∅``），
换算点只有 :func:`element_constraint_sets` 一处。

本文件固定四件事：

1. ``element_union_filter`` 的语义 —— 「**含有其中至少一个**」；
2. 未知元素在并集方向上**没有发言权**（跳过），而不是清空结果；
3. ``prescreen(elements_any=…)`` 与另外两条通路的交集行为；
4. ``Restraints(HAS / MAYBE / closed_world)`` 能一路传到预筛。
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from tests.xindb_support import write_xindb
from xinmatch.core.db.reader_v3 import XinDBReader
from xinmatch.core.model import CellParams, ElementState, Entry, Peak, Restraints
from xinmatch.core.model.element_symbols import (
    ELEMENT_SYMBOLS,
    element_constraint_sets,
)
from xinmatch.core.search import search_match

WL = 1.5406

# 三条相共享同一组 d 值：只要窗口覆盖得住，三者都会进候选池，
# 于是「少了一个」只可能是元素过滤干的，与峰位无关。
_D = [3.34, 4.26, 2.46, 1.82]
_I = [1000.0, 550.0, 300.0, 120.0]


def _entry(entry_id: str, formula: str) -> Entry:
    return Entry(
        entry_id=entry_id,
        formula=formula,
        d_spacings=np.array(_D, dtype=np.float64),
        intensities=np.array(_I, dtype=np.float64),
        space_group="P 1",
        cell=CellParams(4.913, 4.913, 5.405, gamma=120.0),
        hkl=None,
        literature={"source": "synth"},
    )


@pytest.fixture
def any_library(tmp_path):
    """QUARTZ(SiO2) / BIYO(Bi-Y-O) / CALCITE(CaCO3)，峰位完全一致。"""
    lib = tmp_path / "ANY-20260101.xinDB"
    entries = [
        _entry("96-200-0001", "O2 Si"),
        _entry("96-200-0002", "Bi1.284 O2.988 Y0.684"),
        _entry("96-200-0003", "C Ca O3"),
    ]
    return write_xindb(lib, entries)


def _d_to_two_theta(d: float, wavelength: float = WL) -> float:
    return math.degrees(2.0 * math.asin(wavelength / (2.0 * d)))


def _peaks() -> list[Peak]:
    return [Peak(two_theta=_d_to_two_theta(d), intensity=i)
            for d, i in zip(_D, _I, strict=True)]


def _kept(reader: XinDBReader, mask) -> list[str]:
    names = reader.entry_ids()
    return [eid for eid, ok in zip(names, mask, strict=True) if ok]


# ---------------------------------------------------------------------------
# 1. element_union_filter 本身
# ---------------------------------------------------------------------------
def test_union_filter_keeps_phases_with_any_element(any_library) -> None:
    with XinDBReader(any_library) as reader:
        mask = reader.element_union_filter({"Si", "Ca"}, reader.entry_count())
        assert mask is not None and mask.dtype == bool
        assert _kept(reader, mask) == ["96-200-0001", "96-200-0003"]


def test_union_filter_single_element(any_library) -> None:
    with XinDBReader(any_library) as reader:
        mask = reader.element_union_filter({"Bi"}, reader.entry_count())
        assert mask is not None
        assert _kept(reader, mask) == ["96-200-0002"]


def test_union_filter_is_case_insensitive(any_library) -> None:
    with XinDBReader(any_library) as reader:
        n = reader.entry_count()
        assert np.array_equal(
            reader.element_union_filter({"si"}, n),
            reader.element_union_filter({"SI"}, n),
        )


def test_union_filter_unknown_element_cannot_vouch(any_library) -> None:
    """未知元素在并集方向「什么都担保不了」→ 跳过，不清空结果。"""
    with XinDBReader(any_library) as reader:
        n = reader.entry_count()
        mask = reader.element_union_filter({"Zz", "Si"}, n)
        assert mask is not None
        assert _kept(reader, mask) == ["96-200-0001"]


def test_union_filter_all_unknown_empties_the_pool(any_library) -> None:
    """整组元素一个都不在库里 → 全 False（不是 None，不能被当成「不生效」）。"""
    with XinDBReader(any_library) as reader:
        mask = reader.element_union_filter({"Zz", "Yy"}, reader.entry_count())
    assert mask is not None
    assert not mask.any()


def test_union_filter_empty_request_is_a_noop(any_library) -> None:
    with XinDBReader(any_library) as reader:
        n = reader.entry_count()
        assert reader.element_union_filter(set(), n) is None
        assert reader.element_union_filter(["", "  "], n) is None


# ---------------------------------------------------------------------------
# 2. prescreen 集成
# ---------------------------------------------------------------------------
def _ids(result) -> list[str]:
    return list(result.candidate_ids)


def test_prescreen_honours_elements_any(any_library) -> None:
    with XinDBReader(any_library) as reader:
        result = reader.prescreen(_D, _I, min_match=3, rank_limit=100,
                                  elements_any={"Si", "Ca"})
    assert sorted(_ids(result)) == ["96-200-0001", "96-200-0003"]


def test_prescreen_any_intersects_with_allowed(any_library) -> None:
    """必有 O（全部含）× 含有 Si/Ca（至少一个）取交集。"""
    with XinDBReader(any_library) as reader:
        result = reader.prescreen(_D, _I, min_match=3, rank_limit=100,
                                  elements_allowed={"O"},
                                  elements_any={"Si", "Ca"})
    assert sorted(_ids(result)) == ["96-200-0001", "96-200-0003"]


def test_prescreen_any_intersects_with_excluded(any_library) -> None:
    with XinDBReader(any_library) as reader:
        result = reader.prescreen(_D, _I, min_match=3, rank_limit=100,
                                  elements_any={"Si", "Ca", "Bi"},
                                  elements_excluded={"Bi"})
    assert sorted(_ids(result)) == ["96-200-0001", "96-200-0003"]


def test_prescreen_any_all_unknown_returns_empty(any_library) -> None:
    with XinDBReader(any_library) as reader:
        result = reader.prescreen(_D, _I, min_match=3, rank_limit=100,
                                  elements_any={"Zz"})
    assert result.candidate_ids == []
    assert result.n_hits == 0


def test_prescreen_any_does_not_disturb_truncation_flag(any_library) -> None:
    with XinDBReader(any_library) as reader:
        result = reader.prescreen(_D, _I, min_match=3, rank_limit=100,
                                  elements_any={"Si", "Ca"})
    assert result.truncated is False


# ---------------------------------------------------------------------------
# 3. Restraints（HAS / MAYBE / 闭环）→ 预筛
# ---------------------------------------------------------------------------
def test_restraints_has_reaches_the_prescreen(any_library) -> None:
    """``Restraints`` 的「含有」必须真的进预筛，而不是被静默丢弃。"""
    r = Restraints(elements={"Si": ElementState.HAS, "Ca": ElementState.HAS})

    with XinDBReader(any_library) as reader:
        candidates = search_match(_peaks(), reader, WL, restraints=r, top_n=10)

    ids = sorted(c.entry.entry_id for c in candidates)
    assert ids == ["96-200-0001", "96-200-0003"]


def test_restraints_closed_world_drops_out_of_pool_phases(any_library) -> None:
    """闭环：允许池 {Si,Ca,C,O} → 含 Bi/Y 的 Bi-Y-O 假卡被排除。"""
    r = Restraints(
        elements={sym: ElementState.MAYBE for sym in ("Si", "Ca", "C", "O")},
        closed_world=True,
    )
    with XinDBReader(any_library) as reader:
        candidates = search_match(_peaks(), reader, WL, restraints=r, top_n=10)

    ids = sorted(c.entry.entry_id for c in candidates)
    assert ids == ["96-200-0001", "96-200-0003"]


def test_restraints_closed_world_bites_on_has(any_library) -> None:
    """含有 {Si,Ca} + 闭环 → 池只有 Si/Ca，SiO2 与 CaCO3 都因 O 被排除。"""
    r = Restraints(
        elements={"Si": ElementState.HAS, "Ca": ElementState.HAS},
        closed_world=True,
    )
    with XinDBReader(any_library) as reader:
        candidates = search_match(_peaks(), reader, WL, restraints=r, top_n=10)
    assert candidates == []


def test_restraints_open_world_keeps_them(any_library) -> None:
    """同一条约束、闭环关掉 → 开放世界，SiO2 / CaCO3 都回来。"""
    r = Restraints(elements={"Si": ElementState.HAS, "Ca": ElementState.HAS})
    with XinDBReader(any_library) as reader:
        candidates = search_match(_peaks(), reader, WL, restraints=r, top_n=10)
    assert len(candidates) == 2


def test_constraint_sets_closed_world_complement_is_the_prescreen_filter() -> None:
    """闭环补集必须精确等于「118 个元素 − 允许池」，否则库里会有漏网相。"""
    r = Restraints(
        elements={"O": ElementState.REQUIRED, "Si": ElementState.HAS},
        closed_world=True,
    )
    _required, _any_of, excluded = element_constraint_sets(r)
    assert excluded == set(ELEMENT_SYMBOLS) - {"O", "Si"}


def test_must_have_suppresses_the_any_of_filter(tmp_path) -> None:
    """必有 + 含有同时存在时，预筛不能把两个条件取交集。

    PolyXRD 规则④「必有已满足就不再要求至少含一个含有」必须落在**换算点**
    （``element_constraint_sets``）上，否则预筛仍会 AND 一次，
    用户看到的现象是「我明明写了必有 O，只含 O 的相却不见了」。
    """
    d = [3.34, 4.26, 2.46, 1.82]
    i = [1000.0, 550.0, 300.0, 120.0]
    entry = Entry(
        entry_id="96-300-0001", formula="O2",
        d_spacings=np.array(d, dtype=np.float64),
        intensities=np.array(i, dtype=np.float64),
        space_group="P 1", cell=CellParams(4.913, 4.913, 5.405, gamma=120.0),
        hkl=None, literature={"source": "synth"},
    )
    lib = tmp_path / "NOHAS-20260101.xinDB"
    write_xindb(lib, [entry])

    r = Restraints(
        elements={"O": ElementState.REQUIRED, "Si": ElementState.HAS},
        closed_world=True,
    )
    required, any_of, excluded = element_constraint_sets(r)
    assert required == {"O"}
    assert any_of == set()          # 含有整组被丢弃
    with XinDBReader(lib) as reader:
        result = reader.prescreen(
            d, i, min_match=3, rank_limit=10,
            elements_allowed=required or None,
            elements_any=any_of or None,
            elements_excluded=excluded or None,
        )
    assert list(result.candidate_ids) == ["96-300-0001"]
