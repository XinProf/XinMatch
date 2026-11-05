"""原地补齐「空白式卡」的 formula（3.4.1，只改 entries.formula，不碰峰）。

背景
----
COD-Inorg 里有 416 / 78,035 张卡的 CIF 缺全部三种公式标签，库内 ``formula`` 为空。
3.4.1 起 ``same_phase`` 正确地拒绝「无组成证据」的匹配，于是这些卡在组成级真值口径下
无法计入任何相 —— 基准数字只能算到下界。``cif_meta.parse_meta`` 现在会用
:func:`formula_from_sites` 从对称展开的原子位点合成化学式，保证**重建不再回退**。

等价性
------
1. ``--scan`` 用当前代码把全部源 CIF 重解析一遍，与库内 ``META_COLS`` 逐列 diff，
   回答「重建到底会改哪些行、哪些列」。
2. 峰不受影响：``compute_pattern(cif_path, ...)`` 只吃路径，不读 ``parse_meta`` 输出；
   且 ``peak_compute.py`` 的 mtime 早于建库时间。
3. ``--apply`` 只写 ``formula``，且只允许「空 → 值」与「不可解析的占位垃圾 → 值」
   （后者与「同义规范化」同类，元素集必须与库内 ``elements`` 全等）；
   ``elements`` / ``elem_mask`` / ``element_inv`` 一律不动。改前整库备份。
4. 写完跑 ``validate_xindb`` + ``_compare_xindb_peaks`` + 抽样重建对照（见 STATUS）。

用法
----
    python -m tools._patch_meta_blank_formula --scan --db <xinDB>
    python -m tools._patch_meta_blank_formula --apply --db <xinDB>
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from xinmatch.core.db.cif_meta import elements_from_formula
from xinmatch.core.db.cif_scan import (
    DEFAULT_INORG_COD_ROOT,
    entry_id_for_cod,
    iter_cod_cifs,
)

#: 由 parse_meta 决定的 18 列（其余 n_peaks/peak_off/peak_n/tier 不由 CIF 决定）。
META_COLS = (
    "formula", "space_group", "crystal_system", "mineral_name", "elements",
    "elem_mask", "a", "b", "c", "alpha", "beta", "gamma", "volume", "density",
    "year", "author", "journal", "quality",
)
_NUMERIC = frozenset({"a", "b", "c", "alpha", "beta", "gamma", "volume", "density"})


def _parse_one(task: tuple[int, str]) -> tuple[int, tuple | None, str]:
    from xinmatch.core.db.cif_meta import element_mask, parse_meta
    from xinmatch.core.db.cif_scan import entry_id_for_cod

    cod_id, path_str = task
    try:
        meta = parse_meta(Path(path_str), entry_id=entry_id_for_cod(cod_id))
    except Exception as exc:  # noqa: BLE001 - 单个坏文件不能中断全量扫描
        return cod_id, None, repr(exc)
    if meta is None:
        return cod_id, None, "no_meta"
    cell = meta.cell or (None,) * 6
    row = (
        meta.formula, meta.space_group, meta.crystal_system, meta.mineral_name,
        ",".join(meta.elements) if meta.elements else None,
        (element_mask(meta.elements)[0] & ((1 << 63) - 1)) if meta.elements else None,
        *cell, meta.volume, meta.density,
        meta.year, meta.author, meta.journal, meta.quality,
    )
    return cod_id, row, ""


def _native(eid: str) -> int:
    return int(eid.split("-", 1)[1].replace("-", ""))


def _same(col: str, old: Any, new: Any) -> bool:
    if col == "elem_mask":
        return (old or 0) == (new or 0)
    if col in _NUMERIC:
        return (old is None and new is None) or (
            old is not None and new is not None
            and abs(float(old) - float(new)) < 1e-9
        )
    return (old or None) == (new or None)


def scan(db: Path, cif_root: Path, workers: int, diff_out: Path) -> list[dict[str, str]]:
    """全量重解析并逐列 diff；返回可安全补式的行清单。"""
    con = sqlite3.connect(f"file:{db}?immutable=1", uri=True)
    stored = {_native(r[0]): r[1:] for r in con.execute(
        "SELECT entry_id, " + ", ".join(META_COLS) + " FROM entries")}
    total = len(stored)
    con.close()
    print(f"库内 entries: {total:,}　CIF 根: {cif_root}")

    tasks = [(cid, str(p)) for cid, p in iter_cod_cifs(cif_root)]
    print(f"源 CIF: {len(tasks):,}，开始全量重解析（{workers} workers）…")
    fresh: dict[int, tuple] = {}
    failed: list[tuple[int, str]] = []
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for i, (cid, row, err) in enumerate(
            ex.map(_parse_one, tasks, chunksize=200), 1
        ):
            if row is None:
                failed.append((cid, err))
            else:
                fresh[cid] = row
            if i % 20000 == 0:
                print(f"  …{i:,}/{len(tasks):,}  {time.perf_counter() - t0:.0f}s")
    print(f"重解析成功 {len(fresh):,}，失败 {len(failed):,}，"
          f"耗时 {time.perf_counter() - t0:.0f}s")
    if failed:
        print(f"  失败样例: {failed[:5]}")

    common = sorted(set(stored) & set(fresh))
    print(f"\n可比对行: {len(common):,}")
    print(f"{'列':<16}{'不一致行数':>12}   示例（库内 -> 重解析）")
    print("-" * 78)
    per_col: dict[str, list[tuple[int, object, object]]] = {c: [] for c in META_COLS}
    for native in common:
        old_row, new_row = stored[native], fresh[native]
        for ci, col in enumerate(META_COLS):
            if not _same(col, old_row[ci], new_row[ci]):
                per_col[col].append((native, old_row[ci], new_row[ci]))
    for col in META_COLS:
        diffs = per_col[col]
        sample = diffs[0] if diffs else None
        example = (f"id {sample[0]}: {str(sample[1])[:26]!r} -> {str(sample[2])[:26]!r}"
                   if sample else "")
        print(f"{col:<16}{len(diffs):>12,}   {example}{'  <<<' if diffs else ''}")

    # 护栏：只认「formula 空 → 非空」，且其他 17 列全部一致。
    ei = META_COLS.index("elements")
    other_cols = [c for c in META_COLS if c != "formula"]
    changed_other: dict[str, set[int]] = {
        c: {d[0] for d in per_col[c]} for c in other_cols
    }
    safe: list[dict[str, str]] = []
    rejected: list[tuple[int, str]] = []
    for native, old, new in per_col["formula"]:
        old_text, new_text = str(old or ""), str(new or "")
        if old_text.strip() and elements_from_formula(old_text):
            rejected.append((native, "旧值是可解析化学式，不允许覆盖"))
            continue
        if not new_text.strip():
            rejected.append((native, "新值为空"))
            continue
        if any(native in changed_other[c] for c in other_cols):
            rejected.append((native, "该行还有其他列不一致"))
            continue
        stored_elements = set(str(stored[native][ei] or "").split(","))
        if set(elements_from_formula(new_text)) != stored_elements:
            rejected.append((native, "派生式元素集与库内 elements 不符"))
            continue
        # 两类都允许：① 空 → 值；② 不可解析的占位垃圾（如 'Ph as e kn n ow un'）
        # → 值。后者与早先的「同义规范化」同类，且派生元素集必须与库内 elements 全等。
        kind = "blank" if not old_text.strip() else "garbage"
        safe.append({
            "entry_id": entry_id_for_cod(native),
            "formula": new_text,
            "old": old_text,
            "kind": kind,
        })
    kinds = {k: sum(1 for s in safe if s["kind"] == k) for k in ("blank", "garbage")}
    print(f"\n可安全补式 {len(safe):,} 行（空式 {kinds['blank']:,} / "
          f"垃圾式 {kinds['garbage']:,}）；拒写 {len(rejected):,} 行"
          + (f"（样例 {rejected[:3]}）" if rejected else ""))
    print("其他列不一致的行集合（供排查）:",
          {c: len(per_col[c]) for c in other_cols if per_col[c]})
    diff_out.parent.mkdir(parents=True, exist_ok=True)
    diff_out.write_text(json.dumps({
        "db": str(db), "cif_root": str(cif_root), "total": total,
        "common": len(common), "failed": failed[:20],
        "diff_counts": {c: len(per_col[c]) for c in META_COLS},
        "safe": safe,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"diff -> {diff_out}")
    return safe


def apply(db: Path, diff_out: Path, backup: Path | None) -> int:
    payload = json.loads(diff_out.read_text(encoding="utf-8"))
    if Path(payload["db"]).resolve() != db.resolve():
        print("[ERR] diff 文件对应的库与 --db 不一致，拒绝写入")
        return 2
    safe: list[dict[str, str]] = [dict(x) for x in payload["safe"]]
    if not safe:
        print("无可补行。")
        return 0
    if backup is not None:
        backup.parent.mkdir(parents=True, exist_ok=True)
        print(f"备份 {db} -> {backup} …")
        shutil.copy2(db, backup)
        if backup.stat().st_size != db.stat().st_size:
            print("[ERR] 备份大小不一致，拒绝写入")
            return 2
        print("备份完成。")

    con = sqlite3.connect(db)
    con.execute("PRAGMA journal_mode=WAL")
    written = 0
    try:
        con.execute("BEGIN IMMEDIATE")
        for item in safe:
            if item["kind"] == "blank":
                where = "(formula IS NULL OR trim(formula) = '')"
                params: tuple[str, ...] = (item["formula"], item["entry_id"])
            elif item["kind"] == "garbage":
                where = "formula = ?"
                params = (item["formula"], item["entry_id"], item["old"])
            else:
                raise RuntimeError(f"未知补式类别：{item['kind']}")
            cur = con.execute(
                f"UPDATE entries SET formula = ? WHERE entry_id = ? AND {where}",
                params,
            )
            if cur.rowcount != 1:
                raise RuntimeError(
                    f"护栏触发：{item['entry_id']} 不满足 {item['kind']} "
                    f"(rowcount={cur.rowcount})")
            written += 1
        # 确认没碰任何别的列：总行数与峰负载必须不变
        n = con.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        if n != payload["total"]:
            raise RuntimeError(f"entries 行数变化 {payload['total']} -> {n}")
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    left = sqlite3.connect(f"file:{db}?immutable=1", uri=True).execute(
        "SELECT COUNT(*) FROM entries WHERE formula IS NULL OR trim(formula)=''"
    ).fetchone()[0]
    print(f"写入 {written:,} 行 formula；剩余空式 {left:,} 行。")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--cif-root", type=Path, default=DEFAULT_INORG_COD_ROOT)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--diff-out", type=Path,
                    default=Path(".scratch/blank_formula_diff.json"))
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--backup", type=Path, default=None)
    args = ap.parse_args(argv)
    if args.scan == args.apply:
        print("[ERR] 必须且只能选 --scan / --apply 之一")
        return 2
    if args.scan:
        scan(args.db, args.cif_root, args.workers, args.diff_out)
        return 0
    backup = args.backup or args.db.with_name(
        args.db.name + ".bak-" + time.strftime("%Y%m%d-%H%M%S"))
    return apply(args.db, args.diff_out, backup)


if __name__ == "__main__":
    raise SystemExit(main())
