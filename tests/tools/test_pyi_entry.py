"""The frozen-binary dispatcher must know every CLI subcommand.

Regression guard for the v2.0.0 packaging defect: ``tools/pyi_entry.py`` kept a
hard-coded subcommand set that was missing ``libraries`` (and the older
``batch`` / ``instrument``), so ``XinMatch.exe libraries --json`` launched the
GUI instead of mounting a database.  Nothing caught it because the dispatcher
had no tests.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _load_entry():
    path = REPO / "tools" / "pyi_entry.py"
    spec = importlib.util.spec_from_file_location("xinmatch_pyi_entry", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def entry():
    return _load_entry()


def _parser_subcommands() -> set[str]:
    import argparse

    from xinmatch.cli.main import build_parser

    for action in build_parser()._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    return set()


def test_dispatcher_commands_match_the_parser(entry):
    assert entry.cli_commands() == _parser_subcommands()


def test_fallback_list_matches_the_parser(entry):
    """The static fallback is only used when the parser import fails, so it must
    still cover every real subcommand."""
    assert _parser_subcommands() == entry.FALLBACK_CLI_COMMANDS


@pytest.mark.parametrize("command", ["libraries", "batch", "instrument",
                                     "import", "search", "quantify"])
def test_cli_subcommands_route_to_the_cli(entry, command):
    assert entry.wants_cli([command, "--help"]) is True


@pytest.mark.parametrize("argv", [[], ["--not-a-command"], ["some_file.xy"]])
def test_non_commands_open_the_gui(entry, argv):
    assert entry.wants_cli(argv) is False


def test_help_flags_reach_the_cli(entry):
    assert entry.wants_cli(["--help"]) is True
    assert entry.wants_cli(["-h"]) is True
