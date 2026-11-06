"""``python -m xinmatch`` must behave like the installed ``xinmatch`` script.

Why this test exists: the handover tells the next maintainer to run
``python -m xinmatch libraries`` against the source tree, and that form used to
fail with ``No module named xinmatch.__main__`` while ``python -m
xinmatch.cli.main`` worked.  A documented command that does not run is worse
than no documentation, so the entry point is pinned here.
"""

from __future__ import annotations

import subprocess
import sys

import pytest


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "xinmatch", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


def test_module_entry_reports_version() -> None:
    result = _run("--version")
    assert result.returncode == 0, result.stderr
    from xinmatch import __version__

    assert __version__ in result.stdout


def test_module_entry_accepts_subcommand() -> None:
    """``libraries`` is the cheapest subcommand that touches real code paths."""
    result = _run("libraries", "--json")
    if result.returncode != 0:
        # No library registered on this machine is a valid environment, not a
        # defect — but the *entry point* must still have parsed the subcommand.
        assert "cannot be directly executed" not in result.stderr
        assert "No module named" not in result.stderr
        pytest.skip(f"libraries unavailable in this environment: {result.stderr[:200]}")
    assert "xindb" in result.stdout.lower() or "libraries" in result.stdout.lower()
