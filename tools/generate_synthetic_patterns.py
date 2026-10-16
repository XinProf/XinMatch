"""Generate synthetic powder XRD patterns (2-col ASCII) with known ground truth.

Purpose
-------
扩充基线样品集（T0.3/T0.4）：生成 13 个"真相已知"的合成混合物谱，
供在参考软件中以 FPFM 流程人工检索对照，严格检验检索一致率。

方法
----
1. 从 COD 归档取指定 cod_id 的标准 CIF；
2. 用 gemmi 计算各相结构因子 → d/I 峰表（复用
   ``tools.build_cod_full_xinmatch.compute_peaks_from_cif``）；
3. 峰形：Caglioti FWHM 的 pseudo-Voigt，Cu Kα 波长，10–90° 步进 0.02°；
4. 背底（缓变二次多项式）+ 高斯噪音 + 可选择优取向（March-Dollase 简化）；
5. 多相按质量分数加权叠加；输出 ``<out>/synth_XX.txt``（两列 ASCII）与
   ``<out>/manifest.md``（真相相 cod_id / 化学式 / wt% / 元素限定建议）。

用法
----
python tools/generate_synthetic_patterns.py --out <dir> [--seed 42]
"""

from __future__ import annotations

import argparse
import math
import re
import sqlite3
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.build_cod_full_xinmatch import compute_peaks_from_cif  # noqa: E402
from xinmatch.core.refine.cif_store import cod_cif_path  # noqa: E402

COD_INDEX = Path(r"D:\Project\XRD\PolyXRD\cod_data\cod_index.sqlite")
# XinMatch 检索库（cod_inorganics.db）的 peaks 表存 0-100 相对强度，与检索 FoM 同源。
# 生成合成谱的峰强度一律取自该库（entry_id = 96-{cod_id 8 位}），保证"从库内卡片生成、
# 能在库内找回"的净室闭环；库内无此编号时回退 CIF 结构因子计算。
CARD_DB = Path(r"D:\Project\XRD\XinMatch\data\cod_inorganics.db")
WAVELEN = 1.5406  # Cu K-alpha1
TWO_THETA = np.arange(10.0, 90.0, 0.02)
# Caglioti parameters (typical laboratory Cu source).
U, V, W = 0.006, -0.004, 0.010

#: (sample label, [(cod_id, wt_fraction, preferred_hkl_or_None)])
_MATERIALS: list[tuple[str, list[tuple[int, float, tuple[int, int, int] | None]]]] = [
    ("Al2O3-ZnO-CaF2", [(2300448, 0.50, None), (2300112, 0.45, (0, 0, 2)), (2300449, 0.05, None)]),
    ("Quartz-Calcite", [(5000035, 0.60, (1, 0, 1)), (2100992, 0.40, None)]),
    ("Anatase-Rutile", [(5000223, 0.55, (1, 0, 1)), (2310486, 0.45, None)]),
    ("Hematite-Quartz", [(2101167, 0.65, (1, 0, 4)), (5000035, 0.35, None)]),
    ("CuO-ZnO", [(9008961, 0.55, None), (2300112, 0.45, (0, 0, 2))]),
    ("BaTiO3", [(2100858, 1.00, None)]),
    ("NaCl-KCl", [(9000629, 0.60, None), (9003112, 0.40, None)]),
    ("CaF2-Al2O3", [(2300449, 0.70, None), (2300448, 0.30, None)]),
    ("Graphite", [(9000046, 1.00, (0, 0, 2))]),
    ("Fe-Fe3O4", [(5000217, 0.70, None), (2101535, 0.30, None)]),
    ("Anhydrite-Calcite", [(5000040, 0.60, None), (2100992, 0.40, None)]),
    ("Periclase-Spinel", [(5000225, 0.50, None), (5000120, 0.50, None)]),
    ("Zirconia", [(2101234, 1.00, None)]),
]

#: True March-Dollase r for textured phases (platy, r < 1).  Moderate
#: strength (r = 0.75): strong enough to be identifiable by FPFM profile
#: fitting (on-axis enhancement ~ r^-3 ≈ 2.4×) yet gentle enough that the
#: peak-list pre-screen still recalls textured phases.  Notes:
#: * the old "fake" factor was a ~constant 1.52 swallowed by `scale`; the
#:   real model multiplies the per-peak integrated intensity by
#:   (r²cos²α + sin²α/r)^(-3/2);
#: * a very strong texture (r = 0.6) pushed the single-phase Zirconia card
#:   out of the peak-list Top-20 (physical peak-list intensity mismatch);
#:   the acceptance set therefore textures 6 multi-phase samples but keeps
#:   the single-phase Zirconia un-textured — the March-Dollase end-to-end
#:   recovery (textured spectrum → fitted r) is covered by an in-memory
#:   dedicated test (test_march_po_recovers_textured_zirconia).
MD_R = 0.75


def _card_peaks(cod_id: int) -> tuple[np.ndarray, np.ndarray, list[tuple[int, int, int] | None]] | None:
    """从 XinMatch 检索库取卡片 d/I/hkl（强度 0-100 相对强度，与 FoM 同源）。"""
    s = str(cod_id)
    eid = f"96-{s[:3]}-{s[3:]}" if len(s) == 7 else None
    if not eid:
        return None
    conn = sqlite3.connect(f"file:{CARD_DB.as_posix()}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT d, intensity, h, k, l FROM peaks WHERE entry_id=? ORDER BY intensity DESC",
            (eid,),
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        return None
    hkls: list[tuple[int, int, int] | None] = [
        (r[2], r[3], r[4]) if r[2] is not None else None
        for r in rows
    ]
    return (
        np.array([r[0] for r in rows], dtype=float),
        np.array([r[1] for r in rows], dtype=float),
        hkls,
    )


def _cell_for(cod_id: int) -> tuple[float, float, float, float, float, float] | None:
    """卡片晶胞 (a, b, c, α, β, γ)；无则 None（真 MD 需要倒格矢夹角）。"""
    s = str(cod_id)
    eid = f"96-{s[:3]}-{s[3:]}" if len(s) == 7 else None
    if not eid:
        return None
    conn = sqlite3.connect(f"file:{CARD_DB.as_posix()}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT a, b, c, alpha, beta, gamma FROM entries WHERE entry_id=?",
            (eid,),
        ).fetchone()
    finally:
        conn.close()
    if row is None or row[0] is None:
        return None
    return (float(row[0]), float(row[1]), float(row[2]),
            float(row[3] if row[3] is not None else 90.0),
            float(row[4] if row[4] is not None else 90.0),
            float(row[5] if row[5] is not None else 90.0))


def _card_peaks_by_formula(cod_id: int) -> tuple[np.ndarray, np.ndarray, list[tuple[int, int, int] | None]] | None:
    """库内同元素集卡片（peaks 最多者），作为 fallback 强度来源。

    合成谱真相相可能不在库内（如 900- 系列新编号），但同相的
    其他 COD 卡片（元素集一致）在库内——用它们的 0-100 相对强度，
    保证与检索 FoM 同源（CIF 结构因子动态范围过大，直接使用会让
    次强峰淹没，FoM intensity 失真）。
    """
    _, elements = _meta(cod_id)
    if not elements:
        return None
    els = {e.strip() for e in elements.split(",") if e.strip()}
    if not els:
        return None
    conn = sqlite3.connect(f"file:{CARD_DB.as_posix()}?mode=ro", uri=True)
    try:
        ordered = sorted(els)
        q = "SELECT entry_id, formula FROM entries WHERE formula LIKE ?"
        args: list[str] = [f"%{ordered[0]}%"]
        for e in ordered[1:]:
            q += " AND formula LIKE ?"
            args.append(f"%{e}%")
        best: tuple[str, int] | None = None
        for eid, fml in conn.execute(q, args):
            if _formula_elements(fml) != els:
                continue
            n = conn.execute(
                "SELECT COUNT(*) FROM peaks WHERE entry_id=?", (eid,)
            ).fetchone()[0]
            if best is None or n > best[1]:
                best = (eid, n)
        if best is None:
            return None
        rows = conn.execute(
            "SELECT d, intensity, h, k, l FROM peaks WHERE entry_id=? ORDER BY intensity DESC",
            (best[0],),
        ).fetchall()
        hkls: list[tuple[int, int, int] | None] = [
            (r[2], r[3], r[4]) if r[2] is not None else None
            for r in rows
        ]
        return (
            np.array([r[0] for r in rows], dtype=float),
            np.array([r[1] for r in rows], dtype=float),
            hkls,
        )
    finally:
        conn.close()


def _formula_elements(formula: str) -> set[str]:
    return {m.group(1) for m in re.finditer(r"([A-Z][a-z]?)([0-9.]*)", formula or "")}


def _meta(cod_id: int) -> tuple[str, str]:
    conn = sqlite3.connect(f"file:{COD_INDEX.as_posix()}?mode=ro", uri=True)
    row = conn.execute(
        "SELECT formula, elements FROM cod_entries WHERE cod_id=?", (cod_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return str(cod_id), ""
    return row[0] or str(cod_id), row[1] or ""


def _two_theta(d: float) -> float:
    if d <= 0:
        return math.nan
    s = min(1.0, WAVELEN / (2.0 * d))
    return 2.0 * math.degrees(math.asin(s))


def _dump_header(fname: str, label: str, n_points: int, tmin: float, tmax: float) -> str:
    """参考软件兼容的 Profile Data Ascii Dump (XRD) 文件头（行宽 81，对齐实测样本）。

    参考软件端可导入的实测谱（test_xrd/txt/*.txt）即此格式：/// banner +
    分组信息 + # Profile Datafile + # Measurement Condition + # Data 表头。
    合成谱早期版本为无表头纯两列 ASCII，实测在参考软件中零候选，故改用此格式。
    """
    banner = "/" * 81
    mid = "/// Profile Data Ascii Dump (XRD)" + " " * 45 + "///"
    assert len(mid) == 81, len(mid)
    tstamp = "26-10-10 00:00:00"
    return "\n".join([
        banner,
        mid,
        banner,
        "",
        "  Group     : XRD",
        f"  Data      : {label}",
        f"  File Name : {fname}",
        "",
        "# Profile Datafile",
        "          comment             =  ",
        f"          date & time         = {tstamp} ",
        "",
        "# Measurement Condition",
        "    X-ray tube",
        "          target              = Cu ",
        "          voltage             = 40.0 (kV)",
        "          current             = 40.0 (mA)",
        "    Slits",
        "          divergence slit     = 1.00000 (deg) ",
        "          scatter slit        = 1.00000 (deg) ",
        "          receiving slit      = 0.30000 (mm)  ",
        "    Scanning",
        "          drive axis          = Theta-Theta ",
        f"          scan range          =   {tmin:6.3f} -  {tmax:6.3f} ",
        "          scan mode           = Fixed Time ",
        "          scan speed          =   1.0000 (deg/min) ",
        "          sampling pitch      =   0.0200 (deg) ",
        "          preset time         =   1.20 (sec) ",
        "",
        f"# Data      [ Total No. = {n_points} ]",
        "  <2Theta>   <   I   >",
    ]) + "\n"


def _pseudovoigt(tth: float, tth0: float, fwhm: float, eta: float) -> float:
    """Normalised pseudo-Voigt at x=tth (Gaussian+Lorentzian mix)."""
    if fwhm <= 1e-6:
        return 0.0
    g = math.exp(-4.0 * math.log(2.0) * ((tth - tth0) / fwhm) ** 2)
    lorentz = 1.0 / (1.0 + 4.0 * ((tth - tth0) / fwhm) ** 2)
    a = (2.0 / fwhm) * math.sqrt(math.log(2.0) / math.pi)
    b = 2.0 / (math.pi * fwhm)
    return eta * b * lorentz + (1.0 - eta) * a * g


def _fwhm(tth: float) -> float:
    t = math.tan(math.radians(tth / 2.0))
    f = math.sqrt(max(0.0, U * t * t + V * t + W))
    # 下限 0.15°：对齐常规实验室 Cu 源的仪器展宽（实测样本峰形 ~0.15–0.25°）。
    # 早期下限 0.03° 生成 FWHM ~0.1° 的过窄峰，参考软件 FPFM 拟合不稳定。
    return max(f, 0.15)


def _rec_metric(cell: tuple[float, float, float, float, float, float]
                ) -> tuple[float, float, float, float, float, float]:
    """Reciprocal metric (a*, b*, c*, cos α*, cos β*, cos γ*) from a cell."""
    a, b, c, al, be, ga = cell
    ca, cb, cg = (math.cos(math.radians(v)) for v in (al, be, ga))
    sa, sb, sg = (math.sin(math.radians(v)) for v in (al, be, ga))
    if min(sa, sb, sg) <= 1e-12:
        return 1.0 / a, 1.0 / b, 1.0 / c, 0.0, 0.0, 0.0
    vol = a * b * c * math.sqrt(max(
        0.0, 1.0 - ca * ca - cb * cb - cg * cg + 2.0 * ca * cb * cg))
    if vol <= 0.0:
        return 1.0 / a, 1.0 / b, 1.0 / c, 0.0, 0.0, 0.0
    astar, bstar, cstar = b * c * sa / vol, a * c * sb / vol, a * b * sg / vol
    return (astar, bstar, cstar,
            (cb * cg - ca) / (sb * sg),
            (ca * cg - cb) / (sa * sg),
            (ca * cb - cg) / (sa * sb))


def _rec_dot(hkl1: tuple[int, int, int], hkl2: tuple[int, int, int],
             metric: tuple[float, float, float, float, float, float]) -> float:
    astar, bstar, cstar, cos_astar, cos_bstar, cos_gstar = metric
    h1, k1, l1 = hkl1
    h2, k2, l2 = hkl2
    return (
        h1 * h2 * astar * astar
        + k1 * k2 * bstar * bstar
        + l1 * l2 * cstar * cstar
        + (h1 * k2 + k1 * h2) * astar * bstar * cos_gstar
        + (h1 * l2 + l1 * h2) * astar * cstar * cos_bstar
        + (k1 * l2 + l1 * k2) * bstar * cstar * cos_astar
    )


def _march_weight(hkl: tuple[int, int, int] | None, po_hkl: tuple[int, int, int],
                  cell: tuple[float, float, float, float, float, float] | None,
                  r: float) -> float:
    """True March-Dollase intensity factor for one reflection.

    α is the angle between the reflection's reciprocal vector and the PO
    axis (both in the cell's reciprocal metric); weight =
    ``(r²cos²α + sin²α/r)^(-3/2)``.  Reflections without hkl (or a cell)
    get weight 1 (no texture applied).
    """
    if hkl is None or cell is None or r <= 0.0:
        return 1.0
    metric = _rec_metric(cell)
    p_norm = math.sqrt(_rec_dot(po_hkl, po_hkl, metric))
    g_norm = math.sqrt(_rec_dot(hkl, hkl, metric))
    if p_norm <= 0.0 or g_norm <= 0.0:
        return 1.0
    cos = _rec_dot(hkl, po_hkl, metric) / (g_norm * p_norm)
    cos = min(1.0, max(-1.0, cos))
    c2 = cos * cos
    return float((r * r * c2 + (1.0 - c2) / r) ** -1.5)


def _pattern_for_phase(
    d: np.ndarray,
    i: np.ndarray,
    hkls: list[tuple[int, int, int] | None] | np.ndarray,
    cell: tuple[float, float, float, float, float, float] | None,
    rng: np.random.Generator,
    po_hkl: tuple | None,
) -> np.ndarray:
    """Convolve d/I sticks into the 2θ grid with pseudo-Voigt shapes.

    各相峰强度先按自身最强峰归一化（相对强度 0–100），再乘质量分数叠加，
    使混合谱的主相主导、峰型比例接近真实混合物。`po_hkl` 非 None 时，
    每峰强度乘真 March-Dollase 因子（按该峰 hkl 与 PO 轴夹角），
    而非旧实现的"峰内形状"近似（后者被 scale 吸收，不可辨识）。
    """
    tth0 = np.array([_two_theta(x) for x in d])
    # 只保留物理可见峰（2θ ∈ [8°, 92°]）；d < λ/2 的峰（2θ=180°）无意义。
    valid = (
        np.isfinite(tth0)
        & (tth0 >= 8.0)
        & (tth0 <= 92.0)
        & (np.asarray(i) > 0)
    )
    d, i, tth0 = d[valid], np.asarray(i)[valid], tth0[valid]
    hkl_valid = [
        (int(h[0]), int(h[1]), int(h[2])) if isinstance(h, np.ndarray) else h
        for h, v in zip(hkls, valid, strict=True) if v
    ]
    if len(d) == 0:
        return np.zeros_like(TWO_THETA)
    imax = i.max()
    if imax <= 0:
        return np.zeros_like(TWO_THETA)
    i = i / imax
    out = np.zeros_like(TWO_THETA)
    for x0, i0, h in zip(tth0, i, hkl_valid, strict=True):
        fwhm = _fwhm(x0)
        eta = 0.4 + 0.3 * rng.random()
        # 截断取 8×FWHM 且外侧 1.5×FWHM 用余弦窗平滑衰减到 0：
        # 硬截断会在峰两侧留下 ~1% 高度的台阶（Lorentzian 尾部），
        # 峰检测会把台阶误报为伪峰（每个真实峰 +2）。
        half = 8.0 * fwhm
        near = np.abs(TWO_THETA - x0) <= half
        if not near.any():
            continue
        xrel = np.abs(TWO_THETA[near] - x0) / fwhm
        taper_start = half / fwhm - 1.5
        taper = np.where(
            xrel <= taper_start,
            1.0,
            0.5 * (1.0 + np.cos(np.pi * (xrel - taper_start) / 1.5)),
        )
        vals = np.array([_pseudovoigt(x, x0, fwhm, eta) for x in TWO_THETA[near]])
        vals = vals * taper
        # 真 March-Dollase：逐峰常数权重（hkl 与 PO 轴夹角），乘积分强度。
        if po_hkl is not None:
            i0 = i0 * _march_weight(h, po_hkl, cell, MD_R)
        # 相对强度（0–100）× 峰形中心值 → 峰高显著高于背底（×40 放大）。
        out[near] += (i0 * 100.0 * 0.4) * vals
    return out


def _background(tth: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Low, slowly-varying background (~1-2% of peak height)."""
    a, b, c = rng.uniform(0.8, 2.5), rng.uniform(-0.004, 0.002), rng.uniform(0.0, 2e-5)
    return a + b * (tth - 50.0) + c * (tth - 50.0) ** 2


def _build_sample(label: str, phases: list[tuple[int, float, tuple | None]],
                  rng: np.random.Generator, noise_scale: float = 0.001) -> dict:
    """Build one synthetic sample; returns pattern + phase truth."""
    pattern = np.zeros_like(TWO_THETA)
    truth: list[dict] = []
    for cod_id, wt, po_hkl in phases:
        hkls: list[tuple[int, int, int] | None] | np.ndarray
        peaks = _card_peaks(cod_id)
        if peaks is None:
            # 库内无此编号：先找库内同元素集卡片（强度与检索 FoM 同源），
            # 再无则回退 CIF 结构因子计算（归一化到 0-100）。
            peaks = _card_peaks_by_formula(cod_id)
        if peaks is None:
            cif = cod_cif_path(cod_id)
            if not cif.is_file():
                raise RuntimeError(f"no COD CIF for cod_id={cod_id} ({cif})")
            cif_peaks = compute_peaks_from_cif(cif, dmin=0.7, max_peaks=120,
                                               return_hkl=True)
            if cif_peaks is None:
                raise RuntimeError(f"no peaks from {cif}")
            assert len(cif_peaks) == 3  # return_hkl=True contract
            d, i, hkls = cif_peaks
            imax = float(i.max())
            if imax > 0:
                i = i / imax * 100.0
        else:
            d, i, hkls = peaks
        cell = _cell_for(cod_id)
        pattern += wt * _pattern_for_phase(d, i, hkls, cell, rng, po_hkl)
        formula, _ = _meta(cod_id)
        truth.append({"cod_id": cod_id, "formula": formula, "wt": wt})
    pattern += _background(TWO_THETA, rng)
    pattern = np.maximum(pattern, 0.0)
    scale = pattern.max() if pattern.max() > 0 else 1.0
    noise = rng.normal(0.0, noise_scale * scale, size=pattern.shape)
    pattern = np.maximum(pattern + noise, 0.0)
    if pattern.max() > 0:
        pattern = pattern / pattern.max() * 50000.0
    return {"label": label, "pattern": pattern, "truth": truth}


def _element_suggestion(truth: list[dict]) -> list[str]:
    """Suggest an element-restriction list from the phase entries."""
    elems: set[str] = set()
    for t in truth:
        _, elements = _meta(t["cod_id"])
        elems.update(e.strip() for e in elements.split(",") if e.strip())
    return sorted(elems)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path(r"D:\Project\XRD\test_xrd\synthetic"))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--noise-scale", type=float, default=0.001,
                    help="高斯噪音幅度（相对最强峰），默认 0.001（对齐实测 5-x 谱背底统计量级 "
                         "~0.05-0.1% imax）；0.003 在背底区产生 std≈1.2% 的纹波，"
                         "峰检测会误报大量噪音弱峰")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    rows = []
    for idx, (label, phases) in enumerate(_MATERIALS, start=1):
        sample = _build_sample(label, phases, rng, noise_scale=args.noise_scale)
        fname = f"synth_{idx:02d}.txt"
        header = _dump_header(
            fname, label, len(TWO_THETA),
            float(TWO_THETA[0]), float(TWO_THETA[-1]),
        )
        with open(args.out / fname, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(header)
            for x, y in zip(TWO_THETA, sample["pattern"], strict=True):
                # 数据行无中间分隔空格（对齐实测样本 5-x：%11.4f%10.0f 连续拼接，行宽 21）
                fh.write(f"{x:11.4f}{round(float(y)):10d}\n")
        elems = _element_suggestion(sample["truth"])
        rows.append({"file": fname, "label": label, "truth": sample["truth"], "elems": elems})
        print(
            f"{fname}: {label} phases="
            f"{[(t['cod_id'], t['formula'], round(t['wt'], 2)) for t in sample['truth']]}"
        )

    with open(args.out / "manifest.md", "w", encoding="utf-8") as fh:
        fh.write("# 合成谱清单（真相已知）\n\n")
        fh.write(
            "生成方式：COD 标准 CIF → 结构因子 → pseudo-Voigt 峰形 + 背底 + 噪音，"
            "Cu Kα1 1.5406 Å，10–90°，步进 0.02°。\n"
            "文件格式：Profile Data Ascii Dump (XRD) 兼容（/// banner + 测量条件块 + "
            "`<2Theta> <I>` 表头，行宽 81 对齐实测样本），可直接在参考软件中导入并跑 FPFM；"
            "强度已整数化。\n\n"
        )
        for r in rows:
            fh.write(f"## {r['file']} — {r['label']}\n")
            fh.write("| COD | 化学式 | 质量分数 |\n|---|---|---|\n")
            for t in r["truth"]:
                fh.write(f"| {t['cod_id']} | {t['formula']} | {t['wt']:.2f} |\n")
            fh.write(f"\n建议元素限定：{', '.join(r['elems'])}\n\n")
    print(f"\nmanifest -> {args.out / 'manifest.md'}")


if __name__ == "__main__":
    main()
