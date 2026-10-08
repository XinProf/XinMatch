"""Tests for the Match! golden-baseline loader and L3 metrics (T6.9 upgrade).

Verifies:

* ``load_match_csv`` — banner/header handling, ``n.a.`` tolerance,
  FoM-descending ordering, malformed-row skipping;
* ``normalize_formula`` / ``formula_compatible`` — element-composition
  identity across fractional stoichiometry;
* ``same_phase`` — entry-id and formula keys;
* ``top1_agreement`` / ``top5_overlap`` — the two L3 metrics with their
  declared thresholds (Top-1 ≥ 80 %, Top-5 overlap ≥ 60 %).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.match_baseline import (
    MatchCandidate,
    formula_compatible,
    load_match_baseline_dir,
    load_match_csv,
    normalize_formula,
    same_phase,
    top1_agreement,
    top5_overlap,
)

# --------------------------------------------------------------------------- #
# Fixture helpers
# --------------------------------------------------------------------------- #
CSV_HEADER = (
    "Entry;Qual.;Formula sum;Name;P(peakpos.);P(I/I0);P(#peaks);"
    "P(#corr.);I scale fct.;FoM"
)

CSV_1_1 = f"""Candidate list of sample 1-1
{CSV_HEADER}
96-400-1849;C;Fe Li O4 P;;n.a.;n.a.;0.0000;n.a.;0.7083;1.0000
96-400-1848;C;Fe Li O4 P;;n.a.;n.a.;0.0000;n.a.;0.7127;0.9989
96-210-0917;C;Fe Li O4 P;;n.a.;n.a.;0.0000;n.a.;0.6961;0.9215
96-901-1559;C;Li;Lithium;n.a.;n.a.;0.0000;n.a.;0.2027;0.0237
"""


@pytest.fixture
def csv_1_1(tmp_path: Path) -> Path:
    p = tmp_path / "1-1.csv"
    p.write_text(CSV_1_1, encoding="utf-8")
    return p


@pytest.fixture
def sample_1_1() -> MatchCandidate:
    return MatchCandidate(
        entry_id="96-400-1849", quality="C", formula_sum="Fe Li O4 P",
        name=None, p_peakpos=None, p_intensity=None, p_npeaks=0.0,
        p_ncorr=None, i_scale=0.7083, fom=1.0000,
    )


# --------------------------------------------------------------------------- #
# load_match_csv
# --------------------------------------------------------------------------- #
def test_load_csv_skips_banner_and_parses_rows(csv_1_1: Path):
    bl = load_match_csv(csv_1_1)
    assert bl.sample_id == "1-1"
    assert len(bl.candidates) == 4


def test_load_csv_sorts_by_fom_descending(csv_1_1: Path):
    bl = load_match_csv(csv_1_1)
    foms = [c.fom for c in bl.candidates]
    assert foms == sorted(foms, reverse=True)
    assert bl.top1 is not None
    assert bl.top1.entry_id == "96-400-1849"
    assert bl.top1.fom == pytest.approx(1.0000)


def test_load_csv_parses_na_as_none(csv_1_1: Path):
    bl = load_match_csv(csv_1_1)
    top = bl.top1
    assert top is not None
    assert top.p_peakpos is None
    assert top.p_intensity is None
    assert top.p_npeaks == pytest.approx(0.0)
    assert top.i_scale == pytest.approx(0.7083)


def test_load_csv_missing_header_raises(tmp_path: Path):
    p = tmp_path / "bad.csv"
    p.write_text("a;b;c\n1;2;3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="header"):
        load_match_csv(p)


def test_load_csv_skips_malformed_rows(tmp_path: Path):
    p = tmp_path / "x.csv"
    p.write_text(
        f"banner\n{CSV_HEADER}\n"
        "96-1;C;Fe;X;n.a.;n.a.;0;n.a.;1.0;0.5\n"
        "broken;;;not-a-number;;;;;;\n"
        "96-2;C;O2;Y;n.a.;n.a.;0;n.a.;1.0;0.4\n",
        encoding="utf-8",
    )
    bl = load_match_csv(p)
    assert len(bl.candidates) == 2  # malformed row skipped


def test_load_csv_utf8_bom_tolerated(tmp_path: Path):
    p = tmp_path / "bom.csv"
    p.write_bytes(("\ufeffbanner\n" + CSV_HEADER + "\n96-1;C;Fe;X;n.a.;n.a.;0;n.a.;1.0;0.5\n").encode("utf-8"))
    bl = load_match_csv(p)
    assert len(bl.candidates) == 1


def test_load_baseline_dir_skips_bad_files(tmp_path: Path):
    (tmp_path / "1-1.csv").write_text(CSV_1_1, encoding="utf-8")
    (tmp_path / "junk.csv").write_text("not a match csv\n", encoding="utf-8")
    out = load_match_baseline_dir(tmp_path)
    assert set(out) == {"1-1"}


# --------------------------------------------------------------------------- #
# Formula identity
# --------------------------------------------------------------------------- #
def test_normalize_formula_sorts_symbols():
    assert normalize_formula("Fe Li O4 P") == normalize_formula("P O4 Fe Li")
    assert normalize_formula("Fe Li O4 P") == normalize_formula("Fe1 Li1 O4 P1")


def test_formula_compatible_fractional_stoichiometry():
    assert formula_compatible("Fe Li O4 P", "Fe3.74 Li3.88 O16 P4")
    assert formula_compatible("B6 La0.987", "B6 La1")
    assert not formula_compatible("Fe Li O4 P", "Fe Li O4")      # missing P
    assert not formula_compatible("Fe Li O4 P", "Fe Na O4 P")    # different element
    assert not formula_compatible("", "Fe")                      # empty never matches
    assert not formula_compatible("Fe", None)


def test_same_phase_entry_id_wins(sample_1_1: MatchCandidate):
    # Same COD id → match even with a divergent formula.
    assert same_phase(sample_1_1, "96-400-1849", "something entirely different")
    # Different id, compatible formula → match.
    assert same_phase(sample_1_1, "my-curated-1", "Fe Li O4 P")
    # Different id, incompatible formula → no match.
    assert not same_phase(sample_1_1, "my-curated-2", "Si O2")


# --------------------------------------------------------------------------- #
# Agreement metrics
# --------------------------------------------------------------------------- #
def test_top1_agreement_hit(sample_1_1: MatchCandidate):
    assert top1_agreement(sample_1_1, "96-400-1849", "Fe Li O4 P") is True
    assert top1_agreement(sample_1_1, "curated-lifepo4", "Fe Li O4 P") is True


def test_top1_agreement_miss(sample_1_1: MatchCandidate):
    assert top1_agreement(sample_1_1, "96-999-9999", "Si O2") is False


def test_top1_agreement_no_xinmatch_result(sample_1_1: MatchCandidate):
    assert top1_agreement(sample_1_1, None, None) is False


def test_top5_overlap_full():
    match5 = [
        MatchCandidate(entry_id=f"96-{i}", formula_sum="Fe Li O4 P", fom=1.0 - i * 0.01)
        for i in range(5)
    ]
    xin = [(f"96-{i}", "Fe Li O4 P") for i in range(5)]  # same 5 ids
    assert top5_overlap(match5, xin) == pytest.approx(1.0)


def test_top5_overlap_partial():
    """Match!'s Top-5 are 5 distinct phases; XinMatch found only 2 of them."""
    match5 = [
        MatchCandidate(entry_id=f"96-{i}", formula_sum=f, fom=1.0 - i * 0.01)
        for i, f in enumerate(
            ["Fe Li O4 P", "Si O2", "C Ca O3", "O2 Ti", "Fe2 O3"]
        )
    ]
    xin = [("96-0", "Fe Li O4 P"), ("96-1", "Si O2"), ("other", "Si O2")]
    # 2 of 5 phases overlap.
    assert top5_overlap(match5, xin) == pytest.approx(0.4)


def test_top5_overlap_rank_independent():
    """A phase ranked #6 by XinMatch still counts in the overlap."""
    match5 = [
        MatchCandidate(entry_id=f"96-{i}", formula_sum="Fe Li O4 P", fom=1.0 - i * 0.01)
        for i in range(5)
    ]
    xin = [("96-0", "Fe Li O4 P"), ("96-1", "Fe Li O4 P"), ("96-2", "Fe Li O4 P"),
           ("96-3", "Fe Li O4 P"), ("96-4", "Fe Li O4 P"), ("96-5", "Fe Li O4 P")]
    assert top5_overlap(match5, xin) == pytest.approx(1.0)


def test_top5_overlap_empty_baseline():
    assert top5_overlap([], [("x", "Fe")]) == 0.0
