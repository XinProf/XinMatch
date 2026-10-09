"""Tests for the FoM P-value reverse-engineering framework (T0.8).

These tests verify the parsing and reverse-engineering pipeline of
``tools/build_baseline.py`` using a **synthetic** reference-software candidate-list
CSV (5 fake candidates).  They do NOT attempt to reproduce real reference-software
P values — the goal is to verify the pipeline plumbing so that when
real CSV files are placed under ``tests/baseline/`` the framework
works correctly.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from tools.build_baseline import (
    CANDIDATE_CSV_HEADER,
    P_KEY_MAP,
    KernelFit,
    ReverseEngineerReport,
    build_baseline,
    main,
    parse_candidate_csv,
    reverse_engineer_p_defs,
)

# --------------------------------------------------------------------- #
# Synthetic CSV fixtures
# --------------------------------------------------------------------- #

# Five synthetic candidate rows — numbers chosen to span P values in
# [0, 1] so that the kernel fits have something to learn.
SYNTHETIC_CSV = """Entry;Qual.;Formula sum;Name;P(peakpos.);P(I/I0);P(#peaks);P(#corr.);I scale fct.;FoM
96-152-5699;C;B6 La0.987;La0.987 B6;0.9968;0.9963;0.9961;1.0000;1.0348;0.9979
96-100-0051;C;C Ca O3;Calcite;0.8500;0.7800;0.7000;0.9000;1.2000;0.7800
96-200-1234;*;Si O2;Quartz;0.5000;0.6000;0.4500;0.6500;0.5000;0.5100
96-300-5678;?;Fe;Iron;0.3000;0.3500;0.2000;0.4000;2.0000;0.2500
96-400-9999;C;Ti O2;Rutile;0.1000;0.1000;0.0500;0.1000;3.0000;0.0500
"""


@pytest.fixture
def synth_csv_path(tmp_path: Path) -> Path:
    """Write the synthetic CSV to a temp file and return its path."""
    p = tmp_path / "lab6_synthetic.csv"
    p.write_text(SYNTHETIC_CSV, encoding="utf-8")
    return p


# --------------------------------------------------------------------- #
# parse_candidate_csv
# --------------------------------------------------------------------- #


def test_parse_candidate_csv_returns_one_dict_per_row(synth_csv_path: Path):
    rows = parse_candidate_csv(synth_csv_path)
    assert len(rows) == 5


def test_parse_candidate_csv_header_keys_present(synth_csv_path: Path):
    rows = parse_candidate_csv(synth_csv_path)
    for row in rows:
        for col in CANDIDATE_CSV_HEADER:
            assert col in row, f"missing column {col!r}"


def test_parse_candidate_csv_numeric_types(synth_csv_path: Path):
    rows = parse_candidate_csv(synth_csv_path)
    first = rows[0]
    # LaB6 row: known values.
    assert isinstance(first["P(peakpos.)"], float)
    assert isinstance(first["P(I/I0)"], float)
    assert isinstance(first["P(#peaks)"], float)
    assert isinstance(first["P(#corr.)"], float)
    assert isinstance(first["I scale fct."], float)
    assert isinstance(first["FoM"], float)
    assert first["P(peakpos.)"] == pytest.approx(0.9968)
    assert first["P(I/I0)"] == pytest.approx(0.9963)
    assert first["P(#peaks)"] == pytest.approx(0.9961)
    assert first["P(#corr.)"] == pytest.approx(1.0000)
    assert first["I scale fct."] == pytest.approx(1.0348)
    assert first["FoM"] == pytest.approx(0.9979)


def test_parse_candidate_csv_text_fields(synth_csv_path: Path):
    rows = parse_candidate_csv(synth_csv_path)
    first = rows[0]
    assert first["Entry"] == "96-152-5699"
    assert first["Qual."] == "C"
    assert first["Formula sum"] == "B6 La0.987"
    assert first["Name"] == "La0.987 B6"


def test_parse_candidate_csv_handles_european_decimal(tmp_path: Path):
    """Comma decimal separators must be parsed as floats."""
    csv_content = (
        "Entry;Qual.;Formula sum;Name;P(peakpos.);P(I/I0);P(#peaks);"
        "P(#corr.);I scale fct.;FoM\n"
        "X;C;Foo;Bar;0,5;0,25;0,75;1,0;1,5;0,5\n"
    )
    p = tmp_path / "eu.csv"
    p.write_text(csv_content, encoding="utf-8")
    rows = parse_candidate_csv(p)
    assert rows[0]["P(peakpos.)"] == pytest.approx(0.5)
    assert rows[0]["I scale fct."] == pytest.approx(1.5)


def test_parse_candidate_csv_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        parse_candidate_csv(tmp_path / "does_not_exist.csv")


def test_parse_candidate_csv_bad_header_raises(tmp_path: Path):
    p = tmp_path / "bad.csv"
    p.write_text("a;b;c\n1;2;3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="header"):
        parse_candidate_csv(p)


def test_parse_candidate_csv_blank_lines_skipped(tmp_path: Path):
    csv_content = SYNTHETIC_CSV.replace(
        "96-100-0051;C;C Ca O3;Calcite;0.8500;0.7800;0.7000;0.9000;1.2000;0.7800\n",
        "96-100-0051;C;C Ca O3;Calcite;0.8500;0.7800;0.7000;0.9000;1.2000;0.7800\n\n\n",
    )
    p = tmp_path / "blanks.csv"
    p.write_text(csv_content, encoding="utf-8")
    rows = parse_candidate_csv(p)
    assert len(rows) == 5


def test_parse_candidate_csv_trailing_semicolon_tolerated(tmp_path: Path):
    """A trailing ``;`` adds an extra empty field — must not break parsing."""
    csv_content = SYNTHETIC_CSV.replace(
        "96-152-5699;C;B6 La0.987;La0.987 B6;0.9968;0.9963;0.9961;1.0000;1.0348;0.9979\n",
        "96-152-5699;C;B6 La0.987;La0.987 B6;0.9968;0.9963;0.9961;1.0000;1.0348;0.9979;\n",
    )
    p = tmp_path / "trail.csv"
    p.write_text(csv_content, encoding="utf-8")
    rows = parse_candidate_csv(p)
    assert len(rows) == 5
    assert rows[0]["FoM"] == pytest.approx(0.9979)


# --------------------------------------------------------------------- #
# reverse_engineer_p_defs
# --------------------------------------------------------------------- #


def _synth_our_p_values() -> list[dict]:
    """Synthetic *raw mismatch* side-channel matching the 5 CSV rows.

    Mismatches are reverse-engineered from the target P values so the
    Gaussian kernel has a deterministic best fit:

        P = exp(-mismatch / σ²)  ⇒  mismatch = -σ² · ln(P)

    With σ = 0.1 we get mismatch = -0.01 * ln(P).  This makes the test
    fully reproducible.
    """
    sigma = 0.1
    p_values = [
        {"peakpos": 0.9968, "intensity": 0.9963, "npeaks": 0.9961,
         "ncorr": 1.0000, "i_scale": 1.0348},
        {"peakpos": 0.8500, "intensity": 0.7800, "npeaks": 0.7000,
         "ncorr": 0.9000, "i_scale": 1.2000},
        {"peakpos": 0.5000, "intensity": 0.6000, "npeaks": 0.4500,
         "ncorr": 0.6500, "i_scale": 0.5000},
        {"peakpos": 0.3000, "intensity": 0.3500, "npeaks": 0.2000,
         "ncorr": 0.4000, "i_scale": 2.0000},
        {"peakpos": 0.1000, "intensity": 0.1000, "npeaks": 0.0500,
         "ncorr": 0.1000, "i_scale": 3.0000},
    ]
    out = []
    for p in p_values:
        rec = {
            "peakpos_mismatch": -sigma * sigma * math.log(max(p["peakpos"], 1e-12)),
            "intensity_mismatch": -sigma * sigma * math.log(max(p["intensity"], 1e-12)),
            "npeaks_mismatch": 1.0 - p["npeaks"],
            "ncorr_mismatch": 1.0 - p["ncorr"],
            "i_scale_log_delta": abs(math.log(max(p["i_scale"], 1e-12))),
        }
        out.append(rec)
    return out


def test_reverse_engineer_p_defs_returns_one_report_per_p(synth_csv_path: Path):
    samples = parse_candidate_csv(synth_csv_path)
    our = _synth_our_p_values()
    reports = reverse_engineer_p_defs(samples, our)
    assert set(reports.keys()) == {"peakpos", "intensity", "npeaks", "ncorr", "i_scale"}
    for r in reports.values():
        assert isinstance(r, ReverseEngineerReport)


def test_reverse_engineer_p_defs_best_kernel_is_gaussian_for_constructed_data(
    synth_csv_path: Path,
):
    """Data was constructed so Gaussian should reproduce P_peakpos exactly."""
    samples = parse_candidate_csv(synth_csv_path)
    our = _synth_our_p_values()
    reports = reverse_engineer_p_defs(samples, our)
    peakpos_report = reports["peakpos"]
    assert peakpos_report.best_kernel.name == "gaussian"
    # R² must be very close to 1 (data was constructed for σ=0.1).
    assert peakpos_report.best_kernel.r_squared > 0.999
    # Best param (sigma) must be near 0.1.
    assert abs(peakpos_report.best_kernel.best_param - 0.1) < 1e-9


def test_reverse_engineer_p_defs_n_samples_set(synth_csv_path: Path):
    samples = parse_candidate_csv(synth_csv_path)
    our = _synth_our_p_values()
    reports = reverse_engineer_p_defs(samples, our)
    for r in reports.values():
        assert r.n_samples == 5


def test_reverse_engineer_p_defs_all_kernels_populated(synth_csv_path: Path):
    samples = parse_candidate_csv(synth_csv_path)
    our = _synth_our_p_values()
    reports = reverse_engineer_p_defs(samples, our)
    for r in reports.values():
        # Each P value must have at least 4 kernel fits (gaussian,
        # lorentzian, linear, cosine).
        assert len(r.all_kernels) >= 4
        for k in r.all_kernels:
            assert isinstance(k, KernelFit)


def test_reverse_engineer_p_defs_length_mismatch_raises(synth_csv_path: Path):
    samples = parse_candidate_csv(synth_csv_path)
    with pytest.raises(ValueError, match="length"):
        reverse_engineer_p_defs(samples, [{}])  # only 1 vs 5


def test_reverse_engineer_p_defs_i_scale_uses_log_delta(synth_csv_path: Path):
    """I_scale target = exp(-|ln(I_scale)|), kernel must reproduce it."""
    samples = parse_candidate_csv(synth_csv_path)
    our = _synth_our_p_values()
    reports = reverse_engineer_p_defs(samples, our)
    iscale = reports["i_scale"]
    # exp(-|ln(I_scale)|) for I_scale in {1.0348, 1.2, 0.5, 2.0, 3.0}
    # → {0.966, 0.833, 1.0, 0.5, 0.333}.
    # The data has mismatch = |ln(I_scale)| and target = exp(-mismatch).
    # Gaussian with σ=1 gives P = exp(-mismatch) → perfect fit.
    assert iscale.best_kernel.name == "gaussian"
    assert iscale.best_kernel.r_squared > 0.999


def test_reverse_engineer_p_defs_i_scale_handles_zero_mismatch():
    """I_scale = 1.0 → |ln(I_scale)| = 0 → target P = 1.0 (perfect)."""
    samples = [{
        "P(peakpos.)": 1.0, "P(I/I0)": 1.0, "P(#peaks)": 1.0,
        "P(#corr.)": 1.0, "I scale fct.": 1.0, "FoM": 1.0,
        "Entry": "X", "Qual.": "C", "Formula sum": "X",
        "Name": "X",
    }]
    our = [{
        "peakpos_mismatch": 0.0,
        "intensity_mismatch": 0.0,
        "npeaks_mismatch": 0.0,
        "ncorr_mismatch": 0.0,
        "i_scale_log_delta": 0.0,
    }]
    reports = reverse_engineer_p_defs(samples, our)
    # All kernels should give P=1 at mismatch=0 (their boundary value).
    for r in reports.values():
        assert r.best_kernel.r_squared >= 0.0  # well-defined


# --------------------------------------------------------------------- #
# build_baseline (directory scan)
# --------------------------------------------------------------------- #


def test_build_baseline_empty_dir(tmp_path: Path):
    out = build_baseline(tmp_path)
    assert out["csv_files"] == []
    assert out["n_candidates_total"] == 0
    assert out["per_file"] == []


def test_build_baseline_nonexistent_dir(tmp_path: Path):
    """A path that doesn't exist returns an empty report (no exception)."""
    out = build_baseline(tmp_path / "does_not_exist")
    assert out["csv_files"] == []
    assert out["n_candidates_total"] == 0


def test_build_baseline_finds_csvs(tmp_path: Path):
    """Two CSV files in the directory are both parsed."""
    p1 = tmp_path / "sample1.csv"
    p2 = tmp_path / "sample2.csv"
    p1.write_text(SYNTHETIC_CSV, encoding="utf-8")
    p2.write_text(SYNTHETIC_CSV, encoding="utf-8")
    out = build_baseline(tmp_path)
    assert len(out["csv_files"]) == 2
    assert out["n_candidates_total"] == 10  # 5 candidates per file * 2
    assert all(p["n_candidates"] == 5 for p in out["per_file"])


def test_build_baseline_skips_bad_csv(tmp_path: Path):
    """A non-reference-software-format CSV is silently skipped."""
    bad = tmp_path / "bad.csv"
    bad.write_text("a;b;c\n1;2;3\n", encoding="utf-8")
    good = tmp_path / "good.csv"
    good.write_text(SYNTHETIC_CSV, encoding="utf-8")
    out = build_baseline(tmp_path)
    assert out["n_candidates_total"] == 5
    assert len(out["per_file"]) == 1


# --------------------------------------------------------------------- #
# CLI entry point
# --------------------------------------------------------------------- #


def test_main_no_csvs_returns_zero(tmp_path, monkeypatch, capsys):
    """With no CSVs in the directory, main() prints a hint and exits 0."""
    monkeypatch.chdir(tmp_path)
    rc = main([])
    assert rc == 0
    captured = capsys.readouterr()
    assert "No reference-software" in captured.out or "candidate-list" in captured.out


def test_main_with_csvs_returns_zero(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tests" / "baseline").mkdir(parents=True)
    (tmp_path / "tests" / "baseline" / "lab6.csv").write_text(
        SYNTHETIC_CSV, encoding="utf-8"
    )
    rc = main([])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Found" in captured.out
    assert "5 candidates" in captured.out


# --------------------------------------------------------------------- #
# Constants sanity
# --------------------------------------------------------------------- #


def test_candidate_csv_header_has_10_columns():
    assert len(CANDIDATE_CSV_HEADER) == 10


def test_p_key_map_covers_all_p_columns():
    """P_KEY_MAP must map every P / I-scale column to a compute_p_values key."""
    expected_csv_cols = [
        "P(peakpos.)", "P(I/I0)", "P(#peaks)", "P(#corr.)", "I scale fct."
    ]
    for col in expected_csv_cols:
        assert col in P_KEY_MAP
    assert set(P_KEY_MAP.values()) == {
        "peakpos", "intensity", "npeaks", "ncorr", "i_scale"
    }
