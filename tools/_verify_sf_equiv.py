"""只读校验：新的 `_structure_factors`（唯一值去重）与旧实现是否**逐位等价**。

旧实现保存在 `tools/_probe_sf_timing.py::timed_structure_factors`（纯副本，
带分段计时，算法与改动前完全一致）。本脚本对上游库中随机 + 最大的若干相
比较 |F|^2，要求相对偏差为 0（同一浮点运算顺序下应当是 bit-identical；
去重只把"重算"换成"取值"，不改变任何算术）。
"""

from __future__ import annotations

import gzip
import sqlite3
import sys
from pathlib import Path

import gemmi
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools._probe_sf_timing import timed_structure_factors  # noqa: E402
from xinmatch.core.db.peak_compute import (  # noqa: E402
    DEFAULT_DMAX,
    DEFAULT_DMIN,
    _enumerate_hkl,
    _expand_sites,
    _reciprocal_matrix,
    _structure_factors,
)

UPSTREAM_DB = "D:/Project/XRD/PolyXRD/cod_data/COD_inorganics.sqlite"


def _cifs(limit: int) -> list[tuple[int, str, bytes]]:
    conn = sqlite3.connect(f"file:{UPSTREAM_DB}?mode=ro", uri=True)
    try:
        big = conn.execute(
            "SELECT cod_id, formula, cif_gz FROM phases "
            "WHERE cif_gz IS NOT NULL AND n_peaks BETWEEN 20 AND 500 "
            "ORDER BY n_peaks DESC LIMIT ?",
            (limit,),
        ).fetchall()
        rnd = conn.execute(
            "SELECT cod_id, formula, cif_gz FROM phases "
            "WHERE cif_gz IS NOT NULL AND n_peaks BETWEEN 20 AND 500 "
            "AND rowid % 997 = 0 LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return list(big) + list(rnd)


def main() -> int:
    rows = _cifs(12)
    print(f"样本 {len(rows)} 相（最大 12 + 随机 12）\n")
    print(f"{'cod_id':<10}{'n_atoms':>8}{'n_uniqB':>9}{'n_uniqOcc':>10}"
          f"{'n_hkl':>8}{'max_rel':>12}{'max_abs':>13}  verdict      "
          f"{'old':>10}{'new':>10}{'spd':>7}")
    worst = 0.0
    n_bad = 0
    for cod_id, _formula, gz in rows:
        txt = gzip.decompress(gz).decode("utf-8", "replace")
        try:
            ss = gemmi.make_small_structure_from_block(
                gemmi.cif.read_string(txt).sole_block()
            )
        except Exception as exc:  # noqa: BLE001
            print(f"{cod_id:<10} 解析失败: {exc}")
            continue
        frac, occ, b_iso, symbols = _expand_sites(ss)
        recip = _reciprocal_matrix(ss.cell)
        enum = _enumerate_hkl(
            ss.cell, dmin=DEFAULT_DMIN, dmax=DEFAULT_DMAX, max_hkl=400_000
        )
        if enum is None:
            print(f"{cod_id:<10} 枚举失败")
            continue
        hkl, _d = enum

        f2_old, _t = timed_structure_factors(hkl, frac, occ, b_iso, symbols, recip)
        f2_new = _structure_factors(hkl, frac, occ, b_iso, symbols, recip)

        # 速度：用 CPU 时间（process_time）而不是墙钟 —— 建库进程正占满 16 核，
        # 墙钟会把别的进程的调度延迟算进来，CPU 时间才反映真实计算量。
        import time

        reps = 3
        t_old = []
        t_new = []
        for _ in range(reps):
            t0 = time.process_time()
            timed_structure_factors(hkl, frac, occ, b_iso, symbols, recip)
            t_old.append(time.process_time() - t0)
            t0 = time.process_time()
            _structure_factors(hkl, frac, occ, b_iso, symbols, recip)
            t_new.append(time.process_time() - t0)
        m_old = sorted(t_old)[reps // 2]
        m_new = sorted(t_new)[reps // 2]

        absd = float(np.max(np.abs(f2_old - f2_new))) if f2_old.size else 0.0
        scale = float(np.max(np.abs(f2_old))) if f2_old.size else 1.0
        reld = absd / scale if scale else 0.0
        worst = max(worst, reld)
        ok = reld == 0.0
        n_bad += 0 if ok else 1
        print(f"{cod_id:<10}{len(symbols):>8}{len(np.unique(b_iso)):>9}"
              f"{len(np.unique(occ)):>10}{hkl.shape[0]:>8}"
              f"{reld:>12.3e}{absd:>13.3e}  {'BIT-EXACT' if ok else 'DIFF'}"
              f"  {m_old*1000:>7.1f}ms {m_new*1000:>7.1f}ms x{m_old/m_new if m_new else 0:>4.1f}")

    print(f"\n最大相对偏差: {worst:.3e}   差异相数: {n_bad}/{len(rows)}")
    print("结论:", "完全等价，可安全启用" if n_bad == 0 else "存在差异，需回退")
    return 0 if n_bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
