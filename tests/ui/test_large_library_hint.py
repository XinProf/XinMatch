"""覆盖性大库 → 元素约束引导（基准报告 §23，2026-11-06）。

§23：COD-Full 532k 相与 COD-Inorg 78k 相峰数据完全同源，但大库里大量
有机 / 无关相稀释候选池，合成谱 Top-1 7/13 vs 11/13；给元素补集约束后
两库收敛到同一组数字 12/13·13/13·12/13·23/24。

这里固定四件事：
1. 大库判据是纯函数、按 ``entry_count``，读不到时保守不提示；
2. 工具栏在「大库 + 未设约束」时常显引导，已有约束就不再打扰；
3. 选库时给**非阻塞**状态栏提示（不弹模态框），文案带实测数字；
4. 配置里直接写了大库（没走对话框）时，打开检索也会同步；注册表损坏安全降级。
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

from xinmatch.ui import main_window as mw
from xinmatch.ui.main_window import (
    LARGE_LIBRARY_PHASE_THRESHOLD,
    MainWindow,
    is_large_library,
)

SAMPLE = "zn, O o F Al Ca"
BIG_ID = "xindb_cod_full"
SMALL_ID = "xindb_cod_inorg"


def _record(count: int | None, name: str = "COD-Full"):
    return SimpleNamespace(entry_count=count, display_name=name)


def test_is_large_library_threshold_is_a_pure_predicate():
    assert LARGE_LIBRARY_PHASE_THRESHOLD == 200_000
    assert is_large_library(_record(532_038))
    assert is_large_library(_record(LARGE_LIBRARY_PHASE_THRESHOLD))
    assert not is_large_library(_record(78_035))
    assert not is_large_library(_record(None))
    assert not is_large_library(None)
    assert not is_large_library(object())
    # 非整数（例如字符串）也不算，避免配置脏值时误提示
    assert not is_large_library(SimpleNamespace(entry_count="532038"))


def test_large_library_changes_toolbar_text(qapp, monkeypatch):
    monkeypatch.setattr(mw, "library_by_id", lambda _id: _record(532_038))
    win = MainWindow()
    assert win.sample_elements_action.text() == "样品元素：未设置"
    win._set_active_library_scale(BIG_ID)
    assert win._active_library_is_large is True
    assert win.sample_elements_action.text() == "样品元素：大库建议填写"


def test_small_library_keeps_the_plain_text(qapp, monkeypatch):
    monkeypatch.setattr(mw, "library_by_id", lambda _id: _record(78_035, "COD-Inorg"))
    win = MainWindow()
    win._set_active_library_scale(SMALL_ID)
    assert win._active_library_is_large is False
    assert win.sample_elements_action.text() == "样品元素：未设置"


def test_hint_yields_to_existing_constraints(qapp, monkeypatch):
    monkeypatch.setattr(mw, "library_by_id", lambda _id: _record(532_038))
    win = MainWindow()
    win._set_active_library_scale(BIG_ID)
    assert "大库建议填写" in win.sample_elements_action.text()
    win.periodic_panel.apply_detected_elements(SAMPLE)
    assert win.sample_elements_action.text().startswith("样品元素：仅")
    # 清掉约束后引导回来
    win.periodic_panel._clear_all()
    assert win.sample_elements_action.text() == "样品元素：大库建议填写"


def test_library_selection_shows_nonblocking_status_hint(qapp, monkeypatch):
    class FakeDialog:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return True

        def selected_id(self):
            return BIG_ID

    monkeypatch.setattr(mw, "LibraryDialog", FakeDialog)
    monkeypatch.setattr(mw, "library_by_id", lambda _id: _record(532_038, "COD-Full"))
    monkeypatch.setattr(mw, "load_config", lambda: {})
    monkeypatch.setattr(mw, "save_config", lambda _cfg: None)
    win = MainWindow()
    win._open_library_dialog()
    msg = win.statusBar().currentMessage()
    assert "已挂载大库" in msg
    assert "COD-Full" in msg
    assert "532,038" in msg
    assert "7/13 → 12/13" in msg
    assert win.sample_elements_action.text() == "样品元素：大库建议填写"


def test_no_status_hint_when_constraints_already_set(qapp, monkeypatch):
    class FakeDialog:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return True

        def selected_id(self):
            return BIG_ID

    monkeypatch.setattr(mw, "LibraryDialog", FakeDialog)
    monkeypatch.setattr(mw, "library_by_id", lambda _id: _record(532_038))
    monkeypatch.setattr(mw, "load_config", lambda: {})
    monkeypatch.setattr(mw, "save_config", lambda _cfg: None)
    win = MainWindow()
    win.periodic_panel.apply_detected_elements(SAMPLE)
    win.statusBar().clearMessage()
    win._open_library_dialog()
    assert "已挂载大库" not in win.statusBar().currentMessage()
    assert win._active_library_is_large is True


def test_open_search_library_syncs_a_big_library_from_config(qapp, monkeypatch):
    monkeypatch.setattr(
        mw, "load_config",
        lambda: {"reference_db": {"selected_library_id": BIG_ID}},
    )
    monkeypatch.setattr(mw, "library_by_id", lambda _id: _record(532_038))
    monkeypatch.setattr(mw, "open_library", lambda _id: object())
    win = MainWindow()
    conn = win.open_search_library()
    assert conn is not None
    assert win._active_library_id == BIG_ID
    assert win._active_library_is_large is True
    assert win.sample_elements_action.text() == "样品元素：大库建议填写"


def test_broken_registry_degrades_silently(qapp, monkeypatch):
    def boom(_id):
        raise RuntimeError("registry corrupted")

    monkeypatch.setattr(mw, "library_by_id", boom)
    win = MainWindow()
    win._set_active_library_scale("whatever")
    assert win._active_library_is_large is False
    assert win.sample_elements_action.text() == "样品元素：未设置"
