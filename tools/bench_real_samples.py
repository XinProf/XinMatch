"""Benchmark search-match on the **13 real measured samples** (L3 golden set, T6).

Complements :mod:`tools.bench_pattern_set` (synthetic mixtures) and
:mod:`tools.run_acceptance` (curated hand-built reference DB).  Here the
patterns are real laboratory scans and the reference database is a production
``.xinDB`` library, so the numbers describe what a user actually gets.

Ground truth
------------
``D:\\Project\\XRD\\test_xrd\\物相结果+wt%.txt`` names the phases by mineral
name; a name cannot be matched against a card, so the truth is carried as a
**composition ratio** (COD writes formulas per unit cell, so the ratio — not
the absolute count — is the comparable quantity).  Matching therefore happens
at *composition level*: quartz/cristobalite count as one truth phase, and
doped solid solutions cannot be represented at all.  Both limits are listed in
:data:`EXCLUDED` / :data:`NOTES` and repeated in the report, rather than being
silently folded into the score.

Usage::

    python -m tools.bench_real_samples \
        --patterns D:\\Project\\XRD\\test_xrd\\txt \
        --library D:\\Project\\XRD\\XinMatch-DataBase\\data\\COD-Inorg-20261020.xinDB \
        --out .scratch/bench_real_cod.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from xinmatch.core.db.reader_v3 import XinDBReader
from xinmatch.core.io import load_pattern
from xinmatch.core.model import Entry
from xinmatch.core.peak.peak_search import find_peaks
from xinmatch.core.preprocess.auto_pipeline import auto_process
from xinmatch.core.search.fom import CandidateResult
from xinmatch.core.search.phase_key import group_same_phase, same_phase
from xinmatch.core.search.search_match import search_match
from xinmatch.core.search.sequential import SequentialIdentifier, search_residual

#: sample → [(label, formula-ratio string)]，真相来自 `物相结果+wt%.txt`
TRUTH: dict[str, list[tuple[str, str]]] = {
    "1-1": [("LiFePO4", "Fe Li O4 P")],
    "1-2": [],  # NCM811 —— 掺杂固溶体，见 EXCLUDED
    "2-1": [("ZnO", "O Zn"), ("CaCO3", "C Ca O3")],
    # 组成级口径：锐钛矿 / 金红石都是 TiO2，不在此层区分
    "2-2": [("TiO2", "O2 Ti")],
    "3-1": [("ZnO", "O Zn"), ("Al2O3", "Al2 O3"), ("CaF2", "Ca F2")],
    # 非晶不计入分母
    "3-2": [("ZnO", "O Zn"), ("Al2O3", "Al2 O3"), ("CaF2", "Ca F2")],
    "4-1": [("ZnO", "O Zn"), ("Al2O3", "Al2 O3"), ("CaF2", "Ca F2"),
            ("Brucite", "H2 Mg O2")],
    # 石英 / 方石英同为 SiO2
    "5-1": [("SiO2", "O2 Si"), ("CaCO3", "C Ca O3"), ("Magnesite", "C Mg O3"),
            ("Dolomite", "C2 Ca Mg O6")],
    "5-2": [("SiO2", "O2 Si"), ("CaCO3", "C Ca O3"), ("Hematite", "Fe2 O3"),
            ("Muscovite", "Al3 H2 K O12 Si3")],
    "5-2b": [("SiO2", "O2 Si"), ("CaCO3", "C Ca O3"), ("Hematite", "Fe2 O3"),
             ("Muscovite", "Al3 H2 K O12 Si3")],
    "5-3": [("SiO2", "O2 Si"), ("Gehlenite", "Al2 Ca2 O7 Si"),
            ("Fluorapatite", "Ca5 F O12 P3"), ("Goethite", "H Fe O2"),
            ("Kaolinite", "Al2 H4 O9 Si2")],
    "7-1": [("SiO2", "O2 Si"), ("Boehmite", "H Al O2"), ("TiO2", "O2 Ti"),
            ("Goethite", "H Fe O2"), ("Kaolinite", "Al2 H4 O9 Si2"),
            ("Gibbsite", "Al H3 O3"), ("Hematite", "Fe2 O3")],
    "7-2": [("SiO2", "O2 Si"), ("Feldspar", "Al K O8 Si3"),
            ("Albite", "Al Na O8 Si3"), ("Clinochlore", "Al2 H8 Mg5 O18 Si3"),
            ("Zircon", "O4 Si Zr")],
}

#: 无法用组成表示的真值（不进分母，也不假装命中）
EXCLUDED: dict[str, str] = {
    "1-2": "NCM811 Li(Ni0.8Co0.1Mn0.1)O2 —— 掺杂固溶体，库内各卡的元素集互不相同",
    "7-2/Biotite": "K(Mg,Fe)3AlSi3O10(OH)2 —— 固溶体，Mg/Fe 比随卡片变化",
    "7-2/Hornblende": "角闪石 —— 固溶体，元素集随卡片变化",
}

NOTES = (
    "组成级口径：同组成的多晶型（石英/方石英、锐钛矿/金红石）合并为一个真值相；"
    "掺杂固溶体无法表示，已列入 EXCLUDED 且不计入相召回分母。"
)


def _truth_entry(label: str, formula: str) -> Entry:
    """Truth phase as an Entry carrying **only** a formula (no cell).

    ``same_phase`` then falls back to the composition-ratio rule, which is the
    only thing a mineral name can honestly claim to know.
    """
    return Entry(
        entry_id=f"truth:{label}",
        formula=formula,
        d_spacings=np.zeros(0, dtype=float),
        intensities=np.zeros(0, dtype=float),
    )


def _hit(cand: CandidateResult, truths: list[Entry]) -> bool:
    return any(same_phase(cand.entry, t) for t in truths)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patterns", type=Path, required=True)
    ap.add_argument("--library", type=Path, required=True)
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--rounds", type=int, default=3,
                    help="序贯确认轮数（0 = 只跑整谱检索）")
    ap.add_argument("--raw-peaks", action="store_true",
                    help="不做自动预处理，直接在原始谱上寻峰（用于对照）")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    reader = XinDBReader(args.library)
    rows: list[dict] = []
    n = n_top1 = n_top5 = n_all5 = n_full = 0
    hit_phases = hit_phases_fam = n_phases = 0

    for sample, items in sorted(TRUTH.items()):
        path = args.patterns / f"{sample}.txt"
        if not path.is_file():
            print(f"[skip] {sample}: {path} 不存在")
            continue
        if not items:
            continue
        pattern = load_pattern(path)
        if args.raw_peaks:
            peaks = find_peaks(pattern.two_theta, pattern.intensity)
        else:
            # 与 GUI 导入路径一致：平滑 → 背景 → 扣除 → Kα2 剥离 → 寻峰
            pattern, peaks = auto_process(pattern)
        truths = [_truth_entry(label, formula) for label, formula in items]

        # 一次多取一些卡，才能折叠后仍剩 top_n 个「相位」（相族）。
        deep_n = max(args.top_n * 4, 100)
        whole = search_match(peaks, reader, pattern.wavelength, top_n=deep_n)
        cards = whole[:args.top_n]
        fam_reps = [whole[g[0]] for g in group_same_phase([c.entry for c in whole])]
        fam_reps = fam_reps[:args.top_n]
        top1 = whole[0] if whole else None
        top5 = whole[:5]
        t1 = bool(top1) and _hit(top1, truths)
        t5 = any(_hit(c, truths) for c in top5)
        # 每个真值相是否出现（相召回，逐相计）：卡级 Top-N vs 折叠后 Top-N 族
        in_top = [any(_hit(c, [t]) for c in cards) for t in truths]
        in_fam = [any(_hit(c, [t]) for c in fam_reps) for t in truths]
        in_top5 = [any(_hit(c, [t]) for c in top5) for t in truths]

        found: list[str] = []
        cover = 0.0
        found_phases = 0
        if args.rounds > 0:
            seq = SequentialIdentifier(peaks, wavelength=pattern.wavelength)
            confirmed: list[Entry] = []
            for _ in range(args.rounds):
                res = search_residual(seq, reader, top_n=args.top_n)
                if not res.candidates:
                    break
                sel = seq.select(res.candidates[0])
                confirmed.append(res.candidates[0].entry)
                found.append(res.candidates[0].entry.entry_id)
                cover = sel.covered_fraction
            found_phases = sum(any(same_phase(e, t) for e in confirmed) for t in truths)

        n += 1
        n_top1 += t1
        n_top5 += t5
        n_all5 += all(in_top5)
        n_full += found_phases == len(truths)
        n_phases += len(truths)
        hit_phases += sum(in_top)
        hit_phases_fam += sum(in_fam)
        rows.append({
            "sample": sample,
            "n_peaks": len(peaks),
            "truth": [label for label, _ in items],
            "top1": top1.entry.entry_id if top1 else None,
            "top1_formula": top1.entry.formula if top1 else None,
            "hit_top1": t1,
            "hit_top5": t5,
            "phase_in_top": in_top,
            "phase_in_top_family": in_fam,
            "phase_in_top5": in_top5,
            "n_families": len(group_same_phase([c.entry for c in whole])),
            "sequential_found": found,
            "sequential_hit_phase": found_phases,
            "coverage": round(cover, 4),
        })

    print(f"{'sample':<8}{'npk':>5}  {'Top-1':<15}{'T1':>3}{'T5':>3}  "
          f"{'卡级':<14}{'族级':<14}{'序贯':>6}")
    for r in rows:
        marks = "".join("Y" if h else "." for h in r["phase_in_top"])
        marks_f = "".join("Y" if h else "." for h in r["phase_in_top_family"])
        print(f"{r['sample']:<8}{r['n_peaks']:>5}  {(r['top1'] or '-'):<15}"
              f"{'Y' if r['hit_top1'] else '.':>3}{'Y' if r['hit_top5'] else '.':>3}  "
              f"{marks:<6}{sum(r['phase_in_top']):>2}/{len(r['truth']):<5}"
              f"{marks_f:<6}{sum(r['phase_in_top_family']):>2}/{len(r['truth']):<5}"
              f"{r['sequential_hit_phase']}/{len(r['truth'])}")

    print(f"\n整谱 Top-1 命中真相相 {n_top1}/{n}　Top-5 {n_top5}/{n}　"
          f"Top-5 覆盖全部真相相 {n_all5}/{n}")
    print(f"相召回（Top-{args.top_n} 卡）{hit_phases}/{n_phases}　"
          f"相召回（Top-{args.top_n} 族，折叠后）{hit_phases_fam}/{n_phases}　"
          f"序贯完整回收 {n_full}/{n}")
    print(f"口径：{NOTES}")
    for key, why in EXCLUDED.items():
        print(f"  排除 {key}：{why}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps({
                "patterns": str(args.patterns),
                "library": str(args.library),
                "top_n": args.top_n,
                "rounds": args.rounds,
                "notes": NOTES,
                "excluded": EXCLUDED,
                "totals": {
                    "samples": n, "top1": n_top1, "top5": n_top5,
                    "top5_all_phases": n_all5,
                    "phase_recall": [hit_phases, n_phases],
                    "full_recovery": n_full,
                },
                "rows": rows,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("json ->", args.out)
    reader.close()


if __name__ == "__main__":
    main()
