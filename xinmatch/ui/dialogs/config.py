"""Unified YAML configuration persistence for the GUI dialogs (T13.5).

Every settings dialog in :mod:`xinmatch.ui.dialogs` reads from and writes
back into a single YAML document.  The document is a nested dict whose
top-level keys mirror the Options-dialog pages listed in
``docs/options.md`` (general / search-match / candidate list / match list
/ peak list / diffraction pattern / legend / data sheet / raw-data
processing / indexing / quantitative analysis / Rietveld / batch) plus a
``colors`` section for :class:`~xinmatch.ui.dialogs.colors_dialog.ColorsDialog`.

Storage location follows Match!'s "personal settings" idea but uses a
portable file instead of the Windows registry:

* prefer :attr:`QStandardPaths.AppConfigLocation` (per-user, e.g.
  ``%APPDATA%/XinMatch/XinMatch``);
* fall back to ``<project>/config/xinmatch.yaml`` when that path is not
  writable (e.g. in offscreen tests — callers can always pass an explicit
  *path*).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from PySide6 import QtCore

__all__ = [
    "default_config",
    "load_config",
    "save_config",
    "config_path",
    "DEFAULTS",
]


#: Default configuration mirroring every Options / Colors page.
DEFAULTS: dict[str, Any] = {
    "general": {
        "check_updates": True,
        "check_databases": True,
        "auto_save": True,
        "auto_save_interval_min": 10,
        "diamond_path": "",
        "endeavour_path": "",
        "fullprof_path": "",
        "treor90_path": "",
        "dicvol_path": "",
    },
    "searchmatch": {
        "min_fom": 0.6,
        "correlation_window_deg": 0.3,
        "use_marked_peaks_only": False,
    },
    "candidate_list": {
        "show_quality": True,
        "show_crystal_system": True,
        "color_by_fom": True,
    },
    "match_list": {
        "show_amount_pct": True,
        "show_unidentified_area": True,
    },
    "peak_list": {
        "show_fwhm": True,
        "show_hkl": False,
        "show_d_values": True,
    },
    "diffpattern": {
        "background_color": "#ffffff",
        "grid_color": "#dddddd",
        "border_color": "#000000",
        "line_width": 1.0,
        "show_pearl_cursor": True,
    },
    "diffpattern_legend": {
        "show_legend": True,
    },
    "data_sheet": {},
    "auto_rawdata_proc": {
        "smooth": False,
        "background_subtract": False,
    },
    "indexing": {
        "program": "treor90",
    },
    "quant_analysis": {
        "method": "RIR",
    },
    "Rietveld": {},
    "batch": {},
    "colors": {
        "experimental": {"color": "#0000ff", "line_style": "solid", "line_width": 1.0},
        "reference_defaults": [
            {"color": "#ff0000", "line_style": "solid", "line_width": 1.0},
            {"color": "#00aa00", "line_style": "solid", "line_width": 1.0},
            {"color": "#0000ff", "line_style": "solid", "line_width": 1.0},
        ],
        "elements": {
            "required": "#b8e6b8",
            "excluded": "#f2b8b8",
            "optional": "#f0f0f0",
        },
        "spectra": {"k_alpha1": "#000000", "k_alpha2": "#888888"},
    },
}


def default_config() -> dict[str, Any]:
    """Return a deep copy of :data:`DEFAULTS` safe to mutate."""
    return yaml.safe_load(yaml.safe_dump(DEFAULTS))


def config_path() -> Path:
    """Resolve the default YAML config file path.

    Prefers :attr:`QStandardPaths.AppConfigLocation`; falls back to a
    ``config/`` directory next to the project root when the standard path
    is unavailable (offscreen / headless runs).
    """
    base = QtCore.QStandardPaths.writableLocation(
        QtCore.QStandardPaths.StandardLocation.AppConfigLocation
    )
    # pragma: no cover - the else branch only fires when QStandardPaths
    # returns an empty string (headless / offscreen environments).
    fallback = Path(__file__).resolve().parents[3] / "config"
    path = Path(base) if base else fallback
    path.mkdir(parents=True, exist_ok=True)
    return path / "xinmatch.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load the YAML config, merged over :data:`DEFAULTS`.

    Missing sections / keys fall back to defaults so an older or partial
    config file never breaks the dialogs.
    """
    file = Path(path) if path is not None else config_path()
    cfg = default_config()
    if file.exists():
        with file.open("r", encoding="utf-8") as fh:
            on_disk = yaml.safe_load(fh) or {}
        _merge(cfg, on_disk)
    return cfg


def save_config(cfg: dict[str, Any], path: str | Path | None = None) -> None:
    """Write *cfg* to YAML (UTF-8, no anchor explosion)."""
    file = Path(path) if path is not None else config_path()
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, allow_unicode=True, sort_keys=False)


def _merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    """Recursively merge *override* into *base* in place."""
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
