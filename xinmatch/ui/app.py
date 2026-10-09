"""QApplication bootstrap factory and ``main()`` entry point.

T13.0 — GUI architecture (PySide6 native).  This module is the single
entry point for every executable run of the XinMatch GUI.  ``create_app()``
is a testable factory so that offscreen pytest runs and the real program
share exactly the same QApplication setup.

Match! reference: ``docs/working_area.md`` — the program window has a menu
at the top, a toolbar below it, and a status bar at the bottom; this module
only performs the bootstrap that happens before the window itself is built.

v1.0.0 branding notes
---------------------
* In-app splash: the PyInstaller bootloader-level splash would need a
  C-compiled bootloader variant, so ``assets/splash.png`` is shown through a
  ``QSplashScreen`` after Qt starts and is hidden as soon as the main window
  is shown — it never blocks or slows startup.
* Selftest hook (packaging robustness testing only): when the env var
  ``XINMATCH_SELFTEST_ABOUT`` is set, the app opens the About dialog,
  snapshots it to ``XINMATCH_SELFTEST_OUT`` (default ``about_selftest.png``)
  and exits — used to verify logo / version / contact inside the frozen
  bundle without driving the GUI interactively.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence

from PySide6 import QtCore, QtGui, QtWidgets


def create_app(argv: Sequence[str] | None = None) -> QtWidgets.QApplication:
    """Return the process-wide QApplication, creating it on first call.

    Repeated calls return the existing instance (QApplication is a Qt
    singleton), which keeps unit tests cheap and prevents "QApplication
    already exists" errors.
    """
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(list(argv) if argv is not None else [])
    app.setApplicationName("XinMatch")
    app.setApplicationDisplayName("XinMatch — powder XRD phase analysis")
    app.setOrganizationName("XinMatch")
    return app


def _maybe_show_splash(app: QtWidgets.QApplication) -> QtWidgets.QSplashScreen | None:
    """Show ``assets/splash.png`` as an in-app splash until the main window
    is ready; returns ``None`` when the asset is missing (e.g. tests run
    without the assets tree)."""
    del app  # QSplashScreen needs no extra setup beyond the QApplication.
    from xinmatch.ui.main_window import _asset_path

    path = _asset_path("splash.png")
    if not path.is_file():
        return None
    pixmap = QtGui.QPixmap(str(path))
    if pixmap.isNull():
        return None
    splash = QtWidgets.QSplashScreen(pixmap)
    splash.show()
    return splash


def _run_about_selftest(window: QtWidgets.QWidget) -> None:
    """Test-only hook: open the About dialog, snapshot it, then quit."""
    from xinmatch.ui.about_dialog import AboutDialog

    out_path = os.environ.get("XINMATCH_SELFTEST_OUT") or "about_selftest.png"
    dlg = AboutDialog(window)
    dlg.show()

    def _snap() -> None:
        dlg.grab().save(out_path)
        QtWidgets.QApplication.instance().quit()

    QtCore.QTimer.singleShot(800, _snap)


def main(argv: Sequence[str] | None = None) -> int:
    """GUI entry point: build the main window and run the event loop."""
    app = create_app(argv)
    from xinmatch.ui.main_window import MainWindow

    splash = _maybe_show_splash(app)

    window = MainWindow()
    window.show()
    if splash is not None:
        splash.finish(window)

    if os.environ.get("XINMATCH_SELFTEST_ABOUT"):
        _run_about_selftest(window)

    return int(app.exec())


if __name__ == "__main__":
    sys.exit(main())
