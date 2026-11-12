"""回归：合成谱生成器的卡片库路径必须跟仓库走。

背景（2026-11-12）：``tools/generate_synthetic_patterns.py`` 的 ``CARD_DB`` 曾把
迁移前的绝对路径 ``D:\\Project\\XRD\\XinMatch\\data\\cod_inorganics.db`` 写死，
环境迁移后生成第一步就 ``sqlite3.OperationalError: unable to open database file``。
这类「本机绝对路径漂移」在本项目反复出现，所以用测试钉住两件事：

* 默认路径必须是 ``<repo>/data/cod_inorganics.db``（不随机器变）；
* 库缺失时三个取卡函数返回 ``None``（hkl/晶胞缺失只影响织构几何权重，不崩流程）。
"""

from __future__ import annotations

from pathlib import Path

import tools.generate_synthetic_patterns as gen

REPO = Path(__file__).resolve().parents[1]


def test_card_db_is_repo_relative() -> None:
    assert gen.CARD_DB == REPO / "data" / "cod_inorganics.db"


def test_card_peaks_returns_none_when_library_missing(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(gen, "CARD_DB", tmp_path / "missing.db")
    assert gen._card_peaks(2100858) is None
    assert gen._cell_for(2100858) is None


def test_card_peaks_by_formula_returns_none_when_library_missing(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(gen, "CARD_DB", tmp_path / "missing.db")
    assert gen._card_peaks_by_formula(2100858) is None
