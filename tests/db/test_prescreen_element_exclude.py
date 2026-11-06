"""预筛层的「必须不含」元素过滤（``Restraints`` 红色三态的落地）。

背景：三态元素约束里 ``ElementState.EXCLUDE`` 长期是**空转**的 —— 全仓没有任何
地方读它，``search_match`` 的注释也写着「留给调用方二次过滤」，而调用方并不存在。
于是「样品里 XRF/EDS 明确没有 Bi」这类化学上最硬的先验进入不了召回，基准报告
§11.5 记录的 ``3-2`` 假卡（``Bi1.284 O2.988 Y0.684`` 排到 pos 0.984，把真
CaF₂ 挤下去）只能靠人在结果里肉眼剔除。

这里固定三件事：

1. ``element_exclude_filter`` 的语义 —— 「**不含任何一个**给定元素」；
2. 与 ``elements_allowed``（必须全含）在 ``prescreen`` 里的交集行为；
3. ``Restraints.exclude()`` 能一路传到预筛（兼容层不再丢弃红色元素）。

与 ``elements_allowed`` 相反的一处刻意差异：未知元素（库里根本不存在）在
「必须不含」方向上**什么都排除不掉**，所以应返回全 ``True`` 而不是全 ``False``。
把「不可能含有」当成「不可能满足」会让一个拼错的符号直接清空结果。
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from tests.xindb_support import write_xindb
from xinmatch.core.db.reader_v3 import XinDBReader
from xinmatch.core.model import CellParams, Entry, Peak, Restraints
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
def exclude_library(tmp_path):
    """QUARTZ(SiO2) / BIYO(Bi-Y-O) / CALCITE(CaCO3)，峰位完全一致。"""
    lib = tmp_path / "EXCL-20260101.xinDB"
    entries = [
        _entry("96-100-0001", "O2 Si"),
        _entry("96-100-0002", "Bi1.284 O2.988 Y0.684"),
        _entry("96-100-0003", "C Ca O3"),
    ]
    return write_xindb(lib, entries)


def _d_to_two_theta(d: float, wavelength: float = WL) -> float:
    return math.degrees(2.0 * math.asin(wavelength / (2.0 * d)))


def _peaks() -> list[Peak]:
    return [Peak(two_theta=_d_to_two_theta(d), intensity=i)
            for d, i in zip(_D, _I, strict=True)]


# ---------------------------------------------------------------------------
# 1. element_exclude_filter 本身
# ---------------------------------------------------------------------------
def test_exclude_filter_drops_the_banned_phase(exclude_library) -> None:
    with XinDBReader(exclude_library) as reader:
        n = reader.entry_count()
        assert n == 3
        keep = reader.element_exclude_filter({"Bi"}, n)
        names = reader.entry_ids()

    assert keep is not None
    assert keep.shape == (3,)
    assert keep.dtype == bool
    kept = [eid for eid, ok in zip(names, keep, strict=True) if ok]
    assert "96-100-0002" not in kept
    assert kept == ["96-100-0001", "96-100-0003"]


def test_exclude_filter_is_case_insensitive(exclude_library) -> None:
    """元素符号大小写不应影响语义（索引键按 ``.title()`` 归一化）。"""
    with XinDBReader(exclude_library) as reader:
        n = reader.entry_count()
        lower = reader.element_exclude_filter({"bi"}, n)
        upper = reader.element_exclude_filter({"BI"}, n)
        mixed = reader.element_exclude_filter({"bI"}, n)
    assert np.array_equal(lower, upper)
    assert np.array_equal(lower, mixed)


def test_exclude_filter_unknown_element_excludes_nothing(exclude_library) -> None:
    """库里没有的元素：「不可能含有」→ 排不掉任何相，返回全 True。"""
    with XinDBReader(exclude_library) as reader:
        keep = reader.element_exclude_filter({"Zz"}, reader.entry_count())
    assert keep is not None
    assert keep.all()


def test_exclude_filter_empty_request_is_a_noop(exclude_library) -> None:
    """空列表 / 全空白 → ``None``，表示「本参数不生效」，调用方跳过过滤。"""
    with XinDBReader(exclude_library) as reader:
        n = reader.entry_count()
        assert reader.element_exclude_filter(set(), n) is None
        assert reader.element_exclude_filter(["", "   "], n) is None


def test_exclude_filter_multiple_elements_is_a_union(exclude_library) -> None:
    """多个红色元素是并集：含其中**任一**即淘汰。"""
    with XinDBReader(exclude_library) as reader:
        keep = reader.element_exclude_filter({"Bi", "Ca"}, reader.entry_count())
        names = reader.entry_ids()
    assert keep is not None
    kept = [eid for eid, ok in zip(names, keep, strict=True) if ok]
    assert kept == ["96-100-0001"]  # 只剩 SiO2


# ---------------------------------------------------------------------------
# 2. prescreen 集成
# ---------------------------------------------------------------------------
def _ids(result) -> list[str]:
    return list(result.candidate_ids)


def test_prescreen_without_exclusion_keeps_all_three(exclude_library) -> None:
    with XinDBReader(exclude_library) as reader:
        result = reader.prescreen(_D, _I, min_match=3, rank_limit=100)
    assert sorted(_ids(result)) == ["96-100-0001", "96-100-0002", "96-100-0003"]


def test_prescreen_honours_elements_excluded(exclude_library) -> None:
    with XinDBReader(exclude_library) as reader:
        result = reader.prescreen(_D, _I, min_match=3, rank_limit=100,
                                  elements_excluded={"Bi"})
    assert sorted(_ids(result)) == ["96-100-0001", "96-100-0003"]


def test_prescreen_combines_allowed_and_excluded(exclude_library) -> None:
    """绿色（必须含 O）× 红色（必须不含 Bi）取交集。"""
    with XinDBReader(exclude_library) as reader:
        result = reader.prescreen(_D, _I, min_match=3, rank_limit=100,
                                  elements_allowed={"O"},
                                  elements_excluded={"Bi"})
    assert sorted(_ids(result)) == ["96-100-0001", "96-100-0003"]


def test_prescreen_excluding_everything_returns_empty(exclude_library) -> None:
    """三条相都含 O → 全被排掉，且不抛异常。"""
    with XinDBReader(exclude_library) as reader:
        result = reader.prescreen(_D, _I, min_match=3, rank_limit=100,
                                  elements_excluded={"O"})
    assert result.candidate_ids == []
    assert result.n_hits == 0


def test_prescreen_excluded_does_not_disturb_truncation_flag(exclude_library) -> None:
    """过滤后候选数不超限 → ``truncated`` 必须为 False（不能因过滤虚报截断）。"""
    with XinDBReader(exclude_library) as reader:
        result = reader.prescreen(_D, _I, min_match=3, rank_limit=100,
                                  elements_excluded={"Bi"})
    assert result.truncated is False


# ---------------------------------------------------------------------------
# 3. Restraints（兼容层）→ 预筛
# ---------------------------------------------------------------------------
def test_restraints_exclude_reaches_the_prescreen(exclude_library) -> None:
    """``Restraints.exclude("Bi")`` 必须一路传到 v3 预筛，而不是被静默丢弃。"""
    r = Restraints()
    r.exclude("Bi")

    with XinDBReader(exclude_library) as reader:
        candidates = search_match(_peaks(), reader, WL, restraints=r, top_n=10)

    ids = [c.entry.entry_id for c in candidates]
    assert "96-100-0002" not in ids
    assert ids  # 剩下两条仍要被正常打分


def test_restraints_require_and_exclude_together(exclude_library) -> None:
    r = Restraints()
    r.require("O")
    r.exclude("Bi")

    with XinDBReader(exclude_library) as reader:
        candidates = search_match(_peaks(), reader, WL, restraints=r, top_n=10)

    ids = [c.entry.entry_id for c in candidates]
    assert set(ids) == {"96-100-0001", "96-100-0003"}
