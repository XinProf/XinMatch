"""GUI dialogs package (T13.5).

Collects the import / experiment / options / colours dialogs plus the
shared YAML configuration helpers:

* :class:`~xinmatch.ui.dialogs.import_dialog.ImportDialog`
* :class:`~xinmatch.ui.dialogs.experiment_dialog.ExperimentDetailsDialog`
* :class:`~xinmatch.ui.dialogs.options_dialog.OptionsDialog`
* :class:`~xinmatch.ui.dialogs.colors_dialog.ColorsDialog`
* :func:`~xinmatch.ui.dialogs.config.load_config` /
  :func:`~xinmatch.ui.dialogs.config.save_config` /
  :func:`~xinmatch.ui.dialogs.config.default_config`
"""

from __future__ import annotations

from xinmatch.ui.dialogs.colors_dialog import ColorsDialog
from xinmatch.ui.dialogs.config import (
    config_path,
    default_config,
    load_config,
    save_config,
)
from xinmatch.ui.dialogs.experiment_dialog import ExperimentDetailsDialog
from xinmatch.ui.dialogs.import_dialog import ImportDialog
from xinmatch.ui.dialogs.options_dialog import OptionsDialog

__all__ = [
    "ColorsDialog",
    "ExperimentDetailsDialog",
    "ImportDialog",
    "OptionsDialog",
    "config_path",
    "default_config",
    "load_config",
    "save_config",
]
