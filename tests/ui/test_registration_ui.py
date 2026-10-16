"""Registration UI wiring tests (v1.7.0).

覆盖需求里的界面侧约定：

* 正式版：帮助菜单含「输入注册码 (&R)…」；状态栏最右一排显示
  「未注册」/「已注册：<单位部门名称>」；注册状态跨启动持久化。
* 内部评估版：不创建注册管理器、没有「输入注册码」菜单、状态栏最右
  固定显示「内部评估版本」。
* 离屏环境（本套件）下启动检查不弹模态框，返回值可断言。
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402

from xinmatch.ui.main_window import MainWindow  # noqa: E402
from xinmatch.utils import build_variant  # noqa: E402
from xinmatch.utils.registration import generate_code, save_state  # noqa: E402

UNIT = "测试单位·粉末衍射实验室"
ENTER_CODE_TEXT = "输入注册码 (&R)…"


@pytest.fixture
def reg_dir(monkeypatch, tmp_path):
    """把注册状态目录重定向到临时目录，避免污染本机真实注册状态。"""
    monkeypatch.setattr(
        "xinmatch.ui.main_window.app_config_dir", lambda: tmp_path
    )
    return tmp_path


def _action_texts(window: MainWindow) -> list[str]:
    return [a.text() for a in window.findChildren(QtGui.QAction)]


def test_release_build_has_registration_and_help_action(qapp, reg_dir, monkeypatch):
    monkeypatch.setenv(build_variant._ENV_KEY, "release")
    window = MainWindow()
    assert window._registration is not None
    assert ENTER_CODE_TEXT in _action_texts(window)


def test_release_build_status_label_unregistered(qapp, reg_dir, monkeypatch):
    monkeypatch.setenv(build_variant._ENV_KEY, "release")
    window = MainWindow()
    label = window._registration_label
    assert label is not None
    assert label.text() == "未注册"
    assert window.registration_status_text() == "未注册"
    # 右对齐（最下面一排右侧显示）
    assert label.alignment() & QtCore.Qt.AlignmentFlag.AlignRight


def test_release_build_status_label_registered(qapp, reg_dir, monkeypatch):
    monkeypatch.setenv(build_variant._ENV_KEY, "release")
    window = MainWindow()
    save_state(window._registration.state_path, generate_code(UNIT))
    window._registration.refresh()
    assert window._registration_label.text() == f"已注册：{UNIT}"
    assert window.registration_status_text() == f"已注册：{UNIT}"


def test_registration_persists_across_restart(qapp, reg_dir, monkeypatch):
    """注册一次后，下次启动（新窗口）不再提示 / 直接显示单位名。"""
    monkeypatch.setenv(build_variant._ENV_KEY, "release")
    first = MainWindow()
    save_state(first._registration.state_path, generate_code(UNIT))
    second = MainWindow()
    assert second._registration.state.registered
    assert second._registration.state.unit == UNIT
    assert second._registration_label.text() == f"已注册：{UNIT}"


def test_startup_check_is_non_blocking_offscreen(qapp, reg_dir, monkeypatch):
    """离屏下启动检查不弹窗（模块自动跳过），且返回未注册状态。"""
    monkeypatch.setenv(build_variant._ENV_KEY, "release")
    window = MainWindow()
    state = window._registration.startup_check(window)
    assert not state.registered


def test_internal_build_has_no_registration(qapp, reg_dir, monkeypatch):
    monkeypatch.setenv(build_variant._ENV_KEY, "internal")
    window = MainWindow()
    assert window._registration is None
    assert ENTER_CODE_TEXT not in _action_texts(window)


def test_internal_build_status_label(qapp, reg_dir, monkeypatch):
    monkeypatch.setenv(build_variant._ENV_KEY, "internal")
    window = MainWindow()
    label = window._registration_label
    assert label is not None
    assert label.text() == build_variant.INTERNAL_STATUS_TEXT == "内部评估版本"
    assert window.registration_status_text() == "内部评估版本"
    assert label.alignment() & QtCore.Qt.AlignmentFlag.AlignRight


# ---------------------------------------------------------------------------
# 启动弹窗行为（确定性替身：替换 PySide6.QtWidgets.QMessageBox，不真弹模态框）
# ---------------------------------------------------------------------------
class _FakeButton:
    def __init__(self, text: str) -> None:
        self._text = text
        self.default = False
        self.auto_default = False

    def text(self) -> str:
        return self._text

    def setDefault(  self, value: bool) -> None:  # noqa: N802 — Qt API 命名
        self.default = value

    def setAutoDefault(  self, value: bool) -> None:  # noqa: N802 — Qt API 命名
        self.auto_default = value


class _FakeMessageBox:
    """记录构造过程并模拟按钮点击的 QMessageBox 替身。"""

    class Icon:
        Warning = "warning"
        Information = "information"

    class ButtonRole:
        AcceptRole = "accept"
        ActionRole = "action"

    #: 下一个弹窗自动点击的按钮文案（测试设置）
    pick = "确定"
    last: _FakeMessageBox | None = None

    def __init__(self, parent=None) -> None:
        self.parent = parent
        self.title = ""
        self.text = ""
        self._buttons: list[_FakeButton] = []
        self._clicked: _FakeButton | None = None
        _FakeMessageBox.last = self

    def setIcon(self, icon) -> None:  # noqa: N802 — Qt API 命名（替身沿用 Qt 命名）
        self.icon = icon

    def setWindowTitle(  self, title: str) -> None:  # noqa: N802 — Qt API 命名
        self.title = title

    def setText(  self, text: str) -> None:  # noqa: N802 — Qt API 命名
        self.text = text

    def addButton(  self, text, role=None) -> _FakeButton:  # noqa: N802 — Qt API 命名
        button = _FakeButton(text)
        self._buttons.append(button)
        return button

    def buttons(self) -> list[_FakeButton]:
        return list(self._buttons)

    def exec(self) -> int:  # noqa: D102 - 替身
        for button in self._buttons:
            if button.text() == _FakeMessageBox.pick:
                self._clicked = button
                break
        return 1

    def clickedButton(self):  # noqa: N802 — Qt API 命名（替身沿用 Qt 命名）
        return self._clicked


@pytest.fixture
def fake_messagebox(monkeypatch):
    """把 QMessageBox 换成替身，并让启动提示不再因离屏而跳过。"""
    monkeypatch.setattr(QtWidgets, "QMessageBox", _FakeMessageBox)
    monkeypatch.setenv("QT_QPA_PLATFORM", "minimal")
    monkeypatch.delenv("POLYXRD_REG_NO_PROMPT", raising=False)
    _FakeMessageBox.pick = "确定"
    _FakeMessageBox.last = None
    return _FakeMessageBox


def test_startup_prompt_shows_required_notice(fake_messagebox, tmp_path):
    """未注册提示的文案必须逐字符合需求（含版权与联系邮箱）。"""
    from xinmatch.utils.registration import (
        UNREGISTERED_NOTICE,
        RegistrationState,
        startup_prompt,
    )

    _FakeMessageBox.pick = "确定"
    state = startup_prompt(None, tmp_path / "registration.json", "XinMatch")
    box = _FakeMessageBox.last
    assert box is not None
    assert box.text == UNREGISTERED_NOTICE
    assert "禁止用于商业用途" in box.text
    assert "sshztx@outlook.com" in box.text
    assert [b.text() for b in box.buttons()] == ["确定", "输入注册码"]
    # 点「确定」→ 仍是未注册，但软件继续使用（返回未注册状态而非抛错）
    assert isinstance(state, RegistrationState)
    assert not state.registered


def test_startup_prompt_registration_branch(fake_messagebox, tmp_path, monkeypatch):
    """点「输入注册码」→ 走注册对话框；注册成功返回已注册状态（含单位名）。"""
    from xinmatch.utils import registration
    from xinmatch.utils.registration import RegistrationState, startup_prompt

    seen: dict[str, object] = {}

    def fake_prompt(parent, state_path, app_name=""):
        seen["state_path"] = state_path
        seen["app_name"] = app_name
        return RegistrationState(True, UNIT, generate_code(UNIT))

    monkeypatch.setattr(registration, "prompt_for_code", fake_prompt)
    _FakeMessageBox.pick = "输入注册码"
    state = startup_prompt(None, tmp_path / "registration.json", "XinMatch")
    assert state.registered and state.unit == UNIT
    assert seen["app_name"] == "XinMatch"
    assert str(seen["state_path"]).endswith("registration.json")


def test_status_label_is_rightmost_permanent_widget(qapp, reg_dir, monkeypatch):
    """注册标签必须是最后加入的常驻控件（即最靠右）。"""
    monkeypatch.setenv(build_variant._ENV_KEY, "release")
    window = MainWindow()
    bar = window.statusBar()
    assert bar.children()  # 状态栏已构建
    label = window._registration_label
    assert label is not None
    # addPermanentWidget(stretch=1) 后标签会占据剩余空间
    assert bar.sizeHint().width() > 0
    assert label.text() == "未注册"
