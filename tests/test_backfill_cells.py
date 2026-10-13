"""Regression tests for the unit-cell backfill migration (HANDOVER §5.2)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import gemmi
import pytest

from tools.backfill_cells import backfill

_FIX = Path(__file__).resolve().parent / "fixtures" / "gsas2_project"


@pytest.fixture()
def zno_cif() -> Path:
    cif = _FIX / "ZnO_cod.cif"
    assert cif.is_file(), f"missing fixture {cif}"
    return cif


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
    conn.commit()
    conn.close()
    return db


def _insert_entry(db: Path, eid: str, cells: tuple | None) -> None:
    conn = sqlite3.connect(db)
    if cells is None:
        conn.execute(
            "INSERT INTO entries (entry_id, formula) VALUES (?, ?)", (eid, "Zn O")
        )
    else:
        conn.execute(
            "INSERT INTO entries (entry_id, formula, a, b, c, alpha, beta, "
            "gamma, volume) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (eid, "Zn O", *cells),
        )
    conn.commit()
    conn.close()


def test_backfill_cells_dry_run_writes_nothing(tmp_path: Path, zno_cif: Path, monkeypatch) -> None:
    db = _make_scratch_db(tmp_path)
    _insert_entry(db, "96-230-0112", (1.0, 2.0, 3.0, 90.0, 90.0, 90.0, 6.0))

    monkeypatch.setattr("tools.backfill_cells.cod_cif_path",
                        lambda cod_id: zno_cif)

    summary = backfill(db, dry_run=True, backup=False)
    assert summary["mode"] == "dry-run"
    assert summary["updated"] == 1

    conn = sqlite3.connect(db)
    a = conn.execute("SELECT a FROM entries").fetchone()[0]
    conn.close()
    assert a == 1.0  # unchanged


def test_backfill_cells_apply_and_idempotent(tmp_path: Path, zno_cif: Path, monkeypatch) -> None:
    db = _make_scratch_db(tmp_path)
    _insert_entry(db, "96-230-0112", (1.0, 2.0, 3.0, 90.0, 90.0, 90.0, 6.0))

    monkeypatch.setattr("tools.backfill_cells.cod_cif_path",
                        lambda cod_id: zno_cif)

    s1 = backfill(db, dry_run=False, backup=False)
    assert s1["mode"] == "applied"
    assert s1["updated"] == 1
    assert s1["changed_gt_1e3"] == 1

    ss = gemmi.read_small_structure(str(zno_cif))
    cell = ss.cell

    conn = sqlite3.connect(db)
    r = conn.execute(
        "SELECT a, b, c, alpha, beta, gamma, volume FROM entries"
    ).fetchone()
    conn.close()
    assert r[0] == pytest.approx(cell.a)
    assert r[1] == pytest.approx(cell.b)
    assert r[2] == pytest.approx(cell.c)
    assert r[3] == pytest.approx(cell.alpha)
    assert r[4] == pytest.approx(cell.beta)
    assert r[5] == pytest.approx(cell.gamma)
    assert r[6] == pytest.approx(cell.volume)

    # Idempotent: second run reports the same, no volume drift.
    s2 = backfill(db, dry_run=False, backup=False)
    assert s2["updated"] == 1
    conn = sqlite3.connect(db)
    r2 = conn.execute("SELECT volume FROM entries").fetchone()[0]
    conn.close()
    assert r2 == pytest.approx(cell.volume)


def test_backfill_cells_nulls_filled(tmp_path: Path, zno_cif: Path, monkeypatch) -> None:
    db = _make_scratch_db(tmp_path)
    _insert_entry(db, "96-230-0112", None)  # all cell columns NULL

    monkeypatch.setattr("tools.backfill_cells.cod_cif_path",
                        lambda cod_id: zno_cif)

    s = backfill(db, dry_run=False, backup=False)
    assert s["updated"] == 1

    conn = sqlite3.connect(db)
    r = conn.execute(
        "SELECT a, b, c, volume FROM entries"
    ).fetchone()
    conn.close()
    assert r[0] is not None and r[3] is not None


def test_backfill_cells_missing_cif_reported(tmp_path: Path, monkeypatch) -> None:
    db = _make_scratch_db(tmp_path)
    _insert_entry(db, "96-230-0112", (1.0, 2.0, 3.0, 90.0, 90.0, 90.0, 6.0))

    monkeypatch.setattr("tools.backfill_cells.cod_cif_path",
                        lambda cod_id: Path("definitely-missing.cif"))

    s = backfill(db, dry_run=False, backup=False)
    assert s["cif_missing"] == ["96-230-0112"]
    assert s["updated"] == 0
