"""覆盖性大库判据（GUI / CLI 共用阈值，基准报告 §23 / §27）。

阈值与谓词从 ``xinmatch.ui.main_window`` 下沉到 core，避免 CLI 为读一个常量
把 PySide6 拖进命令行进程。这里固定：阈值、边界、脏值保守降级，以及
``is_large_library`` 与整数版谓词语义完全一致。
"""

from __future__ import annotations

from types import SimpleNamespace

from xinmatch.core.db.library_scale import (
    LARGE_LIBRARY_PHASE_THRESHOLD,
    is_large_entry_count,
    is_large_library,
)


def test_threshold_value():
    assert LARGE_LIBRARY_PHASE_THRESHOLD == 200_000


def test_large_counts_trigger():
    assert is_large_entry_count(532_038)      # COD-Full
    assert is_large_entry_count(1_061_953)    # PCOD-Inorg
    assert is_large_entry_count(200_000)      # 边界含等号
    assert is_large_entry_count(200_001)


def test_small_counts_do_not_trigger():
    assert not is_large_entry_count(199_999)
    assert not is_large_entry_count(78_035)   # COD-Inorg（默认库）
    assert not is_large_entry_count(0)


def test_dirty_counts_degrade_silently():
    """引导提示宁可少给，也不能因为脏配置乱给。"""
    for value in (None, "532038", 532038.0, True, False, object(), []):
        assert not is_large_entry_count(value), value


def test_record_predicate_matches_integer_predicate():
    for count in (None, 0, 78_035, 199_999, 200_000, 532_038, "532038"):
        rec = SimpleNamespace(entry_count=count)
        assert is_large_library(rec) is is_large_entry_count(count), count
    assert not is_large_library(None)
    assert not is_large_library(object())
    assert not is_large_library(SimpleNamespace())  # 连 entry_count 都没有
