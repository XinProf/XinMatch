"""Generate synthetic powder XRD patterns (2-col ASCII) with known ground truth.

Purpose
-------
扩充基线样品集（T0.3/T0.4）：生成 13 个"真相已知"的合成混合物谱，
供在参考软件中以 SMPF 流程人工检索对照，严格检验检索一致率。

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
import sqlite3
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.build_cod_full_xinmatch import compute_peaks_from_cif  # noqa: E402
from xinmatch.core.refine.cif_store import cod_cif_path  # noqa: E402

COD_INDEX = Path(r"D:\Project\XRD\PolyXRD\cod_data\cod_index.sqlite")
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
    ("Zirconia", [(2101234, 1.00, (-1, 1, 1))]),
]


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
    return max(f, 0.03)


def _march_factor(tth: np.ndarray, tth0: float, r: float) -> np.ndarray:
    """Simplified March-Dollase for a preferred (00l) axis (raw multiplier)."""
    if r <= 1e-9:
        return np.ones_like(tth)
    alpha = np.radians(tth - tth0)
    ca = np.cos(alpha)
    ca = np.where(np.abs(alpha) < 1.4, ca, 1e-9)
    return (r**3 + (1.0 / r - 1.0) * ca * ca) ** -1.5


def _pattern_for_phase(d, i, rng: np.random.Generator, po_hkl: tuple | None) -> np.ndarray:
    """Convolve d/I sticks into the 2θ grid with pseudo-Voigt shapes.

    各相峰强度先按自身最强峰归一化（相对强度 0–100），再乘质量分数叠加，
    使混合谱的主相主导、峰型比例接近真实混合物。
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
    if len(d) == 0:
        return np.zeros_like(TWO_THETA)
    imax = i.max()
    if imax <= 0:
        return np.zeros_like(TWO_THETA)
    i = i / imax
    out = np.zeros_like(TWO_THETA)
    for x0, i0 in zip(tth0, i, strict=True):
        fwhm = _fwhm(x0)
        eta = 0.4 + 0.3 * rng.random()
        near = np.abs(TWO_THETA - x0) <= 5.0 * fwhm
        if not near.any():
            continue
        vals = np.array([_pseudovoigt(x, x0, fwhm, eta) for x in TWO_THETA[near]])
        if po_hkl is not None:
            # preferred orientation: enhance near-axis peaks modestly (r=0.75)
            vals = vals * _march_factor(TWO_THETA[near], x0, 0.75)
        # 相对强度（0–100）× 峰形中心值 → 峰高显著高于背底（×40 放大）。
        out[near] += (i0 * 100.0 * 0.4) * vals
    return out


def _background(tth: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Low, slowly-varying background (~1-2% of peak height)."""
    a, b, c = rng.uniform(0.8, 2.5), rng.uniform(-0.004, 0.002), rng.uniform(0.0, 2e-5)
    return a + b * (tth - 50.0) + c * (tth - 50.0) ** 2


def _build_sample(label: str, phases: list[tuple[int, float, tuple | None]],
                  rng: np.random.Generator, noise_scale: float = 0.012) -> dict:
    """Build one synthetic sample; returns pattern + phase truth."""
    pattern = np.zeros_like(TWO_THETA)
    truth: list[dict] = []
    for cod_id, wt, po_hkl in phases:
        cif = cod_cif_path(cod_id)
        if not cif.is_file():
            raise RuntimeError(f"no COD CIF for cod_id={cod_id} ({cif})")
        peaks = compute_peaks_from_cif(cif, dmin=0.7, max_peaks=120)
        if peaks is None:
            raise RuntimeError(f"no peaks from {cif}")
        d, i = peaks
        pattern += wt * _pattern_for_phase(d, i, rng, po_hkl)
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
    ap.add_argument("--noise-scale", type=float, default=0.012,
                    help="高斯噪音幅度（相对最强峰），默认 0.012；低噪音对照可用 0.003")
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
            "`<2Theta> <I>` 表头，行宽 81 对齐实测样本），可直接在参考软件中导入并跑 SMPF；"
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
