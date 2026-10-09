"""T13.5 — tests for the GUI dialogs and YAML persistence (offscreen)."""

from __future__ import annotations

from pathlib import Path

import pytest

from xinmatch.ui.dialogs import (
    ColorsDialog,
    ExperimentDetailsDialog,
    ImportDialog,
    OptionsDialog,
    default_config,
    load_config,
    save_config,
)


def test_import_dialog_values(qapp):
    dlg = ImportDialog(config={"wavelength": 1.54, "step": 0.02})
    v = dlg.values()
    assert v["wavelength"] == pytest.approx(1.54)
    assert v["step"] == pytest.approx(0.02)
    assert "format" in v and "axis" not in v  # axis lives on experiment dialog


def test_experiment_dialog_roundtrip(qapp):
    cfg = {"sample_name": "石英", "wavelength": 1.78897, "axis": "2θ"}
    dlg = ExperimentDetailsDialog(config=cfg)
    v = dlg.values()
    assert v["sample_name"] == "石英"
    assert v["wavelength"] == pytest.approx(1.78897)


def test_options_dialog_backfill_and_writeback(qapp):
    cfg = default_config()
    cfg["searchmatch"]["min_fom"] = 0.75
    dlg = OptionsDialog(config=cfg)
    v = dlg.values()
    # Backfill: dialog must reflect the supplied config.
    assert v["searchmatch"]["min_fom"] == pytest.approx(0.75)
    assert v["general"]["check_updates"] is True
    # Every options category present.
    for section in ("general", "searchmatch", "candidate_list", "match_list",
                    "peak_list", "diffpattern", "quant_analysis"):
        assert section in v


def test_options_persists_to_yaml(tmp_path: Path, qapp):
    cfg = default_config()
    cfg["searchmatch"]["min_fom"] = 0.42
    dlg = OptionsDialog(config=cfg)
    out = dlg.values()
    target = tmp_path / "xinmatch.yaml"
    save_config(out, target)
    loaded = load_config(target)
    assert loaded["searchmatch"]["min_fom"] == pytest.approx(0.42)
    # Defaults merged in for untouched sections.
    assert loaded["general"]["auto_save_interval_min"] == 10


def test_colors_dialog_backfill_and_persist(tmp_path: Path, qapp):
    cfg = default_config()
    cfg["colors"]["experimental"]["color"] = "#112233"
    dlg = ColorsDialog(config=cfg["colors"])
    v = dlg.values()
    assert v["experimental"]["color"] == "#112233"
    # Change a colour and persist.
    dlg._exp_color.set_color("#aabbcc")
    v2 = dlg.values()
    assert v2["experimental"]["color"] == "#aabbcc"
    target = tmp_path / "colors.yaml"
    save_config({"colors": v2}, target)
    loaded = load_config(target)
    assert loaded["colors"]["experimental"]["color"] == "#aabbcc"
    assert loaded["colors"]["elements"]["required"].startswith("#")


def test_save_load_creates_file(tmp_path: Path, qapp):
    cfg = default_config()
    cfg["peak_list"]["show_hkl"] = True
    target = tmp_path / "sub" / "xinmatch.yaml"
    save_config(cfg, target)
    assert target.exists()
    loaded = load_config(target)
    assert loaded["peak_list"]["show_hkl"] is True
