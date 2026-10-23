"""构建变体识别（release / internal）的单元测试。

v3.0.0 交付要求：**便携版（内部评估版）**在页面最下方状态栏用红色加粗字
显示「内部评估版本」。文案与判定逻辑都在
:mod:`xinmatch.utils.build_variant`，这里覆盖判定规则本身；状态栏的外观
由 ``tests/ui/test_registration_ui.py::test_internal_build_label_is_red_and_bold``
覆盖。

判定顺序（见模块 docstring）：

1. 源码运行时读 ``XINMATCH_VARIANT`` 环境变量；
2. 冻结二进制只读随包的 ``variant.txt``（onedir 根目录与 ``_internal/``）；
3. 都没有 → ``release``（fail-safe：漏放标记只会多提示注册）。
"""
from __future__ import annotations

import sys

import pytest

from xinmatch.utils import build_variant


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """每个用例都从"没有环境变量"开始，避免被外部环境污染。"""
    monkeypatch.delenv(build_variant._ENV_KEY, raising=False)
    yield


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
def test_internal_status_text_is_the_required_chinese_label():
    assert build_variant.INTERNAL_STATUS_TEXT == "内部评估版本"
    assert build_variant.MARKER_NAME == "variant.txt"


# ---------------------------------------------------------------------------
# 源码运行：环境变量说了算
# ---------------------------------------------------------------------------
def test_source_run_defaults_to_release():
    assert build_variant.current_variant() == build_variant.VARIANT_RELEASE
    assert build_variant.is_release() is True
    assert build_variant.is_internal() is False


def test_source_run_honours_internal_env(monkeypatch):
    monkeypatch.setenv(build_variant._ENV_KEY, "internal")
    assert build_variant.current_variant() == build_variant.VARIANT_INTERNAL
    assert build_variant.is_internal() is True
    assert build_variant.is_release() is False


def test_source_run_ignores_bogus_env(monkeypatch):
    monkeypatch.setenv(build_variant._ENV_KEY, "Internal-Eval")  # 大小写/拼写都不对
    assert build_variant.current_variant() == build_variant.VARIANT_RELEASE


def test_source_run_strips_whitespace(monkeypatch):
    monkeypatch.setenv(build_variant._ENV_KEY, "  internal  ")
    assert build_variant.is_internal() is True


# ---------------------------------------------------------------------------
# 冻结运行：只信 variant.txt（环境变量不得绕过正式版的注册检查）
# ---------------------------------------------------------------------------
class _Frozen:
    """把 ``sys.frozen`` / ``sys.executable`` / ``sys._MEIPASS`` 伪装成 onedir。"""

    def __init__(self, monkeypatch, exe_dir):
        self._monkeypatch = monkeypatch
        self._exe_dir = exe_dir

    def __enter__(self):
        self._monkeypatch.setattr(sys, "frozen", True, raising=False)
        self._monkeypatch.setattr(
            sys, "executable", str(self._exe_dir / "XinMatch.exe"), raising=False
        )
        self._monkeypatch.setattr(
            sys, "_MEIPASS", str(self._exe_dir / "_internal"), raising=False
        )
        return self

    def __exit__(self, *exc):
        self._monkeypatch.undo()
        return False


def test_frozen_reads_marker_next_to_exe(tmp_path, monkeypatch):
    (tmp_path / build_variant.MARKER_NAME).write_text("internal", encoding="utf-8")
    with _Frozen(monkeypatch, tmp_path):
        assert build_variant.is_internal() is True


def test_frozen_reads_marker_inside_internal_dir(tmp_path, monkeypatch):
    internal = tmp_path / "_internal"
    internal.mkdir()
    (internal / build_variant.MARKER_NAME).write_text("release\n", encoding="utf-8")
    with _Frozen(monkeypatch, tmp_path):
        assert build_variant.is_release() is True


def test_frozen_ignores_env_override(tmp_path, monkeypatch):
    """冻结后环境变量不得把正式版变成免注册版。"""
    (tmp_path / build_variant.MARKER_NAME).write_text("release", encoding="utf-8")
    monkeypatch.setenv(build_variant._ENV_KEY, "internal")
    with _Frozen(monkeypatch, tmp_path):
        assert build_variant.is_release() is True


def test_frozen_without_marker_is_release(tmp_path, monkeypatch):
    """漏放 variant.txt 时按 release 处理（多提示注册，绝不静默免注册）。"""
    with _Frozen(monkeypatch, tmp_path):
        assert build_variant.current_variant() == build_variant.VARIANT_RELEASE


def test_frozen_ignores_corrupt_marker(tmp_path, monkeypatch):
    (tmp_path / build_variant.MARKER_NAME).write_text("porable", encoding="utf-8")
    with _Frozen(monkeypatch, tmp_path):
        assert build_variant.is_release() is True
