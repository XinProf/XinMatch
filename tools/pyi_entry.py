"""PyInstaller entry point for the XinMatch onedir bundle.

PyInstaller selects a *single* boot script per executable; splitting multiple
Analysis scripts across two EXEs does not produce independent entry points
(the bootloader always runs the first script).  We therefore ship one
executable that dispatches on ``sys.argv``:

* ``XinMatch.exe <cli-subcommand> ...``  -> run the CLI (xinmatch.cli.main)
* ``XinMatch.exe`` (double-click / no recognized subcommand) -> launch the GUI

This keeps one onedir bundle, one icon/version resource, and still lets us
smoke-test the CLI and the offscreen GUI from the same binary.
"""

from __future__ import annotations

import sys

#: CLI subcommands accepted by ``xinmatch.cli.main:build_parser``.
CLI_COMMANDS = {"import", "process", "search", "quantify", "report", "run"}


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] in CLI_COMMANDS:
        from xinmatch.cli.main import main as cli_main
        return cli_main(args)

    from xinmatch.ui.app import main as gui_main
    return gui_main(args)


if __name__ == "__main__":
    sys.exit(main())
