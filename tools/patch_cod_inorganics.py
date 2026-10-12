"""Idempotent data-repair migration for ``data/cod_inorganics.db`` (v1.4.0 / T14).

Background — what the v1.4.0 无机库构建逻辑排查 found
-----------------------------------------------------
1. **Ambient textbook-phase cards missing.**  A previous session patched four
   "textbook phases" into the library from ``cod_full.db``, but picked COD
   entries that are *non-ambient-condition variants* — e.g. ``96-900-6388``
   is NaCl at 100 K / high pressure (CIF: ``a = 5.8447``, Wang & Reeber
   1996), ``96-900-3133`` KCl with ``a = 6.422`` (ambient 6.2931),
   ``96-900-6475`` MgO with ``a = 4.3741`` (ambient 4.212).  Their
   d-spacings therefore cannot match any ambient measurement.  The upstream
   PolyXRD inorganics dump contains **zero** pure ``Cl Na`` / ``Cl K`` /
   ``Mg O`` entries, so a plain rebuild does not help either.  This tool
   inserts the ambient COD entries (verified against textbook lattice
   constants) instead.
2. **Un-normalised intensities.**  Ten cards store raw structure-factor
   scales (up to 9.5e8) instead of the library convention max = 1000.  FoM
   scoring is scale-invariant (both sides normalise by their own max), so
   this is cosmetic — but the GUI and any absolute-threshold logic expect
   the convention.
3. **Phantom peaks.**  52 366 reflections with ``intensity < 1e-40``
   (systematically absent reflections kept by the build's ``d > 0`` filter)
   across 9 629 entries.  The library's intensity distribution is sharply
   bimodal — there is not a single peak between 1e-20 and 0.01 — so a
   1e-6 floor removes exactly the numerical residue and touches no real
   line.  Removing them restores the reference-software card convention
   (only physically observable reflections) and stops junk candidates from
   correlating against absent reflections.

Ambient entries inserted (all verified against textbook values)
--------------------------------------------------------------
====== ============ ======= ============================================
cod_id mineral      formula  note
====== ============ ======= ============================================
9003308 Halite      Cl Na    a = 5.6401 Å (ambient halite 5.6402)
9003112 Sylvite     Cl K     a = 6.2879 Å (ambient sylvite 6.2931)
9000501 Periclase   Mg O     a = 4.212 Å  (ambient periclase 4.212)
====== ============ ======= ============================================

Peak tables are computed from the COD CIF archive with the same
``compute_peaks_from_cif`` pipeline that built ``cod_full.db``
(``dmin = 1.0`` Å, top 100 by intensity), normalised to max = 1000, and
filtered at ``I >= 0.01`` (drops the ~0-intensity forbidden reflections the
CIF calculator emits for F-centred cells).

The migration is **idempotent**: re-running performs no further writes
(steps 2–4 find nothing to fix; step 1 replaces the same rows).  A backup
copy of the database is written before the first modification.

Usage
-----
::

    python -m tools.patch_cod_inorganics                 # patch data/cod_inorganics.db
    python -m tools.patch_cod_inorganics --dry-run       # report only, no writes
    python -m tools.patch_cod_inorganics --db <path>     # patch another library
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
from xinmatch.core.db import build_element_index, insert_entries  # noqa: E402
from xinmatch.core.model import CellParams, Entry  # noqa: E402
from xinmatch.core.refine.cif_store import cod_cif_path  # noqa: E402

logger = logging.getLogger("tools.patch_cod_inorganics")

DEFAULT_DB = Path(r"D:\Project\XRD\XinMatch\data\cod_inorganics.db")
DEFAULT_COD_INDEX = Path(r"D:\Project\XRD\PolyXRD\cod_data\cod_index.sqlite")

#: Ambient textbook-phase COD ids to insert (see module docstring).
AMBIENT_COD_IDS: tuple[int, ...] = (9003308, 9003112, 9000501)

#: Intensity floor (library convention: max = 1000) — drops the ~0
#: forbidden reflections the CIF calculator emits (e.g. periclase 211).
_MIN_INTENSITY = 0.01

#: Phantom-peak deletion threshold (absolute, library scale).
_PHANTOM_INTENSITY = 1e-6

#: Cards are re-normalised only above this max (1000 + slack for float noise).
_NORMALISE_ABOVE = 1000.5


def _entry_id_for_cod(cod_id: int) -> str:
    """Numeric COD id → reference-software-style ``96-XXX-XXXX`` entry id."""
    s = str(int(cod_id)).zfill(7)
    return f"96-{s[:3]}-{s[3:]}"


def _ambient_entry(cod_id: int, index_conn: sqlite3.Connection) -> Entry | None:
    """Build the ambient :class:`Entry` for *cod_id* from CIF + COD index."""
    row = index_conn.execute(
        "SELECT formula, mineral_name, space_group, a, b, c,"
        " alpha, beta, gamma FROM cod_entries WHERE cod_id=?",
        (cod_id,),
    ).fetchone()
    if row is None:
        logger.error("cod_id %d not found in COD index", cod_id)
        return None
    formula, mineral, sg, a, b, c, alpha, beta, gamma = row

    cif = cod_cif_path(cod_id)
    if not cif.is_file():
        logger.error("CIF missing for cod_id %d (%s)", cod_id, cif)
        return None
    peaks = compute_peaks_from_cif(cif, dmin=1.0, max_peaks=100)
    if peaks is None:
        logger.error("no peaks computed for cod_id %d", cod_id)
        return None
    d_arr, i_arr = peaks
    if d_arr.size == 0:
        logger.error("empty peak table for cod_id %d", cod_id)
        return None

    # Normalise to the library convention (max = 1000) and drop the ~0
    # forbidden reflections (F-centred cells: e.g. periclase 211).
    i_norm = np.asarray(i_arr / i_arr.max() * 1000.0, dtype=np.float64)
    keep = i_norm >= _MIN_INTENSITY
    d_arr = np.asarray(d_arr[keep], dtype=np.float64)
    i_norm = np.asarray(i_norm[keep], dtype=np.float64)

    cell = None
    if a is not None and float(a) > 0:
        cell = CellParams(
            a=float(a),
            b=float(b or a),
            c=float(c or a),
            alpha=float(alpha or 90.0),
            beta=float(beta or 90.0),
            gamma=float(gamma or 90.0),
        )
    return Entry(
        entry_id=_entry_id_for_cod(cod_id),
        formula=str(formula or "").strip(),
        d_spacings=d_arr,
        intensities=i_norm,
        mineral_name=(str(mineral).strip() or None) if mineral else None,
        cell=cell,
        space_group=(str(sg).strip() or None) if sg else None,
        literature={"source": "COD ambient textbook patch (v1.4.0)"},
        quality="",
    )


def _replace_entry(conn: sqlite3.Connection, entry: Entry) -> None:
    """Insert *entry*, replacing any previous rows (idempotent re-runs)."""
    with conn:
        conn.execute("DELETE FROM peaks WHERE entry_id=?", (entry.entry_id,))
        conn.execute("DELETE FROM elements WHERE entry_id=?", (entry.entry_id,))
    insert_entries(conn, [entry])


def patch(
    db: Path,
    cod_index: Path,
    *,
    dry_run: bool = False,
    backup: bool = True,
) -> dict[str, object]:
    """Run the migration against *db*.  Returns a summary dict."""
    summary: dict[str, object] = {}

    # ---- read-only survey (always runs; drives both dry-run and apply) ----
    idx = sqlite3.connect(f"file:{cod_index.as_posix()}?mode=ro", uri=True)
    entries: list[Entry] = []
    for cod_id in AMBIENT_COD_IDS:
        e = _ambient_entry(cod_id, idx)
        if e is None:
            raise RuntimeError(f"cannot build ambient entry for cod_id {cod_id}")
        entries.append(e)
    idx.close()
    summary["ambient_inserted"] = [
        {"entry_id": e.entry_id, "formula": e.formula,
         "mineral": e.mineral_name, "n_peaks": e.n_peaks}
        for e in entries
    ]

    conn = sqlite3.connect(db)
    try:
        unnormalised = conn.execute(
            """
            SELECT entry_id, MAX(intensity) FROM peaks GROUP BY entry_id
            HAVING MAX(intensity) > ?
            """,
            (_NORMALISE_ABOVE,),
        ).fetchall()
        summary["unnormalised_cards"] = len(unnormalised)
        summary["unnormalised_ids"] = [r[0] for r in unnormalised]

        phantom = conn.execute(
            "SELECT COUNT(*) FROM peaks WHERE intensity < ?",
            (_PHANTOM_INTENSITY,),
        ).fetchone()[0]
        summary["phantom_peaks"] = phantom

        if dry_run:
            summary["mode"] = "dry-run"
            return summary

        if backup:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            bak = db.with_name(f"{db.name}.bak-{stamp}")
            shutil.copy2(db, bak)
            summary["backup"] = str(bak)
            print(f"backup -> {bak}")

        # 1. ambient textbook cards (INSERT OR REPLACE semantics).
        for e in entries:
            _replace_entry(conn, e)
            print(
                f"ambient card {e.entry_id} ({e.formula}"
                + (f", {e.mineral_name}" if e.mineral_name else "")
                + f"): {e.n_peaks} peaks, d {e.d_spacings.min():.3f}-"
                f"{e.d_spacings.max():.3f} A, Imax={e.intensity_max:.1f}"
            )

        # 2. re-normalise un-normalised cards to the max=1000 convention.
        for entry_id, mx in unnormalised:
            with conn:
                conn.execute(
                    "UPDATE peaks SET intensity = intensity * ? WHERE entry_id=?",
                    (1000.0 / float(mx), entry_id),
                )
            print(f"normalised {entry_id}: Imax {mx:.4g} -> 1000")
        summary["normalised_cards"] = len(unnormalised)

        # 3. drop phantom peaks (systematically-absent reflections).
        with conn:
            cur = conn.execute(
                "DELETE FROM peaks WHERE intensity < ?", (_PHANTOM_INTENSITY,)
            )
        summary["phantom_deleted"] = cur.rowcount
        print(f"dropped {cur.rowcount} phantom peaks (I < {_PHANTOM_INTENSITY:g})")

        # 4. refresh derived structures.
        n_sets = build_element_index(conn)
        conn.execute("ANALYZE")
        conn.commit()
        summary["element_sets"] = n_sets
        print(f"rebuilt element index ({n_sets} element sets) + ANALYZE")
    finally:
        conn.close()

    summary["mode"] = "applied"
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB,
                        help="reference database to patch")
    parser.add_argument("--cod-index", type=Path, default=DEFAULT_COD_INDEX,
                        help="COD index sqlite (card metadata source)")
    parser.add_argument("--dry-run", action="store_true",
                        help="report findings without writing")
    parser.add_argument("--no-backup", action="store_true",
                        help="skip the backup copy (not recommended)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)
    print(f"db:     {args.db}")
    print(f"index:  {args.cod_index}")
    if not args.db.exists():
        print("[ERR] database not found")
        return 2
    if not args.cod_index.exists():
        print("[ERR] COD index not found")
        return 2

    summary = patch(
        args.db, args.cod_index,
        dry_run=args.dry_run, backup=not args.no_backup,
    )
    print("\nsummary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
