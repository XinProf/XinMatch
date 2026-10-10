"""Pytest fixtures for the report test-suite.

The full-suite single-process run previously appeared to "hang" at the first
matplotlib PNG export test (``tests/report/test_figure_export.py``) with CPU
pegged for 30+ minutes.  Trace evidence (faulthandler 45 s periodic dumps)
showed the main thread was *not* inside matplotlib at all — it was still in
the slow ``scipy.optimize.least_squares`` numerical-Jacobian loop of the
``tests/refine/test_turn_on.py`` Rietveld refinement tests, which run
immediately before this directory.

To guard against any residual backend / figure-state leakage from the
preceding refinement tests (which themselves do not import matplotlib), we
explicitly pin the headless ``Agg`` backend and close any stray figures
before and after each report test.  This fixture is defensive and does not
change production runtime behaviour — :mod:`xinmatch.core.report.figure_export`
already calls ``matplotlib.use("Agg")`` lazily on every public entry point.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _matplotlib_agg_headless():
    """Ensure the Agg backend is active and no stray figures leak between tests.

    Runs automatically for every test under ``tests/report/``.  If matplotlib
    is not installed the fixture is a no-op (the tests themselves use
    ``pytest.importorskip("matplotlib")``).
    """
    mpl = pytest.importorskip("matplotlib")
    mpl.use("Agg")  # headless — no Qt / offscreen dependency
    import matplotlib.pyplot as plt

    # Close any figures left over by earlier (non-report) test modules.
    for num in plt.get_fignums():
        plt.close(num)
    yield
    # Tear-down: close figures created by this test.
    for num in plt.get_fignums():
        plt.close(num)
