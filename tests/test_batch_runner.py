"""End-to-end tests for :mod:`tools.batch_runner` (T14.3).

Self-contained: builds a tiny synthetic reference DB and synthetic 2-column
ASCII patterns (no real COD archive, no vendor files).  Exercises the full
"config → execute → reports" loop for both YAML and JSON configs, plus the
per-sample error isolation (a missing pattern file must not abort the batch).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from tests.xindb_support import write_xindb
from tools.batch_runner import load_config, run_batch
from tools.batch_runner import main as batch_main
from xinmatch.core.model import CellParams, Entry

WL = 1.5406


# --------------------------------------------------------------------------- #
# Synthetic reference DB
# --------------------------------------------------------------------------- #
def _d(two_theta: float) -> float:
    return WL / (2.0 * math.sin(math.radians(two_theta / 2.0)))


def _entry(
    entry_id: str,
    peaks: list[tuple[float, float]],
    formula: str,
    mineral: str | None = None,
) -> Entry:
    order = sorted(range(len(peaks)), key=lambda i: -peaks[i][1])
    return Entry(
        entry_id=entry_id,
        formula=formula,
        d_spacings=np.array([_d(peaks[i][0]) for i in order]),
        intensities=np.array([peaks[i][1] for i in order], dtype=np.float64),
        mineral_name=mineral,
        space_group="P1",
        cell=CellParams(4.0, 4.0, 4.0),
        hkl=None,
        literature={"source": "synth"},
        quality="A",
    )


def _build_synth_db(db_path: Path) -> None:
    """Ground-truth entries (QZ / CC) + decoys (D1 far away, D2 shifted)."""
    entries = [
        _entry("SYN-QZ", [(20.0, 100), (31.77, 60), (45.0, 30)], "O2 Si", "QuartzSynth"),
        _entry("SYN-CC", [(29.4, 100), (39.4, 50), (47.5, 25)], "C Ca O3", "CalciteSynth"),
        _entry("SYN-D1", [(62.0, 100), (66.0, 60)], "X Y"),
        _entry("SYN-D2", [(33.0, 100), (43.0, 60)], "Z W"),
    ]
    # v3.0.0: 检索入口只认列存 .xinDB（旧的 entries/peaks 行表已删除）
    write_xindb(db_path, entries)


def _write_pattern(path: Path, peaks: list[tuple[float, float]]) -> None:
    """Write a 2-column ASCII pattern (2θ, I) with strong Gaussian peaks."""
    rng = np.random.default_rng(7)
    tt = np.arange(15.0, 60.0, 0.05)
    intensity = 100.0 + rng.normal(0.0, 1.5, size=tt.size)
    for center, rel in peaks:
        intensity += 800.0 * (rel / 100.0) * np.exp(-((tt - center) ** 2) / (2 * 0.3**2))
    lines = [f"{t:.5f} {v:.4f}" for t, v in zip(tt, intensity, strict=True)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Fixture: a batch workspace ready to run
# --------------------------------------------------------------------------- #
QZ_PEAKS = [(20.0, 100), (31.77, 60), (45.0, 30)]
CC_PEAKS = [(29.4, 100), (39.4, 50), (47.5, 25)]


@pytest.fixture()
def batch_workspace(tmp_path: Path) -> Path:
    """Lay down DB + two synthetic patterns under tmp_path/work."""
    work = tmp_path / "work"
    work.mkdir()
    (work / "patterns").mkdir()
    _build_synth_db(work / "synth.xinDB")
    _write_pattern(work / "patterns" / "qz.txt", QZ_PEAKS)
    _write_pattern(work / "patterns" / "cc.txt", CC_PEAKS)
    return work


def _write_config(work: Path, name: str) -> Path:
    """Write a YAML or JSON config into *work*; return its path."""
    cfg = {
        "samples": [
            {"name": "qz", "path": "patterns/qz.txt"},
            {"name": "cc", "path": "patterns/cc.txt"},
            {"name": "broken", "path": "patterns/does-not-exist.txt"},
        ],
        "preprocess": {
            "smooth": True,
            "background": True,
            "strip_alpha2": False,
            "peak_sensitivity": "low",
        },
        "search": {"db": "synth.xinDB", "top_n": 10},
        "output": {"dir": "out", "formats": ["html", "md", "txt"]},
    }
    p = work / name
    if name.endswith(".json"):
        p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    else:
        import yaml

        p.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
# YAML end-to-end
# --------------------------------------------------------------------------- #
def test_batch_yaml_end_to_end(batch_workspace: Path):
    cfg_path = _write_config(batch_workspace, "config.yaml")
    config, config_dir = load_config(cfg_path)
    batch = run_batch(config, config_dir=config_dir)

    # Two samples ran; the missing-file sample was isolated as an error.
    assert batch.n_ok == 2
    assert batch.n_failed == 1
    by_name = {s.sample_name: s for s in batch.samples}
    assert by_name["broken"].error is not None

    # Ground-truth phase is the Top-1 hit for each sample.  The FoM
    # magnitude depends on preprocessing tuning (spurious detected peaks
    # lower P_npeaks); the contract under test is "right phase ranked
    # first with a clearly above-baseline score".
    qz = by_name["qz"]
    cc = by_name["cc"]
    assert qz.top_entry_id == "SYN-QZ"
    assert qz.top_fom is not None and qz.top_fom > 0.5
    assert cc.top_entry_id == "SYN-CC"
    assert cc.top_fom is not None and cc.top_fom > 0.5
    assert qz.n_peaks >= 3
    assert qz.n_candidates > 0

    # Every requested report format was written for both good samples.
    for name in ("qz", "cc"):
        for ext in (".html", ".md", ".txt"):
            assert (batch_workspace / "out" / f"{name}{ext}").exists()

    # Summary artefacts exist and mention all samples.
    assert batch.summary_path is not None
    summary = Path(batch.summary_path).read_text(encoding="utf-8")
    assert "SYN-QZ" in summary
    assert "SYN-CC" in summary
    assert "broken" in summary
    assert "ERROR" in summary

    assert batch.json_summary_path is not None
    payload = json.loads(Path(batch.json_summary_path).read_text(encoding="utf-8"))
    assert payload["n_ok"] == 2
    assert payload["n_failed"] == 1


# --------------------------------------------------------------------------- #
# JSON end-to-end
# --------------------------------------------------------------------------- #
def test_batch_json_end_to_end(batch_workspace: Path):
    cfg_path = _write_config(batch_workspace, "config.json")
    config, config_dir = load_config(cfg_path)
    batch = run_batch(config, config_dir=config_dir)

    assert batch.n_ok == 2
    assert batch.n_failed == 1
    by_name = {s.sample_name: s for s in batch.samples}
    assert by_name["qz"].top_entry_id == "SYN-QZ"
    assert by_name["cc"].top_entry_id == "SYN-CC"
    assert (batch_workspace / "out" / "qz.html").exists()
    assert (batch_workspace / "out" / "cc.md").exists()


# --------------------------------------------------------------------------- #
# CLI entry point
# --------------------------------------------------------------------------- #
def test_batch_cli_exit_code_reflects_failures(batch_workspace: Path, capsys):
    cfg_path = _write_config(batch_workspace, "config.yaml")
    # One sample is broken -> the CLI exits 1, but still writes the summary.
    rc = batch_main([str(cfg_path)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "qz" in out
    assert "FAILED" in out
    assert (batch_workspace / "out" / "batch_summary.md").exists()


def test_batch_config_missing_db_is_config_error(tmp_path: Path):
    """A config without search.db is a caller error (exit 2), not a sample error."""
    cfg = tmp_path / "bad.yaml"
    cfg.write_text(
        "samples: [{path: x.txt}]\nsearch: {}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="db"):
        config, config_dir = load_config(cfg)
        run_batch(config, config_dir=config_dir)
