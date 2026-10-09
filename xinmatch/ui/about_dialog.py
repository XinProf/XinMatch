"""自定义"关于 XinMatch"对话框。

参考同类 XRD 数据分析软件的关于页排版（小图标 + 软件名 + 版本 + 功能
简介 + 联系方式 + 版权），样式沿用全局 ``QPalette`` + QSS（浅/深主题自动
协调）。

* 版本号动态读取 :data:`xinmatch.__version__`（``importlib.metadata``），
  不在此硬编码。
* Logo 优先加载 ``assets/icons/logo_128.png``（透明底小图标，避免深色大
  底框）；缺失时依次回退 ``assets/logo_transparent.png``、
  ``assets/logo.png``，再退化空 QLabel，不抛错。
* 联系方式为 ``mailto:`` 富文本链接，``setOpenExternalLinks(True)`` 后可在
  系统默认邮件客户端中唤起。
"""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

import xinmatch
from xinmatch.ui.theme import THEMES, current_theme


def _asset_path(name: str) -> Path:
    """Resolve a top-level ``assets/`` file.

    与 ``main_window._asset_path`` 同构：本模块位于 ``xinmatch/ui/``，故
    ``parents[2]`` 即项目根。在此重复一份而非 ``from main_window import``，
    以避免循环导入。
    """
    return Path(__file__).resolve().parents[2] / "assets" / name


def _load_logo_pixmap() -> QtGui.QPixmap:
    """Load a transparent, small logo (no dark box); empty pixmap on failure."""
    for name in ("icons/logo_128.png", "logo_transparent.png", "logo.png"):
        pix = QtGui.QPixmap(str(_asset_path(name)))
        if not pix.isNull():
            return pix
    return QtGui.QPixmap()


class AboutDialog(QtWidgets.QDialog):
    """模态关于对话框：小 Logo + 标题 + 版本 + 功能简介 + 联系方式 + 版权。"""

    def __init__(self, parent=None) -> None:
        """Build the About dialog; version read dynamically from package."""
        super().__init__(parent)
        self.setWindowTitle("关于 XinMatch")
        self.setModal(True)

        accent = THEMES[current_theme()]["accent"]

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(8)

        # --- 顶部行：小 Logo（左）+ 软件名 / 版本（右） -----------------
        header = QtWidgets.QHBoxLayout()
        header.setSpacing(16)

        logo_label = QtWidgets.QLabel()
        logo_label.setObjectName("about_logo")
        pix = _load_logo_pixmap()
        if not pix.isNull():
            pix = pix.scaled(
                96, 96,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
        logo_label.setPixmap(pix)
        logo_label.setFixedSize(96, 96)
        logo_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        header.addWidget(logo_label)

        title_col = QtWidgets.QVBoxLayout()
        title_col.setSpacing(4)

        title = QtWidgets.QLabel("XinMatch")
        title.setObjectName("about_title")
        title.setStyleSheet(f"color: {accent};")
        font = title.font()
        font.setPointSize(20)
        font.setBold(True)
        title.setFont(font)
        title_col.addWidget(title)

        version_label = QtWidgets.QLabel(f"版本 {xinmatch.__version__}")
        version_label.setObjectName("about_version")
        version_label.setStyleSheet("color: #777;")
        title_col.addWidget(version_label)

        title_col.addStretch(1)
        header.addLayout(title_col)
        header.addStretch(1)
        layout.addLayout(header)

        # --- 分隔线 -----------------------------------------------------
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        layout.addSpacing(4)
        layout.addWidget(line)
        layout.addSpacing(6)

        # --- 定位与功能简介 ---------------------------------------------
        role = QtWidgets.QLabel("X 射线衍射仪数据分析软件")
        role.setObjectName("about_role")
        role.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        font = role.font()
        font.setPointSize(10)
        role.setFont(font)
        layout.addWidget(role)

        features = QtWidgets.QLabel(
            "物相识别 · 峰拟合 · Rietveld 精修 · 多数据库"
        )
        features.setObjectName("about_features")
        features.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        features.setStyleSheet("color: #777;")
        layout.addWidget(features)

        layout.addSpacing(8)

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

        # --- 版权 -------------------------------------------------------
        copyright_label = QtWidgets.QLabel("©2026 版权所有")
        copyright_label.setObjectName("about_copyright")
        copyright_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        copyright_label.setStyleSheet("color: #999;")
        layout.addWidget(copyright_label)

        layout.addSpacing(10)

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

        self.setMinimumWidth(420)
