"""Cooperative cancellation for long-running core computations.

The GUI runs expensive work (Search-Match, FPFM full-pattern fitting) on a
worker thread behind a modal busy dialog.  Killing a thread is never safe (it
can corrupt NumPy state, SQLite handles and half-written files), so cancellation
is **cooperative**: the caller installs a predicate for the current thread, and
long loops poll :func:`check_cancelled`, which raises :class:`OperationCancelled`.

Usage
-----
Worker side (GUI)::

    from xinmatch.core.cancel import set_cancel_check
    set_cancel_check(lambda: dialog.cancelled)
    try:
        work()
    finally:
        set_cancel_check(None)

Core side (long loop)::

    from xinmatch.core.cancel import check_cancelled
    for entry in entries:
        check_cancelled()      # raises OperationCancelled when the user cancels
        ...

The predicate is **thread-local**, so concurrent computations (CLI batch,
batch pipelines) are unaffected, and the core layer never imports Qt.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

__all__ = [
    "OperationCancelledError",
    "check_cancelled",
    "cancelled",
    "set_cancel_check",
]


class OperationCancelledError(RuntimeError):
    """Raised by :func:`check_cancelled` after the user requested cancellation."""


_local = threading.local()


def set_cancel_check(check: Callable[[], bool] | None) -> None:
    """Install (or clear, with ``None``) the cancellation predicate for this thread."""
    _local.check = check


def cancelled() -> bool:
    """Return ``True`` if the current thread's predicate reports cancellation."""
    check = getattr(_local, "check", None)
    return bool(check()) if check is not None else False


def check_cancelled() -> None:
    """Raise :class:`OperationCancelledError` when the current thread was cancelled."""
    if cancelled():
        raise OperationCancelledError("operation cancelled by user")
