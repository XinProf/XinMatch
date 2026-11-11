"""用户数据库对话框（``UserDbDialog``）回归测试。

对话框只是 :mod:`xinmatch.core.db.user_db` 的薄门面，所以这里不重复验证
核心逻辑（那是 ``tests/db/test_user_db.py`` 的活），只钉三件 GUI 独有的事：

1. **表格与库同步** —— 行数、列内容、``selected_entry_ids`` 与库内相一一对应；
2. **操作后视图自己刷新** —— ``add_paths`` / ``remove_entry_ids`` 之后表格
   与状态行必须立刻反映新相数，且 ``library_changed`` 信号被发出（主窗口
   靠它刷新"大库"提示）；
3. **失败要看得见** —— 坏 CIF 的路径与原因必须出现在对话框底部的细节行，
   不能只写日志。

按钮路径走 ``run_with_busy``（模态 + 线程），测试一律用同步 API，避免在
离屏环境里起嵌套事件循环。
"""

from __future__ import annotations

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

pytest.importorskip("PySide6")

from xinmatch.core.db import user_db as udb  # noqa: E402
from xinmatch.ui.user_db_dialog import UserDbDialog  # noqa: E402


@pytest.fixture
def user_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return isolate_user_data(tmp_path, monkeypatch)


@pytest.fixture
def three_cifs(tmp_path: Path) -> list[Path]:
    return [
        write_cif(tmp_path, "si.cif", CIF_SI),
        write_cif(tmp_path, "caf2.cif", CIF_CAF2),
        write_cif(tmp_path, "al2o3.cif", CIF_AL2O3),
    ]


@pytest.fixture
def dialog(qapp, user_data) -> UserDbDialog:
    dlg = UserDbDialog()
    yield dlg
    dlg.deleteLater()


def _column_texts(dialog: UserDbDialog, row: int) -> list[str]:
    return [dialog._table.item(row, col).text() for col in range(5)]


# ---------------------------------------------------------------------------
# 1. 表格与库同步
# ---------------------------------------------------------------------------
def test_empty_database_shows_guidance(dialog: UserDbDialog):
    assert dialog._table.rowCount() == 0
    assert dialog.entry_ids() == []
    status = dialog._status_label.text()
    assert "尚未建立用户库" in status
    assert "添加 CIF" in status, "空库必须告诉用户下一步点哪里"


def test_table_mirrors_library(dialog: UserDbDialog, three_cifs):
    result = dialog.add_paths(three_cifs)
    assert result.total == 3

    assert dialog._table.rowCount() == 3
    assert dialog.entry_ids() == sorted(result.added)
    for row, entry_id in enumerate(dialog.entry_ids()):
        cells = _column_texts(dialog, row)
        assert cells[0] == entry_id
        # 峰数是数字且不为零（说明确实从结构算出了峰表）
        assert int(cells[4].replace(",", "")) > 0
    assert "共 3 相" in dialog._status_label.text()


def test_selected_entry_ids_multiselect(dialog: UserDbDialog, three_cifs):
    dialog.add_paths(three_cifs)
    dialog._table.selectRow(0)
    assert dialog.selected_entry_ids() == [dialog.entry_ids()[0]]

    model = dialog._table.selectionModel()
    model.select(
        dialog._table.model().index(2, 0),
        model.SelectionFlag.Select | model.SelectionFlag.Rows,
    )
    assert dialog.selected_entry_ids() == [dialog.entry_ids()[0], dialog.entry_ids()[2]]


def test_no_selection_returns_empty(dialog: UserDbDialog, three_cifs):
    dialog.add_paths(three_cifs)
    dialog._table.clearSelection()
    assert dialog.selected_entry_ids() == []


# ---------------------------------------------------------------------------
# 2. 操作后视图自己刷新
# ---------------------------------------------------------------------------
def test_add_paths_refreshes_and_signals(dialog: UserDbDialog, three_cifs):
    seen: list[int] = []
    dialog.library_changed.connect(lambda: seen.append(dialog._table.rowCount()))

    dialog.add_paths(three_cifs)

    assert seen == [3], "导入后必须发一次 library_changed（主窗口据此刷新）"
    assert dialog.changed() is True


def test_remove_entry_ids_refreshes(dialog: UserDbDialog, three_cifs):
    added = dialog.add_paths(three_cifs)
    victim = dialog.entry_ids()[0]

    result = dialog.remove_entry_ids([victim])

    assert result.removed == (victim,)
    assert dialog._table.rowCount() == 2
    assert victim not in dialog.entry_ids()
    assert "共 2 相" in dialog._status_label.text()
    assert set(dialog.entry_ids()) == set(added.added) - {victim}


def test_rebuild_now_picks_up_edited_source(dialog: UserDbDialog, three_cifs):
    """改源 CIF 内容后点「重建库」——条目数不变（清单是真相源）。"""
    dialog.add_paths(three_cifs)
    before = dialog.entry_ids()

    three_cifs[0].write_text(CIF_SI.replace("5.4310", "5.4500"), encoding="utf-8")
    dialog.rebuild_now()

    assert dialog.entry_ids() == before
    assert dialog._table.rowCount() == 3


def test_remove_all_returns_to_empty_state(dialog: UserDbDialog, three_cifs):
    dialog.add_paths(three_cifs)
    dialog.remove_entry_ids(dialog.entry_ids())

    assert dialog._table.rowCount() == 0
    assert not udb.user_library_path().exists()
    assert "尚未建立用户库" in dialog._status_label.text()


# ---------------------------------------------------------------------------
# 3. 失败要看得见
# ---------------------------------------------------------------------------
def test_broken_cif_visible_in_detail_line(dialog: UserDbDialog, tmp_path: Path):
    good = write_cif(tmp_path, "si.cif", CIF_SI)
    bad = write_cif(tmp_path, "no_cell.cif", CIF_NO_CELL)

    result = dialog.add_paths([good, bad])

    assert result.total == 1
    detail = dialog._detail_label.text()
    assert "未能入库" in detail
    assert "no_cell.cif" in detail, "坏文件路径必须显示给用户"
    assert "——" in detail, "每条失败都要跟上具体原因（不能只列路径）"


def test_detail_line_persists_while_entry_stays_broken(dialog: UserDbDialog, tmp_path: Path):
    """坏条目按设计留在清单里，所以每次重建都会重新被跳过 —— 提示必须常显。

    如果这里"清空"了，用户会以为库是完整的：那恰恰是本模块最该避免的
    静默失败。
    """
    bad = write_cif(tmp_path, "no_cell.cif", CIF_NO_CELL)
    good = write_cif(tmp_path, "si.cif", CIF_SI)
    dialog.add_paths([bad])
    assert "no_cell.cif" in dialog._detail_label.text()

    dialog.add_paths([good])

    assert dialog._table.rowCount() == 1
    assert "no_cell.cif" in dialog._detail_label.text(), (
        "失败的条目还在清单里，提示就不能消失"
    )


def test_detail_line_clears_once_broken_entry_removed(dialog: UserDbDialog, tmp_path: Path):
    bad = write_cif(tmp_path, "no_cell.cif", CIF_NO_CELL)
    good = write_cif(tmp_path, "si.cif", CIF_SI)
    added = dialog.add_paths([good, bad])

    # 只删掉那条坏条目（它没进库，所以只能按清单里的 id 删）
    bad_id = udb.entry_id_for(bad)
    assert bad_id in added.added
    dialog.remove_entry_ids([bad_id])

    assert dialog._table.rowCount() == 1
    assert dialog._detail_label.text().strip() == "", "库干净了，失败提示也该消失"
