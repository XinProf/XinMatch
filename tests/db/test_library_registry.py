"""外部库注册表 (v3.0.0: 只收 ``.xinDB``)
=========================================

用户可以把任意位置的 ``.xinDB`` 挂进来；注册表只记路径（``<user-data>/libraries.json``），
不复制、不转换。这条链路是"PCOD / TCOD 全库放在移动硬盘上"的用法基础。

钉住五条：
1. **只收 .xinDB** —— 旧格式（``.sqlite`` / ``.db``）在 v3 已被拒，报错要说人话；
2. **幂等** —— 同一路径重复挂载不产生第二行，``id`` 不变（配置里的选中项不会悬空）；
3. **坏文件拒收** —— 扩展名对但内容不是 v3 库时不能挂上（否则检索时才炸）；
4. **卸载只删记录** —— 库文件必须还在；
5. **坏 JSON 不致命** —— 注册表损坏时按"没有外部库"处理。
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from xinmatch.core.db import multi_db


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """把注册表与用户数据目录都隔离到临时目录。

    内置库候选目录（``<repo>/data``、``../XinMatch-DataBase/data``）也指向
    临时目录，保证"本机没有内置库"的假设不依赖开发机上的真实库。
    """
    target = tmp_path / "userdata" / "libraries.json"
    monkeypatch.setenv("XINMATCH_USER_DATA", str(tmp_path / "userdata"))
    monkeypatch.delenv("XINMATCH_LIBRARIES_JSON", raising=False)
    libs = tmp_path / "libs"
    libs.mkdir()
    monkeypatch.setenv("XINMATCH_XINDB_DIR", str(libs))
    monkeypatch.setattr(multi_db, "_data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(multi_db, "project_root", lambda: tmp_path / "repo")
    return target


def test_registry_path_follows_user_data(registry):
    assert multi_db.library_registry_path() == registry


def test_add_then_list(registry, xindb_factory, tmp_path):
    p = xindb_factory(tmp_path / "MyLib.xinDB")
    ext = multi_db.add_external_library(p)
    assert ext.id.startswith("ext_")
    ids = [lib.id for lib in multi_db.load_external_libraries()]
    assert ids == [ext.id]
    recs = {r.id: r for r in multi_db.list_libraries()}
    assert recs[ext.id].available and recs[ext.id].external
    assert recs[ext.id].entry_count > 0


def test_add_is_idempotent(registry, xindb_factory, tmp_path):
    p = xindb_factory(tmp_path / "MyLib.xinDB")
    a = multi_db.add_external_library(p)
    b = multi_db.add_external_library(p, label="改个名")
    assert a.id == b.id
    libs = multi_db.load_external_libraries()
    assert len(libs) == 1 and libs[0].display_name == "改个名"


def test_label_defaults_to_stem(registry, xindb_factory, tmp_path):
    p = xindb_factory(tmp_path / "COD-Inorg-copy.xinDB")
    ext = multi_db.add_external_library(p)
    assert ext.display_name == "COD-Inorg-copy"


def test_add_rejects_legacy_sqlite(registry, tmp_path):
    legacy = tmp_path / "cod_inorganics.db"
    conn = sqlite3.connect(legacy)
    conn.execute("CREATE TABLE entries (entry_id TEXT)")
    conn.commit()
    conn.close()
    with pytest.raises(ValueError) as ei:
        multi_db.add_external_library(legacy)
    msg = str(ei.value)
    assert ".xinDB" in msg, msg
    assert not registry.exists(), "被拒的文件不该写进注册表"


def test_add_rejects_corrupt_xindb(registry, tmp_path):
    bad = tmp_path / "broken.xinDB"
    bad.write_bytes(b"definitely not sqlite")
    with pytest.raises(ValueError):
        multi_db.add_external_library(bad)


def test_add_missing_file(registry, tmp_path):
    with pytest.raises(FileNotFoundError):
        multi_db.add_external_library(tmp_path / "nope.xinDB")


def test_remove_keeps_file(registry, xindb_factory, tmp_path):
    p = xindb_factory(tmp_path / "MyLib.xinDB")
    ext = multi_db.add_external_library(p)
    assert multi_db.remove_external_library(ext.id) is True
    assert p.is_file(), "卸载只删记录，不能删库文件"
    assert multi_db.load_external_libraries() == []


def test_remove_unknown_id(registry):
    assert multi_db.remove_external_library("ext_nope") is False


def test_corrupt_registry_is_tolerated(registry, xindb_factory, tmp_path):
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text("{not json at all", encoding="utf-8")
    assert multi_db.load_external_libraries() == []
    # 依然可以正常挂新的（覆盖掉坏文件）
    p = xindb_factory(tmp_path / "MyLib.xinDB")
    ext = multi_db.add_external_library(p)
    assert [lib.id for lib in multi_db.load_external_libraries()] == [ext.id]


def test_legacy_entries_are_ignored_on_load(registry, xindb_factory, tmp_path):
    """旧注册表里残留的 .sqlite 条目要被静默跳过（v3 读不了它）。"""
    live = xindb_factory(tmp_path / "Good.xinDB")
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(json.dumps({
        "version": 1,
        "libraries": [
            {"id": "ext_old", "path": str(tmp_path / "old.db"), "label": ""},
            {"id": "ext_good", "path": str(live), "label": ""},
        ],
    }), encoding="utf-8")
    libs = multi_db.load_external_libraries()
    assert [lib.id for lib in libs] == ["ext_good"]


def test_duplicate_of_builtin_is_not_listed_twice(registry, xindb_factory, tmp_path):
    """用户把内置库那份又手动挂一次 → 列表里只应出现内置行。"""
    libs_dir = Path(multi_db.xindb_default_dir())
    builtin = xindb_factory(libs_dir / "COD-Inorg-20261020.xinDB")
    multi_db.add_external_library(builtin)
    recs = multi_db.list_libraries()
    same = [r for r in recs if r.path.resolve() == builtin.resolve()]
    assert len(same) == 1
    assert same[0].id == "xindb_cod_inorg"
