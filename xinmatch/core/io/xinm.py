"""``.xinm`` — XinMatch 物相分析状态导出（联合计划 X-1）。

把一次物相分析会话打包成自包含文件，供 XinRefinement 1.1.0 直接导入
（谱图 + 已选物相 CIF + 元数据），打通「检索 → 精修」家族链路。

容器布局（zip，``format: "xinm"`` / ``version: 1``）::

    sample.xinm
    ├── manifest.json          # 结构见 docs/JOINT_PLAN_xinm_xinr.md §2.1
    ├── pattern/pattern.csv    # two_theta,intensity 两列（%.10g）
    └── cifs/*.cif             # 仅 source=cod 且回取成功的相

版权边界：**不打包任何 ICDD/PDF-2 衍生数据文件**。PDF-2 条目只写 id 与元数据、
``structural=false``，``source="pdf2"``（峰表也不导出 —— 那本身就是 ICDD 的
商品数据）。COD 家族用 ``96-XXX-XXXX`` ref_id；PDF-2 用 ``PDF2-<6 位卡片号>``，
由 :func:`_classify_entry` 与 ``unresolved`` 区分开。

CIF 回取复用 :mod:`xinmatch.core.refine.cif_store`（含档案根探测）。
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ..model.project import Project
from ..refine.cif_store import resolve_entry_cif

__all__ = [
    "XINM_FORMAT",
    "XINM_VERSION",
    "XinmExportError",
    "XinmExportReport",
    "XinmPhaseInfo",
    "build_manifest",
    "export_xinm",
]

XINM_FORMAT = "xinm"
XINM_VERSION = 1

_PATTERN_MEMBER = "pattern/pattern.csv"
_CIF_DIR = "cifs"

#: 谱图 CSV 的数值格式（X-1a 约定：%.10g，往返相对误差 ≤ 1e-9，
#: 远超原始数据物理精度——强度为计数、2θ 网格均匀）。
_FLOAT_FMT = "%.10g"

#: 单个 .xinm 解压内容上限（防 zip 炸弹；谱图 ~3 MB + CIF 若干，留足余量）。
_MAX_TOTAL_BYTES = 512 * 1024 * 1024


class XinmExportError(RuntimeError):
    """导出失败（谱图缺失 / 写盘失败等）。"""


@dataclass
class XinmPhaseInfo:
    """单个已选物相在 .xinm 中的落盘结果。"""

    name: str
    entry_id: str
    source: str                 # cod | user_cif | pdf2 | unresolved
    structural: bool
    cif_member: str | None      # zip 内路径；无 CIF 时为 None
    reason: str = ""            # structural=False 时给人看的原因


@dataclass
class XinmExportReport:
    """导出结果摘要（供 GUI 状态栏 / 测试断言）。"""

    path: Path
    n_points: int
    phases: list[XinmPhaseInfo] = field(default_factory=list)
    n_structural: int = 0

    @property
    def summary(self) -> str:
        return (
            f"已导出 {len(self.phases)} 相（{self.n_structural} 个含结构 CIF），"
            f"谱图 {self.n_points} 点 → {self.path.name}"
        )


# --------------------------------------------------------------------------- #
# 谱图 CSV
# --------------------------------------------------------------------------- #
def pattern_to_csv_rows(project: Project) -> tuple[list[str], list[str], int]:
    """锚点谱图 → (two_theta 列文本, intensity 列文本, 点数)。

    用两列独立文本而非行式 CSV：float 格式化一次完成，往返零误差。
    """
    if not project.patterns:
        raise XinmExportError("工程中没有谱图，无法导出 .xinm")
    p = project.patterns[0]
    tt = [_FLOAT_FMT % v for v in p.two_theta.tolist()]
    ii = [_FLOAT_FMT % v for v in p.intensity.tolist()]
    return tt, ii, p.two_theta.size


def _write_pattern_csv(zf: zipfile.ZipFile, project: Project) -> int:
    tt, ii, n = pattern_to_csv_rows(project)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["two_theta", "intensity"])
    writer.writerows(zip(tt, ii, strict=True))
    zf.writestr(_PATTERN_MEMBER, buf.getvalue())
    return n


# --------------------------------------------------------------------------- #
# manifest
# --------------------------------------------------------------------------- #
def _entry_shape_is_ref_id(entry_id: str) -> bool:
    parts = entry_id.strip().split("-")
    return len(parts) == 3 and bool(parts[0]) and (parts[1] + parts[2]).isdigit()


def _is_pdf2_entry(entry_id: str) -> bool:
    """``PDF2-010837`` → 这是 ICDD PDF-2 卡片。

    PDF-2 没有 CIF，也不在 COD 归档里，所以它既不是 ``cod`` 也不该被当成
    「回取失败」的 ``unresolved``：下游（XinRefinement）对 ``pdf2`` 这个枚举值
    的处理是「不注入结构、只画参考线」，与 ``unresolved`` 的「本该有结构但没
    找到」是两回事，混在一起会让报告里的缺结构原因写错。
    """
    head, _, tail = entry_id.strip().partition("-")
    return head.upper() == "PDF2" and bool(tail)


def _classify_entry(
    entry_id: str, cif_member: str | None
) -> tuple[str, bool, str]:
    """判定一个物相的结构来源 → ``(source, structural, reason)``。

    ``source`` 的四个取值与 XinRefinement 侧 ``XinmPhase.source`` 的枚举一致：
    ``cod`` 有结构 / ``pdf2`` 无结构但来源明确 / ``user_cif`` 用户自带 /
    ``unresolved`` 本该有结构却没回取到。区分 ``pdf2`` 与 ``unresolved`` 不是
    文字游戏：下游据此决定「不注入结构」还是「报告结构缺失」。
    """
    if cif_member is not None:
        return "cod", True, ""
    if _entry_shape_is_ref_id(entry_id):
        return "cod", False, "COD 归档未命中该条目的 CIF"
    if _is_pdf2_entry(entry_id):
        return "pdf2", False, "ICDD PDF-2 卡片无 CIF，仅提供参考峰表"
    return "unresolved", False, "条目 id 不是 COD ref_id 形态，无法回取 CIF"


def build_manifest(
    project: Project,
    *,
    cif_members: dict[str, str] | None = None,
    app_version: str = "",
) -> dict[str, Any]:
    """组装 manifest dict（cif_members: entry_id → zip 内 CIF 路径）。"""
    cif_members = cif_members or {}
    p = project.patterns[0] if project.patterns else None
    meta = dict(p.metadata) if p is not None else {}

    phases: list[dict[str, Any]] = []
    for i, ph in enumerate(project.selected_phases):
        eid = ph.entry.entry_id
        member = cif_members.get(eid)
        source, structural, reason = _classify_entry(eid, member)
        phases.append({
            "name": ph.entry.mineral_name or ph.entry.formula or f"phase_{i + 1}",
            "source": source,
            "entry_id": eid,
            "cif_file": member,
            "structural": structural,
            "reason": reason,
            "fom": None,
            "scale_factor": float(ph.scale_factor),
            "two_theta_shift": float(ph.two_theta_shift),
            "weight_fraction": ph.weight_fraction,
            "cell": ph.entry.cell.to_dict() if ph.entry.cell else None,
            "space_group": ph.entry.space_group,
            "formula": ph.entry.formula,
            "mineral_name": ph.entry.mineral_name,
        })

    candidates_summary = [
        {
            "name": e.mineral_name or e.formula or eid,
            "entry_id": eid,
            "source": _classify_entry(eid, None)[0],
            "cif_file": None,
        }
        for e, _fom in project.candidates[:20]
    ]

    # 扫描范围 / 步长：导出侧做一次规范化，别把 None 或 0.019999999999999574
    # 这类浮点尾巴丢给下游（XinRefinement 会把它写进画布与报告头）。
    if p is not None and p.two_theta.size:
        tmin = meta.get("tmin")
        tmax = meta.get("tmax")
        tmin = round(float(p.two_theta[0]), 6) if tmin is None else round(float(tmin), 6)
        tmax = (round(float(p.two_theta[-1]), 6) if tmax is None
                else round(float(tmax), 6))
        step = round(float(p.step), 6) if p.step else None
    else:  # pragma: no cover - patterns 非空已在上游保证
        tmin = tmax = step = None

    return {
        "format": XINM_FORMAT,
        "version": XINM_VERSION,
        "created": datetime.now().isoformat(timespec="seconds"),
        "app": {"name": "XinMatch", "version": app_version},
        "pattern": {
            "file": _PATTERN_MEMBER,
            "source_path": meta.get("source_path") or meta.get("path") or "",
            "wavelength": float(p.wavelength) if p is not None else 1.5406,
            "anode": meta.get("anode", "Cu"),
            "tmin": tmin,
            "tmax": tmax,
            "step": step,
            "metadata": meta,
        },
        "peaks": [pk.to_dict() for pk in project.peaks],
        "phases": phases,
        "candidates_summary": candidates_summary,
        "restraints": project.restraints.to_dict(),
        "notes": "",
    }


# --------------------------------------------------------------------------- #
# 主入口
# --------------------------------------------------------------------------- #
def export_xinm(
    project: Project,
    path: str | Path,
    *,
    include_candidates: bool = True,
    cod_root: str | Path | None = None,
    app_version: str = "",
) -> XinmExportReport:
    """把当前物相分析状态导出为 ``.xinm``（zip 容器）。

    Parameters
    ----------
    project:
        XinMatch 工程（至少含锚点谱图）。
    path:
        目标 ``.xinm`` 路径（建议扩展名 .xinm，不强制）。
    include_candidates:
        是否写 ``candidates_summary``（默认 True；不嵌 CIF，体积可忽略）。
    cod_root:
        COD 档案根（默认走 :mod:`cif_store` 的探测链）。
    app_version:
        写入 manifest 的软件版本（调用方传 ``xinmatch.__version__``）。

    Returns
    -------
    XinmExportReport
        含每相落盘情况；个别 CIF 回取失败**不阻断导出**（该相标记
        ``structural=false``，由 XinRefinement 提示用户手动补 CIF）。
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    cif_members: dict[str, str] = {}
    cif_sources: dict[str, Path] = {}
    infos: list[XinmPhaseInfo] = []
    for i, ph in enumerate(project.selected_phases):
        eid = ph.entry.entry_id
        name = ph.entry.mineral_name or ph.entry.formula or f"phase_{i + 1}"
        src = resolve_entry_cif(eid, cod_root)
        if src is not None:
            member = f"{_CIF_DIR}/{Path(src).stem}.cif"
            cif_members[eid] = member
            cif_sources[eid] = src
            infos.append(XinmPhaseInfo(name, eid, "cod", True, member))
        else:
            source, _structural, reason = _classify_entry(eid, None)
            infos.append(XinmPhaseInfo(name, eid, source, False, None, reason))

    manifest = build_manifest(
        project, cif_members=cif_members, app_version=app_version)
    if not include_candidates:
        manifest["candidates_summary"] = []

    try:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            n = _write_pattern_csv(zf, project)
            for eid, member in cif_members.items():
                zf.write(cif_sources[eid], member)
            zf.writestr("manifest.json", json.dumps(
                manifest, ensure_ascii=False, indent=2))
    except OSError as exc:
        raise XinmExportError(f"写出 .xinm 失败：{exc}") from exc

    return XinmExportReport(
        path=out, n_points=n, phases=infos,
        n_structural=sum(1 for x in infos if x.structural),
    )
