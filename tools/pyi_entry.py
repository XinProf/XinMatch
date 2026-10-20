"""PyInstaller entry point for the XinMatch onedir bundle.

PyInstaller selects a *single* boot script per executable; splitting multiple
Analysis scripts across two EXEs does not produce independent entry points
(the bootloader always runs the first script).  We therefore ship one
executable that dispatches on ``sys.argv``:

* ``XinMatch.exe <cli-subcommand> ...``  -> run the CLI (xinmatch.cli.main)
* ``XinMatch.exe`` (double-click / no recognized subcommand) -> launch the GUI

This keeps one onedir bundle, one icon/version resource, and still lets us
smoke-test the CLI and the offscreen GUI from the same binary.

The accepted subcommand set is read from ``build_parser()`` at runtime rather
than hard-coded: v2.0.0 shipped with ``libraries`` (plus the older ``batch``
and ``instrument``) missing from a static list, so ``XinMatch.exe libraries
--json`` silently launched the GUI instead of mounting a database.  Deriving
the set keeps the dispatcher and the parser from drifting apart again.
"""

from __future__ import annotations

import sys

#: Only used if the CLI parser cannot be imported (kept in sync by
#: ``tests/tools/test_pyi_entry.py``).
FALLBACK_CLI_COMMANDS = {
    "batch",
    "import",
    "instrument",
    "libraries",
    "process",
    "quantify",
    "report",
    "run",
    "search",
}

#: Flags that should reach the CLI parser instead of opening the GUI.
CLI_FLAGS = {"-h", "--help"}


def cli_commands() -> set[str]:
    """Subcommands accepted by ``xinmatch.cli.main:build_parser``."""
    try:
        import argparse

        from xinmatch.cli.main import build_parser

        for action in build_parser()._actions:
            if isinstance(action, argparse._SubParsersAction):
                return set(action.choices)
    except Exception:  # noqa: BLE001 - a broken CLI must not break the GUI
        pass
    return set(FALLBACK_CLI_COMMANDS)


def wants_cli(argv: list[str]) -> bool:
    """True when ``argv`` should be handled by the CLI rather than the GUI."""
    if not argv:
        return False
    head = argv[0]
    return head in CLI_FLAGS or head in cli_commands()


def main() -> int:
    args = sys.argv[1:]
    if wants_cli(args):
        from xinmatch.cli.main import main as cli_main
        return cli_main(args)

    from xinmatch.ui.app import main as gui_main
    return gui_main(args)


if __name__ == "__main__":
    sys.exit(main())
