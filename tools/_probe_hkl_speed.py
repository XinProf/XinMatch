"""只读探针：比较 gemmi 逐平面 vs numpy 倒易度量张量 两种 hkl 枚举。

目的：`_enumerate_hkl` 目前对每个 h 调一次
``gemmi.UnitCell.calculate_d_array(plane)``，plane 大小是
``(2kmax+1)*(2lmax+1)``；大晶胞下这一步会退化成几百万次逐点跨语言调用。
本探针验证「用倒易度量张量 G* = G^-1 直接算 d*^2 = h G* h^T」能否给出
**逐位等价**的 d 集合，并量化加速比。

不修改任何生产代码，只读取上游库里的 CIF 来取真实晶胞。
"""

from __future__ import annotations

import gzip
import sqlite3
import time

import gemmi
import numpy as np

UPSTREAM_DB = "D:/Project/XRD/PolyXRD/cod_data/COD_inorganics.sqlite"

DMIN, DMAX = 1.5406 / 2.0, 30.0


def metric_reciprocal(cell: gemmi.UnitCell) -> np.ndarray:
    """G* = G^-1，其中 G 是正空间度量张量。"""
    a, b, c = cell.a, cell.b, cell.c
    ca, cb, cg = (
        np.cos(np.radians(cell.alpha)),
        np.cos(np.radians(cell.beta)),
        np.cos(np.radians(cell.gamma)),
    )
    g = np.array(
        [
            [a * a, a * b * cg, a * c * cb],
            [a * b * cg, b * b, b * c * ca],
            [a * c * cb, b * c * ca, c * c],
        ],
        dtype=np.float64,
    )
    return np.linalg.inv(g)


def enum_gemmi(cell: gemmi.UnitCell, dmin: float, dmax: float) -> np.ndarray:
    """现有实现（逐 h 平面，gemmi 计算）。"""
    hmax, kmax, lmax = cell.get_hkl_limits(dmin)
    k_arr = np.arange(-kmax, kmax + 1, dtype=np.int32)
    l_arr = np.arange(-lmax, lmax + 1, dtype=np.int32)
    plane = np.empty((k_arr.size * l_arr.size, 3), dtype=np.int32)
    plane[:, 1] = np.tile(k_arr, l_arr.size)
    plane[:, 2] = np.repeat(l_arr, k_arr.size)
    out: list[np.ndarray] = []
    for h in range(-hmax, hmax + 1):
        plane[:, 0] = h
        d_plane = cell.calculate_d_array(plane)
        keep = np.isfinite(d_plane) & (d_plane >= dmin) & (d_plane <= dmax)
        if keep.any():
            out.append(np.asarray(d_plane)[keep])
    return np.concatenate(out) if out else np.empty(0)


def enum_numpy(cell: gemmi.UnitCell, dmin: float, dmax: float) -> np.ndarray:
    """候选实现：一次性构造 hkl 网格，用 G* 向量化算 d。"""
    hmax, kmax, lmax = cell.get_hkl_limits(dmin)
    hs = np.arange(-hmax, hmax + 1, dtype=np.int32)
    ks = np.arange(-kmax, kmax + 1, dtype=np.int32)
    ls = np.arange(-lmax, lmax + 1, dtype=np.int32)
    hkl = np.stack(
        np.meshgrid(hs, ks, ls, indexing="ij"), axis=-1
    ).reshape(-1, 3).astype(np.float64)
    gs = metric_reciprocal(cell)
    # d*^2 = h^T G* h
    dstar2 = np.einsum("ij,jk,ik->i", hkl, gs, hkl)
    good = dstar2 > 0.0
    d = np.full(dstar2.shape, np.inf)
    d[good] = 1.0 / np.sqrt(dstar2[good])
    keep = np.isfinite(d) & (d >= dmin) & (d <= dmax)
    return d[keep]


def _load_cells(limit: int) -> list[tuple[int, str, gemmi.UnitCell, int]]:
    conn = sqlite3.connect(f"file:{UPSTREAM_DB}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT cod_id, formula, cif_gz, n_peaks FROM phases "
            "WHERE cif_gz IS NOT NULL AND n_peaks BETWEEN 20 AND 500 "
            "ORDER BY n_peaks DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    out = []
    for cod_id, formula, gz, n_peaks in rows:
        try:
            txt = gzip.decompress(gz).decode("utf-8", "replace")
            block = gemmi.cif.read_string(txt).sole_block()
            ss = gemmi.make_small_structure_from_block(block)
            out.append((cod_id, formula, ss.cell, n_peaks))
        except Exception as exc:  # noqa: BLE001
            print(f"  [skip] {cod_id}: {exc}")
    return out


def main() -> int:
    cells = _load_cells(12)
    print(f"样本: {len(cells)} 条（按 n_peaks 降序取最大晶胞）\n")
    print(f"{'cod_id':<10}{'formula':<26}{'npk':>5}{'hkl_lim':>18}"
          f"{'n_d':>9}{'t_gemmi':>10}{'t_numpy':>10}{'speedup':>9}  match")
    total_g = total_n = 0.0
    all_ok = True
    for cod_id, formula, cell, n_peaks in cells:
        lim = cell.get_hkl_limits(DMIN)
        t0 = time.perf_counter()
        d_g = enum_gemmi(cell, DMIN, DMAX)
        t_g = time.perf_counter() - t0
        t0 = time.perf_counter()
        d_n = enum_numpy(cell, DMIN, DMAX)
        t_n = time.perf_counter() - t0
        total_g += t_g
        total_n += t_n

        ok = d_g.size == d_n.size
        note = ""
        if ok:
            a = np.sort(d_g)
            b = np.sort(d_n)
            dev = float(np.max(np.abs(a - b))) if a.size else 0.0
            ok = dev < 1e-9
            note = f"max|Δd|={dev:.2e}"
        else:
            note = f"count {d_g.size} vs {d_n.size}"
        all_ok &= ok
        print(f"{cod_id:<10}{formula[:25]:<26}{n_peaks:>5}"
              f"{str(lim):>18}{d_g.size:>9}{t_g:>10.3f}{t_n:>10.3f}"
              f"{'x%.1f' % (t_g / t_n if t_n else 0):>9}  {'OK' if ok else 'DIFF'} {note}")

    print(f"\n合计 gemmi {total_g:.3f}s   numpy {total_n:.3f}s   "
          f"加速 x{total_g / total_n if total_n else 0:.1f}")
    print("等价性:", "全部一致" if all_ok else "存在差异 —— 不可直接替换")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
