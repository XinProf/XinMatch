"""Offscreen GUI test fixtures.

``QT_QPA_PLATFORM=offscreen`` must be set **before** any PySide6 /
pyqtgraph import; importing this conftest first guarantees that.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6 import QtWidgets


@pytest.fixture(scope="session")
def qapp():
    """Session-wide QApplication for all offscreen widget tests."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    yield app
