"""CLI ``userdb`` 子命令回归（v3.6.4 后续计划 ①）。

CLI 与 GUI 对话框共用 :mod:`xinmatch.core.db.user_db` 的同一批函数，本文件
钉住「无头批量导入」这条路径：list / add / remove / rebuild 全链路、
``--json`` 可解析、坏 CIF 只进 skipped 不静默吞掉。

用户库、源清单、注册表全部隔离到 tmp_path（复用 tests.user_db_support），
不触碰开发机上真实的 ``~/.xinmatch``。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.user_db_support import (
    CIF_AL2O3,
    CIF_CAF2,
    CIF_SI,
    isolate_user_data,
    write_cif,
)
from xinmatch.cli.main import main


@pytest.fixture
def user_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return isolate_user_data(tmp_path, monkeypatch)


def _json_run(capsys: pytest.CaptureFixture[str], *argv: str) -> dict:
    assert main([*argv, "--json"]) == 0
    return json.loads(capsys.readouterr().out)


def test_userdb_list_on_empty_library(capsys, user_data: Path) -> None:
    payload = _json_run(capsys, "userdb", "list")
    assert payload["action"] == "list"
    assert payload["total"] == 0
    assert payload["entries"] == []
    assert str(user_data) in payload["library_path"]


def test_userdb_add_list_remove_rebuild(
    capsys, user_data: Path, tmp_path: Path
) -> None:
    cifs = [
        write_cif(tmp_path, "si.cif", CIF_SI),
        write_cif(tmp_path, "caf2.cif", CIF_CAF2),
        write_cif(tmp_path, "al2o3.cif", CIF_AL2O3),
    ]
    added = _json_run(capsys, "userdb", "add", *(str(p) for p in cifs))
    assert added["action"] == "add"
    assert len(added["added"]) == 3
    assert added["skipped"] == []
    assert added["total"] == 3

    listed = _json_run(capsys, "userdb", "list")
    assert listed["total"] == 3
    ids = [e["entry_id"] for e in listed["entries"]]
    assert len(set(ids)) == 3
    assert all(e["n_peaks"] > 0 for e in listed["entries"])

    removed = _json_run(capsys, "userdb", "remove", ids[0])
    assert removed["action"] == "remove"
    assert removed["removed"] == [ids[0]]
    assert removed["total"] == 2

    rebuilt = _json_run(capsys, "userdb", "rebuild")
    assert rebuilt["action"] == "rebuild"
    assert rebuilt["total"] == 2


def test_userdb_bad_cif_is_reported_not_swallowed(
    capsys, user_data: Path, tmp_path: Path
) -> None:
    bad = tmp_path / "broken.cif"
    bad.write_text("this is not a CIF", encoding="utf-8")
    payload = _json_run(capsys, "userdb", "add", str(bad))
    assert payload["skipped"], "a failed parse must be visible in the result"
    assert any("broken.cif" in src for src, _reason in payload["skipped"])


def test_userdb_text_mode_prints_table(capsys, user_data: Path) -> None:
    assert main(["userdb", "list"]) == 0
    out = capsys.readouterr().out
    assert "ENTRY_ID" in out
    assert "相数=0" in out
    assert str(user_data) in out
