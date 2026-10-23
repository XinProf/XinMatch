"""Reader for ``.xinDB`` v3 columnar reference databases (M3 / S3.1 + S3.2).

What this module does
---------------------
A v3 database stores every reflection once, in column-major binary blocks.
This module turns that storage back into the two things the search engine
needs:

1. a **fast candidate prescreen** — a vectorised NumPy intersection of the
   measurement windows against the ``(N, TOP_K)`` matrix of each phase's
   strongest reflections, and
2. **full reflection data** for the (few hundred) phases that survive the
   prescreen, decoded straight from the CSR ``all_d`` / ``all_i`` arrays.

Why the prescreen is safe for accuracy
--------------------------------------
The prescreen only *prunes*: a phase that is not in the returned candidate
set is never scored.  Two properties keep that from losing true phases:

* the matrix holds each phase's **32 strongest** reflections, well above the
  12–40 strongest lines the scoring actually consumes, so a phase that
  matches the sample cannot hide behind weaker lines;
* the candidate cap is generous (800 by default) and :meth:`XinDBReader.prescreen`
  reports when it truncated, so the caller can widen the cap instead of
  silently losing a true phase.

The **final ranking never uses the matrix** — it always uses the complete
reflection list decoded from ``all_d`` / ``all_i``, so the score of a
surviving phase is bit-for-bit the score the v2 engine would give.

Access pattern
--------------
The reader opens the database read-only and caches decoded chunks in a small
LRU.  Peak data is decoded with :func:`numpy.frombuffer` (zero-copy over the
bytes object SQLite hands back), and the prescreen matrix is decoded once per
chunk and reused across queries.
"""

from __future__ import annotations

import contextlib
import logging
import sqlite3
import threading
from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .schema_v3 import (
    REQUIRED_TABLES,
    SCHEMA_VERSION,
    TOP_K,
    read_meta,
)

logger = logging.getLogger(__name__)

#: Default number of candidates handed to the scoring stage.
#:
#: 800 is the cap the v2 engine used on the inorganics library and is
#: comfortably above the real top-N of a well-formed pattern, so it keeps a
#: wide safety margin for the scoring stage to reorder.
DEFAULT_RANK_LIMIT = 800

#: Number of decoded chunks kept in memory.  A chunk holds
#: ``CHUNK_SIZE`` phases, so four chunks cover ~16 k phases; the prescreen
#: needs the whole matrix though, which is cached separately (see below).
_CHUNK_CACHE_MAX = 8

#: The prescreen matrix is the hot structure: it is decoded once per
#: database and kept for the process lifetime.  Its size is
#: ``n_entries × TOP_K × 2 × 4 B`` — 18 MB for 71 k phases, 137 MB for the
#: full 535 k archive.
_MATRIX_CACHE_MAX = 2


@dataclass
class PrescreenResult:
    """Outcome of a candidate prescreen.

    Attributes
    ----------
    candidate_ids:
        Entry ids of the surviving candidates, best-first.
    truncated:
        ``True`` when the candidate cap cut the list — the caller should
        treat this as "the cap was reached", not as "there were no more".
    n_hits:
        Number of candidates that matched at least one measurement window.
    """

    candidate_ids: list[str]
    truncated: bool
    n_hits: int


class XinDBReader:
    """Read-only accessor for a ``.xinDB`` v3 database.

    Args:
        db_path: Path to the ``.xinDB`` file.
        rank_limit: Default candidate cap for :meth:`prescreen`.
    """

    def __init__(
        self,
        db_path: str | Path,
        *,
        rank_limit: int = DEFAULT_RANK_LIMIT,
    ) -> None:
        self.path = Path(db_path)
        self.rank_limit = int(rank_limit)
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()
        self._chunks: OrderedDict[int, dict] = OrderedDict()
        self._matrices: OrderedDict[str, dict] = OrderedDict()
        self._meta: dict[str, str] | None = None
        self._entry_ids: list[str] | None = None
        self._elem_masks: np.ndarray | None = None
        self._elem_index: dict[str, np.ndarray | None] = {}

    # ── lifecycle ─────────────────────────────────────────
    @property
    def available(self) -> bool:
        """True when the file exists and the reader can open it."""
        return self.path.is_file()

    def _get_conn(self) -> sqlite3.Connection | None:
        """Return the read-only connection, opening it on first use."""
        if self._conn is not None:
            return self._conn
        if not self.available:
            return None
        try:
            conn = sqlite3.connect(
                f"file:{self.path.as_posix()}?mode=ro", uri=True,
                check_same_thread=False,
            )
        except sqlite3.Error:
            return None
        conn.execute("PRAGMA query_only = ON")
        self._conn = conn
        return conn

    def close(self) -> None:
        """Release the connection and cached data."""
        with self._lock:
            if self._conn is not None:
                with contextlib.suppress(sqlite3.Error):
                    self._conn.close()
            self._conn = None
            self._chunks.clear()
            self._matrices.clear()
            self._meta = None
            self._entry_ids = None
            self._elem_masks = None
            self._elem_index.clear()

    def __enter__(self) -> XinDBReader:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ── metadata ──────────────────────────────────────────
    def meta(self) -> dict[str, str]:
        """Return the ``meta`` table (cached)."""
        if self._meta is not None:
            return self._meta
        conn = self._get_conn()
        if conn is None:
            return {}
        try:
            self._meta = read_meta(conn)
        except sqlite3.Error:
            self._meta = {}
        return self._meta

    def entry_count(self) -> int:
        """Number of phases stored in the database."""
        return int(self.meta().get("entry_count", 0) or 0)

    def top_k(self) -> int:
        """Number of strongest reflections per phase in the prescreen matrix."""
        return int(self.meta().get("top_k", TOP_K) or TOP_K)

    def entry_ids(self) -> list[str]:
        """All entry ids, in rowid order (cached)."""
        if self._entry_ids is not None:
            return self._entry_ids
        conn = self._get_conn()
        if conn is None:
            return []
        try:
            self._entry_ids = [
                str(r[0])
                for r in conn.execute("SELECT entry_id FROM entries ORDER BY rowid")
            ]
        except sqlite3.Error:
            self._entry_ids = []
        return self._entry_ids

    def element_masks(self) -> np.ndarray:
        """Per-phase element bitmaps, indexed like :meth:`entry_ids`."""
        if self._elem_masks is not None:
            return self._elem_masks
        conn = self._get_conn()
        if conn is None:
            return np.zeros(0, dtype=np.uint64)
        try:
            rows = conn.execute(
                "SELECT elem_mask FROM entries ORDER BY rowid"
            ).fetchall()
        except sqlite3.Error:
            rows = []
        self._elem_masks = np.array(
            [int(r[0] or 0) for r in rows], dtype=np.uint64
        )
        return self._elem_masks

    # ── chunk access ──────────────────────────────────────
    def _chunk(self, chunk_id: int) -> dict | None:
        """Return a decoded chunk (LRU-cached)."""
        with self._lock:
            cached = self._chunks.get(chunk_id)
            if cached is not None:
                self._chunks.move_to_end(chunk_id)
                return cached
        conn = self._get_conn()
        if conn is None:
            return None
        try:
            row = conn.execute(
                "SELECT n, top_d, top_i, all_d, all_i FROM peak_chunks "
                "WHERE chunk_id = ?",
                (chunk_id,),
            ).fetchone()
        except sqlite3.Error:
            return None
        if row is None:
            return None

        n = int(row[0])
        k = self.top_k()
        top_d = self._decode_matrix(row[1], n, k)
        top_i = self._decode_matrix(row[2], n, k)
        all_d = self._decode_flat(row[3])
        all_i = self._decode_flat(row[4])
        chunk = {
            "n": n,
            "top_d": top_d,
            "top_i": top_i,
            "all_d": all_d,
            "all_i": all_i,
        }
        with self._lock:
            self._chunks[chunk_id] = chunk
            self._chunks.move_to_end(chunk_id)
            while len(self._chunks) > _CHUNK_CACHE_MAX:
                self._chunks.popitem(last=False)
        return chunk

    @staticmethod
    def _decode_matrix(blob: object, n: int, k: int) -> np.ndarray:
        """Decode a ``(n, k)`` float32 block from a BLOB."""
        if blob is None:
            return np.zeros((n, k), dtype=np.float32)
        data = bytes(blob)
        expected = n * k * 4
        if len(data) < expected:
            # Tolerate a short block rather than raising: a truncated chunk
            # must not take the whole search down.
            padded = data + b"\x00" * (expected - len(data))
            data = padded
        return np.frombuffer(data, dtype="<f4").reshape(n, k)

    @staticmethod
    def _decode_flat(blob: object) -> np.ndarray:
        """Decode a flat float32 array from a BLOB."""
        if blob is None:
            return np.zeros(0, dtype=np.float32)
        data = bytes(blob)
        count = len(data) // 4
        return np.frombuffer(data[: count * 4], dtype="<f4")

    def _matrix(self) -> dict | None:
        """Return the full prescreen matrix (concatenated over chunks)."""
        key = str(self.path.resolve()) if self.path.exists() else str(self.path)
        with self._lock:
            cached = self._matrices.get(key)
            if cached is not None:
                self._matrices.move_to_end(key)
                return cached

        conn = self._get_conn()
        if conn is None:
            return None
        try:
            rows = conn.execute(
                "SELECT chunk_id, n, top_d, top_i FROM peak_chunks ORDER BY chunk_id"
            ).fetchall()
        except sqlite3.Error:
            return None
        if not rows:
            return None

        k = self.top_k()
        d_blocks: list[np.ndarray] = []
        i_blocks: list[np.ndarray] = []
        for _cid, n, top_d, top_i in rows:
            d_blocks.append(self._decode_matrix(top_d, int(n), k))
            i_blocks.append(self._decode_matrix(top_i, int(n), k))
        matrix = {
            "top_d": np.concatenate(d_blocks, axis=0) if d_blocks else np.zeros((0, k)),
            "top_i": np.concatenate(i_blocks, axis=0) if i_blocks else np.zeros((0, k)),
        }
        with self._lock:
            self._matrices[key] = matrix
            self._matrices.move_to_end(key)
            while len(self._matrices) > _MATRIX_CACHE_MAX:
                self._matrices.popitem(last=False)
        return matrix

    # ── phase data ────────────────────────────────────────
    def fetch_meta(self, entry_id: str) -> dict | None:
        """Return one phase's **scalar** metadata (no reflections).

        Separated from :meth:`fetch_entry` so a bulk caller can fetch all
        scalars cheaply and obtain the reflection arrays in a single batched
        pass through :meth:`fetch_peaks` — decoding reflections per phase
        would rescan the chunk list every time.
        """
        conn = self._get_conn()
        if conn is None:
            return None
        try:
            row = conn.execute(
                "SELECT rowid, entry_id, formula, space_group, crystal_system, "
                "mineral_name, elements, a, b, c, alpha, beta, gamma, "
                "volume, density, n_peaks, peak_off, peak_n, tier "
                "FROM entries WHERE entry_id = ?",
                (entry_id,),
            ).fetchone()
        except sqlite3.Error:
            return None
        if row is None:
            return None
        return {
            "rowid": int(row[0]),
            "entry_id": str(row[1]),
            "formula": row[2] or "",
            "space_group": row[3] or "",
            "crystal_system": row[4] or "",
            "mineral_name": row[5] or "",
            "elements_list": [
                t.strip() for t in str(row[6] or "").replace(";", ",").split(",")
                if t.strip()
            ],
            "cell_a": float(row[7]) if row[7] is not None else 0.0,
            "cell_b": float(row[8]) if row[8] is not None else 0.0,
            "cell_c": float(row[9]) if row[9] is not None else 0.0,
            "cell_alpha": float(row[10]) if row[10] is not None else 90.0,
            "cell_beta": float(row[11]) if row[11] is not None else 90.0,
            "cell_gamma": float(row[12]) if row[12] is not None else 90.0,
            "volume": float(row[13]) if row[13] is not None else 0.0,
            "density": float(row[14]) if row[14] is not None else 0.0,
            "n_peaks": int(row[15] or 0),
            "peak_off": int(row[16] or 0),
            "peak_n": int(row[17] or 0),
            "tier": int(row[18] or 0),
        }

    def fetch_entry(self, entry_id: str) -> dict | None:
        """Return one phase's metadata and full reflection list.

        The returned dict mirrors the shape the v2 engine expects
        (``peaks_d_list`` / ``peaks_i_list`` / ``cell_*`` / ``formula`` /
        ``space_group``), so the scoring code can consume both formats
        unchanged.
        """
        meta = self.fetch_meta(entry_id)
        if meta is None:
            return None
        ds, is_ = self._fetch_peaks_at(
            meta["rowid"], meta["peak_off"], meta["peak_n"]
        )
        if not ds:
            return None
        meta["peaks_d_list"] = ds
        meta["peaks_i_list"] = is_
        return meta

    def _fetch_peaks_at(
        self, rowid: int, peak_off: int, peak_n: int
    ) -> tuple[list[float], list[float]]:
        """Decode one phase's reflections from the CSR arrays.

        ``peak_off`` is the phase's **global** peak index; the chunk that
        holds it is found by asking the database for the chunk boundaries
        (cached per call sequence via a small local scan).
        """
        if peak_n <= 0:
            return [], []
        conn = self._get_conn()
        if conn is None:
            return [], []
        # Locate the chunk: chunks are stored in order and each holds a
        # contiguous global peak range, so a single ordered scan finds it.
        try:
            rows = conn.execute(
                "SELECT chunk_id, n, all_d, all_i FROM peak_chunks "
                "ORDER BY chunk_id"
            ).fetchall()
        except sqlite3.Error:
            return [], []
        # ``peak_off`` counts reflections; chunk boundaries are expressed in
        # reflections as well, so walk the chunks accumulating their sizes.
        cursor = 0
        for _chunk_id, _n, all_d, all_i in rows:
            flat_d = self._decode_flat(all_d)
            flat_i = self._decode_flat(all_i)
            size = int(flat_d.size)
            if peak_off < cursor + size:
                local = peak_off - cursor
                take = min(peak_n, size - local)
                ds = flat_d[local : local + take].astype(np.float64)
                is_ = flat_i[local : local + take].astype(np.float64)
                return ds.tolist(), is_.tolist()
            cursor += size
        return [], []

    def fetch_peaks(self, entry_ids: list[str]) -> dict[str, tuple[list[float], list[float]]]:
        """Batch-decode the reflections of several phases.

        One ordered scan over ``peak_chunks`` serves every requested phase,
        instead of one query per phase.
        """
        if not entry_ids:
            return {}
        wanted = set(entry_ids)
        conn = self._get_conn()
        if conn is None:
            return {}
        try:
            rows = conn.execute(
                "SELECT rowid, entry_id, peak_off, peak_n FROM entries "
                "WHERE entry_id IN ({})".format(",".join("?" * len(wanted))),
                tuple(wanted),
            ).fetchall()
        except sqlite3.Error:
            return {}
        if not rows:
            return {}

        # rowid → (name, global peak offset, count)
        needed: dict[int, tuple[str, int, int]] = {
            int(r[0]): (str(r[1]), int(r[2] or 0), int(r[3] or 0))
            for r in rows
        }
        out: dict[str, tuple[list[float], list[float]]] = {}
        try:
            chunk_rows = conn.execute(
                "SELECT n, all_d, all_i FROM peak_chunks ORDER BY chunk_id"
            ).fetchall()
        except sqlite3.Error:
            return {}
        cursor = 0
        for _n, all_d, all_i in chunk_rows:
            flat_d = self._decode_flat(all_d)
            flat_i = self._decode_flat(all_i)
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

    # ── prescreen ─────────────────────────────────────────
    def prescreen(
        self,
        measured_d: list[float],
        measured_i: list[float] | None = None,
        *,
        tolerance: float = 0.02,
        tolerance_rel: float = 0.0,
        min_match: int = 3,
        rank_limit: int | None = None,
        elements_allowed: set[str] | None = None,
    ) -> PrescreenResult:
        """Vectorised candidate prescreen against the strong-peak matrix.

        For every measurement window the matrix rows whose strongest
        reflections fall inside it are counted; the candidates are then
        ordered by *main-peak hit → intensity-weighted hits → hit count* —
        the same ordering the v2 recall stage used, so the surviving set
        matches the v2 behaviour.

        Args:
            measured_d: Measured d-spacings (Å).
            measured_i: Optional measured intensities (parallel to *measured_d*).
            tolerance: Absolute d-window half-width (Å).
            tolerance_rel: Relative d-window component; when > 0 the window
                is ``max(tolerance, tolerance_rel * d)``.
            min_match: Minimum number of distinct measurement windows a
                phase must hit.
            rank_limit: Candidate cap (defaults to the reader's setting).
            elements_allowed: When given, only phases that contain **every**
                one of these elements are kept (an exact ``required`` filter
                backed by the ``element_inv`` inverted index).  An element that
                occurs in no phase yields zero candidates rather than being
                ignored.

        Returns:
            A :class:`PrescreenResult`.
        """
        matrix = self._matrix()
        if matrix is None or not measured_d:
            return PrescreenResult(candidate_ids=[], truncated=False, n_hits=0)

        top_d = matrix["top_d"]
        top_i = matrix["top_i"]
        n = top_d.shape[0]
        if n == 0:
            return PrescreenResult(candidate_ids=[], truncated=False, n_hits=0)

        md = np.asarray(sorted(float(d) for d in measured_d), dtype=np.float64)
        n_meas = int(md.size)
        if n_meas == 0:
            return PrescreenResult(candidate_ids=[], truncated=False, n_hits=0)

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
        # The strongest reference line of each phase, used for the Hanawalt
        # "main peak" test.  ``top_i`` is the intensity of the same
        # reflections, so the phase's strongest line is column 0 of both
        # matrices (they are stored in descending-intensity order).
        main_i = top_i[:, 0]
        for k in range(n_meas):
            lo = float(md[k] - t_meas[k])
            hi = float(md[k] + t_meas[k])
            in_window = (top_d >= lo) & (top_d <= hi)
            any_k = in_window.any(axis=1)
            hits += any_k
            if w_norm is not None:
                whits += any_k * float(w_norm[k])
            # Strength of the phase's *strongest* line when it falls inside
            # the window: a phase whose 100 % line is observed deserves to
            # outrank a phase that only matched with weak lines.  This is
            # the prescreen's contribution to the Hanawalt main-peak
            # principle, and it is what lets the candidate ordering
            # approximate the final FoM ordering.
            if w_norm is not None:
                strongest_in = in_window[:, 0]
                whits += (
                    strongest_in
                    * (main_i / 1000.0)
                    * float(w_norm[k])
                )
            main_hit |= (main_d >= lo) & (main_d <= hi)

        need = max(1, min(int(min_match), top_d.shape[1]))
        cand = hits >= need

        if elements_allowed:
            keep = self.element_filter(elements_allowed, n)
            if keep is not None:
                cand &= keep

        sel = np.flatnonzero(cand)
        if sel.size == 0:
            return PrescreenResult(candidate_ids=[], truncated=False, n_hits=0)

        # lexsort's last key is the primary one and the sort is ascending;
        # negate the numeric keys and invert the boolean to emulate a
        # descending order on (main_hit, whits, hits).
        order = sel[np.lexsort((-hits[sel], -whits[sel], ~main_hit[sel]))]
        limit = int(rank_limit if rank_limit is not None else self.rank_limit)
        limit = max(1, limit)
        truncated = order.size > limit
        order = order[:limit]

        ids = self.entry_ids()
        candidate_ids = [ids[int(r)] for r in order if int(r) < len(ids)]
        return PrescreenResult(
            candidate_ids=candidate_ids,
            truncated=truncated,
            n_hits=int(sel.size),
        )

    def element_index(self, element: str) -> np.ndarray | None:
        """Entry indices of every phase that contains *element*.

        Reads the exact inverted index ``element_inv`` written by the builder.
        Unlike the packed bitmask in ``entries.elem_mask`` this covers **all**
        elements: the mask column is a single signed 64-bit SQLite integer, so
        it cannot hold bits 63..117 (W, Pb, Bi, U, Ta, Au, Pt, Gd, ... -- 27 % of
        the COD phases carry at least one of those).  Filtering on the mask
        therefore returned wrong results for a quarter of the library, which is
        why the prescreen uses this index instead.

        Args:
            element: Element symbol, case-insensitive.

        Returns:
            Ascending ``uint32`` array of entry indices, an empty array when the
            element exists in no phase, or ``None`` when the element is absent
            from the index altogether (unknown symbol).
        """
        key = str(element).strip().title()
        if key in self._elem_index:
            return self._elem_index[key]
        conn = self._get_conn()
        result: np.ndarray | None = None
        if conn is not None and key:
            with contextlib.suppress(sqlite3.Error):
                row = conn.execute(
                    "SELECT eids FROM element_inv WHERE element = ?", (key,)
                ).fetchone()
                if row is not None:
                    blob = row[0] or b""
                    result = (
                        np.frombuffer(blob, dtype=np.uint32)
                        if len(blob) >= 4 else np.empty(0, dtype=np.uint32)
                    )
        self._elem_index[key] = result
        return result

    def element_filter(self, elements: Iterable[str], n: int) -> np.ndarray | None:
        """Boolean mask of the phases that contain **every** element in *elements*.

        Uses the exact ``element_inv`` inverted index.  An unknown element (one
        that appears in no phase) yields an all-``False`` mask rather than being
        ignored: silently dropping the constraint would turn a query for an
        impossible composition into a full-library scan.

        Args:
            elements: Element symbols to require.
            n: Number of entries in the database.

        Returns:
            A boolean array of length *n*, or ``None`` when the request carries
            no usable element (in which case no filtering should happen).
        """
        required = [str(e).strip().title() for e in elements if str(e).strip()]
        if not required:
            return None
        keep: np.ndarray | None = None
        for element in required:
            idx = self.element_index(element)
            if idx is None or idx.size == 0:
                return np.zeros(n, dtype=bool)
            mine = np.zeros(n, dtype=bool)
            mine[idx[idx < n]] = True
            keep = mine if keep is None else (keep & mine)
            if not keep.any():
                return keep
        return keep

    # ── discovery ─────────────────────────────────────────
    def probe(self) -> tuple[bool, str]:
        """Lightweight check that this file is a usable v3 database.

        Returns:
            ``(ok, reason)``; *reason* is a short machine-readable marker
            when *ok* is ``False``.
        """
        if not self.path.exists():
            return False, "file_not_found"
        if not self.path.is_file():
            return False, "not_a_file"
        try:
            with open(self.path, "rb") as fh:
                if fh.read(16) != b"SQLite format 3\x00":
                    return False, "not_sqlite"
        except OSError as exc:
            return False, f"unreadable: {exc}"
        conn = self._get_conn()
        if conn is None:
            return False, "open_failed"
        try:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        except sqlite3.Error as exc:
            return False, f"query_failed: {exc}"
        missing = [t for t in REQUIRED_TABLES if t not in tables]
        if missing:
            return False, "missing_tables:" + ",".join(missing)
        meta = self.meta()
        version = meta.get("schema_version")
        if version is None:
            return False, "no_schema_version"
        if int(version) != SCHEMA_VERSION:
            return False, f"schema_version:{version}"
        return True, ""


def probe(db_path: str | Path) -> tuple[bool, str]:
    """Module-level probe helper (mirrors :func:`xinmatch.core.db.xinmatch_db.probe`)."""
    return XinDBReader(db_path).probe()


__all__ = [
    "DEFAULT_RANK_LIMIT",
    "PrescreenResult",
    "XinDBReader",
    "probe",
]
