"""PDF-2 source-path config round-trip and override precedence.

D1: the new ``pdf2_source_dir`` YAML key survives a save/load round-trip, and
    an old config file that predates the key loads with the empty default.
D2: the in-memory GUI override (``multi_db.set_pdf2_source_dir``) takes
    precedence over the ``XINMATCH_POLYXRD_DIR`` environment variable, both when
    given a ``.sqlite`` file and when given a containing directory, and
    clearing it falls back to the env var again.
"""

from __future__ import annotations

from pathlib import Path

from xinmatch.core.db import multi_db
from xinmatch.ui.dialogs.config import (
    default_config,
    load_config,
    save_config,
)


# ---------------------------------------------------------------------------
# D1: YAML round-trip + backward compatibility
# ---------------------------------------------------------------------------
def test_pdf2_source_dir_default_is_empty():
    cfg = default_config()
    assert cfg["pdf2_source_dir"] == ""


def test_pdf2_source_dir_roundtrip(tmp_path: Path):
    cfg = default_config()
    cfg["pdf2_source_dir"] = r"D:\PolyXRD\cod_data"
    target = tmp_path / "xinmatch.yaml"
    save_config(cfg, target)
    loaded = load_config(target)
    assert loaded["pdf2_source_dir"] == r"D:\PolyXRD\cod_data"


def test_old_config_without_key_falls_back_to_empty(tmp_path: Path):
    # An old config that predates the key must still load cleanly.
    target = tmp_path / "old.yaml"
    target.write_text(
        "reference_db:\n  selected_library_id: cod_inorganics\n",
        encoding="utf-8",
    )
    loaded = load_config(target)
    assert loaded["pdf2_source_dir"] == ""


# ---------------------------------------------------------------------------
# D2: override precedence over the environment variable
# ---------------------------------------------------------------------------
def test_pdf2_source_override_precedence(monkeypatch, tmp_path: Path):
    tmp_a = tmp_path / "env_dir"
    tmp_a.mkdir()
    tmp_b = tmp_path / "override_dir"
    tmp_b.mkdir()
    tmp_b_file = tmp_b / "PDF2_2004.sqlite"

    # Pin the override global so we restore it after the test.
    monkeypatch.setattr(multi_db, "_pdf2_source_override", None)
    # Env var points at tmp_a.
    monkeypatch.setenv("XINMATCH_POLYXRD_DIR", str(tmp_a))

    # 1. No override -> env var wins.
    assert multi_db.pdf2_source_path() == tmp_a / "PDF2_2004.sqlite"

    # 2. Override with a .sqlite file -> used directly, beats env.
    multi_db.set_pdf2_source_dir(tmp_b_file)
    assert multi_db.pdf2_source_path() == tmp_b_file

    # 3. Override with a directory -> conventional file name appended.
    multi_db.set_pdf2_source_dir(tmp_a)
    assert multi_db.pdf2_source_path() == tmp_a / "PDF2_2004.sqlite"

    # 4. Clear override -> back to env var.
    multi_db.set_pdf2_source_dir(None)
    assert multi_db.pdf2_source_path() == tmp_a / "PDF2_2004.sqlite"
