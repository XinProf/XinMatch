"""用户数据库（UDB）测试的共享素材。

用户库的输入是**真实 CIF 文件**（``parse_meta`` / ``compute_pattern`` 都走
gemmi），所以测试必须自己产出可解析的 CIF。这里放四份内联极简 CIF + 环境
隔离助手，供 ``tests/db/test_user_db.py``（核心层）与
``tests/ui/test_user_db_dialog.py``（对话框）共用 —— 两边各抄一份的话，
"CIF 是否可解析"这个前提会偷偷漂移。

四份 CIF 的用途：

* ``CIF_SI`` / ``CIF_CAF2`` / ``CIF_AL2O3`` —— 三份晶胞互不相同的可解析相，
  用来验证"3 相入库、可被 reader 读回"；
* ``CIF_NO_CELL`` —— 没有任何晶胞标签，``parse_meta`` 必然返回 ``None``，
  用来验证"坏文件只进 skipped、不拖垮整次导入"。
"""

from __future__ import annotations

from pathlib import Path

import pytest

__all__ = [
    "CIF_AL2O3",
    "CIF_CAF2",
    "CIF_NO_CELL",
    "CIF_SI",
    "isolate_user_data",
    "write_cif",
]

CIF_SI = """data_udb_si
_space_group_name_H-M   'P 1'
_cell_length_a          5.4310
_cell_length_b          5.4310
_cell_length_c          5.4310
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
"""

CIF_CAF2 = """data_udb_caf2
_space_group_name_H-M   'P 1'
_cell_length_a          5.4630
_cell_length_b          5.4630
_cell_length_c          5.4630
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
Ca1 Ca 0.0 0.0 0.0 1.0
F1  F  0.25 0.25 0.25 1.0
"""

CIF_AL2O3 = """data_udb_al2o3
_space_group_name_H-M   'P 1'
_cell_length_a          4.7590
_cell_length_b          4.7590
_cell_length_c          12.9910
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
Al1 Al 0.0 0.0 0.0 1.0
O1  O  0.3 0.0 0.25 1.0
"""

CIF_NO_CELL = """data_udb_no_cell
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
Si1 Si 0.0 0.0 0.0 1.0
"""


def write_cif(directory: Path, name: str, text: str) -> Path:
    """把 *text* 写到 ``directory/name`` 并返回路径（UTF-8）。"""
    path = Path(directory) / name
    path.write_text(text, encoding="utf-8")
    return path


def isolate_user_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """把用户库、源清单、库注册表全部隔离到 *tmp_path*。

    ``multi_db`` 的路径函数是**调用时**读环境变量（不是模块导入时），所以
    ``setenv`` 立即生效、不需要 reload。内置库候选目录也一并指空 —— 否则
    开发机上真实存在的 COD 库会让"注册表里只有用户库"这类断言假阳性。
    """
    from xinmatch.core.db import multi_db

    data = Path(tmp_path) / "userdata"
    data.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XINMATCH_USER_DATA", str(data))
    monkeypatch.delenv("XINMATCH_LIBRARIES_JSON", raising=False)
    empty = Path(tmp_path) / "no_libs"
    empty.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XINMATCH_XINDB_DIR", str(empty))
    monkeypatch.setattr(multi_db, "_data_dir", lambda: Path(tmp_path) / "no_data")
    monkeypatch.setattr(multi_db, "project_root", lambda: Path(tmp_path) / "no_repo")
    return data
