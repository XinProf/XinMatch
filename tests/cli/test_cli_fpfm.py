"""Tests for ``xinmatch search --mode fpfm`` and the Kα doublet switches (v1.3.0).

Covers the CLI half of the FPFM Kα2 knob:

* ``--mode fpfm`` runs full-pattern search-match, reports ``mode`` /
  ``kalpha`` in the JSON payload and produces **no** peak list
  (``n_peaks == 0`` — FPFM fits the raw spectrum, it does not seek peaks);
* ``--single-kalpha`` switches the Kα1/Kα2 doublet off;
* ``--kalpha1`` overrides the wavelength taken from the pattern file.

These use a tiny self-built reference DB (no real COD required), so only
two candidates survive pre-screening and each refinement is fast.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from tests.xindb_support import write_xindb
from xinmatch.core.model import CellParams, Entry

WL = 1.5406  # Cu Kα1


def _d_from_two_theta(two_theta: float, wavelength: float = WL) -> float:
    return wavelength / (2.0 * math.sin(math.radians(two_theta / 2.0)))


def run_cli(*args: str, timeout: int = 180) -> subprocess.CompletedProcess:
    """Run the CLI in-process-entrypoint mode (end-to-end, like the core suite)."""
    return subprocess.run(
        [sys.executable, "-m", "xinmatch.cli.main", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@pytest.fixture
def pattern_file(tmp_path: Path) -> Path:
    """Two-column ASCII pattern with Gaussian peaks at known 2θ positions."""
    two_thetas = np.linspace(5.0, 65.0, 1201)
    intensity = np.zeros_like(two_thetas)
    for centre, height in ((15.0, 1000.0), (25.0, 800.0), (35.0, 600.0), (45.0, 400.0)):
        sigma = 0.12
        intensity += height * np.exp(-0.5 * ((two_thetas - centre) / sigma) ** 2)
    intensity += 20.0  # flat background; FPFM absorbs it inside the fit

    path = tmp_path / "pattern.txt"
    path.write_text(
        "\n".join(f"{t:.4f} {i:.4f}" for t, i in zip(two_thetas, intensity, strict=True)),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Two-entry reference DB: one matching the pattern peaks, one decoy."""
    exp_tt = [15.0, 25.0, 35.0, 45.0]
    exp_int = [1000.0, 800.0, 600.0, 400.0]
    order = sorted(range(len(exp_tt)), key=lambda i: -exp_int[i])
    truth = Entry(
        entry_id="TRUTH",
        formula="Si O2",
        d_spacings=np.array(
            [_d_from_two_theta(exp_tt[i]) for i in order], dtype=np.float64
        ),
        intensities=np.array([exp_int[i] for i in order], dtype=np.float64),
        mineral_name="Quartz",
        cell=CellParams(4.914, 4.914, 5.405, gamma=120.0),
        space_group="P3221",
        literature={"author": "tester", "year": 2000},
        quality="A",
    )
    decoy_tt = [20.0, 30.0, 40.0, 50.0]
    decoy_int = [500.0, 400.0, 300.0, 200.0]
    order2 = sorted(range(len(decoy_tt)), key=lambda i: -decoy_int[i])
    decoy = Entry(
        entry_id="DECOY",
        formula="C Ca O3",
        d_spacings=np.array(
            [_d_from_two_theta(decoy_tt[i]) for i in order2], dtype=np.float64
        ),
        intensities=np.array([decoy_int[i] for i in order2], dtype=np.float64),
        mineral_name="Calcite",
        space_group="R-3c",
        quality="B",
    )

    path = tmp_path / "ref.xinDB"
    # v3.0.0: 参考库只能是列存 .xinDB
    return write_xindb(path, [truth, decoy])


def _fpfm_run(pattern_file: Path, db_path: Path, *extra: str) -> dict:
    """Run FPFM search with a small pre-screen and return the parsed payload."""
    result = run_cli(
        "search", str(pattern_file), "--db", str(db_path),
        "--mode", "fpfm", "--prescreen-n", "2", "--top-n", "2",
        *extra, "--json",
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


class TestFpfmMode:
    def test_fpfm_reports_mode_and_no_peaks(
        self, pattern_file: Path, db_path: Path
    ) -> None:
        """FPFM fits the raw spectrum: no peak search, so n_peaks stays 0."""
        data = _fpfm_run(pattern_file, db_path)
        assert data["mode"] == "fpfm"
        assert data["n_peaks"] == 0
        assert data["n_candidates"] >= 1
        assert data["candidates"]

    def test_legacy_smpf_mode_alias_accepted(
        self, pattern_file: Path, db_path: Path
    ) -> None:
        """Pre-v1.6.1 ``--mode smpf`` still runs and reports the new name."""
        result = run_cli(
            "search", str(pattern_file), "--db", str(db_path),
            "--mode", "smpf", "--prescreen-n", "2", "--top-n", "2", "--json",
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["mode"] == "fpfm"
        assert data["n_peaks"] == 0

    def test_double_line_is_default(self, pattern_file: Path, db_path: Path) -> None:
        """Default is the Kα1/Kα2 doublet (real laboratory Cu Kα data)."""
        data = _fpfm_run(pattern_file, db_path)
        ka = data["kalpha"]
        assert ka["double_line"] is True
        assert ka["kalpha2"] == pytest.approx(1.5444)
        # No --kalpha1 given → follow the pattern's own wavelength.
        assert ka["kalpha1"] == pytest.approx(WL)

    def test_single_kalpha_flag_disables_doublet(
        self, pattern_file: Path, db_path: Path
    ) -> None:
        """--single-kalpha: required for CIF-generated / Kα2-stripped patterns."""
        data = _fpfm_run(pattern_file, db_path, "--single-kalpha")
        ka = data["kalpha"]
        assert ka["double_line"] is False
        assert ka["kalpha2"] is None

    def test_kalpha1_override(self, pattern_file: Path, db_path: Path) -> None:
        """--kalpha1 overrides the pattern wavelength (e.g. for Co targets)."""
        data = _fpfm_run(pattern_file, db_path, "--kalpha1", "1.7903")
        assert data["kalpha"]["kalpha1"] == pytest.approx(1.7903)

    def test_default_mode_still_peaks(self, pattern_file: Path, db_path: Path) -> None:
        """Regression guard: without --mode fpfm the CLI keeps seeking peaks."""
        result = run_cli(
            "search", str(pattern_file), "--db", str(db_path),
            "--top-n", "5", "--json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["mode"] == "peaks"
        assert data["n_peaks"] >= 1
