"""Build a XinMatch-schema search sidecar on top of the PDF-2 2004 dump.

Why a sidecar?
--------------
``PDF2_2004.sqlite`` (PolyXRD's ICDD PDF-2 2004 dump) stores each phase in a
``phases`` table with pre-parsed ``peaks_d`` / ``peaks_i`` CSV columns, but the
column layout is **not** the XinMatch schema (``entries`` / ``peaks`` /
``elements``).  Rather than search the dump in place (which would force every
search query to know about PDF-2's peculiar schema), we extract the useful
fields once into a native XinMatch-schema database — the *sidecar* — under the
user data directory (:func:`xinmatch.core.db.multi_db.user_data_dir`).

Guarantees
----------
* The source ``PDF2_2004.sqlite`` (and its ``-wal`` / ``-shm`` sidecars) is only
  ever opened **read-only** (``file:...?mode=ro``).  Nothing here writes into
  the PolyXRD directory.
* The sidecar is a fresh file at
  :func:`xinmatch.core.db.multi_db.pdf2_sidecar_path`; rebuilding deletes and
  recreates it in place.
* After the build, :func:`xinmatch.core.db.multi_db.open_library` with id
  ``"pdf2_2004"`` returns a connection identical in shape to the default
  library's, so :func:`~xinmatch.core.search.search_match.search_match` and
  :func:`~xinmatch.core.search.search_match.fetch_entries_by_ids` work
  unchanged.

Mapping decisions (verified against the real 163,834-row dump)
----------------------------------------------------------------
* **entry_id = ``ref_id``** (e.g. ``"PDF2-010649"``).  It is unique
  (163,834 distinct / 163,834 rows, zero NULLs) and ``display_id`` is always
  identical (0 rows differ), so ``ref_id`` is both unique and meaningful.
* **mineral_name** = ``mineral`` when non-empty, else ``name`` (e.g. quartz
  rows carry ``mineral="Quartz"``; organics carry ``name="Sodium hippurate"``).
* Peaks: ``peaks_d`` / ``peaks_i`` are comma-separated float strings; rows
  with d <= 0 or non-finite values are dropped, the strongest ``--max-peaks``
  (default 100) reflections are kept, sorted by descending intensity (the reference software
  reference-table convention).
* The number reported to the GUI is the sidecar's ``entries`` count
  (== number of phases that had a usable peak table).  The source
  ``phases`` total (163,834) is stored in ``pdf2_meta`` for the two numbers
  never to be confused.

One-off build
-------------
::

    python -m xinmatch.core.db.pdf2_index
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

from xinmatch.core.db import build_element_index, create_tables, insert_entries
from xinmatch.core.db.multi_db import (
    pdf2_sidecar_path,
    pdf2_source_path,
)
from xinmatch.core.model import CellParams, Entry

logger = logging.getLogger("xinmatch.core.db.pdf2_index")

#: Columns read from the source ``phases`` table, in the order selected.
_SOURCE_COLUMNS = (
    "cod_id, ref_id, formula, name, mineral, space_group,"
    " cell_a, cell_b, cell_c, cell_alpha, cell_beta, cell_gamma,"
    " peaks_d, peaks_i, n_peaks"
)


def parse_csv_floats(text: str | None) -> np.ndarray:
    """Parse a ``"1.2,3.4,..."`` CSV string into a float array.

    Returns an empty array for ``None`` / whitespace / unparseable input so
    that a single bad row never aborts the whole build.
    """
    if not text or not str(text).strip():
        return np.empty(0, dtype=np.float64)
    try:
        return np.fromstring(str(text), sep=",", dtype=np.float64)
    except ValueError:
        return np.empty(0, dtype=np.float64)


def entry_from_row(
    row: sqlite3.Row,
    *,
    max_peaks: int,
) -> Entry | None:
    """Convert one PDF-2 ``phases`` row to a XinMatch :class:`Entry`.

    Returns ``None`` when the row carries no usable peak table.
    """
    ref_id = str(row["ref_id"]).strip()
    formula = str(row["formula"] or "").strip()
    d = parse_csv_floats(row["peaks_d"])
    i = parse_csv_floats(row["peaks_i"])
    if d.size == 0 or i.size == 0:
        return None
    n = min(d.size, i.size)
    d, i = d[:n], i[:n]
    mask = (d > 0.0) & np.isfinite(d) & np.isfinite(i)
    d, i = d[mask], i[mask]
    if d.size == 0:
        return None
    order = np.argsort(-i, kind="stable")[:max_peaks]
    d_sorted = d[order]
    i_sorted = i[order]

    cell = None
    if row["cell_a"] is not None:
        cell = CellParams(
            a=float(row["cell_a"]),
            b=float(row["cell_b"] or row["cell_a"]),
            c=float(row["cell_c"] or row["cell_a"]),
            alpha=float(row["cell_alpha"] or 90.0),
            beta=float(row["cell_beta"] or 90.0),
            gamma=float(row["cell_gamma"] or 90.0),
        )

    mineral = str(row["mineral"] or "").strip()
    name = str(row["name"] or "").strip()
    mineral_name = mineral or name or None
    sg = str(row["space_group"] or "").strip() or None

    return Entry(
        entry_id=ref_id,
        formula=formula,
        d_spacings=d_sorted,
        intensities=i_sorted,
        mineral_name=mineral_name,
        cell=cell,
        space_group=sg,
        hkl=None,
        literature={"source": "ICDD PDF-2 2004 (via PolyXRD dump)"},
        quality="",
    )


def _open_source_ro(src: Path) -> sqlite3.Connection:
    """Open the PDF-2 source dump read-only; never write to it.

    The URI is percent-encoded via ``Path.as_uri`` (see
    :func:`xinmatch.core.db.multi_db._readonly_uri`) so spaces / ``#`` / ``?``
    / non-ASCII characters in the path cannot truncate it.
    """
    try:
        uri = src.resolve().as_uri() + "?mode=ro"
    except ValueError:  # pragma: no cover - relative path, defensive
        uri = "file:" + src.as_posix() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def build_pdf2_index(
    out: Path | None = None,
    *,
    max_peaks: int = 100,
    limit: int | None = None,
) -> dict[str, int | float | str]:
    """Build the XinMatch-schema sidecar for the PDF-2 dump.

    Parameters
    ----------
    out:
        Sidecar path (default :func:`pdf2_sidecar_path`).  Existing file is
        deleted and rebuilt.
    max_peaks:
        Strongest reflections kept per entry.
    limit:
        If given, only process the first *limit* source rows (used for
        smoke-testing / CI-sized builds; the real build processes all 163,834).

    Returns
    -------
    dict
        Build summary: source_rows, entries_indexed, entries_skipped,
        peak_rows_total, seconds.
    """
    out = Path(out) if out is not None else pdf2_sidecar_path()
    src = pdf2_source_path()
    if not src.exists():
        raise FileNotFoundError(f"PDF-2 source dump not found: {src}")

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    for sidecar in (out.with_suffix(out.suffix + "-wal"), out.with_suffix(out.suffix + "-shm")):
        if sidecar.exists():
            sidecar.unlink()

    t0 = time.perf_counter()
    sconn = _open_source_ro(src)
    total_src = int(sconn.execute("SELECT COUNT(*) FROM phases").fetchone()[0])

    conn = sqlite3.connect(str(out))
    create_tables(conn)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS pdf2_meta (key TEXT PRIMARY KEY, value TEXT)"
    )

    sql = f"SELECT {_SOURCE_COLUMNS} FROM phases"
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    cur = sconn.execute(sql)

    inserted = 0
    skipped = 0
    peak_rows = 0
    batch: list[Entry] = []
    batch_size = 2000

    def flush() -> None:
        nonlocal inserted, peak_rows
        if not batch:
            return
        inserted += insert_entries(conn, batch)
        peak_rows += sum(e.n_peaks for e in batch)
        batch.clear()

    for row in cur:
        entry = entry_from_row(row, max_peaks=max_peaks)
        if entry is None:
            skipped += 1
            continue
        batch.append(entry)
        if len(batch) >= batch_size:
            flush()
            logger.info("indexed %d / %d", inserted, total_src)
    flush()

    build_element_index(conn)
    conn.execute("ANALYZE")
    with conn:
        conn.executemany(
            "INSERT OR REPLACE INTO pdf2_meta(key, value) VALUES (?,?)",
            [
                ("source_path", str(src)),
                ("source_rows", str(total_src)),
                ("entries_indexed", str(inserted)),
                ("entries_skipped", str(skipped)),
                ("max_peaks", str(max_peaks)),
                ("built_at", str(int(time.time()))),
            ],
        )
    conn.close()
    sconn.close()
    elapsed = time.perf_counter() - t0

    summary: dict[str, int | float | str] = {
        "source_rows": total_src,
        "entries_indexed": inserted,
        "entries_skipped": skipped,
        "peak_rows_total": peak_rows,
        "seconds": round(elapsed, 2),
        "out": str(out),
    }
    logger.info("PDF-2 sidecar built: %s", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=None,
                        help="sidecar output path (default: user-data indexes dir)")
    parser.add_argument("--max-peaks", type=int, default=100)
    parser.add_argument("--limit", type=int, default=None,
                        help="only process the first N source rows (smoke test)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    summary = build_pdf2_index(out=args.out, max_peaks=args.max_peaks, limit=args.limit)
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
