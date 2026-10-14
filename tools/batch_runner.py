"""Config-driven batch search-match runner (T14.3) — CLI wrapper.

Thin compatibility layer over :mod:`xinmatch.core.batch`: keeps the
``tools/batch_runner.py config.yaml`` invocation and the
``from tools.batch_runner import load_config, run_batch`` import path
used by early T14.3 consumers.  New code should import from
:mod:`xinmatch.core.batch` directly.

Usage
-----
::

    python tools/batch_runner.py config.yaml
    python tools/batch_runner.py config.json
    xinmatch batch config.yaml          # same engine via the main CLI
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from xinmatch.core.batch import (  # noqa: E402  — path bootstrap first
    BatchResult,
    SampleResult,
    load_config,
    run_batch,
    run_sample,
    write_summary,
)

__all__ = [
    "SampleResult",
    "BatchResult",
    "load_config",
    "run_sample",
    "run_batch",
    "write_summary",
    "main",
]


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``python tools/batch_runner.py config.yaml``."""
    parser = argparse.ArgumentParser(
        description="Batch XinMatch search-match driven by a JSON/YAML config.",
    )
    parser.add_argument("config", help="Path to the batch config (.yaml/.yml/.json).")
    args = parser.parse_args(argv)

    try:
        config, config_dir = load_config(args.config)
        batch = run_batch(config, config_dir=config_dir)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print("")
    print(
        f"Batch finished: {batch.n_ok} ok, {batch.n_failed} failed "
        f"(total {len(batch.samples)})."
    )
    if batch.summary_path:
        print(f"Summary: {batch.summary_path}")
    return 0 if batch.n_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
