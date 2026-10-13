"""基于 Rietveld 精修的定量相分析（T8.3）。

委托 GSAS-II 执行全谱拟合，从精修后的各相 scale factor 推导重量分数。
公式见 Hill & Howard (1987)，GSAS-II 内部已自动计算（.lst 中
``Weight fraction`` 行）。

参考软件 对应功能
----------------
* *Quantify -> Rietveld*（``docs/Rietveld.md``、
  ``docs/quant_analysis_Rietveld.md``）：全谱最小二乘拟合，收敛后各相
  重量分数直接回填到 match list。

精度策略
--------
建议两轮精修（``docs/Rietveld_Auto_Par.md``）：

1. 第一轮：scale + background 粗拟合，获得合理初值；
2. 第二轮：scale + background + cell + profile(U/V/W) + zero-shift
   精修，提高 wt% 精度。

当前驱动（``gsas2_project._DRIVER_SOURCE``）已在单次运行内按阶段逐步
打开参数（background → cell → profile → shift → atoms），等效于上述
两轮策略。如需进一步控制，通过 *options* 透传
:class:`~xinmatch.core.refine.gsas2_adapter.RefineOptions` 即可。

精度参考（实测于 IUCr CPD-1c / test_xrd 3-1 / test_xrd 4-1，max_iter=40, 2θ=20-120°, refine_atoms=True）
----------------------------------------------------------------------------------------------------
CPD-1c / 3-1 Rwp ≈ 14.3-14.6 %，GoF ≈ 2.3-2.4；4-1 Rwp ≈ 16.7 %。

**CPD-1c / 3-1（三相标准混合）**

+----------+--------+-----------+-----------+-----------+-----------+
| 相       | 真值%  | CPD-1c 测 | 3-1 测    | CPD-1c 误 | 3-1 误    |
+==========+========+===========+===========+===========+===========+
| Al₂O₃    |  5.04  |  14.42 %  |  14.46 %  |  +9.38    |  +9.42    |
| ZnO      | 93.59  |  81.92 %  |  81.85 %  | -11.67    | -11.74    |
| CaF₂     |  1.36  |   3.66 %  |   3.68 %  |  +2.30 ✓  |  +2.32 ✓  |
+----------+--------+-----------+-----------+-----------+-----------+

**4-1（四相标准混合，含 Brucite Mg(OH)₂）**

+----------+--------+-----------+-----------+
| 相       | 真值%  | 4-1 实测  | 4-1 误差  |
+==========+========+===========+===========+
| ZnO      | 19.94  |   8.40 %  | -11.54    |
| Al₂O₃    | 21.27  |  28.92 %  |  +7.65    |
| CaF₂     | 22.53  |  29.18 %  |  +6.65    |
| Brucite  | 36.26  |  33.50 %  |  -2.76 ✓  |
+----------+--------+-----------+-----------+

微量相 CaF₂（CPD-1c）和 Brucite（4-1）误差 < 3 wt %（达标）。
Major 相误差 ~7-12 wt %，归因：
1. 手写 Al₂O₃ CIF 的原子坐标/U_iso 非精修标准值（已修正 U_iso 从
   0.30 → 0.004/0.005，但坐标仍为文本书本值）；
2. ZnO 择优取向（March-Dollase）未有效建模——尝试 `set_HAP_refinements
   ({"PO": True})` 未改变精修结果，需进一步调试 GSAS-II HAP API；
3. 通用仪器参数文件（_DEFAULT_CU_PRM）与实际衍射仪的零位/透明/样品
   偏移不匹配。使用 COD 标准 CIF + 实测仪器参数 + PO 建模后，Major
   相误差预期可降至 < 3 wt %（Phase 8 验收阈值）。

References
----------
* R.J. Hill & C.J. Howard, "Quantitative phase analysis from neutron powder
  diffraction data using the Rietveld method", *J. Appl. Cryst.* 20 (1987)
  467-476. https://doi.org/10.1107/S0021889887086199
* B.H. Toby, R.B. Von Dreele, "GSAS-II", *J. Appl. Cryst.* 46 (2013) 544-549.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from xinmatch.core.model.pattern import Pattern
from xinmatch.core.model.phase import Phase
from xinmatch.core.refine.gsas2_adapter import RefineOptions
from xinmatch.core.refine.gsas2_parse import (
    Gsas2RefineOutcome,
    parse_refinement,
)
from xinmatch.core.report.report_model import RFactorSection

from .internal_standard import QuantResult as _ISQuantResult

__all__ = [
    "RietveldQuantResult",
    "rietveld_quantify",
]


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------
@dataclass
class RietveldQuantResult:
    """Rietveld 定量结果。

    Attributes
    ----------
    weight_fractions:
        ``{phase_name: 重量分数 [0,1]}``，所有晶相合计 ≈ 1.0。
    uncertainties:
        ``{phase_name: 重量分数 1-σ 不确定度}``，取自 .lst 中的 sig 值。
    r_factors:
        剖面一致性因子（Rwp / Rp / Rexp / χ²，小数值）。
    gof:
        拟合优度 GOF（√reduced χ²）。
    refined_phases:
        精修后各相的详细信息（晶胞、原子坐标等），透传自
        :class:`~xinmatch.core.refine.gsas2_parse.Gsas2RefineOutcome`。
    gpx_path:
        GSAS-II 工程文件路径。
    lst_path:
        .lst 精修日志路径。
    prf_path:
        .prf 残差谱路径。
    work_dir:
        所有产物所在目录。
    outcome:
        完整的 :class:`Gsas2RefineOutcome`（含 observed/fitted/residual
        谱），供 GUI 绘图使用。
    """

    weight_fractions: dict[str, float]
    uncertainties: dict[str, float]
    r_factors: RFactorSection
    gof: float | None
    refined_phases: list[Any] = field(default_factory=list)
    gpx_path: Path | None = None
    lst_path: Path | None = None
    prf_path: Path | None = None
    work_dir: Path | None = None
    outcome: Gsas2RefineOutcome | None = None

    def to_quant_result(self) -> _ISQuantResult:
        """转换为与内标法兼容的 :class:`QuantResult`（无内标概念）。

        internal_standard 字段中 ``internal_standard`` 留空字符串，
        ``standard_known_wt_fraction`` 设为 0，``standard_recovery``
        设为重量分数之和。
        """
        recovery = sum(self.weight_fractions.values())
        return _ISQuantResult(
            weight_fractions=dict(self.weight_fractions),
            uncertainties=dict(self.uncertainties),
            internal_standard="",
            standard_known_wt_fraction=0.0,
            standard_recovery=recovery,
            amorphous_fraction=None,
        )


# ---------------------------------------------------------------------------
# Main quantification entry
# ---------------------------------------------------------------------------
def rietveld_quantify(
    pattern: Pattern,
    phases: Sequence[Phase],
    cif_paths: Mapping[str, str | os.PathLike[str]],
    work_dir: str | Path | None = None,
    options: RefineOptions | None = None,
    *,
    driver: Callable[..., Any] | None = None,
    instrument_file: str | os.PathLike[str] | None = None,
) -> RietveldQuantResult:
    """基于 Rietveld 精修的定量相分析。

    流程：构造 GSAS-II 工程 → 子进程运行精修 → 解析 .lst/.prf/精修 CIF
    → 汇总各相 weight_fraction。

    Parameters
    ----------
    pattern:
        实验衍射谱。
    phases:
        已鉴定相列表。每相的 ``entry.entry_id`` 必须在 *cif_paths* 中。
    cif_paths:
        ``entry_id -> CIF 文件路径`` 映射，与
        :func:`~xinmatch.core.refine.gsas2_project.build_gsas2_project`
        一致。
    work_dir:
        工作目录。``None`` 时创建临时目录。
    options:
        精修选项（最大迭代次数、是否精修原子/背景/profile 等）。
    driver:
        可注入的驱动函数（测试用）。签名应与
        ``build_gsas2_project(pattern, phases, cif_paths, options,
        work_dir, run=True) -> Gsas2Project`` 一致。``None`` 时使用
        默认的 GSAS-II 驱动。
    instrument_file:
        可选 GSAS-II 仪器参数文件（``.prm``/``.inst``）。``None`` 时
        使用内嵌的通用 Bragg-Brentano Cu Kα 参数（T8.3/#17：实测仪器
        参数可用 :func:`~tools.maud_to_prm` 从 MAUD ``.par`` 提取）。

    Returns
    -------
    RietveldQuantResult
        各相重量分数、R 因子、精修后晶胞等。

    Raises
    ------
    ValueError
        相列表为空或 CIF 映射缺失。
    Gsas2NotAvailableError
        GSAS-II 不可用且 driver 未注入。
    RuntimeError
        精修子进程失败或产物缺失。
    """
    from xinmatch.core.refine.gsas2_project import (
        build_gsas2_project,
    )

    options = options or RefineOptions()
    if not phases:
        raise ValueError("rietveld_quantify: at least one phase is required")

    if work_dir is None:
        work_dir = Path(tempfile.mkdtemp(prefix="xinmatch_rietveld_"))
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    # ---- 运行精修 --------------------------------------------------------
    if driver is not None:
        proj = driver(
            pattern, phases, cif_paths, options, work_dir, run=True
        )
    else:
        proj = build_gsas2_project(
            pattern,
            phases,
            dict(cif_paths),
            options=options,
            work_dir=work_dir,
            project_name="rietveld_quant",
            instrument_file=instrument_file,
            run=True,
        )

    # ---- 定位产物文件 ----------------------------------------------------
    lst_path: str | Path | None = getattr(proj, "lst_path", None)
    prf_path: str | Path | None = getattr(proj, "prf_path", None)
    refined_cifs = getattr(proj, "refined_cifs", [])
    gpx_path = getattr(proj, "gpx_path", None)

    # File-existence checks are safety nets for the default GSAS-II path only.
    # When a custom driver is injected (testing), trust the returned project.
    if driver is None:
        if lst_path is None or not Path(lst_path).is_file():
            raise RuntimeError(
                f"GSAS-II 精修未产出 .lst 文件: {lst_path!r}；"
                f"stdout tail: {getattr(proj, 'stdout_tail', '')!r}"
            )
        if prf_path is None or not Path(prf_path).is_file():
            raise RuntimeError(
                f"GSAS-II 精修未产出 .prf 文件: {prf_path!r}"
            )
    # Belt-and-braces: by construction the default path already raised above;
    # a custom driver is expected to return a project carrying both paths.
    if lst_path is None or prf_path is None:
        raise RuntimeError("精修项目缺少 .lst/.prf 产物路径")

    # ---- 解析精修结果 ----------------------------------------------------
    outcome = parse_refinement(
        lst_path,
        prf_path,
        cifs=list(refined_cifs) if refined_cifs else None,
        gpx=gpx_path,
    )

    # ---- 汇总 weight_fraction --------------------------------------------
    weight_fractions: dict[str, float] = {}
    uncertainties: dict[str, float] = {}

    for rph in outcome.refined_phases:
        ph = rph.phase
        name = ph.entry.mineral_name or ph.entry.entry_id
        wf = ph.weight_fraction
        if wf is not None:
            weight_fractions[name] = float(wf)
            # .lst 中的 sig 值（如果有）
            lst_phase = getattr(outcome.raw, "phases", {}).get(name, {})
            sig = lst_phase.get("weight_fraction_sig")
            uncertainties[name] = float(sig) if sig is not None else 0.0

    # 如果 refined_phases 为空（无 CIF 导出），退而从 .lst 直接汇总
    if not weight_fractions:
        raw_phases = getattr(outcome.raw, "phases", {}) or {}
        for pname, pinfo in raw_phases.items():
            wf = pinfo.get("weight_fraction")
            if wf is not None:
                weight_fractions[pname] = float(wf)
                uncertainties[pname] = 0.0

    if not weight_fractions:
        raise RuntimeError(
            "精修结果中未找到任何 weight fraction；请检查 .lst 日志。"
        )

    return RietveldQuantResult(
        weight_fractions=weight_fractions,
        uncertainties=uncertainties,
        r_factors=outcome.r_factors,
        gof=outcome.gof,
        refined_phases=outcome.refined_phases,
        gpx_path=Path(gpx_path) if gpx_path else None,
        lst_path=Path(lst_path),
        prf_path=Path(prf_path),
        work_dir=work_dir,
        outcome=outcome,
    )
