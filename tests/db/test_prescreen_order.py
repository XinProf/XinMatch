"""预筛排序：``prescreen_order`` 两种口径（``intensity`` / ``hits``）。

3.4.x 的排序是「主峰命中 → 强度加权命中 → 命中数」。§14.5 判断「二值主峰判据
信息量不足」，建议改成强度加权覆盖率的连续量。2026-11-06 的实测把这件事拆成了
两半，两半都得固定住：

1. **主峰门控是载荷，不能连续化**。去掉它（只按命中数排）池内召回从 51/67 掉到
   41/67；把门控换成加权项（``2·main_hit + 命中率`` / ``+0.3·whits``）分别是
   50/67 与 49/67，都不如纯二值门控 + 命中数。所以第一键不动。
2. **第二键该用命中数还是强度形，两把尺子结论相反**：

   ====  ================  ============  ==========  ===========
   口径   合成 T1/T5/序贯  合成相召回    真实 T1/T5  真实相召回
   ====  ================  ============  ==========  ===========
   intensity  11/13·12/13·10/13  19/24   10/12·12/12  19/43
   hits        8/13·10/13·5/13   14/24   11/12·12/12  23/43
   ====  ================  ============  ==========  ===========

   合成谱是用库内同一批参考强度反演的，强度形判据在那里天然占优；真实谱没有
   这个关系。默认仍是 ``intensity``（「Top-1/Top-5 不退化」是硬验收口径），
   切换属于产品裁定，所以做成开关而不是改默认。

本文件只测**机制**：两种口径都能选中、都能被显式指定、非法值会报错。
"""

from __future__ import annotations

import numpy as np
import pytest

from xinmatch.core.db.reader_v3 import (
    _DEFAULT_PRESCREEN_ORDER,
    _ORDER_CHOICES,
    _ORDER_HITS,
    _ORDER_INTENSITY,
    XinDBReader,
)
from xinmatch.core.model.entry import Entry


def _phase(entry_id: str, d: list[float], intensities: list[float]) -> Entry:
    return Entry(
        entry_id=entry_id,
        formula="X Y",
        d_spacings=np.asarray(d, dtype=float),
        intensities=np.asarray(intensities, dtype=float),
    )


# ---------------------------------------------------------------------------
# 开关本体
# ---------------------------------------------------------------------------
def test_default_order_is_intensity_until_decided():
    """默认必须是 3.4.x 的口径 —— 换默认要用户裁定，不是顺手改。"""
    assert _DEFAULT_PRESCREEN_ORDER == _ORDER_INTENSITY
    assert set(_ORDER_CHOICES) == {_ORDER_INTENSITY, _ORDER_HITS}


def test_unknown_order_is_rejected(tmp_path, xindb_factory):
    """拼错的口径必须立刻报错，而不是静默退回默认值。"""
    lib = xindb_factory(tmp_path / "bad.xinDB",
                        [_phase("A", [2.0], [1000.0])])
    with pytest.raises(ValueError, match="prescreen_order"):
        XinDBReader(lib, prescreen_order="hit")


# ---------------------------------------------------------------------------
# 两种口径的分歧点：主峰都命中，一个命中少但强度形好、一个命中多但强度形差
# ---------------------------------------------------------------------------
@pytest.fixture
def sharp_vs_broad(tmp_path, xindb_factory):
    """SHARP 的最强线落在**最强**实测峰上但只命中 2 窗；BROAD 命中 3 窗，
    但它的最强线只落在一个几乎为零的实测峰上。

    这正是多相谱里次相的样子：线多，但没有一条落在主峰上。两种口径在这里
    给出相反结论 —— 强度形偏爱 SHARP，命中数偏爱 BROAD。
    """
    sharp = _phase("SHARP", [2.0, 3.0], [1000.0, 500.0])
    broad = _phase("BROAD", [5.0, 3.0, 4.0], [1000.0, 500.0, 500.0])
    return xindb_factory(tmp_path / "order.xinDB", [sharp, broad])


def test_intensity_order_prefers_the_sharper_shape(sharp_vs_broad):
    reader = XinDBReader(sharp_vs_broad, prescreen_order=_ORDER_INTENSITY)
    try:
        ids = reader.prescreen(
            [2.0, 3.0, 4.0, 5.0], [1000.0, 1.0, 1.0, 1.0],
            min_match=1, rank_limit=2, diversify_slots=0,
        ).candidate_ids
    finally:
        reader.close()
    assert ids == ["SHARP", "BROAD"]


def test_hits_order_prefers_the_richer_hit_count(sharp_vs_broad):
    reader = XinDBReader(sharp_vs_broad, prescreen_order=_ORDER_HITS)
    try:
        ids = reader.prescreen(
            [2.0, 3.0, 4.0, 5.0], [1000.0, 1.0, 1.0, 1.0],
            min_match=1, rank_limit=2, diversify_slots=0,
        ).candidate_ids
    finally:
        reader.close()
    assert ids == ["BROAD", "SHARP"]


def test_hits_order_still_breaks_ties_by_intensity(tmp_path, xindb_factory):
    """命中数相同时，``hits`` 口径仍用强度形作次键 —— 它只是降级，没有被删。

    两条相各命中 1 个窗，区别只在命中窗的实测强度（2.0 是主峰、5.0 几乎为零）。
    """
    strong = _phase("STRONG", [2.0, 9.0], [1000.0, 100.0])
    weak = _phase("WEAK", [5.0, 9.9], [1000.0, 100.0])
    lib = xindb_factory(tmp_path / "tie.xinDB", [strong, weak])
    reader = XinDBReader(lib, prescreen_order=_ORDER_HITS)
    try:
        ids = reader.prescreen(
            [2.0, 5.0], [1000.0, 1.0],
            min_match=1, rank_limit=2, diversify_slots=0,
        ).candidate_ids
    finally:
        reader.close()
    assert ids == ["STRONG", "WEAK"]


# ---------------------------------------------------------------------------
# 主峰门控：两种口径都必须保留
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("order", [_ORDER_INTENSITY, _ORDER_HITS])
def test_main_peak_tier_dominates_a_richer_hit_count(tmp_path, xindb_factory,
                                                    order):
    """没有主峰命中的相，哪怕命中 3 个窗，也排在主峰命中 1 个窗的相之后。

    这是本轮的**反向**断言：实测「去掉门控」掉 10 个真值相、「换成加权项」掉
    1~2 个，所以门控保持为第一键，两种口径都一样。
    """
    main = _phase("MAIN", [2.0, 9.0, 9.5], [1000.0, 50.0, 50.0])
    # MANY 的最强线故意放在 7.0 Å（没有任何实测窗覆盖），于是命中 3 个窗却
    # 没有主峰命中 —— 正是「次相线多但都不是最强」的形态。
    many = _phase("MANY", [7.0, 3.0, 4.0, 5.0], [1000.0, 10.0, 10.0, 10.0])
    lib = xindb_factory(tmp_path / f"gate_{order}.xinDB", [main, many])
    reader = XinDBReader(lib, prescreen_order=order)
    try:
        ids = reader.prescreen(
            [2.0, 3.0, 4.0, 5.0], [1.0, 1.0, 1.0, 1.0],
            min_match=1, rank_limit=2, diversify_slots=0,
        ).candidate_ids
    finally:
        reader.close()
    assert ids == ["MAIN", "MANY"]


def test_diverse_slots_can_bypass_the_main_peak_gate(tmp_path, xindb_factory):
    """既然门控是载荷，就必须留一条绕过它的通道给次相 —— ``diversify_slots``。

    默认口径下这条通道是 20% 名额（``_DIVERSIFY_SHARE = 0.2``）。
    """
    main = _phase("MAIN", [2.0, 9.0, 9.5], [1000.0, 50.0, 50.0])
    many = _phase("MANY", [7.0, 3.0, 4.0, 5.0], [1000.0, 10.0, 10.0, 10.0])
    lib = xindb_factory(tmp_path / "div2.xinDB", [main, many])
    reader = XinDBReader(lib)
    try:
        legacy = reader.prescreen(
            [2.0, 3.0, 4.0, 5.0], [1.0, 1.0, 1.0, 1.0],
            min_match=1, rank_limit=1, diversify_slots=0,
        ).candidate_ids
        diverse = reader.prescreen(
            [2.0, 3.0, 4.0, 5.0], [1.0, 1.0, 1.0, 1.0],
            min_match=1, rank_limit=1, diversify_slots=1,
        ).candidate_ids
    finally:
        reader.close()
    assert legacy == ["MAIN"]
    assert diverse == ["MANY"]
