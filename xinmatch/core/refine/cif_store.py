"""CIF matching & export helpers for the Rietveld refinement loop (T8.3 / T13.8).

Problem being solved
--------------------
The :class:`~xinmatch.core.model.entry.Entry` data model carries no CIF path,
and GSAS-II needs a CIF per phase.  After a search-match the user has ranked
candidate phases; this module resolves each candidate's *standard* CIF from
the local COD archive and optionally **exports** those CIFs into a working
directory so that:

1. ``build_gsas2_project`` can be called with an explicit
   ``entry_id -> CIF path`` mapping;
2. the exported CIFs are user-visible artefacts (Match! equivalent:
   ``docs/import_udb_entry_cif.md`` — importing structure data from CIF;
   ``docs/export_entry_data.md`` — exporting entry data for reuse);
3. after a refinement, the refined CIFs written by GSAS-II
   (``*_new.cif``) can be located and shown in the 3D viewer.

The local COD archive is **read-only**; exporting copies CIFs *out* of it
into a caller-provided directory.  Nothing here ever writes into the COD
archive.

Path rules (verified against the real 522 K-file archive)
----------------------------------------------------------
* XinMatch entry id (PolyXRD ``ref_id``, e.g. ``"96-400-1849"``) → numeric
  COD id by arithmetic concatenation of the middle and last ``-`` groups
  (0 mismatches over the full dump).
* Numeric COD id → ``{d}/{dd}/{dd}/{id:07d}.cif`` under the archive root.

These two helpers live in ``core`` (not ``ui``) so that CLI / batch /
GSAS-II pipelines can use them without a Qt import.
"""

from __future__ import annotations

import shutil
from pathlib import Path

__all__ = [
    "DEFAULT_COD_ROOT",
    "cod_cif_path",
    "export_cifs",
    "match_entry_cifs",
    "ref_id_to_cod_id",
    "resolve_entry_cif",
]

#: Local COD CIF archive root (read-only; 522 K files).  Overridable via the
#: ``XINMATCH_COD_ROOT`` environment variable or a function argument.
DEFAULT_COD_ROOT = Path(r"D:\Project\XRD\PolyXRD\cod\cif")


def _cod_root(root: str | Path | None) -> Path:
    if root is not None:
        return Path(root)
    env = __import__("os").environ.get("XINMATCH_COD_ROOT")
    return Path(env) if env else DEFAULT_COD_ROOT


# ---------------------------------------------------------------------------
# Pure path / id helpers
# ---------------------------------------------------------------------------
def ref_id_to_cod_id(ref_id: str) -> int:
    """Convert a XinMatch entry id (PolyXRD ``ref_id``) to a numeric COD id.

    ``"96-100-0005"`` → ``1000005``.  Raises :class:`ValueError` when the id
    is not in the ``NN-NNN-NNNN`` ref_id shape.
    """
    parts = ref_id.strip().split("-")
    if len(parts) != 3 or not (parts[1] + parts[2]).isdigit():
        raise ValueError(
            f"not a PolyXRD ref_id: {ref_id!r} (expected e.g. '96-400-1849')"
        )
    return int(parts[1] + parts[2])


def cod_cif_path(cod_id: int, root: str | Path | None = None) -> Path:
    """Numeric COD id → CIF path under the archive *root*.

    Layout (verified on the real archive): the 7-digit-zero-padded id is split
    as ``{first}/{next two}/{next two}/{id:07d}.cif`` — e.g. id ``1000005``
    → ``1/00/00/1000005.cif``.
    """
    s = str(int(cod_id)).zfill(7)
    base = _cod_root(root)
    return Path(base) / s[0] / s[1:3] / s[3:5] / f"{s}.cif"


def resolve_entry_cif(
    entry_id: str, root: str | Path | None = None
) -> Path | None:
    """Resolve a XinMatch entry id to an existing COD CIF, or ``None``."""
    try:
        path = cod_cif_path(ref_id_to_cod_id(entry_id), root)
    except ValueError:
        return None
    return path if path.is_file() else None


# ---------------------------------------------------------------------------
# Match & export
# ---------------------------------------------------------------------------
def match_entry_cifs(
    entry_ids: list[str] | tuple[str, ...],
    root: str | Path | None = None,
) -> dict[str, Path]:
    """Match a set of candidate entry ids to existing COD CIFs.

    Parameters
    ----------
    entry_ids:
        Candidate entry ids (e.g. ``["96-400-1849", "96-230-0112"]``).
    root:
        COD archive root (defaults to :data:`DEFAULT_COD_ROOT` /
        ``XINMATCH_COD_ROOT``).

    Returns
    -------
    dict
        ``entry_id -> CIF path`` for every id that resolved to an existing
        file.  Ids without a CIF in the archive are simply absent (callers
        report them as "no CIF found", the way Match! reports a missing
        database entry).
    """
    out: dict[str, Path] = {}
    for eid in entry_ids:
        cif = resolve_entry_cif(eid, root)
        if cif is not None:
            out[eid] = cif
    return out


def export_cifs(
    cif_map: dict[str, str | Path],
    out_dir: str | Path,
) -> dict[str, Path]:
    """Copy matched CIFs into *out_dir* (created if needed).

    The COD archive is never written to — this copies *from* it (or from any
    caller-provided source paths) into a user working directory, so the CIFs
    become durable, user-visible artefacts (e.g. for a GSAS-II working folder).

    Parameters
    ----------
    cif_map:
        ``entry_id -> source CIF path`` (e.g. from :func:`match_entry_cifs`).
    out_dir:
        Target directory; created when missing.

    Returns
    -------
    dict
        ``entry_id -> exported CIF path``.  Files are named
        ``{entry_id}.cif`` in *out_dir* (source filename is not preserved, so
        the mapping stays explicit and collision-free).
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    exported: dict[str, Path] = {}
    for eid, src in cif_map.items():
        src_path = Path(src)
        if not src_path.is_file():
            continue
        dst = out / f"{eid}.cif"
        shutil.copyfile(src_path, dst)
        exported[eid] = dst
    return exported
