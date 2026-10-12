"""SMPF Kα 双线模型 GUI 旋钮测试（v1.3.0）。

背景：粉末衍射的实验室 Cu 靶数据是 Kα1/Kα2 双线叠加（强度比 2:1），但
由 CIF 理论计算生成、或已做过 Kα2 剥离的合成谱是**单线**。SMPF 全谱拟合
若套用错误的双线模型，正确相的 Rwp 会被抬高而错排——已知案例：
``synth_13``（ZrO₂ 单线谱）在双线模型下 Top-1 错排成 YSZ
（Rwp 0.329 vs 单线 0.152）。

本模块覆盖 Kα1/Kα2 波长与双线开关经「设置→选项…→Search-Match」持久化、
并向 :func:`xinmatch.core.search.smpf.search_match_smpf` 正确传递的完整链路：

* 配置默认值与 OptionsDialog 行。
* :meth:`MainWindow.smpf_kalpha_wavelengths` 的四种取值组合。
* GUI 确实把 ``wavelength_kalpha1`` / ``wavelength_kalpha2`` 传下去。
* 回归（heavy）：``synth_13`` 在关闭 Kα2 后 Top-1 命中真相 ZrO₂。

非 heavy 用例不触碰参考数据库（offscreen 安全），可秒级完成。
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sqlite3  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

from tests.search.test_synthetic_acceptance import TRUTH, is_truth  # noqa: E402
from xinmatch.core.io import load_pattern  # noqa: E402
from xinmatch.ui.dialogs.config import DEFAULTS, default_config  # noqa: E402
from xinmatch.ui.dialogs.options_dialog import OptionsDialog  # noqa: E402
from xinmatch.ui.main_window import MainWindow  # noqa: E402

DB = Path(r"D:\Project\XRD\XinMatch\data\cod_inorganics.db")
SYNTH_DIR = Path(r"D:\Project\XRD\test_xrd\synthetic")

_HEAVY = pytest.mark.skipif(
    not SYNTH_DIR.exists() or not DB.exists(),
    reason="合成谱目录或默认库不存在（仓库外）",
)

_KA_KEYS = (
    "smpf_kalpha2_enabled",
    "smpf_kalpha1_angstrom",
    "smpf_kalpha2_angstrom",
)


def _cfg_with(**smpf_overrides):
    """构造带指定 SMPF 覆写的完整配置 dict。"""
    cfg = default_config()
    cfg["searchmatch"].update(smpf_overrides)
    return cfg


def _apply_cfg(monkeypatch, cfg) -> None:
    """把 MainWindow 读取配置的入口指向给定 dict（避免读写真实用户配置）。"""
    monkeypatch.setattr("xinmatch.ui.main_window.load_config", lambda: cfg)


def _patch_fast_smpf(monkeypatch) -> None:
    """把 GUI 调用的 SMPF 限制到 prescreen=60 / top_n=10 以缩短耗时。

    与 tests/ui/test_search_mode.py 同参数；真相相仍在精排集合内。
    """
    from xinmatch.core.search.smpf import search_match_smpf as real

    def _fast(pattern, conn, **kwargs):
        kwargs.setdefault("prescreen_top_n", 60)
        kwargs.setdefault("top_n", 10)
        return real(pattern, conn, **kwargs)

    monkeypatch.setattr("xinmatch.ui.main_window.search_match_smpf", _fast)


# ---------------------------------------------------------------------------
# 1. 配置默认值 / OptionsDialog 行
# ---------------------------------------------------------------------------
def test_default_config_has_smpf_kalpha_keys():
    """DEFAULTS 必须含三个 SMPF Kα 键，且默认值适合真实 Cu 双线数据。"""
    sm = DEFAULTS["searchmatch"]
    for key in _KA_KEYS:
        assert key in sm, f"缺少配置项 {key}"
    # 真实实验室 Cu Kα 数据恒为双线 → 默认开启。
    assert sm["smpf_kalpha2_enabled"] is True
    # Kα1 默认跟随图谱自身波长（0 = 自动）。
    assert sm["smpf_kalpha1_angstrom"] == 0.0
    # Cu Kα2 标称波长。
    assert sm["smpf_kalpha2_angstrom"] == pytest.approx(1.5444)


def test_options_dialog_roundtrips_kalpha_settings(qapp):
    """Search-Match 页的 Kα 三行能被写入并原样回收。"""
    cfg = _cfg_with(
        smpf_kalpha2_enabled=False,
        smpf_kalpha1_angstrom=1.7903,  # Co Kα1
        smpf_kalpha2_angstrom=1.7929,
    )
    dialog = OptionsDialog(cfg)
    got = dialog.values()["searchmatch"]
    assert got["smpf_kalpha2_enabled"] is False
    assert got["smpf_kalpha1_angstrom"] == pytest.approx(1.7903)
    assert got["smpf_kalpha2_angstrom"] == pytest.approx(1.7929)


# ---------------------------------------------------------------------------
# 2. smpf_kalpha_wavelengths 的取值组合
# ---------------------------------------------------------------------------
def test_kalpha_default_is_double_and_follows_pattern(qapp, monkeypatch):
    """默认（Kα1<=0）：Kα1 跟随图谱波长，Kα2 取默认 1.5444。"""
    _apply_cfg(monkeypatch, default_config())
    win = MainWindow()

    class _Pat:
        wavelength = 1.7903  # Co 靶，用于验证"跟随图谱"

    ka1, ka2 = win.smpf_kalpha_wavelengths(_Pat())
    assert ka1 == pytest.approx(1.7903)
    assert ka2 == pytest.approx(1.5444)


def test_kalpha_disabled_returns_none(qapp, monkeypatch):
    """关闭双线开关 → Kα2 为 None（单线模型）。"""
    _apply_cfg(monkeypatch, _cfg_with(smpf_kalpha2_enabled=False))
    win = MainWindow()
    ka1, ka2 = win.smpf_kalpha_wavelengths(None)
    assert ka2 is None
    # 无图谱时回退到 Cu Kα1 标称值，不产生 0 波长。
    assert ka1 == pytest.approx(1.5406)


def test_kalpha_explicit_wavelength_overrides_pattern(qapp, monkeypatch):
    """显式 Kα1 覆盖图谱自身波长（用于 Co / Mo 等非 Cu 靶手动指定）。"""
    _apply_cfg(
        monkeypatch,
        _cfg_with(smpf_kalpha1_angstrom=1.7903, smpf_kalpha2_angstrom=1.7929),
    )
    win = MainWindow()

    class _Pat:
        wavelength = 1.5406

    ka1, ka2 = win.smpf_kalpha_wavelengths(_Pat())
    assert ka1 == pytest.approx(1.7903)
    assert ka2 == pytest.approx(1.7929)


# ---------------------------------------------------------------------------
# 3. GUI → core 参数传递
# ---------------------------------------------------------------------------
def test_search_smpf_forwards_kalpha_to_core(qapp, monkeypatch):
    """_search_smpf 必须把解析出的波长传给 search_match_smpf。"""
    _apply_cfg(monkeypatch, _cfg_with(smpf_kalpha2_enabled=False))
    win = MainWindow()
    seen = {}
    calls = {"n": 0}

    def _fake(pattern, conn, **kwargs):
        seen.update(kwargs)
        calls["n"] += 1
        return []

    monkeypatch.setattr("xinmatch.ui.main_window.search_match_smpf", _fake)
    win._search_smpf(None, None)
    assert calls["n"] == 1
    assert seen["wavelength_kalpha1"] == pytest.approx(1.5406)
    assert seen["wavelength_kalpha2"] is None


def test_run_search_match_smpf_mode_label_shows_model(qapp, monkeypatch):
    """状态栏模式名应标注当前是单线还是双线，便于用户核对设置是否生效。"""
    pattern = load_pattern(SYNTH_DIR / "synth_06.txt") if SYNTH_DIR.exists() else None
    if pattern is None:
        pytest.skip("合成谱目录不存在")

    win = MainWindow()
    win.set_pattern(pattern)

    def _fake(pattern_, conn, **kwargs):
        return []

    monkeypatch.setattr("xinmatch.ui.main_window.search_match_smpf", _fake)

    _apply_cfg(monkeypatch, _cfg_with(smpf_kalpha2_enabled=False))
    _, label_single = win._search_smpf(pattern, None)
    assert "单线" in label_single

    _apply_cfg(monkeypatch, _cfg_with(smpf_kalpha2_enabled=True))
    _, label_double = win._search_smpf(pattern, None)
    assert "双线" in label_double


# ---------------------------------------------------------------------------
# 4. 回归（heavy）：synth_13 单线谱必须靠旋钮修正回来
# ---------------------------------------------------------------------------
@_HEAVY
def test_synth13_top1_hits_truth_when_kalpha2_disabled(qapp, monkeypatch):
    """synth_13（ZrO₂ 单线谱）关闭 Kα2 后 Top-1 命中真相。

    这是双线旋钮存在的核心理由：双线模型下该谱 Top-1 会错排成 YSZ
    （``O2 Y0.18 Zr0.82``，Rwp 0.329），而单线模型为 ``O2 Zr``（Rwp 0.152）。
    本用例锁定"关掉旋钮即可修复"这一行为；不断言双线必然错排
    （若未来算法改进使双线也正确，不应失败）。
    """
    _apply_cfg(monkeypatch, _cfg_with(smpf_kalpha2_enabled=False))
    _patch_fast_smpf(monkeypatch)
    win = MainWindow()
    win.set_pattern(load_pattern(SYNTH_DIR / "synth_13.txt"))
    conn = sqlite3.connect(DB)
    monkeypatch.setattr(win, "open_search_library", lambda: conn)
    try:
        results, label = win._search_smpf(win._current_pattern, conn)
        assert results, "SMPF 未返回任何候选"
        assert "单线" in label
        top1 = results[0].entry.formula
        truths = TRUTH["synth_13"]
        assert any(is_truth(top1, tf) for tf in truths), (
            f"synth_13 单线模型 Top-1 = {top1!r}，真相 = {truths}；"
            f"前 5：{[c.entry.formula for c in results[:5]]}"
        )
    finally:
        conn.close()
