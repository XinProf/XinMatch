"""3-1 次相 FoM 层定性诊断（只读，不改引擎、不改权重）。

背景（``docs/基准报告-物相检索-v3.md`` §9.3/§9.4）：3-1（ZnO 主相 + Al₂O₃ + CaF₂）
的次相归为「FoM 层问题」。本探针做三件事：

1. **层级定位**：默认名额（1000）与深名额（8000）下，真相相到底在不在池内、
   排名多少 —— 区分「预筛召回失败」与「召回后 FoM 排不上」。
2. **罚分分解**：``compute_fom`` 是罚分制 ``1 − Σ w·(1−p) − w·|ln f|``，把真相相
   相对榜首的**逐判据罚分差**列出来，找最大压制项。
3. **单判据反事实**（纯算术）：把该判据换成榜首值重算 FoM，看能升到什么排名。

注意：真值匹配会**排除 formula 为 NULL/空的卡** —— 库里有 416/78,035 张这样的卡，
``same_phase`` 的组成回退把「无化学式证据」当「不反对」，它们能假匹配任何真值
（这是独立发现，见诊断报告；本探针不受其污染）。

用法::

    python -m tools._probe_31_fom \
        --library "D:/Project/XRD/XinMatch-DataBase/data/COD-Inorg-20261020.xinDB" \
        --pattern "D:/Project/XRD/test_xrd/txt/3-1.txt" [--quota 8000]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np  # noqa: E402

from xinmatch.core.db.reader_v3 import XinDBReader  # noqa: E402
from xinmatch.core.db.search_v3 import search_match_v3  # noqa: E402
from xinmatch.core.io import load_pattern  # noqa: E402
from xinmatch.core.model import Entry  # noqa: E402
from xinmatch.core.preprocess.auto_pipeline import auto_process  # noqa: E402
from xinmatch.core.search.fom_criteria import DEFAULT_WEIGHTS, compute_fom  # noqa: E402
from xinmatch.core.search.phase_key import group_same_phase, same_phase  # noqa: E402

#: 3-1 真值（组成级口径，同 bench_real_samples.TRUTH）
TRUTH_31 = [("ZnO", "O Zn", "96-230-0450"),
            ("Al2O3", "Al2 O3", "96-230-0448"),
            ("CaF2", "Ca F2", "96-230-0449")]


def _penalties(p: dict[str, float], w: dict[str, float]) -> dict[str, float]:
    """compute_fom 的逐判据罚分：w·(1−p)；i_scale 项为 w·|ln f|。"""
    out = {}
    for k in ("peakpos", "intensity", "npeaks", "ncorr"):
        out[k] = w[k] * (1.0 - float(p.get(k, 0.0)))
    f = max(float(p.get("i_scale", 1.0)), 1e-12)
    out["i_scale"] = w["i_scale"] * abs(math.log(f))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--library", type=Path, required=True)
    ap.add_argument("--pattern", type=Path, required=True)
    ap.add_argument("--quotas", type=int, nargs="+", default=[1000, 8000],
                    help="预筛名额扫描（默认 1000 8000）")
    ap.add_argument("--show-reps", type=int, default=12)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    pattern = load_pattern(args.pattern)
    pattern, peaks = auto_process(pattern)
    print(f"谱：{args.pattern.name}  {pattern.two_theta.size} 点 → {len(peaks)} 峰 "
          f"(auto_process)")

    w = DEFAULT_WEIGHTS.as_dict()
    print("权重:", {k: round(v, 4) for k, v in w.items()})
    report: dict = {"pattern": str(args.pattern), "quotas": {}, "truths": {}}

    reader = XinDBReader(args.library)
    for quota in args.quotas:
        res = search_match_v3(peaks, reader, pattern.wavelength,
                              candidate_limit=quota, top_n=quota)
        pool = res.candidates
        groups = group_same_phase([c.entry for c in pool])
        fam_of: dict[int, int] = {}
        for fr, g in enumerate(groups):
            for idx in g:
                fam_of[idx] = fr
        print(f"\n########## quota={quota}: 池 {len(pool)} 条 / {len(groups)} 族 ##########")
        report["quotas"][quota] = {"pool": len(pool), "families": len(groups)}

        top = pool[0]
        print(f"榜首 {top.entry.entry_id} {top.entry.formula!r} fom={top.fom:.4f}")
        print("  p = " + "  ".join(f"{k}={top.p_values.get(k, 0):.3f}" for k in w))
        print(f"\n---- 前 {args.show_reps} 个相位族代表（霸榜者）----")
        print(f"{'族':>4} {'entry_id':<14}{'formula':<24}{'fom':>7} "
              + " ".join(f"{k:>8}" for k in w))
        for fr, g in enumerate(groups[: args.show_reps]):
            c = pool[g[0]]
            print(f"{fr + 1:>4} {c.entry.entry_id:<14}{c.entry.formula[:23]:<24}"
                  f"{c.fom:>7.4f} " + " ".join(f"{c.p_values.get(k, 0):>8.3f}"
                                               for k in w))

        for label, formula, real_id in TRUTH_31:
            t = Entry(entry_id="truth", formula=formula,
                      d_spacings=np.zeros(0, dtype=float),
                      intensities=np.zeros(0, dtype=float))
            # 排除 NULL 式卡：same_phase 的组成回退会把「无化学式证据」当不反对
            hits = [(i, c) for i, c in enumerate(pool)
                    if c.entry.formula and same_phase(c.entry, t)]
            ri = next((i for i, c in enumerate(pool)
                       if c.entry.entry_id == real_id), None)
            rec = report["truths"].setdefault(
                label, {})[quota] = {"formula": formula, "real_card": real_id}
            print(f"\n==== [{label}] {formula!r}（指定卡 {real_id}）====")
            if hits:
                i, best = min(hits, key=lambda x: x[0])
                fr = fam_of[i] + 1
                print(f"  同相卡(有式) {len(hits)} 张；最佳 {best.entry.entry_id}  "
                      f"entry_rank={i + 1}  family_rank={fr}/{len(groups)}  "
                      f"fom={best.fom:.4f}")
                pb = _penalties(best.p_values, w)
                pt = _penalties(top.p_values, w)
                print("  罚分:     " + "  ".join(f"{k}={pb[k]:.3f}" for k in w))
                print("  相对榜首罚分差: " + "  ".join(
                    f"{k}={pb[k] - pt[k]:+.3f}" for k in w))
                worst = max(w, key=lambda k: pb[k] - pt[k])
                print(f"  → 最大压制项: {worst}"
                      f"（罚分差 {pb[worst] - pt[worst]:+.3f}）")
                rec.update({"n_cards": len(hits), "best_card": best.entry.entry_id,
                            "entry_rank": i + 1, "family_rank": fr,
                            "fom": best.fom, "p": dict(best.p_values),
                            "worst_criterion": worst})
            else:
                print("  ✗ 无有式同相卡在池内")
                rec["n_cards"] = 0
            if ri is not None:
                c = pool[ri]
                fr = fam_of[ri] + 1
                print(f"  指定卡 {real_id}: entry_rank={ri + 1}  "
                      f"family_rank={fr}/{len(groups)}  fom={c.fom:.4f}")
                print("    罚分: " + "  ".join(
                    f"{k}={_penalties(c.p_values, w)[k]:.3f}" for k in w))
                rec["real_card_rank"] = {"entry": ri + 1, "family": fr,
                                         "fom": c.fom,
                                         "p": dict(c.p_values)}
            else:
                print(f"  指定卡 {real_id}: 不在池内（预筛未召回）")
                rec["real_card_rank"] = None

            # 反事实：对「池内最佳同相卡」把最大压制判据换成榜首值，重算 FoM
            if hits:
                cf = dict(best.p_values)
                cf[worst] = float(top.p_values.get(worst, 0.0))
                cf_fom = compute_fom(cf, w)
                n_above = sum(1 for c in pool if c.fom > cf_fom)
                fam_above = len({fam_of[i] for i, c in enumerate(pool)
                                 if c.fom > cf_fom})
                print(f"  反事实: {worst}→{cf[worst]:.3f} → fom={cf_fom:.4f} → "
                      f"卡排名 {n_above + 1} / 族排名 {fam_above + 1}")
                rec["counterfactual"] = {"fom": cf_fom, "card_rank": n_above + 1,
                                         "family_rank": fam_above + 1}

    reader.close()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        print("\njson ->", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
