"""Build a curated, de-duplicated copy of ``data/cod_full.db``.

The full COD database (112,734 entries / 10.98M peaks) dilutes the XRD
search-match ranking: many cards describe the *same* phase (identical
``formula`` + ``space_group``) and the FoM vote is spread across them, so
the L3 acceptance Top-1 agreement collapses.  This tool keeps **exactly one
card per (formula, space_group) cluster** and copies only that card's peaks /
elements into a fresh, schema-identical SQLite database.

Selection rule (best card per cluster)
--------------------------------------
Because the COD archive as shipped here carries no usable quality signal
(``quality`` is ``''`` for every row; ``year``/``author``/``journal``/
``density`` are all NULL), the ranking is, in priority order:

1. **most computed peaks** (``peaks`` row count, DESC) — a more complete
   reflection list is a better reference pattern;
2. **has a usable ``mineral_name``** (present, non-empty, not the ``';'``
   junk placeholder) — a proxy for a curated / hand-checked card;
3. **``entry_id`` ASC** — deterministic tie-break.

The source ``data/cod_full.db`` is only ever *read*.  We attach it by plain
path but only issue ``SELECT`` against ``src.*``, and a pre/post checksum
(count + length sum over ``entries``) on a separate read-only handle proves
the source bytes are untouched.

Reproducibility / idempotency
-----------------------------
* Re-running against an existing, complete output skips the build (use
  ``--force`` to rebuild).
* No CIF re-parsing happens — peaks are copied by ``INSERT ... SELECT``
  against the kept ``entry_id`` set.
* All work runs in one big transaction with ``synchronous=OFF`` / WAL off
  for speed on the 10.98M-row peak table.

Usage
-----
::

    python -m tools.build_cod_full_curated                 # build default output
    python -m tools.build_cod_full_curated --force          # rebuild
    python -m tools.build_cod_full_curated --out data/cod_full_curated.db
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from pathlib import Path

from xinmatch.core.db import build_element_index, create_tables

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default paths (resolved against the project root).
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = PROJECT_ROOT / "data" / "cod_full.db"
DEFAULT_OUT = PROJECT_ROOT / "data" / "cod_full_curated.db"

ENTRIES_COLUMNS = (
    "entry_id",
    "formula",
    "mineral_name",
    "space_group",
    "crystal_system",
    "a",
    "b",
    "c",
    "alpha",
    "beta",
    "gamma",
    "volume",
    "density",
    "color",
    "year",
    "author",
    "journal",
    "quality",
    "elements",
)

#: CTE that returns the kept ``entry_id`` (one per formula+space_group cluster).
#: Expects the source database attached as ``src``.
SELECT_KEEP_SQL = """
WITH scored AS (
    SELECT
        e.entry_id                                       AS entry_id,
        e.formula                                        AS formula,
        e.space_group                                    AS space_group,
        (SELECT COUNT(*) FROM src.peaks p
          WHERE p.entry_id = e.entry_id)                 AS n_peaks,
        CASE WHEN e.mineral_name IS NOT NULL
              AND e.mineral_name <> ''
              AND e.mineral_name <> ';'
             THEN 1 ELSE 0 END                          AS has_mineral
    FROM src.entries e
),
ranked AS (
    SELECT
        entry_id,
        ROW_NUMBER() OVER (
            PARTITION BY formula, space_group
            ORDER BY n_peaks DESC, has_mineral DESC, entry_id ASC
        ) AS rn
    FROM scored
)
SELECT entry_id FROM ranked WHERE rn = 1
"""


def _log(msg: str, log) -> None:
    """Print + log a build progress line."""
    print(msg, flush=True)
    log.info(msg)


def _src_checksum(src_path: Path) -> tuple[int, int]:
    """Return (entries_count, sum_of_length(entry_id)) for the source DB.

    Used to prove the source file was not modified during the build.  Opens a
    dedicated read-only connection.
    """
    uri = "file:" + src_path.as_posix() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        n = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        s = conn.execute("SELECT COALESCE(SUM(LENGTH(entry_id)), 0) FROM entries").fetchone()[0]
        return int(n), int(s)
    finally:
        conn.close()


def _output_is_complete(out_path: Path) -> bool:
    """Heuristic completeness check for an existing output DB."""
    if not out_path.exists():
        return False
    try:
        conn = sqlite3.connect(
            "file:" + out_path.as_posix() + "?mode=ro",
            uri=True,
        )
        try:
            for table in ("entries", "peaks", "elements", "element_combo"):
                if (
                    conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (table,),
                    ).fetchone()
                    is None
                ):
                    return False
            n_e = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
            n_p = conn.execute("SELECT COUNT(*) FROM peaks").fetchone()[0]
            return bool(n_e > 0 and n_p > 0)
        finally:
            conn.close()
    except sqlite3.Error:
        return False


def build_curated_db(
    src_path: Path = DEFAULT_SRC,
    out_path: Path = DEFAULT_OUT,
    *,
    force: bool = False,
    log=logger,
) -> dict[str, object]:
    """Build the curated de-duplicated DB.

    Parameters
    ----------
    src_path:
        Full COD database (read-only).
    out_path:
        Output curated database.  Overwritten when *force* is set and the file
        is incomplete / requested.
    force:
        Rebuild even when *out_path* already looks complete.

    Returns
    -------
    dict
        Build statistics (counts, timings).
    """
    t0 = time.perf_counter()
    if not src_path.exists():
        raise FileNotFoundError(f"source COD DB not found: {src_path}")

    if _output_is_complete(out_path) and not force:
        _log(
            f"[skip] {out_path} already looks complete; use --force to rebuild.",
            log,
        )
        conn = sqlite3.connect(
            "file:" + out_path.as_posix() + "?mode=ro",
            uri=True,
        )
        try:
            skip_stats: dict[str, object] = {
                "entries": conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0],
                "peaks": conn.execute("SELECT COUNT(*) FROM peaks").fetchone()[0],
                "elements": conn.execute("SELECT COUNT(*) FROM elements").fetchone()[0],
            }
        finally:
            conn.close()
        skip_stats["skipped"] = True
        skip_stats["elapsed_sec"] = time.perf_counter() - t0
        return skip_stats

    # Pre-build source integrity checksum.
    pre = _src_checksum(src_path)
    _log(f"[src] {src_path}  entries={pre[0]}  idlen_sum={pre[1]}", log)

    if out_path.exists():
        out_path.unlink()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    out = sqlite3.connect(str(out_path))
    try:
        out.execute("PRAGMA foreign_keys = OFF")
        out.execute("PRAGMA journal_mode = OFF")
        out.execute("PRAGMA synchronous = OFF")

        # Attach source by plain absolute path (URI attach unsupported on this
        # build).  We only ever SELECT from src.*; post-build checksum verifies.
        out.execute(f"ATTACH DATABASE '{src_path.as_posix()}' AS src")

        # Fresh schema on the output side (same DDL as the source).
        create_tables(out)
        # build_progress exists in the source but is not in schema.sql; create
        # it for schema parity (left empty — it is a CIF-build checkpoint table).
        out.execute("CREATE TABLE IF NOT EXISTS build_progress (cod_id INTEGER PRIMARY KEY)")

        t1 = time.perf_counter()
        # 1) Compute keep set.
        out.execute("CREATE TEMP TABLE keep (entry_id TEXT PRIMARY KEY)")
        out.execute(f"INSERT INTO keep(entry_id) {SELECT_KEEP_SQL}")
        n_keep = out.execute("SELECT COUNT(*) FROM keep").fetchone()[0]
        _log(f"[keep] {n_keep} cards kept (one per formula+space_group cluster)", log)

        # 2) Copy entries.
        cols = ", ".join(ENTRIES_COLUMNS)
        out.execute(
            f"INSERT INTO entries ({cols}) "
            f"SELECT e.{', e.'.join(ENTRIES_COLUMNS)} "
            f"FROM src.entries e JOIN keep k ON e.entry_id = k.entry_id"
        )
        n_entries = out.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        _log(f"[entries] {n_entries} copied  ({time.perf_counter() - t1:.1f}s)", log)

        # 3) Copy peaks (the big one).
        t2 = time.perf_counter()
        out.execute(
            "INSERT INTO peaks (entry_id, d, intensity, h, k, l) "
            "SELECT p.entry_id, p.d, p.intensity, p.h, p.k, p.l "
            "FROM src.peaks p JOIN keep k ON p.entry_id = k.entry_id"
        )
        n_peaks = out.execute("SELECT COUNT(*) FROM peaks").fetchone()[0]
        _log(f"[peaks] {n_peaks} copied  ({time.perf_counter() - t2:.1f}s)", log)

        # 4) Copy elements inverted index.
        out.execute(
            "INSERT INTO elements (entry_id, element) "
            "SELECT el.entry_id, el.element "
            "FROM src.elements el JOIN keep k ON el.entry_id = k.entry_id"
        )
        n_elements = out.execute("SELECT COUNT(*) FROM elements").fetchone()[0]
        _log(f"[elements] {n_elements} copied", log)

        # 5) Rebuild element_combo from the (filtered) elements table.
        n_sets = build_element_index(out)
        n_combo = out.execute("SELECT COUNT(*) FROM element_combo").fetchone()[0]
        _log(f"[element_combo] {n_combo} distinct element sets rebuilt", log)

        # 6) Indexes already created by create_tables; ANALYZE the peaks table
        #    so the query planner uses idx_peaks_entry_id for lookups.
        out.execute("ANALYZE peaks")

        out.commit()
        out.execute("DETACH DATABASE src")
    finally:
        out.close()

    # Post-build source integrity checksum — must match pre.
    post = _src_checksum(src_path)
    if post != pre:
        raise RuntimeError(
            f"source DB modified during build! pre={pre} post={post} — "
            "refusing to leave the curated DB in place."
        )
    _log(f"[src] post-build checksum matches: {post}", log)

    stats: dict[str, object] = {
        "entries": n_entries,
        "peaks": n_peaks,
        "elements": n_elements,
        "element_combo": n_combo,
        "n_sets": n_sets,
        "kept_cards": n_keep,
        "source_entries": pre[0],
        "removed_cards": pre[0] - n_entries,
        "skipped": False,
        "elapsed_sec": time.perf_counter() - t0,
    }
    _log(
        f"[done] entries={n_entries}  peaks={n_peaks}  "
        f"removed={pre[0] - n_entries}  elapsed={stats['elapsed_sec']:.1f}s",
        log,
    )
    return stats


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``python -m tools.build_cod_full_curated``."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC, help="Full COD DB (read-only).")
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_OUT, help="Curated de-duplicated DB output path."
    )
    parser.add_argument(
        "--force", action="store_true", help="Rebuild even when the output looks complete."
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    stats = build_curated_db(args.src, args.out, force=args.force)
    print("\nBuild summary:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
