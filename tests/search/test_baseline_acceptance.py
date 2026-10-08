"""Tests for the L3 acceptance runner (Phase 6 / T6.9).

Verifies that :mod:`tools.run_acceptance` produces a structured
report, that the synthetic-mode acceptance (no real .txt dependency)
meets the 9/13 hit-rate threshold, and that the per-sample hit / miss
/ DB-missing classification is correct.

These tests run in **synthetic mode** (no real .txt files needed) so
they are CI-friendly and reproducible.  A separate smoke test
verifies that the real-file mode also runs end-to-end when the
test_xrd directory is present (skipped otherwise).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.run_acceptance import (
    CURATED_ENTRIES,
    DB_MISSING_PHASES,
    GROUND_TRUTH,
    AcceptanceReport,
    build_curated_db,
    run_acceptance,
)

# Cu Kα wavelength (test_xrd samples are measured on Cu).
WL = 1.5406


# ---------------------------------------------------------------------------
# Curated DB sanity
# ---------------------------------------------------------------------------
class TestCuratedDB:
    """Sanity checks on the curated reference DB."""

    def test_curated_db_has_entries(self):
        assert len(CURATED_ENTRIES) > 0

    def test_curated_db_covers_ground_truth_phases(self):
        """Every non-DB-missing ground-truth phase has a curated entry."""
        curated_ids = {e.entry_id for e in CURATED_ENTRIES}
        from tools.run_acceptance import _phase_to_entry_id
        missing: list[str] = []
        for sample_id, phases in GROUND_TRUTH.items():
            for phase in phases:
                if phase in DB_MISSING_PHASES:
                    continue
                eid = _phase_to_entry_id(phase)
                if eid not in curated_ids:
                    missing.append(f"{sample_id}/{phase} → {eid}")
        assert not missing, (
            f"Ground-truth phases missing from curated DB: {missing}"
        )

    def test_build_curated_db_returns_connection(self):
        conn = build_curated_db()
        try:
            # Quick sanity query.
            cur = conn.execute("SELECT COUNT(*) FROM entries")
            n = cur.fetchone()[0]
            assert n == len(CURATED_ENTRIES)
        finally:
            conn.close()

    def test_curated_entries_have_peaks(self):
        """Each curated entry has at least 3 d-spacings."""
        for e in CURATED_ENTRIES:
            assert e.n_peaks >= 3, f"{e.entry_id} has only {e.n_peaks} peaks"

    def test_curated_entries_intensities_normalised(self):
        """Each entry's max intensity is reasonable (≤ 200)."""
        for e in CURATED_ENTRIES:
            assert e.intensity_max <= 200.0, (
                f"{e.entry_id} max intensity {e.intensity_max} > 200"
            )


# ---------------------------------------------------------------------------
# GROUND_TRUTH sanity
# ---------------------------------------------------------------------------
class TestGroundTruth:
    """Verify the ground-truth manifest matches the 13-sample spec."""

    def test_has_13_samples(self):
        assert len(GROUND_TRUTH) == 13

    def test_sample_ids_match_expected(self):
        expected = {
            "1-1", "1-2", "2-1", "2-2", "3-1", "3-2", "4-1",
            "5-1", "5-2", "5-2b", "5-3", "7-1", "7-2",
        }
        assert set(GROUND_TRUTH.keys()) == expected

    def test_db_missing_phases_subset_of_ground_truth(self):
        """Every DB-missing phase appears in at least one ground-truth entry."""
        all_phases: set[str] = set()
        for phases in GROUND_TRUTH.values():
            all_phases.update(phases)
        assert DB_MISSING_PHASES.issubset(all_phases)

    def test_lithium_cathode_samples_marked_db_missing(self):
        """1-1 (LiFePO4) and 1-2 (NCM811) must be flagged DB-missing."""
        assert "LiFePO4" in DB_MISSING_PHASES
        assert "NCM811" in DB_MISSING_PHASES


# ---------------------------------------------------------------------------
# Synthetic-mode acceptance (the main T6.9 verification)
# ---------------------------------------------------------------------------
class TestSyntheticAcceptance:
    """Run the acceptance in synthetic mode and verify the threshold."""

    @pytest.fixture(scope="class")
    def report(self) -> AcceptanceReport:
        """Run the synthetic acceptance once for the whole class."""
        return run_acceptance(synthetic=True)

    def test_report_is_acceptance_report(self, report):
        assert isinstance(report, AcceptanceReport)

    def test_report_has_13_samples(self, report):
        assert report.n_samples == 13
        assert len(report.samples) == 13

    def test_hit_rate_meets_threshold(self, report):
        """≥ 9/13 samples must have all ground-truth phases in Top-10."""
        assert report.n_hits >= 9, (
            f"hit rate {report.n_hits}/{report.n_samples} < 9/13; "
            f"failed samples: {report.failed_samples}"
        )

    def test_report_passed_flag(self, report):
        assert report.passed is True

    def test_hit_rate_above_70pct(self, report):
        """70 % sample-level hit rate (per the spec)."""
        assert report.hit_rate_pct >= 70.0

    def test_db_missing_samples_isolated(self, report):
        """1-1 and 1-2 should be in db_missing_samples (Li-ion cathode)."""
        assert "1-1" in report.db_missing_samples
        assert "1-2" in report.db_missing_samples

    def test_db_missing_samples_not_failed(self, report):
        """DB-missing samples should not count as algorithmic failures."""
        # 1-1 and 1-2 are DB-missing only — they should not be in
        # failed_samples.
        for sid in ("1-1", "1-2"):
            if sid in report.db_missing_samples:
                assert sid not in report.failed_samples

    def test_two_phase_samples_all_hit(self, report):
        """2-1 (ZnO + CaCO3) and 2-2 (TiO2 anatase + rutile) hit all phases."""
        for sid in ("2-1", "2-2"):
            s = next(r for r in report.samples if r.sample_id == sid)
            assert s.all_phases_in_top10
            assert not s.missed_phases

    def test_multi_phase_samples_hit(self, report):
        """3-1, 4-1, 5-1, 5-2, 5-3 all hit (3+ phases each)."""
        for sid in ("3-1", "4-1", "5-1", "5-2", "5-3"):
            s = next(r for r in report.samples if r.sample_id == sid)
            assert s.all_phases_in_top10, (
                f"{sid} missed phases: {s.missed_phases}"
            )

    def test_seven_phase_sample_7_1_hits_all(self, report):
        """7-1 (7 phases) — the hardest sample — must hit all phases."""
        s = next(r for r in report.samples if r.sample_id == "7-1")
        assert s.all_phases_in_top10
        # Specifically: all 7 phases found.
        assert len(s.hit_phases) == 7

    def test_sample_results_have_top10_lists(self, report):
        """Each sample result carries the Top-10 entry/mineral lists."""
        for s in report.samples:
            if s.error or s.n_exp_peaks == 0:
                continue  # DB-missing samples have empty lists.
            assert isinstance(s.top10_mineral_names, list)
            assert isinstance(s.top10_entry_ids, list)
            assert len(s.top10_mineral_names) <= 10

    def test_report_serialises_to_json(self, report):
        """The report must be JSON-serialisable (for --json output)."""
        d = report.to_dict()
        text = json.dumps(d, ensure_ascii=False)
        restored = json.loads(text)
        assert restored["n_samples"] == 13
        assert restored["n_hits"] == report.n_hits

    def test_sample_result_to_dict(self, report):
        s = report.samples[0]
        d = s.to_dict()
        assert "sample_id" in d
        assert "ground_truth" in d
        assert "hit_phases" in d
        assert "missed_phases" in d
        assert "db_missing_phases" in d


# ---------------------------------------------------------------------------
# Real-file mode smoke test (skipped when test_xrd is unavailable)
# ---------------------------------------------------------------------------
class TestRealFileMode:
    """Smoke-test the real-file mode; skipped when test_xrd is missing."""

    REAL_DIR = Path(r"D:\Project\XRD\test_xrd\txt")

    @pytest.mark.skipif(
        not REAL_DIR.exists(),
        reason=f"test_xrd directory not present: {REAL_DIR}",
    )
    def test_real_mode_runs_and_meets_threshold(self):
        """Real-file mode must run end-to-end and meet 9/13."""
        report = run_acceptance(sample_dir=self.REAL_DIR, synthetic=False)
        assert isinstance(report, AcceptanceReport)
        assert report.n_samples == 13
        # Threshold: 9/13 (real-file mode may have format-detection
        # issues that fall back to synthetic for some samples).
        assert report.n_hits >= 9, (
            f"real-mode hit rate {report.n_hits}/{report.n_samples} < 9/13; "
            f"failed: {report.failed_samples}"
        )


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
class TestReproducibility:
    """Verify the synthetic acceptance is deterministic."""

    def test_two_runs_identical(self):
        r1 = run_acceptance(synthetic=True)
        r2 = run_acceptance(synthetic=True)
        assert r1.n_hits == r2.n_hits
        assert r1.hit_rate_pct == r2.hit_rate_pct
        for s1, s2 in zip(r1.samples, r2.samples, strict=True):
            assert s1.hit_phases == s2.hit_phases
            assert s1.missed_phases == s2.missed_phases
            assert s1.top10_entry_ids == s2.top10_entry_ids
