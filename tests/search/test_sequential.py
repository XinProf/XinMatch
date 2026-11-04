"""Tests for :mod:`xinmatch.core.search.sequential` (v3.1.0).

The sequential (iterative) workflow is a bookkeeping problem, so the tests
build a **fully determined** synthetic two-phase pattern where every expected
number can be computed by hand:

* phase A: d = 3.0 / 2.0 / 1.5 Å, relative intensities 100 / 50 / 25,
  10 counts per unit relative intensity  → 1000 / 500 / 250 counts;
* phase B: d = 2.6 / 1.8 / 1.3 Å, relative intensities 100 / 60 / 30,
  3 counts per unit relative intensity   → 300 / 180 / 90 counts.

No reflection of A coincides with one of B, so confirming A must leave exactly
B's three peaks as the residual set, and confirming B must explain everything.
"""

from __future__ import annotations

import numpy as np
import pytest

from xinmatch.core.model import Entry, Peak
from xinmatch.core.search.fom import CandidateResult
from xinmatch.core.search.sequential import (
    AnchorPolicy,
    SequentialIdentifier,
    search_residual,
)

WL = 1.5406

A_D = (3.0, 2.0, 1.5)
A_I = (100.0, 50.0, 25.0)
B_D = (2.6, 1.8, 1.3)
B_I = (100.0, 60.0, 30.0)
# Counts per unit *relative* reference intensity (rel = I_ref / I_ref_max).
# A's strongest line (rel 1.0) is 1000 counts, B's is 300 counts.
A_COUNTS_PER_REL = 10.0
B_COUNTS_PER_REL = 3.0
A_SCALE = A_I[0] * A_COUNTS_PER_REL
B_SCALE = B_I[0] * B_COUNTS_PER_REL


def two_theta(d: float, wavelength: float = WL) -> float:
    """Bragg 2θ for a d-spacing (degrees)."""
    return float(2.0 * np.degrees(np.arcsin(wavelength / (2.0 * d))))


def make_entry(entry_id: str, ds, intensities) -> Entry:
    return Entry(
        entry_id=entry_id,
        formula=entry_id,
        d_spacings=np.array(ds, dtype=np.float64),
        intensities=np.array(intensities, dtype=np.float64),
    )


def make_peaks() -> list[Peak]:
    """Two-phase experimental peaks, sorted by 2θ."""
    peaks = [
        Peak(two_theta=two_theta(d), intensity=i * A_COUNTS_PER_REL)
        for d, i in zip(A_D, A_I, strict=True)
    ]
    peaks += [
        Peak(two_theta=two_theta(d), intensity=i * B_COUNTS_PER_REL)
        for d, i in zip(B_D, B_I, strict=True)
    ]
    peaks.sort(key=lambda p: p.two_theta)
    return peaks


def entry_a() -> Entry:
    return make_entry("A", A_D, A_I)


def entry_b() -> Entry:
    return make_entry("B", B_D, B_I)


def identifier(peaks: list[Peak] | None = None) -> SequentialIdentifier:
    return SequentialIdentifier(peaks or make_peaks(), wavelength=WL)


def candidate(entry: Entry, fom: float = 0.9) -> CandidateResult:
    return CandidateResult(entry=entry, fom=fom)


def index_of(peaks: list[Peak], d: float) -> int:
    """Index of the peak sitting at the 2θ of *d* in *peaks*."""
    target = two_theta(d)
    return min(range(len(peaks)), key=lambda i: abs(peaks[i].two_theta - target))


# --------------------------------------------------------------------------- #
# Initial state
# --------------------------------------------------------------------------- #
def test_initial_state_has_no_phases_and_all_peaks_residual():
    seq = identifier()
    assert len(seq) == 0
    assert seq.n_peaks == 6
    assert seq.n_residual_peaks == 6
    assert seq.n_explained == 0
    assert seq.covered_fraction == pytest.approx(0.0)
    assert seq.residual_indices == list(range(6))


def test_residual_peaks_mirror_original_peaks():
    peaks = make_peaks()
    seq = identifier(peaks)
    residual = seq.residual_peaks
    assert len(residual) == len(peaks)
    for original, copy in zip(peaks, residual, strict=True):
        assert copy.two_theta == pytest.approx(original.two_theta)
        assert copy.intensity == pytest.approx(original.intensity)
        assert copy.correlated is False
    # The identifier never mutates the caller's peaks.
    assert all(p.correlated is False for p in peaks)


# --------------------------------------------------------------------------- #
# Selecting the first phase
# --------------------------------------------------------------------------- #
def test_select_first_phase_explains_only_its_own_peaks():
    peaks = make_peaks()
    seq = identifier(peaks)
    selection = seq.select(candidate(entry_a()))

    assert selection.entry_id == "A"
    assert selection.scale == pytest.approx(A_SCALE)
    assert selection.n_residual_peaks == 3
    # Exactly B's three peaks survive.
    expected = sorted(index_of(peaks, d) for d in B_D)
    assert seq.residual_indices == expected
    # Total intensity 2320 counts; A accounts for 1750 → 75.4 %.
    assert selection.covered_fraction == pytest.approx(1750.0 / 2320.0)

    # Correlation bookkeeping is written back to the Phase object, which is
    # what Rietveld / reports / CIF export read downstream.
    phase = seq.phases[0]
    assert phase.entry is not None
    assert phase.scale_factor == pytest.approx(A_SCALE)
    assert sorted(exp for exp, _ in phase.correlations) == sorted(
        index_of(peaks, d) for d in A_D
    )


def test_select_is_idempotent():
    seq = identifier()
    first = seq.select(candidate(entry_a()))
    again = seq.select(candidate(entry_a(), fom=0.1))
    assert len(seq) == 1
    assert again is first
    assert seq.selections[0].scale == pytest.approx(first.scale)


def test_second_phase_explains_everything():
    seq = identifier()
    seq.select(candidate(entry_a()))
    selection = seq.select(candidate(entry_b()))
    assert len(seq) == 2
    assert selection.scale == pytest.approx(B_SCALE)
    assert seq.n_residual_peaks == 0
    assert seq.covered_fraction == pytest.approx(1.0)
    assert seq.residual_peaks == []


def test_weak_peaks_are_ignored_not_left_over():
    """Peaks below the search floor are neither explained nor searched.

    Real / synthetic patterns always carry a tail of noise bumps found by the
    peak search.  Without the floor they would stay in the residual set after
    every true phase is confirmed and the next round would happily match the
    noise (measured: Fe0.75V0.25 on synth_02).  They must be counted separately
    and kept out of :attr:`residual_peaks`.
    """
    peaks = make_peaks()
    peaks.append(Peak(two_theta=two_theta(1.05), intensity=1.0))  # 0.1 % of max
    peaks.sort(key=lambda p: p.two_theta)
    seq = identifier(peaks)

    assert seq.n_ignored == 1
    assert seq.n_residual_peaks == 6  # the ignored peak is not a residual peak
    assert len(seq.residual_peaks) == 6
    assert seq.ignored_indices == [index_of(peaks, 1.05)]

    seq.select(candidate(entry_a()))
    seq.select(candidate(entry_b()))
    assert seq.n_residual_peaks == 0
    assert seq.n_ignored == 1
    assert seq.covered_fraction == pytest.approx(1.0)

    # The floor scales with the pattern maximum, so lowering it re-admits the
    # peak without touching the confirmed phases.
    generous = SequentialIdentifier(
        peaks, wavelength=WL, min_peak_frac=0.0
    )
    assert generous.n_ignored == 0
    assert generous.n_residual_peaks == 7


def test_partially_explained_peak_stays_with_reduced_intensity():
    """A strong unconfirmed peak overlapping phase A's line is not swallowed.

    Phase A's strongest line is assumed to carry 1000 counts, but the measured
    peak holds 1600 — a hidden phase sits underneath.  The least-squares scale
    lands between the two (A alone would over-explain the weak lines), so the
    merged peak keeps a positive residual and stays in the residual set for the
    next round instead of silently disappearing.
    """
    peaks = make_peaks()
    target = index_of(peaks, A_D[0])
    peaks[target] = Peak(
        two_theta=peaks[target].two_theta,
        intensity=A_I[0] * A_COUNTS_PER_REL + 600.0,
    )
    seq = identifier(peaks)
    seq.select(candidate(entry_a()))

    leftover = [
        p
        for p in seq.residual_peaks
        if abs(p.two_theta - peaks[target].two_theta) < 1e-6
    ]
    assert len(leftover) == 1
    assert 0.0 < leftover[0].intensity < 600.0
    # B's three peaks plus the partially explained one.
    assert seq.n_residual_peaks == 4


# --------------------------------------------------------------------------- #
# Undo / remove / rebuild
# --------------------------------------------------------------------------- #
def test_undo_restores_previous_residual():
    seq = identifier()
    seq.select(candidate(entry_a()))
    covered_one = seq.covered_fraction
    seq.select(candidate(entry_b()))
    removed = seq.undo()
    assert removed is not None and removed.entry.entry_id == "B"
    assert len(seq) == 1
    assert seq.n_residual_peaks == 3
    assert seq.covered_fraction == pytest.approx(covered_one)


def test_undo_on_empty_returns_none():
    seq = identifier()
    assert seq.undo() is None
    assert len(seq) == 0


def test_remove_by_entry_id_rebuilds_layers():
    seq = identifier()
    seq.select(candidate(entry_a()))
    seq.select(candidate(entry_b()))
    assert seq.remove("A") is True
    # B alone explains its three peaks; A's peaks come back.
    assert seq.n_residual_peaks == 3
    assert seq.phases[0].entry.entry_id == "B"
    assert seq.remove("A") is False
    assert seq.find("A") is None
    assert seq.is_selected("B") is True


def test_clear_and_reset():
    seq = identifier()
    seq.select(candidate(entry_a()))
    seq.clear()
    assert len(seq) == 0
    assert seq.n_residual_peaks == 6
    assert seq.covered_fraction == pytest.approx(0.0)

    seq.select(candidate(entry_a()))
    new_peaks = make_peaks()[:2]
    seq.reset(new_peaks)
    assert seq.n_peaks == 2
    assert len(seq) == 0


def test_rebuild_is_deterministic():
    first = identifier()
    first.select(candidate(entry_a()))
    second = identifier()
    second.select(candidate(entry_a()))
    assert np.allclose(first.residual_intensity, second.residual_intensity)
    assert first.selections[0].pairs == second.selections[0].pairs


def test_residual_intensity_never_negative():
    seq = identifier()
    seq.select(candidate(entry_a()))
    seq.select(candidate(entry_b()))
    assert float(seq.residual_intensity.min()) == pytest.approx(0.0)


def test_selections_snapshot_sequence():
    seq = identifier()
    seq.select(candidate(entry_a()))
    seq.select(candidate(entry_b()))
    labels = [sel.entry_id for sel in seq.selections]
    assert labels == ["A", "B"]
    # Cumulative coverage is monotonic along the sequence.
    coverages = [sel.covered_fraction for sel in seq.selections]
    assert coverages == sorted(coverages)
    assert seq.selection_of("B") is not None
    assert seq.selection_of("missing") is None


# --------------------------------------------------------------------------- #
# Argument validation
# --------------------------------------------------------------------------- #
def test_invalid_wavelength_and_threshold():
    with pytest.raises(ValueError):
        SequentialIdentifier([], wavelength=0.0)
    with pytest.raises(ValueError):
        SequentialIdentifier([], wavelength=WL, explained_frac=1.5)


# --------------------------------------------------------------------------- #
# Residual search orchestration
# --------------------------------------------------------------------------- #
def test_search_residual_passes_residual_peaks_and_remaps_pairs():
    peaks = make_peaks()
    seq = identifier(peaks)
    seq.select(candidate(entry_a()))
    b_indices = sorted(index_of(peaks, d) for d in B_D)

    seen: dict[str, object] = {}

    def fake_search(exp_peaks, conn, wavelength, **kwargs):
        seen["positions"] = [p.two_theta for p in exp_peaks]
        seen["wavelength"] = wavelength
        seen["kwargs"] = kwargs
        return [
            CandidateResult(entry=entry_b(), fom=0.8, pairs=[(0, 0), (1, 1)]),
            CandidateResult(entry=entry_a(), fom=0.7, pairs=[(0, 0)]),
        ]

    result = search_residual(seq, object(), top_n=5, search_fn=fake_search)

    assert seen["wavelength"] == pytest.approx(WL)
    assert seen["kwargs"] == {"top_n": 5}
    assert seen["positions"] == pytest.approx(
        [p.two_theta for p in seq.residual_peaks]
    )
    # Already confirmed phase A is filtered out by default.
    assert [c.entry.entry_id for c in result.candidates] == ["B"]
    assert result.excluded_ids == ["A"]
    # Residual index 0/1 are the first two surviving peaks (B's 2.6 / 1.8 Å).
    assert [exp for exp, _ in result.candidates[0].pairs] == b_indices[:2]
    assert result.n_residual_peaks == 3
    assert result.n_explained == 3
    assert result.covered_fraction == pytest.approx(seq.covered_fraction)


def test_search_residual_can_keep_matched_entries():
    seq = identifier()
    seq.select(candidate(entry_a()))

    def fake_search(exp_peaks, conn, wavelength, **kwargs):
        return [CandidateResult(entry=entry_a(), fom=0.9, pairs=[])]

    result = search_residual(seq, object(), exclude_matched=False,
                             search_fn=fake_search)
    assert [c.entry.entry_id for c in result.candidates] == ["A"]
    assert result.excluded_ids == []


def test_search_residual_skips_engine_when_nothing_left():
    seq = identifier()
    seq.select(candidate(entry_a()))
    seq.select(candidate(entry_b()))
    called = False

    def fake_search(exp_peaks, conn, wavelength, **kwargs):  # pragma: no cover
        nonlocal called
        called = True
        return []

    result = search_residual(seq, object(), search_fn=fake_search)
    assert called is False
    assert result.candidates == []
    assert result.n_residual_peaks == 0
    assert result.covered_fraction == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# Strong-line anchoring (v3.3.0)
# --------------------------------------------------------------------------- #
# ``P_npeaks`` rewards the number of measured peaks a candidate explains, so a
# peak-rich card carpets the residual set and a correct sparse phase (Fe, KCl)
# never surfaces — measured on the synthetic bench: the true KCl was absent
# from a 1000-deep pool.  The anchoring rule *identifies* such candidates:
# strongest reference line on a strong residual peak, positionally accurate,
# and coherent over its own lines, with a reflection-count cap that keeps the
# peak-rich cards out.
#
# Marking is always on; **reordering is opt-in** (``promote_anchored=True``)
# because the measured trade-off is not free: it recovers NaCl on synth_07
# (11/13) but promotes a Bi-Y-O coincidence on real 3-2, where it outranks the
# true CaF₂ and destroys the sample (5/12 → 4/12).
def residual_index(seq: SequentialIdentifier, d: float) -> int:
    """Index of the residual peak sitting at the 2θ of *d*."""
    target = two_theta(d)
    residual = seq.residual_peaks
    return min(range(len(residual)), key=lambda i: abs(residual[i].two_theta - target))


def dense_entry(entry_id: str = "D", n_ref: int = 24) -> Entry:
    """A peak-rich card: *n_ref* reflections, all at unit intensity."""
    ds = np.linspace(1.2, 3.0, n_ref)
    return make_entry(entry_id, ds, np.full(n_ref, 100.0))


def scored(entry: Entry, fom: float, pairs, **p_values) -> CandidateResult:
    """Candidate carrying FoM sub-scores (what :func:`search_match` returns)."""
    base = {"peakpos": 0.995, "intensity": 0.9, "npeaks": 0.4,
            "ncorr": 0.9, "i_scale": 1.0}
    base.update(p_values)
    return CandidateResult(entry=entry, fom=fom, pairs=list(pairs), p_values=base)


def search_returning(cands: list[CandidateResult]):
    """A :func:`search_match` stand-in that returns *cands* verbatim."""

    def fake_search(exp_peaks, conn, wavelength, **kwargs):
        return list(cands)

    return fake_search


def sparse_pairs(seq: SequentialIdentifier) -> list[tuple[int, int]]:
    """Entry-A-like sparse phase: its three lines land on A's three peaks."""
    return [(residual_index(seq, d), i) for i, d in enumerate(A_D)]


def test_anchor_marks_sparse_phase_without_reordering():
    """Default: the FoM order is untouched, the sparse phase is only flagged.

    This is what ships — the GUI marks the row so the user can look at the
    candidate the peak-count criterion buried, but the engine does not decide
    for them.
    """
    seq = identifier()
    sparse = scored(make_entry("S", A_D, A_I), 0.60, sparse_pairs(seq), npeaks=0.2)
    dense = scored(dense_entry(), 0.95, [(0, 0), (1, 1), (2, 2), (3, 3)])
    weak = scored(entry_b(), 0.80, [(residual_index(seq, B_D[2]), 0)])

    result = search_residual(
        seq, object(), search_fn=search_returning([dense, weak, sparse])
    )

    assert [c.entry.entry_id for c in result.candidates] == ["D", "B", "S"]
    # Only the sparse card passes the rule; the 24-reflection carpet does not.
    assert result.anchored_ids == ["S"]


def test_anchor_promotion_is_opt_in_and_puts_the_sparse_phase_first():
    seq = identifier()
    sparse = scored(make_entry("S", A_D, A_I), 0.60, sparse_pairs(seq), npeaks=0.2)
    dense = scored(dense_entry(), 0.95, [(0, 0), (1, 1), (2, 2), (3, 3)])
    weak = scored(entry_b(), 0.80, [(residual_index(seq, B_D[2]), 0)])

    result = search_residual(
        seq, object(), promote_anchored=True,
        search_fn=search_returning([dense, weak, sparse]),
    )

    assert [c.entry.entry_id for c in result.candidates] == ["S", "D", "B"]
    # Nothing is dropped and no FoM is rewritten — promotion is ordering only.
    assert [c.fom for c in result.candidates] == pytest.approx([0.60, 0.95, 0.80])
    assert result.anchored_ids == ["S"]


def test_anchor_never_marks_dense_cards():
    """A 24-reflection card is excluded even with a perfect anchor.

    Without the reflection cap this candidate passes every other condition
    (position 0.999, all pairs on strong peaks, ``ncorr`` 1.0) — the cap is
    the only thing keeping the carpet out.
    """
    seq = identifier()
    dense = scored(
        dense_entry("D", 24), 0.95,
        [(i, i) for i in range(4)], peakpos=0.999, ncorr=1.0,
    )
    sparse = scored(make_entry("S", A_D, A_I), 0.60, sparse_pairs(seq), npeaks=0.2)

    strict = search_residual(
        seq, object(), search_fn=search_returning([dense, sparse])
    )
    assert strict.anchored_ids == ["S"]

    # Raise the cap and the very same candidate is flagged — proof that the
    # cap, not some other condition, was doing the work.
    loose = search_residual(
        seq, object(),
        anchor_policy=AnchorPolicy(max_reflections=30),
        search_fn=search_returning([dense, sparse]),
    )
    assert loose.anchored_ids == ["D", "S"]
    promoted = search_residual(
        seq, object(), promote_anchored=True,
        anchor_policy=AnchorPolicy(max_reflections=30),
        search_fn=search_returning([dense, sparse]),
    )
    assert [c.entry.entry_id for c in promoted.candidates] == ["D", "S"]


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"ncorr": 0.2}, id="incoherent-own-lines"),
        pytest.param({"peakpos": 0.80}, id="position-off"),
        pytest.param({}, id="weak-anchor-peak"),
    ],
)
def test_anchor_conditions_reject_bad_candidates(overrides):
    """Each guard on its own is enough to keep a candidate unmarked."""
    seq = identifier()
    if overrides:
        pairs = [(residual_index(seq, A_D[1]), 0), (residual_index(seq, A_D[2]), 1)]
        bad = scored(make_entry("S", A_D, A_I), 0.60, pairs, **overrides)
    else:
        # Strongest line (ref 0 = 3.0 Å) anchored on the *weakest* residual
        # peak instead of the 1000-count one.
        pairs = [(residual_index(seq, B_D[2]), 0), (residual_index(seq, A_D[1]), 1)]
        bad = scored(make_entry("S", A_D, A_I), 0.60, pairs)
    filler = scored(dense_entry(), 0.90, [(0, 0), (1, 1), (2, 2)])

    result = search_residual(seq, object(), search_fn=search_returning([filler, bad]))
    assert result.anchored_ids == []


def test_anchor_needs_more_than_one_coincidence():
    """A single matched pair is never enough, however strong the anchor."""
    seq = identifier()
    single = scored(make_entry("S", A_D, A_I), 0.60, [(residual_index(seq, A_D[0]), 0)])
    filler = scored(dense_entry(), 0.90, [(0, 0), (1, 1)])

    result = search_residual(seq, object(), search_fn=search_returning([filler, single]))
    assert result.anchored_ids == []


def test_anchor_is_a_noop_for_degenerate_scores():
    """Empty pairs / empty ``p_values`` must not crash the rule."""
    seq = identifier()
    bare = [
        CandidateResult(entry=make_entry("P", A_D, A_I), fom=0.9),
        CandidateResult(entry=make_entry("Q", A_D, A_I), fom=0.8, pairs=[]),
    ]
    result = search_residual(
        seq, object(), promote_anchored=True, search_fn=search_returning(bare)
    )
    assert [c.entry.entry_id for c in result.candidates] == ["P", "Q"]
    assert result.anchored_ids == []



def test_pairs_are_still_remapped_after_promotion():
    """Anchoring happens in residual space; the output stays in original space."""
    peaks = make_peaks()
    seq = identifier(peaks)
    seq.select(candidate(entry_a()))
    b_indices = sorted(index_of(peaks, d) for d in B_D)
    sparse = scored(entry_b(), 0.60, [(0, 0), (1, 1), (2, 2)], npeaks=1.0)
    filler = scored(entry_a(), 0.90, [(0, 0)])  # filtered out as already matched

    result = search_residual(
        seq, object(), exclude_matched=True, promote_anchored=True,
        search_fn=search_returning([filler, sparse]),
    )
    assert [c.entry.entry_id for c in result.candidates] == ["B"]
    assert [exp for exp, _ in result.candidates[0].pairs] == b_indices
    assert result.excluded_ids == ["A"]
    assert result.anchored_ids == ["B"]

