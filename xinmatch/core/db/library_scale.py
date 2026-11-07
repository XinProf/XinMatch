"""「覆盖性大库」判据（GUI / CLI 共用，**零 PySide6 依赖**）。

基准报告 §23：COD-Full 532k 相与 COD-Inorg 78k 相的峰数据完全同源，但大库里
大量有机 / 无关相会稀释候选池（合成谱 Top-1 7/13 vs 11/13）；给足元素约束后
两库收敛到完全相同的四个数字 12/13 · 13/13 · 12/13 · 23/24。所以挂大库时
值得提醒用户先填样品元素，但只能**非阻塞地提醒** —— 不弹窗、不强制、不改默认值。

阈值与谓词原本写在 ``xinmatch.ui.main_window``。CLI 若直接 import 会把 PySide6
拖进命令行进程，所以下沉到 core：GUI 继续 re-export 同名接口（既有 import 不破），
CLI 用 :func:`is_large_entry_count` 直接判整数。两边永远只有一个阈值。
"""

from __future__ import annotations

#: 相数阈值：COD-Full 532k / PCOD-Inorg 1.06M 属覆盖性大库；
#: 精选无机库 COD-Inorg 78k 不触发。
LARGE_LIBRARY_PHASE_THRESHOLD = 200_000


def is_large_entry_count(count: object | None) -> bool:
    """按相数判断是否为「覆盖性大库」。

    读不到 / 类型不对（字符串、``None``、bool）时保守返回 ``False``，
    不打扰用户 —— 引导提示宁可少给，也不能因为脏配置乱给。
    """
    return (
        isinstance(count, int)
        and not isinstance(count, bool)
        and count >= LARGE_LIBRARY_PHASE_THRESHOLD
    )


def is_large_library(record: object | None) -> bool:
    """按 ``LibraryRecord.entry_count`` 判断（GUI 侧入口）。"""
    return is_large_entry_count(getattr(record, "entry_count", None))


__all__ = [
    "LARGE_LIBRARY_PHASE_THRESHOLD",
    "is_large_entry_count",
    "is_large_library",
]
