"""Options dialog with one page per category (T13.5).

The Options dialog (``docs/options.md``) is a tab widget whose pages map
1:1 to the option sub-documents: general, search-match, candidate list,
match list, peak list, diffraction pattern, legend, data sheet, automatic
raw-data processing, indexing, quantitative analysis, Rietveld and batch.
Each page exposes the controls whose semantics match the corresponding
``docs/options_*.md`` help text; :meth:`values` collects them back into the
YAML-ready nested dict.
"""

from __future__ import annotations

from typing import Any

from PySide6 import QtWidgets

__all__ = ["OptionsDialog"]

# (page title, section key, rows) — each row is (label, config key, kind, default).
# kind: "check" | "spin" | "dspin" | "text".
_PAGES: tuple[tuple[str, str, list[tuple[str, str, str, Any]]], ...] = (
    ("常规", "general", [
        ("启动时检查更新", "check_updates", "check", True),
        ("启动时检查新数据库", "check_databases", "check", True),
        ("自动保存以恢复", "auto_save", "check", True),
        ("自动保存间隔（分钟）", "auto_save_interval_min", "spin", 10),
        ("Diamond 路径", "diamond_path", "text", ""),
        ("FullProf 路径", "fullprof_path", "text", ""),
    ]),
    ("Search-Match", "searchmatch", [
        ("最小 FoM", "min_fom", "dspin", 0.6),
        ("峰相关窗口（°）", "correlation_window_deg", "dspin", 0.3),
        ("仅使用标记峰", "use_marked_peaks_only", "check", False),
        ("FPFM 启用 Kα2 双线", "fpfm_kalpha2_enabled", "check", True),
        ("FPFM Kα1 波长 (Å，0=跟随样品)", "fpfm_kalpha1_angstrom", "dspin", 0.0),
        ("FPFM Kα2 波长 (Å)", "fpfm_kalpha2_angstrom", "dspin", 1.5444),
    ]),
    ("候选列表", "candidate_list", [
        ("显示质量标记", "show_quality", "check", True),
        ("显示晶系", "show_crystal_system", "check", True),
        ("按 FoM 着色", "color_by_fom", "check", True),
    ]),
    ("匹配列表", "match_list", [
        ("显示含量 (%)", "show_amount_pct", "check", True),
        ("显示未识别峰面积", "show_unidentified_area", "check", True),
    ]),
    ("峰列表", "peak_list", [
        ("显示 FWHM", "show_fwhm", "check", True),
        ("显示 hkl", "show_hkl", "check", False),
        ("显示 d 值", "show_d_values", "check", True),
    ]),
    ("衍射图谱", "diffpattern", [
        ("背景色", "background_color", "text", "#ffffff"),
        ("网格色", "grid_color", "text", "#dddddd"),
        ("线宽", "line_width", "dspin", 1.0),
        ("显示珍珠光标", "show_pearl_cursor", "check", True),
    ]),
    ("图例", "diffpattern_legend", [
        ("显示图例", "show_legend", "check", True),
    ]),
    ("自动原始数据处理", "auto_rawdata_proc", [
        ("平滑", "smooth", "check", False),
        ("扣背景", "background_subtract", "check", False),
    ]),
    ("指标化", "indexing", [
        ("默认程序", "program", "text", "treor90"),
    ]),
    ("定量分析", "quant_analysis", [
        ("方法", "method", "text", "RIR"),
    ]),
    ("Rietveld", "Rietveld", []),
    ("批处理", "batch", []),
)


class OptionsDialog(QtWidgets.QDialog):
    """Tabbed options dialog populated from *config*."""

    def __init__(self, config: dict[str, Any] | None = None,
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("选项")
        self.resize(560, 480)
        cfg = config or {}

        self._tabs = QtWidgets.QTabWidget()

        for title, section, rows in _PAGES:
            page = self._build_page(cfg.get(section, {}), rows)
            self._tabs.addTab(page, title)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._tabs)
        self._save_as_defaults = QtWidgets.QCheckBox("保存为默认设置")
        layout.addWidget(self._save_as_defaults)
        layout.addWidget(QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            accepted=self.accept, rejected=self.reject,
        ))  # type: ignore[call-overload]

    def _build_page(self, section_cfg: dict[str, Any],
                    rows: list[tuple[str, str, str, Any]]) -> QtWidgets.QWidget:
        form = QtWidgets.QFormLayout()
        widgets: dict[str, QtWidgets.QWidget] = {}
        for label, key, kind, default in rows:
            value = section_cfg.get(key, default)
            w: (
                QtWidgets.QCheckBox
                | QtWidgets.QSpinBox
                | QtWidgets.QDoubleSpinBox
                | QtWidgets.QLineEdit
            )
            if kind == "check":
                w = QtWidgets.QCheckBox()
                w.setChecked(bool(value))
            elif kind == "spin":
                w = QtWidgets.QSpinBox()
                w.setRange(0, 100000)
                w.setValue(int(value))
            elif kind == "dspin":
                w = QtWidgets.QDoubleSpinBox()
                w.setRange(0.0, 1e6)
                w.setDecimals(4)
                w.setValue(float(value))
            else:
                w = QtWidgets.QLineEdit(str(value))
            widgets[key] = w
            form.addRow(label + ":", w)
        page = QtWidgets.QWidget()
        page.setLayout(form)
        return page

    def values(self) -> dict[str, Any]:
        """Collect every page into the nested config dict."""
        out: dict[str, Any] = {}
        for _title, section, rows in _PAGES:
            out[section] = self._collect_page(section, rows)
        return out

    def _collect_page(self, section: str,
                      rows: list[tuple[str, str, str, Any]]) -> dict[str, Any]:
        # Re-derive widgets from the tab pages (kept simple & robust).
        result: dict[str, Any] = {}
        idx = [t[1] for t in _PAGES].index(section)
        page = self._tabs.widget(idx)
        form = page.layout() if page is not None else None
        if form is None:
            return result
        for i, (_label, key, _kind, _default) in enumerate(rows):
            field_item = form.itemAt(i, QtWidgets.QFormLayout.ItemRole.FieldRole)  # type: ignore[call-arg]
            w = field_item.widget() if field_item is not None else None
            if isinstance(w, QtWidgets.QCheckBox):
                result[key] = w.isChecked()
            elif isinstance(w, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
                result[key] = w.value()
            elif isinstance(w, QtWidgets.QLineEdit):
                result[key] = w.text()
        return result
