"""Idempotent unit-cell (a/b/c/α/β/γ/volume) backfill for ``data/cod_inorganics.db``.

Background (HANDOVER 2026-10-13 §5.2 "同批可做")
------------------------------------------------
The COD dump that built the reference library carried cell parameters in
``entries`` that are *almost* identical to the COD CIFs (probed: relative
drift p50 = 0.000%, max ~0.15% on 500 cards) — but ``volume`` is badly
stale for a large share of cards (probed: p99 relative error +37.8%, max
+50.3%), and 15 entries have no cell at all.  Volume feeds density and
any volume-based logic downstream, so the dump value cannot be trusted.

This tool re-derives the authoritative cell for every entry from its COD
CIF (:class:`gemmi.SmallStructure.cell`) and rewrites ``a/b/c/α/β/γ/
volume``.  Cards without a CIF (216) are left untouched and reported.

The migration is **idempotent**: re-running writes identical values.  A
backup copy is written before the first modification (unless
``--no-backup``).

Usage
-----
::

    python -m tools.backfill_cells                       # backfill data/cod_inorganics.db
    python -m tools.backfill_cells --dry-run             # report only, no writes
    python -m tools.backfill_cells --db <path>           # backfill another library
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import gemmi
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xinmatch.core.refine.cif_store import cod_cif_path, ref_id_to_cod_id  # noqa: E402

logger = logging.getLogger("tools.backfill_cells")

DEFAULT_DB = Path(r"D:\Project\XRD\XinMatch\data\cod_inorganics.db")

#: Update rows per transaction.
_BATCH = 2000


def _cell_from_cif(cod_id: int) -> gemmi.UnitCell | None:
    cif = cod_cif_path(cod_id)
    if not cif.is_file():
        return None
    try:
        ss = gemmi.read_small_structure(str(cif))
    except Exception:
        return None
    return ss.cell


def backfill(
    db: Path,
    *,
    dry_run: bool = False,
    backup: bool = True,
    limit: int | None = None,
) -> dict[str, object]:
    """Re-derive ``entries`` cell parameters from CIFs.  Returns a summary."""
    conn = sqlite3.connect(str(db))
    try:
        eids = [r[0] for r in conn.execute(
            "SELECT entry_id FROM entries ORDER BY entry_id"
        )]
        if limit is not None:
            eids = eids[:limit]

        summary: dict[str, object] = {
            "entries": len(eids),
            "updated": 0,
            "cif_missing": [],
            "changed_gt_1e3": 0,   # cards whose a/b/c/volume moved > 0.1%
            "hkl_fill_after": 0,
        }

        if not dry_run and backup:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            bak = db.with_name(f"{db.name}.bak-cells-{stamp}")
            shutil.copy2(db, bak)
            summary["backup"] = str(bak)
            print(f"backup -> {bak}")

        updates: list[tuple[float, float, float, float, float, float, float, str]] = []
        n_moved = 0
        for eid in eids:
            try:
                cod_id = ref_id_to_cod_id(eid)
            except ValueError:
                summary["cif_missing"].append(eid)
                continue
            cell = _cell_from_cif(cod_id)
            if cell is None:
                summary["cif_missing"].append(eid)
                continue

            row = conn.execute(
                "SELECT a, b, c, alpha, beta, gamma, volume FROM entries "
                "WHERE entry_id=?", (eid,)
            ).fetchone()
            old = (row[0], row[1], row[2], row[3], row[4], row[5], row[6])
            new = (float(cell.a), float(cell.b), float(cell.c),
                   float(cell.alpha), float(cell.beta), float(cell.gamma),
                   float(cell.volume))
            # Flag material changes (>0.1% in a/b/c or >1% in volume) for the report.
            changed = (
                any(
                    old[j] is not None and abs(old[j] - new[j]) / new[j] > 1e-3
                    for j in range(6)
                )
                or (
                    old[6] is not None and abs(old[6] - new[6]) / new[6] > 0.01
                )
            )
            if changed:
                n_moved += 1

            updates.append((*new, eid))

        summary["updated"] = len(updates)
        summary["changed_gt_1e3"] = n_moved

        if not dry_run:
            for start in range(0, len(updates), _BATCH):
                chunk = updates[start:start + _BATCH]
                with conn:
                    conn.executemany(
                        "UPDATE entries SET a=?, b=?, c=?, alpha=?, beta=?, "
                        "gamma=?, volume=? WHERE entry_id=?", chunk
                    )
            with conn:
                conn.execute("ANALYZE")
            summary["mode"] = "applied"
        else:
            summary["mode"] = "dry-run"
        return summary
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB,
                        help="reference database to backfill")
    parser.add_argument("--dry-run", action="store_true",
                        help="report coverage without writing")
    parser.add_argument("--no-backup", action="store_true",
                        help="skip the backup copy (not recommended)")
    parser.add_argument("--limit", type=int, default=None,
                        help="restrict to the first N entries (debug)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)
    print(f"db:     {args.db}")
    if not args.db.exists():
        print("[ERR] database not found")
        return 2

    summary = backfill(
        args.db,
        dry_run=args.dry_run,
        backup=not args.no_backup,
        limit=args.limit,
    )
    print("\nsummary:")
    for k, v in summary.items():
        if k == "cif_missing":
            print(f"  {k}: {len(v)} -> {v[:8]}{'...' if len(v) > 8 else ''}")
        else:
            print(f"  {k}: {v}")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
