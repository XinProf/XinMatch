"""原地补全 COD-Inorg 库的元数据（只改 entries 的元数据列，不碰 peak_chunks）。

背景
----
`COD-Inorg-20261020.xinDB` 建于 2026-10-21，早于 `cif_meta` 的两处修复：

* `find_spacegroup_by_name` 兜底（修无空格写法 H-M 符号，如 ``P1``）；
* `_symmetry_cell_setting` 兜底（修磁结构 / 超空间群，无 IT 号且符号不可解析）。

因此库里有 670 条记录 `crystal_system` 为 NULL，这些相会从「按晶系筛选」里消失。

等价性
------
`data/_meta_diff_cod.py` 用**当前代码**把 78,036 个源 CIF 全部重新解析并与库内逐列比对，
结论是「整库重建只会改动这 670 行的 `crystal_system`，以及其中 11 行的 `space_group`
规范化写法，其余 19 列 77,366 行完全一致」。峰不受影响：`peak_compute.compute_pattern`
只吃 CIF 路径，不读 `parse_meta` 的输出，且该文件自建库以来未修改。

所以把这两列按重建会写出的值写回去，entries 表就与重建结果逐字节相同。

用法
----
    python tools/_patch_meta_cod_inorg.py --dry-run     # 只报告
    python tools/_patch_meta_cod_inorg.py               # 实际写入
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path(
    r"D:\Project\XRD\PolyXRD-DataBase\xindb\COD-Inorg-20261020.xinDB"
)
DEFAULT_DIFF = Path(__file__).resolve().parents[1] / "data" / "_meta_diff_cod.json"

#: 由 `_meta_diff_cod.py` 写出的列顺序（`fresh_rows` 的值就是这个顺序）。
META_COLS = (
    "formula", "space_group", "crystal_system", "mineral_name", "elements",
    "elem_mask", "a", "b", "c", "alpha", "beta", "gamma", "volume", "density",
    "year", "author", "journal", "quality",
)
#: 本补丁只写这两列；其余列经比对确认与重解析结果一致，不动。
PATCH_COLS = ("space_group", "crystal_system")


def entry_id_for(native: int) -> str:
    s = str(int(native))
    return f"96-{s[:3]}-{s[3:]}"


def _same_space_group(a: str, b: str) -> bool:
    """True when two H-M spellings denote the same international space group."""
    try:
        import gemmi

        ga = gemmi.find_spacegroup_by_name(a)
        gb = gemmi.find_spacegroup_by_name(b)
    except Exception:
        return False
    if ga is None or gb is None:
        return False
    return int(ga.number) == int(gb.number)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--diff", type=Path, default=DEFAULT_DIFF)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    payload = json.loads(args.diff.read_text(encoding="utf-8"))
    fresh: dict[str, list] = payload["fresh_rows"]
    si, ci = META_COLS.index("space_group"), META_COLS.index("crystal_system")

    con = sqlite3.connect(args.db)
    con.execute("PRAGMA journal_mode=WAL")
    before_null = con.execute(
        "SELECT COUNT(*) FROM entries WHERE crystal_system IS NULL OR crystal_system=''"
    ).fetchone()[0]
    print(f"库: {args.db}")
    print(f"补丁前 crystal_system 为空: {before_null:,} / "
          f"{con.execute('SELECT COUNT(*) FROM entries').fetchone()[0]:,}")

    # ── 找出真正需要写的行 ───────────────────────────────────
    todo: list[tuple[str, str | None, str | None]] = []
    for native_text, row in fresh.items():
        eid = entry_id_for(int(native_text))
        cur = con.execute(
            "SELECT space_group, crystal_system FROM entries WHERE entry_id = ?",
            (eid,),
        ).fetchone()
        if cur is None:
            continue  # 该相没入库（skipped_no_peaks）
        new_sg, new_cs = row[si], row[ci]
        if (cur[0] or None) != (new_sg or None) or (cur[1] or None) != (new_cs or None):
            todo.append((eid, new_sg, new_cs))

    print(f"需要更新的行: {len(todo):,}")
    if not todo:
        print("无需改动。")
        con.close()
        return 0

    # 只允许「填 NULL → 值」与「符号规范化」。
    # ``space_group`` 的规范化（``Fm-3m`` → ``F m -3 m``）是同一空间群的另一种写法，
    # 用编号相同来放行；编号不同则是真的改值，必须拒绝。
    risky = []
    for eid, new_sg, new_cs in todo:
        cur = con.execute(
            "SELECT space_group, crystal_system FROM entries WHERE entry_id = ?", (eid,)
        ).fetchone()
        for old, new, name in ((cur[0], new_sg, "space_group"), (cur[1], new_cs, "crystal_system")):
            if old in (None, "") or new in (None, "") or old == new:
                continue
            if name == "space_group" and _same_space_group(old, new):
                continue
            risky.append((eid, name, old, new))
    if risky:
        print(f"!! 有 {len(risky)} 处会把已有值改成不同值，拒绝执行：", file=sys.stderr)
        for item in risky[:10]:
            print(f"   {item}", file=sys.stderr)
        con.close()
        return 2

    if args.dry_run:
        for eid, new_sg, new_cs in todo[:10]:
            print(f"   {eid}: space_group={new_sg!r} crystal_system={new_cs!r}")
        print("（dry-run，未写入）")
        con.close()
        return 0

    con.executemany(
        "UPDATE entries SET space_group = ?, crystal_system = ? WHERE entry_id = ?",
        [(sg, cs, eid) for eid, sg, cs in todo],
    )
    con.commit()
    after_null = con.execute(
        "SELECT COUNT(*) FROM entries WHERE crystal_system IS NULL OR crystal_system=''"
    ).fetchone()[0]
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
    con.close()

    print(f"已更新 {len(todo):,} 行")
    print(f"补丁后 crystal_system 为空: {after_null:,}")
    print(f"  减少 {before_null - after_null:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
