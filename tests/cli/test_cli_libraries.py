"""CLI tests for ``xinmatch libraries`` (v2.0.0).

The Mount → index → list → unmount flow is driven through the real CLI
(subprocess) so argument wiring, JSON output and exit codes are covered.
"""

from __future__ import annotations

import json
import os
import pathlib
import sqlite3
import subprocess
import sys

import pytest

PDF2_TABLE = (
    "CREATE TABLE phases (cod_id INTEGER, ref_id TEXT, formula TEXT, name TEXT,"
    " mineral TEXT, space_group TEXT, cell_a REAL, cell_b REAL, cell_c REAL,"
    " cell_alpha REAL, cell_beta REAL, cell_gamma REAL, n_peaks INTEGER,"
    " peaks_d TEXT, peaks_i TEXT)"
)


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


@pytest.fixture
def polyxrd_db(tmp_path):
    path = tmp_path / "downloads" / "PDF2_2004.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(PDF2_TABLE)
    conn.executemany(
        "INSERT INTO phases VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (1, "PDF2-000001", "SiO2", "Quartz", "Quartz", "P3221", 4.913, 4.913,
             5.405, 90, 90, 120, 2, "4.26,3.34", "100,80"),
            (2, "PDF2-000002", "Al2O3", "Corundum", "Corundum", "R-3c", 4.759,
             4.759, 12.99, 90, 90, 120, 2, "2.55,2.09", "100,60"),
        ],
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def isolated_env(tmp_path):
    return {
        "XINMATCH_USER_DATA": str(tmp_path / "userdata"),
        "XINMATCH_LIBRARIES_JSON": str(tmp_path / "libraries.json"),
    }


def test_list_json_contains_builtins(isolated_env):
    result = run_cli("libraries", "--json", env=isolated_env)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["action"] == "list"
    ids = {lib["id"] for lib in payload["libraries"]}
    assert {"cod_inorganics", "pdf2_2004"} <= ids
    assert all(lib["external"] is False for lib in payload["libraries"])


def test_add_builds_index_and_lists_external(polyxrd_db, isolated_env):
    added = run_cli("libraries", "--add", str(polyxrd_db), "--json", env=isolated_env)
    assert added.returncode == 0, added.stderr
    payload = json.loads(added.stdout)
    assert payload["action"] == "add"
    assert payload["library"]["index_built"] is True

    lib_id = payload["library"]["id"]
    listed = json.loads(run_cli("libraries", "--json", env=isolated_env).stdout)
    external = [lib for lib in listed["libraries"] if lib["external"]]
    assert [lib["id"] for lib in external] == [lib_id]
    assert external[0]["available"] is True
    assert external[0]["needs_index"] is False
    assert external[0]["entries"] == 2
    assert external[0]["kind"] == "polyxrd"


def test_add_without_build_then_build(polyxrd_db, isolated_env):
    added = run_cli(
        "libraries", "--add", str(polyxrd_db), "--no-build", "--json", env=isolated_env
    )
    assert added.returncode == 0, added.stderr
    payload = json.loads(added.stdout)
    assert payload["library"]["index_built"] is False
    lib_id = payload["library"]["id"]

    listed = json.loads(run_cli("libraries", "--json", env=isolated_env).stdout)
    record = next(lib for lib in listed["libraries"] if lib["id"] == lib_id)
    assert record["needs_index"] is True

    built = run_cli("libraries", "--build", lib_id, "--json", env=isolated_env)
    assert built.returncode == 0, built.stderr
    assert json.loads(built.stdout)["built"] is True

    listed = json.loads(run_cli("libraries", "--json", env=isolated_env).stdout)
    record = next(lib for lib in listed["libraries"] if lib["id"] == lib_id)
    assert record["needs_index"] is False


def test_remove(polyxrd_db, isolated_env):
    lib_id = json.loads(
        run_cli("libraries", "--add", str(polyxrd_db), "--json", env=isolated_env).stdout
    )["library"]["id"]

    removed = run_cli("libraries", "--remove", lib_id, "--json", env=isolated_env)
    assert removed.returncode == 0, removed.stderr
    assert json.loads(removed.stdout)["removed"] is True

    listed = json.loads(run_cli("libraries", "--json", env=isolated_env).stdout)
    assert all(not lib["external"] for lib in listed["libraries"])


def test_add_rejects_unknown_format(tmp_path, isolated_env):
    junk = tmp_path / "junk.sqlite"
    junk.write_bytes(b"not a database")
    result = run_cli("libraries", "--add", str(junk), env=isolated_env)
    assert result.returncode == 1
    assert "error" in result.stderr.lower()


def test_search_accepts_polyxrd_db_path(polyxrd_db, isolated_env, tmp_path):
    """``search --db`` converts a PolyXRD file on the fly (no registration)."""
    pattern = tmp_path / "pattern.txt"
    pattern.write_text(
        "2theta,I\n20.0,10\n25.0,100\n26.7,80\n35.1,20\n36.5,60\n40.0,5\n", encoding="utf-8"
    )
    result = run_cli(
        "search",
        str(pattern),
        "--db",
        str(polyxrd_db),
        "--top-n",
        "3",
        "--json",
        env=isolated_env,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    # The toy library is too small to produce a *ranked* hit (FoM thresholds),
    # but the CLI must have converted the PolyXRD file (sidecar on disk) and
    # queried it instead of failing on the foreign schema.
    assert isinstance(payload["candidates"], list)
    index_dir = pathlib.Path(isolated_env["XINMATCH_USER_DATA"]) / "indexes" / "external"
    assert list(index_dir.glob("*.db")), f"no sidecar built under {index_dir}"
