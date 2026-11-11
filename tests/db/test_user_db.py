"""用户数据库（UDB）回归测试 —— v3 原生实现。

背景：旧实现产出 v2 SQLite（``entries`` + ``peaks`` 行表），v3.0.0 删掉 v2
读取器之后那种文件**没有任何检索路径能读**。现在 ``user_db`` 直接产出
``.xinDB``，于是本文件的判据也换了口径 —— 不再问"表建了没有"，而是问
"用户导入的 CIF 到底能不能被 reader 读回来"。

钉住七条：

1. **落库可检索** —— 导 3 份 CIF，``XinDBReader`` 必须读回 3 相；
2. **幂等** —— 同一份 CIF 重复导入不产生第二条清单记录，库也不长大；
3. **删条目靠整库重建** —— 删 1 条后库里剩 2 相，删空后库文件消失、注册表注销；
4. **坏 CIF 只进 skipped** —— 一份解析不出晶胞的 CIF 不能拖垮整次导入；
5. **路径错误说人话** —— 目录 / 不存在的文件各给一条中文原因；
6. **清单损坏按空处理** —— 手改坏的 JSON 不能让用户库永久罢工；
7. **峰表是 d 值（Å）不是 2θ** —— ``fetch_peaks`` 的坑，用布拉格换算钉住。

CIF 素材与环境保护放在 :mod:`tests.user_db_support`，与对话框测试共用。
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from tests.user_db_support import (
    CIF_AL2O3,
    CIF_CAF2,
    CIF_NO_CELL,
    CIF_SI,
    isolate_user_data,
    write_cif,
)
from xinmatch.core.db import multi_db
from xinmatch.core.db import user_db as udb
from xinmatch.core.db.reader_v3 import XinDBReader

#: 铜靶 Kα1 波长（与 ``peak_compute.DEFAULT_WAVELENGTH`` 同值，此处独立写死，
#: 以便"用 d 值反算 2θ"的断言不跟着被测代码一起漂）。
CU_KA1 = 1.54056


@pytest.fixture
def user_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """把用户库、源清单、注册表全部隔离到 ``tmp_path``。"""
    return isolate_user_data(tmp_path, monkeypatch)


@pytest.fixture
def three_cifs(tmp_path: Path) -> list[Path]:
    """三份晶胞互不相同的可解析 CIF。"""
    return [
        write_cif(tmp_path, "si.cif", CIF_SI),
        write_cif(tmp_path, "caf2.cif", CIF_CAF2),
        write_cif(tmp_path, "al2o3.cif", CIF_AL2O3),
    ]


# ---------------------------------------------------------------------------
# 1. 落库可检索
# ---------------------------------------------------------------------------
def test_add_cif_files_builds_searchable_library(user_data, three_cifs):
    """导 3 份 CIF → 库文件存在、reader 能读回 3 相、每相都有峰。"""
    result = udb.add_cif_files(three_cifs)

    assert result.total == 3, f"预期 3 相，实际 {result.total}；skipped={result.skipped}"
    assert len(result.added) == 3
    assert result.skipped == ()
    assert result.library_path.is_file()
    assert result.library_id is not None

    reader = XinDBReader(result.library_path)
    try:
        assert reader.entry_count() == 3
        ids = sorted(result.added)
        peaks = reader.fetch_peaks(ids)
        assert len(peaks) == 3
        for entry_id, (d, inten) in peaks.items():
            assert len(d) == len(inten) > 0, f"{entry_id} 没有峰"
    finally:
        reader.close()


def test_list_user_entries_reflects_library(user_data, three_cifs):
    result = udb.add_cif_files(three_cifs)
    entries = udb.list_user_entries()

    assert len(entries) == 3
    assert udb.user_entry_count() == 3
    assert {e.entry_id for e in entries} == set(result.added)
    assert all(e.n_peaks > 0 for e in entries)
    # 按 entry_id 排序（UI 列表的稳定性依赖这一点）
    assert [e.entry_id for e in entries] == sorted(e.entry_id for e in entries)


def test_library_is_registered_in_registry(user_data, three_cifs):
    result = udb.add_cif_files(three_cifs)
    ids = [lib.id for lib in multi_db.load_external_libraries()]
    assert ids == [result.library_id]
    # 重复挂载幂等：id 不变、不产生第二行
    assert udb.ensure_registered() == result.library_id
    assert [lib.id for lib in multi_db.load_external_libraries()] == [result.library_id]


# ---------------------------------------------------------------------------
# 2. 幂等
# ---------------------------------------------------------------------------
def test_duplicate_import_is_idempotent(user_data, three_cifs):
    first = udb.add_cif_files(three_cifs)
    assert first.total == 3

    second = udb.add_cif_files(three_cifs)
    assert second.total == 3, "重复导入不应让库变 6 相"
    assert udb.user_entry_count() == 3
    assert set(second.added) == set(first.added)

    manifest = json.loads(udb.manifest_path().read_text(encoding="utf-8"))
    assert len(manifest["entries"]) == 3


def test_entry_id_is_path_derived_and_stable(tmp_path: Path):
    path = write_cif(tmp_path, "si.cif", CIF_SI)
    assert udb.entry_id_for(path) == udb.entry_id_for(path)
    assert udb.entry_id_for(path).startswith(udb.ENTRY_ID_PREFIX)
    # 另一份同内容不同路径的文件算不同条目（改名 = 另一份数据，有意为之）
    other = write_cif(tmp_path, "si_copy.cif", CIF_SI)
    assert udb.entry_id_for(path) != udb.entry_id_for(other)


# ---------------------------------------------------------------------------
# 3. 删条目
# ---------------------------------------------------------------------------
def test_remove_entry_rebuilds_library(user_data, three_cifs):
    added = udb.add_cif_files(three_cifs)
    victim = added.added[0]

    result = udb.remove_entries([victim])

    assert result.removed == (victim,)
    assert result.total == 2
    assert victim not in {e.entry_id for e in udb.list_user_entries()}
    reader = XinDBReader(result.library_path)
    try:
        assert reader.entry_count() == 2
    finally:
        reader.close()


def test_remove_missing_entry_is_noop(user_data, three_cifs):
    udb.add_cif_files(three_cifs)
    result = udb.remove_entries(["UDB-DOES-NOT-EXIST"])
    assert result.removed == ()
    assert result.total == 3


def test_remove_last_entry_drops_library_and_registry(user_data, three_cifs):
    added = udb.add_cif_files(three_cifs)
    library = added.library_path

    result = udb.remove_entries(list(added.added))

    assert result.removed and len(result.removed) == 3
    assert result.total == 0
    assert result.library_id is None
    assert not library.exists(), "空库不该留在磁盘上"
    assert multi_db.load_external_libraries() == []
    assert udb.list_user_entries() == []


# ---------------------------------------------------------------------------
# 4. 坏 CIF 只进 skipped
# ---------------------------------------------------------------------------
def test_broken_cif_is_skipped_not_fatal(user_data, tmp_path: Path):
    good = write_cif(tmp_path, "si.cif", CIF_SI)
    bad = write_cif(tmp_path, "no_cell.cif", CIF_NO_CELL)

    result = udb.add_cif_files([good, bad])

    assert result.total == 1, "好 CIF 必须照常落库"
    assert len(result.skipped) == 1
    skipped_path, reason = result.skipped[0]
    assert Path(skipped_path) == bad.resolve()
    assert reason, "跳过原因不能是空串"
    # 失败条目仍留在清单里：修好 CIF 下次重建即可，不必重新导入
    assert len(json.loads(udb.manifest_path().read_text(encoding="utf-8"))["entries"]) == 2


def test_all_cifs_broken_leaves_no_library(user_data, tmp_path: Path):
    bad = write_cif(tmp_path, "no_cell.cif", CIF_NO_CELL)
    result = udb.add_cif_files([bad])

    assert result.total == 0
    assert result.library_id is None
    assert not result.library_path.exists()
    assert udb.list_user_entries() == []


# ---------------------------------------------------------------------------
# 5. 路径错误
# ---------------------------------------------------------------------------
def test_directory_and_missing_path_rejected(user_data, tmp_path: Path):
    missing = tmp_path / "nope.cif"
    result = udb.add_cif_files([tmp_path, missing])

    assert result.total == 0
    reasons = dict(result.skipped)
    assert "目录" in reasons[str(tmp_path)]
    assert "不存在" in reasons[str(missing)]


# ---------------------------------------------------------------------------
# 6. 清单损坏
# ---------------------------------------------------------------------------
def test_corrupt_manifest_is_treated_as_empty(user_data, three_cifs):
    udb.manifest_path().parent.mkdir(parents=True, exist_ok=True)
    udb.manifest_path().write_text("{ this is not json", encoding="utf-8")

    assert udb.list_user_entries() == []
    # 坏清单不能让后续导入永久失败
    result = udb.add_cif_files(three_cifs)
    assert result.total == 3


def test_manifest_missing_on_first_run(user_data):
    assert not udb.manifest_path().exists()
    assert udb.list_user_entries() == []
    assert udb.rebuild().total == 0


# ---------------------------------------------------------------------------
# 7. 峰表是 d 值（Å），不是 2θ
# ---------------------------------------------------------------------------
def test_fetch_peaks_returns_d_spacings_not_two_theta(user_data, three_cifs):
    """``fetch_peaks`` 返回的是 d 值。按 2θ 用会得到全错结果，这里钉死。

    反算公式 ``2θ = 2·asin(λ / 2d)``：若真值落在合理衍射角范围内，说明峰表
    确实是 d，而不是被当成角度塞进去的数。
    """
    added = udb.add_cif_files(three_cifs)
    reader = XinDBReader(added.library_path)
    try:
        peaks = reader.fetch_peaks([added.added[0]])
    finally:
        reader.close()

    d_values, intensities = next(iter(peaks.values()))
    two_theta = [
        2.0 * math.degrees(math.asin(CU_KA1 / (2.0 * d))) for d in d_values if d > CU_KA1 / 2.0
    ]
    assert two_theta, "d 值全部小于 λ/2，峰表口径不对"
    assert all(0.0 < t < 180.0 for t in two_theta)
    # 最强线应落在常规实验室衍射角窗口内（Cu Kα 极少出现 5° 以下或 170° 以上）
    strongest = int(max(range(len(intensities)), key=lambda k: intensities[k]))
    best_two_theta = 2.0 * math.degrees(math.asin(CU_KA1 / (2.0 * d_values[strongest])))
    assert 5.0 < best_two_theta < 170.0, f"最强线 2θ={best_two_theta:.2f}° 不合常理"
