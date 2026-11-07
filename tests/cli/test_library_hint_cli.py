# ruff: noqa: F811
# 从 test_cli.py 显式 import 的 pytest fixture 会与同名参数「重定义」——
# 这是 pytest 注入 fixture 的标准写法，不是真的覆盖。
"""CLI 大库元素约束引导（基准报告 §27）。

§24 的「挂大库建议填样品元素」原本只在 GUI。CLI 侧补齐同一条非阻塞引导：
阈值与判据共用 core，相数走 ``XinDBReader.entry_count()``（读 meta，O(1)），
提示只写 **stderr**，``--json`` 的 stdout 必须永远是一个完整 JSON 文档。

固定四件事：
1. 只有「大库 + 未设元素约束 + peaks 模式」才提示；
2. 已有约束、FPFM、``--no-library-hint`` 三种情况不打扰；
3. 提示不污染 stdout，也不影响返回码；
4. ``search`` 与 ``run`` 行为一致，读不到相数时静默降级。
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.cli.test_cli import db_path, pattern_file, run_cli  # noqa: F401
from xinmatch.cli.main import (
    _emit_large_library_hint,
    _large_library_hint_text,
    build_parser,
    cmd_run,
    cmd_search,
    main,
)
from xinmatch.core.db.reader_v3 import XinDBReader

BIG = 532_038  # COD-Full
SAMPLE = "Si O"


def _parse(*argv: str):
    return build_parser().parse_args([*argv])


def _big_library(monkeypatch) -> None:
    """把小测试库伪装成大库：只改 meta 读数，不碰峰数据。"""
    monkeypatch.setattr(XinDBReader, "entry_count", lambda self: BIG)


# ---------------------------------------------------------------------------
# 纯函数：抑制条件矩阵
# ---------------------------------------------------------------------------

class TestHintText:
    def test_large_library_gets_actionable_hint(self):
        text = _large_library_hint_text(
            BIG, has_element_restraints=False, fpfm=False, disabled=False
        )
        assert text is not None
        assert "532,038 相" in text
        assert "--sample-elements" in text
        assert "7/13 → 12/13" in text
        assert "--no-library-hint" in text

    @pytest.mark.parametrize("count", [None, 0, 78_035, 199_999, "532038"])
    def test_small_or_dirty_counts_are_silent(self, count):
        assert _large_library_hint_text(
            count, has_element_restraints=False, fpfm=False, disabled=False
        ) is None

    def test_existing_element_restraints_suppress(self):
        assert _large_library_hint_text(
            BIG, has_element_restraints=True, fpfm=False, disabled=False
        ) is None

    def test_fpfm_suppress(self):
        """FPFM 不接元素约束，给建议会把用户导向必然失败的命令。"""
        assert _large_library_hint_text(
            BIG, has_element_restraints=False, fpfm=True, disabled=False
        ) is None

    def test_explicit_switch_suppress(self):
        assert _large_library_hint_text(
            BIG, has_element_restraints=False, fpfm=False, disabled=True
        ) is None


# ---------------------------------------------------------------------------
# _emit：只写 stderr、脏 reader 静默降级
# ---------------------------------------------------------------------------

class TestEmit:
    def test_writes_stderr_only(self, capsys):
        _emit_large_library_hint(
            SimpleNamespace(entry_count=lambda: BIG), None,
            fpfm=False, disabled=False,
        )
        out, err = capsys.readouterr()
        assert out == ""
        assert "[提示]" in err

    def test_element_restraints_are_checked_not_just_presence(self, capsys):
        from xinmatch.core.model import Restraints

        only_crystal = Restraints(crystal_system="cubic")
        _emit_large_library_hint(
            SimpleNamespace(entry_count=lambda: BIG), only_crystal,
            fpfm=False, disabled=False,
        )
        assert "[提示]" in capsys.readouterr().err  # 没有元素约束，仍应提示

        with_elements = Restraints()
        with_elements.exclude("C")
        _emit_large_library_hint(
            SimpleNamespace(entry_count=lambda: BIG), with_elements,
            fpfm=False, disabled=False,
        )
        assert "[提示]" not in capsys.readouterr().err

    @pytest.mark.parametrize(
        "reader",
        [
            SimpleNamespace(),                       # 没有 entry_count
            SimpleNamespace(entry_count=lambda: "bad"),  # 脏值
            SimpleNamespace(entry_count=None),       # 不可调用
        ],
    )
    def test_unreadable_count_degrades_silently(self, capsys, reader):
        _emit_large_library_hint(reader, None, fpfm=False, disabled=False)
        out, err = capsys.readouterr()
        assert out == "" and err == ""


# ---------------------------------------------------------------------------
# 端到端：search / run 的提示与 --json 纯净性
# ---------------------------------------------------------------------------

class TestSearchHint:
    def test_small_library_end_to_end_is_silent(
        self, pattern_file: Path, db_path: Path
    ) -> None:
        result = run_cli(
            "search", str(pattern_file), "--db", str(db_path),
            "--top-n", "5", "--json",
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["n_candidates"] >= 1
        assert "[提示]" not in result.stderr

    def test_large_library_hint_goes_to_stderr(
        self, monkeypatch, capsys, pattern_file: Path, db_path: Path
    ) -> None:
        _big_library(monkeypatch)
        args = _parse("search", str(pattern_file), "--db", str(db_path),
                      "--top-n", "5")
        result = cmd_search(args)
        out, err = capsys.readouterr()
        assert result["n_candidates"] >= 1
        assert out == ""
        assert "[提示] 当前库含 532,038 相" in err

    def test_json_stdout_stays_pure_even_with_hint(
        self, monkeypatch, capsys, pattern_file: Path, db_path: Path
    ) -> None:
        """最要紧的一条：stderr 提示不能让 --json 的 stdout 变得不可解析。"""
        _big_library(monkeypatch)
        rc = main([
            "search", str(pattern_file), "--db", str(db_path),
            "--top-n", "5", "--json",
        ])
        out, err = capsys.readouterr()
        assert rc == 0
        data = json.loads(out)  # 整个 stdout 必须是一个 JSON 文档
        assert data["n_candidates"] >= 1
        assert "[提示]" not in out
        assert "[提示]" in err

    def test_sample_elements_suppresses_hint(
        self, monkeypatch, capsys, pattern_file: Path, db_path: Path
    ) -> None:
        _big_library(monkeypatch)
        args = _parse("search", str(pattern_file), "--db", str(db_path),
                      "--sample-elements", SAMPLE, "--top-n", "5")
        cmd_search(args)
        assert "[提示]" not in capsys.readouterr().err

    def test_restraints_with_elements_suppresses_hint(
        self, monkeypatch, capsys, pattern_file: Path, db_path: Path
    ) -> None:
        _big_library(monkeypatch)
        raw = json.dumps({"elements": {"Si": "green"}})
        args = _parse("search", str(pattern_file), "--db", str(db_path),
                      "--restraints", raw, "--top-n", "5")
        cmd_search(args)
        assert "[提示]" not in capsys.readouterr().err

    def test_restraints_without_elements_still_hints(
        self, monkeypatch, capsys, pattern_file: Path, db_path: Path
    ) -> None:
        """判据是「实际有没有元素约束」，不是「有没有 --restraints 参数」。"""
        _big_library(monkeypatch)
        raw = json.dumps({"crystal_system": "cubic"})
        args = _parse("search", str(pattern_file), "--db", str(db_path),
                      "--restraints", raw, "--top-n", "5")
        cmd_search(args)
        assert "[提示]" in capsys.readouterr().err

    def test_no_library_hint_flag_suppresses(
        self, monkeypatch, capsys, pattern_file: Path, db_path: Path
    ) -> None:
        _big_library(monkeypatch)
        args = _parse("search", str(pattern_file), "--db", str(db_path),
                      "--no-library-hint", "--top-n", "5")
        cmd_search(args)
        assert "[提示]" not in capsys.readouterr().err

    def test_help_documents_the_switch(self) -> None:
        for sub in ("search", "run"):
            result = run_cli(sub, "--help")
            assert result.returncode == 0
            assert "--no-library-hint" in result.stdout


class TestRunHint:
    def test_run_shows_same_hint(
        self, monkeypatch, capsys, pattern_file: Path,
        db_path: Path, tmp_path: Path
    ) -> None:
        _big_library(monkeypatch)
        out = tmp_path / "report.html"
        args = _parse("run", str(pattern_file), "--db", str(db_path),
                      "--output", str(out), "--top-n", "5")
        result = cmd_run(args)
        stdout, stderr = capsys.readouterr()
        assert result["n_candidates"] >= 1
        assert out.is_file()
        assert stdout == ""
        assert "[提示] 当前库含 532,038 相" in stderr

    def test_run_switch_suppresses(
        self, monkeypatch, capsys, pattern_file: Path,
        db_path: Path, tmp_path: Path
    ) -> None:
        _big_library(monkeypatch)
        args = _parse("run", str(pattern_file), "--db", str(db_path),
                      "--output", str(tmp_path / "report.html"),
                      "--no-library-hint", "--top-n", "5")
        cmd_run(args)
        assert "[提示]" not in capsys.readouterr().err
