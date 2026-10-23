"""只读探针：profile `compute_pattern_from_text` 的热点，定位 8.9s/相 的真凶。

动机：验收脚本 `-n 60` 单进程跑出 8.9 s/相，比建库（14 worker 并行下
约 1 s/相/worker）慢一个量级，怀疑抽样命中了大晶胞相。但
`_probe_hkl_speed.py` 已证明 hkl 枚举本身只要 1-2 ms，所以热点必在
结构因子 / 分组求和 / gemmi 解析中的某一环。
"""

from __future__ import annotations

import cProfile
import gzip
import io
import pstats
import sqlite3
import time

from xinmatch.core.db.peak_compute import compute_pattern_from_text

UPSTREAM_DB = "D:/Project/XRD/PolyXRD/cod_data/COD_inorganics.sqlite"


def _load(limit: int, order: str) -> list[tuple[int, str, bytes, int]]:
    conn = sqlite3.connect(f"file:{UPSTREAM_DB}?mode=ro", uri=True)
    try:
        return conn.execute(
            "SELECT cod_id, formula, cif_gz, n_peaks FROM phases "
            "WHERE cif_gz IS NOT NULL AND n_peaks BETWEEN 20 AND 500 "
            f"ORDER BY {order} LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()


def main() -> int:
    rows = _load(6, "n_peaks DESC")
    print("=== 逐相计时（大 n_peaks）===")
    slowest: tuple[float, int, str, bytes] | None = None
    for cod_id, formula, gz, n_peaks in rows:
        txt = gzip.decompress(gz).decode("utf-8", "replace")
        t0 = time.perf_counter()
        res = compute_pattern_from_text(txt, max_peaks=150)
        dt = time.perf_counter() - t0
        n = 0 if res is None else len(res[0])
        print(f"  cod_id={cod_id:<9} npk_up={n_peaks:<4} {formula[:28]:<30} "
              f"{dt:>8.3f}s  n_out={n}")
        if slowest is None or dt > slowest[0]:
            slowest = (dt, cod_id, formula, gz)

    assert slowest is not None
    dt, cod_id, formula, gz = slowest
    print(f"\n=== cProfile 最慢相 cod_id={cod_id} ({formula}), {dt:.3f}s ===")
    txt = gzip.decompress(gz).decode("utf-8", "replace")
    prof = cProfile.Profile()
    prof.enable()
    compute_pattern_from_text(txt, max_peaks=150)
    prof.disable()
    buf = io.StringIO()
    pstats.Stats(prof, stream=buf).sort_stats("cumulative").print_stats(18)
    out = buf.getvalue().splitlines()
    for line in out[5:30]:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
