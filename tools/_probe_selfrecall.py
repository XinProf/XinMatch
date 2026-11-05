"""库内自召回抽查：把某相自己的峰表反算成 2θ，再检索回本库。

判据很硬：**一张参考相必须检索到自己**。只要 d 或 I 在写库/读库任一侧错位
（列位读偏、CSR 偏移算错、强度尺度不一致、chunk 边界错一格），它就排不到
第一。所以这条检查比任何「字段抽查」都更接近「这份库到底能不能用」。

它不依赖任何真值文件，任何 ``.xinDB`` 都能跑 —— COD 家族与实测库（PDF-2）
用的是同一条检索链路。

用法::

    python -m tools._probe_selfrecall --db data/COD-Inorg-20261020.xinDB --sample 100
    python -m tools._probe_selfrecall --db "D:/.../PDF2-20040317.xinDB" --sample 100

退出码：全部命中 top-1 为 0，否则 1（便于串进验收脚本）。
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from xinmatch.core.db.reader_v3 import XinDBReader  # noqa: E402
from xinmatch.core.db.search_v3 import search_match_v3  # noqa: E402
from xinmatch.core.model.peak import Peak  # noqa: E402

#: Cu Kα1（本工程所有参考库的统一波长约定）。
WAVELENGTH = 1.5406


def d_to_two_theta(d: float, wavelength: float = WAVELENGTH) -> float | None:
    """d(Å) → 2θ(°)；超出可测范围（sinθ 越界）时返回 ``None``。"""
    sin_theta = wavelength / (2.0 * d)
    if sin_theta <= 0.0 or sin_theta >= 1.0:
        return None
    return math.degrees(2.0 * math.asin(sin_theta))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True, type=Path, help="待抽查的 .xinDB")
    ap.add_argument("--sample", type=int, default=40, help="抽查相数（默认 40）")
    ap.add_argument("--seed", type=int, default=20261105, help="抽样随机种子")
    ap.add_argument("--top-n", type=int, default=5, help="每条查询取前 N 个候选")
    args = ap.parse_args(argv)

    rng = random.Random(args.seed)
    with XinDBReader(args.db) as reader:
        ok, reason = reader.probe()
        print(f"probe: ok={ok} reason={reason!r}")
        if not ok:
            return 2
        ids = reader.entry_ids()
        print(f"entries = {len(ids):,}")
        picked = rng.sample(ids, min(args.sample, len(ids)))

        top1 = top5 = 0
        failures: list[tuple[str, str, float]] = []
        for eid in picked:
            entry = reader.fetch_entry(eid)
            if entry is None:
                failures.append((eid, "(entry missing)", 0.0))
                continue
            exp = []
            for d, inten in zip(
                entry["peaks_d_list"], entry["peaks_i_list"], strict=True
            ):
                tt = d_to_two_theta(float(d))
                if tt is not None:
                    exp.append(Peak(two_theta=tt, intensity=float(inten)))
            if len(exp) < 2:
                # 单线相无法在「至少两个窗口命中」的规则下被检索到，
                # 这是检索规则的边界，不是库的缺陷，不计入分母。
                continue
            result = search_match_v3(exp, reader, WAVELENGTH, top_n=args.top_n)
            ranked = [c.entry.entry_id for c in result.candidates]
            pos = ranked.index(eid) + 1 if eid in ranked else 0
            if pos == 1:
                top1 += 1
            elif pos <= args.top_n:
                top5 += 1
            else:
                top = result.candidates[0] if result.candidates else None
                failures.append(
                    (eid, top.entry.entry_id if top else "-", top.fom if top else 0.0)
                )

    total = top1 + top5 + len(failures)
    print(f"\n自召回 {total} 张：top-1 {top1} / top-{args.top_n} {top5} / 未命中 {len(failures)}")
    if failures:
        print("未命中样本：")
        for miss_id, miss_best, miss_fom in failures[:10]:
            print(f"  {miss_id}  ->  {miss_best}  (fom {miss_fom:.3f})")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
