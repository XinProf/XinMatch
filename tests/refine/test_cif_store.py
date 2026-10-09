"""CIF matching / export helpers (core.refine.cif_store)."""
from __future__ import annotations

from pathlib import Path

import pytest

from xinmatch.core.refine.cif_store import (
    cod_cif_path,
    export_cifs,
    match_entry_cifs,
    ref_id_to_cod_id,
    resolve_entry_cif,
)


# ---------------------------------------------------------------------------
# ref_id → COD id
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("ref_id", "cod_id"),
    [
        ("96-100-0005", 1000005),
        ("96-400-1849", 4001849),
        ("96-230-0112", 2300112),
        ("96-900-0381", 9000381),
        ("96-720-6076", 7206076),
    ],
)
def test_ref_id_to_cod_id(ref_id: str, cod_id: int) -> None:
    assert ref_id_to_cod_id(ref_id) == cod_id


@pytest.mark.parametrize("bad", ["100-0005", "96-100", "96-AB-1849", "abc-def-ghij", ""])
def test_ref_id_to_cod_id_rejects_malformed(bad: str) -> None:
    with pytest.raises(ValueError):
        ref_id_to_cod_id(bad)


# ---------------------------------------------------------------------------
# COD archive path layout
# ---------------------------------------------------------------------------
def test_cod_cif_path_layout() -> None:
    p = cod_cif_path(1000005, root=r"C:\cod")
    assert p == Path(r"C:\cod\1\00\00\1000005.cif")


def test_cod_cif_path_zero_padding() -> None:
    p = cod_cif_path(5, root=r"C:\cod")
    assert p == Path(r"C:\cod\0\00\00\0000005.cif")


# ---------------------------------------------------------------------------
# match_entry_cifs against a synthetic COD tree
# ---------------------------------------------------------------------------
@pytest.fixture
def cod_root(tmp_path: Path) -> Path:
    """Synthetic COD archive: two entries present, one missing."""
    root = tmp_path / "cod"
    for cod_id in (4001849, 2300112):
        rel = cod_cif_path(cod_id, root=root)
        rel.parent.mkdir(parents=True, exist_ok=True)
        rel.write_text(f"data_{cod_id}\n", encoding="utf-8")
    return root


def test_match_entry_cifs_finds_existing(cod_root: Path) -> None:
    matched = match_entry_cifs(["96-400-1849", "96-230-0112"], root=cod_root)
    assert set(matched) == {"96-400-1849", "96-230-0112"}
    assert matched["96-400-1849"].is_file()


def test_match_entry_cifs_skips_missing(cod_root: Path) -> None:
    matched = match_entry_cifs(["96-400-1849", "96-900-9231"], root=cod_root)
    assert set(matched) == {"96-400-1849"}


def test_resolve_entry_cif_missing_returns_none(cod_root: Path) -> None:
    assert resolve_entry_cif("96-900-9231", root=cod_root) is None
    assert resolve_entry_cif("not-an-id", root=cod_root) is None


# ---------------------------------------------------------------------------
# export_cifs
# ---------------------------------------------------------------------------
def test_export_cifs_copies_into_out_dir(cod_root: Path, tmp_path: Path) -> None:
    matched = match_entry_cifs(["96-400-1849"], root=cod_root)
    out = tmp_path / "work"
    exported = export_cifs(matched, out)
    assert exported["96-400-1849"] == out / "96-400-1849.cif"
    assert exported["96-400-1849"].read_text(encoding="utf-8") == (
        "data_4001849\n"
    )
    # COD archive untouched (source file still in place)
    assert cod_cif_path(4001849, root=cod_root).is_file()


def test_export_cifs_skips_missing_sources(tmp_path: Path) -> None:
    exported = export_cifs({"96-400-1849": tmp_path / "nope.cif"}, tmp_path / "out")
    assert exported == {}
