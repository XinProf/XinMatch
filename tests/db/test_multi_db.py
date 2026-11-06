"""v3 ``.xinDB`` 库注册表 / 默认库解析 (XinMatch v3.0.0)
========================================================

v3.0.0 把可检索的参考库收敛成一种格式（列存 ``.xinDB``），默认库是
**COD-Inorg**。这里钉住五条：

1. **默认库 = COD-Inorg** —— ``resolve_default()`` 指向它，且它排在列表第一位；
2. **快照取最新** —— 同前缀多个日期文件时取字串序最大；
3. **内置行只在文件存在时可点** —— 缺文件不许抛异常，要给出可读原因；
4. **``open_library`` 返回 reader** —— 不是 sqlite3.Connection（v2 行表已删）；
5. **旧格式一律拒绝** —— ``.sqlite`` / ``.db`` 既不能挂载也不能直接打开。
"""
from __future__ import annotations

import logging
import os
import sqlite3

import pytest

from xinmatch.core.db import multi_db


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """隔离：库搜索目录 / 用户数据目录 / 注册表全部指到临时目录。

    同时把内置候选目录（``<repo>/data`` 与 ``../XinMatch-DataBase/data``）也
    指到临时目录，否则"空库目录"用例在本机真实库存在时会失去隔离性。
    """
    libs = tmp_path / "libs"
    libs.mkdir()
    monkeypatch.setenv("XINMATCH_XINDB_DIR", str(libs))
    monkeypatch.setenv("XINMATCH_USER_DATA", str(tmp_path / "userdata"))
    monkeypatch.delenv("XINMATCH_LIBRARIES_JSON", raising=False)
    monkeypatch.setattr(multi_db, "_data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(multi_db, "project_root", lambda: tmp_path / "repo")
    return libs


# ── 1. 默认库 ───────────────────────────────────────────────

def test_default_id_is_cod_inorg(isolated):
    assert multi_db.DEFAULT_LIBRARY_ID == "xindb_cod_inorg"
    assert multi_db.default_db_path() == multi_db.xindb_cod_inorg_path()


def test_resolve_default_prefers_cod_inorg(isolated, xindb_factory):
    xindb_factory(isolated / "COD-Inorg-20261020.xinDB")
    xindb_factory(isolated / "PCOD-Inorg-20261020.xinDB")
    rec = multi_db.resolve_default()
    assert rec.id == "xindb_cod_inorg"
    assert rec.available and rec.default
    assert rec.entry_count and rec.entry_count > 0


def test_resolve_default_falls_back_to_any_available(isolated, xindb_factory):
    """只有 PCOD 时也要能用 —— 不能因为默认库没构建就整个检索不可用。"""
    xindb_factory(isolated / "PCOD-Inorg-20261020.xinDB")
    rec = multi_db.resolve_default()
    assert rec.id == "xindb_pcod_inorg" and rec.available


def test_resolve_default_never_raises_when_empty(isolated):
    rec = multi_db.resolve_default()
    assert rec.id == "xindb_cod_inorg"
    assert rec.available is False and rec.unavailable_reason


def test_list_puts_default_first(isolated, xindb_factory):
    xindb_factory(isolated / "PCOD-Inorg-20261020.xinDB")
    xindb_factory(isolated / "COD-Inorg-20261020.xinDB")
    recs = multi_db.list_libraries()
    assert recs[0].id == "xindb_cod_inorg"
    assert [r.id for r in recs[:5]] == [
        "xindb_cod_inorg", "xindb_cod_full", "xindb_pcod_inorg",
        "xindb_tcod_inorg", "xindb_tcod_full"]
    # PCOD-Full 不在默认清单里：PCOD 全为无机，与 PCOD-Inorg 等同，按决定不建
    assert "xindb_pcod_full" not in {r.id for r in recs}
    # 缺失的内置行也在列表里（置灰 + 原因），不是干脆不出现
    missing = {r.id for r in recs if not r.available}
    assert "xindb_cod_full" in missing


# ── 2. 快照选择 ─────────────────────────────────────────────

def test_newest_snapshot_wins(isolated, xindb_factory):
    old = xindb_factory(isolated / "COD-Inorg-20261019.xinDB")
    new = xindb_factory(isolated / "COD-Inorg-20261020.xinDB")
    assert old.is_file() and new.is_file()
    assert multi_db.xindb_cod_inorg_path() == new


def test_undated_name_is_the_fallback(isolated, xindb_factory):
    plain = xindb_factory(isolated / "COD-Inorg.xinDB")
    assert multi_db.xindb_cod_inorg_path() == plain


def test_other_prefix_does_not_leak(isolated, xindb_factory):
    """PCOD 的文件不能被当成 COD 默认库（反之亦然）。"""
    pcod = xindb_factory(isolated / "PCOD-Inorg-20261020.xinDB")
    assert multi_db.xindb_cod_inorg_path() != pcod
    assert multi_db.xindb_pcod_inorg_path() == pcod


# ── 3. 打开 ─────────────────────────────────────────────────

def test_open_library_returns_v3_reader(isolated, xindb_factory):
    from xinmatch.core.db.reader_v3 import XinDBReader

    xindb_factory(isolated / "COD-Inorg-20261020.xinDB")
    reader = multi_db.open_library("xindb_cod_inorg")
    try:
        assert isinstance(reader, XinDBReader)
        assert reader.available is True
        assert reader.entry_count() > 0
        assert reader.meta().get("schema_version") == "3"
    finally:
        reader.close()


def test_open_library_missing_raises_friendly(isolated):
    with pytest.raises(multi_db.LibraryNotAvailableError) as ei:
        multi_db.open_library("xindb_cod_inorg")
    assert "not available" in str(ei.value)


def test_open_library_unknown_id(isolated):
    with pytest.raises(multi_db.LibraryNotAvailableError):
        multi_db.open_library("no_such_library")


def test_open_search_database_accepts_path(isolated, xindb_factory):
    from xinmatch.core.db.reader_v3 import XinDBReader

    p = xindb_factory(isolated / "COD-Inorg-20261020.xinDB")
    reader = multi_db.open_search_database(p)
    try:
        assert isinstance(reader, XinDBReader)
    finally:
        reader.close()


def test_open_search_database_rejects_legacy_sqlite(isolated, tmp_path):
    """v2 sqlite（entries/peaks 行表）不再是可检索格式。"""
    legacy = tmp_path / "cod_inorganics.db"
    conn = sqlite3.connect(legacy)
    conn.execute("CREATE TABLE entries (entry_id TEXT)")
    conn.commit()
    conn.close()
    with pytest.raises(multi_db.LibraryNotAvailableError) as ei:
        multi_db.open_search_database(legacy)
    assert "xinDB" in str(ei.value)


def test_open_search_database_missing_file(isolated, tmp_path):
    with pytest.raises(FileNotFoundError):
        multi_db.open_search_database(tmp_path / "nope.xinDB")


def test_open_search_database_rejects_corrupt_xindb(isolated, tmp_path):
    bad = tmp_path / "broken.xinDB"
    bad.write_bytes(b"not a sqlite file at all")
    with pytest.raises(multi_db.LibraryNotAvailableError):
        multi_db.open_search_database(bad)


@pytest.mark.parametrize("name", ["My Lib 中文.xinDB", "hash#tag 中文.xinDB"])
def test_open_search_database_special_paths(tmp_path, xindb_factory, name):
    """Windows 合法文件名里的空格 / 中文 / ``#`` 必须能只读打开。

    旧 reader 用未转义的 ``file:{path}?mode=ro``：``#`` 被当成 URI fragment，
    打开的是截断路径，且 ``probe`` 会在目录里创建一个 0 字节幽灵文件。
    """
    directory = tmp_path / "路径 with space"
    lib = xindb_factory(directory / name)
    reader = multi_db.open_search_database(lib)
    try:
        assert reader.entry_count() > 0
    finally:
        reader.close()
    # 只读路径不得留下任何额外文件（幽灵文件回归）
    assert sorted(p.name for p in lib.parent.iterdir()) == [lib.name]


def test_count_entries_readonly_uri_escapes_hash(tmp_path, xindb_factory):
    """``_readonly_uri`` 用 ``Path.as_uri()``，``#``/空格不得截断路径或建出幽灵文件。"""
    lib = xindb_factory(tmp_path / "hash#tag 中文.xinDB")
    assert multi_db._count_xindb_entries(lib) is not None
    assert multi_db._count_xindb_entries(lib) > 0
    # 只读计数不得在目录里留下任何额外文件
    assert sorted(p.name for p in lib.parent.iterdir()) == [lib.name]


# ── 4. 目录解析 ─────────────────────────────────────────────

def test_env_override_wins_when_it_has_a_library(
    isolated, monkeypatch, tmp_path, xindb_factory
):
    """env 覆盖目录里有库时仍优先（部署/测试语义保留）。"""
    other = tmp_path / "other"
    other.mkdir()
    lib = xindb_factory(other / "COD-Inorg-20261020.xinDB")
    monkeypatch.setenv("XINMATCH_XINDB_DIR", str(other))
    assert multi_db.xindb_default_dir() == other
    assert multi_db.xindb_cod_inorg_path() == lib


def test_empty_env_override_falls_back_to_data_dir(
    isolated, monkeypatch, tmp_path, xindb_factory
):
    """过期/空的环境变量不得静默让内置默认库失效（本机实况回归）。"""
    stale = tmp_path / "stale-env"
    stale.mkdir()
    monkeypatch.setenv("XINMATCH_XINDB_DIR", str(stale))
    # 没有任何候选目录有库 -> 回到内置数据目录，而不是那个空 env 目录
    assert multi_db.xindb_default_dir() == tmp_path / "data"
    # 候选目录真有库时立即采用它
    lib = xindb_factory(tmp_path / "data" / "COD-Inorg-20261020.xinDB")
    assert multi_db.xindb_default_dir() == tmp_path / "data"
    assert multi_db.xindb_cod_inorg_path() == lib


def test_empty_env_override_falls_back_to_sibling(
    isolated, monkeypatch, tmp_path, xindb_factory
):
    """源码态：内置 data/ 空、但构库仓库 ../XinMatch-DataBase/data 有库。"""
    stale = tmp_path / "stale-env"
    stale.mkdir()
    monkeypatch.setenv("XINMATCH_XINDB_DIR", str(stale))
    sibling = tmp_path / "XinMatch-DataBase" / "data"
    lib = xindb_factory(sibling / "COD-Inorg-20261020.xinDB")
    assert multi_db.xindb_default_dir() == sibling
    assert multi_db.xindb_cod_inorg_path() == lib


def test_stale_env_warns_only_once(isolated, monkeypatch, tmp_path, caplog):
    """注册表一次刷新会多次调用 ``xindb_default_dir``，告警只能记一次。"""
    stale = tmp_path / "stale-env"
    stale.mkdir()
    monkeypatch.setenv("XINMATCH_XINDB_DIR", str(stale))
    monkeypatch.setattr(multi_db, "_WARNED_ENV_DIRS", set())
    with caplog.at_level(logging.WARNING, logger="xinmatch.core.db.multi_db"):
        multi_db.xindb_default_dir()
        multi_db.xindb_default_dir()
    hits = [r for r in caplog.records if "XINMATCH_XINDB_DIR" in r.getMessage()]
    assert len(hits) == 1


def test_real_repo_library_is_discoverable():
    """开发机/CI 上若真有内置库，注册表必须认得出来（缺则跳过）。"""
    path = multi_db.xindb_cod_inorg_path()
    if not path.is_file():
        pytest.skip(f"本机没有内置 COD-Inorg 库: {path}")
    rec = multi_db.resolve_default()
    assert rec.available
    # 文件名要与快照命名约定一致
    assert path.name.startswith("COD-Inorg")
    assert path.suffix == ".xinDB" or os.name != "nt"
