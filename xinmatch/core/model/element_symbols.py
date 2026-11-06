"""周期表元素符号与「样品元素」约束（GUI / CLI 共用，**不依赖 PySide6**）。

基准报告 §20：多相样品的次相缺的是**化学信息**，不是预筛名额或排序键。
「只允许 Zn/Al/Ca/O/F」在预筛层只能表达成「其余元素全部标为排除」
（`element_inv` 倒排硬过滤）；给足元素后真实谱相召回 20/43 → 30/43、
COD-Full 合成谱 Top-1 7/13 → 12/13（§23）。

这些是纯数据与纯函数，原本放在 ``xinmatch.ui.periodic_table``（和按钮网格
写在一起）。CLI 若直接 import 会把 PySide6 拖进命令行进程，所以下沉到 core：
GUI 继续 re-export 同名接口，CLI 直接用，两边永远不会各写一份。

**语义护栏**：检出的元素保持 ``OPTIONAL``，绝不标 ``REQUIRED``。次相未必含
主相的每个元素，而且 ``prescreen(elements_allowed=...)`` 是「必须**全部**含有」
—— 按字面传允许集合会把池缩到几十张卡、连真值都 MISS（§20.5）。
"""

from __future__ import annotations

import re

from .restraints import ElementState, Restraints

#: 118 个 IUPAC 元素符号，按**周期表按钮布局**顺序（镧系/锕系单独放末尾），
#: 与 GUI 按钮网格 ``_ELEMENTS`` 逐项一致 —— GUI 在 import 时会校验。
#:
#: 这一层刻意保持零依赖：不 import ``xinmatch.core.db.cif_meta``（那里有绑定
#: ``meta.element_mask_scheme`` 哈希的权威表 ``IUPAC_ELEMENTS``，按原子序数排
#: 序），避免 model 层反向依赖 db 层。两者**集合**必须完全相同，由
#: ``tests/model/test_element_symbols.py`` 守住同步；排列约定不同是有意的
#: （这边服务 UI 摘要展示，那边服务位号），但绝不能互换 —— 位号一变，
#: 已建好的库 ``elem_mask`` 就全读错了。
_ELEMENTS_TEXT = """
    H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn
    Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La
    Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Rf Db Sg Bh Hs Mt Ds Rg
    Cn Nh Fl Mc Lv Ts Og Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Th Pa U Np Pu
    Am Cm Bk Cf Es Fm Md No Lr
    """
ELEMENT_SYMBOLS: tuple[str, ...] = tuple(
    _ELEMENTS_TEXT.split()  # noqa: SIM905 — 表按周期表布局分行，可读性优先
)

_SPLIT_RE = re.compile(r"[,;\s、，/]+")
_SYMBOL_LOOKUP: dict[str, str] = {sym.lower(): sym for sym in ELEMENT_SYMBOLS}


def parse_element_symbols(text: str) -> tuple[list[str], list[str]]:
    """Parse a free-form "detected elements" string into canonical symbols.

    Returns ``(known, unknown)``.  Case is forgiving (``zn`` → ``Zn``),
    duplicates are dropped, and *known* is returned in periodic-table order
    so the UI summary is stable.  Numbers are **not** interpreted: paste
    symbols (``Zn Al Ca O F``), not a formula (``Al2O3``).

    >>> parse_element_symbols("zn, O o F")
    (['O', 'F', 'Zn'], [])
    """
    tokens = [t for t in _SPLIT_RE.split(text.strip()) if t]
    known: list[str] = []
    unknown: list[str] = []
    for token in tokens:
        canon = _SYMBOL_LOOKUP.get(token.lower())
        if canon is None:
            if token not in unknown:
                unknown.append(token)
        elif canon not in known:
            known.append(canon)
    order = {sym: i for i, sym in enumerate(ELEMENT_SYMBOLS)}
    known.sort(key=order.__getitem__)
    return known, unknown


def complement_restraints(detected: list[str] | tuple[str, ...]) -> Restraints:
    """「只允许这几个元素」→ 其余元素全部 ``EXCLUDE`` 的补集约束。

    *detected* 本身不写入 ``Restraints.elements``（即保持 OPTIONAL）。
    返回 ``118 - len(set(detected))`` 个 EXCLUDE 项。
    """
    allowed = set(detected)
    restraints = Restraints()
    for el in ELEMENT_SYMBOLS:
        if el not in allowed:
            restraints.exclude(el)
    return restraints


def restraints_from_sample_elements(text: str) -> Restraints:
    """CLI / GUI 共用入口：一行文本 → 可直接传给检索的补集约束。

    未知符号或空输入抛 :class:`ValueError`（CLI 顶层会转成
    ``error: ...`` 并返回 1），不静默忽略 —— 漏填轻元素会误杀氧化物。
    """
    detected, unknown = parse_element_symbols(text)
    if unknown:
        raise ValueError(
            "无法识别的元素符号：" + "、".join(unknown)
            + "。请填元素符号（如 Zn Al Ca O F），不要填化学式。"
        )
    if not detected:
        raise ValueError("样品元素为空；请填写 XRF/EDS 检出的元素符号")
    restraints = complement_restraints(detected)
    assert set(restraints.elements.values()) == {ElementState.EXCLUDE}
    return restraints


__all__ = [
    "ELEMENT_SYMBOLS",
    "complement_restraints",
    "parse_element_symbols",
    "restraints_from_sample_elements",
]
