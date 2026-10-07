"""Tests for :mod:`xinmatch.core.search.candidate_list` (Phase 6 / T6.7)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from xinmatch.core.model import CellParams, Entry, Peak
from xinmatch.core.search import (
    CandidateList,
    CandidateResult,
    rank_candidates,
)

WL = 1.5406


def _d_from_two_theta(two_theta: float, wavelength: float = WL) -> float:
    return wavelength / (2.0 * math.sin(math.radians(two_theta / 2.0)))


def _entry(
    entry_id: str,
    *,
    two_thetas: list[float] = (10.0, 20.0, 30.0),
    intensities: list[float] = (100.0, 50.0, 25.0),
    formula: str = "Si O2",
    mineral_name: str | None = "Quartz",
    space_group: str | None = "P3221",
) -> Entry:
    """Build a minimal entry with the given peak 2θ positions / intensities.

    Peaks are sorted by descending intensity (Match! convention) so the
    round-trip through ``get_entry_peaks`` preserves the ordering.
    """
    tt = list(two_thetas)
    ints = list(intensities)
    order = sorted(range(len(tt)), key=lambda i: -ints[i])
    ds = [_d_from_two_theta(tt[i]) for i in order]
    ints_sorted = [ints[i] for i in order]
    return Entry(
        entry_id=entry_id,
        formula=formula,
        d_spacings=np.array(ds, dtype=np.float64),
        intensities=np.array(ints_sorted, dtype=np.float64),
        mineral_name=mineral_name,
        cell=CellParams(4.914, 4.914, 5.405, gamma=120.0),
        space_group=space_group,
        hkl=[(1, 0, 0), (1, 1, 0), (1, 1, 1)][: len(ds)],
        literature={"author": "tester", "year": 2000, "journal": "J. Synth."},
        quality="A",
    )


def _exp_peaks() -> list[Peak]:
    return [
        Peak(two_theta=10.0, intensity=100.0),
        Peak(two_theta=20.0, intensity=50.0),
        Peak(two_theta=30.0, intensity=25.0),
        Peak(two_theta=40.0, intensity=10.0),  # 4th exp peak (no ref counterpart)
    ]


@pytest.fixture
def sample_results() -> list[CandidateResult]:
    """A ranked candidate list with 3 distinct-FoM entries.

    * ``E1`` matches all 4 experimental peaks → highest FoM (perfect match).
    * ``E2`` matches 3 of 4 (no peak at 2θ=40) → middle FoM.
    * ``E3`` matches 2 of 4 (no peaks at 2θ=20, 40) → lowest FoM.
    """
    entries = [
        _entry("E1", two_thetas=[10.0, 20.0, 30.0, 40.0],
               intensities=[100.0, 50.0, 25.0, 10.0],
               mineral_name="Quartz"),
        _entry("E2", formula="C Ca O3", mineral_name="Calcite",
               space_group="R-3c",
               two_thetas=[10.0, 20.0, 30.0],
               intensities=[100.0, 50.0, 25.0]),
        _entry("E3", formula="Na Cl", mineral_name="Halite",
               space_group="Fm-3m",
               two_thetas=[10.0, 30.0],
               intensities=[100.0, 25.0]),
    ]
    return rank_candidates(_exp_peaks(), entries, wavelength=WL)


# ===========================================================================
# Container protocol
# ===========================================================================
def test_len_and_iter(sample_results):
    cl = CandidateList(candidates=sample_results, n_exp_peaks=4)
    assert len(cl) == 3
    assert list(cl) == sample_results


def test_getitem(sample_results):
    cl = CandidateList(candidates=sample_results, n_exp_peaks=4)
    assert cl[0] is sample_results[0]
    assert cl[-1] is sample_results[-1]


def test_empty_list_defaults():
    cl = CandidateList()
    assert len(cl) == 0
    assert list(cl) == []
    assert cl.n_exp_peaks == 0
    assert cl.selected_ids == set()


# ===========================================================================
# sort_by_fom / sort_by
# ===========================================================================
def test_sort_by_fom(sample_results):
    """sort_by_fom sorts candidates by descending FoM."""
    # Reverse first to make sure the sort actually does work.
    cl = CandidateList(
        candidates=list(reversed(sample_results)), n_exp_peaks=4
    )
    foms_before = [r.fom for r in cl]
    assert foms_before != sorted(foms_before, reverse=True)
    cl.sort_by_fom()
    foms_after = [r.fom for r in cl]
    assert foms_after == sorted(foms_after, reverse=True)


def test_sort_by_fom_alias(sample_results):
    cl = CandidateList(candidates=list(reversed(sample_results)), n_exp_peaks=4)
    cl.sort_by("fom")
    assert [r.fom for r in cl] == sorted([r.fom for r in cl], reverse=True)


def test_sort_by_entry_id(sample_results):
    cl = CandidateList(candidates=list(reversed(sample_results)), n_exp_peaks=4)
    cl.sort_by("entry_id")
    assert [r.entry.entry_id for r in cl] == ["E1", "E2", "E3"]


def test_sort_by_formula(sample_results):
    cl = CandidateList(candidates=list(reversed(sample_results)), n_exp_peaks=4)
    cl.sort_by("formula")
    # C Ca O3 < Na Cl < Si O2 (alphabetical)
    assert [r.entry.formula for r in cl] == ["C Ca O3", "Na Cl", "Si O2"]


def test_sort_by_mineral_name(sample_results):
    cl = CandidateList(candidates=list(reversed(sample_results)), n_exp_peaks=4)
    cl.sort_by("mineral_name")
    names = [r.entry.mineral_name for r in cl]
    assert names == sorted(names)


def test_sort_by_i_scale(sample_results):
    cl = CandidateList(candidates=sample_results, n_exp_peaks=4)
    cl.sort_by("i_scale")
    iscales = [r.i_scale for r in cl]
    assert iscales == sorted(iscales, reverse=True)


def test_sort_by_case_insensitive(sample_results):
    cl = CandidateList(candidates=list(reversed(sample_results)), n_exp_peaks=4)
    cl.sort_by("FOM")
    assert [r.fom for r in cl] == sorted([r.fom for r in cl], reverse=True)


def test_sort_by_unknown_raises(sample_results):
    cl = CandidateList(candidates=sample_results, n_exp_peaks=4)
    with pytest.raises(ValueError, match="unknown sort key"):
        cl.sort_by("nonexistent")


# ===========================================================================
# filter (min_fom)
# ===========================================================================
def test_filter_min_fom_zero_keeps_all(sample_results):
    cl = CandidateList(candidates=sample_results, n_exp_peaks=4)
    filtered = cl.filter(min_fom=0.0)
    assert len(filtered) == 3


def test_filter_high_min_fom_keeps_top_only(sample_results):
    cl = CandidateList(candidates=sample_results, n_exp_peaks=4)
    threshold = sample_results[0].fom
    filtered = cl.filter(min_fom=threshold)
    # Only the perfect-match entry meets the threshold.
    assert len(filtered) == 1
    assert filtered[0].entry.entry_id == sample_results[0].entry.entry_id


def test_filter_unreachable_threshold_returns_empty(sample_results):
    cl = CandidateList(candidates=sample_results, n_exp_peaks=4)
    filtered = cl.filter(min_fom=2.0)
    assert len(filtered) == 0


def test_filter_does_not_mutate_original(sample_results):
    cl = CandidateList(candidates=sample_results, n_exp_peaks=4)
    _ = cl.filter(min_fom=0.5)
    assert len(cl) == 3  # original unchanged


def test_filter_preserves_selected_ids(sample_results):
    cl = CandidateList(candidates=sample_results, n_exp_peaks=4)
    cl.select("E2")
    filtered = cl.filter(min_fom=0.0)
    assert "E2" in filtered.selected_ids


# ===========================================================================
# get_entry / select / unselect / get_selected
# ===========================================================================
def test_get_entry_present(sample_results):
    cl = CandidateList(candidates=sample_results, n_exp_peaks=4)
    e = cl.get_entry("E2")
    assert e is not None
    assert e.entry.entry_id == "E2"


def test_get_entry_absent(sample_results):
    cl = CandidateList(candidates=sample_results, n_exp_peaks=4)
    assert cl.get_entry("E_DOES_NOT_EXIST") is None


def test_select_present(sample_results):
    cl = CandidateList(candidates=sample_results, n_exp_peaks=4)
    assert cl.select("E1") is True
    assert "E1" in cl.selected_ids
    assert cl.select("E2") is True
    assert len(cl.get_selected()) == 2


def test_select_absent_returns_false(sample_results):
    cl = CandidateList(candidates=sample_results, n_exp_peaks=4)
    assert cl.select("E_DOES_NOT_EXIST") is False
    assert cl.selected_ids == set()


def test_unselect_present(sample_results):
    cl = CandidateList(candidates=sample_results, n_exp_peaks=4)
    cl.select("E1")
    assert cl.unselect("E1") is True
    assert "E1" not in cl.selected_ids


def test_unselect_absent_returns_false(sample_results):
    cl = CandidateList(candidates=sample_results, n_exp_peaks=4)
    assert cl.unselect("E_DOES_NOT_EXIST") is False


def test_unselect_unselected_returns_false(sample_results):
    cl = CandidateList(candidates=sample_results, n_exp_peaks=4)
    cl.select("E1")
    assert cl.unselect("E2") is False  # E2 was never selected


def test_get_selected_preserves_candidate_order(sample_results):
    cl = CandidateList(candidates=sample_results, n_exp_peaks=4)
    cl.select("E3")
    cl.select("E1")
    selected = cl.get_selected()
    # Order follows the candidates list (not selection order).
    assert [r.entry.entry_id for r in selected] == ["E1", "E3"]


def test_get_selected_empty_when_none_selected(sample_results):
    cl = CandidateList(candidates=sample_results, n_exp_peaks=4)
    assert cl.get_selected() == []


# ===========================================================================
# show_unassociated_peaks
# ===========================================================================
def test_show_unassociated_peaks_returns_unmatched(sample_results):
    """E2 (no peak at 2θ=40) leaves the 4th experimental peak unassociated."""
    cl = CandidateList(candidates=sample_results, n_exp_peaks=4)
    # E2 has peaks at 2θ=10, 20, 30 — peak #3 (idx 3) is unmatched.
    e2 = next(r for r in sample_results if r.entry.entry_id == "E2")
    assert 3 not in {ei for ei, _ in e2.pairs}
    unassoc = cl.show_unassociated_peaks("E2")
    assert unassoc == [3]


def test_show_unassociated_peaks_partial_match():
    """An entry covering only 2 of 4 exp peaks leaves 2 unassociated."""
    exp_peaks = _exp_peaks()  # 4 peaks
    entry = _entry(
        "E_PARTIAL",
        two_thetas=[10.0, 20.0],
        intensities=[100.0, 50.0],
    )
    results = rank_candidates(exp_peaks, [entry], wavelength=WL)
    cl = CandidateList(candidates=results, n_exp_peaks=4)
    unassoc = cl.show_unassociated_peaks("E_PARTIAL")
    # 2 of 4 peaks unassociated → indices 2, 3.
    assert sorted(unassoc) == [2, 3]


def test_show_unassociated_peaks_unknown_entry(sample_results):
    cl = CandidateList(candidates=sample_results, n_exp_peaks=4)
    assert cl.show_unassociated_peaks("E_DOES_NOT_EXIST") == []


def test_show_unassociated_peaks_no_n_exp():
    """Without n_exp_peaks set, returns empty."""
    entry = _entry("E1")
    results = rank_candidates(_exp_peaks(), [entry], wavelength=WL)
    cl = CandidateList(candidates=results)  # n_exp_peaks defaults to 0
    assert cl.show_unassociated_peaks("E1") == []


def test_show_unassociated_peaks_perfect_match():
    """When all experimental peaks are matched, the result is empty."""
    # Build an entry whose peaks include all 4 experimental positions.
    entry = _entry(
        "E_PERFECT",
        two_thetas=[10.0, 20.0, 30.0, 40.0],
        intensities=[100.0, 50.0, 25.0, 10.0],
    )
    results = rank_candidates(_exp_peaks(), [entry], wavelength=WL)
    cl = CandidateList(candidates=results, n_exp_peaks=4)
    unassoc = cl.show_unassociated_peaks("E_PERFECT")
    assert unassoc == []


# ===========================================================================
# Serialisation
# ===========================================================================
def test_to_dict_roundtrip(sample_results):
    cl = CandidateList(candidates=sample_results, n_exp_peaks=4)
    cl.select("E1")
    cl.select("E3")
    d = cl.to_dict()
    assert set(d.keys()) == {"candidates", "selected_ids", "n_exp_peaks"}
    assert d["n_exp_peaks"] == 4
    assert d["selected_ids"] == ["E1", "E3"]  # sorted
    assert len(d["candidates"]) == 3
    assert all("entry" in c and "fom" in c for c in d["candidates"])


def test_from_dict_roundtrip(sample_results):
    cl = CandidateList(candidates=sample_results, n_exp_peaks=4)
    cl.select("E1")
    d = cl.to_dict()
    cl2 = CandidateList.from_dict(d)
    assert len(cl2) == len(cl)
    assert cl2.selected_ids == cl.selected_ids
    assert cl2.n_exp_peaks == cl.n_exp_peaks
    # FoMs preserved.
    assert [r.fom for r in cl2] == [r.fom for r in cl]
    # Entry ids preserved.
    assert [r.entry.entry_id for r in cl2] == [r.entry.entry_id for r in cl]
    # Pairs preserved.
    for r_orig, r_new in zip(cl, cl2, strict=True):
        assert r_orig.pairs == r_new.pairs


def test_to_json_and_from_json(sample_results):
    cl = CandidateList(candidates=sample_results, n_exp_peaks=4)
    cl.select("E2")
    text = cl.to_json()
    cl2 = CandidateList.from_json(text)
    assert len(cl2) == 3
    assert cl2.selected_ids == {"E2"}
    assert cl2.n_exp_peaks == 4


def test_candidate_result_to_dict_roundtrip(sample_results):
    """CandidateResult serialises and deserialises correctly."""
    r = sample_results[0]
    d = r.to_dict()
    r2 = CandidateResult.from_dict(d)
    assert r2.entry.entry_id == r.entry.entry_id
    assert r2.fom == pytest.approx(r.fom, abs=1e-12)
    assert r2.i_scale == pytest.approx(r.i_scale, abs=1e-12)
    assert r2.pairs == r.pairs
    assert r2.p_values == r.p_values


def test_candidate_result_from_dict_missing_optionals():
    """from_dict handles missing p_values / pairs / i_scale."""
    entry = _entry("E1")
    d = {
        "entry": entry.to_dict(),
        "fom": 0.5,
    }
    r = CandidateResult.from_dict(d)
    assert r.entry.entry_id == "E1"
    assert r.fom == 0.5
    assert r.p_values == {}
    assert r.pairs == []
    assert r.i_scale == 1.0


# ===========================================================================
# Integration with rank_candidates output
# ===========================================================================
def test_candidate_list_from_rank_candidates():
    """A realistic end-to-end construction: rank_candidates → CandidateList."""
    entries = [
        _entry("E1", two_thetas=[10.0, 20.0, 30.0, 40.0],
               intensities=[100.0, 50.0, 25.0, 10.0],
               mineral_name="Quartz"),
        _entry("E2", formula="C Ca O3", mineral_name="Calcite",
               space_group="R-3c",
               two_thetas=[10.0, 20.0, 30.0],
               intensities=[100.0, 50.0, 25.0]),
    ]
    results = rank_candidates(_exp_peaks(), entries, wavelength=WL)
    cl = CandidateList(candidates=results, n_exp_peaks=4)
    # FoM order is preserved (rank_candidates already sorted).
    foms = [r.fom for r in cl]
    assert foms == sorted(foms, reverse=True)
    # Selecting the top entry and re-filtering keeps it.
    cl.select(cl[0].entry.entry_id)
    selected = cl.get_selected()
    assert len(selected) == 1
    assert selected[0].entry.entry_id == cl[0].entry.entry_id
