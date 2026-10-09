"""自定义"关于 XinMatch"对话框。

把原来的纯文本 :func:`QMessageBox.about` 升级为带 Logo、动态版本号与可点
击联系方式链接的 :class:`QDialog`，样式沿用全局 ``QPalette`` + QSS（浅/深
主题自动协调）。

* 版本号动态读取 :data:`xinmatch.__version__`（``importlib.metadata``），
  不在此硬编码。
* Logo 加载 ``assets/logo.png``；缺失时退化为空 QLabel，不抛错。
* 联系方式为 ``mailto:`` 富文本链接，``setOpenExternalLinks(True)`` 后可在
  系统默认邮件客户端中唤起。
"""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

import xinmatch
from xinmatch.ui.structure_view import THREEMOL_VERSION
from xinmatch.ui.theme import THEMES, current_theme


def _asset_path(name: str) -> Path:
    """Resolve a top-level ``assets/`` file (logo.png).

    与 ``main_window._asset_path`` 同构：本模块位于 ``xinmatch/ui/``，故
    ``parents[2]`` 即项目根。在此重复一份而非 ``from main_window import``，
    以避免循环导入。
    """
    return Path(__file__).resolve().parents[2] / "assets" / name


class AboutDialog(QtWidgets.QDialog):
    """模态关于对话框：Logo + 标题 + 动态版本 + 简介 + 联系方式。"""

    def __init__(self, parent=None) -> None:
        """Build the About dialog; version read dynamically from package."""
        super().__init__(parent)
        self.setWindowTitle("关于 XinMatch")
        self.setModal(True)

        accent = THEMES[current_theme()]["accent"]

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        # --- Logo -------------------------------------------------------
        logo_label = QtWidgets.QLabel()
        logo_label.setObjectName("about_logo")
        pix = QtGui.QPixmap(str(_asset_path("logo.png")))
        if not pix.isNull():
            pix = pix.scaled(
                128, 128,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
        logo_label.setPixmap(pix)
        logo_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo_label)

        # --- 标题 -------------------------------------------------------
        title = QtWidgets.QLabel("XinMatch")
        title.setObjectName("about_title")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {accent};")
        font = title.font()
        font.setPointSize(18)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # --- 版本（动态读取，勿硬编码） ---------------------------------
        version_label = QtWidgets.QLabel(f"版本 {xinmatch.__version__}")
        version_label.setObjectName("about_version")
        version_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        # --- 简介 -------------------------------------------------------
        intro = QtWidgets.QLabel(
            "开源粉末 XRD 物相分析平台 —— 经典商业 XRD 软件的净室开源替代。"
        )
        intro.setWordWrap(True)
        intro.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(intro)

        # --- 3Dmol.js 版本 ----------------------------------------------
        threemol_label = QtWidgets.QLabel(f"3Dmol.js {THREEMOL_VERSION}")
        threemol_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(threemol_label)

        # --- 联系方式（mailto 可点击） ----------------------------------
        contact = QtWidgets.QLabel(
            '联系方式：<a href="mailto:sshztx@outlook.com" '
            f'style="color:{accent}">sshztx@outlook.com</a>'
        )
        contact.setObjectName("about_contact")
        contact.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        contact.setOpenExternalLinks(True)
        contact.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextBrowserInteraction
        )
        layout.addWidget(contact)

        layout.addSpacing(8)

        # --- 确定按钮 ---------------------------------------------------
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
        )
        buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setText(
            "确定"
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setMinimumWidth(360)
