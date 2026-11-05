""".xinm 物相分析状态导出（联合计划 X-1 / X-4）。

不依赖真实 COD 档案：用 tmp 目录伪造 ``{d}/{dd}/{dd}/{id:07d}.cif`` 布局，
经 ``cod_root`` 参数注入。
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np
import pytest

from xinmatch.core.io.xinm import (
    XINM_FORMAT,
    XINM_VERSION,
    XinmExportError,
    export_xinm,
    pattern_to_csv_rows,
)
from xinmatch.core.model.entry import CellParams, Entry
from xinmatch.core.model.pattern import Pattern
from xinmatch.core.model.peak import Peak
from xinmatch.core.model.phase import Phase
from xinmatch.core.model.project import Project


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
def _make_pattern(n: int = 2000) -> Pattern:
    tt = np.linspace(5.0, 90.0, n)
    intensity = 100.0 + 50.0 * np.sin(tt / 3.0)
    return Pattern(two_theta=tt, intensity=intensity,
                   wavelength=1.5406, step=0.0425,
                   metadata={"anode": "Cu", "sample": "demo",
                             "source_path": "D:/data/demo.xy"})


def _make_entry(entry_id: str, name: str = "anatase") -> Entry:
    return Entry(
        entry_id=entry_id,
        formula="O2 Ti",
        d_spacings=np.array([3.52, 2.38, 1.89]),
        intensities=np.array([1000.0, 500.0, 200.0]),
        mineral_name=name,
        cell=CellParams(a=3.785, b=3.785, c=9.5196,
                        alpha=90.0, beta=90.0, gamma=90.0),
        space_group="I41/amd",
    )


@pytest.fixture()
def cod_root(tmp_path: Path) -> Path:
    """伪造 COD 档案：96-400-1849 → 4001849 → 4/00/18/4001849.cif。"""
    d = tmp_path / "4" / "00" / "18"
    d.mkdir(parents=True)
    (d / "4001849.cif").write_text(
        "data_4001849\n_cell_length_a 3.785\n", encoding="utf-8")
    return tmp_path


def _make_project(cod_root: Path, with_cif: bool = True) -> Project:
    e1 = _make_entry("96-400-1849")
    e2 = _make_entry("96-999-9999", name="ghost")     # 档案里没有
    e3 = _make_entry("weird-id", name="weird")        # 非 ref_id 形态
    sel = [Phase(entry=e1, scale_factor=1.25), Phase(entry=e2, scale_factor=0.5)]
    if not with_cif:
        sel = [Phase(entry=e3, scale_factor=1.0)]
    return Project(
        patterns=[_make_pattern()],
        peaks=[Peak(two_theta=25.3, intensity=100.0, d=3.52,
                    hkl=(1, 0, 1))],
        candidates=[(e1, 0.87), (e2, 0.61), (e3, 0.30)],
        selected_phases=sel,
    )


# ---------------------------------------------------------------------------
# 用例
# ---------------------------------------------------------------------------
def test_export_roundtrip_manifest_and_csv(cod_root: Path, tmp_path: Path) -> None:
    out = tmp_path / "analysis.xinm"
    report = export_xinm(_make_project(cod_root), out, cod_root=cod_root,
                         app_version="3.4.0-test")
    assert out.is_file()
    assert report.n_points == 2000
    assert report.n_structural == 1
    assert report.summary.startswith("已导出 2 相（1 个含结构 CIF）")

    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
        assert {"manifest.json", "pattern/pattern.csv",
                "cifs/4001849.cif"} <= names
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        csv_text = zf.read("pattern/pattern.csv").decode("utf-8")

    assert manifest["format"] == XINM_FORMAT
    assert manifest["version"] == XINM_VERSION
    assert manifest["app"]["version"] == "3.4.0-test"
    pat = manifest["pattern"]
    assert pat["wavelength"] == pytest.approx(1.5406)
    assert pat["anode"] == "Cu"
    assert pat["source_path"] == "D:/data/demo.xy"
    # phases：cod 命中 / cod 未命中
    by_name = {p["name"]: p for p in manifest["phases"]}
    assert by_name["anatase"]["structural"] is True
    assert by_name["anatase"]["cif_file"] == "cifs/4001849.cif"
    assert by_name["anatase"]["space_group"] == "I41/amd"
    assert by_name["ghost"]["structural"] is False
    assert by_name["ghost"]["cif_file"] is None
    assert "COD 归档未命中" in by_name["ghost"]["reason"]
    # peaks 随包
    assert manifest["peaks"] and manifest["peaks"][0]["two_theta"] == 25.3
    # candidates 摘要默认带
    assert len(manifest["candidates_summary"]) == 3

    # CSV 往返（%.10g，相对误差 ≤ 1e-9）
    lines = csv_text.strip().splitlines()
    assert lines[0] == "two_theta,intensity"
    assert len(lines) == 2001
    tt = [float(x.split(",")[0]) for x in lines[1:]]
    ii = [float(x.split(",")[1]) for x in lines[1:]]
    src = _make_pattern(2000)
    assert tt == pytest.approx(src.two_theta.tolist(), rel=1e-9)
    assert ii == pytest.approx(src.intensity.tolist(), rel=1e-9)


def test_export_no_candidates_skips_summary(cod_root: Path, tmp_path: Path) -> None:
    out = tmp_path / "a.xinm"
    export_xinm(_make_project(cod_root), out, include_candidates=False,
                cod_root=cod_root)
    with zipfile.ZipFile(out) as zf:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
    assert manifest["candidates_summary"] == []


def test_export_unresolved_id_only(cod_root: Path, tmp_path: Path) -> None:
    out = tmp_path / "b.xinm"
    report = export_xinm(_make_project(cod_root, with_cif=False), out,
                         cod_root=cod_root)
    assert report.phases[0].source == "unresolved"
    assert report.n_structural == 0
    with zipfile.ZipFile(out) as zf:
        assert not any(n.startswith("cifs/") for n in zf.namelist())


def test_export_pdf2_entry_is_pdf2_source(cod_root: Path, tmp_path: Path) -> None:
    """PDF-2 卡片的 ``source`` 必须是 ``pdf2``，不能是 ``unresolved``。

    两者对下游含义不同：``pdf2`` 是「本来就没有结构」，``unresolved`` 是
    「本该有结构却没回取到」。混用会让精修端的缺结构原因写错。
    """
    e = _make_entry("PDF2-010837", name="calcite")
    project = Project(
        patterns=[_make_pattern()],
        peaks=[Peak(two_theta=29.4, intensity=100.0, d=3.04, hkl=(1, 0, 4))],
        candidates=[(e, 0.91)],
        selected_phases=[Phase(entry=e, scale_factor=1.0)],
    )
    out = tmp_path / "pdf2.xinm"
    report = export_xinm(project, out, cod_root=cod_root)
    assert report.phases[0].source == "pdf2"
    assert report.phases[0].structural is False
    assert report.n_structural == 0
    with zipfile.ZipFile(out) as zf:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
    assert manifest["candidates_summary"][0]["source"] == "pdf2"


def test_export_without_pattern_raises(cod_root: Path, tmp_path: Path) -> None:
    with pytest.raises(XinmExportError):
        export_xinm(Project(), tmp_path / "c.xinm", cod_root=cod_root)


def test_pattern_to_csv_rows_matches_pattern(cod_root: Path) -> None:
    tt, ii, n = pattern_to_csv_rows(_make_project(cod_root))
    assert n == 2000
    assert len(tt) == len(ii) == 2000
    assert tt[0] == "5"
    assert tt[-1] == "90"


def test_real_archive_anatase_resolvable() -> None:
    """联调锚点：真实档案（如存在）应能解析 anatase 96-900-8220 → 9008220。"""
    from xinmatch.core.refine.cif_store import resolve_entry_cif
    cif = resolve_entry_cif("96-900-8220")
    if cif is None:  # 档案未挂载的机器上跳过
        pytest.skip("本地 COD 档案不可用")
    assert cif.name == "9008220.cif"
    assert cif.is_file()
