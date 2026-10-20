"""Acceptance probe for a XinMatch / 3COD reference database.

Fast by default (schema, row counts, source split, fill rates).  The slower
sections are opt-in so the default run stays under a minute on a 20 GB file.

Usage
-----
    python tools/acceptance_3cod.py <db.sqlite>
    python tools/acceptance_3cod.py <db.sqlite> --coverage --selectivity
    python tools/acceptance_3cod.py <db.sqlite> --dbstat

Sections
--------
schema        table list, row counts, PRAGMA page stats
meta          `meta` key/value dump (build provenance)
sources       entry split by COD / PCOD / TCOD from the entry_id range
fill          formula / mineral / space group / cell coverage
coverage      entries that have no peaks (invisible to peak search)   [--coverage]
selectivity   rows and distinct entries inside a 2-theta window       [--selectivity]
dbstat        per-table storage via the dbstat virtual table          [--dbstat]
"""

from __future__ import annotations

import argparse
import math
import sqlite3
import time
from pathlib import Path

WAVELENGTH = 1.5406
PROBE_D = (4.2, 3.1, 2.46, 2.13)
WINDOW_DEG = (0.30, 0.20, 0.10, 0.05, 0.02)

# Entry ids look like 96-100-0003; the numeric part encodes the origin because
# the builder offset PCOD by +2e7 and TCOD by +1e8.
SRC_SQL = """
SELECT CASE WHEN v >= 100000000 THEN 'TCOD'
            WHEN v >= 20000000  THEN 'PCOD'
            ELSE 'COD' END AS src,
       COUNT(*) AS n
FROM (SELECT CAST(replace(substr(entry_id, 4), '-', '') AS INTEGER) AS v
      FROM entries)
GROUP BY 1 ORDER BY 2 DESC
"""


def ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)


def window(d: float, wdeg: float) -> tuple[float, float]:
    theta = math.asin(min(1.0, WAVELENGTH / (2.0 * d)))
    half = math.radians(wdeg / 2.0)
    hi_sin = math.sin(min(math.pi / 2.0, theta + half))
    d_lo = WAVELENGTH / (2.0 * hi_sin) if hi_sin > 0 else 0.0
    lo_sin = math.sin(theta - half)
    d_hi = 1e9 if lo_sin <= 0 else WAVELENGTH / (2.0 * lo_sin)
    return d_lo, d_hi


def section_schema(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    print("== schema")
    names = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name"
    )]
    for name in names:
        n = cur.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        print(f"   {name:24s} {n:>14,}")
    page = cur.execute("PRAGMA page_size").fetchone()[0]
    count = cur.execute("PRAGMA page_count").fetchone()[0]
    free = cur.execute("PRAGMA freelist_count").fetchone()[0]
    print(f"   page_size={page} pages={count:,} freelist={free:,} "
          f"-> {page * count / 2**30:.2f} GiB")


def section_meta(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    if cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'"
    ).fetchone() is None:
        return
    print("== meta")
    for k, v in cur.execute("SELECT key, value FROM meta ORDER BY key"):
        print(f"   {k:24s} {str(v or '')[:96]}")


def section_sources(con: sqlite3.Connection) -> None:
    print("== sources (entry_id range)")
    total = 0
    rows = con.execute(SRC_SQL).fetchall()
    for _src, n in rows:
        total += n
    for src, n in rows:
        print(f"   {src:5s} {n:>12,}  {n / total * 100:5.1f} %")


def section_fill(con: sqlite3.Connection) -> None:
    print("== fill rates")
    row = con.execute(
        "SELECT COUNT(*),"
        " SUM(formula IS NULL OR formula=''),"
        " SUM(mineral_name IS NULL OR mineral_name=''),"
        " SUM(space_group IS NULL OR space_group=''),"
        " SUM(a IS NULL OR a<=0),"
        " SUM(elements IS NULL OR elements='')"
        " FROM entries"
    ).fetchone()
    labels = ("entries", "no_formula", "no_mineral", "no_spacegroup", "no_cell",
              "no_elements")
    for label, val in zip(labels, row, strict=True):
        print(f"   {label:16s} {val:>12,}")


def section_coverage(con: sqlite3.Connection) -> None:
    print("== coverage (slow: one index probe per entry)")
    t0 = time.time()
    total = con.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    missing = con.execute(
        "SELECT COUNT(*) FROM entries e "
        "WHERE NOT EXISTS (SELECT 1 FROM peaks p WHERE p.entry_id = e.entry_id)"
    ).fetchone()[0]
    print(f"   entries without peaks {missing:,} / {total:,} "
          f"({missing / total * 100:.2f} %)  [{time.time() - t0:.0f}s]")


def section_selectivity(con: sqlite3.Connection) -> None:
    print("== selectivity (2-theta window vs candidate volume)")
    print(f"   {'wdeg':>6s} {'rows/win':>12s} {'entries/win':>13s} {'sec/win':>9s}")
    for wdeg in WINDOW_DEG:
        rows = ents = 0
        t0 = time.time()
        for d in PROBE_D:
            lo, hi = window(d, wdeg)
            r, e = con.execute(
                "SELECT COUNT(*), COUNT(DISTINCT entry_id) FROM peaks "
                "WHERE d BETWEEN ? AND ?", (lo, hi),
            ).fetchone()
            rows += r
            ents += e
        dt = (time.time() - t0) / len(PROBE_D)
        print(f"   {wdeg:6.2f} {rows / len(PROBE_D):12,.0f} "
              f"{ents / len(PROBE_D):13,.0f} {dt:9.2f}")


def section_dbstat(con: sqlite3.Connection) -> None:
    print("== dbstat (slow: walks every page)")
    try:
        rows = con.execute(
            "SELECT name, SUM(pgsize) AS s FROM dbstat GROUP BY name ORDER BY s DESC"
        ).fetchall()
    except sqlite3.Error as exc:
        print("   dbstat unavailable:", exc)
        return
    total = sum(r[1] for r in rows)
    for name, size in rows:
        if size < 2**20:
            continue
        print(f"   {name:32s} {size / 2**30:7.2f} GiB  {size / total * 100:5.1f} %")
    print(f"   {'TOTAL':32s} {total / 2**30:7.2f} GiB")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("db", type=Path)
    ap.add_argument("--coverage", action="store_true")
    ap.add_argument("--selectivity", action="store_true")
    ap.add_argument("--dbstat", action="store_true")
    args = ap.parse_args()

    if not args.db.is_file():
        ap.error(f"not a file: {args.db}")
    con = ro(args.db)
    print(f"# {args.db.name}  {args.db.stat().st_size / 2**30:.2f} GiB")
    section_schema(con)
    section_meta(con)
    section_sources(con)
    section_fill(con)
    if args.coverage:
        section_coverage(con)
    if args.selectivity:
        section_selectivity(con)
    if args.dbstat:
        section_dbstat(con)
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
