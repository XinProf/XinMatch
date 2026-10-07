"""Insert reference-database entries into SQLite (Phase 5 / T5.1, T5.6).

Implements the "add entry to reference database" workflow used by Match!'s
*Reference Database → Create User Database* and COD import.  An
:class:`~xinmatch.core.model.Entry` is written to three tables:

* ``entries``  — scalar metadata (formula, cell, space group, ...)
* ``peaks``    — the d–I peak table
* ``elements`` — one row per element (inverted-index materialisation)
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterable

import numpy as np

from xinmatch.core.model import CellParams, Entry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Crystal-system derivation
# ---------------------------------------------------------------------------
# Match! exposes "crystal system" as a searchable field.  COD entries usually
# carry a space-group number; from the number (1-230) the crystal system is
# unambiguously defined by these ranges.
_SG_NUMBER_TO_SYSTEM: list[tuple[int, int, str]] = [
    (1, 2, "triclinic"),
    (3, 15, "monoclinic"),
    (16, 74, "orthorhombic"),
    (75, 142, "tetragonal"),
    (143, 167, "trigonal"),
    (168, 194, "hexagonal"),
    (195, 230, "cubic"),
]

# Small lookup of the most common Hermann–Mauguin symbols -> number, so we can
# derive the crystal system from ``Entry.space_group`` without gemmi.  This is
# intentionally a short, representative list; unknown symbols fall back to
# cell-parameter heuristics.
_HM_TO_SG_NUMBER: dict[str, int] = {
    "P1": 1, "P-1": 2,
    "P2": 3, "P21": 4, "C2": 5,
    "Pm": 6, "Pc": 7, "Cm": 8, "Cc": 9,
    "P2/m": 10, "P21/m": 11, "C2/m": 12,
    "P2/c": 13, "P21/c": 14, "C2/c": 15,
    "P222": 16, "P2221": 17, "P21212": 18, "P212121": 19,
    "C2221": 20, "C222": 21, "F222": 22, "I222": 23, "I212121": 24,
    "Pmm2": 25, "Pmc21": 26, "Pcc2": 27, "Pma2": 28, "Pca21": 29,
    "Pnc2": 30, "Pmn21": 31, "Pba2": 32, "Pna21": 33, "Pnn2": 34,
    "Cmm2": 35, "Cmc21": 36, "Ccc2": 37,
    "Amm2": 38, "Abm2": 39, "Ama2": 40, "Aba2": 41,
    "Fmm2": 42, "Fdd2": 43, "Imm2": 44, "Iba2": 45, "Ima2": 46,
    "Pmmm": 47, "Pnnn": 48, "Pccm": 49, "Pban": 50, "Pmma": 51,
    "Pnna": 52, "Pmna": 53, "Pcca": 54, "Pncm": 55, "Pmcn": 56,
    "Pbcm": 57, "Pnnm": 58, "Pmmn": 59, "Pbcn": 60, "Pbca": 61, "Pnma": 62,
    "Cmcm": 63, "Cmce": 64, "Cmmm": 65, "Cccm": 66, "Cmme": 67, "Ccec": 68,
    "Fmmm": 69, "Fddd": 70,
    "Immm": 71, "Ibam": 72, "Ibca": 73, "Imma": 74,
    "P4": 75, "P41": 76, "P42": 77, "P43": 78, "I4": 79, "I41": 80,
    "P-4": 81, "I-4": 82,
    "P4/m": 83, "P42/m": 84, "P4/n": 85, "P42/n": 86, "I4/m": 87, "I41/a": 88,
    "P422": 89, "P4212": 90, "P4122": 91, "P41212": 92, "P4222": 93, "P42212": 94,
    "P4322": 95, "P43212": 96, "I422": 97, "I4122": 98,
    "P4mm": 99, "P4bm": 100, "P42cm": 101, "P42nm": 102,
    "P4cc": 103, "P4nc": 104, "P42mc": 105, "P42bc": 106,
    "I4mm": 107, "I4cm": 108, "I41md": 109, "I41cd": 110,
    "P-42m": 111, "P-42c": 112, "P-421m": 113, "P-421c": 114,
    "P-4m2": 115, "P-4c2": 116, "P-4b2": 117, "P-4n2": 118,
    "I-4m2": 119, "I-4c2": 120, "I-42m": 121, "I-42d": 122,
    "P4/mmm": 123, "P4/mcc": 124, "P4/nbm": 125, "P4/nnc": 126,
    "P4/mbm": 127, "P4/mnc": 128, "P4/nmm": 129, "P4/ncc": 130,
    "P42/mmc": 131, "P42/mcm": 132, "P42/nbc": 133, "P42/nnm": 134,
    "P42/mbc": 135, "P42/mnm": 136, "P42/nmc": 137, "P42/ncm": 138,
    "I4/mmm": 139, "I4/mcm": 140, "I41/amd": 141, "I41/acd": 142,
    "P3": 143, "P31": 144, "P32": 145, "R3": 146,
    "P-3": 147, "R-3": 148,
    "P312": 149, "P321": 150, "P3112": 151, "P3121": 152, "P3212": 153, "P3221": 154,
    "R32": 155,
    "P3m1": 156, "P31m": 157, "P3c1": 158, "P31c": 159, "R3m": 160, "R3c": 161,
    "P-31m": 162, "P-31c": 163, "P-3m1": 164, "P-3c1": 165, "R-3m": 166, "R-3c": 167,
    "P6": 168, "P61": 169, "P65": 170, "P62": 171, "P64": 172, "P63": 173,
    "P-6": 174,
    "P6/m": 175, "P63/m": 176,
    "P622": 177, "P6122": 178, "P6522": 179, "P6222": 180, "P6422": 181, "P6322": 182,
    "P6mm": 183, "P6cc": 184, "P63cm": 185, "P63mc": 186,
    "P-6m2": 187, "P-6c2": 188, "P-62m": 189, "P-62c": 190,
    "P6/mmm": 191, "P6/mcc": 192, "P63/mcm": 193, "P63/mmc": 194,
    "P23": 195, "F23": 196, "I23": 197, "P213": 198, "I213": 199,
    "Pm-3": 200, "Pn-3": 201, "Fm-3": 202, "Fd-3": 203, "Im-3": 204, "Pa-3": 205, "Ia-3": 206,
    "P432": 207, "P4232": 208, "F432": 209, "F4132": 210, "I432": 211, "P4332": 212,
    "P4132": 213, "I4132": 214,
    "P-43m": 215, "F-43m": 216, "P-43n": 217, "F-43c": 218, "I-43m": 219, "I-43d": 220,
    "Pm-3m": 221, "Pn-3n": 222, "Pm-3n": 223, "Pn-3m": 224,
    "Fm-3m": 225, "Fm-3c": 226, "Fd-3m": 227, "Fd-3c": 228,
    "Im-3m": 229, "Ia-3d": 230,
}


def space_group_number(space_group: str | None) -> int | None:
    """Map a Hermann–Mauguin space-group symbol to its number (1-230).

    Returns ``None`` if the symbol is unknown.

    Parameters
    ----------
    space_group:
        Hermann–Mauguin symbol, e.g. ``"Pm-3m"``, ``"R-3c"``.
    """
    if not space_group:
        return None
    sg = space_group.strip()
    return _HM_TO_SG_NUMBER.get(sg)


def crystal_system_from_sg_number(number: int | None) -> str | None:
    """Return the crystal system for a space-group number.

    Parameters
    ----------
    number:
        Space-group number 1-230.
    """
    if number is None:
        return None
    for lo, hi, system in _SG_NUMBER_TO_SYSTEM:
        if lo <= number <= hi:
            return system
    return None


def crystal_system_from_cell(cell: CellParams | None) -> str | None:
    """Guess the crystal system from unit-cell parameters.

    Used as a fallback when the space-group symbol is not in our lookup table.
    Comparisons use :func:`numpy.isclose` with a 1 % relative tolerance so
    small numerical noise does not flip the system.

    Parameters
    ----------
    cell:
        Unit-cell parameters.
    """
    if cell is None:
        return None
    a, b, c = cell.a, cell.b, cell.c
    al, be, ga = cell.alpha, cell.beta, cell.gamma
    ninety = 90.0
    rtol = 0.01
    ab = np.isclose(a, b, rtol=rtol)
    bc = np.isclose(b, c, rtol=rtol)
    ac = np.isclose(a, c, rtol=rtol)
    al90 = np.isclose(al, ninety, rtol=rtol)
    be90 = np.isclose(be, ninety, rtol=rtol)
    ga90 = np.isclose(ga, ninety, rtol=rtol)
    ga120 = np.isclose(ga, 120.0, rtol=rtol)
    if ab and bc and al90 and be90 and ga90:
        return "cubic"
    if ab and (not bc) and al90 and be90 and ga90:
        return "tetragonal"
    if (not ab) and (not bc) and (not ac) and al90 and be90 and ga90:
        return "orthorhombic"
    if ab and (not bc) and al90 and be90 and ga120:
        return "hexagonal"
    if ab and bc and (not (al90 and be90 and ga90)) and np.isclose(al, be, rtol=rtol) and np.isclose(be, ga, rtol=rtol):
        return "trigonal"
    if al90 and ga90 and (not be90):
        return "monoclinic"
    return "triclinic"


def derive_crystal_system(entry: Entry) -> str | None:
    """Derive the crystal system for *entry* (SG number first, cell fallback)."""
    num = space_group_number(entry.space_group)
    sys = crystal_system_from_sg_number(num)
    if sys is not None:
        return sys
    return crystal_system_from_cell(entry.cell)


# ---------------------------------------------------------------------------
# Insert helpers
# ---------------------------------------------------------------------------
def _entry_row(entry: Entry) -> tuple:
    """Build the row tuple for the ``entries`` table from *entry*."""
    cell = entry.cell
    a = b = c = alpha = beta = gamma = volume = density = None
    if cell is not None:
        a, b, c = cell.a, cell.b, cell.c
        alpha, beta, gamma = cell.alpha, cell.beta, cell.gamma
        volume = _cell_volume(cell)
    lit = entry.literature or {}
    year = lit.get("year")
    if year is not None:
        year = int(year)
    return (
        entry.entry_id,
        entry.formula,
        entry.mineral_name,
        entry.space_group,
        derive_crystal_system(entry),
        a, b, c, alpha, beta, gamma, volume, density,
        lit.get("color"),
        year,
        lit.get("author"),
        lit.get("journal"),
        entry.quality,
        ",".join(sorted(entry.elements)),
    )


def _cell_volume(cell: CellParams) -> float:
    """Compute unit-cell volume (Å³) from cell parameters.

    Formula: V = abc * sqrt(1 - cos²α - cos²β - cos²γ + 2 cosα cosβ cosγ).
    """
    a, b, c = cell.a, cell.b, cell.c
    ca = np.cos(np.radians(cell.alpha))
    cb = np.cos(np.radians(cell.beta))
    cg = np.cos(np.radians(cell.gamma))
    return float(a * b * c * np.sqrt(1 - ca**2 - cb**2 - cg**2 + 2 * ca * cb * cg))


def insert_entry(conn: sqlite3.Connection, entry: Entry) -> None:
    """Insert a single :class:`Entry` into the database.

    Implements Match!'s *Reference Database → Create User Database*
    single-entry insertion (Phase 5 / T5.1).  Writes the ``entries``,
    ``peaks``, and ``elements`` tables atomically within one transaction.

    Parameters
    ----------
    conn:
        Open SQLite connection with the schema already created.
    entry:
        Reference-database entry to persist.
    """
    with conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO entries
            (entry_id, formula, mineral_name, space_group, crystal_system,
             a, b, c, alpha, beta, gamma, volume, density, color,
             year, author, journal, quality, elements)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            _entry_row(entry),
        )
        # peaks
        ds = entry.d_spacings
        intensities = entry.intensities
        hkl = entry.hkl or []
        rows = []
        for i in range(ds.size):
            h = k = ell = None
            if i < len(hkl):
                h, k, ell = hkl[i]
            rows.append((entry.entry_id, float(ds[i]), float(intensities[i]) if i < intensities.size else None, h, k, ell))
        conn.executemany(
            "INSERT INTO peaks (entry_id, d, intensity, h, k, l) VALUES (?,?,?,?,?,?)",
            rows,
        )
        # elements inverted index
        elem_rows = [(entry.entry_id, elem) for elem in sorted(entry.elements)]
        conn.executemany(
            "INSERT OR IGNORE INTO elements (entry_id, element) VALUES (?,?)",
            elem_rows,
        )
    logger.debug("inserted entry %s (%d peaks)", entry.entry_id, ds.size)


def insert_entries(conn: sqlite3.Connection, entries: Iterable[Entry]) -> int:
    """Insert multiple entries in batch.

    Implements bulk COD import (Phase 5 / T5.1).  Uses ``executemany`` for
    each table and wraps everything in one transaction.

    Parameters
    ----------
    conn:
        Open SQLite connection with the schema already created.
    entries:
        Iterable of :class:`Entry` objects.

    Returns
    -------
    int
        Number of entries inserted.
    """
    entry_rows: list[tuple] = []
    peak_rows: list[tuple] = []
    elem_rows: list[tuple] = []
    count = 0
    for entry in entries:
        entry_rows.append(_entry_row(entry))
        ds = entry.d_spacings
        intensities = entry.intensities
        hkl = entry.hkl or []
        for i in range(ds.size):
            h = k = ell = None
            if i < len(hkl):
                h, k, ell = hkl[i]
            peak_rows.append((
                entry.entry_id, float(ds[i]),
                float(intensities[i]) if i < intensities.size else None,
                h, k, ell,
            ))
        for elem in sorted(entry.elements):
            elem_rows.append((entry.entry_id, elem))
        count += 1

    with conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO entries
            (entry_id, formula, mineral_name, space_group, crystal_system,
             a, b, c, alpha, beta, gamma, volume, density, color,
             year, author, journal, quality, elements)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            entry_rows,
        )
        conn.executemany(
            "INSERT INTO peaks (entry_id, d, intensity, h, k, l) VALUES (?,?,?,?,?,?)",
            peak_rows,
        )
        conn.executemany(
            "INSERT OR IGNORE INTO elements (entry_id, element) VALUES (?,?)",
            elem_rows,
        )
    logger.info("bulk-inserted %d entries", count)
    return count
