"""耗时操作的忙碌进度窗口（v1.3.1）。

问题背景
--------
Search-Match / FPFM 全谱拟合等操作耗时数秒到数十秒，此前在 GUI 线程内
同步执行：界面完全冻结，用户以为程序没反应而反复点击，事件排队后
连续触发多次检索，表现为"程序卡死"。

方案
----
:func:`run_with_busy` 把工作函数放进 **QThread** 执行，同时弹出一个
**应用级模态**的忙碌对话框（不定进度条走马灯 + 说明文字）：

* 主线程事件循环保持活跃 → 走马灯动画流畅、界面不冻结；
* 模态遮罩挡住主窗口 → 用户点不到任何按钮，物理上不可重复触发；
* 工作完成后对话框自动关闭，结果回调在 GUI 线程执行（可安全更新
  界面 / 弹框）；异常统一捕获后转交 ``on_error`` 回调。
* v1.7.x：长任务（FPFM 全谱拟合）支持**协作式取消**。点击「取消」只置位
  取消标志并提示「正在取消…」，工作线程在下一个轮询点（核心层
  :mod:`xinmatch.core.cancel`）抛出 ``OperationCancelled`` 后退出——绝不
  强杀线程（会破坏 NumPy / SQLite / 半写文件状态）。

用法
----
::

    run_with_busy(
        self, "Search-Match", "正在检索参考数据库…",
        lambda: search_match(peaks, conn, wl),          # 工作线程内执行
        on_success=self._apply_results,                  # GUI 线程回调
        on_error=self._show_search_error,                # GUI 线程回调
    )

注意：``work`` 内部**不得**触碰任何 QWidget / QMessageBox——它运行在
工作线程；一切界面交互放在 ``on_success`` / ``on_error`` 里。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from PySide6 import QtCore, QtWidgets

from xinmatch.core.cancel import OperationCancelledError, set_cancel_check

logger = logging.getLogger(__name__)

__all__ = ["BusyDialog", "run_with_busy"]

#: 取消按钮延迟启用（秒）——短任务不闪一下按钮，长任务用户仍能及时取消。
_CANCEL_ENABLE_DELAY_MS = 1200


class BusyDialog(QtWidgets.QDialog):
    """不定进度（走马灯）忙碌对话框。

    * 无关闭按钮、ESC 无效——用户不能中途关掉，也不该中途关掉
      （工作线程还在跑）；工作结束时由 :func:`run_with_busy` 调
      :meth:`accept` 关闭。
    * ``QProgressBar(range(0, 0))`` 在 Windows / Fusion 样式下显示为
      不定进度走马灯。
    * :meth:`receive_result` / :meth:`receive_error` 是工作线程信号的
      **排队槽**（receiver 是本对话框 → GUI 线程执行）——跨线程关闭
      对话框必须经此路由，直接把闭包 connect 到工作线程信号会变成
      DirectConnection 在 worker 线程里调 QWidget 方法（挂死）。
    """

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        title: str,
        text: str,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        # 去掉关闭按钮（保留标题栏以显示标题）。
        self.setWindowFlag(QtCore.Qt.WindowType.WindowCloseButtonHint, False)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setModal(True)
        self.setMinimumWidth(360)

        self.result_value: Any = None
        self.error_message: str | None = None
        #: 用户是否点了「取消」（工作线程轮询此标志）。
        self.cancel_requested = False
        #: 工作线程是否因取消而退出（由 receive_cancel 置位）。
        self.was_cancelled = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        self._label = QtWidgets.QLabel(text)
        self._label.setWordWrap(True)
        layout.addWidget(self._label)

        bar = QtWidgets.QProgressBar()
        bar.setRange(0, 0)  # 0..0 = 不定进度（走马灯）
        bar.setTextVisible(False)
        bar.setFixedHeight(14)
        layout.addWidget(bar)

        note = QtWidgets.QLabel("处理完成后本窗口自动关闭，请稍候…")
        note.setObjectName("busyNote")
        layout.addWidget(note)

        # 取消按钮：底部右对齐，延迟启用避免短任务闪烁。
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        self._cancel_btn = QtWidgets.QPushButton("取消")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._on_cancel)
        buttons.addWidget(self._cancel_btn)
        layout.addLayout(buttons)
        QtCore.QTimer.singleShot(_CANCEL_ENABLE_DELAY_MS, self._enable_cancel)

    def _enable_cancel(self) -> None:
        # 短任务可能在定时器触发前就结束并 ``deleteLater`` 了对话框；
        # 此时底层 C++ 对象已释放，访问控件会抛 RuntimeError，直接忽略。
        try:
            if not self.cancel_requested:
                self._cancel_btn.setEnabled(True)
        except RuntimeError:  # pragma: no cover - C++ object already deleted
            pass

    def _on_cancel(self) -> None:
        """请求取消：置位标志 + 提示等待，不强杀线程。"""
        self.cancel_requested = True
        self._cancel_btn.setEnabled(False)
        self._label.setText("正在取消，等待当前计算单元结束…")

    # 以下三个槽由 _Worker 的信号（跨线程）触发；receiver=本对话框，
    # Qt 自动走 QueuedConnection，在 GUI 线程执行。
    def receive_result(self, value: Any) -> None:
        self.result_value = value
        self.accept()

    def receive_error(self, message: str) -> None:
        self.error_message = message
        self.accept()

    def receive_cancel(self) -> None:
        self.was_cancelled = True
        self.accept()

    def reject(self) -> None:  # noqa: D102 — 吞掉 ESC，防止中途关闭
        pass


class _Worker(QtCore.QThread):
    """在独立线程执行 ``work``，结果/异常/取消经信号回 GUI 线程。"""

    finished_ok = QtCore.Signal(object)
    failed = QtCore.Signal(str)
    cancelled = QtCore.Signal()

    def __init__(
        self,
        work: Callable[[], Any],
        is_cancelled: Callable[[], bool] = lambda: False,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._work = work
        self._is_cancelled = is_cancelled

    def run(self) -> None:  # noqa: D102
        # 把取消谓词装到**本线程**的 thread-local 上；核心层的长循环通过
        # ``xinmatch.core.cancel.check_cancelled()`` 轮询，据此协作式退出。
        set_cancel_check(self._is_cancelled)
        try:
            self.finished_ok.emit(self._work())
        except OperationCancelledError:
            self.cancelled.emit()
        except Exception as exc:  # noqa: BLE001 — 异常统一转字符串回 GUI 线程
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            set_cancel_check(None)


def run_with_busy(
    parent: QtWidgets.QWidget,
    title: str,
    text: str,
    work: Callable[[], Any],
    *,
    on_success: Callable[[Any], None] | None = None,
    on_error: Callable[[str], None] | None = None,
) -> bool:
    """在忙碌对话框 + 工作线程中执行 *work*（v1.3.1 统一入口）。

    Args:
        parent: 归属窗口（对话框模态遮住它）。
        title: 对话框标题（同时是状态栏提示前缀）。
        text: 正在处理事项的说明（显示给用户）。
        work: 无参工作函数，**在工作线程执行**，禁止触碰 GUI。
        on_success: 工作成功后的回调（参数为 ``work()`` 返回值），
            在 **GUI 线程**执行。
        on_error: 工作抛异常后的回调（参数为异常描述字符串），在
            **GUI 线程**执行；未提供时异常被静默忽略（不推荐）。

    重入保护：同一 parent 上一次忙碌尚未结束时再次调用直接忽略
    （双击/回车连触不会排队多次执行）。

    Returns:
        bool: ``True`` 表示本次调用真正执行了 *work*；``False`` 表示被重入
        保护拒绝（调用方据此回收自己预先申请的资源，例如数据库连接）。

    取消：用户点「取消」只置位标志，工作线程在核心层的轮询点抛出
    :class:`~xinmatch.core.cancel.OperationCancelled` 后正常退出；此时
    ``on_success`` / ``on_error`` 都不会被调用。
    """
    if getattr(parent, "_busy_active", False):
        return False
    parent._busy_active = True  # type: ignore[attr-defined]
    if hasattr(parent, "statusBar"):
        parent.statusBar().showMessage(f"{title}：{text}")

    dlg = BusyDialog(parent, title, text)
    worker = _Worker(work, lambda: dlg.cancel_requested)

    # 关键：connect 的 receiver 必须是 GUI 线程的 QObject（dlg），
    # Qt 才会走 QueuedConnection 把信号派发回 GUI 线程。直接 connect
    # 闭包/普通函数会变成 DirectConnection——信号在 worker 线程当场
    # 执行，dlg.accept() 跨线程调用无效，exec() 永远等不到关闭（挂死）。
    worker.finished_ok.connect(dlg.receive_result)
    worker.failed.connect(dlg.receive_error)
    worker.cancelled.connect(dlg.receive_cancel)
    worker.start()
    # exec() 起局部事件循环：走马灯动画持续刷新，主窗口被模态遮罩挡住。
    # worker 信号经 QueuedConnection 派发到该循环，触发 dlg.accept()。
    dlg.exec()
    # 信号已在 accept() 前发出，正常情况下线程随即结束；给一个上限避免
    # 极端路径下永久阻塞 GUI 线程（取消标志若不生效会在这里留下日志）。
    if not worker.wait(10000):  # pragma: no cover - 防御性
        logger.warning(
            "worker for %r still running 10s after its dialog closed "
            "(cancellation not polled?)", title,
        )
        worker.wait()
    worker.deleteLater()
    dlg.deleteLater()
    parent._busy_active = False  # type: ignore[attr-defined]

    if dlg.was_cancelled:
        if hasattr(parent, "statusBar"):
            parent.statusBar().showMessage(f"{title}：已取消", 5000)
        return True
    if dlg.error_message is not None:
        if on_error is not None:
            on_error(dlg.error_message)
    elif on_success is not None:
        on_success(dlg.result_value)
    return True
