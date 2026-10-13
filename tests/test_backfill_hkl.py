"""Regression tests for the hkl backfill migration (HANDOVER §5.2).

Covers: ``compute_peaks_from_cif(return_hkl=True)`` tri-tuple contract,
the d-spacing match logic, dry-run no-write guarantee and apply
idempotency.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pytest

from tools.backfill_hkl import _match_entry, backfill
from tools.build_cod_full_xinmatch import compute_peaks_from_cif

_FIX = Path(__file__).resolve().parent / "fixtures" / "gsas2_project"


@pytest.fixture()
def zno_cif() -> Path:
    cif = _FIX / "ZnO_cod.cif"
    assert cif.is_file(), f"missing fixture {cif}"
    return cif


# ---------------------------------------------------------------------------
# compute_peaks_from_cif(return_hkl=True)
# ---------------------------------------------------------------------------
def test_compute_peaks_return_hkl_shape(zno_cif: Path) -> None:
    r = compute_peaks_from_cif(zno_cif, dmin=1.0, max_peaks=100, return_hkl=True)
    assert r is not None
    d, i, hkl = r
    assert d.ndim == 1 and i.ndim == 1 and hkl.ndim == 2
    assert d.shape == i.shape == (hkl.shape[0],)
    assert hkl.shape[1] == 3
    assert hkl.dtype == np.int64
    assert len(d) > 0 and len(d) <= 100


def test_compute_peaks_hkl_consistent_with_d(zno_cif: Path) -> None:
    r = compute_peaks_from_cif(zno_cif, dmin=1.0, max_peaks=100, return_hkl=True)
    assert r is not None
    d, i, hkl = r
    # hkl all-zero (the 000 reflection) is impossible in an ASU.
    assert not np.all(hkl == 0)
    # ZnO wurtzite has a strong (002)/(101) family; every returned hkl must
    # reproduce the reported d via the cell of the CIF.
    import gemmi

    ss = gemmi.read_small_structure(str(zno_cif))
    cell = ss.cell
    for j in range(len(d)):
        dd = cell.calculate_d(tuple(int(v) for v in hkl[j]))
        assert abs(dd - d[j]) / d[j] < 1e-6


def test_compute_peaks_default_still_two_tuple(zno_cif: Path) -> None:
    r = compute_peaks_from_cif(zno_cif, dmin=1.0, max_peaks=100)
    assert r is not None
    d, i = r
    assert d.shape == i.shape


# ---------------------------------------------------------------------------
# _match_entry
# ---------------------------------------------------------------------------
def test_match_entry_basic() -> None:
    d_re = np.array([3.0, 2.5, 2.0, 1.5])
    i_re = np.array([1000.0, 500.0, 250.0, 100.0])  # already max=1000 scale
    hkl_re = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 0]])
    db_rows = [
        (11, 2.5, 500.0),   # exact match
        (12, 3.00001, 1000.0),  # float-tolerance match
        (13, 1.9, 200.0),   # no match (rel 5e-2 >> 1e-4)
        (14, 0.8, 50.0),    # d < dmin range: no match
    ]
    h, k, ell, matched, unmatched = _match_entry(
        db_rows, d_re, i_re, hkl_re
    )
    assert matched == 2
    assert unmatched == 2
    assert (h[0], k[0], ell[0]) == (0, 1, 0)
    assert (h[1], k[1], ell[1]) == (1, 0, 0)
    assert h[2] is None and h[3] is None


def test_match_entry_same_d_disambiguated_by_intensity() -> None:
    # Two reflections share the same d (e.g. cubic equivalents); the library
    # intensity must pick the closest member.
    d_re = np.array([2.0, 2.0])
    i_re = np.array([1000.0, 100.0])
    hkl_re = np.array([[1, 0, 0], [0, 1, 1]])
    db_rows = [(21, 2.0, 100.0)]
    h, k, ell, matched, unmatched = _match_entry(
        db_rows, d_re, i_re, hkl_re
    )
    assert matched == 1
    assert (h[0], k[0], ell[0]) == (0, 1, 1)  # intensity 100 closest to 100


def test_match_entry_empty_recompute() -> None:
    h, k, ell, matched, unmatched = _match_entry(
        [(31, 2.0, 100.0)], np.array([]), np.array([]), np.empty((0, 3), np.int64)
    )
    assert matched == 0
    assert unmatched == 1
    assert h == [None] and k == [None] and ell == [None]


# ---------------------------------------------------------------------------
# backfill() integration on a scratch database
# ---------------------------------------------------------------------------
def _make_scratch_db(tmp_path: Path) -> Path:
    db = tmp_path / "lib.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE entries (entry_id TEXT PRIMARY KEY, formula TEXT, "
        "mineral_name TEXT, space_group TEXT, crystal_system TEXT, a REAL, "
        "b REAL, c REAL, alpha REAL, beta REAL, gamma REAL, volume REAL, "
        "density REAL, color TEXT, year INTEGER, author TEXT, journal TEXT, "
        "quality TEXT, elements TEXT)"
    )
    conn.execute(
        "CREATE TABLE peaks (entry_id TEXT NOT NULL, d REAL NOT NULL, "
        "intensity REAL, h INTEGER, k INTEGER, l INTEGER)"
    )
    # One fake entry whose entry_id maps to a COD id; CIF resolved via
    # monkeypatched cod_cif_path below.
    conn.execute(
        "INSERT INTO entries VALUES (?, ?, NULL, NULL, NULL, NULL, NULL, NULL, "
        "NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)",
        ("96-230-0112", "Zn O"),
    )
    conn.commit()
    conn.close()
    return db


def test_backfill_dry_run_writes_nothing(tmp_path: Path, zno_cif: Path, monkeypatch) -> None:
    db = _make_scratch_db(tmp_path)
    conn = sqlite3.connect(db)
    # Seed peaks from the recomputation of the fixture CIF (d-only rows).
    r = compute_peaks_from_cif(zno_cif, dmin=1.0, max_peaks=20, return_hkl=True)
    assert r is not None
    d, i, _ = r
    for dd, ii in zip(d, i, strict=True):
        conn.execute(
            "INSERT INTO peaks (entry_id, d, intensity) VALUES (?, ?, ?)",
            ("96-230-0112", float(dd), float(ii)),
        )
    conn.commit()
    conn.close()

    def _fake_cif_path(cod_id: int) -> Path:
        return zno_cif

    monkeypatch.setattr("tools.backfill_hkl.cod_cif_path", _fake_cif_path)

    summary = backfill(db, dry_run=True, backup=False)
    assert summary["mode"] == "dry-run"
    assert summary["matched_rows"] == len(d)  # all seeds match

    conn = sqlite3.connect(db)
    n = conn.execute(
        "SELECT COUNT(*) FROM peaks WHERE h IS NOT NULL OR k IS NOT NULL "
        "OR l IS NOT NULL"
    ).fetchone()[0]
    conn.close()
    assert n == 0  # nothing written in dry-run


def test_backfill_apply_is_idempotent(tmp_path: Path, zno_cif: Path, monkeypatch) -> None:
    db = _make_scratch_db(tmp_path)
    conn = sqlite3.connect(db)
    r = compute_peaks_from_cif(zno_cif, dmin=1.0, max_peaks=20, return_hkl=True)
    assert r is not None
    d, i, hkl = r
    for dd, ii in zip(d, i, strict=True):
        conn.execute(
            "INSERT INTO peaks (entry_id, d, intensity) VALUES (?, ?, ?)",
            ("96-230-0112", float(dd), float(ii)),
        )
    conn.commit()
    conn.close()

    def _fake_cif_path(cod_id: int) -> Path:
        return zno_cif

    monkeypatch.setattr("tools.backfill_hkl.cod_cif_path", _fake_cif_path)

    s1 = backfill(db, dry_run=False, backup=False)
    assert s1["mode"] == "applied"
    assert s1["matched_rows"] == len(d)
    assert s1["hkl_fill_after"] == len(d)

    # Re-run: same result, no extra writes (idempotent).
    s2 = backfill(db, dry_run=False, backup=False)
    assert s2["matched_rows"] == len(d)
    assert s2["hkl_fill_after"] == len(d)

    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT d, h, k, l FROM peaks ORDER BY d"
    ).fetchall()
    conn.close()
    # hkl written for every row and consistent with the recomputation.
    by_d = {round(float(dd), 6): (int(a), int(b), int(c))
            for dd, a, b, c in zip(d, hkl[:, 0], hkl[:, 1], hkl[:, 2],
                                   strict=True)}
    for dd, hh, kk, ll in rows:
        assert (hh, kk, ll) == by_d[round(float(dd), 6)]
