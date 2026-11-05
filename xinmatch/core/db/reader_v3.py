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
The reader opens the database read-only, maps the file (``PRAGMA mmap_size``)
and caches decoded chunks in a small LRU.  Peak data is decoded with
:func:`numpy.frombuffer` (zero-copy over the bytes object SQLite hands back),
and the prescreen matrix is decoded once per chunk and reused across queries.

The two hot paths are shaped around the memory hierarchy:

* **prescreen** walks the strong-peak matrix in row blocks that fit in CPU
  cache and re-reads each block once per measurement window.  The old code
  re-read the *whole* matrix per window (40 full-matrix passes), so its cost
  was dominated by main-memory bandwidth; the blocked version keeps the block
  hot while all 40 windows are evaluated.  The per-row "does any reflection
  fall inside the window" reduction is done by reinterpreting the ``(rows, K)``
  boolean block as 64-bit words and OR-ing them, which avoids NumPy's slow
  row-at-a-time ``any(axis=1)`` reduction.
* **fetch_peaks** locates candidates through a cached chunk-offset table
  instead of rescanning ``peak_chunks`` and only touches the chunks that
  actually contain a requested phase.
"""

from __future__ import annotations

import bisect
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
#: 800 was the v2 cap on the inorganics library.  v3.2.0 raised it to 1000 for
#: one specific reason: 800 slots is not enough to hold *both* the dominant
#: phase's look-alike cards and the minor phases of a mixture (see
#: :data:`_DIVERSIFY_SHARE`).  Measured on the two benchmarks: 1000 slots with a
#: 200-slot hit-count quota recovers +1 Top-1 / +1 sequential recovery on the
#: synthetic set and +4 phase recall on the real-solids set versus 800, at
#: +11 % search time on COD-Inorg (0.37 s → 0.41 s) and +26 % on PCOD (1.5→1.9 s).
DEFAULT_RANK_LIMIT = 1000

#: Share of the prescreen slots reserved for the **hit-count** order instead of
#: the legacy "main peak first" order.
#:
#: The legacy order ranks a card by (is my strongest reflection one of the strong
#: measured peaks → intensity-weighted hits → hit count).  On a multi-phase
#: mixture that is effectively "am I the dominant phase", so minor phases never
#: make the 800-slot cut: in a ZnO + Al₂O₃ + CaF₂ pattern both Al₂O₃ and CaF₂
#: were absent from an 800-candidate pool although they rank 197 with an
#: 8000-slot pool (measured 2026-11-04).  Half the slots are therefore handed
#: out by hit count alone, which is what a *minor* phase can still win.
_DIVERSIFY_SHARE = 0.2


def _diverse_slots(limit: int, override: int | None) -> int:
    """How many of *limit* slots go to the hit-count order.

    ``override`` is the explicit ``diversify_slots`` argument: ``0`` reproduces
    the pre-3.2.0 behaviour exactly (all slots legacy), ``limit`` uses the
    hit-count order alone.
    """
    if override is not None:
        return max(0, min(int(override), limit))
    return max(0, min(int(round(limit * _DIVERSIFY_SHARE)), limit))


#: Maximum number of prescreen slots one **phase family** may occupy.
#:
#: ``None`` (the default) keeps the pre-3.5.0 behaviour — no family cap.  A
#: family is approximated by the card's **three strongest reflections**
#: quantised to the d-window (:func:`_family_keys`): it needs no metadata lookup
#: (the prescreen already holds the ``top_d`` matrix) and it separates
#: polymorphs, whose strongest lines differ.
#:
#: Measured 2026-11-05 on the 25 benchmark samples (pool recall at 1000 slots,
#: i.e. the upper bound every downstream metric is limited by): cap ``1`` lifts
#: 45/67 → **48/67**, cap 2/8/16 leave it unchanged.  But it does **not** rescue
#: the ``3-1`` minor phases: Al₂O₃'s first same-phase card sits at pool position
#: **2071** and CaF₂'s at **4262**, while the top-1000 already spans ~550
#: distinct families (largest one 44–67 cards) — the crowding is diffuse, not a
#: single family flooding the pool.
#:
#: End-to-end the cap is **harmful**, so it stays off: capping keeps the card
#: that is *first by the legacy order* within a family, not the one the FoM would
#: rank highest, and it drops the sibling cards a phase needs when its strongest
#: card is a poor scorer.  Measured (same day, both benchmarks): synthetic
#: phase-level Top-1 **11/13 → 6/13** (cap 1 and 2), sequential 10/13 → 7/13,
#: recall 19/24 → 15/24; real-samples card recall 19/43 → 18–19/43.  Turning it
#: on is only meaningful together with a better family definition *and* a
#: per-family ordering by score — see ``docs/基准报告-物相检索-v3.md`` §14.
DEFAULT_FAMILY_SLOTS: int | None = None


def _family_keys(top_d: np.ndarray, tol: float) -> np.ndarray:
    """Quantised ``(d1, d2, d3)`` fingerprint of each card, as an ``int64`` key.

    Cards of the same phase carry nearly identical strongest reflections, so
    rounding those d-spacings to the prescreen window collapses sibling cards
    onto one key while leaving polymorphs (whose strongest lines differ by far
    more than the window) distinct.  Missing / non-positive entries map to
    ``-1`` so a 2-line card never shares a key with a 3-line one.
    """
    t = max(float(tol), 1e-6)
    k = top_d[:, :3]
    valid = np.isfinite(k) & (k > 0.0)
    q = np.where(valid, np.rint(np.where(valid, k, 0.0) / t), -1.0).astype(np.int64)
    base = np.int64(100_003)  # d/0.02 ≤ ~2500 for any realistic cell
    return ((q[:, 0] + 1) * base + (q[:, 1] + 1)) * base + (q[:, 2] + 1)

#: Number of decoded chunks kept in memory.  A chunk holds
#: ``CHUNK_SIZE`` phases, so four chunks cover ~16 k phases; the prescreen
#: needs the whole matrix though, which is cached separately (see below).
_CHUNK_CACHE_MAX = 8

#: The prescreen matrix is the hot structure: it is decoded once per
#: database and kept for the process lifetime.  Only the columns the
#: prescreen uses are kept: the full ``(n_entries, TOP_K)`` d-spacing matrix
#: plus the phase's strongest intensity as a flat ``(n_entries,)`` array
#: (the old reader also concatenated the whole ``top_i`` matrix, which the
#: prescreen never used beyond column 0).
_MATRIX_CACHE_MAX = 2

#: Row block used by :meth:`XinDBReader.prescreen`.
#:
#: 8192 rows × TOP_K float32 is ~1 MiB, i.e. it stays in L2 cache across all
#: measurement windows while being large enough to amortise the per-window
#: NumPy call overhead.  Benchmarked on PCOD (1.06 M phases): 4096/8192/12288
#: are within a few percent of each other and 16384+ falls over once the block
#: no longer fits in cache.
_PRESCREEN_BLOCK = 8192

#: ``PRAGMA mmap_size`` applied to the read-only connection.  The PCOD library
#: is 1.7 GiB, so mapping it avoids SQLite copying every 2.4 MiB peak chunk
#: through its page cache in :meth:`XinDBReader.fetch_peaks` (1.4 s → 0.69 s
#: for 800 candidates on the benchmark machine).  Mapped pages are reclaimable
#: file-backed memory, so they do not become private commit.
_MMAP_SIZE = 2 * 1024 * 1024 * 1024

#: Host parameters per ``entry_id IN (...)`` statement in
#: :meth:`XinDBReader.fetch_peaks`.  SQLite allows 999 parameters on older
#: builds and 32766 on current ones; 900 stays under both with room to spare.
_FETCH_ID_BATCH = 900


def _readonly_uri(path: Path) -> str:
    """Return a ``file:`` URI for *path* that is safe for special characters.

    ``#`` is a legal Windows filename character but a URI fragment delimiter:
    interpolating the raw path made SQLite open the truncated path, and because
    the ``mode=ro`` query then landed inside the fragment it even *created* a
    zero-byte file.  ``Path.as_uri()`` percent-encodes such characters;
    :func:`~xinmatch.core.db.multi_db._readonly_uri` uses the same convention.
    """
    try:
        return path.resolve().as_uri() + "?mode=ro"
    except (OSError, ValueError):  # pragma: no cover - defensive
        return "file:" + path.as_posix() + "?mode=ro"


def _block_rows_any(block: np.ndarray, scratch: np.ndarray) -> np.ndarray:
    """Per-row ``any`` of a boolean ``(rows, k)`` block.

    ``block.any(axis=1)`` is noticeably slow because NumPy reduces one short
    row at a time.  For the prescreen matrix (``k == TOP_K == 32`` bytes per
    row) the same answer is much cheaper to get by viewing each row as four
    64-bit words and OR-ing the words vectorised: a non-zero word means some
    reflection of that phase fell inside the window.  NumPy booleans are
    always stored as 0/1 bytes, so this is exact.

    ``scratch`` must be a ``uint64`` buffer of at least ``rows`` elements;
    it is reused across windows to keep the inner loop allocation-free.
    """
    k = block.shape[1]
    if k % 8 == 0 and block.flags.c_contiguous:
        rows = block.shape[0]
        words = block.view(np.uint64).reshape(rows, k // 8)
        out = scratch[:rows]
        np.bitwise_or(words[:, 0], words[:, 1], out=out)
        for j in range(2, words.shape[1]):
            np.bitwise_or(out, words[:, j], out=out)
        non_zero: np.ndarray = out != 0
        return non_zero
    # Fallback for an unusual ``top_k`` (not a multiple of 8).
    return np.asarray(block.any(axis=1))


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
        family_slots: Default per-family slot cap for :meth:`prescreen`
            (``None`` = no cap, see :data:`DEFAULT_FAMILY_SLOTS`).
    """

    def __init__(
        self,
        db_path: str | Path,
        *,
        rank_limit: int = DEFAULT_RANK_LIMIT,
        family_slots: int | None = DEFAULT_FAMILY_SLOTS,
    ) -> None:
        self.path = Path(db_path)
        self.rank_limit = int(rank_limit)
        self.family_slots = None if family_slots is None else max(1, int(family_slots))
        self._conn: sqlite3.Connection | None = None
        self._conn_lock = threading.Lock()
        self._lock = threading.Lock()
        self._chunks: OrderedDict[int, dict] = OrderedDict()
        self._matrices: OrderedDict[str, dict] = OrderedDict()
        self._layouts: OrderedDict[str, list[tuple[int, int, int, int]]] = OrderedDict()
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
        """Return the read-only connection, opening it on first use.

        The double-checked :attr:`_conn_lock` keeps two threads that race on
        the first call from opening two connections (the second would leak,
        because only one can be remembered in :attr:`_conn`).
        """
        conn = self._conn
        if conn is not None:
            return conn
        with self._conn_lock:
            if self._conn is not None:
                return self._conn
            if not self.available:
                return None
            try:
                conn = sqlite3.connect(
                    _readonly_uri(self.path), uri=True, check_same_thread=False
                )
            except sqlite3.Error:
                return None
            conn.execute("PRAGMA query_only = ON")
            with contextlib.suppress(sqlite3.Error):
                # Read-only memory map: peak chunks are copied out of the
                # mapped file straight into the Python bytes object instead of
                # going through SQLite's page cache a page at a time.
                conn.execute(f"PRAGMA mmap_size = {_MMAP_SIZE}")
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
            self._layouts.clear()
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
    def _blob_bytes(blob: object) -> bytes:
        """Return a BLOB value as ``bytes``.

        SQLite already hands BLOBs back as an exact ``bytes`` object, and
        ``bytes(b)`` is a no-op for those, so the common path allocates
        nothing; the ``bytearray``/``memoryview`` branches exist for callers
        that pass their own buffer in.
        """
        if isinstance(blob, bytes):
            return blob
        if isinstance(blob, (bytearray, memoryview)):
            return bytes(blob)
        raise TypeError(f"expected a BLOB value, got {type(blob).__name__}")

    @classmethod
    def _decode_matrix(cls, blob: object, n: int, k: int) -> np.ndarray:
        """Decode a ``(n, k)`` float32 block from a BLOB."""
        if blob is None:
            return np.zeros((n, k), dtype=np.float32)
        data = cls._blob_bytes(blob)
        expected = n * k * 4
        if len(data) < expected:
            # Tolerate a short block rather than raising: a truncated chunk
            # must not take the whole search down.
            data = data + b"\x00" * (expected - len(data))
        return np.frombuffer(data, dtype="<f4").reshape(n, k)

    @classmethod
    def _decode_flat(cls, blob: object) -> np.ndarray:
        """Decode a flat float32 array from a BLOB."""
        if blob is None:
            return np.zeros(0, dtype=np.float32)
        data = cls._blob_bytes(blob)
        count = len(data) // 4
        return np.frombuffer(data[: count * 4], dtype="<f4")

    def _matrix(self) -> dict | None:
        """Return the prescreen matrix (decoded once per process).

        The returned dict holds ``top_d`` — the ``(n_entries, top_k)``
        float32 matrix of each phase's strongest reflections — and
        ``main_i``, the same reflections' intensities as a flat float32
        array (column 0 of the stored ``top_i`` block).  ``top_i``'s other 31
        columns are never read by the prescreen, so decoding them (and
        concatenating another ~130 MB on PCOD) was pure overhead.

        The matrix is pre-allocated and filled chunk by chunk, which keeps the
        peak resident size at ``top_d`` (~130 MB on PCOD instead of ~260 MB)
        and avoids the extra full-size copy ``np.concatenate`` used to make.
        """
        key = str(self.path.resolve()) if self.path.exists() else str(self.path)
        with self._lock:
            cached = self._matrices.get(key)
            if cached is not None:
                self._matrices.move_to_end(key)
                return cached

        conn = self._get_conn()
        if conn is None:
            return None
        k = self.top_k()
        try:
            total = int(
                conn.execute(
                    "SELECT COALESCE(SUM(n), 0) FROM peak_chunks"
                ).fetchone()[0]
                or 0
            )
        except (sqlite3.Error, TypeError, ValueError):
            return None
        if total <= 0 or k <= 0:
            return None

        top_d = np.zeros((total, k), dtype=np.float32)
        main_i = np.zeros(total, dtype=np.float32)
        row = 0
        try:
            # Iterate the cursor instead of ``fetchall()``: a fetchall keeps
            # every ``top_d``/``top_i`` BLOB (260 MB on PCOD) alive at once.
            for n_blob, top_d_blob, top_i_blob in conn.execute(
                "SELECT n, top_d, top_i FROM peak_chunks ORDER BY chunk_id"
            ):
                n = int(n_blob or 0)
                if n <= 0:
                    continue
                take = min(n, total - row)
                if take <= 0:
                    break
                d_block = self._decode_matrix(top_d_blob, n, k)
                i_block = self._decode_matrix(top_i_blob, n, k)
                top_d[row : row + take] = d_block[:take]
                main_i[row : row + take] = i_block[:take, 0]
                row += take
        except sqlite3.Error:
            return None
        if row <= 0:
            return None
        matrix = {
            "top_d": top_d[:row],
            "main_i": main_i[:row],
        }
        with self._lock:
            self._matrices[key] = matrix
            self._matrices.move_to_end(key)
            while len(self._matrices) > _MATRIX_CACHE_MAX:
                self._matrices.popitem(last=False)
        return matrix

    def _chunk_layout(self) -> list[tuple[int, int, int, int]] | None:
        """Cached ``(chunk_id, first_reflection, n_d, n_i)`` table.

        The prescreen matrix holds phases in rowid order, and the CSR peak
        arrays hold reflections in the same order, so a phase's global
        ``peak_off`` (a reflection index) can be mapped to a chunk with a
        binary search over the cumulative reflection counts.  The counts are
        derived from ``length(all_d) // 4`` / ``length(all_i) // 4`` — exactly
        the element counts :meth:`_decode_flat` produces — so locating a
        phase through this table yields the same slice the old full scan did,
        including for a truncated BLOB.
        """
        key = str(self.path.resolve()) if self.path.exists() else str(self.path)
        with self._lock:
            cached = self._layouts.get(key)
            if cached is not None:
                self._layouts.move_to_end(key)
                return cached
        conn = self._get_conn()
        if conn is None:
            return None
        try:
            rows = conn.execute(
                "SELECT chunk_id, length(all_d), length(all_i) "
                "FROM peak_chunks ORDER BY chunk_id"
            ).fetchall()
        except sqlite3.Error:
            return None
        layout: list[tuple[int, int, int, int]] = []
        first = 0
        for chunk_id, d_bytes, i_bytes in rows:
            n_d = int(d_bytes or 0) // 4
            n_i = int(i_bytes or 0) // 4
            layout.append((int(chunk_id), first, n_d, n_i))
            first += n_d
        with self._lock:
            self._layouts[key] = layout
            self._layouts.move_to_end(key)
            while len(self._layouts) > _MATRIX_CACHE_MAX:
                self._layouts.popitem(last=False)
        return layout

    @staticmethod
    def _locate_chunk(
        layout: list[tuple[int, int, int, int]], peak_off: int
    ) -> tuple[int, int, int] | None:
        """Return ``(chunk_id, local_offset, n_d)`` for a global peak offset.

        ``bisect_right`` over the cumulative chunk ends returns the first
        chunk whose end is *after* ``peak_off`` — the same chunk the old
        "walk the chunks accumulating their sizes" loop picked, including for
        zero-length chunks.
        """
        ends = [first + n_d for _cid, first, n_d, _n_i in layout]
        idx = bisect.bisect_right(ends, peak_off)
        if idx >= len(layout):
            return None
        chunk_id, first, n_d, _n_i = layout[idx]
        return chunk_id, peak_off - first, n_d

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

        ``peak_off`` is the phase's **global** peak index; the chunk that holds
        it is found from the cached chunk layout and only that chunk is
        decoded, instead of walking every chunk in the library.
        """
        if peak_n <= 0:
            return [], []
        conn = self._get_conn()
        if conn is None:
            return [], []
        layout = self._chunk_layout()
        if not layout:
            return [], []
        located = self._locate_chunk(layout, peak_off)
        if located is None:
            return [], []
        chunk_id, local, _n_d = located
        try:
            row = conn.execute(
                "SELECT all_d, all_i FROM peak_chunks WHERE chunk_id = ?",
                (chunk_id,),
            ).fetchone()
        except sqlite3.Error:
            return [], []
        if row is None:
            return [], []
        flat_d = self._decode_flat(row[0])
        flat_i = self._decode_flat(row[1])
        size = int(flat_d.size)
        take = min(peak_n, size - local)
        ds = flat_d[local : local + take].astype(np.float64)
        is_ = flat_i[local : local + take].astype(np.float64)
        return ds.tolist(), is_.tolist()

    def fetch_peaks(self, entry_ids: list[str]) -> dict[str, tuple[list[float], list[float]]]:
        """Batch-decode the reflections of several phases.

        Candidates are grouped by chunk through the cached chunk layout and
        only the chunks that actually hold a requested phase are read, so one
        batch serves every candidate without decoding the whole library.  The
        insertion order of the result is unchanged (chunk order, then the
        order SQLite returned the requested rows).

        The ``entry_id IN (...)`` lookup is issued in batches of
        :data:`_FETCH_ID_BATCH`: SQLite caps the number of host parameters per
        statement (999 on older builds, 32766 on current ones), and an
        oversized list used to raise ``OperationalError`` that the blanket
        ``except sqlite3.Error`` turned into an **empty result** — a search with
        ``candidate_limit`` above that cap silently returned no candidates at
        all (found 2026-11-04 on a 40 000-candidate probe).
        """
        if not entry_ids:
            return {}
        wanted = list(dict.fromkeys(entry_ids))
        conn = self._get_conn()
        if conn is None:
            return {}
        rows: list[tuple] = []
        try:
            for start in range(0, len(wanted), _FETCH_ID_BATCH):
                part = wanted[start:start + _FETCH_ID_BATCH]
                rows.extend(
                    conn.execute(
                        "SELECT rowid, entry_id, peak_off, peak_n FROM entries "
                        "WHERE entry_id IN ({})".format(",".join("?" * len(part))),
                        tuple(part),
                    ).fetchall()
                )
        except sqlite3.Error:
            return {}
        if not rows:
            return {}

        layout = self._chunk_layout()
        if not layout:
            return {}

        # group the candidates by chunk, preserving the order in which SQLite
        # returned the entries (that is the order the old per-chunk loop
        # appended them in).
        buckets: dict[int, list[tuple[str, int, int]]] = {}
        order: list[int] = []
        for r in rows:
            name = str(r[1])
            peak_off = int(r[2] or 0)
            peak_n = int(r[3] or 0)
            if peak_n <= 0:
                continue
            located = self._locate_chunk(layout, peak_off)
            if located is None:
                continue
            chunk_id, local, _n_d = located
            if chunk_id not in buckets:
                buckets[chunk_id] = []
                order.append(chunk_id)
            buckets[chunk_id].append((name, local, peak_n))

        out: dict[str, tuple[list[float], list[float]]] = {}
        for chunk_id in sorted(order):
            items = buckets[chunk_id]
            try:
                row = conn.execute(
                    "SELECT all_d, all_i FROM peak_chunks WHERE chunk_id = ?",
                    (chunk_id,),
                ).fetchone()
            except sqlite3.Error:
                return out
            if row is None:
                continue
            flat_d = self._decode_flat(row[0])
            flat_i = self._decode_flat(row[1])
            size = int(flat_d.size)
            for name, local, peak_n in items:
                if name in out:
                    continue
                take = min(peak_n, size - local)
                if take <= 0:
                    continue
                out[name] = (
                    flat_d[local : local + take].astype(np.float64).tolist(),
                    flat_i[local : local + take].astype(np.float64).tolist(),
                )
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
        diversify_slots: int | None = None,
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
            diversify_slots: How many of the ``rank_limit`` slots are filled by
                the hit-count order instead of the legacy main-peak order
                (default: :data:`_DIVERSIFY_SHARE` of the limit; ``0`` keeps the
                pre-3.2.0 ordering, ``rank_limit`` ranks by hit count alone).

        Returns:
            A :class:`PrescreenResult`.
        """
        matrix = self._matrix()
        if matrix is None or not measured_d:
            return PrescreenResult(candidate_ids=[], truncated=False, n_hits=0)

        top_d = matrix["top_d"]
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
        # The windows are evaluated against row blocks of the matrix.  Doing
        # all windows for one block before moving on keeps the block in CPU
        # cache; the old loop streamed the whole ``(n, TOP_K)`` matrix once per
        # window (40 full passes on PCOD, i.e. ~5 GB of memory traffic).
        # ``lo``/``hi`` stay Python floats, the exact scalar objects the old
        # per-window comparison used, so the float32 comparisons NumPy
        # performs are bit-identical.
        win_lo = [float(v) for v in (md - t_meas)]
        win_hi = [float(v) for v in (md + t_meas)]
        main_i_scaled = matrix["main_i"] / 1000.0
        block_rows = min(_PRESCREEN_BLOCK, n)
        row_or_buf = np.empty(block_rows, dtype=np.uint64)
        for start in range(0, n, block_rows):
            stop = min(start + block_rows, n)
            rows = stop - start
            d_block = top_d[start:stop]
            i_block = main_i_scaled[start:stop]
            b_hits = np.zeros(rows, dtype=np.int32)
            b_main = np.zeros(rows, dtype=bool)
            b_whits: np.ndarray | None = None
            if w_norm is not None:
                b_whits = np.zeros(rows, dtype=np.float64)
            for k in range(n_meas):
                lo = win_lo[k]
                hi = win_hi[k]
                in_window = d_block >= lo
                in_window &= d_block <= hi
                any_k = _block_rows_any(in_window, row_or_buf)
                b_hits += any_k
                # Column 0 is the phase's strongest reflection (the matrices
                # are stored in descending-intensity order), so it carries
                # both the Hanawalt "main peak" flag and the intensity-weighted
                # hit term.  ``in_window[:, 0]`` is exactly the old
                # ``(main_d >= lo) & (main_d <= hi)`` mask.
                strongest_in = in_window[:, 0]
                if b_whits is not None and w_norm is not None:
                    wn = float(w_norm[k])
                    b_whits += any_k * wn
                    b_whits += strongest_in * i_block * wn
                b_main |= strongest_in
            hits[start:stop] = b_hits
            if b_whits is not None:
                whits[start:stop] = b_whits
            main_hit[start:stop] = b_main

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
        legacy = sel[np.lexsort((-hits[sel], -whits[sel], ~main_hit[sel]))]
        limit = int(rank_limit if rank_limit is not None else self.rank_limit)
        limit = max(1, limit)
        truncated = sel.size > limit

        n_diverse = _diverse_slots(limit, diversify_slots)
        if self.family_slots is not None and legacy.size > 1:
            # Family-capped allocation (opt-in, see DEFAULT_FAMILY_SLOTS): walk
            # the legacy order and keep at most ``family_slots`` cards per
            # three-strongest-line fingerprint.  The legacy leader stays first,
            # so the head of the pool never moves; the tail reaches further into
            # the family duplicates that the legacy order would have spent every
            # remaining slot on.
            order = self._family_capped(legacy, limit, int(self.family_slots), tol_abs)
        elif n_diverse > 0 and legacy.size > 1:
            # The legacy order asks "is my **strongest** reflection one of the
            # strong measured peaks?" — in a multi-phase mixture that question
            # is really "am I the dominant phase?", so every minor phase loses
            # its slot to the major one and its look-alike cards (measured
            # 2026-11-04: Al2O3/CaF2 in a ZnO + Al2O3 + CaF2 mixture never
            # entered the 800-slot pool).  The second half of the quota is
            # ordered by hit count alone, which keeps cards that explain many
            # strong peaks without being the strongest-phase look-alike.
            n_primary = limit - n_diverse
            primary = legacy[:n_primary]
            by_hits = sel[np.lexsort((-whits[sel], -hits[sel]))]
            extra = by_hits[~np.isin(by_hits, primary)][:n_diverse]
            order = np.concatenate([primary, extra])
        else:
            order = legacy[:limit]
        order = order[:limit]

        ids = self.entry_ids()
        candidate_ids = [ids[int(r)] for r in order if int(r) < len(ids)]
        return PrescreenResult(
            candidate_ids=candidate_ids,
            truncated=truncated,
            n_hits=int(sel.size),
        )

    def _family_capped(
        self,
        legacy: np.ndarray,
        limit: int,
        cap: int,
        tol: float,
    ) -> np.ndarray:
        """Walk *legacy* in order, keeping at most *cap* cards per family.

        The candidate prefix is grown until *limit* slots are filled, so a pool
        that is short of distinct families still ends up full — the cap changes
        **which** cards get slots, never how many.
        """
        matrix = self._matrix()
        if matrix is None:  # pragma: no cover - prescreen already checked
            return legacy[:limit]
        top_d = matrix["top_d"]
        take = min(legacy.size, max(limit * max(cap, 1) * 2, 2048))
        while True:
            head = legacy[:take]
            keys = _family_keys(top_d[head], tol)
            used: dict[int, int] = {}
            picked: list[int] = []
            for pos in range(head.size):
                key = int(keys[pos])
                if used.get(key, 0) >= cap:
                    continue
                used[key] = used.get(key, 0) + 1
                picked.append(pos)
                if len(picked) >= limit:
                    return head[np.asarray(picked, dtype=np.int64)]
            if take >= legacy.size:
                return head[np.asarray(picked, dtype=np.int64)]
            take = min(legacy.size, take * 2)

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
                    # A truncated/corrupt BLOB must not take library discovery
                    # down: keep the whole uint32 prefix, mirroring the
                    # tolerance of the float32 peak decoders.
                    usable = (len(blob) // 4) * 4
                    result = (
                        np.frombuffer(blob[:usable], dtype=np.uint32)
                        if usable
                        else np.empty(0, dtype=np.uint32)
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
        try:
            parsed = int(version)
        except (TypeError, ValueError):
            # A corrupt / foreign library must be rejected, not crash callers
            # such as ``multi_db.list_libraries()`` with ValueError.
            return False, f"schema_version:{version}"
        if parsed != SCHEMA_VERSION:
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
