"""Unit tests for the COD CIF archive scanner (M1-S1.1, v3.0.0 rebuild).

The traversal tests build a synthetic archive in ``tmp_path`` that mirrors
the real COD fan-out layout, so the suite stays fast and does not depend
on the 535 K-file archive being present on the machine running it.  The
tests that do touch the real archive are marked ``slow`` (excluded from
the default run by ``-m "not slow"``) and skip when the archive is absent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from xinmatch.core.db.cif_scan import (
    DEFAULT_COD_ROOT,
    DEFAULT_INORG_COD_ROOT,
    cod_cif_relpath,
    cod_id_from_stem,
    count_cif_files,
    entry_id_for_cod,
    iter_cod_cifs,
)


def _make_archive(root: Path, cod_ids: list[int]) -> Path:
    """Create a COD-style archive containing one CIF per id in *cod_ids*."""
    for cod_id in cod_ids:
        path = root / cod_cif_relpath(cod_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("data_test\n", encoding="utf-8")
    return root


@pytest.fixture()
def archive(tmp_path: Path) -> Path:
    """Synthetic archive with ids 1000000..1000009 plus a 2nd branch."""
    return _make_archive(tmp_path / "COD", [1000000 + i for i in range(10)])


# ---------------------------------------------------------------------------
# Pure id / path rules
# ---------------------------------------------------------------------------
def test_cod_cif_relpath_layout() -> None:
    assert cod_cif_relpath(1000005) == "1/00/00/1000005.cif"
    assert cod_cif_relpath(1000000) == "1/00/00/1000000.cif"
    assert cod_cif_relpath(4001849) == "4/00/18/4001849.cif"
    assert cod_cif_relpath(9010203) == "9/01/02/9010203.cif"
    # POSIX separators regardless of the host platform.
    assert "\\" not in cod_cif_relpath(1000005)


def test_cod_cif_relpath_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        cod_cif_relpath(-1)
    with pytest.raises(ValueError):
        cod_cif_relpath(10_000_000)


def test_cod_id_from_stem() -> None:
    assert cod_id_from_stem("1000005.cif") == 1000005
    assert cod_id_from_stem("1000005") == 1000005
    assert cod_id_from_stem(" 1000005.cif ") == 1000005
    assert cod_id_from_stem("abc") is None
    assert cod_id_from_stem("") is None
    assert cod_id_from_stem("12a") is None
    assert cod_id_from_stem("1000005.dic") is None
    # ``str.isdigit`` accepts superscripts that ``int`` rejects.
    assert cod_id_from_stem("\u00b2") is None


def test_entry_id_for_cod() -> None:
    assert entry_id_for_cod(1000005) == "96-100-0005"
    assert entry_id_for_cod(1000000) == "96-100-0000"
    assert entry_id_for_cod(4001849) == "96-400-1849"
    assert entry_id_for_cod(9010203) == "96-901-0203"
    assert entry_id_for_cod(9999999) == "96-999-9999"


# ---------------------------------------------------------------------------
# Traversal
# ---------------------------------------------------------------------------
def test_iter_cod_cifs_yields_cod_id_and_existing_path(archive: Path) -> None:
    entries = list(iter_cod_cifs(archive))
    assert [cid for cid, _ in entries] == [1000000 + i for i in range(10)]
    for cid, path in entries:
        assert path.is_file()
        assert path.relative_to(archive).as_posix() == cod_cif_relpath(cid)


def test_iter_cod_cifs_is_ascending_by_cod_id(archive: Path) -> None:
    ids = [cid for cid, _ in iter_cod_cifs(archive)]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))


def test_iter_cod_cifs_limit_slices(archive: Path) -> None:
    assert [cid for cid, _ in iter_cod_cifs(archive, limit=3)] == [
        1000000,
        1000001,
        1000002,
    ]
    assert list(iter_cod_cifs(archive, limit=0)) == []
    assert list(iter_cod_cifs(archive, limit=-1)) == []


def test_iter_cod_cifs_start_filters(archive: Path) -> None:
    assert [cid for cid, _ in iter_cod_cifs(archive, start=1000005)] == [
        1000005,
        1000006,
        1000007,
        1000008,
        1000009,
    ]
    assert [cid for cid, _ in iter_cod_cifs(archive, start=1000005, limit=2)] == [
        1000005,
        1000006,
    ]
    assert list(iter_cod_cifs(archive, start=9_999_999)) == []


def test_iter_cod_cifs_spans_multiple_branches(tmp_path: Path) -> None:
    """Ids from different top-level branches must come out in one ascending run."""
    root = _make_archive(
        tmp_path / "COD", [1000005, 4001849, 9010203, 2000001, 1234567]
    )
    ids = [cid for cid, _ in iter_cod_cifs(root)]
    assert ids == sorted(ids)
    assert set(ids) == {1000005, 1234567, 2000001, 4001849, 9010203}


def test_iter_cod_cifs_skips_dictionaries_by_default(tmp_path: Path) -> None:
    root = tmp_path / "COD"
    _make_archive(root, [1000000, 1000001])
    dictionary = root / "dictionaries" / "ddl1"
    dictionary.mkdir(parents=True)
    (dictionary / "cif_cod_0.036.dic").write_text("x", encoding="utf-8")
    # A .cif inside the dictionaries subtree must not be picked up by default.
    (dictionary / "9999999.cif").write_text("x", encoding="utf-8")

    ids = [cid for cid, _ in iter_cod_cifs(root)]
    assert ids == [1000000, 1000001]

    with_dicts = [cid for cid, _ in iter_cod_cifs(root, include_dictionaries=True)]
    assert 9999999 in with_dicts


def test_iter_cod_cifs_ignores_non_numeric_cif_names(tmp_path: Path) -> None:
    root = tmp_path / "COD"
    _make_archive(root, [1000000])
    (root / "1" / "00" / "00" / "notes.cif").write_text("x", encoding="utf-8")
    assert [cid for cid, _ in iter_cod_cifs(root)] == [1000000]


def test_iter_cod_cifs_missing_root_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        list(iter_cod_cifs(tmp_path / "nope"))


def test_count_cif_files(archive: Path) -> None:
    assert count_cif_files(archive) == 10


# ---------------------------------------------------------------------------
# Real archive (opt-in via the ``slow`` marker)
# ---------------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.skipif(
    not DEFAULT_COD_ROOT.is_dir(), reason="real COD archive not present"
)
def test_real_archive_layout_and_count() -> None:
    first = list(iter_cod_cifs(DEFAULT_COD_ROOT, limit=10))
    assert len(first) == 10
    for cid, path in first:
        assert path.is_file()
        assert path.relative_to(DEFAULT_COD_ROOT).as_posix() == cod_cif_relpath(cid)
    assert count_cif_files(DEFAULT_COD_ROOT) == 535166


@pytest.mark.slow
@pytest.mark.skipif(
    not DEFAULT_INORG_COD_ROOT.is_dir(), reason="real inorg archive not present"
)
def test_real_inorg_archive_count() -> None:
    assert count_cif_files(DEFAULT_INORG_COD_ROOT) == 79198
