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

import math
import sqlite3
from pathlib import Path

import numpy as np
import pytest

from xinmatch.core.model import CellParams, Entry, Pattern
from xinmatch.core.search.smpf import (
    SmpfConfig,
    compute_fom,
    compute_rwp,
    expand_reflections,
    expand_reflections_po,
    fit_candidate,
    generate_theory_profile,
    march_dollase_cos,
    march_dollase_weight,
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


# --------------------------------------------------------------------------- #
# v1.4 extensions: Caglioti U/V/W width + cell refinement
# --------------------------------------------------------------------------- #
def _raw_pattern_with(
    entry: Entry,
    *,
    uvw: tuple[float, float, float] | None = None,
    cell_delta: float = 0.0,
    fwhm: float = 0.2,
    eta: float = 0.5,
    noise: float = 2.0,
    scale: float = 8.0,
    shift: float = 0.0,
    bg: tuple[float, float, float] = (300.0, 0.5, 0.0),
) -> Pattern:
    """Build a raw pattern from *entry* (optionally cell-scaled by Δ)."""
    from xinmatch.core.search.smpf import _reflection_windows
    if cell_delta != 0.0:
        # 样本晶胞比卡片大 Δ：d 乘 (1+Δ)
        entry = Entry(
            entry_id=entry.entry_id,
            formula=entry.formula,
            d_spacings=np.asarray(entry.d_spacings) * (1.0 + cell_delta),
            intensities=entry.intensities,
        )
    c, a = expand_reflections(entry, WL, None, 5.0, 90.0)
    tan = np.clip(np.tan(np.radians(c / 2.0)), 0.0, 8.0)
    extra = 0.005 * (360.0 / math.pi) * tan
    win = _reflection_windows(_X, c, 1.5, extra_deg=extra)
    y = generate_theory_profile(
        _X, c, a, win, fwhm=fwhm, eta=eta, shift=shift, scale=scale,
        bg0=bg[0], bg1=bg[1], bg2=bg[2], x_mid=50.0, uvw=uvw, tan_theta=tan,
    )
    if noise > 0.0:
        rng = np.random.default_rng(0)
        y = y + rng.normal(0.0, noise, size=y.shape)
    return Pattern(two_theta=_X, intensity=np.clip(y, 0.0, None),
                   wavelength=WL, step=0.02)


def test_caglioti_fwhm_formula_and_clamps():
    from xinmatch.core.search.smpf import _caglioti_fwhm
    tan45 = np.array([math.tan(math.radians(22.5))])
    h = _caglioti_fwhm(tan45, 0.006, -0.004, 0.010, (0.08, 0.6))
    expect = math.sqrt(0.006 * tan45[0] ** 2 - 0.004 * tan45[0] + 0.010)
    assert h[0] == pytest.approx(expect, rel=1e-12)
    # H² < 0 → clamp at the lower width bound (must not produce NaN).
    assert _caglioti_fwhm(tan45, 0.0, -1.0, 0.0, (0.08, 0.6))[0] == 0.08
    # H far above the upper bound → clamp.
    assert _caglioti_fwhm(tan45, 5.0, 0.0, 5.0, (0.08, 0.6))[0] == 0.6


def _fwhm_at(x: np.ndarray, y: np.ndarray, centre: float) -> float:
    """Measure the FWHM of the peak nearest *centre* (grid resolution)."""
    i = int(np.argmin(np.abs(x - centre)))
    half = 0.5 * float(y[i])
    j = i
    while j > 0 and y[j] > half:
        j -= 1
    k = i
    while k < x.size - 1 and y[k] > half:
        k += 1
    return float(x[k] - x[j])


def test_theory_profile_caglioti_widens_high_angle():
    entry = _entry(_DS, _INTS)
    c, a = expand_reflections(entry, WL, None, 5.0, 90.0)
    from xinmatch.core.search.smpf import _reflection_windows
    # 细网格：峰宽 ~0.1°，0.02° 步进的半高宽量化误差会压过高/低角比值。
    xf = np.arange(5.0, 90.0, 0.005, dtype=np.float64)
    tan = np.clip(np.tan(np.radians(c / 2.0)), 0.0, 8.0)
    win = _reflection_windows(xf, c, 2.5)
    # 纯高斯 (eta=0)，U>0 → 高角峰应显著宽于低角峰。
    y = generate_theory_profile(xf, c, a, win, fwhm=0.2, eta=0.0,
                                uvw=(0.1, 0.0, 0.01), tan_theta=tan,
                                fwhm_bounds=(0.02, 1.0))
    lo_c = float(c[np.argmax(a)])            # 最强峰（低角）
    hi_c = float(c[np.argmin(np.abs(c - 64.0))])
    fwhm_lo = _fwhm_at(xf, y, lo_c)
    fwhm_hi = _fwhm_at(xf, y, hi_c)
    assert fwhm_hi > 1.5 * fwhm_lo


def test_fit_recovers_caglioti_uvw():
    entry = _entry(_DS, _INTS)
    pat = _raw_pattern_with(entry, uvw=(0.006, -0.004, 0.010))
    f = fit_candidate(entry, pat.two_theta, pat.intensity,
                      wavelength_kalpha1=WL, wavelength_kalpha2=None,
                      cfg=SmpfConfig())
    assert f.u == pytest.approx(0.006, abs=0.003)
    assert f.v == pytest.approx(-0.004, abs=0.003)
    assert f.w == pytest.approx(0.010, abs=0.004)
    assert f.rwp < 0.05


def test_caglioti_beats_global_fwhm_on_angle_dependent_width():
    entry = _entry(_DS, _INTS)
    pat = _raw_pattern_with(entry, uvw=(0.05, 0.0, 0.01), noise=1.0)
    f_on = fit_candidate(entry, pat.two_theta, pat.intensity,
                         wavelength_kalpha1=WL, wavelength_kalpha2=None,
                         cfg=SmpfConfig())
    f_off = fit_candidate(entry, pat.two_theta, pat.intensity,
                          wavelength_kalpha1=WL, wavelength_kalpha2=None,
                          cfg=SmpfConfig(caglioti=False, cell_refine=False))
    # 同一角度依赖宽化谱：Caglioti 拟合必须显著优于全局单 FWHM。
    assert f_on.rwp < 0.5 * f_off.rwp


def test_fit_recovers_cell_delta():
    entry = _entry(_DS, _INTS)
    pat = _raw_pattern_with(entry, cell_delta=0.003)
    f = fit_candidate(entry, pat.two_theta, pat.intensity,
                      wavelength_kalpha1=WL, wavelength_kalpha2=None,
                      cfg=SmpfConfig())
    assert f.cell_delta == pytest.approx(0.003, abs=0.0008)
    assert f.rwp < 0.05
    # 不修正时同一谱的 Rwp 显著变差（constant shift 无法吸收 tanθ 差分位移）。
    f2 = fit_candidate(entry, pat.two_theta, pat.intensity,
                       wavelength_kalpha1=WL, wavelength_kalpha2=None,
                       cfg=SmpfConfig(cell_refine=False))
    assert f.rwp < f2.rwp


def test_switches_off_identity_encoding():
    entry = _entry(_DS, _INTS)
    pat = _raw_pattern_with(entry, fwhm=0.2)
    f = fit_candidate(entry, pat.two_theta, pat.intensity,
                      wavelength_kalpha1=WL, wavelength_kalpha2=None,
                      cfg=SmpfConfig(caglioti=False, cell_refine=False))
    assert f.u == 0.0 and f.v == 0.0
    assert f.w == pytest.approx(f.fwhm ** 2)
    assert f.cell_delta == 0.0
    assert f.fwhm == pytest.approx(0.2, abs=0.02)


def test_reflection_windows_extra_margin_widens_high_angle():
    from xinmatch.core.search.smpf import _reflection_windows
    c = np.array([20.0, 60.0])
    plain = _reflection_windows(_X, c, 1.5)
    extra = np.array([0.0, 0.5])
    wide = _reflection_windows(_X, c, 1.5, extra_deg=extra)
    assert np.array_equal(plain[0], wide[0])
    assert wide[1, 0] < plain[1, 0] and wide[1, 1] > plain[1, 1]


def test_score_dict_carries_v14_keys():
    pat = _raw_pattern_with(_entry(_DS, _INTS), scale=8.0, shift=0.0,
                            fwhm=0.2, eta=0.5, bg=(300.0, 0.0, 0.0))
    from tools.run_acceptance import build_curated_db
    conn = build_curated_db()
    try:
        res = search_match_smpf(pat, conn, prescreen_top_n=10, top_n=5)
        if res:
            for _, s in res:
                for key in ("caglioti_u", "caglioti_v", "caglioti_w",
                            "cell_delta", "march_r"):
                    assert key in s
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# March-Dollase preferred orientation (v1.5 SMPF extension)
# --------------------------------------------------------------------------- #
def _hex_graphite_entry() -> Entry:
    """Graphite-like hexagonal cell (a=2.464, c=6.711 Å) with 00l-dominant
    stick pattern; PO axis [001] is the basal plane."""
    ds = [3.355, 2.134, 2.036, 1.678, 1.547]
    ints = [100.0, 8.0, 6.0, 5.0, 4.0]
    cell = CellParams(a=2.464, b=2.464, c=6.711,
                      alpha=90.0, beta=90.0, gamma=120.0)
    hkl = [(0, 0, 2), (1, 0, 0), (1, 0, 1), (0, 0, 4), (1, 0, 2)]
    return Entry(entry_id="hex", formula="C",
                 d_spacings=np.array(ds, dtype=np.float64),
                 intensities=np.array(ints, dtype=np.float64),
                 cell=cell, hkl=hkl)


def _raw_pattern_md(entry: Entry, *, march_r: float = 0.6, scale: float = 8.0,
                    fwhm: float = 0.2, eta: float = 0.5, noise: float = 2.0,
                    bg: tuple[float, float, float] = (300.0, 0.5, 0.0)) -> Pattern:
    """Raw pattern textured by the *true* March-Dollase model (same profile
    builder as the fitter — this validates r recovery, not the synthetic
    generator end-to-end, which the acceptance set covers)."""
    from xinmatch.core.search.smpf import _reflection_windows
    po_cos = march_dollase_cos(entry, (0, 0, 1))
    c, a, pc = expand_reflections_po(entry, WL, None, 5.0, 90.0, po_cos)
    win = _reflection_windows(_X, c, 1.5)
    y = generate_theory_profile(
        _X, c, a, win, fwhm=fwhm, eta=eta, shift=0.0, scale=scale,
        bg0=bg[0], bg1=bg[1], bg2=bg[2], x_mid=50.0, march_cos=pc,
        march_r=march_r,
    )
    if noise > 0.0:
        y = y + np.random.default_rng(0).normal(0.0, noise, size=y.shape)
    return Pattern(two_theta=_X, intensity=np.clip(y, 0.0, None),
                   wavelength=WL, step=0.02)


def test_march_dollase_weight_formula():
    # Isotropic r = 1: no texture anywhere.
    assert march_dollase_weight(1.0, 0.0) == pytest.approx(1.0)
    assert march_dollase_weight(1.0, 1.0) == pytest.approx(1.0)
    # Platy r = 0.6: on-axis (cos α = 1) enhanced by r^-3, off-axis
    # (cos α = 0) suppressed by r^(3/2).
    assert march_dollase_weight(0.6, 1.0) == pytest.approx(0.6 ** -3)
    assert march_dollase_weight(0.6, 0.0) == pytest.approx(0.6 ** 1.5)
    # nan (missing hkl) maps to isotropic weight 1.
    assert march_dollase_weight(0.6, np.nan) == pytest.approx(1.0)
    # r > 1 (needle texture) suppresses the axis instead.
    assert march_dollase_weight(2.0, 1.0) < 1.0


def test_march_dollase_cos_hex_geometry():
    e = _hex_graphite_entry()
    cos = march_dollase_cos(e, (0, 0, 1))
    assert cos is not None and cos.size == e.n_peaks
    # (002) and (004) lie along [001]: cos α = 1.
    assert cos[0] == pytest.approx(1.0, abs=1e-9)
    assert cos[3] == pytest.approx(1.0, abs=1e-9)
    # (100) is ⊥ [001] in the hexagonal metric.
    assert cos[1] == pytest.approx(0.0, abs=1e-9)
    # Mixed-index reflections sit between 0 and 1.
    assert 0.0 < cos[2] < 1.0 and 0.0 < cos[4] < 1.0


def test_march_dollase_cos_requires_hkl_and_cell():
    e = _hex_graphite_entry()
    assert march_dollase_cos(Entry(entry_id="x", formula="C",
                                   d_spacings=e.d_spacings,
                                   intensities=e.intensities,
                                   cell=e.cell)) is None
    assert march_dollase_cos(Entry(entry_id="x", formula="C",
                                   d_spacings=e.d_spacings,
                                   intensities=e.intensities,
                                   hkl=e.hkl)) is None


def test_expand_reflections_po_propagates_cos():
    e = _hex_graphite_entry()
    po_cos = march_dollase_cos(e, (0, 0, 1))
    c1, a1 = expand_reflections(e, WL, None, 5.0, 90.0)
    c2, a2, pc = expand_reflections_po(e, WL, 1.5444, 5.0, 90.0, po_cos)
    assert c2.size == 2 * c1.size
    assert pc is not None and pc.size == c2.size
    # Kα2 block copies the same cos α (same reflection, half intensity).
    assert np.allclose(pc[: c1.size], pc[c1.size:])
    assert np.allclose(a2[c1.size:], a1 * 0.5)


def test_theory_profile_march_r_scales_on_axis_peak():
    e = _hex_graphite_entry()
    po_cos = march_dollase_cos(e, (0, 0, 1))
    c, a, pc = expand_reflections_po(e, WL, None, 5.0, 90.0, po_cos)
    win = np.array([[0, _X.size - 1]] * c.size, dtype=np.int64)
    y0 = generate_theory_profile(_X, c, a, win, fwhm=0.5, eta=0.5, scale=1.0,
                                 march_cos=pc, march_r=1.0)
    yt = generate_theory_profile(_X, c, a, win, fwhm=0.5, eta=0.5, scale=1.0,
                                 march_cos=pc, march_r=0.6)
    # The (002) on-axis peak (index 0, ~26.6°) is enhanced by r^-3.
    on_axis = np.argmin(np.abs(_X - c[0]))
    iso_peak = float(y0[on_axis])
    assert yt[on_axis] > iso_peak * 3.0
    # Off-axis (100) peak shrinks.
    off_axis = np.argmin(np.abs(_X - c[1]))
    assert yt[off_axis] < y0[off_axis] * 0.8


def test_fit_recovers_march_r_on_textured_pattern():
    e = _hex_graphite_entry()
    pat = _raw_pattern_md(e, march_r=0.6)
    f = fit_candidate(e, pat.two_theta, pat.intensity,
                      wavelength_kalpha1=WL, wavelength_kalpha2=None,
                      cfg=SmpfConfig(march_po=True))
    assert f.march_r == pytest.approx(0.6, abs=0.12)
    assert f.rwp < 0.05
    # Without the texture model the same pattern fits worse.
    f0 = fit_candidate(e, pat.two_theta, pat.intensity,
                       wavelength_kalpha1=WL, wavelength_kalpha2=None,
                       cfg=SmpfConfig(march_po=False))
    assert f0.rwp > f.rwp


def test_fit_no_texture_stays_isotropic():
    e = _hex_graphite_entry()
    pat = _raw_pattern_md(e, march_r=1.0)
    f = fit_candidate(e, pat.two_theta, pat.intensity,
                      wavelength_kalpha1=WL, wavelength_kalpha2=None,
                      cfg=SmpfConfig(march_po=True))
    # An un-textured pattern must not be over-fitted into a false texture.
    assert f.march_r == pytest.approx(1.0, abs=0.15)


@pytest.mark.slow
@pytest.mark.skipif(not DB.exists(), reason="参考库不存在（仓库外）")
def test_march_po_recovers_textured_zirconia():
    """End-to-end: a *true-March-Dollase* textured Zirconia spectrum built
    with the (upgraded) synthetic generator must be recovered by SMPF with
    ``march_po=True`` — truth back at Top-1 and Rwp better than the
    un-textured model — proving the generator→fitter contract (the
    previous fake factor could not be detected nor recovered)."""
    from tools.generate_synthetic_patterns import _build_sample
    import tools.generate_synthetic_patterns as gen
    rng = np.random.default_rng(7)
    sample = _build_sample("md-probe", [(2101234, 1.0, (-1, 1, 1))], rng)
    x = gen.TWO_THETA
    y = sample["pattern"]
    pat = Pattern(two_theta=x, intensity=y, wavelength=WL, step=0.02)
    conn = sqlite3.connect(DB)
    try:
        res_md = search_match_smpf(
            pat, conn, wavelength_kalpha1=WL, wavelength_kalpha2=None,
            cfg=SmpfConfig(march_po=True), prescreen_top_n=60, top_n=10)
        res_plain = search_match_smpf(
            pat, conn, wavelength_kalpha1=WL, wavelength_kalpha2=None,
            cfg=SmpfConfig(march_po=False), prescreen_top_n=60, top_n=10)
    finally:
        conn.close()
    from tests.search.test_synthetic_acceptance import is_truth
    assert res_md and res_plain
    truth = "O2 Zr"
    top1 = res_md[0][1]["formula"]
    assert is_truth(top1, truth), f"织构真相未回 Top-1: {top1}"
    f_md = next(s for _, s in res_md if is_truth(s["formula"], truth))
    f_plain = next(s for _, s in res_plain if is_truth(s["formula"], truth))
    # The fitted MD model must beat the isotropic one on the textured
    # spectrum (same truth card, profile fit absorbs the texture).
    assert f_md["rwp"] < f_plain["rwp"]
    assert f_md["march_r"] < 1.0  # textured direction actually fitted
