"""Parity tests for the v3 ``.xinDB`` format (M4 / S4.1 — release gate).

What "parity" means here
------------------------
The v3 format stores the same reference data as the v2 row-table format but
in a different physical shape.  The rebuild is only allowed to be *as
accurate or better*, so these tests assert **two** things:

1. **Data parity** — the reflections decoded from the v3 columnar blocks
   equal the v2 row-table values field by field, within the float32
   rounding budget (d-spacing residual < 1e-6 Å, i.e. three orders of
   magnitude below the 0.01–0.02 Å matching window).
2. **Ranking parity** — a phase that the v2 engine ranks first is still
   ranked first when the same phase is read through the v3 reader and
   scored by the *same* :func:`rank_candidates` code path.

The tests build a small synthetic v3 library (a few dozen phases with known
peak tables) and compare it against the equivalent v2 database, so they run
in milliseconds and do not depend on a built ``.xinDB`` file.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pytest

from xinmatch.core.db import schema as v2_schema
from xinmatch.core.db import schema_v3
from xinmatch.core.db.reader_v3 import XinDBReader
from xinmatch.core.db.writer_v3 import XinDBWriter
from xinmatch.core.model.entry import CellParams, Entry
from xinmatch.core.model.peak import Peak
from xinmatch.core.search.fom import rank_candidates

#: d-spacing residual budget.  float32 has ~7 significant digits, so a
#: d-value around 1–10 Å carries an absolute error around 1e-6 Å.  The
#: matching window is 0.01–0.02 Å, so this residual can never flip a
#: match decision.
D_TOL = 1e-6

#: Intensity residual budget (relative to the 1000-scale normalisation).
I_TOL = 1e-3


def _make_entry(index: int, n_peaks: int) -> Entry:
    """Build a deterministic synthetic entry with *n_peaks* reflections."""
    rng = np.random.default_rng(1000 + index)
    d = np.sort(rng.uniform(1.0, 8.0, size=n_peaks))[::-1].copy()
    i = rng.uniform(10.0, 1000.0, size=n_peaks)
    # Sort by descending intensity — the project convention for stored
    # reference tables.
    order = np.argsort(-i, kind="stable")
    return Entry(
        entry_id=f"96-100-{index:04d}",
        formula=f"Si{index} O3",
        d_spacings=d[order],
        intensities=i[order],
        mineral_name=f"phase{index}",
        cell=CellParams(a=5.0 + index * 0.01, b=6.0, c=7.0),
        space_group="P 1",
        hkl=None,
        literature={},
        quality="",
        # The element list must consist of real IUPAC symbols: the writer
        # keeps ``entries.elements`` and ``entries.elem_mask`` consistent
        # with each other, so a symbol that has no bit in the element table
        # is dropped (see ``cif_meta.element_bit_positions``).
        elements=frozenset({"O", "Si"}),
    )


def _build_v2_db(path: Path, entries: list[Entry]) -> None:
    """Write *entries* into a v2 row-table database."""
    conn = sqlite3.connect(str(path))
    try:
        v2_schema.create_tables(conn)
        for entry in entries:
            conn.execute(
                "INSERT INTO entries (entry_id, formula, mineral_name, space_group, "
                "crystal_system, a, b, c, alpha, beta, gamma, volume, density, "
                "color, year, author, journal, quality, elements) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    entry.entry_id, entry.formula, entry.mineral_name,
                    entry.space_group, "triclinic",
                    entry.cell.a, entry.cell.b, entry.cell.c,
                    entry.cell.alpha, entry.cell.beta, entry.cell.gamma,
                    0.0, None, None, None, None, None, entry.quality,
                    ",".join(sorted(entry.elements)),
                ),
            )
            conn.executemany(
                "INSERT INTO peaks (entry_id, d, intensity, h, k, l) "
                "VALUES (?,?,?,?,?,?)",
                [
                    (entry.entry_id, float(d), float(i), None, None, None)
                    for d, i in zip(entry.d_spacings, entry.intensities, strict=True)
                ],
            )
        conn.commit()
    finally:
        conn.close()


def _build_v3_db(path: Path, entries: list[Entry], *, tier: int = 1) -> None:
    """Write *entries* into a v3 columnar database."""
    from xinmatch.core.db.cif_meta import PhaseMeta

    writer = XinDBWriter(path, tier=tier)
    try:
        for entry in entries:
            cell = entry.cell
            # The canonical shape of :class:`cif_meta.PhaseMeta`: the cell
            # is one 6-tuple ``(a, b, c, alpha, beta, gamma)``.  The writer
            # also accepts flat cell attributes, but the tuple is what the
            # metadata dataclass actually carries.
            meta = PhaseMeta(
                entry_id=entry.entry_id,
                formula=entry.formula,
                elements=sorted(entry.elements),
                space_group=entry.space_group or "",
                crystal_system="triclinic",
                mineral_name=entry.mineral_name or "",
                cell=(
                    (
                        cell.a, cell.b, cell.c,
                        cell.alpha, cell.beta, cell.gamma,
                    )
                    if cell is not None
                    else None
                ),
                volume=None,
                density=None,
                year=None,
                author="",
                journal="",
            )
            writer.add(meta, entry.d_spacings, entry.intensities)
    finally:
        writer.close()


@pytest.fixture
def sample_entries() -> list[Entry]:
    """A handful of synthetic phases with varied peak counts."""
    entries: list[Entry] = []
    for idx, n_peaks in enumerate([100, 87, 64, 33, 12, 5, 1]):
        entries.append(_make_entry(idx, n_peaks))
    return entries


# ---------------------------------------------------------------------------
# Data parity
# ---------------------------------------------------------------------------
def test_peak_values_round_trip(tmp_path, sample_entries):
    """v3 columnar blocks reproduce the v2 reflection values exactly."""
    v2_path = tmp_path / "v2.db"
    v3_path = tmp_path / "v3.xinDB"
    _build_v2_db(v2_path, sample_entries)
    _build_v3_db(v3_path, sample_entries)

    conn = sqlite3.connect(f"file:{v2_path.as_posix()}?mode=ro", uri=True)
    try:
        with XinDBReader(v3_path) as reader:
            assert reader.probe()[0], reader.probe()[1]
            for entry in sample_entries:
                v2_rows = conn.execute(
                    "SELECT d, intensity FROM peaks WHERE entry_id = ? "
                    "ORDER BY intensity DESC",
                    (entry.entry_id,),
                ).fetchall()
                v2_d = np.array([r[0] for r in v2_rows], dtype=np.float64)
                v2_i = np.array([r[1] for r in v2_rows], dtype=np.float64)

                meta = reader.fetch_entry(entry.entry_id)
                assert meta is not None, entry.entry_id
                v3_d = np.asarray(meta["peaks_d_list"], dtype=np.float64)
                v3_i = np.asarray(meta["peaks_i_list"], dtype=np.float64)

                assert v3_d.size == v2_d.size, entry.entry_id
                # d residuals stay far below the matching window.
                assert np.max(np.abs(v3_d - v2_d)) < D_TOL, entry.entry_id
                # Intensities are normalised to 1000 at build time, so the
                # comparison is done on the normalised scale.
                scale = v2_i.max()
                assert np.max(np.abs(v3_i - v2_i / scale * 1000.0)) < I_TOL
    finally:
        conn.close()


def test_metadata_round_trip(tmp_path, sample_entries):
    """Scalar metadata survives the columnar round trip."""
    v3_path = tmp_path / "v3.xinDB"
    _build_v3_db(v3_path, sample_entries)
    with XinDBReader(v3_path) as reader:
        for entry in sample_entries:
            meta = reader.fetch_entry(entry.entry_id)
            assert meta is not None
            assert meta["formula"] == entry.formula
            assert meta["space_group"] == entry.space_group
            assert meta["mineral_name"] == entry.mineral_name
            assert set(meta["elements_list"]) == set(entry.elements)
            assert abs(meta["cell_a"] - entry.cell.a) < 1e-9
            assert abs(meta["cell_b"] - entry.cell.b) < 1e-9
            assert abs(meta["cell_c"] - entry.cell.c) < 1e-9


def test_prescreen_matrix_matches_reference(tmp_path, sample_entries):
    """The prescreen matrix holds each phase's strongest reflections."""
    v3_path = tmp_path / "v3.xinDB"
    _build_v3_db(v3_path, sample_entries)
    with XinDBReader(v3_path) as reader:
        matrix = reader._matrix()
        assert matrix is not None
        top_d = matrix["top_d"]
        assert top_d.shape[0] == len(sample_entries)
        for row, entry in enumerate(sample_entries):
            k = min(schema_v3.TOP_K, entry.n_peaks)
            expected = entry.d_spacings[:k]
            got = top_d[row, :k]
            assert np.max(np.abs(got.astype(np.float64) - expected)) < D_TOL
            # Padding beyond the phase's peak count must be zero.
            if entry.n_peaks < schema_v3.TOP_K:
                assert np.all(top_d[row, entry.n_peaks :] == 0.0)


# ---------------------------------------------------------------------------
# Ranking parity
# ---------------------------------------------------------------------------
def test_ranking_is_identical_between_formats(tmp_path, sample_entries):
    """The v3 reader and the v2 row table produce the same FoM ordering.

    This is the core accuracy guardrail: the scoring code is shared, so a
    phase that wins under v2 must win under v3 with the *same* score.
    """
    from xinmatch.core.db.search_v3 import _entry_from_meta

    v2_path = tmp_path / "v2.db"
    v3_path = tmp_path / "v3.xinDB"
    _build_v2_db(v2_path, sample_entries)
    _build_v3_db(v3_path, sample_entries)

    # Build an experimental pattern from the first phase, jittered.
    target = sample_entries[0]
    wavelength = 1.5406
    exp_peaks: list[Peak] = []
    for d, inten in list(
        zip(target.d_spacings[:20], target.intensities[:20], strict=True)
    ):
        arg = wavelength / (2.0 * float(d))
        if arg >= 1.0:
            continue
        import math

        two_theta = 2.0 * math.degrees(math.asin(arg))
        exp_peaks.append(Peak(two_theta=two_theta, intensity=float(inten)))

    # v2 side: read the entries through the v2 SQL path.
    conn = sqlite3.connect(f"file:{v2_path.as_posix()}?mode=ro", uri=True)
    try:
        v2_entries = []
        for entry in sample_entries:
            rows = conn.execute(
                "SELECT d, intensity FROM peaks WHERE entry_id = ? "
                "ORDER BY intensity DESC",
                (entry.entry_id,),
            ).fetchall()
            v2_entries.append(
                Entry(
                    entry_id=entry.entry_id,
                    formula=entry.formula,
                    d_spacings=np.array([r[0] for r in rows], dtype=np.float64),
                    intensities=np.array([r[1] for r in rows], dtype=np.float64),
                    mineral_name=entry.mineral_name,
                    cell=entry.cell,
                    space_group=entry.space_group,
                    elements=entry.elements,
                )
            )
        v2_ranked = rank_candidates(exp_peaks, v2_entries, wavelength)
    finally:
        conn.close()

    # v3 side: read the same entries through the columnar reader.
    with XinDBReader(v3_path) as reader:
        v3_entries = []
        for entry in sample_entries:
            meta = reader.fetch_entry(entry.entry_id)
            assert meta is not None
            v3_entries.append(_entry_from_meta(meta))
        v3_ranked = rank_candidates(exp_peaks, v3_entries, wavelength)

    assert len(v2_ranked) == len(v3_ranked)
    for v2_result, v3_result in zip(v2_ranked, v3_ranked, strict=True):
        assert v2_result.entry.entry_id == v3_result.entry.entry_id
        # The scores must agree within the float32 storage budget.
        assert abs(v2_result.fom - v3_result.fom) < 1e-3


def test_probe_rejects_non_xindb(tmp_path, sample_entries):
    """The v3 probe refuses a v2 database and accepts a v3 one."""
    v2_path = tmp_path / "v2.db"
    v3_path = tmp_path / "v3.xinDB"
    _build_v2_db(v2_path, sample_entries)
    _build_v3_db(v3_path, sample_entries)

    assert XinDBReader(v2_path).probe()[0] is False
    assert XinDBReader(v3_path).probe()[0] is True
    assert XinDBReader(tmp_path / "missing.xinDB").probe() == (
        False,
        "file_not_found",
    )


def test_prescreen_recall_is_complete(tmp_path, sample_entries):
    """Every phase that hits a measurement window is offered as a candidate.

    The prescreen must not silently drop a phase that a full scan would
    have found — that is the accuracy guarantee behind the speed-up.
    """
    v3_path = tmp_path / "v3.xinDB"
    _build_v3_db(v3_path, sample_entries)

    with XinDBReader(v3_path) as reader:
        for entry in sample_entries:
            # A window centred on this phase's strongest line.
            d0 = float(entry.d_spacings[0])
            result = reader.prescreen([d0], tolerance=0.02, min_match=1)
            assert entry.entry_id in result.candidate_ids, (
                f"{entry.entry_id} missing from prescreen"
            )
