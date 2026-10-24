"""CLI tests for ``xinmatch libraries`` (v3.0.0).

v3.0.0 把参考库收敛成一种格式（列存 ``.xinDB``），所以这个子命令只剩三件事：

* ``libraries``            —— 列出内置四行（默认 COD-Inorg）+ 用户挂载；
* ``libraries --add PATH`` —— 挂载任意位置的 ``.xinDB``（**没有**建索引步骤）；
* ``libraries --remove ID``—— 取消挂载（库文件不动）。

旧的 ``--build`` / ``--no-build`` / ``index_built`` / ``needs_index`` 全随 v2
格式一起删除，这里同时断言它们**不存在**（防止悄悄复活）。测试都走真实
子进程，覆盖参数接线、JSON 输出与退出码。
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys

import numpy as np
import pytest

from tests.xindb_support import write_xindb
from xinmatch.core.model import CellParams, Entry

WL = 1.5406


def run_cli(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run the CLI with an isolated registry (UTF-8 decoded)."""
    full_env = {**os.environ, **env}
    return subprocess.run(
        [sys.executable, "-m", "xinmatch.cli.main", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        env=full_env,
    )


def _d(two_theta: float) -> float:
    return WL / (2.0 * math.sin(math.radians(two_theta / 2.0)))


def _entry(entry_id: str, peaks, formula: str, mineral: str) -> Entry:
    order = sorted(range(len(peaks)), key=lambda i: -peaks[i][1])
    return Entry(
        entry_id=entry_id,
        formula=formula,
        d_spacings=np.array([_d(peaks[i][0]) for i in order], dtype=np.float64),
        intensities=np.array([peaks[i][1] for i in order], dtype=np.float64),
        mineral_name=mineral,
        space_group="P3221",
        cell=CellParams(4.913, 4.913, 5.405, gamma=120.0),
        hkl=None,
        literature={"source": "synth"},
        quality="A",
    )


@pytest.fixture
def external_lib(tmp_path):
    """A tiny but valid v3 ``.xinDB`` library placed outside the app folder."""
    path = tmp_path / "downloads" / "MY-LIB-20260101.xinDB"
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_xindb(
        path,
        [
            _entry("EXT-QZ", [(20.0, 100), (26.6, 60), (50.1, 30)], "O2 Si", "Quartz"),
            _entry("EXT-CC", [(29.4, 100), (39.4, 50), (47.5, 25)], "C Ca O3", "Calcite"),
        ],
    )


@pytest.fixture
def isolated_env(tmp_path):
    return {
        "XINMATCH_USER_DATA": str(tmp_path / "userdata"),
        "XINMATCH_LIBRARIES_JSON": str(tmp_path / "libraries.json"),
        # 不依赖机器上那 1.8 GiB 真实库：把默认库目录指到一个空文件夹，
        # 内置行会以 available=False 出现（列表行为仍可断言）。
        "XINMATCH_XINDB_DIR": str(tmp_path / "no-libs-here"),
    }


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------
def test_list_json_contains_builtins(isolated_env):
    result = run_cli("libraries", "--json", env=isolated_env)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["action"] == "list"

    ids = {lib["id"] for lib in payload["libraries"]}
    assert "xindb_cod_inorg" in ids  # 默认库永远占一行
    defaults = [lib for lib in payload["libraries"] if lib["default"]]
    assert [lib["id"] for lib in defaults] == ["xindb_cod_inorg"]
    assert all(lib["kind"] == "xindb" for lib in payload["libraries"])
    assert all(lib["external"] is False for lib in payload["libraries"])


def test_list_text_output_mentions_default(isolated_env):
    result = run_cli("libraries", env=isolated_env)
    assert result.returncode == 0, result.stderr
    assert "xindb_cod_inorg" in result.stdout
    assert "默认" in result.stdout
    # 文本模式只打印表格（+ 动作提示），不再被 _emit 重复一遍
    # "action: list / libraries: N item(s)" 摘要。
    assert "item(s)" not in result.stdout
    assert "action: list" not in result.stdout


def test_add_text_mode_prints_mounted_id(external_lib, isolated_env):
    result = run_cli("libraries", "--add", str(external_lib), env=isolated_env)
    assert result.returncode == 0, result.stderr
    assert "已挂载" in result.stdout
    assert "ext_" in result.stdout


def test_add_and_remove_are_mutually_exclusive(external_lib, isolated_env):
    result = run_cli(
        "libraries", "--add", str(external_lib), "--remove", "ext_x",
        env=isolated_env,
    )
    assert result.returncode == 2  # argparse usage error
    assert "not allowed with" in result.stderr


# ---------------------------------------------------------------------------
# add / remove
# ---------------------------------------------------------------------------
def test_add_mounts_xindb_and_lists_external(external_lib, isolated_env):
    added = run_cli("libraries", "--add", str(external_lib), "--json", env=isolated_env)
    assert added.returncode == 0, added.stderr
    payload = json.loads(added.stdout)
    assert payload["action"] == "add"
    lib_id = payload["library"]["id"]
    assert lib_id.startswith("ext_")

    listed = json.loads(run_cli("libraries", "--json", env=isolated_env).stdout)
    external = [lib for lib in listed["libraries"] if lib["external"]]
    assert [lib["id"] for lib in external] == [lib_id]
    assert external[0]["available"] is True
    assert external[0]["entries"] == 2
    assert external[0]["kind"] == "xindb"


def test_add_with_label(external_lib, isolated_env):
    added = run_cli(
        "libraries", "--add", str(external_lib), "--label", "我的库", "--json",
        env=isolated_env,
    )
    assert added.returncode == 0, added.stderr
    assert json.loads(added.stdout)["library"]["label"] == "我的库"


def test_add_is_idempotent(external_lib, isolated_env):
    first = json.loads(
        run_cli("libraries", "--add", str(external_lib), "--json", env=isolated_env).stdout
    )["library"]["id"]
    second = json.loads(
        run_cli("libraries", "--add", str(external_lib), "--json", env=isolated_env).stdout
    )["library"]["id"]
    assert first == second
    listed = json.loads(run_cli("libraries", "--json", env=isolated_env).stdout)
    assert len([lib for lib in listed["libraries"] if lib["external"]]) == 1


def test_remove_keeps_the_file(external_lib, isolated_env):
    lib_id = json.loads(
        run_cli("libraries", "--add", str(external_lib), "--json", env=isolated_env).stdout
    )["library"]["id"]

    removed = run_cli("libraries", "--remove", lib_id, "--json", env=isolated_env)
    assert removed.returncode == 0, removed.stderr
    assert json.loads(removed.stdout)["removed"] is True

    listed = json.loads(run_cli("libraries", "--json", env=isolated_env).stdout)
    assert all(not lib["external"] for lib in listed["libraries"])
    assert external_lib.is_file()  # 只改注册表，绝不删用户的库


def test_remove_unknown_id_reports_false(isolated_env):
    result = run_cli("libraries", "--remove", "ext_deadbeef0000", "--json", env=isolated_env)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["removed"] is False


# ---------------------------------------------------------------------------
# rejection of legacy formats / missing files
# ---------------------------------------------------------------------------
def test_add_rejects_legacy_sqlite(tmp_path, isolated_env):
    junk = tmp_path / "cod_inorganics.db"
    junk.write_bytes(b"not a xindb")
    result = run_cli("libraries", "--add", str(junk), env=isolated_env)
    assert result.returncode == 1
    assert "error" in result.stderr.lower()
    assert ".xinDB" in result.stderr


def test_add_rejects_corrupt_xindb(tmp_path, isolated_env):
    bad = tmp_path / "BROKEN-20260101.xinDB"
    bad.write_bytes(b"not a database at all")
    result = run_cli("libraries", "--add", str(bad), env=isolated_env)
    assert result.returncode == 1
    assert "error" in result.stderr.lower()


def test_add_rejects_missing_file(tmp_path, isolated_env):
    result = run_cli(
        "libraries", "--add", str(tmp_path / "nope.xinDB"), env=isolated_env
    )
    assert result.returncode == 1
    assert "error" in result.stderr.lower()


# ---------------------------------------------------------------------------
# v2 knobs must be gone
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("flag", ["--build", "--no-build", "--force"])
def test_legacy_build_flags_are_gone(flag, external_lib, isolated_env):
    """v2 的"建转换索引"参数已删除；argparse 必须直接拒绝。"""
    result = run_cli("libraries", flag, str(external_lib), env=isolated_env)
    assert result.returncode == 2  # argparse usage error
    assert "unrecognized" in result.stderr.lower()


# ---------------------------------------------------------------------------
# search --db <any .xinDB>
# ---------------------------------------------------------------------------
def test_search_accepts_xindb_path(external_lib, isolated_env, tmp_path):
    """``search --db`` 直接打开任意 ``.xinDB``（无需先挂载）。"""
    pattern = tmp_path / "pattern.txt"
    pattern.write_text(
        "2theta,I\n20.0,10\n25.0,100\n26.6,80\n35.1,20\n36.5,60\n40.0,5\n",
        encoding="utf-8",
    )
    result = run_cli(
        "search", str(pattern), "--db", str(external_lib), "--top-n", "3", "--json",
        env=isolated_env,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert isinstance(payload["candidates"], list)
    assert "xinDB" not in result.stderr  # 没有"格式不支持"的告警
