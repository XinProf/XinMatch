"""Search-side test: a curated (de-duplicated) DB is end-to-end searchable.

Builds a tiny source DB with duplicate cards for the same phase, runs the
curated build, then runs :func:`search_match` against the output to confirm the
kept (best) card is the one surfaced as the top hit.
"""

from __future__ import annotations

import math
import sqlite3
from pathlib import Path

from tools.build_cod_full_curated import build_curated_db
from xinmatch.core.model import Peak
from xinmatch.core.search import search_match

WL = 1.5406


def _d(two_theta: float) -> float:
    return WL / (2.0 * math.sin(math.radians(two_theta / 2.0)))


def _make_src(path: Path) -> None:
    """Two near-duplicate cards for quartz (``Si O2 / P3221``).

    ``Q-GOOD`` has 20 well-placed peaks and a mineral name; ``Q-BAD`` has 5
    sparse peaks and no mineral name.  The curated build must keep Q-GOOD.
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
            elements TEXT);
        CREATE TABLE peaks (entry_id TEXT NOT NULL, d REAL NOT NULL,
                            intensity REAL, h INTEGER, k INTEGER, l INTEGER);
        CREATE TABLE elements (entry_id TEXT NOT NULL, element TEXT NOT NULL,
                               PRIMARY KEY (entry_id, element));
        CREATE TABLE element_combo (element_set_hash TEXT PRIMARY KEY,
                                    entry_ids TEXT NOT NULL);
        CREATE INDEX idx_peaks_entry_id ON peaks(entry_id);
        """
    )
    conn.executemany(
        "INSERT INTO entries (entry_id, formula, mineral_name, space_group, elements)"
        " VALUES (?,?,?,?,?)",
        [("Q-GOOD", "O2 Si", "Quartz", "P3221", "O,Si"), ("Q-BAD", "O2 Si", None, "P3221", "O,Si")],
    )
    # Q-GOOD: 20 peaks around the classic quartz positions.
    good_peaks = [
        (d, 100.0 - i * 4)
        for i, d in enumerate(
            [
                _d(tt)
                for tt in (
                    20.9,
                    26.6,
                    36.5,
                    39.5,
                    40.3,
                    42.4,
                    45.8,
                    50.1,
                    54.9,
                    59.9,
                    60.0,
                    62.7,
                    67.7,
                    68.1,
                    71.5,
                    76.7,
                    80.0,
                    84.0,
                    88.0,
                    92.0,
                )
            ]
        )
    ]
    # Q-BAD: only 5 peaks, weaker coverage.
    bad_peaks = [
        (d, 100.0 - i * 10) for i, d in enumerate([_d(tt) for tt in (26.6, 50.1, 60.0, 68.1, 80.0)])
    ]
    conn.executemany(
        "INSERT INTO peaks (entry_id, d, intensity, h, k, l) VALUES (?,?,?,?,?,?)",
        [("Q-GOOD", d, i, 1, 0, 0) for d, i in good_peaks]
        + [("Q-BAD", d, i, 1, 0, 0) for d, i in bad_peaks],
    )
    conn.executemany(
        "INSERT OR IGNORE INTO elements (entry_id, element) VALUES (?,?)",
        [("Q-GOOD", "O"), ("Q-GOOD", "Si"), ("Q-BAD", "O"), ("Q-BAD", "Si")],
    )
    conn.commit()
    conn.close()


def test_curated_db_search_returns_kept_card(tmp_path: Path) -> None:
    src = tmp_path / "src.db"
    _make_src(src)
    out = tmp_path / "curated.db"
    build_curated_db(src, out, force=True)

    conn = sqlite3.connect("file:" + out.as_posix() + "?mode=ro", uri=True)
    try:
        # Experimental pattern: the strong quartz peaks.
        exp = [
            Peak(two_theta=tt, intensity=100.0 - i * 5)
            for i, tt in enumerate((26.6, 20.9, 36.5, 50.1, 60.0, 68.1))
        ]
        results = search_match(exp, conn, wavelength=WL, top_n=5)
        ids = [r.entry.entry_id for r in results]
        # The kept card (Q-GOOD) must be present; Q-BAD was removed.
        assert "Q-GOOD" in ids
        assert "Q-BAD" not in ids
    finally:
        conn.close()
