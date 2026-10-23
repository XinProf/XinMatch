"""只读探针：把 `_structure_factors` 拆成分段计时，找出 0.775s 花在哪一步。

用法：直接跑，对上游库里最大的几个相各测一次。不修改生产代码。

分段依据：函数体由 5 个可独立计时的块组成 ——
  A. 元素系数表准备（含 lru_cache 命中情况）
  B. s / s2 计算
  C. Cromer-Mann f(s)（3D 广播的 exp 与求和）
  D. 热振动 + 占据数加权（(m, n_atoms) 的两个 exp）
  E. 相位 + cos/sin + 求和
"""

from __future__ import annotations

import gzip
import math
import sqlite3
import time

import gemmi
import numpy as np

from xinmatch.core.db.peak_compute import (
    DEFAULT_DMIN,
    DEFAULT_DMAX,
    _CM_PREFACTOR,
    _atomic_numbers,
    _enumerate_hkl,
    _expand_sites,
    _reciprocal_matrix,
    _scattering_table,
)

UPSTREAM_DB = "D:/Project/XRD/PolyXRD/cod_data/COD_inorganics.sqlite"


def timed_structure_factors(
    hkl: np.ndarray,
    frac: np.ndarray,
    occ: np.ndarray,
    b_iso: np.ndarray,
    symbols: tuple[str, ...],
    recip: np.ndarray,
    *,
    chunk: int = 8192,
) -> tuple[np.ndarray, dict[str, float]]:
    """`_structure_factors` 的逐段计时版本（逻辑与生产代码保持一致）。"""
    t = {"A_prepare": 0.0, "B_s2": 0.0, "C_fofs": 0.0, "D_dw_occ": 0.0,
         "E_phase": 0.0, "E_cos_sin": 0.0, "E_sum": 0.0}

    t0 = time.perf_counter()
    table = _scattering_table()
    znum = _atomic_numbers()
    unique = sorted(set(symbols))
    coeff = np.zeros((len(unique), 4, 2), dtype=np.float64)
    zarr = np.zeros(len(unique), dtype=np.float64)
    for i, el in enumerate(unique):
        lookup = {"D": "H", "T": "H"}.get(el, el)
        pairs = table.get(lookup)
        if pairs is None:
            zarr[i] = float(gemmi.Element(el).atomic_number)
            continue
        for j, (a, b) in enumerate(pairs[:4]):
            coeff[i, j, 0] = a
            coeff[i, j, 1] = b
        zarr[i] = znum[lookup]
    el_of_atom = np.array([unique.index(s) for s in symbols], dtype=np.int64)
    hkl_f = hkl.astype(np.float64)
    frac_t = frac.T
    t["A_prepare"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    s = np.linalg.norm(hkl_f @ recip, axis=1) / 2.0
    s2 = s * s
    t["B_s2"] = time.perf_counter() - t0

    out = np.zeros(hkl.shape[0], dtype=np.float64)
    use_dw = bool(np.any(b_iso > 0.0))
    for start in range(0, hkl.shape[0], chunk):
        sl = slice(start, min(start + chunk, hkl.shape[0]))
        s2c = s2[sl][:, None]

        t0 = time.perf_counter()
        terms = coeff[None, :, :, 0] * np.exp(-coeff[None, :, :, 1] * s2c[:, :, None])
        f_el = zarr[None, :] - _CM_PREFACTOR * s2c * terms.sum(axis=2)
        t["C_fofs"] += time.perf_counter() - t0

        t0 = time.perf_counter()
        w = f_el[:, el_of_atom] * occ[None, :]
        if use_dw:
            w = w * np.exp(-b_iso[None, :] * s2c)
        t["D_dw_occ"] += time.perf_counter() - t0

        t0 = time.perf_counter()
        phase = (hkl_f[sl] @ frac_t) * (2.0 * math.pi)
        t["E_phase"] += time.perf_counter() - t0

        t0 = time.perf_counter()
        cs = np.cos(phase)
        sn = np.sin(phase)
        t["E_cos_sin"] += time.perf_counter() - t0

        t0 = time.perf_counter()
        re = (w * cs).sum(axis=1)
        im = (w * sn).sum(axis=1)
        out[sl] = re * re + im * im
        t["E_sum"] += time.perf_counter() - t0
    return out, t


def main() -> int:
    conn = sqlite3.connect(f"file:{UPSTREAM_DB}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT cod_id, formula, cif_gz, n_peaks FROM phases "
        "WHERE cif_gz IS NOT NULL AND n_peaks BETWEEN 20 AND 500 "
        "ORDER BY n_peaks DESC LIMIT 4"
    ).fetchall()
    conn.close()

    for cod_id, formula, gz, n_peaks in rows:
        txt = gzip.decompress(gz).decode("utf-8", "replace")
        block = gemmi.cif.read_string(txt).sole_block()
        ss = gemmi.make_small_structure_from_block(block)
        frac, occ, b_iso, symbols = _expand_sites(ss)
        recip = _reciprocal_matrix(ss.cell)
        enum = _enumerate_hkl(
            ss.cell, dmin=DEFAULT_DMIN, dmax=DEFAULT_DMAX, max_hkl=400_000
        )
        if enum is None:
            print(f"{cod_id}: 枚举失败")
            continue
        hkl, _d = enum

        # 预热（lru_cache + BLAS）
        timed_structure_factors(hkl, frac, occ, b_iso, symbols, recip)

        t_tot0 = time.perf_counter()
        f2, t = timed_structure_factors(hkl, frac, occ, b_iso, symbols, recip)
        t_tot = time.perf_counter() - t_tot0

        print(f"\ncod_id={cod_id}  {formula[:30]}  n_hkl={hkl.shape[0]}  "
              f"n_atoms={len(symbols)}  n_uniq={len(set(symbols))}")
        print(f"  总计 {t_tot*1000:.1f} ms")
        for k, v in sorted(t.items(), key=lambda kv: -kv[1]):
            print(f"    {k:<12} {v*1000:>8.1f} ms  {100*v/t_tot:>5.1f}%")
        print(f"    |F|^2 校验 sum={float(f2.sum()):.6e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
