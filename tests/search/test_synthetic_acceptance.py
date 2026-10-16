"""合成谱验证集（T0.3/T0.4 扩充样品——真相已知、可复现断言）。

13 组合成谱（D:\\Project\\XRD\\test_xrd\\synthetic\\synth_XX.txt）由
``tools/generate_synthetic_patterns.py`` 生成（COD 库卡片 0-100 相对强度 +
pseudo-Voigt 峰形 + 缓变背底 + 高斯噪音，Cu Kα，10–90°，0.02° 步进）。

验证目标：XinMatch 在**默认无机库 + 现状 FoM 参数**下，每一组合成谱的
任一真相相（按化学式元素集与比例判定）必须进入 Top-20 候选。

背景（为什么这条基线存在）：
- 用户已在参考软件中对合成谱 FPFM 验收：jingzhun 模式 13/13 真相相
  Top-1（FoM=1.0000），归档 tests/baseline/ref20261011/。
- XinMatch 侧曾经 3/13 命中，根因（已修复，详见 docs/STATUS.md）：
  1) 生成器峰强度用 CIF 结构因子（动态范围 1e17），与库卡片 0-100
     相对强度严重不匹配 → FoM intensity 失真；
  2) 库内无该编号时回退 CIF（强度仍失真）→ 改为库内同元素集卡片；
  3) 无机库缺 NaCl/KCl/MgO/CuO 卡片 → 从全库导入补卡（备份保留）。
- 修复后：Top-20 13/13、Top-5 13/13、Top-1 11/13；L3 真实谱基线
  Top-1 一致率保持 11/13 未退化（FoM 参数未改动）。
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from xinmatch.core.io import load_pattern
from xinmatch.core.preprocess.auto_pipeline import auto_process
from xinmatch.core.search.search_match import search_match

WL = 1.5406  # Cu Kα1（合成谱波长）
DB = Path(r"D:\Project\XRD\XinMatch\data\cod_inorganics.db")
SYNTH_DIR = Path(r"D:\Project\XRD\test_xrd\synthetic")

# 每组合成谱的真相相（化学式，与 manifest.md 同源；is_truth 按元素集+比例判定，
# 兼容库内 formula 写法变体，如 "Cl Na" / "Na Cl"、下标连写 "Fe3 O4"）。
TRUTH: dict[str, list[str]] = {
    "synth_01": ["Al2 O3", "O Zn", "Ca F2"],
    "synth_02": ["O2 Si", "C Ca O3"],
    "synth_03": ["O2 Ti"],
    "synth_04": ["Fe2 O3", "O2 Si"],
    "synth_05": ["Cu O", "O Zn"],
    "synth_06": ["Ba O3 Ti"],
    "synth_07": ["Cl Na", "Cl K"],
    "synth_08": ["Ca F2", "Al2 O3"],
    "synth_09": ["C"],
    "synth_10": ["Fe", "Fe3 O4"],
    "synth_11": ["Ca O4 S", "C Ca O3"],
    "synth_12": ["Mg O", "Al2 Mg O4"],
    "synth_13": ["O2 Zr"],
}

_EL = re.compile(r"([A-Z][a-z]?)([0-9.]*)")


def _stoich(formula: str) -> dict[str, float]:
    """解析化学式 → {元素: 化学计量}（忽略空格分隔的游离数字）。"""
    out: dict[str, float] = {}
    for el, num in _EL.findall(formula or ""):
        v = float(num) if num else 1.0
        if v > 0:
            out[el] = out.get(el, 0.0) + v
    return out


def is_truth(cand_formula: str, truth_formula: str, tol: float = 0.18) -> bool:
    """候选卡片化学式是否与真相相一致（元素集相同 + 归一化比例差 ≤ tol）。"""
    a, b = _stoich(cand_formula), _stoich(truth_formula)
    if not a or not b or set(a) != set(b):
        return False
    ma, mb = min(a.values()), min(b.values())
    return all(abs(a[k] / ma - b[k] / mb) / (b[k] / mb) <= tol for k in b)


@pytest.fixture(scope="module")
def conn():
    c = sqlite3.connect(DB)
    yield c
    c.close()


@pytest.fixture(scope="module")
def results(conn):
    """一次性跑完全部 13 组合成谱检索，供全模块断言复用。"""
    out: dict[str, list] = {}
    for name, _truth in TRUTH.items():
        pat = load_pattern(SYNTH_DIR / f"{name}.txt")
        _proc, peaks = auto_process(
            pat,
            config={
                "wavelength_kalpha1": WL,
                "wavelength_kalpha2": 1.5444,
                "peak_sensitivity": "medium",
            },
        )
        cands = search_match(peaks, conn, wavelength=WL, top_n=20,
                             recall_strongest_peak=True)
        out[name] = [
            {"entry_id": c.entry.entry_id, "formula": str(c.entry.formula),
             "fom": c.fom}
            for c in cands
        ]
    return out


@pytest.mark.skipif(not SYNTH_DIR.exists(), reason="合成谱目录不存在（仓库外）")
class TestSyntheticAcceptance:
    """13 组合成谱：任一真相相必须进入 Top-20（现状 FoM + 默认无机库）。"""

    def test_all_13_samples_available(self):
        missing = [f"synth_{i:02d}.txt" for i in range(1, 14)
                   if not (SYNTH_DIR / f"synth_{i:02d}.txt").is_file()]
        assert not missing, f"缺失合成谱: {missing}"

    def test_truth_in_top20_for_all(self, results):
        """全部 13 组：任一真相相进入 Top-20。"""
        failed: list[str] = []
        for name, truths in TRUTH.items():
            top20 = results[name]
            if not any(
                is_truth(c["formula"], tf)
                for c in top20
                for tf in truths
            ):
                failed.append(f"{name}(top1={top20[0]['formula'] if top20 else '-'})")
        assert not failed, f"真相相未进 Top-20: {failed}"

    def test_truth_in_top5_for_all(self, results):
        """全部 13 组：任一真相相进入 Top-5（更严格，当前 13/13 达成）。"""
        failed: list[str] = []
        for name, truths in TRUTH.items():
            top5 = results[name][:5]
            if not any(
                is_truth(c["formula"], tf)
                for c in top5
                for tf in truths
            ):
                failed.append(name)
        assert not failed, f"真相相未进 Top-5: {failed}"

    def test_barium_titanate_in_top5(self, results):
        """synth_06（BaTiO3 单相）真相相须进 Top-5。"""
        assert any(
            is_truth(c["formula"], "Ba O3 Ti")
            for c in results["synth_06"][:5]
        )

    def test_alkali_halides_covered(self, results):
        """synth_07（NaCl/KCl）——库覆盖补齐后两真相相都须进 Top-20。"""
        top20 = results["synth_07"]
        for tf in ("Cl Na", "Cl K"):
            assert any(is_truth(c["formula"], tf) for c in top20), (
                f"synth_07 真相相 {tf} 未进 Top-20"
            )

    def test_deterministic(self, conn):
        """同库、同参数下检索结果可复现（两次运行一致）。"""
        def run_once():
            pat = load_pattern(SYNTH_DIR / "synth_06.txt")
            _p, peaks = auto_process(
                pat,
                config={"wavelength_kalpha1": WL, "wavelength_kalpha2": 1.5444,
                        "peak_sensitivity": "medium"},
            )
            cands = search_match(peaks, conn, wavelength=WL, top_n=20,
                                 recall_strongest_peak=True)
            return [(c.entry.entry_id, round(c.fom, 6)) for c in cands]

        assert run_once() == run_once()
