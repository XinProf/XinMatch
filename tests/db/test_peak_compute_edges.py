"""峰引擎边界回归测试（v3.0.0 评估新增，Task #15 / LP-180）。

覆盖两类真实缺陷（均可在旧代码上复现）：

1. ``d = wavelength / 2``（2θ = 180°）边界反射：当晶胞轴恰为 0.7703 Å 的整数
   倍（如 COD 96-100-8057 的 c = 7.703 = 10 × 0.7703）时，浮点舍入使
   ``2 * d > wavelength`` 成立，180° 反射被放进峰表；LP 因子在该角度发散
   （raw I 1e16~1e21），归一化 1000 后其它真实峰的相对强度低于
   ``REL_INTENSITY_CUTOFF``，峰表塌缩成唯一一条 d = 0.7703 的假峰。
2. gemmi ``read_small_structure`` 读不到 CIF 晶胞时留下默认占位晶胞
   (1, 1, 1, 90, 90, 90)；旧代码据此算出单条 d = 1.0 Å 假峰。少数 COD CIF
   把 ``_cell_length_a`` 藏在文件末尾的单列 ``loop_`` 里，文本标签仍可恢复。
"""

from __future__ import annotations

import math
from pathlib import Path

import gemmi
import numpy as np
import pytest

from xinmatch.core.db import peak_compute as pc
from xinmatch.core.db.cif_meta import cell_parameters_from_block

WL = pc.DEFAULT_WAVELENGTH
D_BOUNDARY = WL / 2.0

#: 真实 COD 源 CIF 归档（只读）。不存在时相关用例自动跳过。
SRC_COD = Path(r"D:\Project\XRD\sync-COD\inorg_cif\COD")

#: 最小 CIF：a = b = 5.407 Å, c = 7.703 Å = 10 × 0.7703（与 COD 96-100-8057 同晶胞）。
#: ``(0 0 10)`` 的 d 恰为 0.7703000000000001（浮点误差），旧代码会把它放进峰表。
BOUNDARY_CIF = """data_boundary_180
_space_group_name_H-M   'P 1'
_cell_length_a          5.4070
_cell_length_b          5.4070
_cell_length_c          7.7030
_cell_angle_alpha       90.0
_cell_angle_beta        90.0
_cell_angle_gamma       120.0
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
Si1 Si 0.0 0.0 0.0 1.0
O1  O  0.25 0.25 0.25 1.0
"""

#: gemmi 读不出晶胞、但六个参数在文本标签里齐全的 CIF（a 在文件尾部 loop_）。
RECOVERABLE_CIF = """data_recoverable_cell
_space_group_name_H-M   'P 1'
_cell_length_b          4.0000
_cell_length_c          5.0000
_cell_angle_alpha       90.0
_cell_angle_beta        90.0
_cell_angle_gamma       90.0
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
Si1 Si 0.0 0.0 0.0 1.0
O1  O  0.25 0.25 0.25 1.0
loop_
_cell_length_a
4.0000
"""

#: 完全没有任何晶胞标签（源数据本身不可计算）。
NO_CELL_CIF = """data_no_cell
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
Si1 Si 0.0 0.0 0.0 1.0
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _ss(text: str) -> gemmi.SmallStructure:
    return gemmi.make_small_structure_from_block(
        gemmi.cif.read_string(text).sole_block()
    )


# ---------------------------------------------------------------------------
# 1. 180° 边界反射与 LP 发散
# ---------------------------------------------------------------------------
def test_fixture_really_contains_180deg_reflection() -> None:
    """先证明测试夹具确实命中旧缺陷（(0 0 ±10) 因浮点误差通过 naive 判据）。"""
    ss = _ss(BOUNDARY_CIF)
    enum = pc._enumerate_hkl(
        ss.cell,
        dmin=pc.DEFAULT_DMIN,
        dmax=pc.DEFAULT_DMAX,
        max_hkl=pc.DEFAULT_MAX_HKL,
    )
    assert enum is not None
    hkl, d = enum
    naive = (2.0 * d) > WL
    strict = (2.0 * d) > WL * (1.0 + pc._MEASURABLE_REL_EPS)
    leaked = np.nonzero(naive & ~strict)[0]
    assert leaked.size >= 1, "夹具没有边界反射，测试失去意义"
    # 泄露的正是 c 轴 10 级衍射
    leaked_hkl = {tuple(int(v) for v in row) for row in hkl[leaked]}
    assert (0, 0, 10) in leaked_hkl or (0, 0, -10) in leaked_hkl


def test_boundary_reflection_never_enters_pattern() -> None:
    result = pc.compute_pattern_from_text(BOUNDARY_CIF, max_peaks=0)
    assert result is not None
    d, i = result
    assert d.size > 100, "旧代码在这里只剩 1 条假峰"
    # 任何进入峰表的反射都必须严格小于 180°
    assert bool((2.0 * d > WL * (1.0 + pc._MEASURABLE_REL_EPS)).all())
    # 不得出现 d = lambda/2 的边界线
    assert not np.any(np.isclose(d, D_BOUNDARY, rtol=0.0, atol=1e-9))
    # 全部落在可测 d 区间
    assert float(d.min()) >= pc.DEFAULT_DMIN
    assert float(d.max()) <= pc.DEFAULT_DMAX + 1e-9
    # 归一化仍然成立（真实峰被保留，而不是只剩边界假峰）
    assert float(i.max()) == pytest.approx(pc.INTENSITY_SCALE)


def test_lorentz_polarization_finite_for_any_angle() -> None:
    angles = np.array([0.0, 1e-6, 30.0, 90.0, 179.9, 179.9999, 180.0])
    lp = pc._lorentz_polarization(angles)
    assert bool(np.isfinite(lp).all())
    assert bool((lp > 0.0).all())


def test_lorentz_polarization_normal_angles_bit_identical() -> None:
    """LP 的防御式 floor 不得改变正常角度的数值（逐位相同）。"""
    normal = np.array([10.0, 30.0, 60.0, 90.0, 120.0, 150.0])
    theta = np.radians(normal) / 2.0
    expected = (1.0 + np.cos(2.0 * theta) ** 2) / (
        np.sin(theta) * np.sin(theta) * np.cos(theta)
    )
    np.testing.assert_array_equal(pc._lorentz_polarization(normal), expected)


# ---------------------------------------------------------------------------
# 2. gemmi 占位晶胞（d = 1.0 假峰）
# ---------------------------------------------------------------------------
def test_gemmi_leaves_placeholder_for_recoverable_cif() -> None:
    """夹具前提：gemmi 确实读不出这个 CIF 的晶胞。"""
    assert not pc._cell_is_usable(_ss(RECOVERABLE_CIF).cell)


def test_cell_recovered_from_text_tags(tmp_path: Path) -> None:
    text = RECOVERABLE_CIF
    for result in (
        pc.compute_pattern_from_text(text),
        pc.compute_pattern(_write(tmp_path, "recoverable.cif", text)),
    ):
        assert result is not None, "文本晶胞可用时不得判为不可计算"
        d, i = result
        assert d.size > 1
        assert float(d.max()) == pytest.approx(5.0)  # c 轴
        assert pc.DEFAULT_DMIN <= float(d.min()) <= float(d.max())


def test_no_cell_cif_is_uncomputable(tmp_path: Path) -> None:
    assert pc.compute_pattern_from_text(NO_CELL_CIF) is None
    path = _write(tmp_path, "no_cell.cif", NO_CELL_CIF)
    assert pc.compute_pattern(path) is None
    # 直接拿到占位晶胞的结构也不能算（否则就是 d=1 A 假峰）
    assert pc.compute_pattern_from_structure(_ss(NO_CELL_CIF)) is None


def test_cell_parameters_from_block_parses_uncertainty() -> None:
    text = BOUNDARY_CIF.replace(
        "_cell_length_a          5.4070", "_cell_length_a          5.4070(10)"
    ).replace("_cell_length_c          7.7030", "_cell_length_c          7.7030(5)")
    block = gemmi.cif.read_string(text).sole_block()
    assert cell_parameters_from_block(block) == (
        5.4070,
        5.4070,
        7.7030,
        90.0,
        90.0,
        120.0,
    )
    # 缺一个参数 -> None（不会用默认值补）
    partial = gemmi.cif.read_string(
        "data_x\n_cell_length_b 4\n_cell_length_c 5\n"
        "_cell_angle_alpha 90\n_cell_angle_beta 90\n_cell_angle_gamma 90\n"
    ).sole_block()
    assert cell_parameters_from_block(partial) is None
    assert cell_parameters_from_block(None) is None


# ---------------------------------------------------------------------------
# 3. 真实 COD 源 CIF 回归（归档不在本机时跳过）
# ---------------------------------------------------------------------------
def _cif_path(native_id: int) -> Path:
    s = str(native_id).zfill(7)
    return SRC_COD / s[0] / s[1:3] / s[3:5] / f"{s}.cif"


def _require_cif(native_id: int) -> Path:
    path = _cif_path(native_id)
    if not path.is_file():
        pytest.skip(f"COD 源 CIF 归档不在本机: {path}")
    return path


@pytest.mark.parametrize(
    ("entry_id", "native_id", "expected_peaks"),
    [
        ("96-100-8057", 1008057, 122),
        ("96-151-1248", 1511248, 228),
        ("96-153-3251", 1533251, 152),
        ("96-154-5882", 1545882, 413),
        ("96-210-1175", 2101175, 79),
    ],
)
def test_real_180deg_phases_restore_full_pattern(
    entry_id: str, native_id: int, expected_peaks: int
) -> None:
    """这些相旧代码只剩 1 条 d=0.7703 假峰；修复后应恢复全部真实峰。"""
    path = _require_cif(native_id)
    result = pc.compute_pattern(path, max_peaks=0)
    assert result is not None, entry_id
    d, i = result
    assert d.size == expected_peaks, entry_id
    assert bool((2.0 * d > WL * (1.0 + pc._MEASURABLE_REL_EPS)).all())
    assert not np.any(np.isclose(d, D_BOUNDARY, rtol=0.0, atol=1e-9))
    assert float(i.max()) == pytest.approx(pc.INTENSITY_SCALE)


@pytest.mark.parametrize(
    ("entry_id", "native_id", "expected_peaks", "expected_dmax"),
    [
        ("96-156-3735", 1563735, 150, 19.739),  # c 轴，150 = max_peaks 截断
        ("96-156-3736", 1563736, 114, 10.1704),
        ("96-210-4629", 2104629, None, None),  # 源数据无晶胞 -> 不可计算
    ],
)
def test_real_placeholder_cell_phases(
    entry_id: str, native_id: int, expected_peaks: int | None, expected_dmax: float | None
) -> None:
    path = _require_cif(native_id)
    result = pc.compute_pattern(path, max_peaks=pc.DEFAULT_MAX_PEAKS)
    if expected_peaks is None:
        assert result is None, f"{entry_id}: 无晶胞的相必须判为不可计算"
        return
    assert result is not None, entry_id
    d, _i = result
    assert d.size == expected_peaks, entry_id
    assert float(d.max()) == pytest.approx(expected_dmax, abs=1e-3), entry_id
    # 绝不能出现 d = 1.0 的占位晶胞假峰
    assert not np.any(np.isclose(d, 1.0, rtol=0.0, atol=1e-9)), entry_id
    assert math.isfinite(float(d.min()))


def test_structure_factor_block_size_is_bit_identical(tmp_path: Path) -> None:
    """自适应结构因子分块只改变处理顺序，不改变任何一个比特。

    The block size only decides which reflections are evaluated together; each
    row's sum is computed in the same order, so ``|F|**2`` must be identical for
    every block size.  The production default (``chunk=None``) sizes the block
    from the atom count to keep the per-block temporaries cache-resident; this
    test pins the equivalence and would catch an accidental reduction-order
    change from a future "optimisation".
    """
    path = tmp_path / "boundary.cif"
    path.write_text(BOUNDARY_CIF, encoding="utf-8")
    ss = gemmi.read_small_structure(str(path))
    expanded = pc._expand_sites(ss)
    recip = pc._reciprocal_matrix(ss.cell)
    assert expanded is not None and recip is not None
    frac, occ, b_iso, symbols = expanded
    enum = pc._enumerate_hkl(
        ss.cell, dmin=pc.DEFAULT_DMIN, dmax=pc.DEFAULT_DMAX, max_hkl=pc.DEFAULT_MAX_HKL
    )
    assert enum is not None
    hkl, _d = enum

    reference = pc._structure_factors(hkl, frac, occ, b_iso, symbols, recip, chunk=8192)
    for chunk in (256, 512, 1024, 2048, 4096):
        got = pc._structure_factors(hkl, frac, occ, b_iso, symbols, recip, chunk=chunk)
        assert np.array_equal(reference, got), f"chunk={chunk} changed the result"
    assert np.array_equal(
        reference, pc._structure_factors(hkl, frac, occ, b_iso, symbols, recip)
    )
