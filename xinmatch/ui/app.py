"""QApplication bootstrap factory and ``main()`` entry point.

T13.0 — GUI architecture (PySide6 native).  This module is the single
entry point for every executable run of the XinMatch GUI.  ``create_app()``
is a testable factory so that offscreen pytest runs and the real program
share exactly the same QApplication setup.

Match! reference: ``docs/working_area.md`` — the program window has a menu
at the top, a toolbar below it, and a status bar at the bottom; this module
only performs the bootstrap that happens before the window itself is built.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6 import QtWidgets


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


def main(argv: Sequence[str] | None = None) -> int:
    """GUI entry point: build the main window and run the event loop."""
    app = create_app(argv)
    from xinmatch.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":
    sys.exit(main())
