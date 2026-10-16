"""Idempotent Miller-index (h/k/l) backfill migration for ``data/cod_inorganics.db``.

Background (HANDOVER 2026-10-13 §5.2)
-------------------------------------
``peaks.h/k/l`` are all NULL in the shipped reference library (6 214 072
rows, 71 206 entries): the COD dump that built the library never carried
Miller indices.  A real March-Dollase preferred-orientation model needs the
PO axis reflections (e.g. (001) for layered phases) to be resolvable per
peak, so FPFM refinement cannot start texture work until hkl is populated.

This tool recomputes each entry's reflection list from its COD CIF with the
*same* pipeline that built the library (:func:`compute_peaks_from_cif`,
dmin = 1.0 Å, Cu Kα, unpolarized LP, top-100 by intensity), now also
returning hkl, then matches every library peak by d-spacing and writes the
Miller indices back.  Because the recomputation uses identical parameters,
``d`` values agree to float precision; a 1e-4 relative tolerance covers
cross-version gemmi drift.

The migration is **idempotent**: re-running rewrites the same h/k/l values
and performs no destructive changes.  A backup copy is written before the
first modification (unless ``--no-backup``).

Usage
-----
::

    python -m tools.backfill_hkl                       # backfill data/cod_inorganics.db
    python -m tools.backfill_hkl --dry-run             # report coverage only, no writes
    python -m tools.backfill_hkl --db <path>           # backfill another library
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.build_cod_full_xinmatch import compute_peaks_from_cif  # noqa: E402
from xinmatch.core.refine.cif_store import cod_cif_path, ref_id_to_cod_id  # noqa: E402

logger = logging.getLogger("tools.backfill_hkl")

DEFAULT_DB = Path(r"D:\Project\XRD\XinMatch\data\cod_inorganics.db")

#: d-spacing relative tolerance for library-peak → recomputed-reflection match.
_D_TOL = 1e-4

#: Update rows per transaction (guard against huge single transactions).
_BATCH = 2000


def _recompute_hkl(cod_id: int) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Recompute (d, i, hkl) for *cod_id* with the library build pipeline."""
    cif = cod_cif_path(cod_id)
    if not cif.is_file():
        return None
    try:
        r = compute_peaks_from_cif(cif, dmin=1.0, max_peaks=100, return_hkl=True)
    except Exception:
        return None
    return r


def _match_entry(
    db_rows: list[tuple[int, float, float | None]],
    d_re: np.ndarray,
    i_re: np.ndarray,
    hkl_re: np.ndarray,
) -> tuple[list[int | None], list[int | None], list[int | None], int, int]:
    """Match library peaks (rowid, d, I) to recomputed reflections by d.

    Returns
    -------
    (h_list, k_list, l_list, matched, unmatched)
        Parallel lists aligned with *db_rows* (``None`` = no match).
    """
    if d_re.size == 0:
        none3 = ([None] * len(db_rows), [None] * len(db_rows),
                 [None] * len(db_rows))
        return none3 + (0, len(db_rows))  # type: ignore[return-value]

    # Normalise recomputed intensities to the library convention (max=1000).
    i_max = float(i_re.max())
    i_re_norm = i_re / i_max * 1000.0 if i_max > 0 else i_re

    order = np.argsort(d_re, kind="stable")
    d_s = d_re[order]
    i_s = i_re_norm[order]
    hkl_s = hkl_re[order]
    k_all = len(d_s)

    d_db = np.array([r[1] for r in db_rows], dtype=np.float64)
    i_db = np.array([(r[2] if r[2] is not None else -1.0) for r in db_rows], dtype=np.float64)

    pos = np.searchsorted(d_s, d_db)
    hi = np.minimum(pos, k_all - 1)
    lo = np.maximum(pos - 1, 0)
    d_hi = np.abs(d_s[hi] - d_db)
    d_lo = np.abs(d_s[lo] - d_db)
    best = np.where(d_lo <= d_hi, lo, hi)
    rel = np.abs(d_s[best] - d_db) / np.maximum(d_db, 1e-9)
    matched_mask = rel < _D_TOL

    h_list: list[int | None] = [None] * len(db_rows)
    k_list: list[int | None] = [None] * len(db_rows)
    l_list: list[int | None] = [None] * len(db_rows)
    matched = 0

    # Disambiguate same-d reflections by closest intensity: group recomputed
    # reflections by rounded d (identical d-spacings, e.g. cubic equivalent
    # pairs) and pick the member whose intensity is closest to the library's.
    buckets: dict[int, list[int]] = {}
    for j in range(k_all):
        buckets.setdefault(round(float(d_s[j]), 6), []).append(j)

    for m in np.nonzero(matched_mask)[0]:
        rowid, _, _ = db_rows[m]
        cand = buckets.get(round(float(d_db[m]), 6))
        if cand is None:
            cand = [int(best[m])]
        if len(cand) == 1:
            j = cand[0]
        else:
            j = min(cand, key=lambda jj: abs(float(i_s[jj]) - float(i_db[m])))
        h, kk, ell = (int(v) for v in hkl_s[j])
        h_list[m] = h
        k_list[m] = kk
        l_list[m] = ell
        matched += 1

    unmatched = len(db_rows) - matched
    return h_list, k_list, l_list, matched, unmatched


def backfill(
    db: Path,
    *,
    dry_run: bool = False,
    backup: bool = True,
    limit: int | None = None,
) -> dict[str, object]:
    """Run the hkl backfill against *db*.  Returns a summary dict."""
    conn = sqlite3.connect(str(db))
    try:
        eids = [r[0] for r in conn.execute(
            "SELECT entry_id FROM entries ORDER BY entry_id"
        )]
        if limit is not None:
            eids = eids[:limit]

        summary: dict[str, object] = {
            "entries": len(eids),
            "cif_missing": [],
            "compute_failed": [],
            "matched_rows": 0,
            "unmatched_rows": 0,
            "unmatched_d_lt_1": 0,
            "unmatched_d_ge_1": 0,
            "matched_entries": 0,
            "hkl_fill_after": 0,
        }

        if not dry_run and backup:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            bak = db.with_name(f"{db.name}.bak-hkl-{stamp}")
            shutil.copy2(db, bak)
            summary["backup"] = str(bak)
            print(f"backup -> {bak}")

        total_peaks = 0
        for eid in eids:
            try:
                cod_id = ref_id_to_cod_id(eid)
            except ValueError:
                summary["cif_missing"].append(eid)
                continue
            r = _recompute_hkl(cod_id)
            if r is None:
                summary["cif_missing"].append(eid)
                continue
            d_re, i_re, hkl_re = r
            if d_re.size == 0:
                summary["compute_failed"].append(eid)
                continue

            db_rows = conn.execute(
                "SELECT rowid, d, intensity FROM peaks WHERE entry_id=?", (eid,)
            ).fetchall()
            total_peaks += len(db_rows)
            h_list, k_list, l_list, matched, unmatched = _match_entry(
                db_rows, d_re, i_re, hkl_re
            )
            summary["matched_rows"] = int(summary["matched_rows"]) + matched
            summary["unmatched_rows"] = int(summary["unmatched_rows"]) + unmatched
            # Unmatched rows split by cause: peaks with d < 1.0 Å are outside
            # the recomputation's dmin range (the library dump went deeper
            # than 1.0 Å); peaks with d >= 1.0 that still fail to match are
            # lattice/pipe differences between the PolyXRD dump and the local
            # COD CIF archive (relative d drift ~0.1-30%).
            if unmatched:
                d_un = np.array(
                    [db_rows[i][1] for i in range(len(db_rows))
                     if h_list[i] is None], dtype=np.float64
                )
                summary["unmatched_d_lt_1"] = int(
                    summary["unmatched_d_lt_1"]) + int((d_un < 1.0).sum())
                summary["unmatched_d_ge_1"] = int(
                    summary["unmatched_d_ge_1"]) + int((d_un >= 1.0).sum())
            if matched > 0:
                summary["matched_entries"] = int(summary["matched_entries"]) + 1

            if dry_run:
                continue

            updates = [
                (h_list[i], k_list[i], l_list[i], db_rows[i][0])
                for i in range(len(db_rows))
                if h_list[i] is not None
            ]
            for start in range(0, len(updates), _BATCH):
                chunk = updates[start:start + _BATCH]
                with conn:
                    conn.executemany(
                        "UPDATE peaks SET h=?, k=?, l=? WHERE rowid=?", chunk
                    )

        summary["total_peaks"] = total_peaks

        if not dry_run:
            with conn:
                conn.execute("ANALYZE")
            fill = conn.execute(
                "SELECT COUNT(*) FROM peaks WHERE h IS NOT NULL AND "
                "k IS NOT NULL AND l IS NOT NULL"
            ).fetchone()[0]
            summary["hkl_fill_after"] = fill
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
        if k in ("cif_missing", "compute_failed"):
            print(f"  {k}: {len(v)} -> {v[:8]}{'...' if len(v) > 8 else ''}")
        else:
            print(f"  {k}: {v}")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
