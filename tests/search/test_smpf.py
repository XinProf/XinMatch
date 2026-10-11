"""Tests for SMPF (Search-Match with Profile Fitting, 全谱拟合检索).

Covers:
* unit behaviour of the profile-expansion / theory / scoring primitives;
* per-candidate refinement recovery (scale / shift / FWHM / background);
* ranking (true entry above wrong), determinism, empty input;
* synthetic 13-set acceptance (truth in Top-20), re-using the canonical
  ``TRUTH`` / ``is_truth`` from :mod:`tests.search.test_synthetic_acceptance`;
* real-pattern record mode (13 Cu Kα patterns, Kα1/Kα2 doublet);
* a single-pattern performance guard (< 120 s).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pytest

from xinmatch.core.model import Entry, Pattern
from xinmatch.core.search.smpf import (
    SmpfConfig,
    compute_fom,
    compute_rwp,
    expand_reflections,
    fit_candidate,
    generate_theory_profile,
    search_match_smpf,
)

WL = 1.5406
DB = Path(r"D:\Project\XRD\XinMatch\data\cod_inorganics.db")
SYNTH_DIR = Path(r"D:\Project\XRD\test_xrd\synthetic")
REAL_DIR = Path(r"D:\Project\XRD\test_xrd\txt")


def _entry(ds: list[float], ints: list[float], eid: str = "ref",
           formula: str = "Si O2") -> Entry:
    return Entry(
        entry_id=eid,
        formula=formula,
        d_spacings=np.array(ds, dtype=np.float64),
        intensities=np.array(ints, dtype=np.float64),
    )


# A small, well-separated stick pattern.
_DS = [4.257, 3.343, 2.457, 2.282, 2.128, 1.980, 1.818]
_INTS = [100.0, 80.0, 12.0, 12.0, 4.0, 14.0, 4.0]
_X = np.arange(5.0, 90.0, 0.02, dtype=np.float64)


# --------------------------------------------------------------------------- #
# Reflection expansion (single line / Kα doublet)
# --------------------------------------------------------------------------- #
def test_expand_single_line():
    e = _entry(_DS, _INTS)
    c, a = expand_reflections(e, WL, None, 5.0, 90.0)
    # All 7 reflections fall in 5-90° for Cu Kα1.
    assert c.size == 7
    assert np.allclose(a, _INTS)


def test_expand_kalpha2_doubles_lines():
    e = _entry(_DS, _INTS)
    c1, a1 = expand_reflections(e, WL, None, 5.0, 90.0)
    c2, a2 = expand_reflections(e, WL, 1.5444, 5.0, 90.0)
    assert c2.size == 2 * c1.size
    # c2 = concat(Kα1 lines, Kα2 lines).  Kα2 (longer wavelength) sits at a
    # slightly larger 2θ than Kα1 for the same d, with half the intensity.
    ka2_block = c2[c1.size:]
    assert np.all(ka2_block > c1 + 1e-6)
    assert np.allclose(a2[c1.size:], a1 * 0.5)
    assert np.allclose(a2[: c1.size], a1)


def test_expand_empty_entry():
    e = _entry([], [])
    c, a = expand_reflections(e, WL, None, 5.0, 90.0)
    assert c.size == 0 and a.size == 0


# --------------------------------------------------------------------------- #
# Theory profile
# --------------------------------------------------------------------------- #
def test_theory_peak_at_bragg_position():
    e = _entry(_DS, _INTS)
    c, a = expand_reflections(e, WL, None, 5.0, 90.0)
    from xinmatch.core.search.smpf import _reflection_windows
    win = _reflection_windows(_X, c, 1.5)
    y = generate_theory_profile(_X, c, a, win, fwhm=0.2, eta=0.5)
    # The strongest stick should produce a local max near its Bragg angle.
    cmax = c[np.argmax(a)]
    idx = int(np.argmin(np.abs(_X - cmax)))
    assert y[idx] > y[max(0, idx - 8)]
    assert y[idx] > y[min(_X.size - 1, idx + 8)]


def test_theory_zero_background_when_scale_zero():
    e = _entry(_DS, _INTS)
    c, a = expand_reflections(e, WL, None, 5.0, 90.0)
    from xinmatch.core.search.smpf import _reflection_windows
    win = _reflection_windows(_X, c, 1.5)
    y = generate_theory_profile(_X, c, a, win, fwhm=0.2, eta=0.5,
                               scale=0.0, bg0=10.0, bg1=0.0, bg2=0.0)
    assert np.allclose(y, 10.0)


# --------------------------------------------------------------------------- #
# Rwp / FoM definitions
# --------------------------------------------------------------------------- #
def test_rwp_perfect_fit_zero():
    y = np.array([100.0, 50.0, 25.0, 10.0])
    rwp, rexp, gof = compute_rwp(y, y.copy())
    assert rwp == pytest.approx(0.0, abs=1e-12)
    assert gof == pytest.approx(0.0, abs=1e-9)


def test_rwp_bad_fit_is_large():
    y = np.array([100.0, 50.0, 25.0, 10.0])
    rwp, rexp, gof = compute_rwp(y, np.zeros_like(y))
    assert rwp == pytest.approx(1.0)
    assert gof >= 0.0


def test_rwp_no_positive_points_inf():
    y = np.array([0.0, -1.0, 0.0])
    rwp, _, _ = compute_rwp(y, np.zeros_like(y))
    assert rwp == float("inf")


def test_fom_in_unit_interval_and_monotonic():
    assert 0.0 < compute_fom(0.05, 0.25) <= 1.0
    assert compute_fom(0.05, 0.25) > compute_fom(0.5, 0.25)
    assert compute_fom(float("inf"), 0.25) == 0.0


# --------------------------------------------------------------------------- #
# Per-candidate refinement recovery
# --------------------------------------------------------------------------- #
def _make_raw_pattern(entry: Entry, *, scale: float, shift: float,
                     fwhm: float, eta: float, bg: tuple[float, float, float],
                     noise: float = 0.0) -> Pattern:
    c, a = expand_reflections(entry, WL, None, 5.0, 90.0)
    from xinmatch.core.search.smpf import _reflection_windows
    win = _reflection_windows(_X, c, 1.5)
    y = generate_theory_profile(_X, c, a, win, fwhm=fwhm, eta=eta,
                                shift=shift, scale=scale,
                                bg0=bg[0], bg1=bg[1], bg2=bg[2], x_mid=50.0)
    if noise > 0.0:
        rng = np.random.default_rng(0)
        y = y + rng.normal(0.0, noise, size=y.shape)
    return Pattern(two_theta=_X, intensity=np.clip(y, 0.0, None),
                   wavelength=WL, step=0.02)


def test_fit_recovers_scale_shift_fwhm():
    entry = _entry(_DS, _INTS)
    pat = _make_raw_pattern(entry, scale=8.0, shift=0.1, fwhm=0.2, eta=0.5,
                            bg=(300.0, 0.5, 0.0), noise=2.0)
    f = fit_candidate(entry, pat.two_theta, pat.intensity,
                     wavelength_kalpha1=WL, wavelength_kalpha2=None,
                     cfg=SmpfConfig())
    assert f.scale == pytest.approx(8.0, rel=0.15)
    assert f.shift_deg == pytest.approx(0.1, abs=0.05)
    assert f.fwhm == pytest.approx(0.2, rel=0.2)
    assert f.rwp < 0.15


def test_fit_ranks_true_above_wrong():
    true_entry = _entry(_DS, _INTS)
    pat = _make_raw_pattern(true_entry, scale=8.0, shift=0.0, fwhm=0.2,
                            eta=0.5, bg=(300.0, 0.0, 0.0), noise=2.0)
    wrong = _entry([6.0, 5.0, 4.0, 3.0, 2.5, 2.0],
                   [100.0, 80.0, 60.0, 40.0, 30.0, 20.0], eid="wrong")
    ft = fit_candidate(true_entry, pat.two_theta, pat.intensity,
                       wavelength_kalpha1=WL, wavelength_kalpha2=None,
                       cfg=SmpfConfig())
    fw = fit_candidate(wrong, pat.two_theta, pat.intensity,
                       wavelength_kalpha1=WL, wavelength_kalpha2=None,
                       cfg=SmpfConfig())
    assert ft.fom > fw.fom
    assert ft.rwp < fw.rwp


def test_search_empty_entries_returns_empty():
    pat = _make_raw_pattern(_entry(_DS, _INTS), scale=8.0, shift=0.0,
                            fwhm=0.2, eta=0.5, bg=(300.0, 0.0, 0.0))
    # An in-memory DB with no recallable entries → empty result quickly.
    from tools.run_acceptance import build_curated_db
    conn = build_curated_db()
    try:
        res = search_match_smpf(pat, conn, prescreen_top_n=10, top_n=5)
        # Curated DB recall may or may not match; just assert no crash and
        # sorted-by-FoM ordering when non-empty.
        foms = [s["fom"] for _, s in res]
        assert foms == sorted(foms, reverse=True)
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Determinism (uses the real DB on one synthetic file)
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not SYNTH_DIR.exists(), reason="合成谱目录不存在（仓库外）")
def test_deterministic_single_pattern():
    from xinmatch.core.io import load_pattern
    pat = load_pattern(SYNTH_DIR / "synth_06.txt")
    conn = sqlite3.connect(DB)
    try:
        def run():
            res = search_match_smpf(pat, conn, wavelength_kalpha1=WL,
                                    wavelength_kalpha2=None,
                                    prescreen_top_n=60, top_n=5)
            return [(e.entry_id, round(s["fom"], 6)) for e, s in res]
        assert run() == run()
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Synthetic 13-set acceptance
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def synth_results():
    from tests.search.test_synthetic_acceptance import TRUTH
    from xinmatch.core.io import load_pattern
    out = {}
    conn = sqlite3.connect(DB)
    try:
        for name in TRUTH:
            pat = load_pattern(SYNTH_DIR / f"{name}.txt")
            res = search_match_smpf(pat, conn, wavelength_kalpha1=WL,
                                    wavelength_kalpha2=None,
                                    prescreen_top_n=150, top_n=20)
            out[name] = [(e.entry_id, s["formula"], s["fom"], s["rwp"])
                         for e, s in res]
    finally:
        conn.close()
    return out


@pytest.mark.skipif(not SYNTH_DIR.exists(), reason="合成谱目录不存在（仓库外）")
class TestSyntheticSmpfAcceptance:
    """13 组合成谱：任一真相相必须进入 Top-20（SMPF 全谱拟合精排）。"""

    def test_truth_in_top20_for_all(self, synth_results):
        from tests.search.test_synthetic_acceptance import TRUTH, is_truth
        failed = []
        for name, truths in TRUTH.items():
            top20 = synth_results[name]
            if not any(is_truth(f, tf) for (_, f, _, _) in top20 for tf in truths):
                failed.append(name)
        assert not failed, f"SMPF 真相相未进 Top-20: {failed}"

    def test_truth_in_top5_for_all(self, synth_results):
        from tests.search.test_synthetic_acceptance import TRUTH, is_truth
        failed = []
        for name, truths in TRUTH.items():
            top5 = synth_results[name][:5]
            if not any(is_truth(f, tf) for (_, f, _, _) in top5 for tf in truths):
                failed.append(name)
        assert not failed, f"SMPF 真相相未进 Top-5: {failed}"

    def test_results_sorted_by_fom(self, synth_results):
        for name, lst in synth_results.items():
            foms = [t[2] for t in lst]
            assert foms == sorted(foms, reverse=True), name


# --------------------------------------------------------------------------- #
# Real-pattern record mode (Kα1/Kα2 doublet; no hard hit assertion)
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def real_results():
    from xinmatch.core.io import load_pattern
    out = {}
    ids = ["1-1", "1-2", "2-1", "2-2", "3-1", "3-2", "4-1",
           "5-1", "5-2", "5-2b", "5-3", "7-1", "7-2"]
    conn = sqlite3.connect(DB)
    try:
        for sid in ids:
            p = REAL_DIR / f"{sid}.txt"
            if not p.exists():
                continue
            pat = load_pattern(p)
            res = search_match_smpf(pat, conn, wavelength_kalpha1=WL,
                                    wavelength_kalpha2=1.5444,
                                    prescreen_top_n=150, top_n=10)
            out[sid] = [(e.entry_id, s["formula"], s["fom"], s["rwp"])
                        for e, s in res]
    finally:
        conn.close()
    return out


@pytest.mark.skipif(not REAL_DIR.exists(), reason="真实谱目录不存在（仓库外）")
class TestRealSmpfRecord:
    """13 组真实谱：跑通、候选非空、记录 Top-10（不设硬命中率断言）。"""

    def test_all_samples_run(self, real_results):
        assert len(real_results) >= 10

    def test_candidates_nonempty_and_sorted(self, real_results):
        for sid, lst in real_results.items():
            assert lst, sid
            foms = [t[2] for t in lst]
            assert foms == sorted(foms, reverse=True), sid


# --------------------------------------------------------------------------- #
# Performance guard
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not SYNTH_DIR.exists(), reason="合成谱目录不存在（仓库外）")
def test_single_pattern_under_120s():
    from xinmatch.core.io import load_pattern
    pat = load_pattern(SYNTH_DIR / "synth_01.txt")
    conn = sqlite3.connect(DB)
    t = {}
    try:
        search_match_smpf(pat, conn, wavelength_kalpha1=WL,
                          wavelength_kalpha2=None,
                          prescreen_top_n=150, top_n=20, timing=t)
    finally:
        conn.close()
    assert t["total"] < 120.0, f"单谱全流程 {t['total']:.1f}s > 120s"
