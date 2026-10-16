"""Tests for :mod:`xinmatch.utils` — registration core + build variant.

The registration module is a verbatim copy of the PolyXRD-family reference
implementation (``D:\\Project\\XRD\\PolyXRD-Reg\\registration.py``), so these
tests cover the *reused* contract from XinMatch's side:

* registration code generation / verification round-trip (Chinese unit names);
* input tolerance (case, whitespace, full-width dashes, missing prefix);
* tamper resistance: hand-edited ``registration.json`` must not fake a
  registered state (the code is re-verified on every load);
* build-variant resolution (release default / env override / frozen marker).
"""
from __future__ import annotations

import json

import pytest

from xinmatch.utils import build_variant
from xinmatch.utils.registration import (
    CODE_PREFIX,
    CONTACT_EMAIL,
    UNREGISTERED_NOTICE,
    RegistrationState,
    default_state_path,
    generate_code,
    load_state,
    save_state,
    verify_code,
)

UNIT = "清华大学材料学院粉末衍射实验室"


# --------------------------------------------------------------------------
# 注册码：生成 / 校验
# --------------------------------------------------------------------------
def test_generate_and_verify_roundtrip() -> None:
    code = generate_code(UNIT)
    assert verify_code(code) == UNIT


def test_code_shape_prefix_and_groups() -> None:
    code = generate_code("XRD Lab")
    assert code.startswith(CODE_PREFIX + "-")
    body = code[len(CODE_PREFIX) + 1:]
    assert all(len(part) == 4 for part in body.split("-")[:-1])
    assert set(body.replace("-", "")) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")


def test_verify_tolerates_case_whitespace_and_dashes() -> None:
    code = generate_code(UNIT)
    assert verify_code(code.lower()) == UNIT
    assert verify_code("  " + code + "  ") == UNIT
    assert verify_code(code.replace("-", " ")) == UNIT
    assert verify_code(code.replace("-", "－")) == UNIT  # 全角连字符
    assert verify_code(code[len(CODE_PREFIX) + 1:]) == UNIT  # 去前缀


def test_verify_rejects_garbage() -> None:
    for bad in ("", "   ", "PXRD1-", "NOT-A-CODE", "PXRD1-AAAA", "@@@@"):
        assert verify_code(bad) is None


def test_verify_rejects_tampered_payload() -> None:
    """Flipping one Base32 character must invalidate the HMAC."""
    code = generate_code(UNIT)
    body = code[len(CODE_PREFIX) + 1:].replace("-", "")
    flipped = ("B" if body[0] != "B" else "C") + body[1:]
    assert verify_code(CODE_PREFIX + "-" + flipped) is None


def test_verify_rejects_code_from_other_unit() -> None:
    """A valid code for unit A must not verify as unit B (MAC binds the name)."""
    code = generate_code("A 实验室")
    assert verify_code(code) == "A 实验室"
    assert verify_code(code) != "B 实验室"


def test_unit_name_validation() -> None:
    with pytest.raises(ValueError):
        generate_code("")
    with pytest.raises(ValueError):
        generate_code("   ")
    with pytest.raises(ValueError):
        generate_code("X" * 101)
    with pytest.raises(ValueError):
        generate_code("A\x00B")  # 控制字符（分隔符冲突）
    assert verify_code(generate_code("X" * 100)) == "X" * 100


def test_unit_name_is_normalized() -> None:
    """Consecutive whitespace collapses, so 'A  B' and 'A B' are one unit."""
    assert generate_code("材料  学院") == generate_code("材料 学院")


def test_unregistered_notice_text() -> None:
    assert CONTACT_EMAIL in UNREGISTERED_NOTICE
    assert "禁止用于商业用途" in UNREGISTERED_NOTICE


# --------------------------------------------------------------------------
# 注册状态：存取与防篡改
# --------------------------------------------------------------------------
def test_save_and_load_roundtrip(tmp_path) -> None:
    path = tmp_path / "registration.json"
    code = generate_code(UNIT)
    state = save_state(path, code)
    assert state.registered and state.unit == UNIT
    loaded = load_state(path)
    assert loaded.registered and loaded.unit == UNIT
    assert loaded.status_text == f"已注册：{UNIT}"


def test_load_missing_file_is_unregistered(tmp_path) -> None:
    state = load_state(tmp_path / "nope.json")
    assert not state.registered and state.status_text == "未注册"


def test_load_corrupt_json_is_unregistered(tmp_path) -> None:
    path = tmp_path / "registration.json"
    path.write_text("{not json", encoding="utf-8")
    assert not load_state(path).registered


def test_hand_edited_state_cannot_fake_registration(tmp_path) -> None:
    """JSON says registered but the code does not match -> treated as unpaid."""
    path = tmp_path / "registration.json"
    code = generate_code(UNIT)
    path.write_text(
        json.dumps({"code": code, "unit": "随便填的单位"}),
        encoding="utf-8",
    )
    assert not load_state(path).registered

    # 甚至把 code 换成一个无效串 + 任意 unit 也无效
    path.write_text(
        json.dumps({"code": "PXRD1-ZZZZ-ZZZZ", "unit": UNIT}),
        encoding="utf-8",
    )
    assert not load_state(path).registered


def test_save_state_rejects_invalid_code(tmp_path) -> None:
    with pytest.raises(ValueError):
        save_state(tmp_path / "registration.json", "bogus")


def test_registration_state_dataclass_defaults() -> None:
    state = RegistrationState(False)
    assert state.unit == "" and state.code == ""
    assert state.status_text == "未注册"


def test_default_state_path_is_sanitized() -> None:
    path = default_state_path("XinMatch")
    assert path.name == "XinMatch.json"
    path2 = default_state_path("A B/C")
    assert path2.name == "A_B_C.json"


# --------------------------------------------------------------------------
# 构建变体
# --------------------------------------------------------------------------
def test_variant_defaults_to_release(monkeypatch) -> None:
    monkeypatch.delenv(build_variant._ENV_KEY, raising=False)
    assert build_variant.current_variant() == build_variant.VARIANT_RELEASE
    assert build_variant.is_release() and not build_variant.is_internal()


def test_variant_env_override_when_not_frozen(monkeypatch) -> None:
    monkeypatch.setenv(build_variant._ENV_KEY, "internal")
    assert build_variant.is_internal()
    monkeypatch.setenv(build_variant._ENV_KEY, "INTERNAL")
    assert build_variant.is_internal()
    monkeypatch.setenv(build_variant._ENV_KEY, "bogus")
    assert build_variant.is_release()  # 未知值回落 release


def test_frozen_build_reads_marker_and_ignores_env(tmp_path, monkeypatch) -> None:
    """打包后的二进制只认随包 variant.txt，环境变量不能绕过注册提示。"""
    exe = tmp_path / "XinMatch.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(build_variant.sys, "frozen", True, raising=False)
    monkeypatch.setattr(build_variant.sys, "executable", str(exe), raising=False)
    monkeypatch.setenv(build_variant._ENV_KEY, "internal")
    # 无标记 -> release（fail-safe）
    assert build_variant.current_variant() == build_variant.VARIANT_RELEASE
    # 放 internal 标记 -> internal（环境变量不再起作用）
    (tmp_path / build_variant.MARKER_NAME).write_text("internal", encoding="utf-8")
    assert build_variant.is_internal()
    monkeypatch.delenv(build_variant._ENV_KEY)
    (tmp_path / build_variant.MARKER_NAME).write_text("release", encoding="utf-8")
    assert build_variant.is_release()


def test_frozen_build_reads_marker_from_internal_dir(tmp_path, monkeypatch) -> None:
    """onedir 布局：标记落在 _internal/ 下也要能读到。"""
    exe = tmp_path / "XinMatch.exe"
    exe.write_bytes(b"")
    (tmp_path / "_internal").mkdir()
    (tmp_path / "_internal" / build_variant.MARKER_NAME).write_text(
        "internal", encoding="utf-8"
    )
    monkeypatch.setattr(build_variant.sys, "frozen", True, raising=False)
    monkeypatch.setattr(build_variant.sys, "executable", str(exe), raising=False)
    monkeypatch.delenv(build_variant._ENV_KEY, raising=False)
    assert build_variant.is_internal()


def test_internal_status_text() -> None:
    assert build_variant.INTERNAL_STATUS_TEXT == "内部评估版本"
