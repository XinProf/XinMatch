"""Command-line interface for XinMatch.

Usage::

    xinmatch import <pattern>
    xinmatch search <pattern> --db <cod.db>
    xinmatch report <project>

For the full workflow, see :mod:`xinmatch.cli.batch`.
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``xinmatch`` console script."""
    parser = argparse.ArgumentParser(
        prog="xinmatch",
        description="XinMatch — powder XRD phase analysis (CLI front-end).",
    )
    parser.add_argument(
        "--version", action="version", version=f"xinmatch {_version()}"
    )
    sub = parser.add_subparsers(dest="command")

    # Placeholder subcommands — implemented in later phases.
    sub.add_parser("import", help="import a diffraction pattern")
    sub.add_parser("search", help="run search-match phase identification")
    sub.add_parser("report", help="generate an analysis report")

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    print(f"[xinmatch] command '{args.command}' is not yet implemented.")
    return 0


def _version() -> str:
    from xinmatch import __version__

    return __version__


if __name__ == "__main__":
    sys.exit(main())
