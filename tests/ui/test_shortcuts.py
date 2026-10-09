"""T13.6 — 快捷键映射：全量注册、无重复键序列、回调生效。"""

from __future__ import annotations

import pytest
from PySide6 import QtGui, QtWidgets

from xinmatch.ui.main_window import MODULES, MainWindow
from xinmatch.ui.shortcuts import SHORTCUTS, install_shortcuts


def test_all_entries_registered(qapp):
    win = QtWidgets.QMainWindow()
    registered = install_shortcuts(win)
    assert set(registered) == {e.name for e in SHORTCUTS}
    assert len(registered) == len(SHORTCUTS)


def test_every_module_id_is_known(qapp):
    known = {mod_id for mod_id, _, _ in MODULES}
    for entry in SHORTCUTS:
        assert entry.module_id == "" or entry.module_id in known, entry


def test_every_sequence_parses(qapp):
    for entry in SHORTCUTS:
        seq = QtGui.QKeySequence(entry.sequence)
        assert not seq.isEmpty(), f"{entry.name}: 无法解析键序列 {entry.sequence!r}"


def test_no_duplicate_key_sequences(qapp):
    seen: dict[str, str] = {}
    for entry in SHORTCUTS:
        key = QtGui.QKeySequence(entry.sequence).toString()
        assert key not in seen, f"键序列 {key} 重复: {seen[key]} 与 {entry.name}"
        seen[key] = entry.name


def test_injected_callbacks_fire(qapp):
    win = QtWidgets.QMainWindow()
    calls: list[str] = []
    registered = install_shortcuts(
        win,
        {
            "search_match": lambda: calls.append("search_match"),
            "delete_all_peaks": lambda: calls.append("delete_all_peaks"),
            "quit": lambda: calls.append("quit"),
        },
    )
    registered["search_match"].trigger()
    registered["delete_all_peaks"].trigger()
    registered["quit"].trigger()
    assert calls == ["search_match", "delete_all_peaks", "quit"]


def test_default_wiring_triggers_module_action(qapp):
    win = MainWindow()
    registered = install_shortcuts(win)
    # Ctrl+M → search_match 模块占位动作 → 状态栏提示
    registered["search_match"].trigger()
    assert "Search-Match" in win.statusBar().currentMessage()
    # Ctrl+F5 等 profile_fitting 条目同样联动
    registered["profile_fit"].trigger()
    assert "Profile Fitting" in win.statusBar().currentMessage()


def test_global_entry_without_callback_is_noop(qapp):
    win = QtWidgets.QMainWindow()
    registered = install_shortcuts(win)
    # module_id 为 "" 的全局条目默认无动作，触发不应报错
    registered["undo"].trigger()
    registered["previous_zoom"].trigger()


def test_unknown_callback_key_raises(qapp):
    win = QtWidgets.QMainWindow()
    with pytest.raises(KeyError):
        install_shortcuts(win, {"no_such_entry": lambda: None})
