"""Regression and performance smoke tests for the v3 ``.xinDB`` reader.

Why this file exists
--------------------
The 2026-10 performance work on :mod:`xinmatch.core.db.reader_v3` replaced
three hot paths:

* the prescreen used to stream the whole ``(n_entries, TOP_K)`` matrix once
  per measurement window; it now walks the matrix in cache-sized row blocks,
* ``_matrix()`` used to concatenate the complete ``top_i`` matrix (which the
  prescreen only read column 0 of); it now caches ``top_d`` + a flat
  ``main_i``,
* ``fetch_peaks`` used to decode every chunk in the library; it now locates
  candidates through a cached chunk-offset table and reads only the chunks
  that contain a requested phase.

None of that is allowed to change a single result.  The pre-optimisation
algorithms are therefore embedded below as a small reference oracle that talks
to the database through a raw ``sqlite3`` connection and never touches the
reader internals under test.  Every prescreen candidate list (including order),
``truncated`` flag, ``n_hits`` count and every ``fetch_peaks`` / ``fetch_entry``
float64 value is compared against it.

The oracle tracks the **current** slot policy, not the 2026-10 one: v3.2.0
changed the per-slot ordering (a :data:`_DIVERSIFY_SHARE` slice of the quota is
ordered by hit count alone, and the default quota went 800 → 1000).  When that
policy changes again, change the oracle with it -- what this file guards is
"the optimised reader returns exactly what the straightforward implementation
would", not "the policy never moves".

The real COD/PCOD/TCOD libraries are used when present; those tests skip
otherwise.  The slow ones are marked ``slow`` (excluded by the default
``-m "not slow"`` run) because loading the PCOD matrix and running the
reference implementation on 1.06 M phases takes seconds per call.
"""

from __future__ import annotations

import random
import shutil
import sqlite3
import statistics
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from tests.xindb_support import entry_to_meta
from xinmatch.core.db.reader_v3 import (
    _DIVERSIFY_SHARE,
    DEFAULT_RANK_LIMIT,
    XinDBReader,
)
from xinmatch.core.db.schema_v3 import TOP_K
from xinmatch.core.db.writer_v3 import XinDBWriter
from xinmatch.core.model import CellParams, Entry

#: Real reference libraries (read-only).  The tests skip when absent.
REAL_DBS: dict[str, Path] = {
    "COD": Path(r"D:\Project\XRD\XinMatch-DataBase\data\COD-Inorg-20261020.xinDB"),
    "TCOD": Path(r"D:\Project\XRD\XinMatch-DataBase\data\TCOD-Inorg-20261020.xinDB"),
    "PCOD": Path(r"D:\Project\XRD\XinMatch-DataBase\data\PCOD-Inorg-20261020.xinDB"),
}

#: Element groups exercised against both implementations.
ELEMENT_GROUPS: tuple[frozenset[str] | None, ...] = (
    None,
    frozenset({"O"}),
    frozenset({"Si", "O"}),
    frozenset({"Na", "Cl"}),
    frozenset({"Zz"}),  # element absent from every phase
)

#: Fixed seed: the synthetic library and all query sets are deterministic.
SEED = 20261024


# ---------------------------------------------------------------------------
# Database construction
# ---------------------------------------------------------------------------
def _make_entries() -> list[Entry]:
    """Build a varied synthetic library.

    Covers the cases the prescreen/fetch code must keep bit-identical:
    phases with fewer and more than ``TOP_K`` reflections, duplicate d-values
    (ties in ``hits``), a zero-intensity phase (``w_norm is None`` branch) and
    distinct element sets so ``elements_allowed`` really filters.
    """
    rng = random.Random(SEED)
    element_sets = [
        ["O", "Si"],
        ["O", "Ca", "C"],
        ["Na", "Cl"],
        ["O"],
        ["Si"],
        ["Fe", "O"],
        ["O", "Ti"],
    ]
    peak_counts = [1, 3, 5, 8, 12, 20, 31, 32, 33, 40, 8, 5, 3, 2]
    entries: list[Entry] = []
    for i, n_peaks in enumerate(peak_counts):
        ds = np.asarray(
            sorted((rng.uniform(0.8, 9.0) for _ in range(n_peaks)), reverse=True),
            dtype=np.float64,
        )
        if n_peaks >= 8:
            # Force repeated d-values across phases (and inside one phase) so
            # the hit counter and lexsort tie-breaking are exercised.
            ds[3] = round(ds[3], 2)
        ints = np.linspace(1000.0, 40.0, n_peaks) if n_peaks else np.zeros(0)
        if i == 5:
            ints = np.zeros(n_peaks)  # all-zero intensities
        cell = CellParams(4.0 + i * 0.1, 5.0 + i * 0.1, 6.0 + i * 0.1)
        entries.append(
            Entry(
                entry_id=f"PERF-{i:04d}",
                formula=" ".join(element_sets[i % len(element_sets)]),
                cell=cell,
                space_group="P -1",
                d_spacings=ds,
                intensities=ints,
                elements=frozenset(element_sets[i % len(element_sets)]),
            )
        )
    return entries


def _write_library(
    path: Path,
    entries: list[Entry],
    *,
    chunk_size: int = 4,
    top_k: int = TOP_K,
) -> Path:
    """Write *entries* as a v3 library with an explicit chunk size / top_k."""
    writer = XinDBWriter(path, top_k=top_k, chunk_size=chunk_size, tier=1)
    try:
        for entry in entries:
            writer.add(entry_to_meta(entry), entry.d_spacings, entry.intensities)
    finally:
        writer.close()
    return path


def _raw_conn(path: Path, *, read_only: bool = True) -> sqlite3.Connection:
    if read_only:
        conn = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)
        conn.execute("PRAGMA query_only = ON")
        return conn
    return sqlite3.connect(path)


# ---------------------------------------------------------------------------
# Reference oracle: the pre-optimisation implementation, on a raw connection
# ---------------------------------------------------------------------------
def _ref_decode_matrix(blob: object, n: int, k: int) -> np.ndarray:
    if blob is None:
        return np.zeros((n, k), dtype=np.float32)
    data = bytes(blob)
    expected = n * k * 4
    if len(data) < expected:
        data = data + b"\x00" * (expected - len(data))
    return np.frombuffer(data, dtype="<f4").reshape(n, k)


def _ref_decode_flat(blob: object) -> np.ndarray:
    if blob is None:
        return np.zeros(0, dtype=np.float32)
    data = bytes(blob)
    count = len(data) // 4
    return np.frombuffer(data[: count * 4], dtype="<f4")


@dataclass
class _ReferenceDb:
    """Raw-SQL oracle holding the pre-optimisation algorithms."""

    conn: sqlite3.Connection
    top_d: np.ndarray
    top_i: np.ndarray
    ids: list[str]
    entry_filter: XinDBReader  # element_filter is unchanged; reuse it

    @classmethod
    def load(cls, path: Path, reader: XinDBReader) -> _ReferenceDb:
        conn = _raw_conn(path)
        k = reader.top_k()
        rows = conn.execute(
            "SELECT n, top_d, top_i FROM peak_chunks ORDER BY chunk_id"
        ).fetchall()
        d_blocks = [_ref_decode_matrix(b, int(n), k) for n, b, _i in rows]
        i_blocks = [_ref_decode_matrix(b, int(n), k) for n, _d, b in rows]
        top_d = (
            np.concatenate(d_blocks, axis=0) if d_blocks else np.zeros((0, k), np.float32)
        )
        top_i = (
            np.concatenate(i_blocks, axis=0) if i_blocks else np.zeros((0, k), np.float32)
        )
        ids = [
            str(r[0])
            for r in conn.execute("SELECT entry_id FROM entries ORDER BY rowid")
        ]
        return cls(conn=conn, top_d=top_d, top_i=top_i, ids=ids, entry_filter=reader)

    def close(self) -> None:
        self.conn.close()

    # -- pre-optimisation prescreen -------------------------------------
    def prescreen(
        self,
        measured_d: list[float],
        measured_i: list[float] | None = None,
        *,
        tolerance: float = 0.02,
        tolerance_rel: float = 0.0,
        min_match: int = 3,
        rank_limit: int | None = None,
        diversify_slots: int | None = None,
        elements_allowed: set[str] | frozenset[str] | None = None,
    ) -> tuple[list[str], bool, int]:
        """Old full-matrix implementation; returns (ids, truncated, n_hits)."""
        if not measured_d:
            return [], False, 0
        top_d = self.top_d
        top_i = self.top_i
        n = top_d.shape[0]
        if n == 0:
            return [], False, 0
        md = np.asarray(sorted(float(d) for d in measured_d), dtype=np.float64)
        n_meas = int(md.size)
        if n_meas == 0:
            return [], False, 0

        mi: np.ndarray | None
        if measured_i is not None and len(measured_i) == len(measured_d):
            pairs = sorted(
                zip(
                    (float(x) for x in measured_d),
                    (float(v) for v in measured_i),
                    strict=True,
                ),
                key=lambda p: p[0],
            )
            mi = np.asarray([p[1] for p in pairs], dtype=np.float64)
        else:
            mi = None

        trel = float(tolerance_rel or 0.0)
        use_rel = trel > 0.0
        tol_abs = float(tolerance)
        t_meas = (
            np.maximum(tol_abs, trel * md) if use_rel else np.full(n_meas, tol_abs)
        )
        w_norm = (mi / mi.sum()) if (mi is not None and mi.sum() > 0) else None

        hits = np.zeros(n, dtype=np.int32)
        whits = np.zeros(n, dtype=np.float64)
        main_hit = np.zeros(n, dtype=bool)
        main_d = top_d[:, 0]
        main_i = top_i[:, 0]
        for k in range(n_meas):
            lo = float(md[k] - t_meas[k])
            hi = float(md[k] + t_meas[k])
            in_window = (top_d >= lo) & (top_d <= hi)
            any_k = in_window.any(axis=1)
            hits += any_k
            if w_norm is not None:
                whits += any_k * float(w_norm[k])
                whits += in_window[:, 0] * (main_i / 1000.0) * float(w_norm[k])
            main_hit |= (main_d >= lo) & (main_d <= hi)

        need = max(1, min(int(min_match), top_d.shape[1]))
        cand = hits >= need
        if elements_allowed:
            keep = self.entry_filter.element_filter(elements_allowed, n)
            if keep is not None:
                cand &= keep
        sel = np.flatnonzero(cand)
        if sel.size == 0:
            return [], False, 0
        # Oracle for the **default** order (``prescreen_order="intensity"``):
        # main-peak hit → intensity-weighted hits → hit count.  The alternative
        # "hits" order is covered by test_prescreen_order.py.
        order = sel[np.lexsort((-hits[sel], -whits[sel], ~main_hit[sel]))]
        limit = int(rank_limit if rank_limit is not None else DEFAULT_RANK_LIMIT)
        limit = max(1, limit)
        truncated = order.size > limit

        # v3.2.0 slot policy: a slice of the quota is filled by hit count alone
        # (see reader_v3.prescreen for why).  The oracle must encode the policy
        # as well, otherwise it stops describing "what the reader is supposed to
        # return" and only tests a stale ordering.
        n_diverse = (
            max(0, min(int(round(limit * _DIVERSIFY_SHARE)), limit))
            if diversify_slots is None
            else max(0, min(int(diversify_slots), limit))
        )
        if n_diverse > 0 and order.size > 1:
            primary = order[: limit - n_diverse]
            by_hits = sel[np.lexsort((-whits[sel], -hits[sel]))]
            extra = by_hits[~np.isin(by_hits, primary)][:n_diverse]
            order = np.concatenate([primary, extra])
        else:
            order = order[:limit]
        order = order[:limit]
        return [self.ids[int(r)] for r in order if int(r) < len(self.ids)], truncated, int(
            sel.size
        )

    # -- pre-optimisation fetch ------------------------------------------
    def fetch_peaks(
        self, entry_ids: list[str]
    ) -> dict[str, tuple[list[float], list[float]]]:
        """Old whole-library scan implementation."""
        if not entry_ids:
            return {}
        wanted = set(entry_ids)
        rows = self.conn.execute(
            "SELECT rowid, entry_id, peak_off, peak_n FROM entries "
            "WHERE entry_id IN ({})".format(",".join("?" * len(wanted))),
            tuple(wanted),
        ).fetchall()
        if not rows:
            return {}
        needed: dict[int, tuple[str, int, int]] = {
            int(r[0]): (str(r[1]), int(r[2] or 0), int(r[3] or 0)) for r in rows
        }
        out: dict[str, tuple[list[float], list[float]]] = {}
        chunk_rows = self.conn.execute(
            "SELECT n, all_d, all_i FROM peak_chunks ORDER BY chunk_id"
        ).fetchall()
        cursor = 0
        for _n, all_d, all_i in chunk_rows:
            flat_d = _ref_decode_flat(all_d)
            flat_i = _ref_decode_flat(all_i)
            size = int(flat_d.size)
            for _rowid, (name, peak_off, peak_n) in needed.items():
                if peak_n <= 0 or name in out:
                    continue
                if peak_off < cursor or peak_off >= cursor + size:
                    continue
                local = peak_off - cursor
                take = min(peak_n, size - local)
                out[name] = (
                    flat_d[local : local + take].astype(np.float64).tolist(),
                    flat_i[local : local + take].astype(np.float64).tolist(),
                )
            cursor += size
            if len(out) == len(needed):
                break
        return out

    def fetch_entry(self, entry_id: str) -> dict | None:
        """Old fetch_entry (scans every chunk to locate one phase)."""
        row = self.conn.execute(
            "SELECT rowid, peak_off, peak_n FROM entries WHERE entry_id = ?",
            (entry_id,),
        ).fetchone()
        if row is None:
            return None
        _rowid, peak_off, peak_n = int(row[0]), int(row[1] or 0), int(row[2] or 0)
        if peak_n <= 0:
            return None
        chunk_rows = self.conn.execute(
            "SELECT all_d, all_i FROM peak_chunks ORDER BY chunk_id"
        ).fetchall()
        cursor = 0
        for all_d, all_i in chunk_rows:
            flat_d = _ref_decode_flat(all_d)
            flat_i = _ref_decode_flat(all_i)
            size = int(flat_d.size)
            if peak_off < cursor + size:
                local = peak_off - cursor
                take = min(peak_n, size - local)
                return {
                    "peaks_d_list": flat_d[local : local + take]
                    .astype(np.float64)
                    .tolist(),
                    "peaks_i_list": flat_i[local : local + take]
                    .astype(np.float64)
                    .tolist(),
                }
            cursor += size
        return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def small_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("reader_v3_perf")
    return _write_library(tmp / "small.xinDB", _make_entries(), chunk_size=4)


@pytest.fixture()
def reader(small_db: Path):
    r = XinDBReader(small_db)
    try:
        yield r
    finally:
        r.close()


@pytest.fixture()
def reference(small_db: Path, reader: XinDBReader):
    ref = _ReferenceDb.load(small_db, reader)
    try:
        yield ref
    finally:
        ref.close()


def _query_sets(ref: _ReferenceDb) -> list[tuple[list[float], list[float] | None]]:
    """Deterministic measurement windows: real peaks with jitter + synthetic."""
    rng = random.Random(SEED)
    pool: list[tuple[list[float], list[float] | None]] = []
    for i, entry_id in enumerate(ref.ids):
        peaks = ref.fetch_entry(entry_id)
        if peaks is None or not peaks["peaks_d_list"]:
            continue
        ds = peaks["peaks_d_list"]
        is_ = peaks["peaks_i_list"]
        n = min(len(ds), rng.choice((3, 5, 8, 20, 40)))
        sel = rng.sample(range(len(ds)), n)
        pairs = sorted(
            (float(ds[j]) + rng.uniform(-0.005, 0.005), float(is_[j])) for j in sel
        )
        qd = [p[0] for p in pairs]
        qi = [p[1] for p in pairs]
        pool.append((list(qd), list(qi)))
        if i == 0:
            pool.append((list(qd), None))  # no intensities -> w_norm is None
            pool.append((list(qd), qi[:-1]))  # length mismatch -> ignored
            pool.append((list(qd), [0.0] * n))  # zero total intensity
    # synthetic patterns: sparse windows, strong overlap and single peak
    for n, hi in ((3, 3.0), (8, 6.0), (20, 9.0), (40, 9.0)):
        qd = sorted(rng.uniform(0.8, hi) for _ in range(n))
        pool.append((qd, [rng.uniform(1.0, 1000.0) for _ in range(n)]))
    pool.append(([4.0, 4.0, 4.0], [1000.0, 500.0, 100.0]))  # duplicate windows
    pool.append(([0.31], [1000.0]))  # d below the stored range
    return pool


# ---------------------------------------------------------------------------
# Synthetic-library parity
# ---------------------------------------------------------------------------
def test_matrix_cache_holds_only_prescreen_columns(reader: XinDBReader, reference: _ReferenceDb):
    """``_matrix()`` keeps ``top_d`` + flat ``main_i``; values are unchanged."""
    matrix = reader._matrix()
    assert matrix is not None
    assert set(matrix) == {"top_d", "main_i"}
    assert matrix["top_d"].shape == reference.top_d.shape
    assert matrix["main_i"].shape == (reference.top_d.shape[0],)
    assert np.array_equal(matrix["top_d"], reference.top_d)
    assert np.array_equal(matrix["main_i"], reference.top_i[:, 0])


def test_prescreen_matches_reference(reader: XinDBReader, reference: _ReferenceDb):
    """Every parameter combination yields an identical candidate set/order."""
    pool = _query_sets(reference)
    failures: list[str] = []
    checked = 0

    def check(
        qi: int,
        measured_d: list[float],
        ints: list[float] | None,
        **kwargs,
    ) -> None:
        nonlocal checked
        ref_result = reference.prescreen(measured_d, ints, **kwargs)
        new_result = reader.prescreen(measured_d, ints, **kwargs)
        checked += 1
        actual = (
            new_result.candidate_ids,
            new_result.truncated,
            new_result.n_hits,
        )
        if actual != ref_result:
            failures.append(
                f"q{qi} {kwargs} ref={ref_result[:2]} new={actual[:2]}"
            )

    # 1) every query through both implementations, with all intensity variants
    for qi, (measured_d, measured_i) in enumerate(pool):
        for variant in ("ints", "none", "mismatch", "zero"):
            if variant == "none":
                ints: list[float] | None = None
            elif variant == "mismatch":
                ints = (measured_i or measured_d)[:-1]
            elif variant == "zero":
                ints = [0.0] * len(measured_d)
            else:
                ints = measured_i
            check(qi, measured_d, ints, min_match=2, tolerance=0.02)

    # 2) full parameter matrix on three representative queries
    representative = (0, 6, len(pool) - 2)
    for qi in representative:
        measured_d, measured_i = pool[qi]
        for min_match in (1, 2, 3):
            for tolerance in (0.01, 0.02, 0.05):
                for tolerance_rel in (0.0, 1e-3):
                    for elements in ELEMENT_GROUPS:
                        for rank_limit in (3, 800):
                            check(
                                qi,
                                measured_d,
                                measured_i,
                                min_match=min_match,
                                tolerance=tolerance,
                                tolerance_rel=tolerance_rel,
                                rank_limit=rank_limit,
                                elements_allowed=(
                                    set(elements) if elements else None
                                ),
                            )
    assert checked > 500
    assert not failures, f"{len(failures)} mismatches, first 5: {failures[:5]}"


def test_prescreen_degenerate_inputs_match_reference(
    reader: XinDBReader, reference: _ReferenceDb
):
    """Empty / single-peak / out-of-range inputs behave exactly as before."""
    cases: list[list[float]] = [[], [0.31], [12.0], [4.0], [1e-9]]
    for ds in cases:
        for min_match in (0, 1, 3):
            ref = reference.prescreen(ds, None, min_match=min_match)
            new = reader.prescreen(ds, None, min_match=min_match)
            assert (new.candidate_ids, new.truncated, new.n_hits) == ref


def test_fetch_peaks_matches_reference(reader: XinDBReader, reference: _ReferenceDb):
    """Batched decoding returns the same phases in the same order and values."""
    all_ids = list(reference.ids)
    candidate_lists: list[list[str]] = [
        all_ids,
        [all_ids[0]],
        [all_ids[-1]],
        [],
        [all_ids[1], all_ids[1], all_ids[2]],  # duplicates
        [all_ids[2], "DOES-NOT-EXIST", all_ids[4]],
    ]
    # candidates from a real prescreen (exercises the normal search path)
    screen = reader.prescreen(
        [4.0, 3.0, 2.0, 1.5], [1000.0, 800.0, 400.0, 200.0], min_match=1
    )
    candidate_lists.append(screen.candidate_ids)
    for ids in candidate_lists:
        ref = reference.fetch_peaks(ids)
        new = reader.fetch_peaks(ids)
        assert list(new.keys()) == list(ref.keys())
        assert set(new) == set(ref)
        for key, value in ref.items():
            assert new[key][0] == value[0], key
            assert new[key][1] == value[1], key


def test_fetch_entry_matches_reference(reader: XinDBReader, reference: _ReferenceDb):
    for entry_id in reference.ids:
        ref = reference.fetch_entry(entry_id)
        new = reader.fetch_entry(entry_id)
        if ref is None:
            assert new is None, entry_id
            continue
        assert new is not None
        assert new["peaks_d_list"] == ref["peaks_d_list"], entry_id
        assert new["peaks_i_list"] == ref["peaks_i_list"], entry_id


def test_fetch_peaks_reads_only_candidate_chunks(
    small_db: Path, reader: XinDBReader
):
    """A candidate batch must not rescan every chunk in the library."""
    conn = reader._get_conn()
    assert conn is not None
    # chunk boundaries in reflection counts
    layout = conn.execute(
        "SELECT chunk_id, length(all_d) FROM peak_chunks ORDER BY chunk_id"
    ).fetchall()
    starts = []
    cursor = 0
    for chunk_id, d_bytes in layout:
        starts.append((int(chunk_id), cursor, int(d_bytes) // 4))
        cursor += int(d_bytes) // 4
    # entries that live in the last chunk
    last_chunk, last_start, _size = starts[-1]
    rows = conn.execute(
        "SELECT entry_id, peak_off FROM entries WHERE peak_n > 0 ORDER BY rowid"
    ).fetchall()
    ids = [str(r[0]) for r in rows if int(r[1]) >= last_start]
    assert ids, "expected at least one phase in the last chunk"

    statements: list[str] = []
    conn.set_trace_callback(statements.append)
    try:
        result = reader.fetch_peaks(ids)
    finally:
        conn.set_trace_callback(None)
    assert set(result) == set(ids)
    chunk_reads = [
        s for s in statements if "FROM peak_chunks WHERE chunk_id" in s
    ]
    assert len(chunk_reads) == 1, statements
    # The old implementation fetched the peak payload of every chunk in one
    # ordered scan; the optimised path must never issue that query.
    assert not any("all_d, all_i FROM peak_chunks ORDER BY" in s for s in statements)


def test_prescreen_supports_top_k_not_multiple_of_eight(
    tmp_path: Path, small_db: Path
):
    """The fast row-OR reduction falls back cleanly for an unusual ``top_k``."""
    path = _write_library(tmp_path / "tk12.xinDB", _make_entries(), chunk_size=3, top_k=12)
    reader = XinDBReader(path)
    ref = _ReferenceDb.load(path, reader)
    try:
        assert reader.top_k() == 12
        matrix = reader._matrix()
        assert matrix is not None
        assert matrix["top_d"].shape[1] == 12
        qd = [4.0, 3.0, 2.0, 1.5, 1.2]
        qi = [1000.0, 700.0, 500.0, 250.0, 100.0]
        for min_match in (1, 2, 3):
            ref_result = ref.prescreen(qd, qi, tolerance=0.02, min_match=min_match)
            new = reader.prescreen(qd, qi, tolerance=0.02, min_match=min_match)
            assert (new.candidate_ids, new.truncated, new.n_hits) == ref_result
    finally:
        ref.close()
        reader.close()


def test_truncated_chunk_blobs_still_match_reference(tmp_path: Path):
    """A short ``all_d``/``all_i`` BLOB must decode to the same (shorter) list."""
    path = _write_library(tmp_path / "trunc.xinDB", _make_entries(), chunk_size=2)
    conn = _raw_conn(path, read_only=False)
    try:
        chunk_id, d_bytes, i_bytes = conn.execute(
            "SELECT chunk_id, length(all_d), length(all_i) FROM peak_chunks "
            "ORDER BY chunk_id LIMIT 1 OFFSET 1"
        ).fetchone()
        d_blob = conn.execute(
            "SELECT all_d FROM peak_chunks WHERE chunk_id = ?", (chunk_id,)
        ).fetchone()[0]
        i_blob = conn.execute(
            "SELECT all_i FROM peak_chunks WHERE chunk_id = ?", (chunk_id,)
        ).fetchone()[0]
        # chop one reflection (4 bytes) off both arrays
        conn.execute(
            "UPDATE peak_chunks SET all_d = ?, all_i = ? WHERE chunk_id = ?",
            (d_blob[:-4], i_blob[:-4], chunk_id),
        )
        conn.commit()
    finally:
        conn.close()

    reader = XinDBReader(path)
    ref = _ReferenceDb.load(path, reader)
    try:
        ids = list(ref.ids)
        ref_peaks = ref.fetch_peaks(ids)
        new_peaks = reader.fetch_peaks(ids)
        assert list(new_peaks.keys()) == list(ref_peaks.keys())
        for key, value in ref_peaks.items():
            assert new_peaks[key] == value, key
        for entry_id in ids:
            ref_entry = ref.fetch_entry(entry_id)
            new_entry = reader.fetch_entry(entry_id)
            if ref_entry is None:
                assert new_entry is None, entry_id
            else:
                assert new_entry is not None
                assert new_entry["peaks_d_list"] == ref_entry["peaks_d_list"]
                assert new_entry["peaks_i_list"] == ref_entry["peaks_i_list"]
    finally:
        ref.close()
        reader.close()


# ---------------------------------------------------------------------------
# Defect regressions found in the same audit (also owned by this module)
# ---------------------------------------------------------------------------
def test_probe_handles_hash_in_path_without_creating_ghost_file(tmp_path: Path):
    """``#`` is legal in a Windows filename but a URI fragment delimiter.

    Regression: the raw path was interpolated into ``file:<path>?mode=ro``, so
    SQLite opened the truncated path *without* ``mode=ro`` and left a zero-byte
    file behind; ``probe()`` then reported ``missing_tables:...``.
    """
    path = _write_library(tmp_path / "hash#tag.xinDB", _make_entries(), chunk_size=4)
    before = {p.name for p in tmp_path.iterdir()}
    reader = XinDBReader(path)
    try:
        ok, reason = reader.probe()
        assert (ok, reason) == (True, "")
        # writing/reading must not create the truncated "#" variants
        assert {p.name for p in tmp_path.iterdir()} == before
        screen = reader.prescreen(
            [4.0, 3.0, 2.0], [1000.0, 500.0, 100.0], min_match=1
        )
        assert screen.candidate_ids
        assert reader.fetch_peaks(screen.candidate_ids[:3])
        entry_id = reader.entry_ids()[0]
        assert reader.fetch_entry(entry_id) is not None
    finally:
        reader.close()


def test_probe_rejects_non_integer_schema_version(tmp_path: Path, small_db: Path):
    """A corrupt ``meta.schema_version`` yields ``(False, reason)``, not ValueError."""
    path = tmp_path / "bad_version.xinDB"
    shutil.copyfile(small_db, path)
    conn = _raw_conn(path, read_only=False)
    try:
        conn.execute("UPDATE meta SET value = 'not-a-number' WHERE key = 'schema_version'")
        conn.commit()
    finally:
        conn.close()
    ok, reason = XinDBReader(path).probe()
    assert ok is False
    assert reason == "schema_version:not-a-number"


def test_element_index_tolerates_truncated_blob(tmp_path: Path, small_db: Path):
    """A ``element_inv.eids`` BLOB that is not a whole number of uint32s is tolerated."""
    healthy = XinDBReader(small_db)
    try:
        expected = healthy.element_index("O")
    finally:
        healthy.close()
    assert expected is not None and expected.size > 0

    path = tmp_path / "trunc_elem.xinDB"
    shutil.copyfile(small_db, path)
    conn = _raw_conn(path, read_only=False)
    try:
        eids_len = conn.execute(
            "SELECT length(eids) FROM element_inv WHERE element = 'O'"
        ).fetchone()[0]
        conn.execute(
            "UPDATE element_inv SET eids = substr(eids, 1, ?) WHERE element = 'O'",
            (eids_len - 2,),
        )
        conn.commit()
    finally:
        conn.close()
    reader = XinDBReader(path)
    try:
        indices = reader.element_index("O")
        assert indices is not None
        assert indices.dtype == np.uint32
        assert indices.size == (eids_len - 2) // 4
        assert indices.tolist() == expected[: indices.size].tolist()
        # and the filter that consumes it still works
        assert reader.element_filter(["O"], reader.entry_count()) is not None
    finally:
        reader.close()


def test_connection_is_opened_once_under_concurrency(small_db: Path):
    """Racing first calls must share one connection instead of leaking one."""
    reader = XinDBReader(small_db)
    barrier = threading.Barrier(8)
    connections: list[sqlite3.Connection | None] = []
    lock = threading.Lock()

    def worker() -> None:
        barrier.wait()
        conn = reader._get_conn()
        with lock:
            connections.append(conn)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert all(conn is not None for conn in connections)
        assert len({id(conn) for conn in connections}) == 1
        assert reader._conn is connections[0]
    finally:
        reader.close()


# ---------------------------------------------------------------------------
# Real-library parity (skipped when the libraries are absent)
# ---------------------------------------------------------------------------
def _real_query_pool(ref: _ReferenceDb, n_queries: int = 3) -> list[list[float]]:
    rng = random.Random(SEED + 1)
    ids = list(ref.ids)
    pool: list[list[float]] = []
    for entry_id in rng.sample(ids, min(200, len(ids))):
        peaks = ref.fetch_entry(entry_id)
        if peaks is None or len(peaks["peaks_d_list"]) < 5:
            continue
        ds = peaks["peaks_d_list"]
        n = min(len(ds), 40)
        jittered = sorted(float(d) + rng.uniform(-0.005, 0.005) for d in ds[:n])
        pool.append(jittered)
        if len(pool) >= n_queries:
            break
    return pool


def _check_real_library_parity(
    name: str, path: Path, queries: list[list[float]], n_fetch: int
) -> None:
    reader = XinDBReader(path)
    ref = _ReferenceDb.load(path, reader)
    try:
        for ds in queries:
            for min_match, tolerance, tolerance_rel, elements in (
                (3, 0.01, 0.0, None),
                (1, 0.05, 0.0, None),
                (2, 0.02, 1e-3, frozenset({"O"})),
            ):
                ref_result = ref.prescreen(
                    ds,
                    None,
                    min_match=min_match,
                    tolerance=tolerance,
                    tolerance_rel=tolerance_rel,
                    elements_allowed=elements,
                )
                new = reader.prescreen(
                    ds,
                    None,
                    min_match=min_match,
                    tolerance=tolerance,
                    tolerance_rel=tolerance_rel,
                    elements_allowed=elements,
                )
                assert (
                    new.candidate_ids,
                    new.truncated,
                    new.n_hits,
                ) == ref_result, f"{name} min_match={min_match}"

        # fetch_peaks: a real candidate batch plus a random id sample
        screen = reader.prescreen(
            queries[0], None, min_match=1, rank_limit=n_fetch
        )
        candidate_ids = screen.candidate_ids[:n_fetch]
        rng = random.Random(SEED)
        candidate_ids += rng.sample(list(ref.ids), min(100, len(ref.ids)))
        ref_peaks = ref.fetch_peaks(candidate_ids)
        new_peaks = reader.fetch_peaks(candidate_ids)
        assert list(new_peaks.keys()) == list(ref_peaks.keys()), name
        for key, value in ref_peaks.items():
            assert new_peaks[key] == value, f"{name}:{key}"

        for entry_id in candidate_ids[:10]:
            ref_entry = ref.fetch_entry(entry_id)
            new_entry = reader.fetch_entry(entry_id)
            if ref_entry is None:
                assert new_entry is None
            else:
                assert new_entry is not None
                assert new_entry["peaks_d_list"] == ref_entry["peaks_d_list"]
                assert new_entry["peaks_i_list"] == ref_entry["peaks_i_list"]
    finally:
        ref.close()
        reader.close()


_SMALL_REAL = [name for name in ("COD", "TCOD") if REAL_DBS[name].is_file()]


@pytest.mark.skipif(
    not _SMALL_REAL, reason="real COD/TCOD .xinDB libraries not present"
)
@pytest.mark.parametrize("name", _SMALL_REAL)
def test_real_library_parity_small(name: str):
    """Parity against the real COD/TCOD libraries (fast enough for CI)."""
    path = REAL_DBS[name]
    reader = XinDBReader(path)
    try:
        ref = _ReferenceDb.load(path, reader)
        try:
            queries = _real_query_pool(ref, n_queries=2)
        finally:
            ref.close()
    finally:
        reader.close()
    assert queries
    _check_real_library_parity(name, path, queries, n_fetch=300)


@pytest.mark.slow
@pytest.mark.skipif(
    not REAL_DBS["PCOD"].is_file(), reason="real PCOD .xinDB library not present"
)
def test_real_library_parity_pcod():
    """Parity against the full 1.06 M-phase PCOD library."""
    path = REAL_DBS["PCOD"]
    reader = XinDBReader(path)
    try:
        ref = _ReferenceDb.load(path, reader)
        try:
            queries = _real_query_pool(ref, n_queries=2)
        finally:
            ref.close()
    finally:
        reader.close()
    assert queries
    _check_real_library_parity("PCOD", path, queries, n_fetch=500)


# ---------------------------------------------------------------------------
# Performance smoke tests (loose: relative to the reference implementation)
# ---------------------------------------------------------------------------
def _best_ms(fn, repeats: int = 3) -> float:
    best = float("inf")
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        best = min(best, (time.perf_counter() - t0) * 1000.0)
    return best


@pytest.mark.skipif(
    not _SMALL_REAL, reason="real COD/TCOD .xinDB libraries not present"
)
def test_real_library_prescreen_is_faster_than_reference():
    """Loose smoke test: the blocked prescreen beats the old full-matrix scan.

    Relative rather than absolute, so machine speed does not matter; the
    measured ratio on this repository is ~3-5x, the assertion only needs >1x.
    """
    name = _SMALL_REAL[0]
    path = REAL_DBS[name]
    reader = XinDBReader(path)
    ref = _ReferenceDb.load(path, reader)
    try:
        queries = _real_query_pool(ref, n_queries=1)
        assert queries
        ds = queries[0]
        reader.prescreen(ds, None, min_match=2)  # warm the matrix cache
        new_ms = _best_ms(lambda: reader.prescreen(ds, None, min_match=2))
        ref_ms = _best_ms(lambda: ref.prescreen(ds, None, min_match=2))
        assert new_ms < ref_ms, (
            f"{name}: blocked prescreen {new_ms:.1f} ms is not faster than "
            f"the reference {ref_ms:.1f} ms"
        )
        # The old profile was dominated by memory bandwidth; a large win over
        # the reference should hold at any realistic machine speed.
        assert new_ms < ref_ms * 0.8, (
            f"{name}: prescreen speed-up only {ref_ms / new_ms:.2f}x"
        )
    finally:
        ref.close()
        reader.close()


@pytest.mark.slow
@pytest.mark.skipif(
    not REAL_DBS["PCOD"].is_file(), reason="real PCOD .xinDB library not present"
)
def test_pcod_prescreen_speed_smoke():
    """PCOD: the 1.06 M-phase prescreen must be substantially faster.

    The acceptance target for the optimisation was ``prescreen >= 2.5x``
    faster (3.0 s -> <= 1.2 s on the report machine).  The threshold here is
    deliberately loose (0.5x of the reference) to survive CI noise.
    """
    path = REAL_DBS["PCOD"]
    reader = XinDBReader(path)
    ref = _ReferenceDb.load(path, reader)
    try:
        queries = _real_query_pool(ref, n_queries=1)
        assert queries
        ds = queries[0]
        reader.prescreen(ds, None, min_match=2)  # warm the matrix cache
        new_ms = _best_ms(lambda: reader.prescreen(ds, None, min_match=2), repeats=2)
        ref_ms = _best_ms(lambda: ref.prescreen(ds, None, min_match=2), repeats=2)
        assert new_ms < ref_ms * 0.5, (
            f"PCOD prescreen {new_ms:.1f} ms vs reference {ref_ms:.1f} ms "
            f"({ref_ms / new_ms:.2f}x)"
        )
        # Very loose absolute guard against a regression back to full-matrix
        # scanning (~3.8 s measured on the dev machine / 3.0 s in the report).
        assert new_ms < 2500.0, f"PCOD prescreen unexpectedly slow: {new_ms:.1f} ms"
        print(
            f"PCOD prescreen: new {new_ms:.1f} ms, reference {ref_ms:.1f} ms, "
            f"{ref_ms / new_ms:.2f}x"
        )
    finally:
        ref.close()
        reader.close()


def test_small_library_fetch_peaks_memory_shape(
    small_db: Path, reader: XinDBReader
):
    """fetch_peaks must return plain Python float64 lists (the scorer contract)."""
    screen = reader.prescreen([4.0, 3.0, 2.0], [1000.0, 500.0, 100.0], min_match=1)
    wanted = screen.candidate_ids[:20]
    result = reader.fetch_peaks(wanted)
    assert result
    for ds, is_ in result.values():
        assert isinstance(ds, list) and isinstance(is_, list)
        assert all(isinstance(v, float) for v in ds)
        assert all(isinstance(v, float) for v in is_)


def test_prescreen_result_type(reader: XinDBReader):
    """The public result shape is unchanged."""
    result = reader.prescreen([4.0, 3.0], [1000.0, 500.0], min_match=1)
    assert isinstance(result.candidate_ids, list)
    assert all(isinstance(eid, str) for eid in result.candidate_ids)
    assert isinstance(result.truncated, bool)
    assert isinstance(result.n_hits, int)


def test_prescreen_timing_is_reported(reader: XinDBReader):
    """Sanity: a repeated prescreen is not pathologically slow on a tiny DB."""
    queries = [[4.0, 3.0, 2.0, 1.5, 1.2]] * 5
    times = []
    for ds in queries:
        t0 = time.perf_counter()
        reader.prescreen(ds, None, min_match=1)
        times.append((time.perf_counter() - t0) * 1000.0)
    # tiny library: <100 ms even on a slow machine; the old implementation
    # would also pass this, it only guards against accidental O(n^2) bloat.
    assert statistics.median(times) < 100.0
