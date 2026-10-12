"""耗时操作的忙碌进度窗口（v1.3.1）。

问题背景
--------
Search-Match / SMPF 全谱拟合等操作耗时数秒到数十秒，此前在 GUI 线程内
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

from collections.abc import Callable
from typing import Any

from PySide6 import QtCore, QtWidgets

__all__ = ["BusyDialog", "run_with_busy"]


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

    # 以下两个槽由 _Worker 的信号（跨线程）触发；receiver=本对话框，
    # Qt 自动走 QueuedConnection，在 GUI 线程执行。
    def receive_result(self, value: Any) -> None:
        self.result_value = value
        self.accept()

    def receive_error(self, message: str) -> None:
        self.error_message = message
        self.accept()

    def reject(self) -> None:  # noqa: D102 — 吞掉 ESC，防止中途关闭
        pass


class _Worker(QtCore.QThread):
    """在独立线程执行 ``work``，结果/异常经信号回 GUI 线程。"""

    finished_ok = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, work: Callable[[], Any], parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._work = work

    def run(self) -> None:  # noqa: D102
        try:
            self.finished_ok.emit(self._work())
        except Exception as exc:  # noqa: BLE001 — 异常统一转字符串回 GUI 线程
            self.failed.emit(f"{type(exc).__name__}: {exc}")


def run_with_busy(
    parent: QtWidgets.QWidget,
    title: str,
    text: str,
    work: Callable[[], Any],
    *,
    on_success: Callable[[Any], None] | None = None,
    on_error: Callable[[str], None] | None = None,
) -> None:
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
    """
    if getattr(parent, "_busy_active", False):
        return
    parent._busy_active = True  # type: ignore[attr-defined]
    if hasattr(parent, "statusBar"):
        parent.statusBar().showMessage(f"{title}：{text}")

    dlg = BusyDialog(parent, title, text)
    worker = _Worker(work)

    # 关键：connect 的 receiver 必须是 GUI 线程的 QObject（dlg），
    # Qt 才会走 QueuedConnection 把信号派发回 GUI 线程。直接 connect
    # 闭包/普通函数会变成 DirectConnection——信号在 worker 线程当场
    # 执行，dlg.accept() 跨线程调用无效，exec() 永远等不到关闭（挂死）。
    worker.finished_ok.connect(dlg.receive_result)
    worker.failed.connect(dlg.receive_error)
    worker.start()
    # exec() 起局部事件循环：走马灯动画持续刷新，主窗口被模态遮罩挡住。
    # worker 信号经 QueuedConnection 派发到该循环，触发 dlg.accept()。
    dlg.exec()
    worker.wait()
    worker.deleteLater()
    dlg.deleteLater()
    parent._busy_active = False  # type: ignore[attr-defined]

    if dlg.error_message is not None:
        if on_error is not None:
            on_error(dlg.error_message)
    elif on_success is not None:
        on_success(dlg.result_value)
