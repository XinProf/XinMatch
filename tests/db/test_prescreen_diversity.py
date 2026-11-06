"""Prescreen slot allocation: the hit-count half must rescue minor phases.

The legacy order ranks candidates by *is my strongest reflection one of the
strong measured peaks* → intensity-weighted hits → hit count.  In a mixture that
question is really "am I the dominant phase": a minor phase's strongest line is a
weak measured peak, so it never makes the candidate cut (2026-11-04: Al₂O₃ and
CaF₂ in a ZnO + Al₂O₃ + CaF₂ pattern were absent from an 800-slot pool although
they rank 197 with an 8000-slot pool).

3.2.0 的解法是「抽一部分名额改用命中数排序」。3.5.0 复核后**保留**这道配额：
它仍然是次相进池的通道（默认口径下关掉它会同时损失合成 T1 与真实卡级相召回）。
另一种口径（``prescreen_order="hits"``，命中数直接做次键）下配额才变成负收益，
见 ``test_prescreen_order.py`` 与报告 §16。下面这些测试固定配额机制本身。
"""

from __future__ import annotations

import numpy as np

from xinmatch.core.db.reader_v3 import _DIVERSIFY_SHARE, XinDBReader, _diverse_slots
from xinmatch.core.model.entry import Entry


# ---------------------------------------------------------------------------
# slot arithmetic
# ---------------------------------------------------------------------------
def test_default_share_is_twenty_percent():
    """默认口径（``intensity``）下配额仍是 20%：它是次相进池的唯一通道。

    3.5.0 实测：配额只对新排序（``prescreen_order="hits"``）有害；默认口径下
    关掉它会同时损失合成 T1（11/13→9/13）与真实卡级相召回（19/43→18/43）。
    """
    assert _DIVERSIFY_SHARE == 0.2
    assert _diverse_slots(800, None) == 160
    assert _diverse_slots(800, 0) == 0          # 显式关闭
    assert _diverse_slots(800, 200) == 200


def test_override_is_clamped():
    assert _diverse_slots(800, 0) == 0          # legacy behaviour
    assert _diverse_slots(800, 200) == 200
    assert _diverse_slots(800, 5000) == 800     # never more than the pool
    assert _diverse_slots(800, -5) == 0


# ---------------------------------------------------------------------------
# ordering
# ---------------------------------------------------------------------------
def _phase(entry_id: str, d: list[float], intensities: list[float]) -> Entry:
    return Entry(
        entry_id=entry_id,
        formula="X Y",
        d_spacings=np.asarray(d, dtype=float),
        intensities=np.asarray(intensities, dtype=float),
    )


def test_minor_phase_enters_the_pool_through_the_hit_count_half(
        tmp_path, xindb_factory):
    """`MINOR` explains two strong peaks but its strongest line is absent."""
    minor = _phase("MINOR", [3.0, 4.0, 5.0, 9.9], [900, 500, 400, 100])
    major = _phase("MAJOR", [8.0, 7.0], [900, 500])
    reader = XinDBReader(xindb_factory(tmp_path / "div.xinDB", [minor, major]))
    try:
        measured_d = [4.0, 5.0, 8.0]
        measured_i = [1.0, 1.0, 1.0]
        legacy = reader.prescreen(measured_d, measured_i, min_match=1,
                                  rank_limit=1, diversify_slots=0)
        assert legacy.candidate_ids == ["MAJOR"]  # main peak wins the only slot

        diverse = reader.prescreen(measured_d, measured_i, min_match=1,
                                   rank_limit=1, diversify_slots=1)
        assert diverse.candidate_ids == ["MINOR"]  # two hits beat one main peak
    finally:
        reader.close()


def test_diversify_zero_keeps_every_legacy_slot(tmp_path, xindb_factory):
    """With both slots legacy-ordered the two phases keep their legacy order."""
    minor = _phase("MINOR", [3.0, 4.0, 5.0, 9.9], [900, 500, 400, 100])
    major = _phase("MAJOR", [8.0, 7.0], [900, 500])
    reader = XinDBReader(xindb_factory(tmp_path / "legacy.xinDB", [minor, major]))
    try:
        ids = reader.prescreen([4.0, 5.0, 8.0], [1.0, 1.0, 1.0], min_match=1,
                               rank_limit=2, diversify_slots=0).candidate_ids
        assert ids == ["MAJOR", "MINOR"]
        # And with the default quota the minor phase is promoted into the pool.
        promoted = reader.prescreen([4.0, 5.0, 8.0], [1.0, 1.0, 1.0], min_match=1,
                                    rank_limit=2, diversify_slots=1).candidate_ids
        # Legacy picks keep the front of the pool; the hit-count half fills the rest.
        assert set(promoted) == {"MAJOR", "MINOR"}
        assert promoted[0] == "MAJOR"
    finally:
        reader.close()
