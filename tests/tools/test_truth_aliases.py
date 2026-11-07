"""§31.5 别名缺口审计落地 —— 真值别名表（TRUTH_FINE / IUCR_FINE）的判据级单测。

只测「真值侧 accepted 名单 × mineral_name_matches」的语义，不跑检索：

* 该补的四个别名（同物异名 / 化学名 / 错拼 / 种名）必须命中，且逐卡核过晶胞
  （Calcite 两张 R-3c、Bohmite 三张 Cmcm、Orthoclase 即 K-长石种名）；
* 刻意不收的 ``Corundum`` ← ``"eta- Al-oxid"``（96-110-1168，空间群 Fd-3m
  尖晶石型 η-Al₂O₃）必须仍然被拒 —— 同组成不同多晶型是正确拒绝
  （与 Rutile←Anatase 同类），§31.5 原表误列「该补」已更正；
* 别名经 :func:`mineral_species_key` 归一化生效，不做子串匹配。
"""

from __future__ import annotations

from tools.bench_iucr import IUCR_TRUTH_FINE
from tools.bench_real_samples import TRUTH_FINE
from xinmatch.core.search.mineral_name import (
    has_species_name,
    mineral_name_matches,
)


def _truth_of(table, sample: str, label: str):
    return next(t for t in table[sample] if t.label == label)


# ---------------------------------------------------------------------------
# 该补：同物异名 / 化学名 / 错拼 / 种名
# ---------------------------------------------------------------------------
def test_calcite_accepts_chemical_and_formula_names():
    t = _truth_of(TRUTH_FINE, "2-1", "Calcite")
    assert mineral_name_matches("Calcium Carbonate", t.minerals)
    assert mineral_name_matches("CaCO3", t.minerals)
    assert mineral_name_matches("Calcite", t.minerals)
    # 首尾限定词照常丢弃；嵌入词不合并（保守尺子）
    assert mineral_name_matches("calcite high", t.minerals)
    assert not mineral_name_matches("Nitrocalcite", t.minerals)


def test_calcite_alias_applies_to_every_calcite_truth():
    """5-1 / 5-2 / 5-2b 的 Calcite 真值同样带别名（同一 _CALCITE_NAMES）。"""
    for sample in ("5-1", "5-2", "5-2b"):
        t = _truth_of(TRUTH_FINE, sample, "Calcite")
        assert mineral_name_matches("Calcium Carbonate", t.minerals), sample


def test_boehmite_accepts_misspelling():
    t = _truth_of(TRUTH_FINE, "7-1", "Boehmite")
    assert mineral_name_matches("Boehmite", t.minerals)
    assert mineral_name_matches("Bohmite", t.minerals)


def test_bauxite_boehmite_accepts_misspelling():
    t = _truth_of(IUCR_TRUTH_FINE, "BAUXITE", "Boehmite")
    assert mineral_name_matches("Bohmite", t.minerals)


def test_feldspar_accepts_orthoclase():
    t = _truth_of(TRUTH_FINE, "7-2", "Feldspar")
    assert mineral_name_matches("Orthoclase", t.minerals)
    assert mineral_name_matches("K-feldspar", t.minerals)
    # 钠长石是相邻种，不得因 Feldspar 泛名而并入
    assert not mineral_name_matches("Albite", t.minerals)


# ---------------------------------------------------------------------------
# 该拒：同组成不同多晶型
# ---------------------------------------------------------------------------
def test_corundum_rejects_eta_alumina():
    """96-110-1168 ``"eta- Al-oxid_fit2gnn"`` 是 Fd-3m 尖晶石型 η-Al₂O₃，
    不是刚玉（R-3c）—— 按名判定必须拒绝，且它的名字是「有物种名」的
    （非占位符），所以也不会回落到组成比。"""
    t = _truth_of(TRUTH_FINE, "3-1", "Corundum")
    assert has_species_name("eta- Al-oxid_fit2gnn")
    assert not mineral_name_matches("eta- Al-oxid_fit2gnn", t.minerals)


def test_polymorph_rejections_unchanged():
    anatase = _truth_of(TRUTH_FINE, "2-2", "Anatase")
    rutile = _truth_of(TRUTH_FINE, "2-2", "Rutile")
    assert not mineral_name_matches("Rutile", anatase.minerals)
    assert not mineral_name_matches("Anatase", rutile.minerals)
