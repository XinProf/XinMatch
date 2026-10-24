"""v3 (``.xinDB``) 检索集成回归测试。

覆盖：

1. **prescreen 强度对齐** —— ``search_match_v3`` 把强峰的 ``(d, intensity)``
   成对送给 ``prescreen``；旧实现分别取"前 N 个 d"和"前 N 个强度"，一旦某个
   峰因 2θ ≤ 0 被跳过，强度就会错位到别的测量窗上（静默改变候选排序）。
2. **端到端 v3 检索** —— 用库内卡片反演的峰表自召回，Top-1 必须是该相；
   混入一条非法峰（2θ=0）也不得破坏召回。
3. **分派** —— ``xinmatch.core.search.search_match`` 收到 ``XinDBReader``
   时必须走 v3 管线（而不是 v2 的 SQL peaks 行表）。
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from tests.xindb_support import write_xindb
from xinmatch.core.db.reader_v3 import PrescreenResult, XinDBReader
from xinmatch.core.db.search_v3 import (
    _exp_d_intensity_pairs,
    search_match_v3,
)
from xinmatch.core.model import CellParams, Entry, Peak
from xinmatch.core.search import search_match

WL = 1.5406


def _entry(entry_id: str, d: list[float], i: list[float], formula: str) -> Entry:
    return Entry(
        entry_id=entry_id,
        formula=formula,
        d_spacings=np.array(d, dtype=np.float64),
        intensities=np.array(i, dtype=np.float64),
        mineral_name=formula,
        space_group="P 1",
        cell=CellParams(4.913, 4.913, 5.405, gamma=120.0),
        hkl=None,
        literature={"source": "synth"},
    )


def _d_to_two_theta(d: float, wavelength: float = WL) -> float:
    return math.degrees(2.0 * math.asin(wavelength / (2.0 * d)))


def _peaks_from_d(ds: list[float], is_: list[float]) -> list[Peak]:
    return [
        Peak(two_theta=_d_to_two_theta(d), intensity=i)
        for d, i in zip(ds, is_, strict=True)
    ]


class _RecordingReader:
    """Minimal reader double that records what the prescreen was fed."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[float], list[float] | None, dict]] = []

    def prescreen(self, measured_d, measured_i=None, **kwargs) -> PrescreenResult:
        self.calls.append(
            (list(measured_d), None if measured_i is None else list(measured_i), kwargs)
        )
        return PrescreenResult(candidate_ids=[], truncated=False, n_hits=0)

    def fetch_peaks(self, entry_ids):  # pragma: no cover - no candidates
        return {}

    def fetch_meta(self, entry_id):  # pragma: no cover - no candidates
        return None


# ---------------------------------------------------------------------------
# 1. prescreen 入参对齐
# ---------------------------------------------------------------------------
def test_prescreen_weights_stay_attached_to_their_d() -> None:
    peaks = [
        Peak(two_theta=0.0, intensity=9999.0),  # 非法峰：d 不可得，会被跳过
        Peak(two_theta=_d_to_two_theta(3.34), intensity=500.0),
        Peak(two_theta=_d_to_two_theta(4.26), intensity=300.0),
        Peak(two_theta=_d_to_two_theta(2.46), intensity=100.0),
    ]
    reader = _RecordingReader()
    search_match_v3(peaks, reader, WL)
    assert len(reader.calls) == 1
    measured_d, measured_i, _kwargs = reader.calls[0]
    assert measured_i is not None
    assert len(measured_d) == len(measured_i) == 3
    # 强度与 d 必须一一对应（按强度降序：500 @3.34、300 @4.26、100 @2.46）
    assert measured_i == [500.0, 300.0, 100.0]
    assert measured_d == pytest.approx([3.34, 4.26, 2.46])


def test_exp_d_intensity_pairs_skips_invalid_peaks() -> None:
    peaks = [
        Peak(two_theta=0.0, intensity=10.0),
        Peak(two_theta=30.0, intensity=20.0),
        Peak(two_theta=40.0, intensity=30.0),
    ]
    pairs = _exp_d_intensity_pairs(peaks, WL)
    assert [i for _d, i in pairs] == [20.0, 30.0]
    assert all(d > 0 for d, _i in pairs)


# ---------------------------------------------------------------------------
# 2. 端到端 v3 检索
# ---------------------------------------------------------------------------
@pytest.fixture
def tiny_library(tmp_path):
    lib = tmp_path / "TINY-20260101.xinDB"
    a = _entry("96-100-0001", [3.34, 4.26, 2.46, 1.82], [1000, 550, 300, 120], "O2 Si")
    b = _entry("96-100-0002", [2.09, 2.55, 1.60, 1.45], [1000, 400, 250, 80], "Na Cl")
    return write_xindb(lib, [a, b]), a


def test_v3_search_recalls_the_source_phase(tiny_library) -> None:
    lib, source = tiny_library
    peaks = _peaks_from_d(source.d_spacings.tolist(), source.intensities.tolist())

    with XinDBReader(lib) as reader:
        result = search_match_v3(peaks, reader, WL, top_n=5)

    assert result.candidates, "库内相必须被召回"
    assert result.candidates[0].entry.entry_id == source.entry_id
    assert result.truncated is False


def test_v3_search_survives_invalid_peak(tiny_library) -> None:
    lib, source = tiny_library
    peaks = [Peak(two_theta=0.0, intensity=1e9)] + _peaks_from_d(
        source.d_spacings.tolist(), source.intensities.tolist()
    )

    with XinDBReader(lib) as reader:
        result = search_match_v3(peaks, reader, WL, top_n=5)

    assert result.candidates
    assert result.candidates[0].entry.entry_id == source.entry_id


def test_search_match_dispatches_reader_to_v3(tiny_library) -> None:
    """``search_match`` 收到 XinDBReader 时必须走 v3（v2 的 SQL 路径会炸）。"""
    lib, source = tiny_library
    peaks = _peaks_from_d(source.d_spacings.tolist(), source.intensities.tolist())

    with XinDBReader(lib) as reader:
        candidates = search_match(peaks, reader, WL, top_n=5)

    assert candidates
    assert candidates[0].entry.entry_id == source.entry_id
