"""Report renderers (T12.2).

Converts a :class:`~xinmatch.core.report.report_model.Report` into the
formats supported by the reference software (see ``docs/export_report.md`` and
``docs/report_print.md``):

* :func:`render_html`     — single-file HTML string (CSS inlined).
* :func:`render_text`     — pure-ASCII text report (matches the
  ``report_print.md`` layout).
* :func:`render_markdown` — Markdown for documentation integration.
* :func:`render_pdf`      — HTML → PDF via *weasyprint* (optional).

All three text formats render the **same** chapter set:
``sample_info / peak_list / candidate_list / selected_phases /
quant_result / r_factors``.  The renderers do not perform file I/O
except for :func:`render_pdf`, which writes the PDF to disk.

The HTML is built with f-strings — no Jinja2 dependency required.
weasyprint is imported lazily inside :func:`render_pdf` so the rest of
the module works without it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from xinmatch.core.report.report_model import (
    CandidateEntry,
    Report,
)


# ---------------------------------------------------------------------------
# Helpers shared by all renderers
# ---------------------------------------------------------------------------
def _fmt_optional(value: Any, fmt: str = "{}", na: str = "—") -> str:
    """Format *value* with *fmt*; return *na* if ``None``."""
    if value is None:
        return na
    try:
        return fmt.format(value)
    except (TypeError, ValueError):
        return str(value)


def _peak_rows(report: Report) -> list[dict[str, Any]]:
    """Return peak rows as plain dicts (two_theta / intensity / fwhm / d / hkl)."""
    rows: list[dict[str, Any]] = []
    for i, p in enumerate(report.peak_list.peaks, start=1):
        rows.append(
            {
                "idx": i,
                "two_theta": p.two_theta,
                "intensity": p.intensity,
                "fwhm": p.fwhm,
                "d": p.d,
                "hkl": (
                    " ".join(str(h) for h in p.hkl) if p.hkl is not None else ""
                ),
            }
        )
    return rows


def _candidate_rows(report: Report) -> list[CandidateEntry]:
    return list(report.candidate_list.candidates)


def _phase_rows(report: Report) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ph in report.selected_phases.phases:
        e = ph.entry
        rows.append(
            {
                "entry_id": e.entry_id,
                "formula": e.formula,
                "name": e.mineral_name or "",
                "space_group": e.space_group or "",
                "scale_factor": ph.scale_factor,
                "weight_fraction": ph.weight_fraction,
            }
        )
    return rows


def _quant_rows(report: Report) -> list[tuple[str, float, float]]:
    """Return ``(phase_name, weight_fraction, percent)`` tuples."""
    return [
        (name, wf, wf * 100.0)
        for name, wf in report.quant_result.weight_fractions.items()
    ]


def _rfactor_pairs(report: Report) -> list[tuple[str, float | None]]:
    r = report.r_factors
    return [
        ("Rwp", r.rwp),
        ("Rp", r.rp),
        ("Rexp", r.rexp),
        ("χ² (chi²)", r.chi2),
    ]


# ---------------------------------------------------------------------------
# Plain-text renderer
# ---------------------------------------------------------------------------
def render_text(report: Report) -> str:
    """Render the report as a plain ASCII text string.

    Layout follows ``docs/report_print.md`` (the *printable* report):
    header → sample info → peak list → candidate list → selected phases
    → quantitative result → R factors.
    """
    lines: list[str] = []
    lines.append("=" * 78)
    lines.append("XinMatch — Phase Analysis Report")
    lines.append("=" * 78)
    if report.timestamp:
        lines.append(f"Generated: {report.timestamp}")
    lines.append("")

    # Sample info
    si = report.sample_info
    lines.append("-" * 78)
    lines.append("Sample Information")
    lines.append("-" * 78)
    lines.append(f"  Sample name      : {si.sample_name or '—'}")
    lines.append(f"  Operator         : {si.operator or '—'}")
    lines.append(f"  Date             : {si.date or '—'}")
    lines.append(f"  Instrument       : {si.instrument or '—'}")
    lines.append(
        f"  Wavelength (Å)   : {_fmt_optional(si.wavelength, '{:.4f}')}"
    )
    lines.append(f"  Sample prep.    : {si.sample_preparation or '—'}")
    lines.append(f"  Comments         : {si.comments or '—'}")
    lines.append("")

    # Peak list
    _render_text_peak_table(report, lines)
    # Candidate list
    _render_text_candidate_table(report, lines)
    # Selected phases
    _render_text_phase_table(report, lines)
    # Quantitative result
    _render_text_quant_table(report, lines)
    # R factors
    _render_text_rfactor_table(report, lines)

    lines.append("=" * 78)
    lines.append("End of report")
    lines.append("=" * 78)
    return "\n".join(lines) + "\n"


def _render_text_peak_table(report: Report, lines: list[str]) -> None:
    lines.append("-" * 78)
    lines.append("Peak List")
    lines.append("-" * 78)
    rows = _peak_rows(report)
    if not rows:
        lines.append("  (no peaks)")
        lines.append("")
        return
    header = (
        f"  {'#':>3}  {'2θ (°)':>10}  {'I':>10}  "
        f"{'FWHM':>8}  {'d (Å)':>10}  {'hkl':<8}"
    )
    lines.append(header)
    lines.append("  " + "-" * 70)
    for r in rows:
        lines.append(
            f"  {r['idx']:>3}  {r['two_theta']:>10.3f}  {r['intensity']:>10.2f}  "
            f"{_fmt_optional(r['fwhm'], '{:>8.3f}', '       —'):>8}  "
            f"{_fmt_optional(r['d'], '{:>10.4f}', '         —'):>10}  "
            f"{r['hkl']:<8}"
        )
    lines.append("")


def _render_text_candidate_table(report: Report, lines: list[str]) -> None:
    lines.append("-" * 78)
    lines.append("Candidate List")
    lines.append("-" * 78)
    rows = _candidate_rows(report)
    if not rows:
        lines.append("  (no candidates)")
        lines.append("")
        return
    lines.append(
        f"  {'#':>3}  {'Entry ID':<14}  {'Formula':<22}  "
        f"{'Name':<18}  {'FoM':>10}"
    )
    lines.append("  " + "-" * 70)
    for i, c in enumerate(rows, start=1):
        lines.append(
            f"  {i:>3}  {c.entry_id:<14}  {c.formula[:22]:<22}  "
            f"{(c.name or '—')[:18]:<18}  {c.fom:>10.4f}"
        )
    lines.append("")


def _render_text_phase_table(report: Report, lines: list[str]) -> None:
    lines.append("-" * 78)
    lines.append("Selected Phases")
    lines.append("-" * 78)
    rows = _phase_rows(report)
    if not rows:
        lines.append("  (no phases selected)")
        lines.append("")
        return
    lines.append(
        f"  {'#':>3}  {'Entry ID':<14}  {'Formula':<22}  "
        f"{'Name':<18}  {'S.G.':<8}  {'Scale':>8}  {'Wt%':>7}"
    )
    lines.append("  " + "-" * 70)
    for i, r in enumerate(rows, start=1):
        wt = _fmt_optional(r["weight_fraction"], "{:>7.2f}", "     —")
        lines.append(
            f"  {i:>3}  {r['entry_id']:<14}  {r['formula'][:22]:<22}  "
            f"{(r['name'] or '—')[:18]:<18}  {r['space_group'] or '—':<8}  "
            f"{r['scale_factor']:>8.3f}  {wt:>7}"
        )
    lines.append("")


def _render_text_quant_table(report: Report, lines: list[str]) -> None:
    lines.append("-" * 78)
    lines.append("Quantitative Result (weight fractions)")
    lines.append("-" * 78)
    rows = _quant_rows(report)
    if not rows:
        lines.append("  (no quantitative result)")
        lines.append("")
        return
    lines.append(f"  {'Phase':<30}  {'Wt frac':>10}  {'wt %':>10}")
    lines.append("  " + "-" * 54)
    for name, wf, pct in rows:
        lines.append(f"  {name[:30]:<30}  {wf:>10.4f}  {pct:>10.2f}")
    lines.append("")


def _render_text_rfactor_table(report: Report, lines: list[str]) -> None:
    lines.append("-" * 78)
    lines.append("Profile Agreement Factors (Rietveld / pattern fit)")
    lines.append("-" * 78)
    pairs = _rfactor_pairs(report)
    has_any = any(v is not None for _, v in pairs)
    if not has_any:
        lines.append("  (no R factors computed)")
        lines.append("")
        return
    for name, v in pairs:
        lines.append(f"  {name:<10}  =  {_fmt_optional(v, '{:.4f}')}")
    lines.append("")


# ---------------------------------------------------------------------------
# HTML renderer
# ---------------------------------------------------------------------------
_CSS = """
body { font-family: -apple-system, "Segoe UI", Arial, sans-serif; color: #222;
       margin: 2em auto; max-width: 880px; padding: 0 1em; }
h1 { border-bottom: 2px solid #2c5d8a; color: #2c5d8a; padding-bottom: .25em; }
h2 { border-bottom: 1px solid #ccc; margin-top: 1.5em; color: #2c5d8a; }
table { border-collapse: collapse; width: 100%; margin: .5em 0 1em 0;
        font-size: 0.92em; }
th, td { border: 1px solid #bbb; padding: 4px 8px; text-align: left; }
th { background: #eef3f8; font-weight: 600; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
.meta { color: #555; font-size: 0.88em; }
.empty { color: #888; font-style: italic; }
.kv td:first-child { width: 30%; color: #555; }
"""


def _html_escape(s: Any) -> str:
    """Minimal HTML escaping (no external dependency)."""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _html_table(headers: list[str], rows: list[list[str]], cls: str = "") -> str:
    if not rows:
        return '<p class="empty">(none)</p>'
    th = "".join(f"<th>{_html_escape(h)}</th>" for h in headers)
    body = []
    for row in rows:
        tds = "".join(f"<td>{_html_escape(c)}</td>" for c in row)
        body.append(f"<tr>{tds}</tr>")
    class_attr = f' class="{cls}"' if cls else ""
    return f"<table{class_attr}><thead><tr>{th}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def render_html(report: Report) -> str:
    """Render the report as a self-contained HTML string.

    CSS is inlined so the file can be opened directly in a browser
    without any external stylesheet (see ``docs/export_report.md``).
    """
    si = report.sample_info

    def kv(label: str, value: Any, fmt: str = "{}") -> str:
        if value is None or value == "":
            v = "—"
        else:
            try:
                v = fmt.format(value)
            except (TypeError, ValueError):
                v = str(value)
        return f"<tr><td>{_html_escape(label)}</td><td>{_html_escape(v)}</td></tr>"

    sample_html = (
        '<table class="kv">'
        + kv("Sample name", si.sample_name)
        + kv("Operator", si.operator)
        + kv("Date", si.date)
        + kv("Instrument", si.instrument)
        + kv("Wavelength (Å)", si.wavelength, "{:.4f}")
        + kv("Sample preparation", si.sample_preparation)
        + kv("Comments", si.comments)
        + "</table>"
    )

    # Peak list table
    peak_rows = [
        [
            str(r["idx"]),
            f"{r['two_theta']:.3f}",
            f"{r['intensity']:.2f}",
            _fmt_optional(r["fwhm"], "{:.3f}", "—"),
            _fmt_optional(r["d"], "{:.4f}", "—"),
            r["hkl"] or "—",
        ]
        for r in _peak_rows(report)
    ]
    peak_html = _html_table(
        ["#", "2θ (°)", "I", "FWHM", "d (Å)", "hkl"], peak_rows
    )

    # Candidate list table
    cand_rows = [
        [
            str(i),
            c.entry_id,
            c.formula,
            c.name or "—",
            f"{c.fom:.4f}",
        ]
        for i, c in enumerate(_candidate_rows(report), start=1)
    ]
    cand_html = _html_table(
        ["#", "Entry ID", "Formula", "Name", "FoM"], cand_rows
    )

    # Selected phases table
    phase_rows = [
        [
            str(i),
            r["entry_id"],
            r["formula"],
            r["name"] or "—",
            r["space_group"] or "—",
            f"{r['scale_factor']:.3f}",
            _fmt_optional(r["weight_fraction"], "{:.2f}", "—"),
        ]
        for i, r in enumerate(_phase_rows(report), start=1)
    ]
    phase_html = _html_table(
        ["#", "Entry ID", "Formula", "Name", "Space group", "Scale", "Wt %"],
        phase_rows,
    )

    # Quant result table
    quant_rows = [
        [name, f"{wf:.4f}", f"{pct:.2f}"]
        for name, wf, pct in _quant_rows(report)
    ]
    quant_html = _html_table(
        ["Phase", "Weight fraction", "wt %"], quant_rows, cls="num"
    )

    # R factors
    rf_pairs = _rfactor_pairs(report)
    if any(v is not None for _, v in rf_pairs):
        rf_rows = [
            [name, _fmt_optional(v, "{:.4f}", "—")]
            for name, v in rf_pairs
            if v is not None
        ]
        rf_html = _html_table(["Factor", "Value"], rf_rows, cls="num")
    else:
        rf_html = '<p class="empty">(no R factors computed)</p>'

    ts = _html_escape(report.timestamp or "—")
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>XinMatch Report</title>"
        f"<style>{_CSS}</style></head><body>"
        "<h1>XinMatch Phase Analysis Report</h1>"
        f'<p class="meta">Generated: {ts}</p>'
        "<h2>Sample Information</h2>"
        f"{sample_html}"
        "<h2>Peak List</h2>"
        f"{peak_html}"
        "<h2>Candidate List</h2>"
        f"{cand_html}"
        "<h2>Selected Phases</h2>"
        f"{phase_html}"
        "<h2>Quantitative Result</h2>"
        f"{quant_html}"
        "<h2>R Factors</h2>"
        f"{rf_html}"
        "</body></html>"
    )


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------
def render_markdown(report: Report) -> str:
    """Render the report as Markdown (GitHub-flavoured)."""
    si = report.sample_info
    out: list[str] = []
    out.append("# XinMatch Phase Analysis Report")
    if report.timestamp:
        out.append(f"\n_Generated: {report.timestamp}_\n")

    # Sample info
    out.append("## Sample Information\n")
    out.append("| Field | Value |")
    out.append("|---|---|")
    out.append(f"| Sample name | {si.sample_name or '—'} |")
    out.append(f"| Operator | {si.operator or '—'} |")
    out.append(f"| Date | {si.date or '—'} |")
    out.append(f"| Instrument | {si.instrument or '—'} |")
    out.append(
        f"| Wavelength (Å) | {_fmt_optional(si.wavelength, '{:.4f}')} |"
    )
    out.append(f"| Sample preparation | {si.sample_preparation or '—'} |")
    out.append(f"| Comments | {si.comments or '—'} |")
    out.append("")

    # Peak list
    out.append("## Peak List\n")
    if not _peak_rows(report):
        out.append("_(no peaks)_\n")
    else:
        out.append("| # | 2θ (°) | I | FWHM | d (Å) | hkl |")
        out.append("|---:|---:|---:|---:|---:|---|")
        for r in _peak_rows(report):
            out.append(
                f"| {r['idx']} | {r['two_theta']:.3f} | {r['intensity']:.2f} | "
                f"{_fmt_optional(r['fwhm'], '{:.3f}', '—')} | "
                f"{_fmt_optional(r['d'], '{:.4f}', '—')} | "
                f"{r['hkl'] or '—'} |"
            )
        out.append("")

    # Candidate list
    out.append("## Candidate List\n")
    if not _candidate_rows(report):
        out.append("_(no candidates)_\n")
    else:
        out.append("| # | Entry ID | Formula | Name | FoM |")
        out.append("|---:|---|---|---|---:|")
        for i, c in enumerate(_candidate_rows(report), start=1):
            out.append(
                f"| {i} | {c.entry_id} | {c.formula} | "
                f"{c.name or '—'} | {c.fom:.4f} |"
            )
        out.append("")

    # Selected phases
    out.append("## Selected Phases\n")
    if not _phase_rows(report):
        out.append("_(no phases selected)_\n")
    else:
        out.append("| # | Entry ID | Formula | Name | Space group | Scale | Wt % |")
        out.append("|---:|---|---|---|---|---:|---:|")
        for i, r in enumerate(_phase_rows(report), start=1):
            out.append(
                f"| {i} | {r['entry_id']} | {r['formula']} | "
                f"{r['name'] or '—'} | {r['space_group'] or '—'} | "
                f"{r['scale_factor']:.3f} | "
                f"{_fmt_optional(r['weight_fraction'], '{:.2f}', '—')} |"
            )
        out.append("")

    # Quant result
    out.append("## Quantitative Result\n")
    if not _quant_rows(report):
        out.append("_(no quantitative result)_\n")
    else:
        out.append("| Phase | Weight fraction | wt % |")
        out.append("|---|---:|---:|")
        for name, wf, pct in _quant_rows(report):
            out.append(f"| {name} | {wf:.4f} | {pct:.2f} |")
        out.append("")

    # R factors
    out.append("## R Factors\n")
    rf_pairs = _rfactor_pairs(report)
    if not any(v is not None for _, v in rf_pairs):
        out.append("_(no R factors computed)_\n")
    else:
        out.append("| Factor | Value |")
        out.append("|---|---:|")
        for name, v in rf_pairs:
            if v is not None:
                out.append(f"| {name} | {v:.4f} |")
        out.append("")

    return "\n".join(out)


# ---------------------------------------------------------------------------
# PDF renderer (optional weasyprint)
# ---------------------------------------------------------------------------
def render_pdf(report: Report, output_path: str | Path) -> None:
    """Render the report to a PDF file via *weasyprint*.

    weasyprint is an **optional** dependency — if it is not installed an
    :class:`ImportError` is raised with installation instructions.  This
    keeps the report layer importable on minimal installs.

    Parameters
    ----------
    report:
        The :class:`Report` to render.
    output_path:
        Destination PDF file path.
    """
    try:
        from weasyprint import HTML  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "weasyprint is required for PDF rendering. "
            "Install it with: pip install weasyprint"
        ) from exc

    html_str = render_html(report)
    HTML(string=html_str).write_pdf(str(output_path))
