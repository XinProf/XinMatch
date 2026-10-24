"""Tests for the XinMatch CLI (T14.1) and top-level Python API (T14.2).

Tests use synthetic pattern data and a small on-disk reference database;
no real COD database is required.  The CLI is invoked via
``subprocess.run`` so the entry point declared in ``pyproject.toml``
(``xinmatch.cli.main:main``) is exercised end-to-end.
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

# Cu Kα1 wavelength.
WL = 1.5406


def _d_from_two_theta(two_theta: float, wavelength: float = WL) -> float:
    return wavelength / (2.0 * math.sin(math.radians(two_theta / 2.0)))


# ---------------------------------------------------------------------------
# Synthetic pattern file
# ---------------------------------------------------------------------------
@pytest.fixture
def pattern_file(tmp_path: Path) -> Path:
    """A 2-column ASCII pattern with four strong peaks."""
    two_thetas = np.linspace(5.0, 60.0, 551)
    intensity = np.zeros_like(two_thetas)
    # Place Gaussian peaks at known 2θ positions.
    peak_positions = [15.0, 25.0, 35.0, 45.0]
    for pos in peak_positions:
        intensity += 1000.0 * np.exp(-((two_thetas - pos) ** 2) / (2 * 0.15**2))
    # Add a small baseline so background subtraction doesn't zero everything.
    intensity += 20.0

    path = tmp_path / "sample.xy"
    lines = [f"{t:.6f}  {i:.4f}" for t, i in zip(two_thetas, intensity, strict=True)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Synthetic reference database on disk
# ---------------------------------------------------------------------------
@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """A small SQLite reference DB whose top entry matches the pattern peaks."""
    # Ground-truth entry: d-spacings exactly at the experimental peak 2θ.
    exp_tt = [15.0, 25.0, 35.0, 45.0]
    exp_int = [1000.0, 800.0, 600.0, 400.0]
    order = sorted(range(len(exp_tt)), key=lambda i: -exp_int[i])
    ds = [_d_from_two_theta(exp_tt[i]) for i in order]
    ints = [exp_int[i] for i in order]

    truth = Entry(
        entry_id="TRUTH",
        formula="Si O2",
        d_spacings=np.array(ds, dtype=np.float64),
        intensities=np.array(ints, dtype=np.float64),
        mineral_name="Quartz",
        cell=CellParams(4.914, 4.914, 5.405, gamma=120.0),
        space_group="P3221",
        hkl=[(1, 0, 0), (1, 0, 1), (1, 1, 0), (1, 1, 1)],
        literature={"author": "tester", "year": 2000},
        quality="A",
    )

    # A decoy entry with shifted peaks.
    decoy_tt = [15.5, 25.5, 35.5, 45.5]
    decoy_int = [500.0, 400.0, 300.0, 200.0]
    order2 = sorted(range(len(decoy_tt)), key=lambda i: -decoy_int[i])
    decoy = Entry(
        entry_id="DECOY",
        formula="C Ca O3",
        d_spacings=np.array([_d_from_two_theta(decoy_tt[i]) for i in order2]),
        intensities=np.array([decoy_int[i] for i in order2]),
        mineral_name="Calcite",
        space_group="R-3c",
        quality="B",
    )

    path = tmp_path / "ref.xinDB"
    # v3.0.0: 参考库只能是列存 .xinDB
    return write_xindb(path, [truth, decoy])


# ---------------------------------------------------------------------------
# CLI invocation helper
# ---------------------------------------------------------------------------
def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the XinMatch CLI as a subprocess and return the result.

    The CLI reconfigures its own stdio to UTF-8 (``_configure_stdio``), so the
    helper must decode UTF-8 explicitly: with ``text=True`` alone Python uses
    the *locale* codec, which is GBK on a default zh-CN Windows install and
    blows up on the Chinese help text (``UnicodeDecodeError: 'gbk' codec ...``).
    """
    return subprocess.run(
        [sys.executable, "-m", "xinmatch.cli.main", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


# ---------------------------------------------------------------------------
# Tests: --help
# ---------------------------------------------------------------------------
class TestHelp:
    def test_top_level_help(self) -> None:
        result = run_cli("--help")
        assert result.returncode == 0
        assert "XinMatch" in result.stdout
        # All six subcommands must be listed.
        for sub in ("import", "process", "search", "quantify", "report", "run"):
            assert sub in result.stdout

    @pytest.mark.parametrize(
        "sub", ["import", "process", "search", "quantify", "report", "run"]
    )
    def test_subcommand_help(self, sub: str) -> None:
        result = run_cli(sub, "--help")
        assert result.returncode == 0
        assert "--json" in result.stdout


# ---------------------------------------------------------------------------
# Tests: import
# ---------------------------------------------------------------------------
class TestImport:
    def test_import_human_readable(self, pattern_file: Path) -> None:
        result = run_cli("import", str(pattern_file))
        assert result.returncode == 0
        assert "n_points" in result.stdout
        assert "wavelength" in result.stdout

    def test_import_json(self, pattern_file: Path) -> None:
        result = run_cli("import", str(pattern_file), "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["n_points"] == 551
        assert data["wavelength"] == pytest.approx(WL)
        assert data["two_theta_start"] == pytest.approx(5.0)
        assert data["two_theta_end"] == pytest.approx(60.0)

    def test_import_wavelength_override(self, pattern_file: Path) -> None:
        result = run_cli("import", str(pattern_file), "--wavelength", "1.7889", "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["wavelength"] == pytest.approx(1.7889)

    def test_import_missing_file_friendly_error(self, tmp_path: Path) -> None:
        """缺文件时给中文可读提示（核心层异常消息只有路径）。"""
        result = run_cli("import", str(tmp_path / "nope.xy"))
        assert result.returncode == 1
        assert not result.stdout.strip()
        assert "文件不存在" in result.stderr
        assert "nope.xy" in result.stderr


# ---------------------------------------------------------------------------
# Tests: process
# ---------------------------------------------------------------------------
class TestProcess:
    def test_process_runs(self, pattern_file: Path) -> None:
        result = run_cli("process", str(pattern_file), "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["n_points"] == 551
        assert data["n_peaks"] >= 1

    def test_process_flags(self, pattern_file: Path) -> None:
        result = run_cli(
            "process", str(pattern_file),
            "--no-smooth", "--no-background", "--no-alpha2",
            "--json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["n_peaks"] >= 1


# ---------------------------------------------------------------------------
# Tests: search
# ---------------------------------------------------------------------------
class TestSearch:
    def test_search_finds_truth(self, pattern_file: Path, db_path: Path) -> None:
        result = run_cli(
            "search", str(pattern_file), "--db", str(db_path),
            "--top-n", "5", "--json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["n_peaks"] >= 1
        assert data["n_candidates"] >= 1
        ids = [c["entry_id"] for c in data["candidates"]]
        assert "TRUTH" in ids

    def test_search_with_restraints(self, pattern_file: Path, db_path: Path) -> None:
        restraints = json.dumps({"elements": {"Si": "green"}})
        result = run_cli(
            "search", str(pattern_file), "--db", str(db_path),
            "--restraints", restraints, "--top-n", "5", "--json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        ids = [c["entry_id"] for c in data["candidates"]]
        # TRUTH contains Si; DECOY does not.
        assert "TRUTH" in ids
        assert "DECOY" not in ids


# ---------------------------------------------------------------------------
# Tests: quantify
# ---------------------------------------------------------------------------
class TestQuantify:
    def test_quantify_default_rir(self) -> None:
        phases = json.dumps({"Quartz": 1000.0, "Calcite": 500.0})
        result = run_cli("quantify", "--phases", phases, "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        wf = data["weight_fractions"]
        assert set(wf) == {"Quartz", "Calcite"}
        assert wf["Quartz"] == pytest.approx(2.0 / 3.0, rel=1e-6)
        assert wf["Calcite"] == pytest.approx(1.0 / 3.0, rel=1e-6)
        assert abs(sum(wf.values()) - 1.0) < 1e-9

    def test_quantify_explicit_rir(self) -> None:
        phases = json.dumps({"A": 100.0, "B": 100.0})
        rir = json.dumps({"A": 2.0, "B": 1.0})
        result = run_cli("quantify", "--phases", phases, "--rir", rir, "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        wf = data["weight_fractions"]
        # I/RIR ratios: A=50, B=100 → A=1/3, B=2/3
        assert wf["A"] == pytest.approx(1.0 / 3.0, rel=1e-6)
        assert wf["B"] == pytest.approx(2.0 / 3.0, rel=1e-6)


# ---------------------------------------------------------------------------
# Tests: report
# ---------------------------------------------------------------------------
class TestReport:
    def test_report_from_pattern(self, pattern_file: Path, tmp_path: Path) -> None:
        out = tmp_path / "report.html"
        result = run_cli(
            "report", str(pattern_file), "--output", str(out), "--json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["format"] == "html"
        assert Path(data["output"]).exists()
        assert data["bytes"] > 0

    def test_report_markdown(self, pattern_file: Path, tmp_path: Path) -> None:
        out = tmp_path / "report.md"
        result = run_cli(
            "report", str(pattern_file), "--output", str(out),
            "--format", "md", "--json",
        )
        assert result.returncode == 0
        content = out.read_text(encoding="utf-8")
        assert "# XinMatch" in content

    def test_report_default_output_uses_format_suffix(self, pattern_file: Path) -> None:
        """省略 --output 时扩展名必须跟随 --format（旧实现永远是 .html）。"""
        result = run_cli("report", str(pattern_file), "--format", "md", "--json")
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["output"].endswith(".md")
        assert "# XinMatch" in Path(data["output"]).read_text(encoding="utf-8")

    def test_report_input_report_default_output(self, tmp_path: Path) -> None:
        """``report --input-report X`` 省略 -o 时不得再崩在 Path(None) 上。"""
        from xinmatch.core.report.report_model import Report, SampleInfo

        src = tmp_path / "report_in.json"
        Report.now(sample_info=SampleInfo(sample_name="t", wavelength=WL)).to_json(src)
        result = run_cli("report", "--input-report", str(src), "--json")
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["output"].endswith("-report.html")
        assert Path(data["output"]).is_file()
        assert data["bytes"] > 0

    def test_report_without_input_reports_friendly_error(self) -> None:
        result = run_cli("report")
        assert result.returncode == 1
        assert not result.stdout.strip()
        assert "pattern_file" in result.stderr or "input-report" in result.stderr

    def test_report_rejects_non_report_json(self, tmp_path: Path) -> None:
        """检索结果摘要（search --json）不是报告，必须报错而不是静默出空报告。"""
        junk = tmp_path / "search_result.json"
        junk.write_text(json.dumps({"n_candidates": 0, "candidates": []}),
                        encoding="utf-8")
        result = run_cli("report", "--input-report", str(junk))
        assert result.returncode == 1
        assert "报告" in result.stderr
        assert not junk.with_name("search_result-report.html").exists()

    def test_report_input_report_missing_file(self, tmp_path: Path) -> None:
        result = run_cli("report", "--input-report", str(tmp_path / "nope.json"))
        assert result.returncode == 1
        assert "not found" in result.stderr


# ---------------------------------------------------------------------------
# Tests: batch (T14.3) — --json 的 stdout 必须是完整可解析的 JSON
# ---------------------------------------------------------------------------
class TestBatch:
    def _write_config(
        self, tmp_path: Path, pattern_file: Path, db_path: Path
    ) -> Path:
        out_dir = tmp_path / "batch_out"
        cfg = tmp_path / "batch.yaml"
        cfg.write_text(
            "samples:\n"
            "  - name: s1\n"
            f"    path: {pattern_file.as_posix()}\n"
            "search:\n"
            f"  db: {db_path.as_posix()}\n"
            "  mode: peaks\n"
            "  top_n: 5\n"
            "output:\n"
            f"  dir: {out_dir.as_posix()}\n"
            "  formats: [md, txt]\n",
            encoding="utf-8",
        )
        return cfg

    def test_batch_json_stdout_is_pure_json(
        self, pattern_file: Path, db_path: Path, tmp_path: Path
    ) -> None:
        """回归：core.batch 的进度行曾混进 stdout，导致 json.loads 失败。"""
        cfg = self._write_config(tmp_path, pattern_file, db_path)
        result = run_cli("batch", str(cfg), "--json")
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)  # 整个 stdout 必须是一个 JSON 文档
        assert data["n_ok"] == 1
        assert data["n_failed"] == 0
        assert data["samples"][0]["top_entry_id"] == "TRUTH"
        assert Path(data["summary_path"]).is_file()
        # 进度信息改道 stderr，人类仍然看得到。
        assert "[s1] running" in result.stderr
        assert "OK:" in result.stderr

    def test_batch_text_keeps_progress_on_stdout(
        self, pattern_file: Path, db_path: Path, tmp_path: Path
    ) -> None:
        cfg = self._write_config(tmp_path, pattern_file, db_path)
        result = run_cli("batch", str(cfg))
        assert result.returncode == 0, result.stderr
        assert "[s1] running" in result.stdout
        assert "n_ok: 1" in result.stdout


# ---------------------------------------------------------------------------
# Tests: run (one-shot pipeline)
# ---------------------------------------------------------------------------
class TestRun:
    def test_run_full_pipeline(
        self, pattern_file: Path, db_path: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "full_report.html"
        result = run_cli(
            "run", str(pattern_file),
            "--db", str(db_path),
            "--output", str(out),
            "--top-n", "5",
            "--json",
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["n_peaks"] >= 1
        assert data["n_candidates"] >= 1
        assert data["top_candidate"] == "TRUTH"
        assert data["weight_fractions"]  # non-empty
        assert Path(data["report"]).exists()

    def test_run_text_format(
        self, pattern_file: Path, db_path: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "full_report.txt"
        result = run_cli(
            "run", str(pattern_file),
            "--db", str(db_path),
            "--output", str(out),
            "--format", "text",
            "--json",
        )
        assert result.returncode == 0, result.stderr
        content = out.read_text(encoding="utf-8")
        assert "XinMatch" in content
        assert "Peak List" in content


# ---------------------------------------------------------------------------
# Tests: top-level Python API (T14.2)
# ---------------------------------------------------------------------------
class TestPythonAPI:
    def test_version_defined(self) -> None:
        import xinmatch

        assert isinstance(xinmatch.__version__, str)
        assert xinmatch.__version__

    def test_symbol_exports(self) -> None:
        import xinmatch

        for name in (
            "Pattern", "Peak", "Entry", "CellParams", "Phase",
            "Restraints", "Project", "load_pattern", "preprocess",
            "search_match", "quantify", "generate_report",
            "load_and_preprocess", "identify_phase", "full_analysis",
        ):
            assert hasattr(xinmatch, name), name

    def test_load_and_preprocess(self, pattern_file: Path) -> None:
        from xinmatch import load_and_preprocess

        pattern = load_and_preprocess(str(pattern_file))
        assert len(pattern) == 551

    def test_identify_phase(self, pattern_file: Path, db_path: Path) -> None:
        from xinmatch import identify_phase, load_pattern

        pattern = load_pattern(str(pattern_file))
        candidates = identify_phase(pattern, str(db_path), top_n=5)
        assert candidates
        assert candidates[0].entry.entry_id == "TRUTH"

    def test_full_analysis(
        self, pattern_file: Path, db_path: Path, tmp_path: Path
    ) -> None:
        from xinmatch import full_analysis

        out = tmp_path / "analysis.html"
        result = full_analysis(str(pattern_file), str(db_path), output_report=str(out))
        assert result["n_peaks"] >= 1
        assert result["n_candidates"] >= 1
        assert result["candidates"][0]["entry_id"] == "TRUTH"
        assert result["report_file"] == str(out)
        assert Path(out).exists()
