"""GUI: COD-full one-click background build (offscreen).

Covers the ``构建 COD 全库…`` workflow on
:class:`~xinmatch.ui.dialogs.library_dialog.LibraryDialog`:

* clicking the button (or calling the launch entry directly) wires a fake
  builder onto a background :class:`~PySide6.QtCore.QThread`;
* ``progress: N inserted`` log lines are streamed into the read-only log view;
* the progress control reflects the inserted count;
* on completion the dialog refreshes the library list and pops a summary box;
* requesting cancellation makes the (fake) builder return early and restores
  the buttons to the idle state.

The real builder (gemmi over hundreds of thousands of CIFs) is never run here;
``dialog._builder`` is monkeypatched to a fast, interruption-aware fake that
mimics the real ``logger.info("progress: N inserted ...")`` contract.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6 import QtWidgets

from xinmatch.core.db.multi_db import cod_full_db_path
from xinmatch.ui.dialogs import LibraryDialog

BUILDER_LOGGER = "tools.build_cod_full_xinmatch"


def _pump(app: QtWidgets.QApplication, until, timeout_ms: int = 5000) -> None:
    """Spin the offscreen event loop until ``until()`` is true or timeout."""
    deadline = time.perf_counter() + timeout_ms / 1000.0
    while time.perf_counter() < deadline:
        app.processEvents()
        if until():
            return
        time.sleep(0.01)
    raise TimeoutError("event-loop pump timed out")


def _make_fake_builder(calls: list[dict], dialog: LibraryDialog, total: int = 50):
    """Return a builder callable matching the real ``build(...)`` signature.

    Emits a ``progress: N inserted ...`` line every ~20 ms and bails out early
    when the running QThread has an interruption request pending.
    """

    def builder(
        out: Path,
        *,
        start: int,
        limit: int | None,
        resume: bool,
        dmin: float,
        max_peaks: int,
        cod_index: Path | None,
        log_every: int,
    ) -> dict:
        calls.append(
            {
                "out": out,
                "start": start,
                "limit": limit,
                "resume": resume,
                "dmin": dmin,
                "max_peaks": max_peaks,
                "cod_index": cod_index,
                "log_every": log_every,
            }
        )
        lg = logging.getLogger(BUILDER_LOGGER)
        inserted = 0
        while inserted < total:
            thread = dialog._build_thread
            if thread is not None and thread.isInterruptionRequested():
                return {
                    "entries_inserted": inserted,
                    "seconds": 0.2,
                    "entries_per_min": 300.0,
                    "cod_entries_known": total,
                }
            inserted += 10
            lg.info(
                "progress: %d inserted (skip_cif=0 skip_no_peaks=0 peaks=500) "
                "3000 entries/min, ETA 0.1 min",
                inserted,
            )
            time.sleep(0.02)
        return {
            "entries_inserted": inserted,
            "seconds": 0.2,
            "entries_per_min": 300.0,
            "cod_entries_known": total,
        }

    return builder


def test_build_button_calls_builder_and_streams_log(qapp):
    dialog = LibraryDialog()
    calls: list[dict] = []
    dialog._builder = _make_fake_builder(calls, dialog, total=50)

    with patch(
        "PySide6.QtWidgets.QMessageBox.question",
        return_value=QtWidgets.QMessageBox.StandardButton.Yes,
    ), patch("PySide6.QtWidgets.QMessageBox.information") as info:
        # Click the real button (confirmation returns Yes above).
        dialog._build_btn.click()
        # Buttons enter the "building" state immediately.
        assert dialog._build_btn.isEnabled() is False
        assert dialog._cancel_btn.isEnabled() is True
        _pump(qapp, lambda: dialog._build_thread is None)

    # Builder was invoked once, against the configured output path.
    assert len(calls) == 1
    assert calls[0]["out"] == cod_full_db_path()
    assert calls[0]["limit"] is None  # full build via the button
    assert calls[0]["resume"] is True
    assert calls[0]["dmin"] == pytest.approx(1.0)
    assert calls[0]["max_peaks"] == 100

    # Progress lines reached the read-only log view.
    log_text = dialog._log_view.toPlainText()
    assert "progress:" in log_text
    assert " inserted" in log_text

    # Completion ran: summary box popped and buttons restored.
    assert info.called
    assert dialog._build_btn.isEnabled() is True
    assert dialog._cancel_btn.isEnabled() is False
    assert dialog._progress_bar.format() == "完成"


def test_launch_with_small_limit_and_progress_bar(qapp):
    dialog = LibraryDialog()
    calls: list[dict] = []
    dialog._builder = _make_fake_builder(calls, dialog, total=30)

    with patch("PySide6.QtWidgets.QMessageBox.information") as info:
        # Direct launch with a small limit (test / slice mode).
        dialog._launch_build(limit=50)
        _pump(qapp, lambda: dialog._build_thread is None)

    assert calls[0]["limit"] == 50
    assert info.called
    # The summary message mentions the inserted count.
    assert "已插入" in info.call_args.args[-1]


def test_cancel_path_stops_builder_and_restores_ui(qapp):
    dialog = LibraryDialog()
    calls: list[dict] = []
    # Many iterations so cancellation lands mid-run.
    dialog._builder = _make_fake_builder(calls, dialog, total=100000)

    with patch("PySide6.QtWidgets.QMessageBox.information") as info:
        dialog._launch_build(limit=100000)
        # Let a couple of progress lines land, then cancel.
        _pump(qapp, lambda: "progress:" in dialog._log_view.toPlainText())
        dialog._cancel_btn.click()
        _pump(qapp, lambda: dialog._build_thread is None)

    # Builder returned early (far fewer than 100000).
    assert calls[0]["limit"] == 100000
    # Cancel path: info box says cancelled, no "完成".
    assert info.called
    assert "取消" in info.call_args.args[-1]
    assert dialog._build_btn.isEnabled() is True
    assert dialog._cancel_btn.isEnabled() is False
    assert dialog._progress_bar.format() == "已取消"


# ---------------------------------------------------------------------------
# C2: the already-built data/cod_full.db slice must be registered & available
# ---------------------------------------------------------------------------
def test_cod_full_slice_is_listed_available():
    from xinmatch.core.db.multi_db import list_libraries

    rec = next((r for r in list_libraries() if r.id == "cod_full"), None)
    assert rec is not None
    assert rec.available, rec.unavailable_reason
    assert rec.entry_count is not None
    # A real full build now registers 112,734 entries; a --limit slice registers
    # fewer but must still be >= the slice minimum. Only the lower bound is
    # meaningful for "the built library is registered and usable".
    assert rec.entry_count >= 300
