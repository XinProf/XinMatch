"""自定义"关于 XinMatch"对话框的离屏测试。

覆盖：
* AboutDialog 可构造、Logo pixmap 真实加载 assets/logo.png；
* 版本号动态读取（文本含包版本）、联系方式链接文本正确；
* 浅/深主题下均可构造且文字可读；
* MainWindow._open_about 正确接线到 AboutDialog（monkeypatch 避免 exec 阻塞）。
"""

from __future__ import annotations

from unittest.mock import MagicMock

from PySide6 import QtWidgets

import xinmatch
from xinmatch.ui.about_dialog import AboutDialog
from xinmatch.ui.main_window import MainWindow
from xinmatch.ui.theme import apply_theme


def test_about_dialog_constructs(qapp):
    dlg = AboutDialog()
    assert dlg.windowTitle()


def test_about_logo_loaded_from_asset(qapp):
    dlg = AboutDialog()
    logo = dlg.findChild(QtWidgets.QLabel, "about_logo")
    assert logo is not None
    pm = logo.pixmap()
    assert pm is not None
    assert not pm.isNull()
    assert pm.width() > 0 and pm.height() > 0


def test_about_version_dynamic(qapp):
    dlg = AboutDialog()
    version = dlg.findChild(QtWidgets.QLabel, "about_version")
    assert xinmatch.__version__ in version.text()
    assert "版本" in version.text()


def test_about_contact_contains_email(qapp):
    dlg = AboutDialog()
    contact = dlg.findChild(QtWidgets.QLabel, "about_contact")
    assert "sshztx@outlook.com" in contact.text()
    assert contact.openExternalLinks() is True


def test_about_dialog_constructs_in_dark_theme(qapp):
    apply_theme(qapp, "dark")
    try:
        dlg = AboutDialog()
        version = dlg.findChild(QtWidgets.QLabel, "about_version")
        contact = dlg.findChild(QtWidgets.QLabel, "about_contact")
        assert xinmatch.__version__ in version.text()
        assert "sshztx@outlook.com" in contact.text()
    finally:
        apply_theme(qapp, "light")


def test_open_about_wires_about_dialog(qapp, monkeypatch):
    """_open_about 必须实例化 AboutDialog 并调用 exec（避免 exec 阻塞测试）。"""
    win = MainWindow()

    instances: list = []

    class FakeAbout:
        def __init__(self, *args, **kwargs):
            self.exec_ = MagicMock(return_value=0)
            instances.append(self)

        def exec(self):
            return self.exec_()

    monkeypatch.setattr("xinmatch.ui.main_window.AboutDialog", FakeAbout)
    win._open_about()
    assert len(instances) == 1
    instances[0].exec_.assert_called_once()


def test_about_has_no_open_source_or_cleanroom_mention(qapp):
    """关于页不出现"开源 / 净室 / 商业对标"类措辞。"""
    dlg = AboutDialog()
    texts = [lbl.text() for lbl in dlg.findChildren(QtWidgets.QLabel)]
    joined = "\n".join(texts)
    for banned in ("开源", "净室", "clean-room", "CleanRoom"):
        assert banned not in joined
    # 功能简介两行存在
    assert any("X 射线衍射仪数据分析软件" in t for t in texts)
    assert any("物相识别" in t and "Rietveld" in t for t in texts)


def test_about_has_copyright_line(qapp):
    dlg = AboutDialog()
    copyright_label = dlg.findChild(QtWidgets.QLabel, "about_copyright")
    assert copyright_label is not None
    assert "版权所有" in copyright_label.text()
