"""版本号「一个真相源」检查：pyproject ↔ ``__init__`` ↔ Inno Setup ↔ spec。

历史包袱（3.4.x 实测）：同一个版本号在四处各写一遍，然后各自漂移 ——
``pyproject.toml`` 写着 3.4.1，``__init__._FALLBACK_VERSION`` 是 3.4.0，
``xinmatch.spec`` 的 ``APP_VERSION`` 是 3.4.0，``tools/xinmatch_setup.iss`` 的
``AppVersion`` 也是 3.4.0。后果不是「显示不好看」，而是三件实事：

* 冻结包的 ``About`` / ``.xinm`` manifest 写出 ``_FALLBACK_VERSION``（3.4.0），
  源码运行却报 3.4.1 —— 用户报 bug 时给的版本号对不上仓库 tag；
* 安装包文件名固定成 ``XinMatch-Setup-3.4.0.exe``，与 Release 的 tag 不一致；
* spec 里那道 guard 只比 ``spec ↔ __init__``，两个都是 3.4.0 所以照样放行，
  **管不到 pyproject 与 iss** —— 这正是它漂了三处还没人发现的原因。

所以这里不再靠「记得一起改」，而是让不一致直接测试失败。真相源固定为
``pyproject.toml`` 的 ``[project] version``，其余三处必须与它逐字相同；
``xinmatch.spec`` 额外要求**不出现字面量**（必须从 pyproject 推导，这样
bump 时不需要动 spec，只剩 iss 一处需要同步）。
"""

from __future__ import annotations

import re
from pathlib import Path

import xinmatch

REPO = Path(__file__).resolve().parents[1]
_PYPROJECT = REPO / "pyproject.toml"
_ISS = REPO / "tools" / "xinmatch_setup.iss"
_SPEC = REPO / "xinmatch.spec"


def _pyproject_version() -> str:
    """读 ``[project] version``。不依赖 ``tomllib``（3.10 没有）。"""
    text = _PYPROJECT.read_text(encoding="utf-8")
    section = re.search(r"^\[project\]\s*$(.*?)(?=^\[)", text,
                        re.MULTILINE | re.DOTALL)
    assert section, "pyproject.toml 里找不到 [project] 段"
    m = re.search(r'^version\s*=\s*"([^"]+)"', section.group(1), re.MULTILINE)
    assert m, "pyproject.toml 的 [project] 段缺 version"
    return m.group(1)


def test_pyproject_is_the_source_of_truth() -> None:
    version = _pyproject_version()
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), (
        f"版本号必须是三段式数字，实际 {version!r}"
    )


def test_frozen_fallback_version_matches_pyproject() -> None:
    """冻结包没有 pyproject，``__version__`` 直接返回这个常量。"""
    assert _pyproject_version() == xinmatch._FALLBACK_VERSION, (
        "xinmatch/__init__.py 的 _FALLBACK_VERSION 与 pyproject.toml 不同步；"
        "冻结 exe 的 About / .xinm manifest 会写出错误版本"
    )


def test_inno_setup_version_matches_pyproject() -> None:
    """``AppVersion`` 决定安装包文件名与控制面板里显示的版本。"""
    text = _ISS.read_text(encoding="utf-8")
    m = re.search(r'^#define\s+AppVersion\s+"([^"]+)"', text, re.MULTILINE)
    assert m, "tools/xinmatch_setup.iss 缺 `#define AppVersion \"x.y.z\"`"
    assert m.group(1) == _pyproject_version(), (
        f"iss AppVersion={m.group(1)!r} 与 pyproject "
        f"{_pyproject_version()!r} 不同步"
    )


def test_inno_setup_has_no_other_hardcoded_version() -> None:
    """``AppVerName`` / ``UninstallDisplayName`` / ``OutputBaseFilename`` 必须引用宏。

    直接在字符串里写版本号是第二次漂移的入口（3.4.0 时代就有 5 处各写一遍）。
    """
    text = _ISS.read_text(encoding="utf-8")
    version = _pyproject_version()
    offenders = [
        f"{no}: {line.strip()}"
        for no, line in enumerate(text.splitlines(), start=1)
        if version in line and "#define" not in line
    ]
    assert not offenders, (
        "安装脚本里除了 #define 之外不应再出现字面版本号，改用 {#AppVersion}：\n"
        + "\n".join(offenders)
    )


def test_spec_derives_app_version_instead_of_literal() -> None:
    """spec 必须从 pyproject 推导，否则每次 bump 都要改第四处。"""
    text = _SPEC.read_text(encoding="utf-8")
    assert not re.search(r'^APP_VERSION\s*=\s*"', text, re.MULTILINE), (
        "xinmatch.spec 的 APP_VERSION 又写回字面量了；应调用 pyproject 读取函数"
    )
    assert "def _pyproject_version" in text, (
        "xinmatch.spec 缺少 _pyproject_version() —— 版本号无法从 pyproject 推导"
    )
