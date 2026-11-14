"""Benchmark search-match on the 7 ShiJK-Refinement MAUD patterns (fourth ruler).

前三把尺子（合成谱 ``bench_pattern_set`` / 真实谱 ``bench_real_samples`` /
IUCr ``bench_iucr``）的真值靠矿物名或组成比，这里不一样：每个样品目录里的
``*.cif`` 是 Match! 导出的**已识别相**，文件名内嵌 Match! 的编号，按固定换算
可得到 COD 官方 entry_id ——::

    "1-kaolinite-Entry_96-900-9231.cif"
    去掉前导 "96-" → 900-9231 → 七位数字减 1 → 9009230 → 96-900-9230

用户 2026-11-13 给出的规则；本地 33/33 与库内化学式逐一核对一致
（``--verify-truth`` 可复跑）。因此这套尺子的**主口径是条目级**（比相位级更硬），
相位级并列输出。

口径
----
* **条目级（主口径）**：命中的卡 ``entry_id`` 必须等于换算出的真值卡。
  注意库里的 entry_id 带 ``96-`` 前缀且是"我们自己的编号"，与 Match! 的编号
  差 1，**不能用文件名里的编号直接查库**（会查到别的相）。
* **相位级（并列）**：元素集相同 + 晶胞在 1.2% / 1.5° 内，**不比空间群**。
  同一相在库里常有左右手设置两张卡（石英 ``P 32 2 1`` / ``P 31 2 1``），
  按空间群判会把"找对了相但拿了姊妹卡"记成漏检 —— 实测 Top-1 会从 6/33 误报成 4/33。
* **分母 33 晶体相 / 7 样本**（5/4/5/5/5/4/5）。样品 2、3 含普通玻璃，6、7 含
  沉淀法气相 SiO2，**非晶相没有晶体卡、不入分母、不算漏检**，其宽弥散峰表现为
  残差未解释属正常。
* 「序贯」是相级（6 轮残差检索命中的真相数 / 33 相）。
* **``--oracle-elements`` 是上界口径，不是交付指标**：把整套检索切换到"样品元素
  已知"，允许池 = 全部真值相 CIF 元素集的并集，其余元素一律标为「必须不含」
  （与 IUCr 尺子的 ``complement_restraints`` 同源）。现实中元素来自 XRF/EDS 或
  工艺配方，不能从答案反推，所以只能用它衡量"化学信息给足时引擎能做到什么"。
  非晶相没有 CIF、其元素不进允许池，这只会让约束更严，不会误杀真值相。
  与默认口径的对比用 ``--baseline``，两套结果不混算。

为什么单独成尺
--------------
这套谱与前三套的差别是**噪声峰极多**（自动寻峰 116–158 峰/条），预筛按"命中强峰
计数"排序时会被 150 线的致密假卡挤满，真值相进不了打分池。它测量的是**预筛+
排序的联合召回**，与前三把尺子的口径不同，所以只并列、不并入
``bench_three_rulers`` 的 26 项指标，也不跨尺子平均。

用法
----
    python -m tools.bench_shijk --library D:\\XinMatch-DataBase\\data\\COD-Inorg-20261020.xinDB \
        --candidate-limit 20000 --out .scratch/shijk.json

    # 只核真值（不动检索）
    python -m tools.bench_shijk --library <...> --verify-truth

    # 化学信息上界（与默认口径 A/B，不混算）
    python -m tools.bench_shijk --library <...> --oracle-elements \
        --baseline docs/bench/shijk-20261113.json --out .scratch/shijk-oracle.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from xinmatch.core.db.reader_v3 import _DEFAULT_PRESCREEN_ORDER, _ORDER_CHOICES, XinDBReader
from xinmatch.core.io import load_pattern
from xinmatch.core.model.element_symbols import complement_restraints
from xinmatch.core.model.entry import CellParams, Entry
from xinmatch.core.model.restraints import Restraints
from xinmatch.core.preprocess.auto_pipeline import auto_process
from xinmatch.core.search.phase_key import parse_composition
from xinmatch.core.search.search_match import search_match
from xinmatch.core.search.sequential import SequentialIdentifier, search_residual

#: 默认数据根目录（不入 Git；见项目笔记「ShiJK-Refinement」条）。
DEFAULT_ROOT = Path(r"D:\test_XRD\ShiJK-Refinement")

#: Match! 导出文件名里的编号，形如 ``96-900-9231``。
_MATCH_ID_RE = re.compile(r"\d{2}-(\d{3})-(\d{4})")

#: CIF 里要读的键。
_CIF_KEYS = (
    "_chemical_formula_sum",
    "_cell_length_a",
    "_cell_length_b",
    "_cell_length_c",
    "_cell_angle_alpha",
    "_cell_angle_beta",
    "_cell_angle_gamma",
    "_symmetry_space_group_name_H-M",
)

#: 晶胞判等容差（相位级口径）。
CELL_REL_TOL = 0.012
ANGLE_ABS_TOL = 1.5


def match_entry_id(name: str) -> str | None:
    """``"1-quartz-Entry_96-101-1177.cif"`` → ``"96-101-1176"``。

    Match! 编号去掉前导 ``96-`` 后是 COD 官方 7 位号 **+1**，所以减 1 再补回
    本库的 ``96-`` 前缀。文件名里没有编号时返回 ``None``。
    """
    m = _MATCH_ID_RE.search(name)
    if m is None:
        return None
    number = int(m.group(1) + m.group(2)) - 1
    digits = f"{number:07d}"
    return f"96-{digits[:3]}-{digits[3:]}"


def _num(text: str) -> float:
    return float(re.sub(r"\(.*\)", "", text.strip().strip("'\"")))


def read_cif(path: Path) -> tuple[str, CellParams | None, str]:
    """读 ``_chemical_formula_sum`` / 晶胞 / 空间群（够判相，不解析原子）。"""
    got: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        for key in _CIF_KEYS:
            if line.startswith(key):
                got[key] = line[len(key):].strip().strip("'\"")
                break
    formula = got.get("_chemical_formula_sum", "")
    cell: CellParams | None = None
    try:
        cell = CellParams(
            _num(got["_cell_length_a"]),
            _num(got["_cell_length_b"]),
            _num(got["_cell_length_c"]),
            _num(got.get("_cell_angle_alpha", "90")),
            _num(got.get("_cell_angle_beta", "90")),
            _num(got.get("_cell_angle_gamma", "90")),
        )
    except (KeyError, ValueError):
        cell = None
    return formula, cell, got.get("_symmetry_space_group_name_H-M", "")


@dataclass
class Truth:
    """一个真值相：条目级 id + 相位级指纹（元素集 + 晶胞）。"""

    entry_id: str
    formula: str
    cell: CellParams | None
    cif: str

    @property
    def elements(self) -> frozenset[str]:
        return frozenset(parse_composition(self.formula))


def phase_same(cand: Entry, truth: Truth) -> bool:
    """相位级判等：元素集相同 + 晶胞在容差内，**不看空间群**。

    晶胞已经足够把多晶型分开（石英 a4.91/c5.40 vs 方石英 a4.97/c6.93），
    而空间群会把同一相的左右手设置判成两个相，属于假阴性。
    """
    if truth.cell is None or cand.cell is None:
        return False
    if frozenset(parse_composition(cand.formula)) != truth.elements:
        return False
    for got, want in (
        (cand.cell.a, truth.cell.a),
        (cand.cell.b, truth.cell.b),
        (cand.cell.c, truth.cell.c),
    ):
        if abs(got - want) > CELL_REL_TOL * max(abs(want), 1e-9):
            return False
    for got, want in (
        (cand.cell.alpha, truth.cell.alpha),
        (cand.cell.beta, truth.cell.beta),
        (cand.cell.gamma, truth.cell.gamma),
    ):
        if abs(got - want) > ANGLE_ABS_TOL:
            return False
    return True


def load_truths(sample_dir: Path) -> list[Truth]:
    truths: list[Truth] = []
    for cif in sorted(sample_dir.glob("*.cif")):
        eid = match_entry_id(cif.name)
        if eid is None:
            continue
        formula, cell, _sg = read_cif(cif)
        truths.append(Truth(entry_id=eid, formula=formula, cell=cell, cif=cif.name))
    return truths


def verify_truths(reader: XinDBReader, truths: list[Truth]) -> tuple[int, list[str]]:
    """逐相对库核对换算出的 entry_id（化学式必须一致）。"""
    problems: list[str] = []
    for t in truths:
        meta = reader.fetch_entry(t.entry_id)
        if meta is None:
            problems.append(f"{t.cif}: {t.entry_id} 库里没有")
            continue
        got = frozenset(parse_composition(meta.get("formula") or ""))
        if got != t.elements:
            problems.append(
                f"{t.cif}: {t.entry_id} 库里是 {meta.get('formula')!r}，CIF 是 {t.formula!r}"
            )
    return len(truths) - len(problems), problems


def sample_elements(truths: list[Truth]) -> list[str]:
    """样品的"已知元素"= 全部真值相（CIF）元素集的并集。

    **只供上界口径使用**：现实中这些信息来自 XRF / EDS 或工艺配方，不能从答案
    反推。样品 2/3/6/7 的非晶相没有 CIF，其元素不进允许池 —— 这只会让约束
    **更严**，不会把真值相误杀（真值相自己的元素必然在并集里）。
    """
    elems: set[str] = set()
    for t in truths:
        elems |= set(t.elements)
    return sorted(elems)


def oracle_restraints(truths: list[Truth]) -> Restraints | None:
    """「只允许样品元素」→ 其余元素全部 EXCLUDE 的补集约束。

    与 IUCr 尺子的 ``complement_restraints(_sample_elements(...))`` 同源；
    ``element_constraint_sets`` 是唯一换算点，预筛层拿到的是
    ``elements_excluded``（「必须不含」），不是 ``elements_allowed``（「必须全含」）。
    """
    detected = sample_elements(truths)
    return complement_restraints(detected) if detected else None


def _first_rank(cands: list, truths: list[Truth], *, phase: bool) -> list[int | None]:
    """每个真值相在候选列表里的最好名次（1 起；未出现为 ``None``）。"""
    out: list[int | None] = []
    for t in truths:
        rank: int | None = None
        for i, cand in enumerate(cands, 1):
            hit = (
                phase_same(cand.entry, t)
                if phase
                else cand.entry.entry_id == t.entry_id
            )
            if hit:
                rank = i
                break
        out.append(rank)
    return out


def run(args: argparse.Namespace) -> dict:
    reader = XinDBReader(
        str(args.library), prescreen_order=getattr(args, "prescreen_order", None)
        or _DEFAULT_PRESCREEN_ORDER,
    )
    samples = sorted(p for p in args.patterns.iterdir() if p.is_dir())
    if not samples:
        raise SystemExit(f"没有子目录：{args.patterns}")

    ks = (1, 3, 5, 10, 20)
    totals = {
        "entry": {"n": 0, **{k: 0 for k in ks}},
        "phase": {"n": 0, **{k: 0 for k in ks}},
        "seq": 0,
        "sample_top1_entry": 0,
        "sample_top1_phase": 0,
        "n_samples": 0,
    }
    rows: list[dict] = []

    if args.verify_truth:
        print("== 真值核对（Match! 编号 −1 → 本库 entry_id）")
        ok_all = 0
        n_all = 0
        for sample in samples:
            truths = load_truths(sample)
            ok, problems = verify_truths(reader, truths)
            ok_all += ok
            n_all += len(truths)
            print(f"  {sample.name[:24]:<26} {ok}/{len(truths)}")
            for p in problems:
                print(f"    !! {p}")
        print(f"  合计 {ok_all}/{n_all} 一致")
        return {"verify": {"ok": ok_all, "total": n_all}}

    for sample in samples:
        txt = next(iter(sorted(sample.glob("*.txt"))), None)
        if txt is None:
            print(f"[skip] {sample.name}: 没有 .txt")
            continue
        truths = load_truths(sample)
        if not truths:
            print(f"[skip] {sample.name}: 没有 CIF")
            continue

        pattern = load_pattern(txt)
        processed, peaks = auto_process(pattern)
        oracle = getattr(args, "oracle_elements", False)
        restraints = oracle_restraints(truths) if oracle else None
        cands = search_match(
            peaks,
            reader,
            processed.wavelength,
            top_n=args.fetch,
            candidate_limit=args.candidate_limit,
            adaptive_pool=args.adaptive_pool,
            restraints=restraints,
        )
        r_entry = _first_rank(cands, truths, phase=False)
        r_phase = _first_rank(cands, truths, phase=True)

        n = len(truths)
        totals["entry"]["n"] += n
        totals["phase"]["n"] += n
        for k in ks:
            totals["entry"][k] += sum(1 for r in r_entry if r and r <= k)
            totals["phase"][k] += sum(1 for r in r_phase if r and r <= k)

        seq_hit = 0
        seq_ids: list[str] = []
        if args.rounds > 0:
            ident = SequentialIdentifier(peaks, wavelength=processed.wavelength)
            confirmed: list[Entry] = []
            for _ in range(args.rounds):
                res = search_residual(ident, reader, top_n=args.top_n,
                                      adaptive_pool=args.adaptive_pool,
                                      candidate_limit=args.seq_candidate_limit,
                                      restraints=restraints)
                if not res.candidates:
                    break
                ident.select(res.candidates[0])
                confirmed.append(res.candidates[0].entry)
                seq_ids.append(res.candidates[0].entry.entry_id)
            seq_hit = sum(any(phase_same(e, t) for e in confirmed) for t in truths)
            totals["seq"] += seq_hit

        top1_entry = bool(cands) and any(
            cands[0].entry.entry_id == t.entry_id for t in truths
        )
        top1_phase = bool(cands) and any(phase_same(cands[0].entry, t) for t in truths)
        totals["sample_top1_entry"] += top1_entry
        totals["sample_top1_phase"] += top1_phase
        totals["n_samples"] += 1

        def _fmt(ranks: list[int | None]) -> str:
            return " ".join(f"#{r}" if r else "-" for r in ranks)

        print(
            f"\n=== {sample.name[:24]:<26} 峰 {len(peaks):>3}  真值 {n} 相  "
            f"Top-1 {cands[0].entry.entry_id if cands else '-'} "
            f"{'✓' if top1_entry else '✗'}"
        )
        if oracle:
            print(f"  样品元素（上界）{', '.join(sample_elements(truths))}")
        print(f"  条目级名次 {_fmt(r_entry)}")
        print(f"  相位级名次 {_fmt(r_phase)}")
        print(f"  序贯 {args.rounds} 轮：{seq_hit}/{n} → {', '.join(seq_ids) or '-'}")

        rows.append(
            {
                "sample": sample.name,
                "n_points": int(pattern.two_theta.size),
                "n_peaks": len(peaks),
                "sample_elements": sample_elements(truths) if oracle else None,
                "truths": [
                    {
                        "entry_id": t.entry_id,
                        "formula": t.formula,
                        "cif": t.cif,
                        "rank_entry": re_,
                        "rank_phase": rp,
                    }
                    for t, re_, rp in zip(truths, r_entry, r_phase, strict=True)
                ],
                "sequential": seq_ids,
                "seq_hit": seq_hit,
                "top1_entry": bool(top1_entry),
                "top1_phase": bool(top1_phase),
            }
        )

    metrics: dict[str, dict[str, int]] = {
        "entry": {
            **{f"top{k}": totals["entry"][k] for k in ks},
            "n": totals["entry"]["n"],
        },
        "phase": {
            **{f"top{k}": totals["phase"][k] for k in ks},
            "n": totals["phase"]["n"],
        },
        "seq": {"hit": totals["seq"], "n": totals["entry"]["n"]},
        "sample_top1": {
            "entry": totals["sample_top1_entry"],
            "phase": totals["sample_top1_phase"],
            "n": totals["n_samples"],
        },
    }

    print("\n" + "=" * 74)
    n_ph = totals["entry"]["n"]
    print(f"分母 {n_ph} 晶体相 / {totals['n_samples']} 样本（非晶相不计）")
    for caliber in ("entry", "phase"):
        line = "  ".join(
            f"Top-{k}:{totals[caliber][k]:>2d}" for k in ks
        )
        print(f"  {caliber:<12}{line}")
    print(f"  序贯 {args.rounds} 轮   {totals['seq']}/{n_ph}")
    print(
        f"  样本 Top-1  条目级 {totals['sample_top1_entry']}/{totals['n_samples']}"
        f"　相位级 {totals['sample_top1_phase']}/{totals['n_samples']}"
    )

    return {
        "patterns": str(args.patterns),
        "library": str(args.library),
        "candidate_limit": args.candidate_limit,
        "adaptive_pool": args.adaptive_pool,
        "seq_candidate_limit": args.seq_candidate_limit,
        "oracle_elements": getattr(args, "oracle_elements", False),
        "prescreen_order": args.prescreen_order,
        "fetch": args.fetch,
        "rounds": args.rounds,
        "metrics": metrics,
        "samples": rows,
    }


def _compare(current: dict, baseline: dict) -> None:
    """13 项全比：entry/phase 各 5 个 Top-K + seq + sample_top1 两项。

    早期版本只比前 10 项，``seq`` 与 ``sample_top1`` 的下跌会悄悄漏过去
    （§43 的序贯 16→14 当时就是手动从 JSON 读出来的）。涨跌两侧单列，
    与 ``tools/bench_three_rulers.py`` 的 compare() 保持同一套约定。
    """
    cur = current.get("metrics") or {}
    old = baseline.get("metrics") or {}
    if not cur or not old:
        print("基线里没有 metrics，跳过对比")
        return

    rows: list[tuple[str, int, int]] = []
    for group in ("entry", "phase"):
        for k in (1, 3, 5, 10, 20):
            name = f"top{k}"
            a = (old.get(group) or {}).get(name)
            b = (cur.get(group) or {}).get(name)
            if a is not None and b is not None:
                rows.append((f"{group}.{name}", int(a), int(b)))
    a = (old.get("seq") or {}).get("hit")
    b = (cur.get("seq") or {}).get("hit")
    if a is not None and b is not None:
        rows.append(("seq", int(a), int(b)))
    for name in ("entry", "phase"):
        a = (old.get("sample_top1") or {}).get(name)
        b = (cur.get("sample_top1") or {}).get(name)
        if a is not None and b is not None:
            rows.append((f"sample_top1.{name}", int(a), int(b)))

    print(f"\n{'metric':22} {'baseline':>12} {'current':>12} {'delta':>8}  dir")
    counts = {"涨": 0, "跌": 0, "平": 0}
    for label, a, b in rows:
        d = b - a
        direction = "涨" if d > 0 else "跌" if d < 0 else "平"
        counts[direction] += 1
        print(f"{label:22} {a:>12d} {b:>12d} {d:>+8d}  {direction}")
    print(f"\n涨 {counts['涨']} 项 / 跌 {counts['跌']} 项 / 平 {counts['平']} 项")
    if counts["跌"] and counts["涨"]:
        print("注意：涨跌同时存在时属零和交换，按项目约定不算改善。")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Search-match benchmark on the 7 ShiJK-Refinement MAUD patterns."
    )
    ap.add_argument("--patterns", type=Path, default=DEFAULT_ROOT,
                    help=f"ShiJK-Refinement 根目录（默认 {DEFAULT_ROOT}）")
    ap.add_argument("--library", type=Path, required=True, help=".xinDB 库绝对路径")
    ap.add_argument("--candidate-limit", type=int, default=None,
                    help="v3 预筛后打分池上限（None=引擎默认 1000）")
    ap.add_argument("--adaptive-pool", type=int, default=None,
                    help="v3 自适应放大池：FoM 头部平坦时用该池复算（None=关闭）")
    ap.add_argument("--seq-candidate-limit", type=int, default=None,
                    help="序贯每轮的 v3 预筛池上限（None=引擎默认 1000，与历史基线一致）。"
                         "默认**不**跟随 --candidate-limit：实测放大它会让序贯 16/33→14/33，"
                         "见基准报告 §45")
    ap.add_argument("--oracle-elements", action="store_true",
                    help="把整套检索切到「样品元素已知」**上界**口径：真值相 CIF 的"
                         "元素并集作允许池、其余元素全部必须不含。与默认口径用"
                         " --baseline 对比，两套不混算；元素现实来自 XRF/EDS，"
                         "不能从答案反推，故不是可交付的自动结果")
    ap.add_argument("--prescreen-order", choices=_ORDER_CHOICES,
                    default=_DEFAULT_PRESCREEN_ORDER,
                    help="v3 预筛第二排序键（intensity=强度加权 / hits=命中计数）")
    ap.add_argument("--fetch", type=int, default=200,
                    help="一次取回的候选卡数（决定可见名次深度，默认 200）")
    ap.add_argument("--top-n", type=int, default=20, help="序贯每轮取前 N，默认 20")
    ap.add_argument("--rounds", type=int, default=6, help="序贯轮数，默认 6（0=不跑）")
    ap.add_argument("--verify-truth", action="store_true",
                    help="只核对真值换算，不跑检索")
    ap.add_argument("--out", type=Path, default=None, help="汇总 JSON 输出路径")
    ap.add_argument("--baseline", type=Path, default=None, help="上一次的汇总 JSON（对比涨跌）")
    args = ap.parse_args(argv)

    if not args.library.is_file():
        ap.error(f"库不存在：{args.library}")
    if not args.patterns.is_dir():
        ap.error(f"数据目录不存在：{args.patterns}")

    doc = run(args)
    if "verify" in doc:
        return 0 if doc["verify"]["ok"] == doc["verify"]["total"] else 1

    if args.baseline is not None:
        if not args.baseline.is_file():
            ap.error(f"基线不存在：{args.baseline}")
        _compare(doc, json.loads(args.baseline.read_text(encoding="utf-8")))

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
