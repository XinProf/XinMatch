"""Build a full-COD XinMatch reference SQLite from the CIF archive.

This is the *full COD* build entry point (113,223 phases), complementing the
shipped ``cod_inorganics.db`` (71,199 phases, pre-computed peaks).  The source
``cod_index.sqlite`` has no peak table — peaks are computed here from each
entry's CIF with :mod:`gemmi` (Cu Kα, unpolarized Lorentz-polarization factor).

Output
------
A XinMatch-schema SQLite (``entries`` / ``peaks`` / ``elements`` /
``element_combo``) at ``data/cod_full.db`` (overridable with ``--out``), fully
searchable by
:func:`~xinmatch.core.search.search_match.search_match`.

Entry-id convention
-------------------
``entry_id`` is the Match!-style ``96-XXX-XXXX`` id derived from the numeric
COD id, so that :func:`xinmatch.core.refine.cif_store.ref_id_to_cod_id`
round-trips and the CIF archive keeps resolving.  E.g. COD ``5000035`` →
``"96-500-0035"``.

Resumable / batchable
---------------------
The script is designed to be left running in the background:

* ``--start N`` / ``--limit K`` — process COD ids in ``[start, start+K)``;
* ``--resume`` — continue from the highest COD id already present in the
  output DB (a ``build_progress`` bookkeeping table records it);
* progress, throughput (entries/min) and an ETA are logged every
  ``--log-every`` entries;
* entries whose CIF is missing or unparseable are counted and skipped, never
  fatal.

Usage
-----
Full build (hours; run in background)::

    python -m tools.build_cod_full_xinmatch

Small verification slice (a few hundred entries)::

    python -m tools.build_cod_full_xinmatch --limit 500 --out data/cod_full.db
"""

from __future__ import annotations

import argparse
import logging
import math
import sqlite3
import sys
import time
from pathlib import Path

import gemmi
import numpy as np

from xinmatch.core.db import build_element_index, create_tables, insert_entries
from xinmatch.core.model import CellParams, Entry
from xinmatch.core.refine.cif_store import cod_cif_path

logger = logging.getLogger("tools.build_cod_full_xinmatch")

DEFAULT_COD_INDEX = Path(
    r"D:\Project\XRD\PolyXRD\cod_data\cod_index.sqlite"
)
DEFAULT_OUT = Path(r"D:\Project\XRD\XinMatch\data\cod_full.db")

# Cu K-alpha wavelength (Å) used for the Lorentz-polarization factor.
DEFAULT_WAVELENGTH = 1.5406
DEFAULT_DMIN = 1.0  # Å; reference tables rarely go deeper for search-match
DEFAULT_MAX_PEAKS = 100


# ---------------------------------------------------------------------------
# CIF -> d-I pattern
# ---------------------------------------------------------------------------
def compute_peaks_from_cif(
    cif_path: Path,
    *,
    dmin: float = DEFAULT_DMIN,
    wavelength: float = DEFAULT_WAVELENGTH,
    max_peaks: int = DEFAULT_MAX_PEAKS,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Compute a d–I powder pattern from a CIF with gemmi.

    Unique reflections are selected with a reciprocal-space asymmetry unit
    (:class:`gemmi.ReciprocalAsu`); X-ray structure factors are computed with
    :class:`gemmi.StructureFactorCalculatorX` and weighted by the standard
    unpolarized Lorentz-polarization factor.

    Returns
    -------
    (d, i):
        Two float64 arrays sorted by descending intensity, truncated to the
        strongest *max_peaks*.  ``None`` when the CIF cannot be parsed or
        yields no reflections.
    """
    try:
        ss = gemmi.read_small_structure(str(cif_path))
    except Exception as exc:  # gemmi raises on malformed CIFs
        logger.debug("cannot read %s: %s", cif_path, exc)
        return None
    if ss.cell is None or ss.spacegroup is None:
        return None
    try:
        ss.setup_cell_images()
    except Exception:
        return None

    cell = ss.cell
    try:
        hmax, kmax, lmax = cell.get_hkl_limits(dmin)
    except Exception:
        return None
    if hmax <= 0 or kmax <= 0 or lmax <= 0:
        return None

    asu = gemmi.ReciprocalAsu(ss.spacegroup)
    sfc = gemmi.StructureFactorCalculatorX(cell)
    acc: dict[tuple[int, int, int], float] = {}
    for h in range(-hmax, hmax + 1):
        for k in range(-kmax, kmax + 1):
            for ell in range(-lmax, lmax + 1):
                hkl = (h, k, ell)
                try:
                    d = cell.calculate_d(hkl)
                except Exception:
                    continue
                if not np.isfinite(d) or d < dmin:
                    continue
                if not asu.is_in(hkl):
                    continue
                try:
                    f = sfc.calculate_sf_from_small_structure(ss, hkl)
                except Exception:
                    continue
                f2 = float(f.real ** 2 + f.imag ** 2)
                if f2 <= 0.0:
                    continue
                theta = math.asin(min(1.0, wavelength / (2.0 * d)))
                s = math.sin(theta)
                c = math.cos(theta)
                if s <= 0.0 or c <= 0.0:
                    continue
                lp = (1.0 + math.cos(2.0 * theta) ** 2) / (s * s * c)
                acc[hkl] = f2 * lp

    if not acc:
        return None
    items = sorted(acc.items(), key=lambda kv: -kv[1])[:max_peaks]
    d_arr = np.array([cell.calculate_d(hkl) for hkl, _ in items], dtype=np.float64)
    i_arr = np.array([v for _, v in items], dtype=np.float64)
    return d_arr, i_arr


# ---------------------------------------------------------------------------
# Row -> Entry
# ---------------------------------------------------------------------------
def _entry_id_for_cod(cod_id: int) -> str:
    """Numeric COD id → Match!-style ``96-XXX-XXXX`` entry id."""
    s = str(int(cod_id)).zfill(7)
    return f"96-{s[:3]}-{s[3:]}"


def _row_to_entry(row: sqlite3.Row, *, dmin: float, max_peaks: int) -> Entry | None:
    """Convert one ``cod_entries`` row to a XinMatch :class:`Entry`.

    Returns ``None`` when the CIF is missing / unusable.
    """
    cod_id = int(row["cod_id"])
    cif = cod_cif_path(cod_id)
    if not cif.is_file():
        return None
    peaks = compute_peaks_from_cif(cif, dmin=dmin, max_peaks=max_peaks)
    if peaks is None:
        return None
    d_arr, i_arr = peaks

    a = row["a"]
    cell = None
    if a is not None and a > 0:
        cell = CellParams(
            a=float(a),
            b=float(row["b"] or a),
            c=float(row["c"] or a),
            alpha=float(row["alpha"] or 90.0),
            beta=float(row["beta"] or 90.0),
            gamma=float(row["gamma"] or 90.0),
        )

    mineral = str(row["mineral_name"] or "").strip()
    if not mineral or mineral.isdigit():
        mineral = ""
    elements_raw = str(row["elements"] or "")
    elements = frozenset(e.strip() for e in elements_raw.split(",") if e.strip())

    return Entry(
        entry_id=_entry_id_for_cod(cod_id),
        formula=str(row["formula"] or "").strip(),
        d_spacings=d_arr,
        intensities=i_arr,
        mineral_name=mineral or None,
        cell=cell,
        space_group=str(row["space_group"] or "").strip() or None,
        hkl=None,
        literature={"source": "COD full (CIF-computed peaks)"},
        quality="",
        elements=elements,
    )


# ---------------------------------------------------------------------------
# Build driver
# ---------------------------------------------------------------------------
def build(
    out: Path,
    *,
    start: int,
    limit: int | None,
    resume: bool,
    dmin: float,
    max_peaks: int,
    cod_index: Path,
    log_every: int,
) -> dict[str, object]:
    """Run the build.  See module docstring for the argument semantics."""
    out.parent.mkdir(parents=True, exist_ok=True)

    last_done = 0
    if resume and out.exists():
        # Recover the watermark from the previous run.
        existing = sqlite3.connect(str(out))
        try:
            exists = existing.execute(
                "SELECT name FROM sqlite_master WHERE name='build_progress'"
            ).fetchone()
            if exists:
                row = existing.execute(
                    "SELECT MAX(cod_id) FROM build_progress"
                ).fetchone()
                last_done = int(row[0] or 0)
        finally:
            existing.close()
        start = max(start, last_done)

    is_fresh = not out.exists()
    conn = sqlite3.connect(str(out))
    create_tables(conn)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS build_progress (cod_id INTEGER PRIMARY KEY)"
    )

    src = sqlite3.connect("file:" + cod_index.as_posix() + "?mode=ro", uri=True)
    src.row_factory = sqlite3.Row

    total_known = int(src.execute("SELECT COUNT(*) FROM cod_entries WHERE parse_ok=1").fetchone()[0])

    sql = (
        "SELECT cod_id, formula, mineral_name, elements, space_group,"
        " a, b, c, alpha, beta, gamma FROM cod_entries"
        " WHERE parse_ok=1 AND cod_id > ? ORDER BY cod_id ASC"
    )
    args: list[object] = [start]
    if limit is not None:
        sql += " LIMIT ?"
        args.append(int(limit))
    cur = src.execute(sql, args)

    inserted = 0
    skipped_cif = 0
    skipped_no_peaks = 0
    peak_rows = 0
    batch: list[Entry] = []
    batch_size = 200
    t0 = time.perf_counter()
    last_t = t0
    last_inserted = 0

    def flush(up_to: int) -> None:
        nonlocal inserted, peak_rows, last_inserted, last_t
        if not batch:
            return
        inserted += insert_entries(conn, batch)
        peak_rows += sum(e.n_peaks for e in batch)
        with conn:
            conn.executemany(
                "INSERT OR REPLACE INTO build_progress(cod_id) VALUES (?)",
                [(up_to,)],
            )
        batch.clear()
        now = time.perf_counter()
        dt = now - last_t
        done = inserted - last_inserted
        rate = done / dt * 60.0 if dt > 0 else float("inf")
        remaining = (limit - inserted) if limit is not None else None
        eta = f"{remaining / rate:.1f} min" if remaining and rate > 0 else "?"
        logger.info(
            "progress: %d inserted (skip_cif=%d skip_no_peaks=%d peaks=%d) "
            "%.0f entries/min, ETA %s",
            inserted, skipped_cif, skipped_no_peaks, peak_rows, rate, eta,
        )
        last_t = now
        last_inserted = inserted

    current_cod = start
    for row in cur:
        current_cod = int(row["cod_id"])
        cif = cod_cif_path(current_cod)
        if not cif.is_file():
            skipped_cif += 1
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO build_progress(cod_id) VALUES (?)",
                    (current_cod,),
                )
            continue
        entry = _row_to_entry(row, dmin=dmin, max_peaks=max_peaks)
        if entry is None:
            skipped_no_peaks += 1
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO build_progress(cod_id) VALUES (?)",
                    (current_cod,),
                )
            continue
        batch.append(entry)
        if len(batch) >= batch_size:
            flush(current_cod)

    flush(current_cod)

    # Indexes after all entries are in (faster than incremental).
    build_element_index(conn)
    conn.execute("ANALYZE")
    conn.commit()
    conn.close()
    src.close()

    elapsed = time.perf_counter() - t0
    rate = inserted / elapsed * 60.0 if elapsed > 0 else 0.0
    summary: dict[str, object] = {
        "out": str(out),
        "fresh_build": is_fresh,
        "start_cod_id": start,
        "limit": limit,
        "cod_entries_known": total_known,
        "entries_inserted": inserted,
        "skipped_no_cif": skipped_cif,
        "skipped_no_peaks": skipped_no_peaks,
        "peak_rows_total": peak_rows,
        "seconds": round(elapsed, 1),
        "entries_per_min": round(rate, 1),
    }
    logger.info("build done: %s", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--cod-index", type=Path, default=DEFAULT_COD_INDEX)
    p.add_argument("--start", type=int, default=0, help="smallest COD id to process")
    p.add_argument("--limit", type=int, default=None,
                   help="max number of entries to process (None = all)")
    p.add_argument("--resume", action="store_true",
                   help="continue after the highest COD id already in --out")
    p.add_argument("--dmin", type=float, default=DEFAULT_DMIN)
    p.add_argument("--max-peaks", type=int, default=DEFAULT_MAX_PEAKS)
    p.add_argument("--log-every", type=int, default=200)
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not args.cod_index.exists():
        print(f"[ERR] cod_index not found: {args.cod_index}")
        return 2

    summary = build(
        args.out,
        start=args.start,
        limit=args.limit,
        resume=args.resume,
        dmin=args.dmin,
        max_peaks=args.max_peaks,
        cod_index=args.cod_index,
        log_every=args.log_every,
    )
    print("build summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
