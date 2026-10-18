"""v1.7.x：忙碌窗口的协作式取消。

长任务（FPFM 全谱拟合）此前没有任何中断手段：模态遮罩挡住主窗口，用户只能
等或强杀进程。现在「取消」按钮只置位标志，核心层在轮询点
(:func:`xinmatch.core.cancel.check_cancelled`) 抛
:class:`OperationCancelledError` 后正常退出——绝不强杀线程。

这里锁定三件事：
1. 取消标志 → ``check_cancelled`` 抛异常（核心层契约）；
2. 取消后 ``on_success`` / ``on_error`` 都不执行，状态栏显示「已取消」；
3. 重入被拒绝时 ``run_with_busy`` 返回 ``False``（调用方据此回收连接）。
"""

from __future__ import annotations

import time

from PySide6 import QtCore

from xinmatch.core.cancel import (
    OperationCancelledError,
    check_cancelled,
    set_cancel_check,
)
from xinmatch.ui import busy as busy_mod
from xinmatch.ui.busy import run_with_busy
from xinmatch.ui.main_window import MainWindow


# ---------------------------------------------------------------------------
# 1. 核心层契约
# ---------------------------------------------------------------------------
def test_cancel_flag_raises_and_clears():
    set_cancel_check(lambda: True)
    try:
        try:
            check_cancelled()
        except OperationCancelledError:
            pass
        else:  # pragma: no cover - 失败路径
            raise AssertionError("check_cancelled 未在取消时抛异常")
    finally:
        set_cancel_check(None)

    # 清理后恢复正常（不抛）。
    check_cancelled()


# ---------------------------------------------------------------------------
# 2. 忙碌窗口取消路径
# ---------------------------------------------------------------------------
def test_run_with_busy_cancel_skips_callbacks(qapp, monkeypatch):
    win = MainWindow()
    original_exec = busy_mod.BusyDialog.exec

    def _exec_and_cancel(self):  # noqa: ANN001 - Qt 槽签名
        # 打开对话框后 50 ms 触发「取消」，模拟用户点击。
        QtCore.QTimer.singleShot(50, self._on_cancel)
        return original_exec(self)

    monkeypatch.setattr(busy_mod.BusyDialog, "exec", _exec_and_cancel)

    def work():
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            time.sleep(0.01)
            check_cancelled()  # 用户在 50 ms 时置位 → 这里抛出
        return "finished-without-cancel"

    seen: list = []
    started = run_with_busy(
        win, "取消测试", "正在计算…", work,
        on_success=seen.append,
        on_error=seen.append,
    )

    assert started is True
    assert seen == [], "取消后不应再调用 on_success / on_error"
    assert "已取消" in win.statusBar().currentMessage()
    assert not win._busy_active, "忙碌标志必须复位"


# ---------------------------------------------------------------------------
# 3. 重入保护返回值
# ---------------------------------------------------------------------------
def test_run_with_busy_reentrancy_returns_false(qapp):
    win = MainWindow()
    win._busy_active = True
    try:
        assert run_with_busy(win, "t", "t", lambda: None) is False
    finally:
        win._busy_active = False
