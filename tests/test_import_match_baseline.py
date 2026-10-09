"""Tests for :mod:`tools.import_match_baseline` (T0.3 / T0.4).

The conversion is exercised against *synthetic* raw reference-software exports that
deliberately carry the quirks a hand-exported CSV may have:

* UTF-8 BOM / European decimal commas (``0,8585``);
* header drift (``I scale fct`` without the trailing dot);
* optional columns left blank;
* malformed rows (empty Entry / unparseable FoM).

The round-trip invariant is the acceptance criterion: every converted file
must be re-loadable by the production loader
:func:`tools.match_baseline.load_match_csv` with the expected candidates.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.import_match_baseline import (
    CANONICAL_HEADER,
    convert_dir,
    convert_file,
)
from tools.match_baseline import load_match_csv

# A raw export with European decimal commas, a drifted header alias, blank
# optional cells and two deliberately malformed rows.
RAW_CSV = (
    "Candidate list of sample 1-1\n"
    "Entry;Qual.;Formula sum;Name;P(peakpos.);P(I/I0);P(#peaks);P(#corr.);"
    "I scale fct;FoM\n"
    "96-400-1849;C;Fe Li O4 P;Lithium Iron Phosphate(V);0,0098;n.a.;0,0000;"
    "n.a.;0,7128;0,8585\n"
    "96-400-1848;C;Fe Li O4 P;;n.a.;n.a.;0,0000;n.a.;0,7127;0,9989\n"
    ";C;X Y;;n.a.;n.a.;0;n.a.;1,0;0,5\n"          # empty Entry -> rejected
    "96-xyz;C;X Y;;;n.a.;n.a.;abc;\n"              # missing FoM -> rejected
)


def _write_raw(path: Path, text: str = RAW_CSV, *, bom: bool = False) -> Path:
    data = text.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)
    return path


# --------------------------------------------------------------------------- #
# convert_file
# --------------------------------------------------------------------------- #
def test_convert_file_writes_canonical_header(tmp_path: Path):
    src = _write_raw(tmp_path / "1-1.csv")
    res = convert_file(src, tmp_path / "out" / "1-1.csv")

    assert res.sample_id == "1-1"
    assert res.n_rows_written == 2
    assert len(res.rejected) == 2
    reasons = " ".join(r.reason for r in res.rejected)
    assert "Entry" in reasons
    assert "FoM" in reasons

    out_lines = res.output.read_text(encoding="utf-8").splitlines()
    assert out_lines[0] == "Candidate list of sample 1-1"
    assert out_lines[1] == ";".join(CANONICAL_HEADER)


def test_convert_file_normalises_decimal_comma_and_sorts(tmp_path: Path):
    src = _write_raw(tmp_path / "1-1.csv")
    res = convert_file(src, tmp_path / "out" / "1-1.csv")

    # Round-trip through the PRODUCTION loader.
    bl = load_match_csv(res.output)
    assert bl.sample_id == "1-1"
    assert len(bl.candidates) == 2
    # Sorted by FoM descending: 0.9989 must come first.
    assert bl.candidates[0].entry_id == "96-400-1848"
    assert bl.candidates[0].fom == pytest.approx(0.9989, abs=1e-4)
    # European decimal comma was normalised to a dot.
    assert bl.candidates[0].i_scale == pytest.approx(0.7127, abs=1e-4)
    assert bl.candidates[1].p_peakpos == pytest.approx(0.0098, abs=1e-4)
    # n.a. cells map to None.
    assert bl.candidates[0].p_intensity is None


def test_convert_file_bom_tolerated(tmp_path: Path):
    src = _write_raw(tmp_path / "bom.csv", bom=True)
    res = convert_file(src, tmp_path / "out" / "bom.csv")
    bl = load_match_csv(res.output)
    assert len(bl.candidates) == 2


def test_convert_file_missing_header_raises(tmp_path: Path):
    src = tmp_path / "junk.csv"
    src.write_text("a;b;c\n1;2;3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="header"):
        convert_file(src, tmp_path / "out" / "junk.csv")


# --------------------------------------------------------------------------- #
# convert_dir
# --------------------------------------------------------------------------- #
def test_convert_dir_batch(tmp_path: Path):
    src_dir = tmp_path / "raw"
    src_dir.mkdir()
    _write_raw(src_dir / "1-1.csv")
    _write_raw(src_dir / "2-1.csv", RAW_CSV.replace("sample 1-1", "sample 2-1"))

    out_dir = tmp_path / "canonical"
    report = convert_dir(src_dir, out_dir)

    assert report.n_files == 2
    assert report.n_rows == 4
    assert report.n_rejected == 4
    assert (out_dir / "1-1.csv").exists()
    assert (out_dir / "2-1.csv").exists()

    # Every converted file loads cleanly.
    for name in ("1-1", "2-1"):
        bl = load_match_csv(out_dir / f"{name}.csv")
        assert bl.sample_id == name
        assert len(bl.candidates) == 2
