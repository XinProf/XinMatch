"""构建变体识别：正式版（带注册） vs 内部评估版（不带注册）。

XinMatch v1.7.0 起同时产出两个二进制：

* **正式版（release）** —— Inno Setup 安装版。启动时检查注册状态：未注册弹
  出版权提示（确定→继续使用／输入注册码→完成注册），状态栏最右侧显示
  「已注册：<单位部门名称>」或「未注册」。
* **内部评估版（internal）** —— 免安装 zip，自用。不接入注册机制，状态栏
  最右侧固定显示 ``内部评估版本``。

变体如何判定
------------
打包时由 :mod:`PyInstaller` 把一份 ``variant.txt``（内容 ``release`` 或
``internal``）随产物分发，运行时按下列顺序解析：

1. ``XINMATCH_VARIANT`` 环境变量——**仅在源码运行时生效**（测试与开发用）。
   冻结后的二进制忽略该变量，避免用它绕过正式版的注册提示。
2. 二进制目录下的 ``variant.txt``（onedir 根目录与 ``_internal/`` 都查）。
3. 都没有 → 按 **release** 处理（fail-safe：漏放标记只会多提示注册，不会
   静默变成免注册版本）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

__all__ = [
    "VARIANT_RELEASE",
    "VARIANT_INTERNAL",
    "MARKER_NAME",
    "INTERNAL_STATUS_TEXT",
    "current_variant",
    "is_internal",
    "is_release",
]

#: 正式版变体（含注册机制）。
VARIANT_RELEASE = "release"

#: 内部评估版变体（不含注册机制）。
VARIANT_INTERNAL = "internal"

_VARIANTS = (VARIANT_RELEASE, VARIANT_INTERNAL)

#: 打包时随产物分发的标记文件名。
MARKER_NAME = "variant.txt"

#: 环境变量名（仅源码运行时生效）。
_ENV_KEY = "XINMATCH_VARIANT"

#: 内部评估版在状态栏最右侧显示的固定文案。
INTERNAL_STATUS_TEXT = "内部评估版本"


def _bundle_roots() -> list[Path]:
    """冻结运行时需要查找 ``variant.txt`` 的目录（按优先级）。"""
    if not getattr(sys, "frozen", False):
        return []
    roots: list[Path] = []
    exe_dir = Path(sys.executable).resolve().parent
    roots.append(exe_dir)
    roots.append(exe_dir / "_internal")
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(Path(meipass))
    return roots


def _read_marker(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip().lower()
    except OSError:
        return ""
    return value if value in _VARIANTS else ""


def current_variant() -> str:
    """返回当前进程的构建变体（``"release"`` / ``"internal"``）。"""
    # 1) 源码运行（含 pytest）：允许环境变量覆盖，便于两种变体都可直接测。
    if not getattr(sys, "frozen", False):
        env = os.environ.get(_ENV_KEY, "").strip().lower()
        if env in _VARIANTS:
            return env
        return VARIANT_RELEASE
    # 2) 冻结二进制：只看随包分发的标记文件。
    for root in _bundle_roots():
        value = _read_marker(root / MARKER_NAME)
        if value:
            return value
    return VARIANT_RELEASE


def is_internal() -> bool:
    """当前是否为内部评估版（不弹注册提示）。"""
    return current_variant() == VARIANT_INTERNAL


def is_release() -> bool:
    """当前是否为正式版（需要注册检查）。"""
    return current_variant() == VARIANT_RELEASE
