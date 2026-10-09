"""Build the XinMatch reference SQLite from the PolyXRD COD_inorganics dump.

Converts the 71,199 inorganic COD entries of
``D:\\Project\\XRD\\PolyXRD\\cod_data\\COD_inorganics.sqlite`` (parsed d–I
peak tables, cell parameters, space group — produced by the sibling
PolyXRD project from the 522 K COD CIF archive) into the XinMatch
schema (``entries`` / ``peaks`` / ``elements``).

Key design decision — **entry_id = COD ref_id**.  PolyXRD stores each
phase with a ``ref_id`` such as ``96-400-1849``, the same id format that
Match! writes into its candidate-list CSVs.  Using it as the XinMatch
``entry_id`` means the L3 golden-baseline comparison
(``tools/match_baseline.py``) can match on **exact entry_id equality**
instead of composition-normalised formulas.

Peak-table conventions (Match! / XinMatch):

* peaks are ordered by **descending intensity** (Match! reference-table
  convention; PolyXRD's CSV is d-descending, so we re-sort);
* only the strongest ``--max-peaks`` (default 100) reflections are kept
  per entry — the same order of magnitude as Match!'s reference tables
  and enough for d-window search-match (``search_by_d``);
* d ≤ 0 or intensity < 0 rows are dropped.

Usage
-----
::

    python -m tools.build_cod_xinmatch \
        --source "D:\\Project\\XRD\\PolyXRD\\cod_data\\COD_inorganics.sqlite" \
        --out "D:\\Project\\XRD\\XinMatch\\data\\cod_inorganics.db"

Prints a build summary (entries inserted / skipped / peak rows) and
exits 0 on success.
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

import numpy as np

from xinmatch.core.db import build_element_index, create_tables, insert_entries
from xinmatch.core.model import CellParams, Entry

logger = logging.getLogger("tools.build_cod_xinmatch")

DEFAULT_SOURCE = Path(
    r"D:\Project\XRD\PolyXRD\cod_data\COD_inorganics.sqlite"
)
DEFAULT_OUT = Path(r"D:\Project\XRD\XinMatch\data\cod_inorganics.db")


def parse_csv_floats(text: str | None) -> np.ndarray:
    """Parse a ``"1.2,3.4,..."`` CSV string into a float array."""
    if not text or not text.strip():
        return np.empty(0, dtype=np.float64)
    try:
        return np.fromstring(text, sep=",", dtype=np.float64)
    except ValueError:
        return np.empty(0, dtype=np.float64)


def entry_from_row(
    row: tuple,
    *,
    max_peaks: int,
    col: dict[str, int],
) -> Entry | None:
    """Convert one PolyXRD ``phases`` row into a XinMatch :class:`Entry`.

    Returns ``None`` when the row carries no usable peak table (empty or
    all-negative intensities).
    """
    ref_id = str(row[col["ref_id"]]).strip()
    formula = str(row[col["formula"]] or "").strip()
    d = parse_csv_floats(row[col["peaks_d"]])
    i = parse_csv_floats(row[col["peaks_i"]])
    if d.size == 0 or i.size == 0:
        return None
    # Align (some rows have mismatched list lengths — truncate to the
    # shorter one and keep only physically meaningful rows).
    n = min(d.size, i.size)
    d, i = d[:n], i[:n]
    mask = (d > 0.0) & np.isfinite(d) & np.isfinite(i)
    d, i = d[mask], i[mask]
    if d.size == 0:
        return None
    # Sort by intensity descending, keep the strongest max_peaks.
    order = np.argsort(-i, kind="stable")[:max_peaks]
    d_sorted = d[order]
    i_sorted = i[order]

    cell = None
    a = row[col["cell_a"]]
    if a is not None:
        cell = CellParams(
            a=float(a),
            b=float(row[col["cell_b"]] or a),
            c=float(row[col["cell_c"]] or a),
            alpha=float(row[col["cell_alpha"]] or 90.0),
            beta=float(row[col["cell_beta"]] or 90.0),
            gamma=float(row[col["cell_gamma"]] or 90.0),
        )

    sg = str(row[col["space_group"]] or "").strip() or None
    return Entry(
        entry_id=ref_id,
        formula=formula,
        d_spacings=d_sorted,
        intensities=i_sorted,
        mineral_name=None,
        cell=cell,
        space_group=sg,
        hkl=None,
        literature={"source": "COD (via PolyXRD inorganics dump)"},
        quality="",
    )


def build(
    source: Path,
    out: Path,
    *,
    max_peaks: int,
) -> dict[str, int]:
    """Convert the PolyXRD dump into the XinMatch SQLite at *out*."""
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    src = sqlite3.connect(source)
    src.row_factory = sqlite3.Row
    conn = sqlite3.connect(out)
    create_tables(conn)

    rows = src.execute(
        "SELECT cod_id, ref_id, formula, space_group,"
        " cell_a, cell_b, cell_c, cell_alpha, cell_beta, cell_gamma,"
        " peaks_d, peaks_i, n_peaks"
        " FROM phases"
    )
    col = {name: idx for idx, name in enumerate(
        ["cod_id", "ref_id", "formula", "space_group",
         "cell_a", "cell_b", "cell_c", "cell_alpha", "cell_beta",
         "cell_gamma", "peaks_d", "peaks_i", "n_peaks"])}
    # NOTE: sqlite3.Row rows are already column-addressable; the tuple
    # column index map is used for the plain-tuple fallback.

    inserted = 0
    skipped_empty = 0
    peak_rows_total = 0
    batch: list[Entry] = []
    BATCH = 5000

    def flush() -> None:
        nonlocal inserted, peak_rows_total
        if not batch:
            return
        n = insert_entries(conn, batch)
        inserted += n
        peak_rows_total += sum(e.n_peaks for e in batch)
        batch.clear()

    for row in rows:
        entry = entry_from_row(
            tuple(row),
            max_peaks=max_peaks,
            col=col,
        )
        if entry is None:
            skipped_empty += 1
            continue
        batch.append(entry)
        if len(batch) >= BATCH:
            flush()
    flush()

    build_element_index(conn)
    conn.commit()
    conn.execute("ANALYZE")
    conn.close()
    src.close()

    summary = {
        "entries_inserted": inserted,
        "skipped_empty": skipped_empty,
        "peak_rows_total": peak_rows_total,
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-peaks", type=int, default=100,
                        help="strongest reflections kept per entry (default 100)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)
    print(f"source: {args.source}")
    print(f"out:    {args.out}")
    if not args.source.exists():
        print(f"[ERR] source not found: {args.source}")
        return 2

    summary = build(args.source, args.out, max_peaks=args.max_peaks)
    print("build summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
