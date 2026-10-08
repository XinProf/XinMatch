"""T13.0 — QApplication bootstrap factory and main() entry point."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from xinmatch.ui import app as app_module


def test_create_app_returns_qapplication(qapp):
    app = app_module.create_app([])
    assert isinstance(app, QtWidgets.QApplication)


def test_create_app_is_singleton(qapp):
    assert app_module.create_app() is qapp


def test_main_runs_event_loop_to_completion(qapp):
    # Quit the event loop right after it starts; offscreen show() is a no-op.
    QtCore.QTimer.singleShot(0, qapp.quit)
    rc = app_module.main([])
    assert rc == 0
