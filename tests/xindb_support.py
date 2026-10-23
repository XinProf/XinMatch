"""Helpers to build tiny v3 ``.xinDB`` reference libraries for tests.

v3.0.0 removed every legacy reference format (v2 ``entries``/``peaks``/
``elements`` SQLite, PolyXRD dumps, PDF-2 dumps), so tests can no longer hand a
SQLite file to the search code: they must produce a real columnar ``.xinDB``.
:func:`write_xindb` wraps :class:`~xinmatch.core.db.writer_v3.XinDBWriter` so a
test only has to supply :class:`~xinmatch.core.model.Entry` objects.

Usage::

    from tests.xindb_support import write_xindb

    db = write_xindb(tmp_path / "ref.xinDB", [truth, decoy])
    result = run_cli("search", str(pattern), "--db", str(db))
"""

from __future__ import annotations

from pathlib import Path

from xinmatch.core.model import Entry

__all__ = ["entry_to_meta", "write_xindb"]


def entry_to_meta(entry: Entry):
    """Convert an :class:`Entry` into the :class:`PhaseMeta` the writer wants.

    The writer indexes on ``CellParams`` + element list; ``hkl`` and the
    literature dict are not part of the v3 metadata (``hkl`` is optional in the
    file and left empty, which is what COD-Inorg ships anyway).
    """
    from xinmatch.core.db.cif_meta import PhaseMeta

    cell = entry.cell
    return PhaseMeta(
        entry_id=entry.entry_id,
        formula=entry.formula,
        elements=sorted(entry.elements),
        space_group=entry.space_group or "",
        crystal_system="triclinic",
        mineral_name=entry.mineral_name or "",
        cell=(
            (
                cell.a,
                cell.b,
                cell.c,
                cell.alpha,
                cell.beta,
                cell.gamma,
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


def write_xindb(path, entries: list[Entry]) -> Path:
    """Write *entries* into a v3 columnar ``.xinDB`` library at *path*.

    The file is created (or truncated) — pass a path under ``tmp_path``.
    """
    from xinmatch.core.db.writer_v3 import XinDBWriter

    target = Path(path)
    writer = XinDBWriter(target, tier=1)
    try:
        for entry in entries:
            writer.add(
                entry_to_meta(entry),
                entry.d_spacings,
                entry.intensities,
            )
    finally:
        writer.close()
    return target
