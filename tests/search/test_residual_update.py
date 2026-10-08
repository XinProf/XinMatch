"""Tests for :mod:`xinmatch.core.search.residual_update` (Phase 6 / T6.8).

Self-contained synthetic-data tests verifying the residual-driven FoM
recompute:

* Selecting a phase subtracts its contributed intensity from the
  experimental peaks it correlates to.
* Candidates that overlap with the selected phase see their FoM
  **rise** (their matched peaks constitute a larger fraction of the
  now-smaller residual peak set).
* Candidates unrelated to the selected phase (no correlated pairs at
  all) keep their FoM at the no-pair baseline.

The fixtures reuse the synthetic-entry factory style of
``tests/search/test_search_match.py`` so the two test files stay
consistent.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from xinmatch.core.model import Entry, Peak, Phase, Project
from xinmatch.core.search import (
    DEFAULT_WEIGHTS,
    CandidateResult,
    build_residual_peaks,
    rank_candidates,
    recompute_fom_after_selection,
)

# Cu Kα wavelength used throughout the synthetic tests.
WL = 1.5406


def _d_from_two_theta(two_theta: float, wavelength: float = WL) -> float:
    """Inverse of ``d_to_two_theta`` for synthesising reference peaks."""
    return wavelength / (2.0 * math.sin(math.radians(two_theta / 2.0)))


def _entry_from_two_theta(
    entry_id: str,
    two_thetas: list[float],
    intensities: list[float],
    *,
    formula: str = "Si O2",
    space_group: str | None = "P3221",
    mineral_name: str | None = None,
) -> Entry:
    """Build an :class:`Entry` whose (d, I) table lands at the given 2θ positions."""
    order = sorted(range(len(two_thetas)), key=lambda i: -intensities[i])
    ds = [_d_from_two_theta(two_thetas[i]) for i in order]
    ints = [intensities[i] for i in order]
    hkls = [(1, 0, 0), (1, 1, 0), (1, 1, 1), (2, 0, 0), (2, 1, 0), (2, 2, 0)]
    return Entry(
        entry_id=entry_id,
        formula=formula,
        d_spacings=np.array(ds, dtype=np.float64),
        intensities=np.array(ints, dtype=np.float64),
        mineral_name=mineral_name,
        space_group=space_group,
        hkl=hkls[: len(ds)],
        literature={"author": "tester", "journal": "J. Synth.", "year": 2000},
        quality="A",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def ru_exp_peaks() -> list[Peak]:
    """6 experimental peaks at 2θ = [10, 20, 30, 40, 50, 60]°."""
    return [
        Peak(two_theta=10.0, intensity=100.0),
        Peak(two_theta=20.0, intensity=80.0),
        Peak(two_theta=30.0, intensity=60.0),
        Peak(two_theta=40.0, intensity=40.0),
        Peak(two_theta=50.0, intensity=20.0),
        Peak(two_theta=60.0, intensity=10.0),
    ]


@pytest.fixture
def ru_selected_entry() -> Entry:
    """The selected phase's reference entry: peaks at 2θ = [10, 20]°."""
    return _entry_from_two_theta(
        "SEL",
        [10.0, 20.0],
        [100.0, 80.0],
        formula="Fe O",
        space_group="Pnma",
        mineral_name="SelectedPhase",
    )


@pytest.fixture
def ru_selected_phase(ru_selected_entry: Entry) -> Phase:
    """A Phase explaining experimental peaks 0 and 1 (2θ = 10°, 20°)."""
    # Correlations: exp peak 0 ↔ ref peak 0, exp peak 1 ↔ ref peak 1.
    # Reference peaks sorted by intensity desc → both at full intensity.
    return Phase(
        entry=ru_selected_entry,
        scale_factor=1.0,
        two_theta_shift=0.0,
        correlations=[(0, 0), (1, 1)],
    )


@pytest.fixture
def ru_candidate_entries() -> list[Entry]:
    """Three candidate entries for the re-rank test.

    * ``C_OVERLAP`` — has peaks at 2θ = [10, 30, 40, 50, 60].  It
      shares peak 0 (2θ=10°) with the selected phase but also has 4
      unique peaks.  After removing peaks 0, 1 (explained by the
      selected phase), it matches all 4 residual peaks → P_npeaks
      rises from 5/6 ≈ 0.83 to 4/4 = 1.0 → FoM rises.

    * ``C_UNRELATED`` — has peaks far from any experimental peak
      (2θ = [70, 75, 80]).  It matches nothing before or after → FoM
      stays at the no-pair baseline.

    * ``C_PARTIAL`` — has peaks at 2θ = [20, 30, 70].  It shares
      peak 1 (2θ=20°, explained) with the selected phase and has one
      unique residual peak (2θ=30°) plus one out-of-range peak.
    """
    c_overlap = _entry_from_two_theta(
        "C_OVERLAP", [10.0, 30.0, 40.0, 50.0, 60.0],
        [100.0, 80.0, 60.0, 40.0, 20.0],
        formula="C Ov", space_group="P1", mineral_name="Overlap",
    )
    c_unrelated = _entry_from_two_theta(
        "C_UNRELATED", [70.0, 75.0, 80.0],
        [100.0, 50.0, 25.0],
        formula="C Un", space_group="P1", mineral_name="Unrelated",
    )
    c_partial = _entry_from_two_theta(
        "C_PARTIAL", [20.0, 30.0, 70.0],
        [100.0, 60.0, 30.0],
        formula="C Pa", space_group="P1", mineral_name="Partial",
    )
    return [c_overlap, c_unrelated, c_partial]


# ===========================================================================
# build_residual_peaks
# ===========================================================================
class TestBuildResidualPeaks:
    """Unit tests for the residual-peak builder."""

    def test_no_correlations_returns_copy(
        self, ru_exp_peaks: list[Peak], ru_selected_entry: Entry
    ):
        """A phase with no correlations leaves the peak list unchanged."""
        phase = Phase(entry=ru_selected_entry, correlations=[])
        residual = build_residual_peaks(ru_exp_peaks, phase)
        assert len(residual) == len(ru_exp_peaks)
        # Identical 2θ positions and intensities (copy, not aliasing).
        for orig, res in zip(ru_exp_peaks, residual, strict=True):
            assert res.two_theta == orig.two_theta
            assert res.intensity == pytest.approx(orig.intensity)

    def test_empty_peaks_returns_empty(self, ru_selected_phase: Phase):
        assert build_residual_peaks([], ru_selected_phase) == []

    def test_correlated_peaks_intensity_reduced(
        self, ru_exp_peaks: list[Peak], ru_selected_phase: Phase
    ):
        """Peaks correlated to the selected phase have their intensity reduced."""
        residual = build_residual_peaks(ru_exp_peaks, ru_selected_phase)
        # 2 peaks explained → residual has 4 peaks.
        assert len(residual) == 4
        # Unexplained peaks (indices 2..5) keep their original intensity.
        for res, orig in zip(residual, ru_exp_peaks[2:], strict=True):
            assert res.intensity == pytest.approx(orig.intensity)
            assert res.two_theta == orig.two_theta

    def test_fully_explained_peaks_dropped(
        self, ru_exp_peaks: list[Peak], ru_selected_entry: Entry
    ):
        """When the phase contribution exceeds the experimental intensity,
        the residual drops below threshold and the peak is removed."""
        # Scale factor 5.0 → ref contribution 5×100 = 500 > 100 (exp peak 0).
        phase = Phase(
            entry=ru_selected_entry,
            scale_factor=5.0,
            correlations=[(0, 0), (1, 1)],
        )
        residual = build_residual_peaks(ru_exp_peaks, phase)
        # Both explained peaks fully subtracted → only 4 residual peaks.
        assert len(residual) == 4
        residual_tt = [r.two_theta for r in residual]
        assert 10.0 not in residual_tt
        assert 20.0 not in residual_tt
        assert 30.0 in residual_tt

    def test_partial_subtraction_keeps_reduced_peak(
        self, ru_exp_peaks: list[Peak], ru_selected_entry: Entry
    ):
        """A peak whose residual is above threshold is kept with reduced I."""
        # Scale factor 0.5 → ref contributes 0.5×100 = 50; exp was 100 →
        # residual = 50, which is well above the 1% threshold (1.0).
        phase = Phase(
            entry=ru_selected_entry,
            scale_factor=0.5,
            correlations=[(0, 0), (1, 1)],
        )
        residual = build_residual_peaks(ru_exp_peaks, phase)
        # Both peaks kept but with intensity 50 each.
        assert len(residual) == 6
        assert residual[0].intensity == pytest.approx(50.0)
        assert residual[1].intensity == pytest.approx(40.0)  # 80 - 0.5*80
        # Unexplained peaks unchanged.
        assert residual[2].intensity == pytest.approx(60.0)

    def test_original_peaks_not_mutated(
        self, ru_exp_peaks: list[Peak], ru_selected_phase: Phase
    ):
        """The caller's peak list must not be mutated."""
        original_intensities = [p.intensity for p in ru_exp_peaks]
        _ = build_residual_peaks(ru_exp_peaks, ru_selected_phase)
        assert [p.intensity for p in ru_exp_peaks] == original_intensities


# ===========================================================================
# recompute_fom_after_selection
# ===========================================================================
class TestRecomputeFomAfterSelection:
    """End-to-end FoM recompute tests."""

    def _project_with_candidates(
        self,
        exp_peaks: list[Peak],
        candidate_entries: list[Entry],
    ) -> Project:
        """Build a Project whose candidates list is ``(Entry, fom)`` tuples."""
        # Initial rank to populate project.candidates with fom values.
        ranked = rank_candidates(exp_peaks, candidate_entries, wavelength=WL)
        project = Project(
            peaks=exp_peaks,
            candidates=[(r.entry, r.fom) for r in ranked],
        )
        return project

    def test_overlapping_candidate_fom_rises(
        self,
        ru_exp_peaks: list[Peak],
        ru_selected_phase: Phase,
        ru_candidate_entries: list[Entry],
    ):
        """C_OVERLAP's FoM rises after the selected phase explains peak 0."""
        project = self._project_with_candidates(
            ru_exp_peaks, ru_candidate_entries
        )
        # Original FoM of C_OVERLAP.
        before = next(
            r for r in rank_candidates(ru_exp_peaks, ru_candidate_entries, wavelength=WL)
            if r.entry.entry_id == "C_OVERLAP"
        )
        # Recompute on residual peaks.
        results = recompute_fom_after_selection(
            project, ru_selected_phase, wavelength=WL
        )
        after = next(r for r in results if r.entry.entry_id == "C_OVERLAP")
        # FoM must strictly increase: 5/6 → 4/4 (P_npeaks 0.833 → 1.0).
        assert after.fom > before.fom, (
            f"expected FoM to rise, before={before.fom:.4f} after={after.fom:.4f}"
        )
        # P_npeaks specifically: 5/6 → 4/4.
        assert after.p_values["npeaks"] > before.p_values["npeaks"]
        assert after.p_values["npeaks"] == pytest.approx(1.0, abs=1e-9)

    def test_unrelated_candidate_fom_unchanged(
        self,
        ru_exp_peaks: list[Peak],
        ru_selected_phase: Phase,
        ru_candidate_entries: list[Entry],
    ):
        """C_UNRELATED (no correlated pairs) keeps the no-pair baseline FoM."""
        project = self._project_with_candidates(
            ru_exp_peaks, ru_candidate_entries
        )
        results = recompute_fom_after_selection(
            project, ru_selected_phase, wavelength=WL
        )
        unrelated = next(
            r for r in results if r.entry.entry_id == "C_UNRELATED"
        )
        # No pairs before or after → FoM = 1 - sum(w_i for i in
        # [peakpos, intensity, npeaks, ncorr]) (i_scale defaults to 1.0).
        expected = 1.0 - (
            DEFAULT_WEIGHTS.peakpos
            + DEFAULT_WEIGHTS.intensity
            + DEFAULT_WEIGHTS.npeaks
            + DEFAULT_WEIGHTS.ncorr
        )
        assert unrelated.fom == pytest.approx(expected, abs=1e-9)
        assert unrelated.pairs == []

    def test_results_sorted_by_fom_descending(
        self,
        ru_exp_peaks: list[Peak],
        ru_selected_phase: Phase,
        ru_candidate_entries: list[Entry],
    ):
        project = self._project_with_candidates(
            ru_exp_peaks, ru_candidate_entries
        )
        results = recompute_fom_after_selection(
            project, ru_selected_phase, wavelength=WL
        )
        foms = [r.fom for r in results]
        assert foms == sorted(foms, reverse=True)

    def test_returns_candidate_result_objects(
        self,
        ru_exp_peaks: list[Peak],
        ru_selected_phase: Phase,
        ru_candidate_entries: list[Entry],
    ):
        project = self._project_with_candidates(
            ru_exp_peaks, ru_candidate_entries
        )
        results = recompute_fom_after_selection(
            project, ru_selected_phase, wavelength=WL
        )
        assert len(results) == len(ru_candidate_entries)
        for r in results:
            assert isinstance(r, CandidateResult)
            assert isinstance(r.pairs, list)
            assert isinstance(r.p_values, dict)

    def test_project_not_mutated(
        self,
        ru_exp_peaks: list[Peak],
        ru_selected_phase: Phase,
        ru_candidate_entries: list[Entry],
    ):
        """The function must not mutate project.peaks / project.candidates."""
        project = self._project_with_candidates(
            ru_exp_peaks, ru_candidate_entries
        )
        peaks_before = list(project.peaks)
        cands_before = list(project.candidates)
        _ = recompute_fom_after_selection(
            project, ru_selected_phase, wavelength=WL
        )
        assert project.peaks == peaks_before
        assert project.candidates == cands_before

    def test_no_correlations_returns_full_recompute(
        self,
        ru_exp_peaks: list[Peak],
        ru_selected_entry: Entry,
        ru_candidate_entries: list[Entry],
    ):
        """A phase with no correlations → residual = all peaks → FoM unchanged."""
        project = self._project_with_candidates(
            ru_exp_peaks, ru_candidate_entries
        )
        phase = Phase(entry=ru_selected_entry, correlations=[])
        results = recompute_fom_after_selection(
            project, phase, wavelength=WL
        )
        # Compare against a plain rank_candidates run (same input).
        baseline = rank_candidates(
            ru_exp_peaks, ru_candidate_entries, wavelength=WL
        )
        for r, b in zip(results, baseline, strict=True):
            assert r.fom == pytest.approx(b.fom, abs=1e-9)

    def test_empty_project_returns_empty(self, ru_selected_phase: Phase):
        """A project with no peaks / no candidates → empty result."""
        project = Project()
        assert recompute_fom_after_selection(
            project, ru_selected_phase, wavelength=WL
        ) == []

    def test_residual_peak_count_reflected_in_npeaks(
        self,
        ru_exp_peaks: list[Peak],
        ru_selected_phase: Phase,
        ru_candidate_entries: list[Entry],
    ):
        """The FoM recompute uses the residual peak count, not the original."""
        project = self._project_with_candidates(
            ru_exp_peaks, ru_candidate_entries
        )
        results = recompute_fom_after_selection(
            project, ru_selected_phase, wavelength=WL
        )
        overlap = next(
            r for r in results if r.entry.entry_id == "C_OVERLAP"
        )
        # Residual peaks: 4 (peaks at 30, 40, 50, 60).  C_OVERLAP
        # matches all 4 → npeaks = 4/4 = 1.0.
        assert overlap.p_values["npeaks"] == pytest.approx(1.0, abs=1e-9)

    def test_wavelength_fallback_to_project_pattern(
        self,
        ru_exp_peaks: list[Peak],
        ru_selected_phase: Phase,
        ru_candidate_entries: list[Entry],
    ):
        """When wavelength is None, the project's first pattern is used."""
        from xinmatch.core.model import Pattern

        project = Project(
            patterns=[Pattern(
                two_theta=np.array([10.0, 60.0]),
                intensity=np.array([100.0, 10.0]),
                wavelength=WL,
            )],
            peaks=ru_exp_peaks,
            candidates=[(e, 0.0) for e in ru_candidate_entries],
        )
        # No explicit wavelength → uses project.patterns[0].wavelength.
        results = recompute_fom_after_selection(
            project, ru_selected_phase
        )
        assert len(results) == 3

    def test_custom_weights_passthrough(
        self,
        ru_exp_peaks: list[Peak],
        ru_selected_phase: Phase,
        ru_candidate_entries: list[Entry],
    ):
        """Custom weights are forwarded to rank_candidates."""
        from xinmatch.core.search.fom_criteria import FomWeights

        custom = FomWeights(
            peakpos=0.5, intensity=0.1, npeaks=0.2, ncorr=0.1, i_scale=0.0
        )
        project = self._project_with_candidates(
            ru_exp_peaks, ru_candidate_entries
        )
        results = recompute_fom_after_selection(
            project, ru_selected_phase, wavelength=WL, weights=custom
        )
        # Compare against a direct rank_candidates call with the same
        # custom weights on the manually-built residual peaks.
        residual_peaks = build_residual_peaks(ru_exp_peaks, ru_selected_phase)
        baseline = rank_candidates(
            residual_peaks, ru_candidate_entries, wavelength=WL, weights=custom
        )
        for r, b in zip(results, baseline, strict=True):
            assert r.fom == pytest.approx(b.fom, abs=1e-9)
            assert r.p_values["npeaks"] == pytest.approx(
                b.p_values["npeaks"], abs=1e-9
            )
