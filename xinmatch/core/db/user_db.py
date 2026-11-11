"""User database (UDB) — v3-native implementation (2026-11-11).

背景（为什么重写）
------------------
Phase 5 / T5.6 的旧实现把「用户数据库」写成 v2 SQLite（``entries`` + ``peaks``
行表，见 :mod:`xinmatch.core.db.schema`）。v3.0.0 删掉 v2 读取器之后，那种文件
**没有任何检索路径能读**——「能建库、不能检索」的死路。本模块改为直接产出
``.xinDB``：与内置库同格式、同 reader、同检索链，用户导入的 CIF 立刻可以被
search-match 命中，前提只是把文件挂进注册表（本模块落库后自动挂）。

存储布局
--------
``~/.xinmatch/UserDB.xinDB``
    用户库本体（v3 列存，与 ``XinMatch-DataBase`` 分发的库完全同构）。
``~/.xinmatch/user_db.json``
    **源清单**：``entry_id → 原始 CIF 绝对路径``。增删条目只改清单再整库重建，
    所以库内容永远能从清单复现，删条目也不必理解列存布局。
``XINMATCH_USER_DATA``
    环境变量可整体改掉上面两个位置；测试靠它把用户库隔离到 ``tmp_path``。

设计取舍
--------
**整库重建，而不是增量追加。** ``XinDBWriter`` 支持 ``resume``，但用户库规模是
几十到几百相（每相 10–30 ms），而增量追加要同时维护「清单」与「库内容」两种
真相、删条目还得重写块。整库重建让清单成为唯一真相源，代价可以忽略。

**entry_id 由源路径派生**（``UDB-<sha1(path)[:8]>``）：同一份 CIF 重复导入幂等；
CIF 改名算新条目（有意为之——改名通常意味着另一份数据）。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .cif_meta import PhaseMeta, parse_meta
from .multi_db import (
    ExternalLibrary,
    add_external_library,
    load_external_libraries,
    remove_external_library,
    user_data_dir,
)
from .peak_compute import compute_pattern
from .schema_v3 import CHUNK_SIZE, TOP_K
from .writer_v3 import XinDBWriter

logger = logging.getLogger(__name__)

#: 注册表里显示的名字。
USER_LIBRARY_LABEL = "用户数据库（自建）"

#: 用户库文件名与源清单文件名（都在 :func:`multi_db.user_data_dir` 下）。
USER_XINDB_NAME = "UserDB.xinDB"
MANIFEST_NAME = "user_db.json"

#: 用户条目前缀，便于与 COD/PCOD/TCOD 的 ``96-`` 号段区分。
ENTRY_ID_PREFIX = "UDB-"


@dataclass(frozen=True)
class UserEntry:
    """用户库里的一条参考相（从 ``.xinDB`` 的 ``entries`` 表读回）。"""

    entry_id: str
    formula: str | None
    mineral_name: str | None
    space_group: str | None
    n_peaks: int


@dataclass(frozen=True)
class UserDbResult:
    """一次增删 / 重建的结果。

    Attributes:
        added: 本次进入清单的 entry_id（可能仍因解析失败而没进库）。
        removed: 本次移出清单的 entry_id。
        skipped: ``(来源路径, 原因)``；解析失败、文件缺失等都记在这里，绝不静默。
        total: 重建完成后库里的相数。
        library_path: 用户库文件路径。
        library_id: 注册表 id；库为空或挂载失败时为 ``None``。
    """

    added: tuple[str, ...]
    removed: tuple[str, ...]
    skipped: tuple[tuple[str, str], ...]
    total: int
    library_path: Path
    library_id: str | None


# ---------------------------------------------------------------------------
# 路径与清单
# ---------------------------------------------------------------------------
def user_library_path() -> Path:
    """用户库 ``.xinDB`` 的位置（``~/.xinmatch/UserDB.xinDB``）。"""
    return user_data_dir() / USER_XINDB_NAME


def manifest_path() -> Path:
    """源清单 JSON 的位置（``~/.xinmatch/user_db.json``）。"""
    return user_data_dir() / MANIFEST_NAME


def entry_id_for(cif_path: str | Path) -> str:
    """由 CIF 绝对路径派生稳定的 entry_id（同一文件重复导入即幂等）。"""
    resolved = str(Path(cif_path).expanduser().resolve())
    digest = hashlib.sha1(resolved.encode("utf-8")).hexdigest()
    return f"{ENTRY_ID_PREFIX}{digest[:8].upper()}"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_manifest() -> list[dict[str, str]]:
    """读源清单；损坏或缺失一律当作空清单（用户库可以重建，不阻断启动）。"""
    path = manifest_path()
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("用户库清单损坏，按空清单处理：%s", path)
        return []
    items = raw.get("entries") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        return []
    out: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        cif = item.get("cif")
        entry_id = item.get("entry_id")
        if isinstance(cif, str) and cif and isinstance(entry_id, str) and entry_id:
            out.append(
                {
                    "entry_id": entry_id,
                    "cif": cif,
                    "added_at": str(item.get("added_at") or ""),
                }
            )
    return out


def _save_manifest(items: Sequence[dict[str, str]]) -> None:
    """原子写源清单（先写 ``.tmp`` 再 replace，半写文件不会留在磁盘上）。"""
    path = manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "updated_at": _now(), "entries": list(items)}
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)


def _readonly_uri(path: Path) -> str:
    """只读 ``file:`` URI（与 :mod:`multi_db` 同一写法，兼容特殊字符）。"""
    try:
        return path.resolve().as_uri() + "?mode=ro"
    except ValueError:  # pragma: no cover - 相对路径防御
        return "file:" + path.as_posix() + "?mode=ro"


# ---------------------------------------------------------------------------
# 读：条目列表
# ---------------------------------------------------------------------------
def list_user_entries() -> list[UserEntry]:
    """列出用户库里的相（库不存在或读不动时返回空列表，不抛异常）。"""
    path = user_library_path()
    if not path.is_file():
        return []
    try:
        conn = sqlite3.connect(_readonly_uri(path), uri=True)
    except sqlite3.Error:
        return []
    try:
        rows = conn.execute(
            "SELECT entry_id, formula, mineral_name, space_group, n_peaks "
            "FROM entries ORDER BY entry_id"
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    return [
        UserEntry(
            entry_id=str(row[0]),
            formula=row[1],
            mineral_name=row[2],
            space_group=row[3],
            n_peaks=int(row[4] or 0),
        )
        for row in rows
    ]


def user_entry_count() -> int:
    """用户库里的相数（库不存在时 0）。"""
    return len(list_user_entries())


def source_cif(entry_id: str) -> Path | None:
    """某条用户相来自哪个 CIF（清单里没有该 id 时返回 ``None``）。"""
    for item in _load_manifest():
        if item["entry_id"] == entry_id:
            return Path(item["cif"])
    return None


# ---------------------------------------------------------------------------
# 单相构建
# ---------------------------------------------------------------------------
def _build_one(cif_path: str) -> tuple[PhaseMeta, np.ndarray, np.ndarray] | str:
    """把一份 CIF 变成 ``(meta, d, i)``；失败时返回中文原因字符串。"""
    path = Path(cif_path)
    if not path.is_file():
        return "文件不存在"
    meta = parse_meta(path, entry_id=entry_id_for(path))
    if meta is None:
        return "CIF 无法解析（缺晶胞或不是晶体结构）"
    pattern = compute_pattern(path)
    if pattern is None:
        return "无法从结构算出衍射峰"
    d = np.asarray(pattern[0], dtype=np.float64).ravel()
    i = np.asarray(pattern[1], dtype=np.float64).ravel()
    if d.size == 0 or i.size != d.size:
        return "峰表为空"
    return meta, d, i


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------
def _unregister_user_library() -> None:
    """把用户库从注册表里摘掉（库为空 / 被删时调用）。"""
    target = user_library_path().resolve()
    for lib in load_external_libraries():
        try:
            same = lib.path.resolve() == target
        except OSError:  # pragma: no cover - 路径已失联
            same = False
        if same:
            remove_external_library(lib.id)


def ensure_registered() -> str | None:
    """确保用户库挂在注册表里，返回 library id；库不存在或挂载失败返回 ``None``。

    重复调用幂等（``add_external_library`` 按路径派生 id，重挂只更新标签），
    所以每次重建后都可以无条件调用。
    """
    path = user_library_path()
    if not path.is_file():
        return None
    try:
        record: ExternalLibrary = add_external_library(path, USER_LIBRARY_LABEL)
    except (OSError, ValueError) as exc:
        logger.warning("用户库挂载失败：%s", exc)
        return None
    return record.id


# ---------------------------------------------------------------------------
# 写：重建整库
# ---------------------------------------------------------------------------
def rebuild() -> UserDbResult:
    """按源清单整体重建用户库（原子替换）。

    清单为空时删除库文件并注销注册表——避免「0 相库」长期挂在库列表里。
    任何单相失败只进 ``skipped``，不中止整库重建。
    """
    items = _load_manifest()
    library = user_library_path()

    if not items:
        library.unlink(missing_ok=True)
        _unregister_user_library()
        return UserDbResult(
            added=(), removed=(), skipped=(), total=0,
            library_path=library, library_id=None,
        )

    library.parent.mkdir(parents=True, exist_ok=True)
    tmp = library.with_name(library.name + ".tmp")
    tmp.unlink(missing_ok=True)

    added: list[str] = []
    skipped: list[tuple[str, str]] = []
    writer = XinDBWriter(
        tmp,
        top_k=TOP_K,
        chunk_size=CHUNK_SIZE,
        tier=0,  # 用户自带 CIF 一律视作实验相
        cif_source="user",
        library_kind="user",
        build_tool="xinmatch.core.db.user_db",
    )
    try:
        for item in items:
            built = _build_one(item["cif"])
            if isinstance(built, str):
                skipped.append((item["cif"], built))
                continue
            meta, d, i = built
            try:
                writer.add(meta, d, i)
            except (ValueError, RuntimeError) as exc:
                skipped.append((item["cif"], f"写入失败：{exc}"))
                continue
            added.append(meta.entry_id)
        writer.close()
    except Exception:
        # 失败时删掉半成品：绝不让坏库覆盖上一个可用的库
        tmp.unlink(missing_ok=True)
        raise

    if not added:
        tmp.unlink(missing_ok=True)
        return UserDbResult(
            added=(), removed=(), skipped=tuple(skipped), total=0,
            library_path=library, library_id=None,
        )

    os.replace(tmp, library)
    library_id = ensure_registered()
    logger.info("用户库重建完成：%d 相、跳过 %d 相（%s）", len(added), len(skipped), library)
    return UserDbResult(
        added=tuple(added),
        removed=(),
        skipped=tuple(skipped),
        total=len(added),
        library_path=library,
        library_id=library_id,
    )


# ---------------------------------------------------------------------------
# 写：增 / 删
# ---------------------------------------------------------------------------
def add_cif_files(paths: Iterable[str | Path]) -> UserDbResult:
    """把若干 CIF 加入用户库（重复导入幂等），返回本次结果。

    只登记清单，解析与写库在 :func:`rebuild` 里做；解析失败的相会出现在
    ``skipped``，但仍留在清单中 —— 下次修好 CIF 重建即可，不必重新导入。
    """
    current = {item["entry_id"]: item for item in _load_manifest()}
    added: list[str] = []
    rejected: list[tuple[str, str]] = []

    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_dir():
            rejected.append((str(path), "这是目录；请传入具体 CIF 文件"))
            continue
        if not path.is_file():
            rejected.append((str(path), "文件不存在"))
            continue
        entry_id = entry_id_for(path)
        current[entry_id] = {
            "entry_id": entry_id,
            "cif": str(path.resolve()),
            "added_at": _now(),
        }
        added.append(entry_id)

    if added:
        _save_manifest(list(current.values()))

    result = rebuild()
    return UserDbResult(
        added=tuple(added),
        removed=result.removed,
        skipped=tuple(rejected) + result.skipped,
        total=result.total,
        library_path=result.library_path,
        library_id=result.library_id,
    )


def remove_entries(entry_ids: Iterable[str]) -> UserDbResult:
    """从用户库删除若干条目（只删清单登记，随后整库重建）。"""
    drop = {str(e) for e in entry_ids if e}
    items = _load_manifest()
    kept = [item for item in items if item["entry_id"] not in drop]
    removed = tuple(item["entry_id"] for item in items if item["entry_id"] in drop)
    if removed:
        _save_manifest(kept)
    result = rebuild()
    return UserDbResult(
        added=result.added,
        removed=removed,
        skipped=result.skipped,
        total=result.total,
        library_path=result.library_path,
        library_id=result.library_id,
    )
