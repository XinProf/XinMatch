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

Two calibers (2026-11-06)
-------------------------
``TRUTH`` is the **composition-level** caliber above — unchanged since 3.2.0,
so its numbers stay comparable across versions.  ``TRUTH_FINE`` adds a
**mineral-name-level** caliber that reads ``entries.mineral_name``:

* polymorphs are separated instead of merged (anatase ≠ rutile, quartz ≠
  cristobalite) — the library carries those names;
* solid solutions that a formula ratio cannot express are recovered by name
  (Biotite, Hornblende) or by element set (NCM811), moving them out of
  :data:`EXCLUDED` into the denominator;
* a card **without** a name falls back to composition, except for polymorph
  splits where composition cannot tell the two truths apart.

The fine caliber is a *superset* of the coarse one (denominator 50 vs 43), so
the two are never mixed in one ratio — see ``docs/基准报告-物相检索-v3.md`` §17.

Usage::

    python -m tools.bench_real_samples \
        --patterns D:\\Project\\XRD\\test_xrd\\txt \
        --library D:\\Project\\XRD\\XinMatch-DataBase\\data\\COD-Inorg-20261020.xinDB \
        --out .scratch/bench_real_cod.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from xinmatch.core.db.reader_v3 import XinDBReader
from xinmatch.core.io import load_pattern
from xinmatch.core.model import Entry
from xinmatch.core.model.entry import parse_formula
from xinmatch.core.model.restraints import Restraints
from xinmatch.core.peak.peak_search import find_peaks
from xinmatch.core.preprocess.auto_pipeline import auto_process
from xinmatch.core.search.fom import CandidateResult
from xinmatch.core.search.mineral_name import has_species_name, mineral_name_matches
from xinmatch.core.search.phase_key import group_same_phase, same_phase
from xinmatch.core.search.search_match import search_match
from xinmatch.core.search.sequential import SequentialIdentifier, search_residual

#: 元素符号全集，用于构造「其余元素一律排除」的排除集。
#: 「必须不含」是预筛层唯一的"减法"约束（`elements_allowed` 是"必须全含"，
#: 语义不同），所以"只允许这些元素"必须表达成补集。
ALL_ELEMENTS: tuple[str, ...] = tuple(
    ["H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne", "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar", "K", "Ca", "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn", "Ga", "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr", "Y", "Zr", "Nb", "Mo", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn", "Sb", "Te", "I", "Xe", "Cs", "Ba", "La", "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb", "Ho", "Er", "Tm", "Yb", "Lu", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg", "Tl", "Pb", "Bi", "Po", "At", "Rn", "Ra", "Ac", "Th", "Pa", "U", "Np", "Pu"]
)

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


@dataclass(frozen=True)
class FineTruth:
    """One truth phase under the **mineral-name-level** caliber.

    Args:
        label: Human-readable phase name (report column).
        minerals: Names the phase is known by; a card hits when its
            ``mineral_name`` normalises to any of them
            (:func:`~xinmatch.core.search.mineral_name.mineral_name_matches`).
        formula: Composition ratio, used only as the fallback for a card that
            carries **no** mineral name.
        family_required: Elements a card must contain to be this doped solid
            solution.  Together with *family_optional* it replaces the
            composition test, which can never match because the library
            reproduces neither the doping level nor the exact ratio.
        family_optional: The only other elements a card may carry — the variable
            dopants.  A card with an element outside
            ``required | optional`` is a different phase.
        split: ``True`` when another truth in the same sample has the same
            composition (anatase/rutile, quartz/cristobalite).  A nameless card
            then cannot be attributed, so it does not count for either side —
            composition alone is not evidence for a specific polymorph.
    """

    label: str
    minerals: tuple[str, ...] = ()
    formula: str | None = None
    family_required: frozenset[str] = frozenset()
    family_optional: frozenset[str] = frozenset()
    split: bool = False

    @property
    def has_family(self) -> bool:
        return bool(self.family_required)


#: 矿物名级口径：13 组 × 50 个真值相（组成级 43 个 + 3.4.1 起被排除的 7 个）。
#: 矿物名均已在 COD-Inorg-20261020 里定位到（覆盖率见报告 §17.1）；
#: ``split=True`` 只标在同一组里成对出现的同组成多晶型。
TRUTH_FINE: dict[str, list[FineTruth]] = {
    "1-1": [FineTruth("Triphylite", ("Triphylite",), "Fe Li O4 P")],
    # NCM811 没有矿物名，库内也没有等比例卡（榜首是 Li1.01Mn0.1Ni0.89O2，缺 Co）。
    # 判据：必含 Li/Ni/O，其余元素只能是 Co/Mn 这类可变掺杂 → 同一层状家族。
    "1-2": [FineTruth("NCM811",
                      family_required=frozenset({"Li", "Ni", "O"}),
                      family_optional=frozenset({"Co", "Mn"}))],
    "2-1": [FineTruth("Zincite", ("Zincite",), "O Zn"),
            FineTruth("Calcite", ("Calcite",), "C Ca O3")],
    "2-2": [FineTruth("Anatase", ("Anatase",), "O2 Ti", split=True),
            FineTruth("Rutile", ("Rutile",), "O2 Ti", split=True)],
    "3-1": [FineTruth("Zincite", ("Zincite",), "O Zn"),
            FineTruth("Corundum", ("Corundum",), "Al2 O3"),
            FineTruth("Fluorite", ("Fluorite",), "Ca F2")],
    "3-2": [FineTruth("Zincite", ("Zincite",), "O Zn"),
            FineTruth("Corundum", ("Corundum",), "Al2 O3"),
            FineTruth("Fluorite", ("Fluorite",), "Ca F2")],
    "4-1": [FineTruth("Zincite", ("Zincite",), "O Zn"),
            FineTruth("Corundum", ("Corundum",), "Al2 O3"),
            FineTruth("Fluorite", ("Fluorite",), "Ca F2"),
            FineTruth("Brucite", ("Brucite",), "H2 Mg O2")],
    "5-1": [FineTruth("Quartz", ("Quartz",), "O2 Si", split=True),
            FineTruth("Cristobalite", ("Cristobalite",), "O2 Si", split=True),
            FineTruth("Calcite", ("Calcite",), "C Ca O3"),
            FineTruth("Magnesite", ("Magnesite",), "C Mg O3"),
            FineTruth("Dolomite", ("Dolomite",), "C2 Ca Mg O6")],
    "5-2": [FineTruth("Quartz", ("Quartz",), "O2 Si", split=True),
            FineTruth("Cristobalite", ("Cristobalite",), "O2 Si", split=True),
            FineTruth("Calcite", ("Calcite",), "C Ca O3"),
            FineTruth("Hematite", ("Hematite",), "Fe2 O3"),
            FineTruth("Muscovite", ("Muscovite", "Muscovite 2M1"), "Al3 H2 K O12 Si3")],
    "5-2b": [FineTruth("Quartz", ("Quartz",), "O2 Si", split=True),
             FineTruth("Cristobalite", ("Cristobalite",), "O2 Si", split=True),
             FineTruth("Calcite", ("Calcite",), "C Ca O3"),
             FineTruth("Hematite", ("Hematite",), "Fe2 O3"),
             FineTruth("Muscovite", ("Muscovite", "Muscovite 2M1"), "Al3 H2 K O12 Si3")],
    "5-3": [FineTruth("Quartz", ("Quartz",), "O2 Si"),
            FineTruth("Gehlenite", ("Gehlenite",), "Al2 Ca2 O7 Si"),
            FineTruth("Fluorapatite", ("Fluorapatite",), "Ca5 F O12 P3"),
            FineTruth("Goethite", ("Goethite",), "H Fe O2"),
            FineTruth("Kaolinite", ("Kaolinite",), "Al2 H4 O9 Si2")],
    "7-1": [FineTruth("Quartz", ("Quartz",), "O2 Si"),
            FineTruth("Boehmite", ("Boehmite",), "H Al O2"),
            FineTruth("Anatase", ("Anatase",), "O2 Ti"),
            FineTruth("Goethite", ("Goethite",), "H Fe O2"),
            FineTruth("Kaolinite", ("Kaolinite",), "Al2 H4 O9 Si2"),
            FineTruth("Gibbsite", ("Gibbsite",), "Al H3 O3"),
            FineTruth("Hematite", ("Hematite",), "Fe2 O3")],
    "7-2": [FineTruth("Quartz", ("Quartz",), "O2 Si", split=True),
            FineTruth("Feldspar", ("Feldspar", "K-feldspar"), "Al K O8 Si3"),
            FineTruth("Albite", ("Albite",), "Al Na O8 Si3"),
            FineTruth("Clinochlore", ("Clinochlore",), "Al2 H8 Mg5 O18 Si3"),
            FineTruth("Zircon", ("Zircon",), "O4 Si Zr"),
            # 固溶体：组成比随卡变化，只有矿物名可判
            FineTruth("Biotite", ("Biotite",)),
            FineTruth("Hornblende", ("Hornblende", "Magnesiohornblende",
                                     "Ferrohornblende"))],
}

FINE_NOTES = (
    "矿物名级口径（细）：有矿物名的卡按名判定（多晶型不再合并），无名的卡回落到组成比；"
    "真值相含同一组成的两种多晶型时，无名卡不计入任一侧；"
    "NCM811 判「必含 Li/Ni/O、其余元素只允许 Co/Mn 掺杂」的层状家族，"
    "Biotite/Hornblende 仅按矿物名判定。"
    "分母 50 个相（组成级 43 个 + 此前被排除的 7 个），两个口径不可混算。"
)


def _oracle_restraints(items, fine_truths) -> Restraints | None:
    """「样品元素已知」口径的约束：真值元素留下，其余全部标为必须不含。

    现实中样品元素来自 XRF/EDS 或工艺配方，不是从答案反推。这里用真值构造，
    所以它是**上界**：衡量"化学信息给足时引擎能做到什么"，不能当自动结果报。
    """
    elems: set[str] = set()
    for _label, formula in items:
        elems |= set(parse_formula(formula))
    for t in fine_truths:
        elems |= set(t.family_required) | set(t.family_optional)
        if t.formula:
            elems |= set(parse_formula(t.formula))
    if not elems:
        return None
    restraints = Restraints()
    for el in ALL_ELEMENTS:
        if el not in elems:
            restraints.exclude(el)
    return restraints


def truth_entry(label: str, formula: str) -> Entry:
    """Truth phase as an Entry carrying **only** a formula (no cell).

    ``same_phase`` then falls back to the composition-ratio rule, which is the
    only thing a mineral name can honestly claim to know.

    Public because :mod:`tools.bench_iucr` scores its patterns with the *same*
    rule — one definition of "hit", two ground-truth sets.
    """
    return Entry(
        entry_id=f"truth:{label}",
        formula=formula,
        d_spacings=np.zeros(0, dtype=float),
        intensities=np.zeros(0, dtype=float),
    )


def _hit(cand: CandidateResult, truths: list[Entry]) -> bool:
    return any(same_phase(cand.entry, t) for t in truths)


def fine_hit_entry(entry: Entry, truth: FineTruth) -> bool:
    """Mineral-name-level hit test for one card against one truth phase.

    Precedence is deliberate: a card that **has** a mineral name is judged by
    that name alone (a named rutile is a miss for an anatase truth even though
    the composition matches).  Composition is only consulted when the card
    carries no name — and not at all for a polymorph split, where composition is
    known to be unable to distinguish the truths.
    """
    if truth.has_family:
        elems = frozenset(entry.elements or ())
        return (truth.family_required <= elems
                and elems <= truth.family_required | truth.family_optional)
    if truth.minerals:
        # A non-empty string is not yet evidence: "hexagonal" / "unknown" must be
        # treated exactly like a missing name (see mineral_name.has_species_name).
        if has_species_name(entry.mineral_name):
            return mineral_name_matches(entry.mineral_name, truth.minerals)
        if truth.split or not truth.formula:
            return False
        return same_phase(entry, truth_entry(truth.label, truth.formula))
    return bool(truth.formula) and same_phase(
        entry, truth_entry(truth.label, truth.formula)
    )


def _fine_hit(cand: CandidateResult, truths: list[FineTruth]) -> bool:
    return any(fine_hit_entry(cand.entry, t) for t in truths)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patterns", type=Path, required=True)
    ap.add_argument("--library", type=Path, required=True)
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--rounds", type=int, default=3,
                    help="序贯确认轮数（0 = 只跑整谱检索）")
    ap.add_argument("--family-slots", type=int, default=None,
                    help="预筛每族名额上限（默认不设限；1 = 每族只留最强一张卡）")
    ap.add_argument("--oracle-elements", action="store_true",
                    help="额外跑一套「元素上界」口径：用真值化学式推出样品元素，"
                         "把其余元素全部标为必须不含（现实中由 XRF/EDS 给出）。"
                         "这是**上界**，不是可直接交付的自动结果")
    ap.add_argument("--raw-peaks", action="store_true",
                    help="不做自动预处理，直接在原始谱上寻峰（用于对照）")
    ap.add_argument("--prescreen-order", choices=("intensity", "hits"),
                    default="intensity",
                    help="预筛第二排序键（默认 intensity = 发布口径；hits 为待裁定口径）。"
                         "配置会写进结果 JSON —— 基线按配置认，不按文件名认")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    reader = XinDBReader(args.library, family_slots=args.family_slots,
                         prescreen_order=args.prescreen_order)
    print(f"[配置] prescreen_order={args.prescreen_order}  "
          f"family_slots={args.family_slots}  top_n={args.top_n}  rounds={args.rounds}")
    rows: list[dict] = []
    n = n_top1 = n_top5 = n_all5 = n_full = 0
    hit_phases = hit_phases_fam = n_phases = 0
    # 细口径累计（与粗口径完全并行，互不影响）
    f_n = 0
    f_top1 = f_top5 = f_all5 = f_full = 0
    f_hit = f_hit_fam = f_n_phases = 0
    # 元素上界口径（--oracle-elements）：与上面两套并列，分母相同
    e_n = e_top1 = e_top5 = e_hit = e_hit_fam = e_n_phases = e_full = 0

    for sample, items in sorted(TRUTH.items()):
        path = args.patterns / f"{sample}.txt"
        if not path.is_file():
            print(f"[skip] {sample}: {path} 不存在")
            continue
        if not items and not TRUTH_FINE.get(sample):
            continue
        # A sample whose coarse truth is empty (1-2 / NCM811) still runs: it is
        # only excluded from the *coarse* denominators, not from the fine ones.
        in_coarse = bool(items)
        pattern = load_pattern(path)
        if args.raw_peaks:
            peaks = find_peaks(pattern.two_theta, pattern.intensity)
        else:
            # 与 GUI 导入路径一致：平滑 → 背景 → 扣除 → Kα2 剥离 → 寻峰
            pattern, peaks = auto_process(pattern)
        truths = [truth_entry(label, formula) for label, formula in items]
        fine_truths = TRUTH_FINE.get(sample, [])

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

        # 细口径（矿物名级）：同一批候选，换用 TRUTH_FINE 判定
        f_in_top = [any(fine_hit_entry(c.entry, t) for c in cards) for t in fine_truths]
        f_in_fam = [any(fine_hit_entry(c.entry, t) for c in fam_reps)
                    for t in fine_truths]
        f_in_top5 = [any(fine_hit_entry(c.entry, t) for c in top5)
                     for t in fine_truths]
        f_t1 = bool(top1) and any(fine_hit_entry(top1.entry, t) for t in fine_truths)
        f_t5 = any(_fine_hit(c, fine_truths) for c in top5)

        found: list[str] = []
        cover = 0.0
        found_phases = 0
        found_phases_fine = 0
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
            found_phases_fine = sum(
                any(fine_hit_entry(e, t) for e in confirmed) for t in fine_truths
            )

        if in_coarse:
            n += 1
            n_top1 += t1
            n_top5 += t5
            n_all5 += all(in_top5)
            n_full += found_phases == len(truths)
            n_phases += len(truths)
            hit_phases += sum(in_top)
            hit_phases_fam += sum(in_fam)
        f_n += 1
        f_top1 += f_t1
        f_top5 += f_t5
        f_all5 += bool(f_in_top5) and all(f_in_top5)
        f_full += bool(fine_truths) and found_phases_fine == len(fine_truths)
        f_n_phases += len(fine_truths)
        f_hit += sum(f_in_top)
        f_hit_fam += sum(f_in_fam)
        e_top: list[bool] = []
        e_top_fam: list[bool] = []
        e_t1 = e_t5 = False
        e_found = 0
        if args.oracle_elements:
            restraints = _oracle_restraints(items, fine_truths)
            if restraints is not None:
                whole_e = search_match(peaks, reader, pattern.wavelength,
                                       top_n=deep_n, restraints=restraints)
                cards_e = whole_e[:args.top_n]
                fam_e = [whole_e[g[0]] for g in
                         group_same_phase([c.entry for c in whole_e])][:args.top_n]
                e_top = [any(_hit(c, [t]) for c in cards_e) for t in truths]
                e_top_fam = [any(_hit(c, [t]) for c in fam_e) for t in truths]
                e_t1 = bool(whole_e) and _hit(whole_e[0], truths)
                e_t5 = any(_hit(c, truths) for c in whole_e[:5])
                if items:
                    e_n += 1
                    e_n_phases += len(truths)
                    e_top1 += e_t1
                    e_top5 += e_t5
                    e_hit += sum(e_top)
                    e_hit_fam += sum(e_top_fam)
                if args.rounds > 0:
                    seq_e = SequentialIdentifier(peaks, wavelength=pattern.wavelength)
                    confirmed_e: list[Entry] = []
                    for _ in range(args.rounds):
                        res_e = search_residual(seq_e, reader, top_n=args.top_n,
                                                restraints=restraints)
                        if not res_e.candidates:
                            break
                        seq_e.select(res_e.candidates[0])
                        confirmed_e.append(res_e.candidates[0].entry)
                    e_found = sum(
                        any(same_phase(e, t) for e in confirmed_e) for t in truths
                    )
                    if items:
                        e_full += e_found == len(truths)

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
            # ── 细口径（矿物名级），与上面的组成级字段并列，不可混算 ──
            "fine_truth": [t.label for t in fine_truths],
            "fine_phase_in_top": f_in_top,
            "fine_phase_in_top_family": f_in_fam,
            "fine_phase_in_top5": f_in_top5,
            "fine_hit_top1": f_t1,
            "fine_hit_top5": f_t5,
            "fine_sequential_hit_phase": found_phases_fine,
            "fine_top1_mineral": (top1.entry.mineral_name or None) if top1 else None,
            # ── 元素上界口径（--oracle-elements），同样独立，不与上面混算 ──
            "oracle_phase_in_top": e_top,
            "oracle_phase_in_top_family": e_top_fam,
            "oracle_hit_top1": e_t1,
            "oracle_hit_top5": e_t5,
            "oracle_sequential_hit_phase": e_found,
        })

    print(f"{'sample':<8}{'npk':>5}  {'Top-1':<15}{'T1':>3}{'T5':>3}  "
          f"{'卡级':<14}{'族级':<14}{'序贯':>6}")
    for r in rows:
        if not r["truth"]:
            continue  # 1-2 / NCM811 只参与细口径，不进粗口径表
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

    # ── 细口径（矿物名级）：分母更大，与上面的数字不可混算 ──
    print(f"\n[细口径] 矿物名级（分母 {f_n_phases} 相，含多晶型分列与固溶体）")
    print(f"{'sample':<8}{'npk':>5}  {'Top-1矿物名':<22}{'T1':>3}{'T5':>3}  "
          f"{'卡级':<14}{'族级':<14}{'序贯':>6}")
    for r in rows:
        marks = "".join("Y" if h else "." for h in r["fine_phase_in_top"])
        marks_f = "".join("Y" if h else "." for h in r["fine_phase_in_top_family"])
        print(f"{r['sample']:<8}{r['n_peaks']:>5}  "
              f"{(r['fine_top1_mineral'] or r['top1'] or '-'):<22}"
              f"{'Y' if r['fine_hit_top1'] else '.':>3}"
              f"{'Y' if r['fine_hit_top5'] else '.':>3}  "
              f"{marks:<6}{sum(r['fine_phase_in_top']):>2}/{len(r['fine_truth']):<5}"
              f"{marks_f:<6}{sum(r['fine_phase_in_top_family']):>2}/"
              f"{len(r['fine_truth']):<5}"
              f"{r['fine_sequential_hit_phase']}/{len(r['fine_truth'])}")

    print(f"\n[细口径] 整谱 Top-1 {f_top1}/{f_n}　Top-5 {f_top5}/{f_n}　"
          f"Top-5 覆盖全部真相相 {f_all5}/{f_n}")
    print(f"[细口径] 相召回（Top-{args.top_n} 卡）{f_hit}/{f_n_phases}　"
          f"（Top-{args.top_n} 族，折叠后）{f_hit_fam}/{f_n_phases}　"
          f"序贯完整回收 {f_full}/{f_n}")
    print(f"细口径定义：{FINE_NOTES}")

    if args.oracle_elements:
        print(f"\n[元素上界] 真值元素已知（其余必须不含），分母 {e_n_phases} 相")
        print(f"{'sample':<8}{'npk':>5}  {'卡级':<14}{'族级':<14}{'序贯':>6}")
        for r in rows:
            if not r["truth"]:
                continue
            marks = "".join("Y" if h else "." for h in r["oracle_phase_in_top"])
            marks_f = "".join("Y" if h else "." for h in r["oracle_phase_in_top_family"])
            print(f"{r['sample']:<8}{r['n_peaks']:>5}  "
                  f"{marks:<6}{sum(r['oracle_phase_in_top']):>2}/"
                  f"{len(r['truth']):<5}"
                  f"{marks_f:<6}{sum(r['oracle_phase_in_top_family']):>2}/"
                  f"{len(r['truth']):<5}"
                  f"{r['oracle_sequential_hit_phase']}/{len(r['truth'])}")
        print(f"[元素上界] 整谱 Top-1 {e_top1}/{e_n}　Top-5 {e_top5}/{e_n}　"
              f"相召回（Top-{args.top_n} 卡）{e_hit}/{e_n_phases}　"
              f"（族）{e_hit_fam}/{e_n_phases}　序贯完整 {e_full}/{e_n}")
        print("[元素上界] 这是**上界**：元素由真值反推，现实中来自 XRF/EDS 或配方")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps({
                "patterns": str(args.patterns),
                "library": str(args.library),
                "top_n": args.top_n,
                "rounds": args.rounds,
                "config": {
                    "prescreen_order": args.prescreen_order,
                    "family_slots": args.family_slots,
                },
                "notes": NOTES,
                "notes_fine": FINE_NOTES,
                "excluded": EXCLUDED,
                "totals": {
                    "samples": n, "top1": n_top1, "top5": n_top5,
                    "top5_all_phases": n_all5,
                    "phase_recall": [hit_phases, n_phases],
                    "full_recovery": n_full,
                },
                "totals_oracle": {
                    "samples": e_n, "top1": e_top1, "top5": e_top5,
                    "phase_recall": [e_hit, e_n_phases],
                    "phase_recall_family": [e_hit_fam, e_n_phases],
                    "full_recovery": e_full,
                },
                "totals_fine": {
                    "samples": f_n, "top1": f_top1, "top5": f_top5,
                    "top5_all_phases": f_all5,
                    "phase_recall": [f_hit, f_n_phases],
                    "phase_recall_family": [f_hit_fam, f_n_phases],
                    "full_recovery": f_full,
                },
                "rows": rows,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("json ->", args.out)
    reader.close()


if __name__ == "__main__":
    main()
