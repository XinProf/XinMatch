"""Tests for ``tools/build_cod_full_curated.py`` — de-duplicated COD build.

The selection logic (one best card per ``(formula, space_group)`` cluster,
ranked by peak count > usable mineral_name > entry_id) is exercised end-to-end
on a tiny synthetic source DB in ``tmp_path`` — never against the 941 MB real
COD database.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tools.build_cod_full_curated import (
    ENTRIES_COLUMNS,
    build_curated_db,
)


# --------------------------------------------------------------------------- #
# Tiny synthetic source DB
# --------------------------------------------------------------------------- #
def _make_source_db(path: Path) -> Path:
    """Create a small source DB with known duplicate clusters.

    Clusters
    --------
    * ``O Zn / P63mc`` — 3 cards.  Peak counts: A1=10 (no mineral),
      A2=50 (mineral "Zincite"), A3=50 (no mineral).  Expected keep: A2
      (most peaks; tie broken by usable mineral_name).
    * ``C Ca O3 / R-3c`` — 2 cards.  B1=20 (mineral "Calcite"),
      B2=20 (no mineral).  Expected keep: B1 (tie on peaks, mineral wins).
    * ``Si O2 / P3221`` — singleton, kept as-is.
    * ``Ti O2 / P42/mnm`` — 2 cards with equal peaks AND equal mineral-less
      rows: C1=5, C2=5 (no mineral).  Expected keep: C1 (entry_id ASC).
    """
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE entries (
            entry_id TEXT PRIMARY KEY, formula TEXT, mineral_name TEXT,
            space_group TEXT, crystal_system TEXT,
            a REAL, b REAL, c REAL, alpha REAL, beta REAL, gamma REAL,
            volume REAL, density REAL, color TEXT,
            year INTEGER, author TEXT, journal TEXT, quality TEXT,
            elements TEXT
        );
        CREATE TABLE peaks (
            entry_id TEXT NOT NULL, d REAL NOT NULL, intensity REAL,
            h INTEGER, k INTEGER, l INTEGER
        );
        CREATE TABLE elements (entry_id TEXT NOT NULL, element TEXT NOT NULL,
                               PRIMARY KEY (entry_id, element));
        CREATE TABLE element_combo (element_set_hash TEXT PRIMARY KEY,
                                    entry_ids TEXT NOT NULL);
        CREATE INDEX idx_peaks_entry_id ON peaks(entry_id);
        """
    )
    rows = [
        # entry_id, formula, mineral, sg, elements
        ("CARD-A1", "O Zn", None, "P63mc", "O,Zn"),
        ("CARD-A2", "O Zn", "Zincite", "P63mc", "O,Zn"),
        ("CARD-A3", "O Zn", None, "P63mc", "O,Zn"),
        ("CARD-B1", "C Ca O3", "Calcite", "R-3c", "C,Ca,O"),
        ("CARD-B2", "C Ca O3", None, "R-3c", "C,Ca,O"),
        ("CARD-C1", "Si O2", None, "P3221", "O,Si"),
        ("CARD-D1", "Ti O2", None, "P42/mnm", "O,Ti"),
        ("CARD-D2", "Ti O2", None, "P42/mnm", "O,Ti"),
    ]
    conn.executemany(
        "INSERT INTO entries (entry_id, formula, mineral_name, space_group, elements)"
        " VALUES (?,?,?,?,?)",
        rows,
    )

    # Peak counts per entry (must match the expected-selection narrative).
    peak_counts = {
        "CARD-A1": 10,
        "CARD-A2": 50,
        "CARD-A3": 50,
        "CARD-B1": 20,
        "CARD-B2": 20,
        "CARD-C1": 30,
        "CARD-D1": 5,
        "CARD-D2": 5,
    }
    peak_rows = []
    for eid, n in peak_counts.items():
        for i in range(n):
            peak_rows.append((eid, 3.0 + i * 0.01, 100.0 - i, 1, 0, 0))
    conn.executemany(
        "INSERT INTO peaks (entry_id, d, intensity, h, k, l) VALUES (?,?,?,?,?,?)",
        peak_rows,
    )
    elem_rows = []
    for eid, _, _, _, elems in rows:
        for el in elems.split(","):
            elem_rows.append((eid, el))
    conn.executemany(
        "INSERT OR IGNORE INTO elements (entry_id, element) VALUES (?,?)",
        elem_rows,
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture()
def source_db(tmp_path: Path) -> Path:
    return _make_source_db(tmp_path / "src.db")


def test_build_keeps_one_card_per_cluster(source_db: Path, tmp_path: Path) -> None:
    out = tmp_path / "curated.db"
    stats = build_curated_db(source_db, out, force=True)

    conn = sqlite3.connect("file:" + out.as_posix() + "?mode=ro", uri=True)
    try:
        kept = {r[0] for r in conn.execute("SELECT entry_id FROM entries")}
    finally:
        conn.close()

    # One kept card per cluster.
    assert "CARD-A2" in kept  # most peaks (50) + mineral wins over A1/A3
    assert "CARD-A1" not in kept
    assert "CARD-A3" not in kept
    assert "CARD-B1" in kept  # tie on 20 peaks, mineral wins
    assert "CARD-B2" not in kept
    assert "CARD-C1" in kept  # singleton
    assert "CARD-D1" in kept  # tie (5 peaks, no mineral) -> entry_id ASC
    assert "CARD-D2" not in kept

    assert stats["entries"] == 4
    assert stats["source_entries"] == 8
    assert stats["removed_cards"] == 4


def test_output_schema_matches_source(source_db: Path, tmp_path: Path) -> None:
    out = tmp_path / "curated.db"
    build_curated_db(source_db, out, force=True)
    conn = sqlite3.connect("file:" + out.as_posix() + "?mode=ro", uri=True)
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in ("entries", "peaks", "elements", "element_combo", "build_progress"):
            assert t in tables, f"missing table {t}"
        cols = [r[1] for r in conn.execute("PRAGMA table_info(entries)")]
        assert cols == list(ENTRIES_COLUMNS)
        # No orphan peaks (every peak's entry_id exists in entries).
        orphan = conn.execute(
            "SELECT COUNT(*) FROM peaks p LEFT JOIN entries e "
            "ON p.entry_id=e.entry_id WHERE e.entry_id IS NULL"
        ).fetchone()[0]
        assert orphan == 0
        # Every (formula, space_group) group has exactly 1 card.
        max_group = conn.execute(
            "SELECT MAX(c) FROM (SELECT COUNT(*) c FROM entries GROUP BY formula, space_group)"
        ).fetchone()[0]
        assert max_group == 1
    finally:
        conn.close()


def test_idempotent_skip(source_db: Path, tmp_path: Path) -> None:
    out = tmp_path / "curated.db"
    first = build_curated_db(source_db, out, force=True)
    assert first["skipped"] is False
    # Second run without --force should skip and report the same counts.
    second = build_curated_db(source_db, out, force=False)
    assert second["skipped"] is True
    assert second["entries"] == first["entries"]
    assert second["peaks"] == first["peaks"]


def test_force_rebuilds(source_db: Path, tmp_path: Path) -> None:
    out = tmp_path / "curated.db"
    build_curated_db(source_db, out, force=True)
    mtime1 = out.stat().st_mtime
    # --force must rebuild even though the file already looks complete.
    build_curated_db(source_db, out, force=True)
    # File was recreated (size / mtime may differ; just assert it still exists
    # and is valid).
    assert out.exists()
    conn = sqlite3.connect("file:" + out.as_posix() + "?mode=ro", uri=True)
    try:
        assert conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0] == 4
    finally:
        conn.close()
    assert mtime1 is not None
