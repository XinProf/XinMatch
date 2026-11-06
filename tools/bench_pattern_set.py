"""Benchmark search-match against a **pattern directory** with known ground truth.

Complements :mod:`tools.bench_search_v3` (which synthesises single-phase patterns
from the library itself): this one runs on real *mixture* pattern files
(``synth_XX.txt``) whose composition is known, and measures two things:

1. **whole-pattern** — one ``search_match`` on the full peak list; is a true
   entry in Top-1 / Top-5?
2. **sequential** — confirm Top-1, re-search the residual, confirm again, up to
   ``--rounds``; how many true phases were recovered, and the final coverage.

Ground truth comes from :data:`TRUTH` (kept in sync with
``tools/generate_synthetic_patterns._MATERIALS``). Entry ids use the library
convention ``96-<3 digits>-<4 digits>``.

``--oracle-elements`` adds a parallel "sample elements are known" pass: the
element set is derived from the *truth* entries and everything else is excluded.
That is an **upper bound**, not a deliverable metric (the real input would come
from XRF/EDS or a recipe).  It mirrors ``tools.bench_real_samples`` and is used
to quantify how much candidate-pool dilution costs on large libraries (report
§23).  Default output is unchanged when the flag is off.

Usage::

    python -m tools.bench_pattern_set \
        --patterns D:\\Project\\XRD\\test_xrd\\synthetic_v3 \
        --library D:\\Project\\XRD\\XinMatch-DataBase\\data\\COD-Inorg-20261020.xinDB \
        --out .scratch/bench_v3.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from xinmatch.core.db.reader_v3 import XinDBReader
from xinmatch.core.db.search_v3 import _entry_from_meta
from xinmatch.core.io import load_pattern
from xinmatch.core.model import Entry
from xinmatch.core.model.restraints import Restraints
from xinmatch.core.peak.peak_search import find_peaks
from xinmatch.core.search.fom import CandidateResult
from xinmatch.core.search.phase_key import same_phase
from xinmatch.core.search.search_match import search_match
from xinmatch.core.search.sequential import SequentialIdentifier, search_residual

#: sample file stem -> [(cod_id, wt)]，与生成器的 _MATERIALS 一致
TRUTH: dict[str, list[tuple[int, float]]] = {
    "synth_01": [(2300448, 0.50), (2300112, 0.45), (2300449, 0.05)],
    "synth_02": [(5000035, 0.60), (2100992, 0.40)],
    "synth_03": [(5000223, 0.55), (2310486, 0.45)],
    "synth_04": [(2101167, 0.65), (5000035, 0.35)],
    "synth_05": [(9008961, 0.55), (2300112, 0.45)],
    "synth_06": [(2100858, 1.00)],
    "synth_07": [(9000629, 0.60), (9003112, 0.40)],
    "synth_08": [(2300449, 0.70), (2300448, 0.30)],
    "synth_09": [(9000046, 1.00)],
    "synth_10": [(5000217, 0.70), (2101535, 0.30)],
    "synth_11": [(5000040, 0.60), (2100992, 0.40)],
    "synth_12": [(5000225, 0.50), (5000120, 0.50)],
    "synth_13": [(2101234, 1.00)],
}


def cod_to_entry_id(cod_id: int) -> str:
    """COD 归档 id → 库内 entry_id（``5000035`` → ``96-500-0035``）。"""
    s = str(cod_id)
    return f"96-{s[:3]}-{s[3:]}" if len(s) == 7 else s


def _ids(cands: list[CandidateResult], n: int) -> list[str]:
    return [c.entry.entry_id for c in cands[:n]]


def _load_truth(reader: XinDBReader, entry_ids: list[str]) -> list[Entry]:
    """真相相条目（取不到就跳过，不影响其余样品）。"""
    out: list[Entry] = []
    for eid in entry_ids:
        meta = reader.fetch_entry(eid)
        if meta:
            out.append(_entry_from_meta(meta))
    return out


def _phase_hit(cand: CandidateResult, truth: list[Entry]) -> bool:
    """按相位判定：候选与任一真相相"同相"（他卡也算命中）。"""
    return any(same_phase(cand.entry, t) for t in truth)


def _oracle_restraints(truth_entries: list[Entry]) -> Restraints | None:
    """「样品元素已知」上界口径：真值元素留下，其余全部标为必须不含。

    元素由真值相在库内的 ``elements`` 反推，所以这是**上界**：衡量
    「化学信息给足时引擎能做到什么」，不能当自动结果报。检出元素保持
    OPTIONAL（绝不 REQUIRED）—— 次相未必含主相的每个元素，且
    ``elements_allowed`` 是「必须全部含有」语义。
    """
    from tools.bench_real_samples import ALL_ELEMENTS

    elems: set[str] = set()
    for entry in truth_entries:
        elems |= set(entry.elements)
    if not elems:
        return None
    restraints = Restraints()
    for el in ALL_ELEMENTS:
        if el not in elems:
            restraints.exclude(el)
    return restraints


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patterns", type=Path, required=True)
    ap.add_argument("--library", type=Path, required=True)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--family-slots", type=int, default=None,
                    help="预筛每族名额上限（默认不设限；1 = 每族只留最强一张卡）")
    ap.add_argument("--prescreen-order", choices=("intensity", "hits"),
                    default="intensity",
                    help="预筛第二排序键（默认 intensity = 发布口径；hits 为待裁定口径）。"
                         "配置会写进结果 JSON —— 基线按配置认，不按文件名认")
    ap.add_argument("--oracle-elements", action="store_true",
                    help="额外跑一套「元素上界」口径：用真值相元素反推样品元素，把其余"
                         "元素全部标为必须不含。这是**上界**，不是交付指标")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    reader = XinDBReader(args.library, family_slots=args.family_slots,
                         prescreen_order=args.prescreen_order)
    print(f"[配置] prescreen_order={args.prescreen_order}  "
          f"family_slots={args.family_slots}  top_n={args.top_n}  rounds={args.rounds}"
          f"  oracle_elements={args.oracle_elements}")
    rows: list[dict] = []
    n_top1 = n_top5 = n_full = n_phases_hit = n_phases = 0
    n_top1_phase = n_top5_phase = 0
    n_phases_hit_entry = 0
    n_full_phase = 0
    # 元素上界口径（与默认两套并列，相位级）
    e_top1 = e_top5 = e_full = e_phases_hit = 0

    for name, phases in sorted(TRUTH.items()):
        path = args.patterns / f"{name}.txt"
        if not path.is_file():
            continue
        pattern = load_pattern(path)
        peaks = find_peaks(pattern.two_theta, pattern.intensity)
        truth_ids = [cod_to_entry_id(c) for c, _wt in phases]
        truth_set = set(truth_ids)

        whole = search_match(peaks, reader, pattern.wavelength, top_n=args.top_n)
        top1, top5 = _ids(whole, 1), _ids(whole, 5)
        hit1 = bool(set(top1) & truth_set)
        hit5 = bool(set(top5) & truth_set)
        truth_entries = _load_truth(reader, truth_ids)
        hit1_phase = bool(whole) and _phase_hit(whole[0], truth_entries)
        hit5_phase = any(_phase_hit(c, truth_entries) for c in whole[:5])
        n_top1 += hit1
        n_top5 += hit5
        n_top1_phase += hit1_phase
        n_top5_phase += hit5_phase

        seq = SequentialIdentifier(peaks, wavelength=pattern.wavelength)
        found: list[str] = []
        found_entries: list[Entry] = []
        cover = 0.0
        for _ in range(args.rounds):
            res = search_residual(seq, reader, top_n=args.top_n)
            if not res.candidates:
                break
            sel = seq.select(res.candidates[0])
            found.append(res.candidates[0].entry.entry_id)
            found_entries.append(res.candidates[0].entry)
            cover = sel.covered_fraction

        # 条目级：真相 id 是否原样出现在已确认相里
        got = {f for f in found if f in truth_set}
        # 相位级：任一已确认相与某个真相相"同相"（同相异卡也算），且每个真相相至多记一次
        got_phase = [t for t in truth_entries if any(same_phase(fe, t) for fe in found_entries)]
        n_phases += len(truth_entries)
        n_phases_hit += len(got_phase)
        n_phases_hit_entry += len(got)
        n_full += truth_set <= set(found)
        n_full_phase += len(got_phase) == len(truth_entries) and bool(truth_entries)

        row = {
            "sample": name,
            "n_peaks": len(peaks),
            "truth": truth_ids,
            "top1": top1[0] if top1 else None,
            "top5": top5,
            "hit_top1": hit1,
            "hit_top5": hit5,
            "hit_top1_phase": hit1_phase,
            "hit_top5_phase": hit5_phase,
            "sequential_found": found,
            "sequential_hit": len(got),
            "sequential_hit_phase": len(got_phase),
            "sequential_truth": len(truth_entries),
            "coverage": round(cover, 4),
            "all_recovered": truth_set <= set(found),
            "all_recovered_phase": len(got_phase) == len(truth_entries) and bool(truth_entries),
        }

        if args.oracle_elements:
            restraints = _oracle_restraints(truth_entries)
            if restraints is not None:
                whole_e = search_match(peaks, reader, pattern.wavelength,
                                       top_n=args.top_n, restraints=restraints)
                e_hit1 = bool(whole_e) and _phase_hit(whole_e[0], truth_entries)
                e_hit5 = any(_phase_hit(c, truth_entries) for c in whole_e[:5])
                seq_e = SequentialIdentifier(peaks, wavelength=pattern.wavelength)
                found_e: list[Entry] = []
                for _ in range(args.rounds):
                    res_e = search_residual(seq_e, reader, top_n=args.top_n,
                                            restraints=restraints)
                    if not res_e.candidates:
                        break
                    seq_e.select(res_e.candidates[0])
                    found_e.append(res_e.candidates[0].entry)
                got_phase_e = [
                    t for t in truth_entries
                    if any(same_phase(fe, t) for fe in found_e)
                ]
                e_full_one = (
                    len(got_phase_e) == len(truth_entries) and bool(truth_entries)
                )
                e_top1 += e_hit1
                e_top5 += e_hit5
                e_phases_hit += len(got_phase_e)
                e_full += e_full_one
                row.update({
                    "oracle_hit_top1_phase": e_hit1,
                    "oracle_hit_top5_phase": e_hit5,
                    "oracle_sequential_hit_phase": len(got_phase_e),
                    "oracle_all_recovered_phase": e_full_one,
                })
        rows.append(row)

    print(f"{'sample':<10}{'npk':>5}  {'top1':<15}{'T1':>3}{'T5':>3}  "
          f"{'sequential':<40}{'hit':>6}{'cover':>8}")
    for r in rows:
        seq_txt = " > ".join(r["sequential_found"]) or "-"
        print(f"{r['sample']:<10}{r['n_peaks']:>5}  {(r['top1'] or '-'):<15}"
              f"{'Y' if r['hit_top1'] else '.':>3}{'Y' if r['hit_top5'] else '.':>3}  "
              f"{seq_txt[:39]:<40}{r['sequential_hit']}/{r['sequential_truth']:<5}"
              f"{r['coverage']*100:7.1f}%")

    n = len(rows)
    print(f"\n条目级（严格 id）：Top-1 {n_top1}/{n}　Top-5 {n_top5}/{n}　"
          f"序贯完整回收 {n_full}/{n}　相召回 {n_phases_hit_entry}/{n_phases}")
    print(f"相位级（同相异卡算命中）：Top-1 {n_top1_phase}/{n}　Top-5 {n_top5_phase}/{n}　"
          f"序贯完整回收 {n_full_phase}/{n}　相召回 {n_phases_hit}/{n_phases}")
    if args.oracle_elements:
        print(f"[元素上界] 相位级 Top-1 {e_top1}/{n}　Top-5 {e_top5}/{n}　"
              f"序贯完整回收 {e_full}/{n}　相召回 {e_phases_hit}/{n_phases}")
        print("[元素上界] 这是**上界**：元素由真值相在库内反推，现实中来自 XRF/EDS 或配方")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(
                {
                    "patterns": str(args.patterns),
                    "library": str(args.library),
                    "config": {
                        "prescreen_order": args.prescreen_order,
                        "family_slots": args.family_slots,
                        "oracle_elements": args.oracle_elements,
                    },
                    "n_samples": n,
                    "top1": n_top1,
                    "top5": n_top5,
                    "full_recovery": n_full,
                    "entry_level": {
                        "top1": n_top1, "top5": n_top5,
                        "full_recovery": n_full, "phase_recall": n_phases_hit_entry,
                    },
                    "phase_level": {
                        "top1": n_top1_phase, "top5": n_top5_phase,
                        "full_recovery": n_full_phase, "phase_recall": n_phases_hit,
                    },
                    "phase_recall": [n_phases_hit, n_phases],
                    **({
                        "totals_oracle": {
                            "top1": e_top1, "top5": e_top5,
                            "full_recovery": e_full,
                            "phase_recall": [e_phases_hit, n_phases],
                        },
                    } if args.oracle_elements else {}),
                    "rows": rows,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print("json ->", args.out)
    reader.close()


if __name__ == "__main__":
    main()
