"""Tests for :mod:`xinmatch.core.batch` and the ``xinmatch batch`` CLI (T14.3).

Covers:
* the SMPF-mode batch path (config ``search.mode: smpf``) against the real
  COD database — the pipeline must fit the raw profile without peak
  picking and rank a ground-truth phase on top;
* the main-CLI integration (``xinmatch batch config.yaml``) end to end;
* config validation for an unknown ``search.mode``.

The peaks-mode path is covered by ``tests/test_batch_runner.py`` (which
exercises the same engine through the ``tools.batch_runner`` wrapper).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from xinmatch.core.batch import load_config, run_batch
from xinmatch.core.db import build_element_index, create_tables, insert_entries
from xinmatch.core.model import CellParams, Entry

WL = 1.5406
REAL_DB = Path(r"D:\Project\XRD\XinMatch\data\cod_inorganics.db")
SYNTH_01 = Path(r"D:\Project\XRD\test_xrd\synthetic\synth_01.txt")
# Ground truth of synth_01 (see tests/search/test_synthetic_acceptance.py).
SYNTH_01_TRUTH = ("Al2 O3", "O Zn", "Ca F2")


def _formula_norm(f: str) -> str:
    return "".join(str(f).upper().split())


@pytest.mark.skipif(
    not REAL_DB.exists() or not SYNTH_01.exists(),
    reason="requires the real COD DB and synthetic pattern (dev machine)",
)
def test_batch_smpf_mode_ranks_truth(tmp_path: Path):
    """SMPF batch: no peak picking, truth phase on top for synth_01.

    The synthetic patterns are single-line (Kα1 only), so the config must
    use ``single_kalpha: true`` — a double-line model would depress the
    true phases (see docs/smpf_mechanism.md §8.1).
    """
    cfg = {
        "samples": [{"name": "synth_01", "path": str(SYNTH_01)}],
        "search": {
            "db": str(REAL_DB),
            "mode": "smpf",
            "single_kalpha": True,
            "top_n": 20,
        },
        "output": {"dir": str(tmp_path / "out"), "formats": ["md"]},
    }
    cfg_path = tmp_path / "batch_smpf.json"
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    config, config_dir = load_config(cfg_path)
    batch = run_batch(config, config_dir=config_dir)

    assert batch.n_ok == 1, batch.samples[0].error if batch.samples else "no samples"
    sample = batch.samples[0]
    assert sample.ok
    assert sample.top_entry_id is not None
    assert sample.top_fom is not None and sample.top_fom > 0.0
    # SMPF fits the raw profile — n_peaks stays 0 (no peak picking).
    assert sample.n_peaks == 0
    norm = _formula_norm(sample.top_formula)
    assert any(norm == _formula_norm(t) for t in SYNTH_01_TRUTH), (
        f"top {sample.top_formula} not in truth {SYNTH_01_TRUTH}"
    )
    assert (tmp_path / "out" / "synth_01.md").exists()


# --------------------------------------------------------------------------- #
# Main-CLI integration: xinmatch batch config.yaml
# --------------------------------------------------------------------------- #
def _build_synth_db(db_path: Path) -> None:
    import numpy as np

    from xinmatch.core.io import load_pattern  # noqa: F401 — keep import order stable

    def _d(two_theta: float) -> float:
        return WL / (2.0 * np.sin(np.radians(two_theta / 2.0)))

    def _entry(eid: str, peaks: list[tuple[float, float]], formula: str) -> Entry:
        order = sorted(range(len(peaks)), key=lambda i: -peaks[i][1])
        return Entry(
            entry_id=eid,
            formula=formula,
            d_spacings=np.array([_d(peaks[i][0]) for i in order]),
            intensities=np.array([peaks[i][1] for i in order], dtype=np.float64),
            mineral_name=None,
            space_group="P1",
            cell=CellParams(4.0, 4.0, 4.0),
            hkl=None,
            literature={"source": "synth"},
            quality="A",
        )

    entries = [
        _entry("SYN-QZ", [(20.0, 100), (31.77, 60), (45.0, 30)], "O2 Si"),
        _entry("SYN-CC", [(29.4, 100), (39.4, 50), (47.5, 25)], "C Ca O3"),
    ]
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)
    insert_entries(conn, entries)
    build_element_index(conn)
    conn.close()


def _write_pattern(path: Path, peaks: list[tuple[float, float]]) -> None:
    import numpy as np

    rng = np.random.default_rng(7)
    tt = np.arange(15.0, 60.0, 0.05)
    intensity = 100.0 + rng.normal(0.0, 1.5, size=tt.size)
    for center, rel in peaks:
        intensity += 800.0 * (rel / 100.0) * np.exp(-((tt - center) ** 2) / (2 * 0.3**2))
    path.write_text(
        "\n".join(f"{t:.5f} {v:.4f}" for t, v in zip(tt, intensity, strict=True))
        + "\n",
        encoding="utf-8",
    )


def test_xinmatch_batch_cli_end_to_end(tmp_path: Path, capsys):
    """``xinmatch batch config.yaml`` runs the engine and writes the summary."""
    work = tmp_path / "work"
    work.mkdir()
    (work / "patterns").mkdir()
    _build_synth_db(work / "synth.db")
    _write_pattern(work / "patterns" / "qz.txt", [(20.0, 100), (31.77, 60), (45.0, 30)])

    cfg = {
        "samples": [{"name": "qz", "path": "patterns/qz.txt"}],
        "search": {"db": "synth.db", "top_n": 10},
        "output": {"dir": "out", "formats": ["html", "md", "txt"]},
    }
    cfg_path = work / "config.yaml"
    import yaml

    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    from xinmatch.cli.main import main as cli_main

    rc = cli_main(["batch", str(cfg_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "SYN-QZ" in out  # top entry surfaced in the per-sample log
    assert (work / "out" / "qz.html").exists()
    assert (work / "out" / "batch_summary.md").exists()
    payload = json.loads((work / "out" / "batch_summary.json").read_text(
        encoding="utf-8"
    ))
    assert payload["n_ok"] == 1
    assert payload["samples"][0]["top_entry_id"] == "SYN-QZ"


def test_batch_invalid_mode_rejected(tmp_path: Path):
    """Unknown search.mode is a config error raised before any I/O."""
    cfg = {
        "samples": [{"path": "x.txt"}],
        "search": {"db": "d.db", "mode": "fancy"},
    }
    cfg_path = tmp_path / "bad.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    config, config_dir = load_config(cfg_path)
    with pytest.raises(ValueError, match="peaks.*smpf"):
        run_batch(config, config_dir=config_dir)
