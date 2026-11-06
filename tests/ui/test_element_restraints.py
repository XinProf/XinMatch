"""「限制条件」面板 → 检索链：元素三态（必含 / 排除）必须真的生效。

背景：周期表面板能标红（排除）、能在摘要里显示「排除：Bi」，但从 1.x 到 3.4
**没有任何下游消费者** —— ``main_window._do_search`` 调 ``search_match`` 时根本
不传 ``restraints``，``Restraints`` 的 ``EXCLUDE`` 更是全仓零引用。于是
「样品里没有 Bi」（XRF/EDS 已确认）这条化学上最硬的先验进不了召回，
基准报告 §11.5 的 ``3-2`` ``Bi-Y-O`` 假卡只能靠肉眼剔。

这里固定三件事：

1. 面板状态能正确映射成 :class:`Restraints`（空选择 / 关闭开关 → ``None``）；
2. 峰列表 FoM 模式下 ``restraints`` 一路传到 ``search_match``；
3. FPFM 模式下**不传**且明确提示 —— 它的检索链没有 restraints 形参，
   静默忽略会让用户以为红色元素生效了。
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from xinmatch.core.model import ElementState, Pattern, Restraints
from xinmatch.ui.main_window import SEARCH_MODE_FPFM_FULL, SEARCH_MODE_PEAKS_FOM, MainWindow


def _pattern() -> Pattern:
    """两个高斯峰，够 ``find_peaks`` 找出两条线（不依赖任何数据文件）。"""
    two_theta = np.linspace(10.0, 60.0, 2001)
    intensity = (
        1000.0 * np.exp(-((two_theta - 26.6) ** 2) / (2 * 0.05 ** 2))
        + 400.0 * np.exp(-((two_theta - 39.5) ** 2) / (2 * 0.05 ** 2))
        + 5.0
    )
    return Pattern(two_theta=two_theta, intensity=intensity, wavelength=1.5406)


class _FakeConn:
    """``_do_search`` 只要求一个能 ``close()`` 的对象。"""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_empty_panel_maps_to_no_restraints(qapp):
    win = MainWindow()
    assert win.periodic_panel.states() == {}
    assert win._current_restraints() is None


def test_disabled_panel_maps_to_no_restraints(qapp):
    win = MainWindow()
    win.periodic_panel.set_states({"Bi": ElementState.EXCLUDE})
    win.periodic_panel.set_enabled(False)
    assert win._current_restraints() is None


def test_panel_states_become_three_state_restraints(qapp):
    win = MainWindow()
    win.periodic_panel.set_states({
        "O": ElementState.REQUIRED,
        "Bi": ElementState.EXCLUDE,
        "Ca": ElementState.OPTIONAL,
    })
    r = win._current_restraints()
    assert isinstance(r, Restraints)
    # 面板只回报非默认态（黄色 OPTIONAL 就是默认，不会出现在 states() 里）——
    # 语义上正好：黄色本来就不参与过滤。
    assert r.elements == {
        "O": ElementState.REQUIRED,
        "Bi": ElementState.EXCLUDE,
    }


def test_peak_list_search_forwards_restraints(qapp, monkeypatch):
    """峰列表 FoM：restraints 必须出现在 ``search_match`` 的实参里。"""
    import xinmatch.ui.main_window as mw

    seen: dict = {}

    def _fake_search(peaks, conn, wavelength, **kwargs):
        seen["kwargs"] = kwargs
        seen["n_peaks"] = len(peaks)
        return []

    monkeypatch.setattr(mw, "search_match", _fake_search)

    win = MainWindow()
    win.periodic_panel.set_states({"Bi": ElementState.EXCLUDE})
    restraints = win._current_restraints()
    assert restraints is not None

    conn = _FakeConn()
    results, label, peaks = win._do_search(
        _pattern(), conn, SEARCH_MODE_PEAKS_FOM, restraints
    )

    assert results == [] and label == "峰列表 FoM"
    assert seen["kwargs"]["restraints"] is restraints
    assert seen["n_peaks"] > 0
    assert conn.closed is True


def test_fpfm_search_does_not_get_restraints(qapp, monkeypatch):
    """FPFM 检索链没有 restraints 形参 —— 不能半路塞进去，也不能假装生效。"""
    import xinmatch.ui.main_window as mw

    monkeypatch.setattr(
        MainWindow, "_search_fpfm",
        lambda self, pattern, conn: ([], "FPFM"),
    )

    win = MainWindow()
    win.periodic_panel.set_states({"Bi": ElementState.EXCLUDE})
    restraints = win._current_restraints()

    conn = _FakeConn()
    results, label, peaks = win._do_search(
        _pattern(), conn, SEARCH_MODE_FPFM_FULL, restraints
    )
    assert results == [] and label == "FPFM"
    assert peaks is None          # FPFM 不寻峰，不覆盖峰列表
    assert conn.closed is True


def test_status_bar_warns_when_restraints_meet_fpfm(qapp, monkeypatch):
    """选了元素又切到 FPFM 时必须给出可见提示，而不是静默不生效。"""
    import xinmatch.ui.main_window as mw

    win = MainWindow()
    win.periodic_panel.set_states({"Bi": ElementState.EXCLUDE})
    win._current_pattern = _pattern()
    win._search_mode = SEARCH_MODE_FPFM_FULL

    monkeypatch.setattr(win, "open_search_library", lambda: _FakeConn())
    monkeypatch.setattr(mw, "run_with_busy",
                        lambda *a, **k: True)  # 不真的起线程

    win._run_search_match()
    assert "元素限制条件不参与" in win.statusBar().currentMessage()
