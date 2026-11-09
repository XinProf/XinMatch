"""Benchmark search-match on the **IUCr CPD standard patterns** — the third ruler.

Why a third ruler
-----------------
Two rulers exist already, and each has a known blind spot:

* ``tools/bench_pattern_set`` (synthetic mixtures) rebuilds every pattern from
  the *same* reference intensities it then searches against, so relative
  intensity carries no independent information — any rule that keys on
  intensity shape looks better there than it is on real data
  (``docs/基准报告-物相检索-v3.md`` §23 / §28).
* ``tools/bench_real_samples`` (13 laboratory scans) is real, but its three
  multi-phase mixtures carry **no quantified composition** — wt% is unknown,
  so "how small a minor phase can still be found" cannot be answered.

The IUCr Commission on Powder Diffraction certified reference materials fill
exactly that gap: real scans with **weighed wt%**, including a deliberate
1.15 %-to-94.81 % composition gradient.  ``CPD-1A`` … ``CPD-1H`` are the same
three phases (corundum / zincite / fluorite) at eight different ratios, so this
dataset measures *detection versus abundance* rather than one aggregate score.

Data
----
``D:\\Project\\XRD\\XRData\\IUCr\\txt`` — 38 two-column ASCII scans at 0.02°
steps.  Ground truth is ``IUCr物相说明-en.txt`` (weighed + XRF, both listed;
this script scores against **weighed**, the value that describes what was put
in the sample).

Two calibers, and why both are printed
--------------------------------------
``fine`` (mineral-name level, :data:`IUCR_TRUTH_FINE`) is the **primary**
caliber, ``coarse`` (composition ratio, :data:`IUCR_TRUTH`) is printed
alongside it under ``--coarse``.  That reverses the order used by
``bench_real_samples``, for a concrete reason: this dataset's multi-phase
samples are *natural* or *mineral* mixtures whose truth phases sit inside
polymorph families that composition alone cannot split.  ``Synthetic Bauxite``
is the extreme case — all seven of its truth phases have same-composition
siblings in the library:

===================  ==================================================
truth phase          same-composition cards in COD-Inorg
===================  ==================================================
Gibbsite (54.90 %)   Gibbsite / Bayerite / Doyleite / Nordstrandite (17)
Kaolinite (3.02 %)   Kaolinite / Dickite / Nacrite / Metahalloysite (22)
Anatase (2.00 %)     Anatase / Rutile / Brookite (40)
Quartz (5.16 %)      Quartz / Cristobalite / Coesite / Moganite (309)
===================  ==================================================

The bias between the two calibers is **measured, not reasoned** — and the
measurement changed once the family rule was fixed.  On COD-Inorg with elements
supplied (family level) fine scores 45/48 and coarse 44/48; the single
difference is coarse under-counting:

* **coarse under-counts** CPD-2's Brucite: most Brucite cards in the library
  are deuterated (``D1.96 H0.04 Mg O2``) and the ratio rule demands an
  identical element set, so those cards can never match ``H2 Mg O2``.

An earlier version of this docstring also claimed coarse *over*-counted
BAUXITE's Boehmite.  That turned out to be an artefact of judging a family by
its **representative card** alone: the family was led by a misspelled
``Bohmite`` card while the correctly spelled card sat at rank 15 inside the very
same family.  Once the family check looks at every member, fine hits Boehmite
too and the "over-count" disappears (report §29).  The lesson is recorded in
``COARSE_NOTES``: a caliber difference you did not measure may be a bug in the
caliber's implementation.

Neither caliber is a superset of the other, so they are reported side by side
and never averaged.

What is *not* scored, and why
-----------------------------
:data:`IUCR_EXCLUDED` lists the samples whose truth cannot be verified against
this library.  The pharmaceutical group is the important one: **COD holds no
card for any of those phases** — the same-composition cards are isomers
(sorbitol for mannitol, lactose/trehalose for sucrose, norvaline for valine,
levoglucosan for starch), so a real drug pattern is expected to score badly and
the cause is library coverage, not the engine.  Recording that gap is the point;
folding it into a recall ratio would hide it.

Usage::

    python -m tools.bench_iucr \\
        --patterns D:\\Project\\XRD\\XRData\\IUCr\\txt \\
        --library D:\\Project\\XRD\\XinMatch-DataBase\\data\\COD-Inorg-20261020.xinDB \\
        --out .scratch/bench_iucr_cod_inorg.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from tools.bench_real_samples import (
    FineTruth,
    family_members,
    fine_hit_entry,
    truth_entry,
)
from xinmatch.core.db.reader_v3 import XinDBReader
from xinmatch.core.db.search_v3 import search_match_v3
from xinmatch.core.io import load_pattern
from xinmatch.core.model import Entry
from xinmatch.core.model.element_symbols import (
    complement_restraints,
    element_constraint_sets,
)
from xinmatch.core.model.entry import parse_formula
from xinmatch.core.model.restraints import Restraints
from xinmatch.core.peak.peak_search import find_peaks
from xinmatch.core.preprocess.auto_pipeline import auto_process
from xinmatch.core.search.phase_key import same_phase
from xinmatch.core.search.sequential import SequentialIdentifier, search_residual

#: wt% 分桶边界（下界含、上界不含）。「次相能小到多少还能找到」是这套基准
#: 唯一能回答、前两把尺子都答不了的问题，所以分桶是这个脚本的主输出之一。
WT_BUCKETS: tuple[tuple[str, float, float], ...] = (
    ("<5%", 0.0, 5.0),
    ("5-20%", 5.0, 20.0),
    ("20-50%", 20.0, 50.0),
    (">=50%", 50.0, 1e9),
)


@dataclass(frozen=True)
class IucrPhase:
    """One truth phase of one IUCr sample.

    Args:
        label: Report name (also the mineral name used by the fine caliber).
        formula: Composition ratio, space-separated, used by the coarse caliber.
        wt_pct: Weighed abundance.  ``100.0`` for a single-phase standard;
            ``None`` when the IUCr note does not quantify the phase.
    """

    label: str
    formula: str
    wt_pct: float | None = None


def _pure(label: str, formula: str) -> list[IucrPhase]:
    """A single-phase standard: by definition 100 wt%."""
    return [IucrPhase(label, formula, 100.0)]


def _cpd1(al2o3: float, zno: float, caf2: float) -> list[IucrPhase]:
    """CPD-1a…1h: corundum / zincite / fluorite, weighed wt% from the IUCr note."""
    return [
        IucrPhase("Corundum", "Al2 O3", al2o3),
        IucrPhase("Zincite", "O Zn", zno),
        IucrPhase("Fluorite", "Ca F2", caf2),
    ]


def _fine_triple() -> list[FineTruth]:
    """CPD-1a…1h share one truth set — same three phases, different wt%."""
    return [
        FineTruth("Corundum", ("Corundum",), "Al2 O3"),
        FineTruth("Zincite", ("Zincite", "Zinc oxide"), "O Zn"),
        FineTruth("Fluorite", ("Fluorite",), "Ca F2"),
    ]


#: 组成级口径（coarse）。数字与 §2 起的粗口径同源，但与矿物名级的偏差**方向实测**为
#: 组成级单方漏判（氘代/掺杂卡元素集不等），见 ``COARSE_NOTES``；因此只作并列对照。
IUCR_TRUTH: dict[str, list[IucrPhase]] = {
    # ── 单相 certified standards ──────────────────────────────────────────
    "BRUCITE": _pure("Brucite", "H2 Mg O2"),
    "CORUNDUM": _pure("Corundum", "Al2 O3"),
    "FLUORITE": _pure("Fluorite", "Ca F2"),
    "MAGNETIT": _pure("Magnetite", "Fe3 O4"),
    "ZINCITE": _pure("Zincite", "O Zn"),
    "ZIRCON": _pure("Zircon", "O4 Si Zr"),
    "CPD-Y2O3": _pure("Y2O3", "O3 Y2"),
    # ── CPD-1a…1h：同一体系 8 个配比（weighed wt%）──────────────────────
    # 1a 是极端稀释样本：刚玉只有 1.15 wt%，萤石 94.81 wt%。
    "CPD-1A": _cpd1(1.15, 4.04, 94.81),
    "CPD-1B": _cpd1(94.31, 1.36, 4.33),
    "CPD-1C": _cpd1(5.04, 93.59, 1.36),
    "CPD-1D": _cpd1(13.53, 32.89, 53.58),
    "CPD-1E": _cpd1(55.12, 15.25, 29.62),
    "CPD-1F": _cpd1(27.06, 55.22, 17.72),
    "CPD-1G": _cpd1(31.37, 34.21, 34.42),
    "CPD-1H": _cpd1(35.12, 30.19, 34.69),
    # ── CPD-2：四相 + 择优取向（brucite 36.26 wt% 是最强相）───────────────
    "CPD-2": [
        IucrPhase("Corundum", "Al2 O3", 21.27),
        IucrPhase("Zincite", "O Zn", 19.94),
        IucrPhase("Fluorite", "Ca F2", 22.53),
        IucrPhase("Brucite", "H2 Mg O2", 36.26),
    ],
    # ── CPD-3：三相 + 非晶（Glass 29.47 wt% 不计入相分母）─────────────────
    "CPD-3": [
        IucrPhase("Corundum", "Al2 O3", 30.79),
        IucrPhase("Zincite", "O Zn", 19.68),
        IucrPhase("Fluorite", "Ca F2", 20.06),
    ],
    # ── CPD-4：三相，微吸收（magnetite 与 zircon 密度差大）────────────────
    "CPD-4": [
        IucrPhase("Corundum", "Al2 O3", 50.46),
        IucrPhase("Magnetite", "Fe3 O4", 19.64),
        IucrPhase("Zircon", "O4 Si Zr", 29.90),
    ],
    # ── 合成铝土矿：七相，weighed wt% 已给 ────────────────────────────────
    "BAUXITE": [
        IucrPhase("Gibbsite", "Al H3 O3", 54.90),
        IucrPhase("Boehmite", "H Al O2", 14.93),
        IucrPhase("Hematite", "Fe2 O3", 10.00),
        IucrPhase("Goethite", "H Fe O2", 9.98),
        IucrPhase("Quartz", "O2 Si", 5.16),
        IucrPhase("Kaolinite", "Al2 H4 O9 Si2", 3.02),
        IucrPhase("Anatase", "O2 Ti", 2.00),
    ],
}

#: 矿物名级口径（fine）——**本数据集的主口径**。
#: 所有真值相在 COD-Inorg-20261020 里都能按名定位到（覆盖情况见报告 §29.1）。
#: ``split=True`` 只用在真值本身有两个多晶型的地方，本数据集没有。
IUCR_TRUTH_FINE: dict[str, list[FineTruth]] = {
    "BRUCITE": [FineTruth("Brucite", ("Brucite",), "H2 Mg O2")],
    "CORUNDUM": [FineTruth("Corundum", ("Corundum",), "Al2 O3")],
    "FLUORITE": [FineTruth("Fluorite", ("Fluorite",), "Ca F2")],
    "MAGNETIT": [FineTruth("Magnetite", ("Magnetite",), "Fe3 O4")],
    "ZINCITE": [FineTruth("Zincite", ("Zincite", "Zinc oxide"), "O Zn")],
    "ZIRCON": [FineTruth("Zircon", ("Zircon",), "O4 Si Zr")],
    # Y2O3 在库内有两种写法：矿物名 Yttriaite-(Y) 与 yttria oxide，均指同一相。
    "CPD-Y2O3": [FineTruth("Y2O3", ("Yttriaite-(Y)", "yttria oxide"), "O3 Y2")],
    "CPD-1A": _fine_triple(),
    "CPD-1B": _fine_triple(),
    "CPD-1C": _fine_triple(),
    "CPD-1D": _fine_triple(),
    "CPD-1E": _fine_triple(),
    "CPD-1F": _fine_triple(),
    "CPD-1G": _fine_triple(),
    "CPD-1H": _fine_triple(),
    "CPD-2": [
        FineTruth("Corundum", ("Corundum",), "Al2 O3"),
        FineTruth("Zincite", ("Zincite", "Zinc oxide"), "O Zn"),
        FineTruth("Fluorite", ("Fluorite",), "Ca F2"),
        FineTruth("Brucite", ("Brucite",), "H2 Mg O2"),
    ],
    "CPD-3": [
        FineTruth("Corundum", ("Corundum",), "Al2 O3"),
        FineTruth("Zincite", ("Zincite", "Zinc oxide"), "O Zn"),
        FineTruth("Fluorite", ("Fluorite",), "Ca F2"),
    ],
    "CPD-4": [
        FineTruth("Corundum", ("Corundum",), "Al2 O3"),
        FineTruth("Magnetite", ("Magnetite",), "Fe3 O4"),
        FineTruth("Zircon", ("Zircon",), "O4 Si Zr"),
    ],
    "BAUXITE": [
        FineTruth("Gibbsite", ("Gibbsite",), "Al H3 O3"),
        # "Bohmite" 是库内 96-901-2273/2274/2275 的错拼（§31.5 别名审计；
        # 晶胞同为 Cmcm 一水软铝石结构，§29 族级口径已把它并进同一族）。
        FineTruth("Boehmite", ("Boehmite", "Bohmite"), "H Al O2"),
        FineTruth("Hematite", ("Hematite",), "Fe2 O3"),
        FineTruth("Goethite", ("Goethite",), "H Fe O2"),
        FineTruth("Quartz", ("Quartz",), "O2 Si"),
        FineTruth("Kaolinite", ("Kaolinite",), "Al2 H4 O9 Si2"),
        FineTruth("Anatase", ("Anatase",), "O2 Ti"),
    ],
}

#: 不进评分分母的样本。每条都必须给出可复核的理由——「样本不好跑」不是理由。
IUCR_EXCLUDED: dict[str, str] = {
    "SILICA": "非晶硅石标样：背景 912 / 峰高 985（7251 点里 267 个「峰」全是噪声），"
              "无周期性晶格可检索 → 不计入相召回，只作非晶样本记录",
    "MANNITOL": "COD-Full 里无甘露醇卡；同组成 C6H14O6 的 7 张全是山梨醇/无名卡（异构体）",
    "SUCROSE": "COD-Full 里无蔗糖卡；同组成 C12H22O11 的 14 张全是乳糖/海藻糖（异构体）",
    "VALINE": "真值为 DL-Valine（外消旋）；COD-Full 只有 L-Valine 1 张，手性不同即是不同晶相",
    "STARCH": "淀粉是半结晶聚合物，COD 不收录；同组成 C6H10O5 的 13 张是糖酐等小分子",
    "NIZATIDI": "COD-Full 里化学式 C12H21N5O2S2 为 0 张 → 真值在库内不可达",
    "PHARM1GR": "说明文件只给出药物组 5 个候选相，未指明本谱含哪些、含量多少 → 真值不完整",
    "PHARM2GR": "说明文件只给出药物组 5 个候选相，未指明本谱含哪些、含量多少 → 真值不完整",
    "GRANODIO": "天然花岗闪长岩，说明文件明写「True values not known」→ 无真值可评",
}

FINE_NOTES = (
    "主口径 = 矿物名级：卡有可用矿物名就按名判定，无名的卡才回落到组成比。"
    "本数据集的天然多相样品（尤其 BAUXITE）真值相都落在同组成多晶型族里，"
    "组成级无法区分它们，故以矿物名级为准、组成级只作并列对照。"
)
COARSE_NOTES = (
    "对照口径 = 组成级：同组成的多晶型/异构相不区分。它与矿物名级的偏差**方向必须实测，不能推理**："
    "实测（COD-Inorg，给元素，族级）矿物名级 45/48、组成级 44/48，唯一差异是组成级漏掉 "
    "CPD-2 的 Brucite（库内 Brucite 多为氘代，元素集含 D，而比值口径要求元素集相等）。"
    "上一版这里写的是「双向偏差、BAUXITE 的 Boehmite 被组成级误判命中」——那条在族级口径修好"
    "（族内任一成员命中即算命中，见 §29）之后不再成立：矿物名级现在也命中 Boehmite，"
    "所谓「误判」其实是族级只看代表卡造成的**假差异**。两个口径仍然只能并列、不可互相替代。"
)


def _resolve_pattern(root: Path, sample: str) -> tuple[Path, str] | None:
    """Locate a sample's scan, preferring the ``_raw`` export.

    ``_raw`` and ``_mdi`` are **two exports of the same measurement**, not two
    scans: ``_mdi`` starts at 5.02° instead of 5.00° and carries 7250 instead of
    7251 points.  Mixing them inside one benchmark would make the numbers
    incomparable, so the rule is fixed here and the chosen suffix is recorded in
    the result JSON.

    ``CPD-1F`` / ``1G`` / ``1H`` exist only without a suffix — that is why the
    bare name is the fallback rather than an error.
    """
    for suffix in ("_raw", "_mdi", ""):
        path = root / f"{sample}{suffix}.txt"
        if path.is_file():
            return path, (suffix or "(bare)")
    return None


def _wt_of(phases: list[IucrPhase], label: str) -> float | None:
    for p in phases:
        if p.label == label:
            return p.wt_pct
    return None


def _bucket_of(wt: float | None) -> str | None:
    if wt is None:
        return None
    for name, lo, hi in WT_BUCKETS:
        if lo <= wt < hi:
            return name
    return None


def _sample_elements(phases: list[IucrPhase]) -> list[str]:
    """Elements the sample is known to contain (from its truth phases)."""
    elems: set[str] = set()
    for p in phases:
        elems |= set(parse_formula(p.formula))
    return sorted(elems)


def _library_coverage(library: Path, formulas: dict[str, str]) -> dict[str, int]:
    """Count cards per composition — evidence for :data:`IUCR_EXCLUDED`.

    Read-only metadata query on a side connection; it never participates in the
    search itself, which is why it can use plain SQL instead of the reader API.
    """
    out: dict[str, int] = {}
    if not formulas:
        return out
    con = sqlite3.connect(f"file:{library}?mode=ro", uri=True)
    try:
        for label, formula in formulas.items():
            try:
                count = con.execute(
                    "SELECT COUNT(*) FROM entries WHERE formula = ?", (formula,)
                ).fetchone()[0]
            except sqlite3.Error:
                count = -1
            out[label] = int(count)
    finally:
        con.close()
    return out


def _pools(
    restraints: Restraints | None,
) -> tuple[set[str] | None, set[str] | None, set[str] | None]:
    """Split a :class:`Restraints` into the three pools the v3 prescreen takes.

    Delegates to :func:`element_constraint_sets` — the same single conversion
    point ``search_match`` uses — so the benchmark searches with the *exact*
    product semantics (必有 → ``elements_allowed``, 含有 → ``elements_any``,
    没有 + 闭环补集 → ``elements_excluded``).
    """
    if restraints is None:
        return None, None, None
    required, any_of, excluded = element_constraint_sets(restraints)
    return required or None, any_of or None, excluded or None


def _search(peaks, reader, wavelength: float, *, deep_n: int,
            pools: tuple[set[str] | None, set[str] | None, set[str] | None]):
    """One whole-pattern search, keeping the prescreen metadata.

    ``search_match`` throws ``n_prescreened`` / ``truncated`` away, but they are
    the only direct evidence of **candidate-pool dilution** — which turned out to
    be the dominant failure mode on this dataset.  So the v3 entry point is
    called directly.
    """
    allowed, any_of, excluded = pools
    return search_match_v3(
        peaks, reader, wavelength, top_n=deep_n,
        elements_allowed=allowed, elements_any=any_of,
        elements_excluded=excluded,
    )


def _score(whole, fine_truths: list[FineTruth], top_n: int,
           coarse_truths: list[Entry] | None = None) -> dict:
    """Card / family / Top-1 / Top-5 masks for one candidate list.

    ``coarse_truths``（组成级）只在 ``--coarse`` 时给出：它和 ``fine`` 用的是
    同一批候选，只是换一把判据，所以两者的差可以直接读作「口径差异」。

    族级判定看**族内全部成员卡**，不看代表卡 —— 理由与
    :func:`tools.bench_real_samples.family_members` 同源，那次修复的起因正是
    BAUXITE 的 Boehmite 被错拼卡 ``Bohmite`` 领衔的族判成漏检。
    """
    cards = whole.candidates[:top_n]
    fams = family_members(whole.candidates, top_n)
    top5 = whole.candidates[:5]
    top1 = whole.candidates[0] if whole.candidates else None
    out = {
        "in_top": [any(fine_hit_entry(c.entry, t) for c in cards) for t in fine_truths],
        "in_fam": [any(fine_hit_entry(c.entry, t) for fam in fams for c in fam)
                   for t in fine_truths],
        "in_top5": [any(fine_hit_entry(c.entry, t) for c in top5) for t in fine_truths],
        "t1": bool(top1) and any(fine_hit_entry(top1.entry, t) for t in fine_truths),
        "t5": any(any(fine_hit_entry(c.entry, t) for t in fine_truths)
                  for c in top5),
        "top1": top1,
    }
    if coarse_truths is not None:
        out["c_in_fam"] = [any(same_phase(c.entry, t) for fam in fams for c in fam)
                           for t in coarse_truths]
        out["c_in_top"] = [any(same_phase(c.entry, t) for c in cards)
                           for t in coarse_truths]
    return out


def _fmt_wt_range(wts: list[float | None]) -> str:
    values = [w for w in wts if w is not None]
    return f"{min(values):.2f}-{max(values):.2f}" if values else "-"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patterns", type=Path, required=True)
    ap.add_argument("--library", type=Path, required=True)
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--rounds", type=int, default=8,
                    help="序贯确认轮数（默认 8：BAUXITE 有 7 个真值相，3 轮不够）")
    ap.add_argument("--family-slots", type=int, default=None,
                    help="预筛每族名额上限（默认不设限）")
    ap.add_argument("--prescreen-order", choices=("intensity", "hits"),
                    default="intensity",
                    help="预筛第二排序键（默认 intensity = 发布口径）")
    ap.add_argument("--no-elements", action="store_true",
                    help="只跑「不给元素」一套。默认两套并列：plain（只给谱）与 "
                         "elements（给样品元素，按产品路径 118 元素补集约束）")
    ap.add_argument("--coarse", action="store_true",
                    help="额外按**组成级**口径再判一次（同一批候选，只换判据）。"
                         "两个口径不可互相替代：组成级会漏判掺杂/氘代卡（如库内 "
                         "Brucite 多为 D 代，元素集不等），也会误判同组成的异名相。")
    ap.add_argument("--raw-peaks", action="store_true",
                    help="不做自动预处理，直接在原始谱上寻峰（用于对照）")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    reader = XinDBReader(args.library, family_slots=args.family_slots,
                         prescreen_order=args.prescreen_order)
    modes = ["plain"] if args.no_elements else ["plain", "elements"]
    print(f"[配置] prescreen_order={args.prescreen_order}  "
          f"family_slots={args.family_slots}  top_n={args.top_n}  rounds={args.rounds}  "
          f"modes={modes}")
    print(f"[库]   {args.library}  相数={reader.entry_count():,}")

    rows: list[dict] = []
    tot: dict[str, dict] = {
        m: {"samples": 0, "phases": 0, "top1": 0, "top5": 0, "all5": 0,
            "card": 0, "fam": 0, "seq": 0, "wt_sum": 0.0, "wt_hit": 0.0,
            "trunc": 0, "c_card": 0, "c_fam": 0}
        for m in modes
    }
    buckets: dict[str, dict[str, dict[str, int]]] = {
        m: {name: {"phases": 0, "card": 0, "family": 0, "seq": 0}
            for name, _lo, _hi in WT_BUCKETS}
        for m in modes
    }

    for sample in sorted(IUCR_TRUTH):
        resolved = _resolve_pattern(args.patterns, sample)
        if resolved is None:
            print(f"[skip] {sample}: 找不到谱文件")
            continue
        path, suffix = resolved
        phases = IUCR_TRUTH[sample]
        fine_truths = IUCR_TRUTH_FINE[sample]
        wts = [_wt_of(phases, t.label) for t in fine_truths]

        pattern = load_pattern(path)
        if args.raw_peaks:
            peaks = find_peaks(pattern.two_theta, pattern.intensity)
        else:
            pattern, peaks = auto_process(pattern)

        deep_n = max(args.top_n * 4, 100)
        row: dict = {
            "sample": sample, "file": path.name, "suffix": suffix,
            "n_peaks": len(peaks),
            "truth": [p.label for p in phases],
            "wt_pct": [p.wt_pct for p in phases],
        }

        for mode in modes:
            restraints = None
            if mode == "elements":
                restraints = complement_restraints(_sample_elements(phases))
            whole = _search(peaks, reader, pattern.wavelength, deep_n=deep_n,
                            pools=_pools(restraints))
            coarse_truths = None
            if args.coarse:
                coarse_truths = [truth_entry(p.label, p.formula) for p in phases]
            scored = _score(whole, fine_truths, args.top_n, coarse_truths)

            seq_masks: list[bool] = []
            if args.rounds > 0:
                seq = SequentialIdentifier(peaks, wavelength=pattern.wavelength)
                confirmed: list[Entry] = []
                for _ in range(args.rounds):
                    res = search_residual(seq, reader, top_n=args.top_n,
                                          restraints=restraints)
                    if not res.candidates:
                        break
                    seq.select(res.candidates[0])
                    confirmed.append(res.candidates[0].entry)
                seq_masks = [any(fine_hit_entry(e, t) for e in confirmed)
                             for t in fine_truths]

            t = tot[mode]
            t["samples"] += 1
            t["phases"] += len(fine_truths)
            t["top1"] += scored["t1"]
            t["top5"] += scored["t5"]
            t["all5"] += all(scored["in_top5"])
            t["card"] += sum(scored["in_top"])
            t["fam"] += sum(scored["in_fam"])
            t["seq"] += sum(seq_masks)
            t["trunc"] += whole.truncated
            if args.coarse:
                t["c_card"] += sum(scored["c_in_top"])
                t["c_fam"] += sum(scored["c_in_fam"])
            for w, ok in zip(wts, scored["in_fam"], strict=True):
                if w is not None:
                    t["wt_sum"] += w
                    t["wt_hit"] += w if ok else 0.0
            if len(fine_truths) > 1:
                for w, a, b, sq in zip(wts, scored["in_top"], scored["in_fam"],
                                       seq_masks, strict=True):
                    bk = _bucket_of(w)
                    if bk is None:
                        continue
                    buckets[mode][bk]["phases"] += 1
                    buckets[mode][bk]["card"] += a
                    buckets[mode][bk]["family"] += b
                    buckets[mode][bk]["seq"] += sq

            top1 = scored["top1"]
            row[mode] = {
                "hit_top1": scored["t1"],
                "hit_top5": scored["t5"],
                "phase_in_top": scored["in_top"],
                "phase_in_top_family": scored["in_fam"],
                "phase_in_top5": scored["in_top5"],
                "sequential_masks": seq_masks,
                "sequential_hit_phase": sum(seq_masks),
                "prescreened": whole.n_prescreened,
                "truncated": whole.truncated,
                "top1": top1.entry.entry_id if top1 else None,
                "top1_mineral": (top1.entry.mineral_name or None) if top1 else None,
                "top1_formula": top1.entry.formula if top1 else None,
                "coarse_phase_in_top": scored.get("c_in_top"),
                "coarse_phase_in_top_family": scored.get("c_in_fam"),
            }
        rows.append(row)

    print("\n[主表·矿物名级]  ps=预筛通过数（*=被 1000 上限截断）；每套 4 列 = 卡/族/序贯/wt")
    header = f"{'sample':<10}{'npk':>5}{'ps':>6}  {'wt% 范围':<14}"
    for _ in modes:
        header += f"{'卡':>7}{'族':>7}{'序':>7}{'wt':>7}  "
    print(header)
    for r in rows:
        wts = r["wt_pct"]
        wsum = sum(w for w in wts if w is not None)
        line = f"{r['sample']:<10}{r['n_peaks']:>5}"
        ps = r[modes[0]]["prescreened"]
        line += f"{ps:>5}{'*' if r[modes[0]]['truncated'] else ' '}  "
        line += f"{_fmt_wt_range(wts):<14}"
        for mode in modes:
            m = r[mode]
            k = len(r["truth"])
            whit = sum(w for w, ok in zip(wts, m["phase_in_top_family"], strict=True)
                       if w is not None and ok)
            line += (f"{sum(m['phase_in_top']):>3}/{k:<3}"
                     f"{sum(m['phase_in_top_family']):>3}/{k:<3}"
                     f"{m['sequential_hit_phase']:>3}/{k:<3}"
                     f"{(whit / wsum if wsum else 0.0):>7.3f}  ")
        print(line)

    for mode in modes:
        t = tot[mode]
        label = "plain（只给谱）" if mode == "plain" else "elements（给样品元素）"
        print(f"\n[{label}] 样本 {t['samples']}　相 {t['phases']}"
              f"　Top-1 {t['top1']}/{t['samples']}　Top-5 {t['top5']}/{t['samples']}"
              f"　Top-5 覆盖全相 {t['all5']}/{t['samples']}")
        wt = t["wt_hit"] / t["wt_sum"] if t["wt_sum"] else 0.0
        print(f"  相召回：卡级 {t['card']}/{t['phases']}　族级 {t['fam']}/{t['phases']}"
              f"　序贯 {t['seq']}/{t['phases']}"
              f"　wt 加权（族级）{wt:.3f}"
              f"　预筛被截断 {t['trunc']}/{t['samples']} 样本")
        if args.coarse:
            print(f"  [对照·组成级] 卡级 {t['c_card']}/{t['phases']}"
                  f"　族级 {t['c_fam']}/{t['phases']}"
                  f"　（总数可比，构成不同：见 COARSE_NOTES）")

    print("\n[含量梯度] 多相样本按 weighed wt% 分桶的相召回")
    header = f"{'桶':<8}{'相数':>5}"
    for _ in modes:
        header += f"{'卡':>9}{'族':>9}{'序':>9}"
    print(header)
    for name, _lo, _hi in WT_BUCKETS:
        base = buckets[modes[0]][name]["phases"]
        if not base:
            continue
        line = f"{name:<8}{base:>5}"
        for mode in modes:
            b = buckets[mode][name]
            line += (f"{b['card']:>5}/{b['phases']:<3}"
                     f"{b['family']:>5}/{b['phases']:<3}"
                     f"{b['seq']:>5}/{b['phases']:<3}")
        print(line)
    print("口径：" + FINE_NOTES)

    print(f"\n[未评分] {len(IUCR_EXCLUDED)} 个样本（真值不可验证，不计入任何分母）")
    formulas = {
        "MANNITOL": "C6 H14 O6", "SUCROSE": "C12 H22 O11",
        "VALINE": "C5 H11 N O2", "STARCH": "C6 H10 O5",
        "NIZATIDI": "C12 H21 N5 O2 S2",
    }
    coverage = _library_coverage(args.library, formulas)
    for sample, why in IUCR_EXCLUDED.items():
        extra = ""
        if sample in coverage:
            extra = f"　[当前库内同组成卡 {coverage[sample]} 张]"
        print(f"  {sample:<10}{extra}　{why}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps({
                "dataset": "IUCr CPD",
                "patterns": str(args.patterns),
                "library": str(args.library),
                "library_entry_count": reader.entry_count(),
                "top_n": args.top_n,
                "rounds": args.rounds,
                "config": {
                    "prescreen_order": args.prescreen_order,
                    "family_slots": args.family_slots,
                    "raw_peaks": args.raw_peaks,
                    "modes": modes,
                },
                "notes_fine": FINE_NOTES,
                "notes_coarse": COARSE_NOTES,
                "excluded": IUCR_EXCLUDED,
                "library_coverage": coverage,
                "totals": tot,
                "wt_buckets": buckets,
                "rows": rows,
            }, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        print("json ->", args.out)
    reader.close()


if __name__ == "__main__":
    main()
