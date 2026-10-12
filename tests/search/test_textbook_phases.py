"""教科书物相环境条件检索回归（v1.4.0 / 任务 #14）。

用教科书晶胞常数现场合成**单波长（纯 Kα1）**高斯谱，走默认
``auto_process`` + 默认 ``search_match``：

1. 峰查找必须恰好找到全部教科书线——锁定 Kα2 剥离自激振荡护栏与
   MAD 噪声估计崩塌下限两处修复（修复前：5 条真线会炸出 40+ 伪峰，
   密集 junk 卡片凭 P_npeaks 霸榜）；
2. 环境条件卡片（``96-900-3308`` Halite / ``96-900-3112`` Sylvite /
   ``96-900-0501`` Periclase，由 ``tools/patch_cod_inorganics.py``
   迁移插入）必须进入 Top-20，Halite 必须进入 Top-5。

背景：COD dump 中这三相的纯二元条目数为 0，非环境条件变体卡片
（如 100K 高压 NaCl）与教科书线位偏差大；上游数据缺陷由迁移工具
修复，本条回归同时锁定「峰查找稳定性 + 环境条件卡片在位」两个
修复面。库缺卡片时测试失败并提示运行迁移工具。
"""

from __future__ import annotations

import math
import sqlite3
from pathlib import Path

import numpy as np
import pytest

from xinmatch.core.model import Pattern
from xinmatch.core.preprocess.auto_pipeline import auto_process
from xinmatch.core.search.search_match import search_match

WL = 1.5406  # Cu Kα1
DB = Path(r"D:\Project\XRD\XinMatch\data\cod_inorganics.db")

# 2θ grid: 10–90°, 0.02° step（与合成谱生成器一致）。
TT = np.arange(10.0, 90.0, 0.02)

# (标签, entry_id, 晶胞常数 a, [(h,k,l), 相对强度]) —— 教科书环境条件结构。
PHASES: list[tuple[str, str, float, list[tuple[tuple[int, int, int], float]]]] = [
    ("Halite", "96-900-3308", 5.6402,
     [((1, 1, 1), 13.0), ((2, 0, 0), 100.0), ((2, 2, 0), 55.0),
      ((3, 1, 1), 2.0), ((2, 2, 2), 15.0), ((4, 0, 0), 5.0)]),
    ("Sylvite", "96-900-3112", 6.2931,
     [((2, 0, 0), 100.0), ((2, 2, 0), 55.0), ((2, 2, 2), 13.0),
      ((4, 0, 0), 4.0), ((4, 2, 0), 7.0)]),
    ("Periclase", "96-900-0501", 4.2117,
     [((1, 1, 1), 30.0), ((2, 0, 0), 100.0), ((2, 2, 0), 45.0),
      ((3, 1, 1), 8.0), ((2, 2, 2), 12.0)]),
]

# 环境条件卡片在库中缺失时的指引。
_MIGRATION_HINT = (
    "环境条件卡片缺失，请运行: python -m tools.patch_cod_inorganics"
)


def _two_theta(d: float) -> float:
    s = min(1.0, WL / (2.0 * d))
    return 2.0 * math.degrees(math.asin(s))


def build_textbook_pattern(
    a: float,
    lines: list[tuple[tuple[int, int, int], float]],
) -> Pattern:
    """由立方晶胞常数 + (hkl, 相对强度) 线表合成纯 Kα1 高斯谱。"""
    y = np.full(TT.shape, 30.0)  # 缓变背底
    for (h, k, ll), rel in lines:
        d = a / math.sqrt(h * h + k * k + ll * ll)
        x0 = _two_theta(d)
        y = y + rel * 1000.0 * np.exp(
            -4.0 * math.log(2.0) * ((TT - x0) / 0.18) ** 2
        )
    return Pattern(two_theta=TT, intensity=y, wavelength=WL, step=0.02)


@pytest.fixture(scope="module")
def conn():
    if not DB.exists():
        pytest.skip(f"检索库不存在: {DB}")
    c = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    yield c
    c.close()


@pytest.fixture(scope="module")
def ambient_results(conn) -> dict[str, list]:
    """一次性跑完三相环境条件检索，供全模块断言复用。"""
    out: dict[str, list] = {}
    for label, _eid, a, lines in PHASES:
        pat = build_textbook_pattern(a, lines)
        _proc, peaks = auto_process(pat)
        cands = search_match(peaks, conn, wavelength=WL, top_n=20)
        out[label] = cands
    return out


@pytest.mark.parametrize(
    "label,eid,a,lines",
    PHASES,
    ids=[p[0] for p in PHASES],
)
class TestTextbookPhaseAmbient:
    """环境条件合成谱：峰数精确 + 真相卡片排名达标。"""

    def test_peak_count_exact(self, label, eid, a, lines):
        """峰查找恰好找到全部教科书线（锁定 alpha2 护栏 + 噪声下限）。

        修复前：Kα2 剥离在无卫星峰谱上自激振荡（±24000 计数，达峰高
        50%）+ SNIP 残留 ±16 计数被崩塌的 MAD 噪声门限全放行 → 5 条
        真线炸出 40+ 伪峰。
        """
        pat = build_textbook_pattern(a, lines)
        _proc, peaks = auto_process(pat)
        assert len(peaks) == len(lines), (
            f"{label}: 期望 {len(lines)} 个峰，实得 {len(peaks)} 个"
            f"（2θ={[round(p.two_theta, 2) for p in peaks]}）"
        )

    def test_ambient_card_ranked(self, conn, ambient_results, label, eid, a, lines):
        """环境条件卡片进入 Top-20（库缺卡片时提示运行迁移工具）。"""
        row = conn.execute(
            "SELECT COUNT(*) FROM entries WHERE entry_id = ?", (eid,)
        ).fetchone()
        assert row is not None and row[0] == 1, f"{label}: {_MIGRATION_HINT}"
        cands = ambient_results[label]
        rank = next(
            (i for i, c in enumerate(cands, 1) if c.entry.entry_id == eid), None
        )
        assert rank is not None, (
            f"{label}: 真相卡片 {eid} 未进 Top-20；"
            f"榜首: {cands[0].entry.entry_id} {cands[0].entry.formula} "
            f"FoM={cands[0].fom:.3f}"
        )

    def test_halite_top5(self, ambient_results, label, eid, a, lines):
        """Halite（最强线 200，Fm-3m）必须进入 Top-5。"""
        if label != "Halite":
            pytest.skip("仅 Halite 断言 Top-5")
        cands = ambient_results["Halite"]
        top5 = [c.entry.entry_id for c in cands[:5]]
        assert eid in top5, f"Halite 未进 Top-5: {top5}"
