"""PolyXRD ``.sqlite`` database compatibility (detect → convert → cache).

Why this module exists
----------------------
PolyXRD (the sibling project at ``D:\\Project\\XRD\\PolyXRD``) ships its
reference data as SQLite files with a **different schema** from XinMatch:

``phases`` (searchable)
    ``COD_inorganics.sqlite`` / ``COD_inorganics_index.sqlite`` /
    ``PDF2_2004.sqlite``.  One row per phase, with the peak table stored as
    two comma-separated float strings (``peaks_d`` / ``peaks_i``).  Column sets
    differ between products (PDF-2 adds ``mineral`` / ``name`` / ``pearson``,
    the COD dumps only carry ``formula`` / ``space_group`` / cell).
``cod_entries`` (not searchable as-is)
    ``cod_index.sqlite``: full-structure COD index with *no* peak table (peaks
    are computed from the CIF at runtime by PolyXRD).  XinMatch cannot use it
    directly; :func:`detect_source` reports it as
    :data:`KIND_POLYXRD_ENTRIES` with an actionable reason.

Conversion strategy
-------------------
Searching the PolyXRD files in place would force every query in
:mod:`xinmatch.core.search` to know about their layout.  Instead we extract the
search-relevant fields **once** into a native XinMatch-schema *sidecar*
(``entries`` / ``peaks`` / ``elements``) cached under
``<user-data>/indexes/external/<hash>.db``:

* the source file (and its ``-wal`` / ``-shm``) is only ever opened
  ``mode=ro`` — nothing is written next to the user's data;
* the sidecar records the source ``mtime`` / ``size`` in ``ext_source_meta``,
  so replacing or rebuilding the source automatically triggers a rebuild;
* builds are incremental-free but cancellable (``check_cancelled``) and report
  progress, so the GUI can show a progress dialog and the CLI can log.

The sidecar is what :func:`xinmatch.core.db.multi_db.open_library` hands to the
search engine; :class:`~xinmatch.core.model.Entry` derives ``elements`` from
the formula, so the element index is built the same way as for native
databases.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from xinmatch.core.cancel import check_cancelled
from xinmatch.core.db.build_cod import insert_entries
from xinmatch.core.db.index_build import build_element_index
from xinmatch.core.db.schema import create_tables
from xinmatch.core.model import CellParams, Entry

logger = logging.getLogger(__name__)

__all__ = [
    "SCHEMA_XINMATCH",
    "SCHEMA_POLYXRD",
    "SCHEMA_UNKNOWN",
    "SourceSchema",
    "build_sidecar",
    "detect_source",
    "ensure_sidecar",
    "sidecar_path_for",
    "sidecar_is_fresh",
    "parse_csv_floats",
]

#: native XinMatch schema (``entries`` / ``peaks`` / ``elements``)
SCHEMA_XINMATCH = "xinmatch"
#: PolyXRD ``phases`` table with CSV peak columns — searchable after conversion
SCHEMA_POLYXRD = "polyxrd_phases"
#: PolyXRD structure-only index (``cod_entries``) — no peaks, not searchable
SCHEMA_POLYXRD_ENTRIES = "polyxrd_entries"
#: anything else
SCHEMA_UNKNOWN = "unknown"

#: column-name candidates, in preference order
_ID_COLUMNS = ("ref_id", "display_id", "cod_id", "id")
_FORMULA_COLUMNS = ("formula", "formula_red")
_NAME_COLUMNS = ("mineral", "name", "mineral_name")
_SG_COLUMNS = ("space_group", "space_group_name", "sg")

#: strongest reflections kept per entry (reference-table convention)
DEFAULT_MAX_PEAKS = 100

#: rows between progress callbacks
_PROGRESS_EVERY = 2000


# ---------------------------------------------------------------------------
# Schema detection
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SourceSchema:
    """What kind of SQLite file *path* is, and how to read it.

    Attributes
    ----------
    kind:
        One of :data:`SCHEMA_XINMATCH`, :data:`SCHEMA_POLYXRD`,
        :data:`SCHEMA_POLYXRD_ENTRIES`, :data:`SCHEMA_UNKNOWN`.
    table:
        Primary table used for the conversion (``phases`` for PolyXRD).
    columns:
        Column names available in *table*.
    id_column / name_column / space_group_column:
        Resolved source columns (``None`` when absent).
    cell_columns:
        Mapping of XinMatch cell parameter → source column.
    row_count:
        ``COUNT(*)`` of *table* (``None`` when unknown).
    reason:
        Human-readable explanation when the source is not searchable.
    """

    kind: str
    table: str | None = None
    columns: tuple[str, ...] = ()
    id_column: str | None = None
    formula_column: str | None = None
    name_column: str | None = None
    space_group_column: str | None = None
    cell_columns: tuple[tuple[str, str], ...] = ()
    row_count: int | None = None
    reason: str | None = None

    @property
    def searchable(self) -> bool:
        """True when a sidecar can be built from this source."""
        return self.kind in (SCHEMA_XINMATCH, SCHEMA_POLYXRD)

    @property
    def needs_conversion(self) -> bool:
        """True when the source must be converted before searching."""
        return self.kind == SCHEMA_POLYXRD


def _readonly_uri(path: Path) -> str:
    """``file:`` URI for *path* (percent-encoded, read-only).

    ``#`` / ``?`` / non-ASCII characters in the path would otherwise be parsed
    as URI syntax and truncate the file name.
    """
    try:
        return path.resolve().as_uri() + "?mode=ro"
    except ValueError:  # pragma: no cover - relative path, defensive
        return "file:" + path.as_posix() + "?mode=ro"


def _columns(conn: sqlite3.Connection, table: str) -> tuple[str, ...]:
    return tuple(row[1] for row in conn.execute(f'PRAGMA table_info("{table}")'))


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
        )
    }


def _pick(columns: tuple[str, ...], candidates: tuple[str, ...]) -> str | None:
    lowered = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand in lowered:
            return lowered[cand]
    return None


def _cell_mapping(columns: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    """Map XinMatch cell parameters to the source's column names."""
    lowered = {c.lower(): c for c in columns}
    out: list[tuple[str, str]] = []
    for param in ("a", "b", "c", "alpha", "beta", "gamma"):
        for prefix in (f"cell_{param}", param):
            if prefix in lowered:
                out.append((param, lowered[prefix]))
                break
    return tuple(out)


def detect_source(path: str | Path) -> SourceSchema:
    """Inspect *path* and describe how (or whether) it can be searched.

    Never raises for a plausible file: I/O and SQLite errors are folded into
    ``kind=SCHEMA_UNKNOWN`` with a ``reason`` so the GUI can show a friendly
    row instead of crashing.
    """
    p = Path(path)
    if not p.exists():
        return SourceSchema(SCHEMA_UNKNOWN, reason=f"file not found: {p}")
    if p.is_dir():
        return SourceSchema(SCHEMA_UNKNOWN, reason=f"not a file: {p}")
    try:
        conn = sqlite3.connect(_readonly_uri(p), uri=True)
    except sqlite3.Error as exc:  # pragma: no cover - unreadable path
        return SourceSchema(SCHEMA_UNKNOWN, reason=f"cannot open SQLite file: {exc}")
    try:
        tables = _tables(conn)
        if "entries" in tables and "peaks" in tables:
            n = int(conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0])
            return SourceSchema(
                SCHEMA_XINMATCH,
                table="entries",
                columns=_columns(conn, "entries"),
                id_column="entry_id",
                formula_column="formula",
                row_count=n,
            )
        if "phases" in tables:
            cols = _columns(conn, "phases")
            n = int(conn.execute("SELECT COUNT(*) FROM phases").fetchone()[0])
            has_peaks = "peaks_d" in {c.lower() for c in cols} and "peaks_i" in {
                c.lower() for c in cols
            }
            if not has_peaks:
                return SourceSchema(
                    SCHEMA_POLYXRD_ENTRIES,
                    table="phases",
                    columns=cols,
                    row_count=n,
                    reason=(
                        "PolyXRD 'phases' table has no peaks_d/peaks_i columns; "
                        "cannot build a peak-based search index."
                    ),
                )
            return SourceSchema(
                SCHEMA_POLYXRD,
                table="phases",
                columns=cols,
                id_column=_pick(cols, _ID_COLUMNS),
                formula_column=_pick(cols, _FORMULA_COLUMNS),
                name_column=_pick(cols, _NAME_COLUMNS),
                space_group_column=_pick(cols, _SG_COLUMNS),
                cell_columns=_cell_mapping(cols),
                row_count=n,
            )
        if "cod_entries" in tables:
            cols = _columns(conn, "cod_entries")
            n = int(conn.execute("SELECT COUNT(*) FROM cod_entries").fetchone()[0])
            return SourceSchema(
                SCHEMA_POLYXRD_ENTRIES,
                table="cod_entries",
                columns=cols,
                row_count=n,
                reason=(
                    "PolyXRD 'cod_entries' stores structures only (no peak "
                    "table); use COD_inorganics.sqlite or PDF2_2004.sqlite, or "
                    "export a phases-style database from PolyXRD."
                ),
            )
        return SourceSchema(
            SCHEMA_UNKNOWN,
            reason="no 'entries'/'peaks' (XinMatch) or 'phases'/'cod_entries' "
            "(PolyXRD) tables found",
        )
    except sqlite3.Error as exc:
        return SourceSchema(SCHEMA_UNKNOWN, reason=f"SQLite error: {exc}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Sidecar paths / freshness
# ---------------------------------------------------------------------------
def _index_dir(index_dir: str | Path | None = None) -> Path:
    if index_dir is not None:
        return Path(index_dir)
    from .multi_db import user_data_dir  # local import: avoids an import cycle

    return user_data_dir() / "indexes" / "external"


def sidecar_path_for(source: str | Path, index_dir: str | Path | None = None) -> Path:
    """Return the cached sidecar path for *source* (stable across runs).

    The name is derived from the **resolved absolute path** only — not from the
    mtime — so rebuilding the source reuses the same sidecar file (which is
    recreated when the fingerprint no longer matches).
    """
    src = Path(source)
    try:
        key = str(src.resolve()).lower()
    except OSError:  # pragma: no cover - defensive
        key = str(src).lower()
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    stem = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in src.stem)[:40]
    return _index_dir(index_dir) / f"{stem}_{digest}.db"


def _source_fingerprint(source: Path) -> dict[str, str]:
    st = source.stat()
    return {
        "source_path": str(source.resolve()),
        "source_mtime_ns": str(st.st_mtime_ns),
        "source_size": str(st.st_size),
    }


def _read_meta(sidecar: Path) -> dict[str, str]:
    if not sidecar.exists():
        return {}
    try:
        conn = sqlite3.connect(_readonly_uri(sidecar), uri=True)
    except sqlite3.Error:
        return {}
    try:
        if "ext_source_meta" not in _tables(conn):
            return {}
        return {
            str(k): str(v)
            for k, v in conn.execute("SELECT key, value FROM ext_source_meta")
        }
    except sqlite3.Error:
        return {}
    finally:
        conn.close()


def sidecar_is_fresh(source: str | Path, sidecar: str | Path | None = None) -> bool:
    """True when *sidecar* exists and was built from this exact source revision."""
    src = Path(source)
    if not src.is_file():
        return False
    target = Path(sidecar) if sidecar is not None else sidecar_path_for(src)
    meta = _read_meta(target)
    if not meta:
        return False
    fp = _source_fingerprint(src)
    return all(meta.get(k) == v for k, v in fp.items())


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------
def parse_csv_floats(text: object) -> np.ndarray:
    """Parse ``"1.2,3.4,…"`` into a float array (empty array on bad input)."""
    if text is None:
        return np.empty(0, dtype=np.float64)
    raw = str(text).strip()
    if not raw:
        return np.empty(0, dtype=np.float64)
    try:
        return np.fromstring(raw, sep=",", dtype=np.float64)
    except ValueError:
        return np.empty(0, dtype=np.float64)


def _entry_id_for(schema: SourceSchema, row: sqlite3.Row, rowid: int) -> str:
    """Build a stable, unique-enough entry id from a PolyXRD row."""
    raw = row["eid"]
    if raw is None or str(raw).strip() == "":
        raw = rowid
    ident = str(raw).strip()
    if schema.id_column and schema.id_column.lower() == "cod_id":
        return f"COD-{ident}"
    return ident


def _entry_from_row(
    schema: SourceSchema,
    row: sqlite3.Row,
    rowid: int,
    *,
    max_peaks: int,
    source_label: str,
) -> Entry | None:
    """Convert one PolyXRD ``phases`` row to an :class:`Entry` (or ``None``)."""
    d = parse_csv_floats(row["pd"])
    i = parse_csv_floats(row["pi"])
    if d.size == 0 or i.size == 0:
        return None
    n = min(d.size, i.size)
    d, i = d[:n], i[:n]
    mask = np.isfinite(d) & np.isfinite(i) & (d > 0.0)
    d, i = d[mask], i[mask]
    if d.size == 0:
        return None
    order = np.argsort(-i, kind="stable")[:max_peaks]
    d_sorted, i_sorted = d[order], i[order]

    cell = None
    cell_values: dict[str, float] = {}
    for param, column in schema.cell_columns:
        value = row[column]
        if value is not None:
            cell_values[param] = float(value)
    if "a" in cell_values:
        a = cell_values["a"]
        cell = CellParams(
            a=a,
            b=cell_values.get("b", a),
            c=cell_values.get("c", a),
            alpha=cell_values.get("alpha", 90.0),
            beta=cell_values.get("beta", 90.0),
            gamma=cell_values.get("gamma", 90.0),
        )

    # ``_select_rows`` aliases the source columns to these fixed names.
    mineral = str(row["name"] or "").strip() or None
    sg = str(row["sg"] or "").strip() or None
    formula = str(row["formula"] or "").strip()

    return Entry(
        entry_id=_entry_id_for(schema, row, rowid),
        formula=formula,
        d_spacings=d_sorted,
        intensities=i_sorted,
        mineral_name=mineral,
        cell=cell,
        space_group=sg,
        hkl=None,
        literature={"source": source_label},
        quality="",
    )


def _select_rows(conn: sqlite3.Connection, schema: SourceSchema):
    """SELECT with stable aliases for the columns we care about."""
    parts = [
        "rowid AS rid",
        f'{schema.id_column} AS eid' if schema.id_column else "NULL AS eid",
        f'{schema.formula_column} AS formula' if schema.formula_column else "'' AS formula",
        f'{schema.name_column} AS name' if schema.name_column else "NULL AS name",
        f'{schema.space_group_column} AS sg' if schema.space_group_column else "NULL AS sg",
        "peaks_d AS pd",
        "peaks_i AS pi",
    ]
    parts += [f'{column} AS "{column}"' for _, column in schema.cell_columns]
    return conn.execute(f'SELECT {", ".join(parts)} FROM "{schema.table}"')


def build_sidecar(
    source: str | Path,
    out: str | Path,
    *,
    max_peaks: int = DEFAULT_MAX_PEAKS,
    limit: int | None = None,
    progress: Callable[[int], None] | None = None,
) -> dict[str, Any]:
    """Convert a PolyXRD ``.sqlite`` into a XinMatch-schema sidecar at *out*.

    Parameters
    ----------
    source:
        PolyXRD database (read-only input).
    out:
        Sidecar path.  An existing file is replaced atomically (build to
        ``out.tmp`` then rename), so a cancelled build never leaves a
        half-written sidecar that later looks fresh.
    max_peaks:
        Strongest reflections kept per phase.
    limit:
        Only convert the first *limit* source rows (tests / smoke builds).
    progress:
        Called with the number of entries written so far (every few thousand
        rows), used by the GUI progress dialog.

    Raises
    ------
    ValueError
        When the source is not convertible (see :func:`detect_source`).
    FileNotFoundError
        When the source does not exist.
    """
    src = Path(source)
    if not src.is_file():
        raise FileNotFoundError(f"source database not found: {src}")
    schema = detect_source(src)
    if schema.kind != SCHEMA_POLYXRD:
        raise ValueError(schema.reason or f"unsupported source schema: {schema.kind}")

    target = Path(out)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    for stale in (tmp, tmp.with_name(tmp.name + "-wal"), tmp.with_name(tmp.name + "-shm")):
        if stale.exists():
            stale.unlink()

    t0 = time.perf_counter()
    sconn = sqlite3.connect(_readonly_uri(src), uri=True)
    sconn.row_factory = sqlite3.Row
    total = int(schema.row_count or 0)

    conn = sqlite3.connect(str(tmp))
    built_ok = False
    try:
        # The sidecar is a derived cache: it is written once and then only read,
        # so durability during the build buys nothing while costing ~2x on a
        # 7.9 M-row insert (measured on the real PDF-2 dump).
        conn.execute("PRAGMA journal_mode = OFF")
        conn.execute("PRAGMA synchronous = OFF")
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.execute("PRAGMA cache_size = -131072")  # 128 MB page cache
        create_tables(conn)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS ext_source_meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        inserted = 0
        skipped = 0
        peak_rows = 0
        batch: list[Entry] = []
        label = f"PolyXRD ({src.name})"

        def flush() -> None:
            nonlocal inserted, peak_rows
            if not batch:
                return
            inserted += insert_entries(conn, batch)
            peak_rows += sum(e.n_peaks for e in batch)
            batch.clear()

        # Honour a cancel request that arrives before the loop even starts (the
        # GUI may be closed while the build is still spinning up).
        check_cancelled()
        rows = _select_rows(sconn, schema)
        for rowid, row in enumerate(rows, start=1):
            if limit is not None and rowid > limit:
                break
            if rowid % 200 == 0:
                check_cancelled()
            entry = _entry_from_row(
                schema, row, rowid, max_peaks=max_peaks, source_label=label
            )
            if entry is None:
                skipped += 1
                continue
            batch.append(entry)
            if len(batch) >= _PROGRESS_EVERY:
                flush()
                if progress is not None:
                    progress(inserted)

        flush()
        if progress is not None:
            progress(inserted)

        build_element_index(conn)
        conn.execute("ANALYZE")
        meta = {
            "kind": SCHEMA_POLYXRD,
            "source_table": str(schema.table),
            "source_rows": str(total),
            "entries_indexed": str(inserted),
            "entries_skipped": str(skipped),
            "max_peaks": str(max_peaks),
            "built_at": str(int(time.time())),
            **_source_fingerprint(src),
        }
        with conn:
            conn.executemany(
                "INSERT OR REPLACE INTO ext_source_meta(key, value) VALUES (?,?)",
                sorted(meta.items()),
            )
        conn.commit()
        built_ok = True
    finally:
        conn.close()
        sconn.close()
        if not built_ok:
            # A cancelled/failed build must not leave a ``.tmp`` behind (dead
            # weight next to the cache, confusing when inspecting the folder).
            # The connection is closed first: on Windows an open handle would
            # make the unlink fail with ``WinError 32``.
            for leftover in (
                tmp,
                tmp.with_name(tmp.name + "-wal"),
                tmp.with_name(tmp.name + "-shm"),
            ):
                if leftover.exists():
                    leftover.unlink()

    if target.exists():
        target.unlink()
    tmp.replace(target)
    elapsed = time.perf_counter() - t0
    summary: dict[str, Any] = {
        "source": str(src),
        "out": str(target),
        "source_rows": total,
        "entries_indexed": inserted,
        "entries_skipped": skipped,
        "peak_rows_total": peak_rows,
        "seconds": round(elapsed, 2),
    }
    logger.info("PolyXRD sidecar built: %s", summary)
    return summary


def ensure_sidecar(
    source: str | Path,
    *,
    index_dir: str | Path | None = None,
    max_peaks: int = DEFAULT_MAX_PEAKS,
    force: bool = False,
    progress: Callable[[int], None] | None = None,
) -> tuple[Path, dict[str, Any] | None]:
    """Return a fresh sidecar for *source*, building it when necessary.

    Returns
    -------
    tuple
        ``(sidecar_path, summary)`` — ``summary`` is ``None`` when an existing
        fresh cache was reused (nothing was built).
    """
    src = Path(source)
    out = sidecar_path_for(src, index_dir=index_dir)
    if not force and sidecar_is_fresh(src, out):
        logger.debug("reusing fresh PolyXRD sidecar %s for %s", out, src)
        return out, None
    summary = build_sidecar(src, out, max_peaks=max_peaks, progress=progress)
    return out, summary
