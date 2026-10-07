"""XinMatch command-line interface (T14.1).

A thin argparse-based wrapper around the core pipeline.  Each subcommand
delegates to the corresponding :mod:`xinmatch.core` routine; no
algorithms are implemented at this layer.
"""

from __future__ import annotations

from typing import Any

__all__ = ["main"]


def __getattr__(name: str) -> Any:
    """Lazily import :func:`main` to avoid ``runpy`` re-execution warnings."""
    if name == "main":
        from .main import main

        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
