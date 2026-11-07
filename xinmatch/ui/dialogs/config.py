"""Unified YAML configuration persistence for the GUI dialogs (T13.5).

Every settings dialog in :mod:`xinmatch.ui.dialogs` reads from and writes
back into a single YAML document.  The document is a nested dict whose
top-level keys mirror the Options-dialog pages listed in
``docs/options.md`` (general / search-match / candidate list / match list
/ peak list / diffraction pattern / legend / data sheet / raw-data
processing / indexing / quantitative analysis / Rietveld / batch) plus a
``colors`` section for :class:`~xinmatch.ui.dialogs.colors_dialog.ColorsDialog`.

Storage location follows the reference software's "personal settings" idea but uses a
portable file instead of the Windows registry:

* prefer :attr:`QStandardPaths.AppConfigLocation` (per-user, e.g.
  ``%APPDATA%/XinMatch/XinMatch``);
* fall back to ``<project>/config/xinmatch.yaml`` when that path is not
  writable (e.g. in offscreen tests — callers can always pass an explicit
  *path*).
"""

from __future__ import annotations

import contextlib
import logging
import os
from pathlib import Path
from typing import Any

import yaml
from PySide6 import QtCore

from xinmatch.core.db.multi_db import DEFAULT_LIBRARY_ID

__all__ = [
    "default_config",
    "load_config",
    "save_config",
    "app_config_dir",
    "config_path",
    "DEFAULTS",
]

logger = logging.getLogger(__name__)


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
        # FPFM 全谱拟合的 Kα1/Kα2 双线旋钮 (T16.5)。
        # ``fpfm_kalpha2_enabled`` 关闭时只按 Kα1 单线计算（旧行为）；
        # 波长填 0.0 表示"跟随样品波长配置"，非 0 时强制覆盖。
        "fpfm_kalpha2_enabled": True,
        "fpfm_kalpha1_angstrom": 0.0,
        "fpfm_kalpha2_angstrom": 1.5444,
    },
    # Multi-DB mount: which registered reference library search-match opens.
    # Missing / unknown ids resolve to the default library
    # (``xinmatch.core.db.multi_db.resolve_default()``, i.e. ``xindb_cod_inorg``
    # — the bundled COD-Inorg ``.xinDB``).
    "reference_db": {
        "selected_library_id": DEFAULT_LIBRARY_ID,
    },
    "candidate_list": {
        "show_quality": True,
        "show_crystal_system": True,
        "color_by_fom": True,
        # 候选表显示行数上限（§35 方案 B）。折叠（族合并）时一行 ≈ 一个相族，
        # 所以这个数同时是「族数上限」；展开时按卡计。检索侧返回的卡数由
        # ``main_window._candidate_row_budget()`` 按它换算（族合并只减行数，
        # 显示 N 行需要返回多于 N 张卡）。
        "max_display_rows": 50,
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
    result: dict[str, Any] = yaml.safe_load(yaml.safe_dump(DEFAULTS))
    return result


def app_config_dir() -> Path:
    """Resolve (and create) the per-user configuration directory.

    Same resolution rule as :func:`config_path`: prefer
    :attr:`QStandardPaths.AppConfigLocation`, fall back to a ``config/``
    directory next to the project root when the standard path is
    unavailable (offscreen / headless runs).

    v1.7.0: the registration state file (``registration.json``) lives here
    too, so both files move together when the user relocates their profile.
    """
    base = QtCore.QStandardPaths.writableLocation(
        QtCore.QStandardPaths.StandardLocation.AppConfigLocation
    )
    # pragma: no cover - the else branch only fires when QStandardPaths
    # returns an empty string (headless / offscreen environments).
    fallback = Path(__file__).resolve().parents[3] / "config"
    path = Path(base) if base else fallback
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    """Resolve the default YAML config file path (see :func:`app_config_dir`)."""
    return app_config_dir() / "xinmatch.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load the YAML config, merged over :data:`DEFAULTS`.

    Missing sections / keys fall back to defaults so an older or partial
    config file never breaks the dialogs.  Keys written by pre-v1.6.1
    versions (``smpf_*``) are migrated to their ``fpfm_*`` names before the
    merge, so legacy user settings keep working (and win over defaults).

    A damaged config file (truncated by an interrupted write, hand-edited
    syntax error, or replaced by a directory) must not brick the GUI: such
    files are reported in the log and the built-in defaults are returned.
    The unusable file is left on disk untouched so the user can inspect or
    delete it.  (:func:`save_config` writes atomically, so an interrupted
    ``save_config`` can no longer produce a truncated file in the first
    place — this guard covers files damaged by other means.)
    """
    file = Path(path) if path is not None else config_path()
    cfg = default_config()
    if not file.exists():
        return cfg
    try:
        with file.open("r", encoding="utf-8") as fh:
            on_disk = yaml.safe_load(fh) or {}
    except (OSError, yaml.YAMLError) as exc:
        logger.warning(
            "ignoring unreadable config file %s (%s: %s); using defaults",
            file, type(exc).__name__, exc,
        )
        return cfg
    if not isinstance(on_disk, dict):
        logger.warning(
            "ignoring config file %s: top-level YAML node is %s, expected mapping",
            file, type(on_disk).__name__,
        )
        return cfg
    _migrate_legacy_fpfm_keys(on_disk)
    _merge(cfg, on_disk)
    return cfg


def save_config(cfg: dict[str, Any], path: str | Path | None = None) -> None:
    """Write *cfg* to YAML (UTF-8, no anchor explosion) **atomically**.

    The document is serialised to a sibling ``*.tmp`` file and then
    ``os.replace``-d onto the target.  A crash / kill during the write can
    therefore never leave a half-written ``xinmatch.yaml`` behind (which
    previously made every ``load_config()`` caller raise ``yaml.YAMLError``
    on the next launch).  On any serialisation error the previous file is
    left untouched.
    """
    file = Path(path) if path is not None else config_path()
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_name(file.name + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(cfg, fh, allow_unicode=True, sort_keys=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, file)
    finally:
        # 失败路径（序列化异常 / 磁盘满 / replace 失败）清掉半成品临时文件。
        if tmp.exists():
            with contextlib.suppress(OSError):  # pragma: no cover - defensive
                tmp.unlink()


def _merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    """Recursively merge *override* into *base* in place."""
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value


def _migrate_legacy_fpfm_keys(node: Any) -> None:
    """Rename pre-v1.6.1 ``smpf_*`` config keys to ``fpfm_*`` (recursive, in place).

    v1.6.1 renamed the full-pattern fitting match feature from SMPF to FPFM;
    YAML files written by older versions carry the old key names.  Migration
    runs on the on-disk dict *before* the merge so an explicitly saved legacy
    setting still overrides the (new-named) defaults.
    """
    if not isinstance(node, dict):
        return
    for old in [k for k in node if isinstance(k, str) and k.startswith("smpf_")]:
        new = "fpfm_" + old[len("smpf_"):]
        popped = node.pop(old)
        if new not in node:
            node[new] = popped
    for value in node.values():
        _migrate_legacy_fpfm_keys(value)
