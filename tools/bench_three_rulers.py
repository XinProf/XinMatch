"""Run the three benchmark rulers in one shot and diff against a baseline.

三把尺子（合成谱 / 真实谱 / IUCr）以前要分别跑三个脚本、再手工对数字。
本入口把它们串起来，产出统一汇总 JSON；带 ``--baseline`` 时按指标算差值，
并把「涨 / 跌 / 平」两侧单列输出 —— 项目约定：**零和交换不算改善**，
所以只看净增益是不够的，必须能看见每一项的方向。

口径注意
--------
* 三个脚本的 ``rounds`` 默认值不同（合成/真实谱 3，IUCr 8）。本入口默认
  **沿用各自默认值**，这样汇总结果与既有基线可比；显式传 ``--rounds`` 会
  统一覆盖三者，此时 IUCr 的数字不可与历史基线混算。
* 指标名带口径前缀：``entry.*`` / ``phase.*``（合成）、``coarse.*`` / ``fine.*``
  （真实谱）、``plain.*`` / ``elements.*``（IUCr）。不同口径只能并列、不能平均。
* IUCr 的 ``seq`` 是**相级**（命中相数 / 真相相数），与合成/真实谱的
  「样本级序贯完整回收」不是同一量纲，不要横向比大小。

用法
----
    python -m tools.bench_three_rulers \
        --synth  D:\\test_XRD\\synthetic_v3 \
        --real   "D:\\test_XRD\\temp\\smz xrd analysis" \
        --iucr   D:\\test_XRD\\IUCr\\txt \
        --library D:\\XinMatch-DataBase\\data\\COD-Inorg-20261020.xinDB \
        --out docs/bench/all-20261112.json

    # 与基线对比（涨 / 跌 单列）
    python -m tools.bench_three_rulers ... --baseline docs/bench/all-20261112.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

Metric = dict[str, int]
Metrics = dict[str, Metric]


# ---------------------------------------------------------------------------
# Metric extraction — one adapter per ruler script
# ---------------------------------------------------------------------------
def _metric(hit: int, total: int) -> Metric:
    return {"hit": int(hit), "total": int(total)}


def _ratio(m: Metric) -> float | None:
    total = int(m.get("total") or 0)
    if total <= 0:
        return None
    return m["hit"] / total


def extract_synthetic(doc: dict) -> Metrics:
    """合成谱：``entry_level`` / ``phase_level``；相召回分母从 rows 的 truth 求和。"""
    rows = doc.get("rows") or []
    n = int(doc.get("n_samples") or len(rows))
    entry = doc["entry_level"]
    phase = doc["phase_level"]
    total_phases = sum(len(r.get("truth") or []) for r in rows)
    return {
        "entry.top1": _metric(entry["top1"], n),
        "entry.top5": _metric(entry["top5"], n),
        "entry.recall": _metric(entry["phase_recall"], total_phases),
        "entry.seq": _metric(entry["full_recovery"], n),
        "phase.top1": _metric(phase["top1"], n),
        "phase.top5": _metric(phase["top5"], n),
        "phase.recall": _metric(phase["phase_recall"], total_phases),
        "phase.seq": _metric(phase["full_recovery"], n),
    }


def extract_real(doc: dict) -> Metrics:
    """真实谱：粗口径（组成级）与细口径（矿物名级）并列，不平均。"""
    coarse = doc["totals"]
    fine = doc.get("totals_fine") or {}
    out: Metrics = {
        "coarse.top1": _metric(coarse["top1"], coarse["samples"]),
        "coarse.top5": _metric(coarse["top5"], coarse["samples"]),
        "coarse.recall": _metric(*coarse["phase_recall"]),
        "coarse.seq": _metric(coarse["full_recovery"], coarse["samples"]),
    }
    if fine:
        out.update({
            "fine.top1": _metric(fine["top1"], fine["samples"]),
            "fine.top5": _metric(fine["top5"], fine["samples"]),
            "fine.recall": _metric(*fine["phase_recall"]),
            "fine.seq": _metric(fine["full_recovery"], fine["samples"]),
        })
        if "phase_recall_family" in fine:
            out["fine.family"] = _metric(*fine["phase_recall_family"])
    return out


def extract_iucr(doc: dict) -> Metrics:
    """IUCr：``plain`` / ``elements`` 两种模式；``seq`` 与 ``card`` 均为相级。"""
    out: Metrics = {}
    for mode, totals in (doc.get("totals") or {}).items():
        out.update({
            f"{mode}.top1": _metric(totals["top1"], totals["samples"]),
            f"{mode}.top5": _metric(totals["top5"], totals["samples"]),
            f"{mode}.card": _metric(totals["card"], totals["phases"]),
            f"{mode}.family": _metric(totals["fam"], totals["phases"]),
            f"{mode}.seq": _metric(totals["seq"], totals["phases"]),
        })
    return out


RULERS: dict[str, dict] = {
    "synthetic": {"module": "tools.bench_pattern_set", "extract": extract_synthetic},
    "real": {"module": "tools.bench_real_samples", "extract": extract_real},
    "iucr": {"module": "tools.bench_iucr", "extract": extract_iucr},
}

#: 各尺子脚本自己的 ``--rounds`` 默认值（汇总时保持一致，除非显式覆盖）。
DEFAULT_ROUNDS = {"synthetic": 3, "real": 3, "iucr": 8}


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------
def build_argv(
    name: str,
    patterns: Path,
    library: Path,
    out: Path,
    args: argparse.Namespace,
) -> list[str]:
    argv = [
        sys.executable, "-m", RULERS[name]["module"],
        "--patterns", str(patterns),
        "--library", str(library),
        "--out", str(out),
    ]
    if args.rounds is not None:
        argv += ["--rounds", str(args.rounds)]
    if name in ("synthetic", "real"):
        argv += ["--top-n", str(args.top_n)]
        argv += ["--prescreen-order", args.prescreen_order]
        if args.family_slots is not None:
            argv += ["--family-slots", str(args.family_slots)]
    elif name == "iucr":
        # bench_iucr 也支持 --top-n；rounds 已在上面按需传入。
        argv += ["--top-n", str(args.top_n)]
    # getattr：单测会用手工 Namespace 拼参数，旧调用方也没有这个字段。
    pool = getattr(args, "adaptive_pool", None)
    if pool is not None:
        # 四个尺子脚本都接受该开关；None 表示关闭，命令行不出现即逐位不变。
        argv += ["--adaptive-pool", str(pool)]
    return argv


def run_ruler(
    name: str,
    patterns: Path,
    library: Path,
    workdir: Path,
    args: argparse.Namespace,
) -> dict:
    out = workdir / f"{name}.json"
    argv = build_argv(name, patterns, library, out, args)
    proc = subprocess.run(
        argv, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    tail = (proc.stdout or "").strip().splitlines()[-6:]
    record: dict = {
        "patterns": str(patterns),
        "json": str(out),
        "returncode": proc.returncode,
        "tail": tail,
    }
    if proc.returncode != 0:
        record["error"] = (proc.stderr or "").strip()[-1200:]
        return record
    if not out.is_file():
        record["returncode"] = 1
        record["error"] = "benchmark finished but no JSON was written"
        return record
    doc = json.loads(out.read_text(encoding="utf-8"))
    record["metrics"] = RULERS[name]["extract"](doc)
    return record


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------
def compare(current: dict[str, Metrics], baseline: dict[str, Metrics]) -> dict:
    """逐指标对比，返回 rows 与涨 / 跌 / 平计数（方向按「越高越好」）。"""
    rows: list[dict] = []
    for ruler, metrics in current.items():
        base = baseline.get(ruler) or {}
        for key, metric in metrics.items():
            old = base.get(key)
            if not old:
                continue
            r_new, r_old = _ratio(metric), _ratio(old)
            if r_new is None or r_old is None:
                continue
            delta = r_new - r_old
            direction = "up" if delta > 1e-12 else ("down" if delta < -1e-12 else "flat")
            rows.append({
                "ruler": ruler,
                "metric": key,
                "baseline": f"{old['hit']}/{old['total']}",
                "current": f"{metric['hit']}/{metric['total']}",
                "delta_pp": round(delta * 100.0, 2),
                "direction": direction,
            })
    counts = {k: sum(1 for r in rows if r["direction"] == k) for k in ("up", "down", "flat")}
    return {"rows": rows, "counts": counts}


def _pct(m: Metric) -> str:
    r = _ratio(m)
    return "n/a" if r is None else f"{r * 100:5.1f}%"


def print_metrics(rulers: dict[str, dict]) -> None:
    print(f'\n{"ruler":10} {"metric":16} {"value":>9}   {"ratio":>7}')
    for ruler, record in rulers.items():
        if "metrics" not in record:
            print(f"{ruler:10} FAILED (rc={record.get('returncode')})")
            continue
        for key, metric in record["metrics"].items():
            print(f"{ruler:10} {key:16} {metric['hit']:>4}/{metric['total']:<4} {_pct(metric):>7}")


def print_comparison(result: dict) -> None:
    print(f'\n{"ruler":10} {"metric":16} {"baseline":>10} {"current":>10} {"delta":>9}  dir')
    for row in result["rows"]:
        arrow = {"up": "UP", "down": "DOWN", "flat": "="}[row["direction"]]
        print(
            f'{row["ruler"]:10} {row["metric"]:16} {row["baseline"]:>10} '
            f'{row["current"]:>10} {row["delta_pp"]:>+8.2f}pp  {arrow}'
        )
    c = result["counts"]
    print(f'\n涨 {c["up"]} 项 / 跌 {c["down"]} 项 / 平 {c["flat"]} 项')
    if c["down"] and c["up"]:
        print("注意：涨跌同时存在时属零和交换，按项目约定不算改善。")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Run synthetic / real / IUCr benchmarks and diff against a baseline."
    )
    ap.add_argument("--synth", type=Path, default=None, help="合成谱目录（synth_XX.txt）")
    ap.add_argument("--real", type=Path, default=None, help="真实谱目录")
    ap.add_argument("--iucr", type=Path, default=None, help="IUCr txt 目录")
    ap.add_argument("--library", type=Path, required=True, help=".xinDB 参考库")
    ap.add_argument("--out", type=Path, required=True, help="汇总 JSON 输出路径")
    ap.add_argument("--baseline", type=Path, default=None, help="上一次汇总 JSON（用于涨跌对比）")
    ap.add_argument("--workdir", type=Path, default=None, help="三个尺子各自的原始 JSON 目录")
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--rounds", type=int, default=None,
                    help="覆盖三个尺子的轮数；默认沿用各自默认（IUCr 8，其余 3）")
    ap.add_argument("--prescreen-order", choices=("intensity", "hits"), default="intensity")
    ap.add_argument("--family-slots", type=int, default=None)
    ap.add_argument("--adaptive-pool", type=int, default=None,
                    help="v3 自适应放大池：FoM 头部平坦时用该池复算（None=关闭）")
    ap.add_argument("--fail-on-down", action="store_true",
                    help="对比结果出现下跌项时以非零码退出（作为回归门用）")
    args = ap.parse_args(argv)

    inputs = {"synthetic": args.synth, "real": args.real, "iucr": args.iucr}
    selected = {k: v for k, v in inputs.items() if v is not None}
    if not selected:
        ap.error("至少给一个尺子目录：--synth / --real / --iucr")
    for name, path in selected.items():
        if not path.is_dir():
            ap.error(f"{name} 目录不存在：{path}")
    if not args.library.is_file():
        ap.error(f"参考库不存在：{args.library}")

    workdir = args.workdir or Path(tempfile.mkdtemp(prefix="bench3-"))
    workdir.mkdir(parents=True, exist_ok=True)

    rulers: dict[str, dict] = {}
    failed = False
    for name, path in selected.items():
        print(f"[run] {name}: {path}")
        record = run_ruler(name, path, args.library, workdir, args)
        rulers[name] = record
        if record.get("returncode") != 0:
            failed = True
            print(f"[fail] {name} rc={record['returncode']}: {record.get('error', '')[:300]}")

    print_metrics(rulers)

    summary: dict = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "library": str(args.library),
        "config": {
            "top_n": args.top_n,
            "rounds": args.rounds if args.rounds is not None else DEFAULT_ROUNDS,
            "prescreen_order": args.prescreen_order,
            "family_slots": args.family_slots,
            "adaptive_pool": args.adaptive_pool,
        },
        "rulers": rulers,
    }

    comparison = None
    if args.baseline:
        if not args.baseline.is_file():
            ap.error(f"基线不存在：{args.baseline}")
        base_doc = json.loads(args.baseline.read_text(encoding="utf-8"))
        base_metrics = {
            name: rec.get("metrics", {}) for name, rec in (base_doc.get("rulers") or {}).items()
        }
        comparison = compare({k: v.get("metrics", {}) for k, v in rulers.items()}, base_metrics)
        comparison["baseline"] = str(args.baseline)
        print_comparison(comparison)
        summary["comparison"] = comparison

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsummary -> {args.out}")

    if failed:
        return 1
    if args.fail_on_down and comparison and comparison["counts"]["down"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
