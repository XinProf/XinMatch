"""三把尺子统一入口的纯函数回归（指标抽取 / 涨跌对比 / 参数拼装）。"""

from __future__ import annotations

import argparse
from pathlib import Path

from tools import bench_three_rulers as b3


def test_extract_synthetic_counts_truth_phases() -> None:
    doc = {
        "n_samples": 2,
        "entry_level": {"top1": 1, "top5": 2, "phase_recall": 2, "full_recovery": 1},
        "phase_level": {"top1": 2, "top5": 2, "phase_recall": 3, "full_recovery": 1},
        "rows": [
            {"truth": [{"cod_id": 1}, {"cod_id": 2}]},
            {"truth": [{"cod_id": 3}]},
        ],
    }
    m = b3.extract_synthetic(doc)
    assert m["entry.top1"] == {"hit": 1, "total": 2}
    assert m["entry.recall"] == {"hit": 2, "total": 3}
    assert m["phase.recall"] == {"hit": 3, "total": 3}
    assert m["phase.seq"] == {"hit": 1, "total": 2}


def test_extract_real_keeps_coarse_and_fine_separate() -> None:
    doc = {
        "totals": {"samples": 12, "top1": 10, "top5": 12,
                   "phase_recall": [20, 43], "full_recovery": 4},
        "totals_fine": {"samples": 13, "top1": 12, "top5": 13,
                        "phase_recall": [21, 50], "phase_recall_family": [22, 50],
                        "full_recovery": 4},
    }
    m = b3.extract_real(doc)
    assert m["coarse.recall"] == {"hit": 20, "total": 43}
    assert m["fine.recall"] == {"hit": 21, "total": 50}
    assert m["fine.family"] == {"hit": 22, "total": 50}
    # 两个口径只并列，不做平均
    assert m["coarse.top1"]["total"] != m["fine.top1"]["total"]


def test_extract_iucr_emits_both_modes() -> None:
    doc = {
        "totals": {
            "plain": {"samples": 19, "phases": 48, "top1": 17, "top5": 18,
                      "card": 26, "fam": 27, "seq": 37},
            "elements": {"samples": 19, "phases": 48, "top1": 18, "top5": 18,
                         "card": 39, "fam": 45, "seq": 45},
        }
    }
    m = b3.extract_iucr(doc)
    assert m["plain.card"] == {"hit": 26, "total": 48}
    assert m["elements.family"] == {"hit": 45, "total": 48}
    assert m["elements.seq"] == {"hit": 45, "total": 48}


def test_compare_splits_up_down_flat() -> None:
    current = {"synthetic": {
        "entry.top1": {"hit": 8, "total": 10},
        "entry.top5": {"hit": 9, "total": 10},
        "entry.seq": {"hit": 4, "total": 10},
    }}
    baseline = {"synthetic": {
        "entry.top1": {"hit": 6, "total": 10},   # 涨
        "entry.top5": {"hit": 9, "total": 10},   # 平
        "entry.seq": {"hit": 5, "total": 10},    # 跌
    }}
    result = b3.compare(current, baseline)
    assert result["counts"] == {"up": 1, "down": 1, "flat": 1}
    by_metric = {r["metric"]: r for r in result["rows"]}
    assert by_metric["entry.top1"]["delta_pp"] == 20.0
    assert by_metric["entry.seq"]["delta_pp"] == -10.0
    assert by_metric["entry.top5"]["direction"] == "flat"


def test_compare_skips_metrics_missing_in_baseline() -> None:
    current = {"real": {"coarse.top1": {"hit": 5, "total": 10},
                        "fine.top1": {"hit": 6, "total": 10}}}
    baseline = {"real": {"coarse.top1": {"hit": 5, "total": 10}}}
    result = b3.compare(current, baseline)
    assert [r["metric"] for r in result["rows"]] == ["coarse.top1"]
    assert result["counts"]["flat"] == 1


def _args(rounds: int | None, adaptive_pool: int | None = None) -> argparse.Namespace:
    return argparse.Namespace(
        rounds=rounds, top_n=20, prescreen_order="intensity", family_slots=None,
        adaptive_pool=adaptive_pool,
    )


def test_build_argv_keeps_per_ruler_rounds_unless_overridden() -> None:
    base = dict(patterns=Path("p"), library=Path("l"), out=Path("o"))

    argv = b3.build_argv("iucr", args=_args(None), **base)
    assert "--rounds" not in argv  # 沿用各尺子默认（IUCr 8）
    assert "--top-n" in argv

    argv_r5 = b3.build_argv("synthetic", args=_args(5), **base)
    assert argv_r5[argv_r5.index("--rounds") + 1] == "5"
    assert "--prescreen-order" in argv_r5


def test_build_argv_forwards_adaptive_pool_only_when_set() -> None:
    base = dict(patterns=Path("p"), library=Path("l"), out=Path("o"))

    # 默认关闭：命令行不出现 —— 子脚本按既有默认跑，结果与历史基线可比。
    assert "--adaptive-pool" not in b3.build_argv("iucr", args=_args(None), **base)

    for ruler in ("synthetic", "real", "iucr"):
        argv = b3.build_argv(ruler, args=_args(None, 20000), **base)
        assert argv[argv.index("--adaptive-pool") + 1] == "20000"
