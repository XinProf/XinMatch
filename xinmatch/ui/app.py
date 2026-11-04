"""QApplication bootstrap factory and ``main()`` entry point.

T13.0 — GUI architecture (PySide6 native).  This module is the single
entry point for every executable run of the XinMatch GUI.  ``create_app()``
is a testable factory so that offscreen pytest runs and the real program
share exactly the same QApplication setup.

The reference software reference: ``docs/working_area.md`` — the program window has a menu
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
from typing import TYPE_CHECKING, cast

from PySide6 import QtCore, QtGui, QtWidgets

if TYPE_CHECKING:  # pragma: no cover - typing only (avoids import cycle)
    from xinmatch.ui.main_window import MainWindow


def create_app(argv: Sequence[str] | None = None) -> QtWidgets.QApplication:
    """Return the process-wide QApplication, creating it on first call.

    Repeated calls return the existing instance (QApplication is a Qt
    singleton), which keeps unit tests cheap and prevents "QApplication
    already exists" errors.
    """
    # instance() is typed on the base QCoreApplication; cast narrows it.
    app = cast(QtWidgets.QApplication, QtWidgets.QApplication.instance())
    if app is None:
        app = QtWidgets.QApplication(list(argv) if argv is not None else [])
    app.setApplicationName("XinMatch")
    # setApplicationDisplayName exists at runtime; the PySide6 stub for the
    # base QCoreApplication class omits it.
    app.setApplicationDisplayName("XinMatch — powder XRD phase analysis")  # type: ignore[attr-defined]
    app.setOrganizationName("XinMatch")
    # 应用级图标：任务栏/Alt-Tab 在窗口出现前就有图标（v3.2.0 起用新标志）。
    from xinmatch.ui.main_window import _asset_path

    for _name in ("icons/logo_256.png", "logo.png"):
        _path = _asset_path(_name)
        if _path.is_file():
            app.setWindowIcon(QtGui.QIcon(str(_path)))
            break
    return app


def _maybe_show_splash(app: QtWidgets.QApplication) -> QtWidgets.QSplashScreen | None:
    """Show ``assets/splash.png`` as an in-app splash until the main window
    is ready; returns ``None`` when the asset is missing or the platform is
    offscreen (e.g. tests run with ``QT_QPA_PLATFORM=offscreen``).

    Why skip offscreen: ``QSplashScreen.show()`` processes pending events,
    which can consume a pre-scheduled ``QTimer.singleShot(0, quit)`` before
    ``app.exec()`` starts — leaving the event loop running forever.  The
    splash is a cosmetic startup feature, so headless test environments
    safely run without it.
    """
    del app  # QSplashScreen needs no extra setup beyond the QApplication.
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        return None
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
        QtWidgets.QApplication.quit()

    QtCore.QTimer.singleShot(800, _snap)


def _run_libraries_selftest() -> None:
    """Test-only hook: dump the reference-library registry as JSON, then quit.

    Used by the packaging robustness suite to verify the multi-library mount
    inside the frozen bundle (default DB present with its entry count, PDF-2
    sidecar availability, COD-full build status) without driving the GUI.
    """
    import json
    from pathlib import Path

    from xinmatch.core.db.multi_db import list_libraries

    out_path = (
        os.environ.get("XINMATCH_SELFTEST_LIBS_OUT") or "libraries_selftest.json"
    )
    records = [
        {
            "id": rec.id,
            "display_name": rec.display_name,
            "kind": rec.kind,
            "path": str(rec.path),
            "entry_count": rec.entry_count,
            "available": rec.available,
            "unavailable_reason": rec.unavailable_reason,
        }
        for rec in list_libraries()
    ]
    Path(out_path).write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    QtWidgets.QApplication.quit()


def _run_registration_selftest(window: MainWindow) -> None:
    """Test-only hook: dump build variant + registration status, then quit.

    Used to verify the two v1.7.0 binaries without driving the GUI:

    * release build → ``registration_enabled`` true, ``status_text`` is
      ``未注册`` / ``已注册：<单位>``;
    * internal build → ``registration_enabled`` false, ``status_text`` is
      ``内部评估版本``.
    """
    import json
    from pathlib import Path

    from xinmatch.utils import build_variant

    out_path = (
        os.environ.get("XINMATCH_SELFTEST_REG_OUT")
        or "registration_selftest.json"
    )
    reg = getattr(window, "_registration", None)
    payload = {
        "variant": build_variant.current_variant(),
        "registration_enabled": reg is not None,
        "registered": bool(reg is not None and reg.state.registered),
        "unit": reg.state.unit if reg is not None else "",
        "status_text": window.registration_status_text(),
        "state_path": str(reg.state_path) if reg is not None else "",
    }
    Path(out_path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    QtWidgets.QApplication.quit()


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
    elif os.environ.get("XINMATCH_SELFTEST_LIBS"):
        QtCore.QTimer.singleShot(0, _run_libraries_selftest)
    elif os.environ.get("XINMATCH_SELFTEST_REG"):
        QtCore.QTimer.singleShot(0, lambda: _run_registration_selftest(window))

    return int(app.exec())


if __name__ == "__main__":
    sys.exit(main())
