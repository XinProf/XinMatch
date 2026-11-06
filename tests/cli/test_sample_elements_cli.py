# ruff: noqa: F811
# 下面从 test_cli.py 显式 import 的 pytest fixture 会与测试函数同名参数
# 「重定义」——这是 pytest 注入 fixture 的标准写法，不是真的覆盖。
"""CLI ``--sample-elements`` 端到端验收（基准报告 §25）。

GUI 已经把「只允许这几个元素」产品化成一行输入框（§24），CLI 原来只能
手写 113 个 ``EXCLUDE`` 键值的 ``--restraints`` JSON。本组测试固定：

* 快捷参数确实把补集约束送进检索（含 C/Ca 的 DECOY 被挡，Si/O 的 TRUTH 保留）；
* 与 ``--restraints`` 互斥、FPFM 模式明确报错（不静默忽略）；
* 未知符号 / 化学式 / 空输入给出中文可操作提示；
* 默认输出逐项不变（不给参数时结果 JSON 不新增字段，便于脚本比对基线）。
"""

from __future__ import annotations

import json
from pathlib import Path

# 复用 test_cli.py 的 fixture 与 subprocess helper：这些是 pytest fixture
# 函数，显式 import 后本模块可直接注入（tests/cli 下没有 conftest.py）。
from tests.cli.test_cli import db_path, pattern_file, run_cli  # noqa: F401


class TestSearchSampleElements:
    def test_complement_filters_decoy_and_echoes_input(
        self, pattern_file: Path, db_path: Path
    ) -> None:
        result = run_cli(
            "search", str(pattern_file), "--db", str(db_path),
            "--sample-elements", "Si O", "--top-n", "5", "--json",
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        ids = [c["entry_id"] for c in data["candidates"]]
        assert "TRUTH" in ids
        assert "DECOY" not in ids  # 含 C / Ca，均不在样品元素里
        assert data["sample_elements"] == "Si O"

    def test_case_insensitive_and_mixed_separators(
        self, pattern_file: Path, db_path: Path
    ) -> None:
        result = run_cli(
            "search", str(pattern_file), "--db", str(db_path),
            "--sample-elements", "si、O", "--top-n", "5", "--json",
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert "TRUTH" in [c["entry_id"] for c in data["candidates"]]

    def test_default_output_has_no_extra_key(
        self, pattern_file: Path, db_path: Path
    ) -> None:
        """不给快捷参数时结果 JSON 不新增字段 —— 保护既有脚本基线。"""
        result = run_cli(
            "search", str(pattern_file), "--db", str(db_path),
            "--top-n", "5", "--json",
        )
        assert result.returncode == 0, result.stderr
        assert "sample_elements" not in json.loads(result.stdout)

    def test_mutually_exclusive_with_restraints(
        self, pattern_file: Path, db_path: Path
    ) -> None:
        restraints = json.dumps({"elements": {"Si": "green"}})
        result = run_cli(
            "search", str(pattern_file), "--db", str(db_path),
            "--restraints", restraints,
            "--sample-elements", "Si O", "--json",
        )
        assert result.returncode == 2
        assert "not allowed with argument" in result.stderr

    def test_unknown_symbol_friendly_error(
        self, pattern_file: Path, db_path: Path
    ) -> None:
        result = run_cli(
            "search", str(pattern_file), "--db", str(db_path),
            "--sample-elements", "Zn Xx", "--json",
        )
        assert result.returncode == 1
        assert "无法识别的元素符号" in result.stderr
        assert "Xx" in result.stderr
        assert not result.stdout.strip()

    def test_formula_input_friendly_error(
        self, pattern_file: Path, db_path: Path
    ) -> None:
        result = run_cli(
            "search", str(pattern_file), "--db", str(db_path),
            "--sample-elements", "Al2O3", "--json",
        )
        assert result.returncode == 1
        assert "不要填化学式" in result.stderr

    def test_empty_input_friendly_error(
        self, pattern_file: Path, db_path: Path
    ) -> None:
        result = run_cli(
            "search", str(pattern_file), "--db", str(db_path),
            "--sample-elements", "   ", "--json",
        )
        assert result.returncode == 1
        assert "样品元素为空" in result.stderr

    def test_fpfm_rejects_instead_of_silently_ignoring(
        self, pattern_file: Path, db_path: Path
    ) -> None:
        """FPFM 不接元素约束：必须报错，不能像 --restraints 那样静默忽略。"""
        result = run_cli(
            "search", str(pattern_file), "--db", str(db_path),
            "--mode", "fpfm", "--sample-elements", "Si O", "--json",
        )
        assert result.returncode == 1
        assert "FPFM" in result.stderr
        assert "--sample-elements" in result.stderr

    def test_help_documents_shortcut(
        self, pattern_file: Path, db_path: Path
    ) -> None:
        result = run_cli("search", "--help")
        assert result.returncode == 0
        assert "--sample-elements" in result.stdout
        assert "--restraints" in result.stdout


class TestRunSampleElements:
    def test_run_accepts_and_echoes(
        self, pattern_file: Path, db_path: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "report.html"
        result = run_cli(
            "run", str(pattern_file), "--db", str(db_path),
            "--output", str(out), "--top-n", "5",
            "--sample-elements", "Si O", "--json",
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["top_candidate"] == "TRUTH"
        assert data["sample_elements"] == "Si O"
        assert out.is_file()

    def test_run_mutually_exclusive_with_restraints(
        self, pattern_file: Path, db_path: Path, tmp_path: Path
    ) -> None:
        result = run_cli(
            "run", str(pattern_file), "--db", str(db_path),
            "--output", str(tmp_path / "report.html"),
            "--restraints", '{"elements": {"Si": "green"}}',
            "--sample-elements", "Si O", "--json",
        )
        assert result.returncode == 2
        assert "not allowed with argument" in result.stderr
