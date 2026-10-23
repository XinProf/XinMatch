"""Read-only progress probe for an in-flight ``.xinDB`` build.

The build writer commits a chunk every ``chunk_size`` entries (default 5000),
so ``meta.entry_count`` is only refreshed at close time.  That makes the
``--log-every`` cadence the only in-build signal, and at 20 000 entries it is
roughly 45 minutes on a COD-Full run -- far too coarse to tell a slow
head-of-line stall apart from a genuine throughput drop.

This probe opens the target file with ``mode=ro&immutable=1``.  ``immutable=1``
tells SQLite to skip every file lock, which is required because the writer runs
with ``PRAGMA journal_mode = OFF`` and holds an exclusive lock for the whole
run.  Reading a database that is actively growing is normally unsafe; it is
acceptable here because we only ever run ``count(*)`` against ``entries``, a
rowid table whose committed pages are append-only in practice.  Any transient
inconsistency shows up as an ``OperationalError`` and is reported, not raised.

Usage::

    python -m tools._probe_build_progress data/COD-Full-20261020.xinDB
    python -m tools._probe_build_progress data/COD-Full-20261020.xinDB \
        --total 535166 --interval 120 --samples 10
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path


def _count_entries(db: Path) -> int | None:
    """Committed entry count, or ``None`` if the file is mid-page-write."""
    uri = f"file:{db.as_posix()}?mode=ro&immutable=1"
    try:
        con = sqlite3.connect(uri, uri=True, timeout=3.0)
    except sqlite3.Error:
        return None
    try:
        row = con.execute("SELECT count(*) FROM entries").fetchone()
        return int(row[0])
    except sqlite3.Error:
        return None
    finally:
        con.close()


def _size_mb(db: Path) -> float:
    try:
        return db.stat().st_size / (1024.0 * 1024.0)
    except OSError:
        return 0.0


def _fmt_duration(seconds: float) -> str:
    if seconds != seconds or seconds < 0 or seconds == float("inf"):
        return "unknown"
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("db", type=Path, help=".xinDB file being built")
    ap.add_argument(
        "--total",
        type=int,
        default=0,
        help="expected final entry count; enables ETA when given",
    )
    ap.add_argument("--interval", type=float, default=60.0, help="seconds between samples")
    ap.add_argument(
        "--samples",
        type=int,
        default=0,
        help="number of samples; 0 means loop until interrupted",
    )
    ap.add_argument(
        "--window",
        type=int,
        default=5,
        help="trailing samples averaged for the rate and ETA",
    )
    args = ap.parse_args(argv)

    db: Path = args.db
    if not db.exists():
        print(f"no such file: {db}", file=sys.stderr)
        return 2

    history: list[tuple[float, int]] = []
    taken = 0
    try:
        while True:
            now = time.time()
            count = _count_entries(db)
            if count is None:
                print(f"{time.strftime('%H:%M:%S')}  (unreadable, retrying)")
            else:
                history.append((now, count))
                line = f"{time.strftime('%H:%M:%S')}  entries={count:>8d}"
                if len(history) >= 2:
                    prev_t, prev_c = history[-2]
                    span = now - prev_t
                    if span > 0:
                        line += f"  +{count - prev_c:>5d}  {((count - prev_c) / span):6.2f}/s"
                if args.total and len(history) >= 2:
                    tail = history[-min(args.window, len(history)):]
                    span = tail[-1][0] - tail[0][0]
                    done = tail[-1][1] - tail[0][1]
                    if span > 0 and done > 0:
                        rate = done / span
                        remaining = max(args.total - count, 0)
                        line += (
                            f"  avg={rate:6.2f}/s"
                            f"  {count * 100.0 / args.total:5.1f}%"
                            f"  eta={_fmt_duration(remaining / rate)}"
                        )
                line += f"  size={_size_mb(db):7.1f}MB"
                print(line, flush=True)
            taken += 1
            if args.samples and taken >= args.samples:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\ninterrupted", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
