#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探测 PolyXRD 官方无机库 ``COD_inorganics.sqlite`` 的权威峰表约定（只读）。

目的
----
为 XinMatch v3 数据库重建（.xinDB）确定参数依据。峰数据要从 COD CIF 重算，
必须与上游 v2 主库（``cod_inorganics.db``，源自 ``COD_inorganics.sqlite``）口径一致。

本脚本 **只读**，不写任何库、不改任何上游脚本。

实测项
------
1. 上游库 meta 表全量内容
2. 全表 ``peaks_d`` 值域 / 每行 dmax、dmin 分布
3. ``n_peaks`` 分布直方图与截断值
4. 存储顺序（``peaks_d`` 是否降序）、``peaks_i`` 是否同序、强度 max 是否恒 1000
5. 决定性对拍：fastcif + fastxrd 重算 vs 上游库，多参数组合误差矩阵
6. fastcif.parse_cif / gemmi.read_small_structure 鲁棒性（200 条抽样）
7. fastxrd 与 gemmi 结构因子差异来源（定量）

用法
----
::

    C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe \
        D:/Project/XRD/XinMatch/tools/_probe_peak_convention.py --stage all
"""

from __future__ import annotations

import argparse
import json
import gzip
import math
import os
import sqlite3
import sys
import traceback
from collections import Counter

import numpy as np

# ── 本机路径（Windows，统一正斜杠） ────────────────────────────────────────
UPSTREAM_DB = "D:/Project/XRD/PolyXRD/cod_data/COD_inorganics.sqlite"
XINMATCH_DB = "D:/Project/XRD/XinMatch/data/cod_inorganics.db"
REF_TOOLS = "D:/Project/XRD/PolyXRD-DataBase/tools"
SCAT_JSON = "D:/Project/XRD/PolyXRD-DataBase/_atomic_scattering_params.json"

WL = 1.5406

# 候选参数组合：(标签, kwargs)
#   tth_range : fastxrd 的 2θ 区间（度）
#   dmin/dmax : 计算后按 d 区间二次截断
#   max_peaks : 0 表示不截断；>0 按 fastxrd 语义（按强度保留 top-N 再按 2θ 升序）
#   half      : fastxrd 的 Friedel 减半开关
PARAM_SETS = [
    ("tth(5,115)", dict(tth_range=(5.0, 115.0), max_peaks=500)),
    ("tth(5,90)", dict(tth_range=(5.0, 90.0), max_peaks=500)),
    ("tth(2,180)", dict(tth_range=(2.0, 180.0), max_peaks=500)),
    ("tth(2,180)+d<=30", dict(tth_range=(2.0, 180.0), max_peaks=500, dmax=30.0)),
    ("tth(2.9431,180)", dict(tth_range=(2.0 * math.degrees(math.asin(WL / 60.0)), 180.0),
                             max_peaks=500)),
    ("tth(2,180)不截峰", dict(tth_range=(2.0, 180.0), max_peaks=0)),
    ("tth(2,180)全球", dict(tth_range=(2.0, 180.0), max_peaks=500, half=False)),
    ("tth(2,180)全球+d<=30", dict(tth_range=(2.0, 180.0), max_peaks=500,
                                   half=False, dmax=30.0)),
]


def _hr(title: str) -> None:
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)


# ──────────────────────────────────────────────────────────────────────────
# stage 1: meta 表全量
# ──────────────────────────────────────────────────────────────────────────
def stage_meta() -> None:
    _hr("STAGE 1 — 上游库 meta 表全量内容")
    conn = sqlite3.connect("file:%s?mode=ro" % UPSTREAM_DB, uri=True)
    print("-- sqlite_master (tables/indexes) --")
    for t, name in conn.execute(
        "SELECT type, name FROM sqlite_master ORDER BY type, name"
    ):
        print("   %-6s %s" % (t, name))
    print("\n-- meta 全量 key/value --")
    meta = dict(conn.execute("SELECT key, value FROM meta"))
    for k in sorted(meta):
        print("   %-22s = %s" % (k, meta[k]))
    print("\n-- 任务要求确认的 7 个 key 是否存在 --")
    for k in (
        "two_theta_range",
        "max_peaks",
        "intensity_scale",
        "wavelength",
        "peak_engine",
        "cif_source",
        "build_time",
    ):
        print("   %-18s : %s" % (k, ("存在 -> %s" % meta[k]) if k in meta else "*** 不存在 ***"))
    print("\n-- phases 表结构 --")
    for (sql,) in conn.execute(
        "SELECT sql FROM sqlite_master WHERE name='phases'"
    ):
        print(sql)
    print("\n-- 行数统计 --")
    q = conn.execute
    print("   phases 总数           :", q("SELECT COUNT(*) FROM phases").fetchone()[0])
    print("   cif_gz 非空           :", q("SELECT COUNT(*) FROM phases WHERE cif_gz IS NOT NULL").fetchone()[0])
    print("   n_peaks>0             :", q("SELECT COUNT(*) FROM phases WHERE n_peaks>0").fetchone()[0])
    print("   parse_errors 行数     :", q("SELECT COUNT(*) FROM parse_errors").fetchone()[0])
    print("\n-- parse_errors reason 分类 --")
    for reason, n in q(
        "SELECT reason, COUNT(*) FROM parse_errors GROUP BY reason ORDER BY COUNT(*) DESC LIMIT 20"
    ):
        print("   %-40s %d" % (reason, n))
    conn.close()


# ──────────────────────────────────────────────────────────────────────────
# stage 2: d 值域 + 峰数分布 + 存储顺序
# ──────────────────────────────────────────────────────────────────────────
def stage_stats(sample_mod: int = 7) -> None:
    _hr("STAGE 2 — d 值域 / n_peaks 分布 / 存储顺序 / 归一化")
    conn = sqlite3.connect("file:%s?mode=ro" % UPSTREAM_DB, uri=True)

    # 2a 全表扫描：每行 dmin / dmax / 是否降序 / Imax
    print("-- 2a 全表 71,199 行扫描（d 极值、单调性、Imax）--")
    row_dmin = []
    row_dmax = []
    desc_rows = 0
    nonmono_rows = 0
    asc_rows = 0
    imax_hist = Counter()
    imax_not_1000 = []
    len_mismatch = []
    npk_hist = Counter()
    npk_mismatch = 0
    global_dmin = (1e9, None)
    global_dmax = (-1.0, None)
    tie_rows = 0

    cur = conn.execute(
        "SELECT cod_id, n_peaks, peaks_d, peaks_i FROM phases"
    )
    for cid, n_pk, pd_, pi_ in cur:
        if not pd_:
            continue
        d = np.fromstring(pd_.replace(",", " "), sep=" ")
        i = np.fromstring(pi_.replace(",", " "), sep=" ")
        if d.size != i.size:
            len_mismatch.append((cid, d.size, i.size))
            continue
        if d.size != n_pk:
            npk_mismatch += 1
        npk_hist[n_pk] += 1
        row_dmin.append(float(d.min()))
        row_dmax.append(float(d.max()))
        if d.min() < global_dmin[0]:
            global_dmin = (float(d.min()), cid)
        if d.max() > global_dmax[0]:
            global_dmax = (float(d.max()), cid)
        diffs = np.diff(d)
        if np.all(diffs < 0):
            desc_rows += 1
        elif np.all(diffs > 0):
            asc_rows += 1
        else:
            nonmono_rows += 1
        if np.any(diffs == 0):
            tie_rows += 1
        imax_hist[round(float(i.max()), 3)] += 1
        if abs(float(i.max()) - 1000.0) > 0.051:
            imax_not_1000.append((cid, float(i.max()), int(i.argmax())))

    row_dmin = np.array(row_dmin)
    row_dmax = np.array(row_dmax)
    print("   扫描行数              : %d" % row_dmin.size)
    print("   全局 dmin             : %.4f Å (cod_id=%s)" % global_dmin)
    print("   全局 dmax             : %.4f Å (cod_id=%s)" % global_dmax)
    print("   每行 dmax 中位        : %.4f  (p90=%.4f)" % (np.median(row_dmax), np.percentile(row_dmax, 90)))
    print("   每行 dmin 中位        : %.4f  (p10=%.4f)" % (np.median(row_dmin), np.percentile(row_dmin, 10)))
    print("   dmax>29.5 的行数      : %d" % int((row_dmax > 29.5).sum()))
    print("   dmax>30.0 的行数      : %d" % int((row_dmax > 30.0).sum()))
    print("   dmin<0.7703(=λ/2) 行数: %d" % int((row_dmin < WL / 2).sum()))
    print("   dmin<0.80 的行数      : %d" % int((row_dmin < 0.80).sum()))
    print("   d 严格降序行数        : %d" % desc_rows)
    print("   d 严格升序行数        : %d" % asc_rows)
    print("   d 非单调行数          : %d" % nonmono_rows)
    print("   含等 d(相邻相等) 行数 : %d   <== 等价反射未合并" % tie_rows)
    print("   len(d)!=len(i) 行数   : %d" % len(len_mismatch))
    print("   n_peaks!=len(peaks_d) : %d" % npk_mismatch)
    print("   Imax 直方图 top5      : %s" % imax_hist.most_common(5))
    print("   Imax!=1000 的行数     : %d" % len(imax_not_1000))
    for cid, mx, arg in imax_not_1000[:12]:
        print("      cod_id=%-9s Imax=%.1f (argmax=%d)" % (cid, mx, arg))

    # 2b 2theta 反推
    print("\n-- 2b 由 d 反推 2θ（λ=%.4f）--" % WL)
    tt_of_dmax = 2 * np.degrees(np.arcsin(np.clip(WL / (2 * row_dmax), 0, 1)))
    tt_of_dmin = 2 * np.degrees(np.arcsin(np.clip(WL / (2 * row_dmin), 0, 1)))
    print("   每行 2θ_min: min=%.3f  p1=%.3f  中位=%.3f  max=%.3f"
          % (tt_of_dmax.min(), np.percentile(tt_of_dmax, 1),
             np.median(tt_of_dmax), tt_of_dmax.max()))
    print("   每行 2θ_max: min=%.3f  中位=%.3f  p99=%.3f  max=%.3f"
          % (tt_of_dmin.min(), np.median(tt_of_dmin),
             np.percentile(tt_of_dmin, 99), tt_of_dmin.max()))
    print("   -> λ/2 = %.4f Å 对应 2θ=180°；d=30 Å 对应 2θ=%.3f°"
          % (WL / 2, 2 * math.degrees(math.asin(min(1.0, WL / 60.0)))))

    # 2c n_peaks 分布
    print("\n-- 2c n_peaks 分布 --")
    nps = np.array(sorted(npk_hist.keys()))
    cnt = np.array([npk_hist[k] for k in nps])
    print("   min=%d  p25=%d  median=%d  p75=%d  p95=%d  max=%d"
          % (nps.min(), np.percentile(nps, 25), np.median(nps),
             np.percentile(nps, 75), np.percentile(nps, 95), nps.max()))
    print("   频次 top 20:")
    for k, v in npk_hist.most_common(20):
        print("      n_peaks=%-5d %6d 条 (%.2f%%)" % (k, v, 100.0 * v / sum(npk_hist.values())))
    print("   n_peaks>=495:")
    for k in sorted(k for k in npk_hist if k >= 495):
        print("      %d : %d 条" % (k, npk_hist[k]))
    print("   n_peaks<=12:")
    for k in sorted(k for k in npk_hist if k <= 12):
        print("      %d : %d 条" % (k, npk_hist[k]))

    # 2d 抽样 ≥5000 行的均匀抽样统计
    print("\n-- 2d 均匀抽样统计 (rowid %% %d == 0) --" % sample_mod)
    rows = conn.execute(
        "SELECT cod_id, n_peaks, peaks_d, peaks_i FROM phases WHERE rowid %% %d = 0" % sample_mod
    ).fetchall()
    print("   抽样行数: %d (≥5000 满足)" % len(rows))
    alld = []
    alli = []
    for cid, n_pk, pd_, pi_ in rows:
        alld.append(np.fromstring(pd_.replace(",", " "), sep=" "))
        alli.append(np.fromstring(pi_.replace(",", " "), sep=" "))
    D = np.concatenate(alld)
    I = np.concatenate(alli)
    print("   抽样总峰数: %d" % D.size)
    print("   d  min=%.4f  max=%.4f   I  min=%.4f  max=%.4f"
          % (D.min(), D.max(), I.min(), I.max()))
    conn.close()


# ──────────────────────────────────────────────────────────────────────────
# stage 3: 决定性对拍
# ──────────────────────────────────────────────────────────────────────────
def _load_ref_tools():
    """把 PolyXRD-DataBase/tools 加入 sys.path（只读引用）。"""
    if REF_TOOLS not in sys.path:
        sys.path.insert(0, REF_TOOLS)
    import fastcif  # noqa: E402
    import fastxrd  # noqa: E402
    global _FX
    _FX = fastxrd
    return fastcif, fastxrd


_FX = None


def _pick_entries(conn, n_target=16):
    """挑选带 cif_gz、n_peaks 在 80~500、覆盖不同空间群的条目。"""
    want_sg = [
        "F m -3 m", "P 4/n m m", "R -3 c", "P 6_3/m m c", "I 4_1/a m d",
        "C 1 2/c 1", "P n m a", "P 1 21/c 1", "P 4_2/m n m", "I m -3 m",
        "P m -3 m", "R 3 m", "P 63/m m c", "P 21 21 21", "C 2/m",
        "P -1", "I 4/m m m",
    ]
    picked = []
    seen_sg = set()
    rows = conn.execute(
        "SELECT cod_id, formula, space_group, cell_a, cell_b, cell_c, "
        "       n_peaks, peaks_d, peaks_i, cif_gz "
        "FROM phases WHERE cif_gz IS NOT NULL AND n_peaks BETWEEN 80 AND 500"
    )
    for row in rows:
        cid, formula, sg, a, b, c, n_pk, pd_, pi_, gz = row
        sg = (sg or "").strip()
        if sg in want_sg and sg not in seen_sg:
            picked.append(row)
            seen_sg.add(sg)
        if len(picked) >= n_target:
            break
    # 补齐：fluorite / SiO2 / Fe3O4 之类
    for pat in ("Ca F2", "Si O2", "Fe3 O4", "Al2 O3", "Ti O2"):
        if len(picked) >= n_target + 4:
            break
        for row in conn.execute(
            "SELECT cod_id, formula, space_group, cell_a, cell_b, cell_c, "
            "       n_peaks, peaks_d, peaks_i, cif_gz "
            "FROM phases WHERE cif_gz IS NOT NULL AND formula = ? LIMIT 1",
            (pat,),
        ):
            picked.append(row)
    return picked


def _refl_from_cif(fastcif, fastxrd, text):
    """用 fastcif 解析 + 对称展开，得到 fastxrd 需要的数组。"""
    d = fastcif.parse_cif(text)
    coords, sp_list, _ = fastcif.expand_sites(d.sites, d.symops)
    rows_, syms, occs = [], [], []
    for coord, sp in zip(coords, sp_list):
        for el, o in sp.items():
            o = float(o)
            rows_.append(coord)
            syms.append(el)
            occs.append(min(o, 1.0) if o > 0 else 1.0)
    return d, np.asarray(rows_, dtype=float), syms, occs


def _group_by_d(dvals, ivals, nd=4):
    """把 (d, I) 序列按 d 四舍五入到 nd 位分组。

    返回 {d_key: [I, ...]}，每组 I 升序排序。
    """
    out = {}
    for dv, iv in zip(dvals, ivals):
        out.setdefault(round(float(dv), nd), []).append(float(iv))
    for k in out:
        out[k].sort()
    return out


def _cmp_by_d(d_ref, i_ref, d_new, i_new, nd=4):
    """按 d 分组做集合级比对（上游存在「相邻等 d 未合并」的情形，下标对齐会错位）。"""
    g_ref = _group_by_d(d_ref, i_ref, nd)
    g_new = _group_by_d(d_new, i_new, nd)
    keys_ref = set(g_ref)
    keys_new = set(g_new)
    common = keys_ref & keys_new
    only_ref = keys_ref - keys_new
    only_new = keys_new - keys_ref
    ddif = 0.0
    idif = 0.0
    for k in common:
        a = g_ref[k]
        b = g_new[k]
        n = min(len(a), len(b))
        for j in range(n):
            idif = max(idif, abs(a[j] - b[j]))
        if len(a) != len(b):
            # 同 d 但峰条数不同（上游未合并等价反射）
            idif = max(idif, 1e9)
    # Δd 用未取整的 d 求（组内取第一条做代表）
    rep_ref = {}
    for dv in d_ref:
        rep_ref.setdefault(round(float(dv), nd), float(dv))
    rep_new = {}
    for dv in d_new:
        rep_new.setdefault(round(float(dv), nd), float(dv))
    for k in common:
        ddif = max(ddif, abs(rep_ref[k] - rep_new[k]))
    return dict(
        n_ref=len(d_ref), n_new=len(d_new),
        n_keys_ref=len(keys_ref), n_keys_new=len(keys_new),
        n_common=len(common), n_only_ref=len(only_ref), n_only_new=len(only_new),
        ddif=ddif, idif=idif,
        only_ref=sorted(only_ref)[:8], only_new=sorted(only_new)[:8],
    )


def stage_match(n_target=16) -> None:
    _hr("STAGE 3 — 决定性对拍：fastcif+fastxrd 重算 vs 上游库")
    fastcif, fastxrd = _load_ref_tools()
    conn = sqlite3.connect("file:%s?mode=ro" % UPSTREAM_DB, uri=True)
    entries = _pick_entries(conn, n_target)
    print("对拍条目数: %d" % len(entries))

    summary = {}
    for cid, formula, sg, a, b, c, n_pk, pd_, pi_, gz in entries:
        d_ref = np.fromstring(pd_.replace(",", " "), sep=" ")
        i_ref = np.fromstring(pi_.replace(",", " "), sep=" ")
        print("\n" + "-" * 100)
        print("cod_id=%-9s %-22s sg=%-14s n_peaks=%-4d d范围 %.4f–%.4f"
              % (cid, formula, sg, n_pk, d_ref.max(), d_ref.min()))
        try:
            text = gzip.decompress(gz).decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001
            print("   CIF 解压失败: %s" % exc)
            continue
        try:
            d_cif, frac, syms, occs = _refl_from_cif(fastcif, fastxrd, text)
        except Exception as exc:  # noqa: BLE001
            print("   fastcif 解析失败: %s" % exc)
            continue
        print("   fastcif: ok=%s a=%.4f b=%.4f c=%.4f 展开位点=%d"
              % (d_cif.ok, d_cif.a, d_cif.b, d_cif.c, len(syms)))

        for label, kw in PARAM_SETS:
            tth = kw.get("tth_range", (5.0, 115.0))
            dmin = kw.get("dmin")
            dmax = kw.get("dmax")
            mp = kw.get("max_peaks", 500)
            half = kw.get("half", True)
            try:
                dd, ii = fastxrd.compute_pattern_arrays(
                    d_cif.a, d_cif.b, d_cif.c, d_cif.alpha, d_cif.beta, d_cif.gamma,
                    frac, syms, occs,
                    wavelength=WL, tth_range=tth,
                    max_peaks=mp, scale=1000.0, max_hkl=300000,
                    half_sphere=half,
                )
            except Exception as exc:  # noqa: BLE001
                print("   %-22s 计算异常: %s" % (label, exc))
                continue
            dd = np.asarray(dd, dtype=float)
            ii = np.asarray(ii, dtype=float)
            if dmin is not None:
                m = dd >= dmin
                dd, ii = dd[m], ii[m]
            if dmax is not None:
                m = dd <= dmax
                dd, ii = dd[m], ii[m]
            if dd.size == 0:
                print("   %-22s 0 峰" % label)
                continue
            c = _cmp_by_d(d_ref, i_ref, dd, ii)
            # 前 6 条 d 逐条一致（按 d 降序，各取前 6）
            o_ref = np.argsort(-d_ref, kind="stable")
            o_new = np.argsort(-dd, kind="stable")
            d6_ref = d_ref[o_ref][:6]
            d6_new = dd[o_new][:6]
            n6 = min(d6_ref.size, d6_new.size)
            first6_ok = bool(n6 == 6 and np.allclose(d6_ref, d6_new, atol=5e-4))
            # 最强线
            k_ref = int(np.argmax(i_ref))
            k_new = int(np.argmax(ii))
            print("   %-22s 峰数 %4d(上游 %4d)  d键 上游%4d 新%4d 公共%4d  仅上游%3d 仅新%3d"
                  "  maxΔd=%.2e  maxΔI=%.2f  前6d一致=%s"
                  % (label, dd.size, d_ref.size, c["n_keys_ref"], c["n_keys_new"],
                     c["n_common"], c["n_only_ref"], c["n_only_new"],
                     c["ddif"], c["idif"], first6_ok))
            if c["n_only_ref"] or c["n_only_new"]:
                print("        仅上游 d: %s" % c["only_ref"])
                print("        仅新算 d: %s" % c["only_new"])
            print("        最强线: 上游 d=%.4f I=%.1f | 新算 d=%.4f I=%.1f"
                  % (d_ref[k_ref], i_ref[k_ref], dd[k_new], ii[k_new]))
            summary.setdefault(label, []).append(
                dict(cid=cid, n_new=int(dd.size), n_ref=int(d_ref.size),
                     ddn=int(dd.size - d_ref.size), ddif=c["ddif"], idif=c["idif"],
                     first6=first6_ok, n_common=c["n_common"],
                     n_keys_ref=c["n_keys_ref"], n_keys_new=c["n_keys_new"],
                     n_only_ref=c["n_only_ref"], n_only_new=c["n_only_new"])
            )
    conn.close()

    print("\n" + "=" * 100)
    print("对拍汇总（各参数组合在全部条目上的表现）")
    print("=" * 100)
    print("%-22s %7s %7s %7s %7s %9s %11s %11s %8s"
          % ("参数组合", "Δn均值", "|Δn|max", "d键Δ", "公共", "maxΔd", "maxΔI",
             "仅上游和", "前6全对"))
    for label, _ in PARAM_SETS:
        recs = summary.get(label)
        if not recs:
            continue
        ddn = np.array([r["ddn"] for r in recs], dtype=float)
        ddif = np.array([r["ddif"] for r in recs], dtype=float)
        idif = np.array([r["idif"] for r in recs], dtype=float)
        ncom = np.array([r["n_common"] for r in recs], dtype=float)
        kref = np.array([r["n_keys_ref"] for r in recs], dtype=float)
        knew = np.array([r["n_keys_new"] for r in recs], dtype=float)
        kdiff = np.abs(kref - knew)
        only = np.array([r["n_only_ref"] + r["n_only_new"] for r in recs], dtype=float)
        print("%-22s %7.1f %7d %7.1f %7.1f %9.2e %11.2f %11.1f %8d/%d"
              % (label, ddn.mean(), int(np.abs(ddn).max()), kdiff.mean(),
                 ncom.mean(), ddif.max(), idif.max(), only.mean(),
                 int(sum(r["first6"] for r in recs)), len(recs)))


# ──────────────────────────────────────────────────────────────────────────
# stage 4: 解析鲁棒性
# ──────────────────────────────────────────────────────────────────────────
def stage_robust(n=200) -> None:
    _hr("STAGE 4 — fastcif / gemmi 解析鲁棒性（抽样 %d 条 cif_gz）" % n)
    fastcif, fastxrd = _load_ref_tools()
    import gemmi

    conn = sqlite3.connect("file:%s?mode=ro" % UPSTREAM_DB, uri=True)
    rows = conn.execute(
        "SELECT cod_id, formula, space_group, cif_gz FROM phases "
        "WHERE cif_gz IS NOT NULL ORDER BY cod_id LIMIT ?", (n,)
    ).fetchall()
    conn.close()
    print("抽样条目: %d" % len(rows))

    fc_fail = Counter()
    fc_fail_detail = []
    gm_fail = Counter()
    gm_fail_detail = []
    sg_none = 0
    no_symops = 0
    fc_ok = 0
    gm_ok = 0

    for cid, formula, sg, gz in rows:
        try:
            text = gzip.decompress(gz).decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001
            fc_fail["gzip: %s" % type(exc).__name__] += 1
            gm_fail["gzip: %s" % type(exc).__name__] += 1
            continue

        # --- fastcif ---
        try:
            d = fastcif.parse_cif(text)
            if not d.ok:
                fc_fail["not ok: %s" % d.err] += 1
                fc_fail_detail.append((cid, "not ok: %s" % d.err))
            else:
                fc_ok += 1
                if not d.symops or d.symops == ["x, y, z"]:
                    no_symops += 1
        except Exception as exc:  # noqa: BLE001
            fc_fail["exc: %s" % type(exc).__name__] += 1
            fc_fail_detail.append((cid, "exc %s: %s" % (type(exc).__name__, exc)))

        # --- gemmi ---
        try:
            ss = _gemmi_read_small_structure(gemmi, text)
            if ss.spacegroup is None:
                sg_none += 1
            else:
                gm_ok += 1
        except Exception as exc:  # noqa: BLE001
            gm_fail["exc: %s" % type(exc).__name__] += 1
            gm_fail_detail.append((cid, "exc %s: %s" % (type(exc).__name__, exc)))

    print("\n-- fastcif.parse_cif --")
    print("   成功: %d / %d  (%.2f%%)" % (fc_ok, len(rows), 100.0 * fc_ok / len(rows)))
    print("   失败/未 ok 明细:")
    for k, v in fc_fail.most_common():
        print("      %-52s %d" % (k, v))
    for cid, msg in fc_fail_detail[:15]:
        print("        cod_id=%s %s" % (cid, msg))
    print("   仅恒等对称操作(未展开)的条目数: %d" % no_symops)

    print("\n-- gemmi.read_small_structure --")
    print("   成功(有空间群): %d / %d  (%.2f%%)" % (gm_ok, len(rows), 100.0 * gm_ok / len(rows)))
    print("   spacegroup is None: %d" % sg_none)
    print("   失败明细:")
    for k, v in gm_fail.most_common():
        print("      %-52s %d" % (k, v))
    for cid, msg in gm_fail_detail[:15]:
        print("        cod_id=%s %s" % (cid, msg))


# ──────────────────────────────────────────────────────────────────────────
# stage 5: fastxrd vs gemmi 结构因子差异
# ──────────────────────────────────────────────────────────────────────────
def stage_gemmi_diff() -> None:
    _hr("STAGE 5 — fastxrd 与 gemmi 结构因子差异来源（定量）")
    fastcif, fastxrd = _load_ref_tools()
    import gemmi

    with open(SCAT_JSON, "r", encoding="utf-8") as fh:
        fast_tab = json.load(fh)

    # ── 5a 散射因子表：fastxrd(JSON, Z-形式) vs gemmi ITC-1992 ──────────────
    print("-- 5a 原子散射因子 f(s)：fastxrd 表 vs gemmi it92 --")
    print("   fastxrd 形式: f(s) = Z - 41.78214*s^2*SUM_i a_i*exp(-b_i*s^2)")
    print("   系数来源: %s（%d 元素）" % (SCAT_JSON, len(fast_tab)))
    elems = ["H", "C", "O", "F", "Na", "Mg", "Al", "Si", "Ca", "Ti", "Cr",
             "Fe", "Cu", "Zn", "Zr", "W", "Pb"]
    s_grid = [0.05, 0.10, 0.20, 0.30, 0.40, 0.50]
    print("   %-4s %s" % ("元素", "  ".join("s=%.2f" % s for s in s_grid)))
    rel_all = []
    for el in elems:
        coeffs = fast_tab[el]
        z = fastxrd._Z[el]
        cells = []
        for s in s_grid:
            fs = sum(a * math.exp(-b * s * s) for a, b in coeffs)
            f_fast = z - 41.78214 * s * s * fs
            f_gem = _gemmi_it92_f(el, s)
            rel = 100.0 * (f_fast - f_gem) / f_gem
            rel_all.append(rel)
            cells.append("%+7.4f%%" % rel)
        print("   %-4s %s" % (el, "  ".join(cells)))
    rel_all = np.array(rel_all)
    print("   -> 全部 %d 个 (元素,s) 组合: 相对差 均值=%+.4f%%  |均值|最大=%.4f%%  "
          "中位=%+.4f%%" % (rel_all.size, rel_all.mean(),
                           np.abs(rel_all).max(), np.median(rel_all)))

    # ── 5b 同一条 CIF：fastxrd 强度 vs gemmi |F|²·LP·mult（双方归一化到 1000） ──
    print("\n-- 5b 同一条 CIF 的强度对比（fastxrd 已含多重度；gemmi 侧按 ASU 计数×mult）--")
    conn = sqlite3.connect("file:%s?mode=ro" % UPSTREAM_DB, uri=True)
    rows = conn.execute(
        "SELECT cod_id, formula, space_group, n_peaks, peaks_d, peaks_i, cif_gz "
        "FROM phases WHERE cif_gz IS NOT NULL AND n_peaks BETWEEN 80 AND 500 LIMIT 3"
    ).fetchall()
    conn.close()
    for cid, formula, sg, n_pk, pd_, pi_, gz in rows:
        print("\n   ==== cod_id=%s %s sg=%s ====" % (cid, formula, sg))
        text = gzip.decompress(gz).decode("utf-8", "replace")
        d_cif, frac, syms, occs = _refl_from_cif(fastcif, fastxrd, text)
        dd, ii = fastxrd.compute_pattern_arrays(
            d_cif.a, d_cif.b, d_cif.c, d_cif.alpha, d_cif.beta, d_cif.gamma,
            frac, syms, occs,
            wavelength=WL, tth_range=(5.0, 115.0), max_peaks=0,
            scale=1000.0, max_hkl=300000,
        )
        dd = np.asarray(dd, dtype=float)
        ii = np.asarray(ii, dtype=float)
        ss = _gemmi_read_small_structure(gemmi, text)
        ss.setup_cell_images()
        cell = ss.cell
        sfc = gemmi.StructureFactorCalculatorX(cell)
        asu = gemmi.ReciprocalAsu(ss.spacegroup)
        hmax, kmax, lmax = cell.get_hkl_limits(1.0)
        gm = {}
        for h in range(-hmax, hmax + 1):
            for k in range(-kmax, kmax + 1):
                for l in range(-lmax, lmax + 1):
                    hkl = (h, k, l)
                    if not asu.is_in(hkl):
                        continue
                    d = cell.calculate_d(hkl)
                    if not np.isfinite(d) or d < 1.0:
                        continue
                    f = sfc.calculate_sf_from_small_structure(ss, hkl)
                    f2 = f.real ** 2 + f.imag ** 2
                    if f2 <= 0:
                        continue
                    t = math.asin(min(1.0, WL / (2 * d)))
                    lp = (1 + math.cos(2 * t) ** 2) / (math.sin(t) ** 2 * math.cos(t))
                    key = round(d, 5)
                    if key not in gm:
                        gm[key] = [0.0, 0]
                    gm[key][0] += f2 * lp
                    gm[key][1] += 1
        gm_norm = {k: (v[0] * 1000.0 / max(v[0] for v in gm.values()), v[1])
                   for k, v in gm.items()}
        gmax = max(v[0] for v in gm.values())
        print("      %-9s %-10s %-13s %-8s %-13s %-9s %-9s"
              % ("d", "fastxrd I", "gemmi raw", "mult", "gemmi×mult", "norm(×1000)", "相对差%"))
        rels = []
        for k in range(min(len(dd), 14)):
            dval = round(float(dd[k]), 5)
            if dval not in gm:
                continue
            base, mult = gm[dval]
            gm_mult = base * mult
            gnn = gm_mult * 1000.0 / gmax
            rel = 100.0 * (ii[k] - gnn) / gnn if gnn else float("nan")
            rels.append(rel)
            print("      %-9.4f %-10.1f %-13.1f %-8d %-13.1f %-9.1f %+9.4f"
                  % (dd[k], ii[k], base, mult, gm_mult, gnn, rel))
        if rels:
            print("      -> n=%d 相对差 均值=%+.4f%%  中位=%+.4f%%  min=%+.4f%%  max=%+.4f%%"
                  % (len(rels), float(np.mean(rels)), float(np.median(rels)),
                     min(rels), max(rels)))

    # ── 5c 同一 hkl：|F|² 逐点对比（隔离散射因子表差异） ────────────────────
    print("\n-- 5c 同一 hkl 的 |F|² 对比：fastxrd 公式 vs gemmi StructureFactorCalculatorX --")
    conn = sqlite3.connect("file:%s?mode=ro" % UPSTREAM_DB, uri=True)
    row = conn.execute(
        "SELECT cod_id, formula, space_group, cif_gz FROM phases "
        "WHERE cif_gz IS NOT NULL AND formula LIKE '%F%' AND n_peaks BETWEEN 80 AND 500 "
        "LIMIT 1"
    ).fetchone()
    conn.close()
    if row is None:
        print("   未取到样本")
        return
    cid, formula, sg, gz = row
    text = gzip.decompress(gz).decode("utf-8", "replace")
    d_cif, frac, syms, occs = _refl_from_cif(fastcif, fastxrd, text)
    ss = _gemmi_read_small_structure(gemmi, text)
    ss.setup_cell_images()
    cell = ss.cell
    sfc = gemmi.StructureFactorCalculatorX(cell)
    recip = fastxrd.reciprocal_matrix(d_cif.a, d_cif.b, d_cif.c,
                                      d_cif.alpha, d_cif.beta, d_cif.gamma)
    print("   样本 cod_id=%s %s sg=%s" % (cid, formula, sg))
    print("   gemmi cell: a=%.5f b=%.5f c=%.5f al=%.4f be=%.4f ga=%.4f"
          % (cell.a, cell.b, cell.c, cell.alpha, cell.beta, cell.gamma))
    print("   fastcif cell: a=%.5f b=%.5f c=%.5f al=%.4f be=%.4f ga=%.4f"
          % (d_cif.a, d_cif.b, d_cif.c, d_cif.alpha, d_cif.beta, d_cif.gamma))
    print("   %-12s %-8s %-14s %-14s %-10s %-14s %-10s"
          % ("hkl", "s", "|F|² fastxrd", "|F|² gemmi", "相对差%", "F²·LP fast", "F²·LP gm"))
    for hkl in [(1, 1, 1), (2, 0, 0), (2, 2, 0), (3, 1, 1), (0, 2, 0)]:
        g = np.asarray(hkl, dtype=float) @ recip
        s = float(np.linalg.norm(g) / 2.0)
        # fastxrd 风格 |F|²
        f2_fast = 0.0
        for coord, sp, occ in zip(frac, syms, occs):
            el = sp
            coeffs = fast_tab[el]
            fs = sum(a * math.exp(-b * s * s) for a, b in coeffs)
            f_el = fastxrd._Z[el] - 41.78214 * s * s * fs
            ph = 2.0 * math.pi * float(np.dot(g, coord))
            f2_fast += (f_el * occ) ** 2
        # 交叉项不能丢——用复数求和
        re = 0.0
        im = 0.0
        for coord, el, occ in zip(frac, syms, occs):
            coeffs = fast_tab[el]
            fs = sum(a * math.exp(-b * s * s) for a, b in coeffs)
            f_el = fastxrd._Z[el] - 41.78214 * s * s * fs
            ph = 2.0 * math.pi * float(np.dot(g, coord))
            w = f_el * occ
            re += w * math.cos(ph)
            im += w * math.sin(ph)
        f2_fast = re * re + im * im
        try:
            fg = sfc.calculate_sf_from_small_structure(ss, hkl)
            f2_gem = fg.real ** 2 + fg.imag ** 2
        except Exception as exc:  # noqa: BLE001
            print("   %-12s gemmi 失败: %s" % (str(hkl), exc))
            continue
        d = cell.calculate_d(hkl)
        t = math.asin(min(1.0, WL / (2 * d)))
        lp = (1 + math.cos(2 * t) ** 2) / (math.sin(t) ** 2 * math.cos(t))
        rel = 100.0 * (f2_fast - f2_gem) / f2_gem if f2_gem else float("nan")
        print("   %-12s %-8.4f %-14.4f %-14.4f %+10.4f %-14.4f %-10.4f"
              % (str(hkl), s, f2_fast, f2_gem, rel, f2_fast * lp, f2_gem * lp))

    # ── 5d LP 公式差异（同一 d 下 fastxrd LP vs gemmi 常用 LP） ──────────────
    print("\n-- 5d Lorentz-Polarization 因子对比 --")
    print("   fastxrd: lp = (1+cos^2(2T))/(sin^2(T)*cos(T)),  T=theta")
    print("   gemmi 常用: lp = (1+cos^2(2T))/(sin^2(T)*cos(T))  —— 同式")
    for dval in (3.1535, 1.9311, 1.0640, 0.8):
        t = math.asin(min(1.0, WL / (2 * dval)))
        lp1 = (1 + np.cos(2 * t) ** 2) / (np.sin(t) ** 2 * np.cos(t))
        lp2 = (1 + math.cos(2 * t) ** 2) / (np.sin(t) * np.cos(t) ** 3)  # 另一种等价写法
        print("   d=%-8.4f 2T=%-7.3f  lp(θ) = %.6f   lp 变体 = %.6f   相对差 %+.3e%%"
              % (dval, 2 * np.degrees(t), lp1, lp2,
                 100.0 * (lp1 - lp2) / lp1))


def _gemmi_read_small_structure(gemmi, text: str):
    """gemmi 0.7.5 只提供 ``read_small_structure(path)``，用临时文件喂字符串。

    先尝试 ``read_small_structure_from_string``（新版本），失败则落临时文件。
    """
    fn = getattr(gemmi, "read_small_structure_from_string", None)
    if fn is not None:
        return fn(text)
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".cif", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(text)
        path = fh.name
    try:
        return gemmi.read_small_structure(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _gemmi_it92_f(el: str, s: float):
    """gemmi ITC-1992 原子散射因子 f(s)。

    注意 gemmi 0.7.5 的 ``IT92Coef.calculate_sf(x)`` 内部按 ``exp(-b * x)``
    计算，因此**传入的是 s² 而非 s**（实测：arg=0.04 -> 9.6748 = ITC(s=0.2)）。
    """
    import gemmi
    coef = gemmi.Element(el).it92
    try:
        return coef.calculate_sf(s * s)
    except AttributeError:
        pass
    co = coef.get_coefs()
    a = co[0:4]
    b = co[4:8]
    c = co[8] if len(co) > 8 else 0.0
    return float(sum(ai * math.exp(-bi * s * s) for ai, bi in zip(a, b)) + c)


def json_load(path):
    import json
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ──────────────────────────────────────────────────────────────────────────
# stage 6: raw —— 解剖指定条目的原始峰表，判定存储语义
# ──────────────────────────────────────────────────────────────────────────
def stage_raw(cod_ids=None) -> None:
    _hr("STAGE 6 — 原始峰表解剖（存储语义判定）")
    conn = sqlite3.connect("file:%s?mode=ro" % UPSTREAM_DB, uri=True)
    if not cod_ids:
        cod_ids = [1000043, 1000013, 1000005, 1000017, 1000021]
    for cid in cod_ids:
        row = conn.execute(
            "SELECT cod_id, formula, space_group, cell_a, cell_b, cell_c, "
            "       cell_alpha, cell_beta, cell_gamma, n_peaks, peaks_d, peaks_i, "
            "       peaks_top_d, peaks_top_i, cif_gz "
            "FROM phases WHERE cod_id = ?", (cid,)
        ).fetchone()
        if row is None:
            print("\n### cod_id=%s 不存在" % cid)
            continue
        (cid_, formula, sg, a, b, c, al, be, ga, n_pk, pd_, pi_,
         top_d, top_i, gz) = row
        print("\n" + "=" * 90)
        print("### cod_id=%s  %s  sg=%s  n_peaks=%d" % (cid_, formula, sg, n_pk))
        print("    库内 cell: a=%.5f b=%.5f c=%.5f al=%.4f be=%.4f ga=%.4f"
              % (a, b, c, al, be, ga))
        d = np.fromstring((pd_ or "").replace(",", " "), sep=" ")
        i = np.fromstring((pi_ or "").replace(",", " "), sep=" ")
        print("    len(peaks_d)=%d len(peaks_i)=%d" % (d.size, i.size))
        print("    前 24 条 d: %s" % " ".join("%.4f" % v for v in d[:24]))
        print("    前 24 条 I: %s" % " ".join("%.1f" % v for v in i[:24]))
        if d.size:
            diffs = np.diff(d)
            print("    d 严格非递增: %s" % (bool(np.all(diffs <= 0))))
            print("    d 严格降序  : %s" % (bool(np.all(diffs < 0))))
            ties = np.flatnonzero(diffs == 0)
            print("    相邻等 d 的下标对: %d 个 -> %s"
                  % (ties.size, [(int(t), int(t + 1)) for t in ties[:12]]))
            for t in ties[:6]:
                print("       d[%d]=d[%d]=%.4f  I=%.1f / %.1f"
                      % (t, t + 1, d[t], i[t], i[t + 1]))
            near = np.flatnonzero((diffs < 0) & (diffs > -1e-3))
            print("    相邻近似等 d(差<1e-3 且非零) 的对数: %d" % near.size)
            tt = 2 * np.degrees(np.arcsin(np.clip(WL / (2 * d), -1, 1)))
            print("    前 12 条 2θ: %s" % " ".join("%.4f" % v for v in tt[:12]))
            print("    dmax=%.4f -> 2θ=%.4f ; dmin=%.4f -> 2θ=%.4f"
                  % (d.max(), 2 * math.degrees(math.asin(min(1.0, WL / (2 * d.max())))),
                     d.min(), 2 * math.degrees(math.asin(min(1.0, WL / (2 * d.min()))))))
            print("    Imax=%.1f  Imin=%.1f  I==0 的条数=%d"
                  % (i.max(), i.min(), int((i == 0).sum())))
        if top_d:
            td = np.frombuffer(top_d, dtype=np.float64)
            ti = np.frombuffer(top_i, dtype=np.float64)
            print("    peaks_top_d/i: len=%d/%d  前 10 d: %s"
                  % (td.size, ti.size, " ".join("%.4f" % v for v in td[:10])))
            print("                    前 10 I: %s"
                  % " ".join("%.1f" % v for v in ti[:10]))
            print("    是否为 I 降序 Top-N: %s"
                  % bool(np.all(np.diff(ti) <= 0)))
        if gz:
            try:
                text = gzip.decompress(gz).decode("utf-8", "replace")
                lines = text.splitlines()
                print("    CIF 共 %d 行，_cell / _atom_site 关键行:" % len(lines))
                for ln in lines:
                    ls = ln.strip()
                    low = ls.lower()
                    if (low.startswith("_cell_length") or low.startswith("_cell_angle")
                            or low.startswith("_cell_volume")
                            or low.startswith("_symmetry_space_group_name_h-m")
                            or low.startswith("_symmetry_int_tables_number")
                            or low.startswith("_chemical_formula")):
                        print("      %s" % ls[:110])
                n_atom = sum(1 for ln in lines
                             if ln.strip().startswith("_atom_site_label"))
                print("    _atom_site 标签出现次数: %d" % n_atom)
                for ln in lines[:40]:
                    print("      | %s" % ln[:110])
            except Exception as exc:  # noqa: BLE001
                print("    CIF 读取失败: %s" % exc)
    conn.close()


# ──────────────────────────────────────────────────────────────────────────
# stage 7: cell —— 库内 cell 与 CIF 内 cell 的一致性（cell_fix 影响面）
# ──────────────────────────────────────────────────────────────────────────
def stage_cell(n=2000) -> None:
    _hr("STAGE 7 — 库内晶胞 vs CIF 内晶胞 一致性（cell_fix 影响面）")
    fastcif, fastxrd = _load_ref_tools()
    conn = sqlite3.connect("file:%s?mode=ro" % UPSTREAM_DB, uri=True)
    rows = conn.execute(
        "SELECT cod_id, formula, cell_a, cell_b, cell_c, cell_alpha, cell_beta, "
        "       cell_gamma, cif_gz FROM phases WHERE cif_gz IS NOT NULL "
        "ORDER BY cod_id LIMIT ?", (n,)
    ).fetchall()
    conn.close()
    bad = []
    nparse_fail = 0
    for cid, formula, a, b, c, al, be, ga, gz in rows:
        try:
            text = gzip.decompress(gz).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            nparse_fail += 1
            continue
        try:
            d = fastcif.parse_cif(text)
        except Exception:  # noqa: BLE001
            nparse_fail += 1
            continue
        if not d.ok:
            nparse_fail += 1
            continue
        dif = max(abs(d.a - a), abs(d.b - b), abs(d.c - c),
                  abs(d.alpha - al), abs(d.beta - be), abs(d.gamma - ga))
        if dif > 1e-3:
            bad.append((cid, formula, dif,
                        (a, b, c, al, be, ga), (d.a, d.b, d.c, d.alpha, d.beta, d.gamma)))
    print("   抽样 %d 条；fastcif 解析失败/不 ok %d 条" % (len(rows), nparse_fail))
    print("   晶胞参数与库内记录不一致(>1e-3) 的条目: %d 条 (%.2f%%)"
          % (len(bad), 100.0 * len(bad) / max(1, len(rows))))
    for cid, formula, dif, lib, cif in bad[:20]:
        print("      cod_id=%-9s %-18s maxΔ=%.6g" % (cid, formula, dif))
        print("            库内 : %s" % (" ".join("%.5f" % v for v in lib)))
        print("            CIF内: %s" % (" ".join("%.5f" % v for v in cif)))


# ──────────────────────────────────────────────────────────────────────────
# stage 8: detail —— 逐反射组解剖强度差异来源
# ──────────────────────────────────────────────────────────────────────────
def _f_sq_fastxrd(hkl, frac, syms, occs, fast_tab):
    """按 fastxrd 的公式算某 hkl 的 |F|²（不含 Debye-Waller）。

    注意相位是 ``2*pi*(h*x + k*y + l*z)``（Miller 指数 × 分数坐标），
    **不是** ``2*pi*g·r``（后者量纲不同，会得到完全错误的 F）。
    """
    s2 = 0.25 / float(np.dot(np.asarray(hkl, dtype=float),
                              np.asarray(hkl, dtype=float)))  # 占位，实际用下面重算
    return 0.0, 0.0


def _f_sq_fastxrd2(hkl, recip, frac, syms, occs, fast_tab):
    """fastxrd 公式的 |F|²（相位用 Miller 指数 × 分数坐标）。"""
    hkl = np.asarray(hkl, dtype=float)
    s = float(np.linalg.norm(hkl @ recip) / 2.0)
    s2 = s * s
    re = 0.0
    im = 0.0
    for coord, el, occ in zip(frac, syms, occs):
        coeffs = fast_tab[el]
        fs = sum(a * math.exp(-b * s2) for a, b in coeffs)
        f_el = _FX._Z[el] - 41.78214 * s2 * fs
        ph = 2.0 * math.pi * float(np.dot(hkl, coord))
        w = f_el * occ
        re += w * math.cos(ph)
        im += w * math.sin(ph)
    return re * re + im * im, s


def stage_detail(cod_ids=None) -> None:
    _hr("STAGE 8 — 逐反射组解剖：强度差异来源")
    fastcif, fastxrd = _load_ref_tools()
    import gemmi

    with open(SCAT_JSON, "r", encoding="utf-8") as fh:
        fast_tab = json.load(fh)

    conn = sqlite3.connect("file:%s?mode=ro" % UPSTREAM_DB, uri=True)
    if not cod_ids:
        cod_ids = [1000043, 1000017, 1010369, 1000250]
    for cid in cod_ids:
        row = conn.execute(
            "SELECT cod_id, formula, space_group, cell_a, cell_b, cell_c, n_peaks, "
            "       peaks_d, peaks_i, cif_gz FROM phases WHERE cod_id = ?", (cid,)
        ).fetchone()
        if row is None:
            print("\n### cod_id=%s 不存在" % cid)
            continue
        (cid_, formula, sg, a, b, c, n_pk, pd_, pi_, gz) = row
        d_ref = np.fromstring(pd_.replace(",", " "), sep=" ")
        i_ref = np.fromstring(pi_.replace(",", " "), sep=" ")
        print("\n" + "=" * 100)
        print("### cod_id=%s %s sg=%s n_peaks=%d" % (cid_, formula, sg, n_pk))
        text = gzip.decompress(gz).decode("utf-8", "replace")
        d_cif, frac, syms, occs = _refl_from_cif(fastcif, fastxrd, text)
        print("   fastcif sites: %d 条 (cell a=%.5f b=%.5f c=%.5f al=%.4f be=%.4f ga=%.4f)"
              % (len(syms), d_cif.a, d_cif.b, d_cif.c,
                 d_cif.alpha, d_cif.beta, d_cif.gamma))
        # 打印原始 site（元素/占据/Uiso）
        try:
            for s0 in d_cif.sites[:12]:
                print("      site: %s" % (s0,))
        except Exception:  # noqa: BLE001
            pass

        # E1: fastxrd
        dd1, ii1 = fastxrd.compute_pattern_arrays(
            d_cif.a, d_cif.b, d_cif.c, d_cif.alpha, d_cif.beta, d_cif.gamma,
            frac, syms, occs, wavelength=WL, tth_range=(2.0, 180.0),
            max_peaks=0, scale=1000.0, max_hkl=2000000, half_sphere=False)
        dd1 = np.asarray(dd1)
        ii1 = np.asarray(ii1)

        # gemmi 侧
        ss = _gemmi_read_small_structure(gemmi, text)
        ss.setup_cell_images()
        cell = ss.cell
        sfc = gemmi.StructureFactorCalculatorX(cell)
        print("   gemmi sites: %d 条 (cell a=%.5f b=%.5f c=%.5f al=%.4f be=%.4f ga=%.4f)"
              % (len(ss.sites), cell.a, cell.b, cell.c,
                 cell.alpha, cell.beta, cell.gamma))
        for st in list(ss.sites)[:8]:
            print("      gsite: label=%s el=%s occ=%.4f u_iso=%.5f biso=%.5f"
                  % (st.label, st.element.name, st.occ, st.u_iso,
                     8 * math.pi ** 2 * st.u_iso))

        recip = fastxrd.reciprocal_matrix(d_cif.a, d_cif.b, d_cif.c,
                                          d_cif.alpha, d_cif.beta, d_cif.gamma)
        max_r = 2.0 * math.sin(math.radians(90.0)) / WL
        min_r = 2.0 * math.sin(math.radians(1.0)) / WL
        got = fastxrd._gen_hkl(recip, max_r, min_r, False, 4000000, (a, b, c))
        if got is None:
            print("   hkl 枚举失败（网格过大）")
            continue
        H, G, gabs = got
        dall = 1.0 / gabs
        # 逐个上游 d 求反射组
        rows = []
        for k in range(len(d_ref)):
            dtarget = float(d_ref[k])
            sel = np.flatnonzero(np.abs(dall - dtarget) < 2e-4)
            s1 = 0.0
            s2 = 0.0
            det = []
            for idx in sel:
                hkl = tuple(int(v) for v in H[idx])
                dval = float(dall[idx])
                t = math.asin(min(1.0, WL / (2 * dval)))
                lp = (1 + math.cos(2 * t) ** 2) / (math.sin(t) ** 2 * math.cos(t))
                f2f, _s = _f_sq_fastxrd(hkl, recip, frac, syms, occs, fast_tab)
                s1 += f2f * lp
                fg = sfc.calculate_sf_from_small_structure(ss, hkl)
                f2g = fg.real ** 2 + fg.imag ** 2
                det.append((hkl, f2f, f2g))
                s2 += f2g * lp
            rows.append((dtarget, float(i_ref[k]), int(sel.size), s1, s2, det))
        m1 = max((r[3] for r in rows), default=0.0)
        m2 = max((r[4] for r in rows), default=0.0)
        print("\n   %-9s %-6s | %-10s %-12s %-12s %-10s %-10s"
              % ("d_up", "n_hkl", "I_up", "E1 fastxrd", "E2 gemmi", "E1/E2", "I_up/E1"))
        for (dtarget, iu, nh, s1, s2, _det) in rows[:24]:
            e1 = 1000.0 * s1 / m1 if m1 else 0.0
            e2 = 1000.0 * s2 / m2 if m2 else 0.0
            print("   %-9.4f %-6d | %-10.1f %-12.2f %-12.2f %-10.4f %-10.4f"
                  % (dtarget, nh, iu, e1, e2,
                     (s1 / s2) if s2 else float("nan"),
                     (iu / e1) if e1 else float("nan")))
        for (dtarget, iu, nh, s1, s2, det) in rows[:2]:
            print("   -- d=%.4f 逐 hkl (|F|² fastxrd vs gemmi) --" % dtarget)
            for (hkl, f2f, f2g) in det[:10]:
                print("      %-12s |F|²_fast=%-18.6f |F|²_gemmi=%-18.6f  比=%s"
                      % (str(hkl), f2f, f2g,
                         ("%.6f" % (f2f / f2g)) if f2g else "n/a"))
        # fastxrd 整表归一化后的最强线对照
        if dd1.size:
            print("   fastxrd(E1) 整表: 峰数=%d  最强 d=%.4f I=%.1f"
                  % (dd1.size, dd1[int(np.argmax(ii1))], ii1.max()))
    conn.close()


# ──────────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", default="all",
                    choices=["all", "meta", "stats", "match", "robust", "gemmi",
                             "raw", "cell", "detail"])
    ap.add_argument("--entries", type=int, default=16)
    ap.add_argument("--robust-n", type=int, default=200)
    ap.add_argument("--cod-ids", default="",
                    help="raw / detail stage 用，逗号分隔的 cod_id")
    ap.add_argument("--cell-n", type=int, default=2000)
    args = ap.parse_args(argv)

    cod_ids = [int(x) for x in args.cod_ids.split(",") if x.strip()] or None
    stages = {
        "meta": lambda: stage_meta(),
        "stats": lambda: stage_stats(),
        "match": lambda: stage_match(args.entries),
        "robust": lambda: stage_robust(args.robust_n),
        "gemmi": lambda: stage_gemmi_diff(),
        "raw": lambda: stage_raw(cod_ids),
        "cell": lambda: stage_cell(args.cell_n),
        "detail": lambda: stage_detail(cod_ids),
    }
    if args.stage == "all":
        for fn in stages.values():
            try:
                fn()
            except Exception:  # noqa: BLE001
                traceback.print_exc()
    else:
        stages[args.stage]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
