"""Search-match baseline benchmark for the v3.0.0 ``.xinDB`` rebuild (M0 / S0.2).

Purpose
-------
Before touching the database format we need a *ruler*: a reproducible set of
measurements that says "with the current library the search-match returns X".
The v3 rebuild is only allowed to be **as accurate or better** than this
ruler (see the accuracy guardrails in the rebuild plan).

Method
------
For each standard phase we build a **synthetic experimental pattern** from the
phase's own reference peaks:

* take the phase's strongest reference peaks,
* perturb the 2θ positions slightly (a fixed pseudo-random jitter) so the
  pattern is not a bit-exact copy of the library row — a retrieval that only
  worked on exact matches would be useless,
* rescale the intensities to a realistic profile,
* run the real :func:`~xinmatch.core.search.search_match.search_match` against
  the library under test,
* record whether the phase is found at rank 1, in the top 10, and the wall
  time.

The synthetic patterns are deterministic (fixed seed), so the baseline is
reproducible across runs and machines.

Usage
-----
::

    python -m tools.bench_search_v3 --db data/cod_inorganics.db
    python -m tools.bench_search_v3 --db data/cod_inorganics.db \
        --out docs/bench/baseline-v3.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np  # noqa: E402

from xinmatch.core.model.peak import Peak  # noqa: E402
from xinmatch.core.search.search_match import search_match  # noqa: E402

#: Cu K-alpha wavelength (Å) — the convention of the whole project.
WAVELENGTH = 1.5406

#: The standard phases the accuracy guardrail is measured on.
#:
#: Each case carries the *expected* chemistry plus the characteristic
#: strongest-line d-spacing of the mineral (Å).  The concrete COD card is
#: resolved at run time by matching **both** the formula and the strongest
#: line, because the library stores formulas in several equivalent spellings
#: (``"C Ca O3"`` / ``"Ca C O3"`` / ``"Al2 O3"`` / ``"O2 Si"`` …) — the
#: formula alone is not a reliable key, and matching on d alone is not
#: discriminating enough.
#:
#: ``formula`` candidates are tried in order; the first one that yields a
#: card whose strongest line matches ``strongest_d`` within ``D_MATCH_TOL``
#: wins.  Space groups were verified against the real COD cards.
STANDARD_PHASES: tuple[tuple[str, tuple[str, ...], float, str], ...] = (
    ("quartz", ("O2 Si", "Si O2"), 3.343, "P 31 2 1"),
    ("calcite", ("C Ca O3", "Ca C O3"), 3.035, "R -3 c"),
    ("corundum", ("Al2 O3",), 2.550, "R -3 c"),
    ("rutile", ("O2 Ti", "Ti O2"), 3.249, "P 42/m n m"),
    ("anatase", ("O2 Ti", "Ti O2"), 3.512, "I 41/a m d d"),
    ("hematite", ("Fe2 O3",), 2.700, "R -3 c"),
    ("zincite", ("O Zn", "Zn O"), 2.475, "P 63 m c"),
    ("fluorite", ("Ca F2",), 1.931, "F m -3 m"),
    ("gypsum", ("Ca H4 O6 S",), 4.271, "C 1 2/c 1"),
    ("barite", ("Ba O4 S",), 3.104, "P n m a"),
    ("magnetite", ("Fe3 O4",), 2.530, "F d -3 m"),
    ("halite", ("Cl Na",), 2.820, "F m -3 m"),
    ("pyrite", ("Fe S2",), 2.689, "P n n m"),
)

#: Tolerance (Å) when matching a card's strongest line against the expected
#: mineral line.  Wide enough to absorb the several-unit-cell variants COD
#: holds for the same mineral, tight enough to exclude other compounds.
D_MATCH_TOL = 0.02

#: Number of reference peaks used to synthesise one experimental pattern.
N_SYNTH_PEAKS = 25

#: Peak-position jitter (degrees 2θ) — small enough to stay inside the
#: correlation window, large enough that an exact-match shortcut would fail.
JITTER_DEG = 0.012

#: Random seed — fixed so the baseline is byte-reproducible.
RANDOM_SEED = 20261021


@dataclass
class BenchCase:
    """One benchmark case: a standard phase and its synthetic pattern."""

    key: str
    formula: str
    entry_id: str
    space_group: str
    peaks: list[Peak]


def _open_ro(path: Path) -> sqlite3.Connection:
    """Open *path* read-only (the benchmark never writes to the library)."""
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _resolve_card(
    conn: sqlite3.Connection, formulas: tuple[str, ...], strongest_d: float
) -> tuple[str, str] | None:
    """Resolve the concrete COD card for a standard phase.

    Returns ``(entry_id, space_group)`` for the first card whose formula is
    listed and whose strongest reflection matches *strongest_d* within
    :data:`D_MATCH_TOL`; ``None`` when the phase is absent from the library.

    The two-part match is deliberate: the library spells the same compound
    in several ways (``"C Ca O3"`` vs ``"Ca C O3"``), so formula alone is
    ambiguous, while a d-spacing alone would match unrelated cards that
    happen to share a strong line.
    """
    for formula in formulas:
        rows = conn.execute(
            "SELECT entry_id, space_group FROM entries WHERE formula = ?",
            (formula,),
        ).fetchall()
        for row in rows:
            peak = conn.execute(
                "SELECT d FROM peaks WHERE entry_id = ? "
                "ORDER BY intensity DESC LIMIT 1",
                (row["entry_id"],),
            ).fetchone()
            if peak is None:
                continue
            if abs(float(peak["d"]) - strongest_d) <= D_MATCH_TOL:
                return str(row["entry_id"]), str(row["space_group"] or "")
    return None


def _fetch_reference_peaks(
    conn: sqlite3.Connection, entry_id: str
) -> tuple[list[float], list[float]]:
    """Return ``(d_list, i_list)`` for *entry_id*, strongest first."""
    rows = conn.execute(
        "SELECT d, intensity FROM peaks WHERE entry_id = ? "
        "ORDER BY intensity DESC LIMIT ?",
        (entry_id, N_SYNTH_PEAKS),
    ).fetchall()
    ds = [float(r["d"]) for r in rows if r["d"] is not None and r["d"] > 0]
    is_ = [
        float(r["intensity"] or 0.0)
        for r in rows
        if r["d"] is not None and r["d"] > 0
    ]
    return ds, is_


def _two_theta_from_d(d: float, wavelength: float) -> float | None:
    """d-spacing → 2θ (degrees), or ``None`` when unphysical for *wavelength*."""
    arg = wavelength / (2.0 * d)
    if arg >= 1.0:
        return None
    return 2.0 * math.degrees(math.asin(arg))


# ---------------------------------------------------------------------------
# Library adapters
# ---------------------------------------------------------------------------
#: The benchmark must run against both storage layouts, so the three
#: operations it needs (resolve a card, read its reference peaks, search)
#: are hidden behind two small adapters.  Everything below this point is
#: layout-agnostic — which is what makes the v2/v3 numbers comparable.


class _V2Library:
    """Row-table (``.db``) backend — the v2 schema."""

    layout = "v2"

    def __init__(self, path: Path) -> None:
        self._conn = _open_ro(path)

    def resolve_card(
        self, formulas: tuple[str, ...], strongest_d: float
    ) -> tuple[str, str] | None:
        return _resolve_card(self._conn, formulas, strongest_d)

    def reference_peaks(self, entry_id: str) -> tuple[list[float], list[float]]:
        return _fetch_reference_peaks(self._conn, entry_id)

    def search(self, peaks: list[Peak], *, top_n: int):
        t0 = time.perf_counter()
        results = search_match(peaks, self._conn, WAVELENGTH, top_n=top_n)
        return results, time.perf_counter() - t0, -1

    def close(self) -> None:
        self._conn.close()


class _V3Library:
    """Columnar (``.xinDB``) backend — the v3 schema.

    Search goes through :func:`~xinmatch.core.db.search_v3.search_match_v3`,
    i.e. the **whole** v3 path (prescreen → CSR decode → v2 scorer).  Using
    the shortcut of scoring every phase directly would hide prescreen recall
    misses, which are exactly what this benchmark is meant to catch.
    """

    layout = "v3"

    def __init__(self, path: Path) -> None:
        from xinmatch.core.db.reader_v3 import XinDBReader

        self._reader = XinDBReader(path)
        ok, reason = self._reader.probe()
        if not ok:
            raise RuntimeError(f"not a usable .xinDB library: {reason}")
        # A separate read-only connection serves the metadata lookups; keeping
        # it apart from the reader means the adapter never reaches into the
        # reader's private connection handling.
        self._conn = _open_ro(path)

    def resolve_card(
        self, formulas: tuple[str, ...], strongest_d: float
    ) -> tuple[str, str] | None:
        for formula in formulas:
            rows = self._conn.execute(
                "SELECT entry_id, space_group FROM entries WHERE formula = ?",
                (formula,),
            ).fetchall()
            for row in rows:
                entry_id = str(row["entry_id"])
                meta = self._reader.fetch_entry(entry_id)
                if meta is None:
                    continue
                ds = meta["peaks_d_list"]
                is_ = meta["peaks_i_list"]
                if not ds:
                    continue
                k = int(np.argmax(np.asarray(is_, dtype=np.float64)))
                if abs(float(ds[k]) - strongest_d) <= D_MATCH_TOL:
                    return entry_id, str(row["space_group"] or "")
        return None

    def reference_peaks(self, entry_id: str) -> tuple[list[float], list[float]]:
        meta = self._reader.fetch_entry(entry_id)
        if meta is None:
            return [], []
        ds = np.asarray(meta["peaks_d_list"], dtype=np.float64)
        is_ = np.asarray(meta["peaks_i_list"], dtype=np.float64)
        if ds.size == 0:
            return [], []
        # v3 stores reflections in descending-d order, so the "strongest 25"
        # of the v2 baseline has to be selected explicitly here.
        order = np.argsort(-is_, kind="stable")[:N_SYNTH_PEAKS]
        keep = ds[order] > 0
        return (
            [float(v) for v in ds[order][keep]],
            [float(v) for v in is_[order][keep]],
        )

    def search(self, peaks: list[Peak], *, top_n: int):
        from xinmatch.core.db.search_v3 import search_match_v3

        outcome = search_match_v3(peaks, self._reader, WAVELENGTH, top_n=top_n)
        return outcome.candidates, outcome.seconds, outcome.n_prescreened

    def close(self) -> None:
        self._reader.close()
        self._conn.close()


def _open_library(path: Path):
    """Pick the adapter that matches *path* (by extension, then by probe)."""
    if path.suffix.lower() == ".xindb":
        return _V3Library(path)
    return _V2Library(path)


def build_cases(source) -> tuple[list[BenchCase], list[str]]:
    """Build one synthetic experimental pattern per standard phase.

    Phases missing from the library under test are skipped (reported in the
    second return value) rather than failing the whole run — the baseline
    must stay comparable across libraries of different coverage.
    """
    rng = random.Random(RANDOM_SEED)
    cases: list[BenchCase] = []
    missing: list[str] = []
    for key, formulas, strongest_d, _sg in STANDARD_PHASES:
        resolved = source.resolve_card(formulas, strongest_d)
        if resolved is None:
            missing.append(key)
            continue
        entry_id, space_group = resolved
        ds, is_ = source.reference_peaks(entry_id)
        if not ds:
            missing.append(key)
            continue
        peaks: list[Peak] = []
        for d, inten in zip(ds, is_, strict=False):
            tt = _two_theta_from_d(d, WAVELENGTH)
            if tt is None:
                continue
            peaks.append(
                Peak(
                    two_theta=tt + rng.uniform(-JITTER_DEG, JITTER_DEG),
                    intensity=inten,
                    d=None,
                )
            )
        if peaks:
            cases.append(
                BenchCase(
                    key=key,
                    formula=formulas[0],
                    entry_id=entry_id,
                    space_group=space_group,
                    peaks=peaks,
                )
            )
    return cases, missing


def run_case(
    case: BenchCase, source, *, top_n: int = 20
) -> dict[str, object]:
    """Run one benchmark case and return its metrics row."""
    results, elapsed, n_prescreened = source.search(case.peaks, top_n=top_n)

    ranked = [r.entry.entry_id for r in results]
    rank = ranked.index(case.entry_id) + 1 if case.entry_id in ranked else 0
    top1 = rank == 1
    top10 = 1 <= rank <= 10
    return {
        "key": case.key,
        "formula": case.formula,
        "entry_id": case.entry_id,
        "n_exp_peaks": len(case.peaks),
        "n_candidates": len(results),
        "n_prescreened": n_prescreened,
        "rank": rank,
        "top1": int(top1),
        "top10": int(top10),
        "best_fom": round(float(results[0].fom), 6) if results else 0.0,
        "hit_fom": round(
            float(next(r.fom for r in results if r.entry.entry_id == case.entry_id)),
            6,
        )
        if any(r.entry.entry_id == case.entry_id for r in results)
        else 0.0,
        "seconds": round(elapsed, 3),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--db",
        type=Path,
        default=PROJECT_ROOT / "data" / "cod_inorganics.db",
        help="library under test (read-only)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=PROJECT_ROOT / "docs" / "bench" / "baseline-v3.csv",
        help="CSV output path",
    )
    parser.add_argument("--label", default="baseline", help="label recorded in the CSV")
    parser.add_argument("--top-n", type=int, default=20)
    args = parser.parse_args(argv)

    if not args.db.is_file():
        print(f"[ERR] database not found: {args.db}")
        return 2

    library = _open_library(args.db)
    try:
        cases, missing = build_cases(library)
        if not cases:
            print("[ERR] no standard phase found in the library — cannot benchmark")
            return 2
        print(f"library: {args.db}   layout: {library.layout}")
        print(f"cases:   {len(cases)}/{len(STANDARD_PHASES)} standard phases found")
        if missing:
            print(f"missing: {', '.join(missing)}")
        print()
        rows: list[dict[str, object]] = []
        for case in cases:
            row = run_case(case, library, top_n=args.top_n)
            rows.append(row)
            flag = "OK " if row["top1"] else ("~  " if row["top10"] else "MISS")
            print(
                f"  {flag} {case.key:<10} {case.formula:<12} "
                f"sg={case.space_group:<12} rank={row['rank']:<4} "
                f"fom={row['hit_fom']:<10} {row['seconds']:.3f}s"
            )
    finally:
        library.close()

    n = len(rows)
    top1 = sum(int(r["top1"]) for r in rows)
    top10 = sum(int(r["top10"]) for r in rows)
    total_time = sum(float(r["seconds"]) for r in rows)
    print()
    print(f"summary: top1 {top1}/{n}   top10 {top10}/{n}   total {total_time:.2f}s")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "label", "db", "key", "formula", "entry_id", "n_exp_peaks",
        "n_candidates", "n_prescreened", "rank", "top1", "top10",
        "best_fom", "hit_fom", "seconds",
    ]
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({"label": args.label, "db": str(args.db), **row})

    summary_path = args.out.with_suffix(".summary.json")
    summary_path.write_text(
        json.dumps(
            {
                "label": args.label,
                "db": str(args.db),
                "n_cases": n,
                "top1": top1,
                "top10": top10,
                "total_seconds": round(total_time, 3),
                "per_case_seconds": {
                    str(r["key"]): r["seconds"] for r in rows
                },
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"wrote {args.out}")
    print(f"wrote {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
