"""XinMatch command-line interface (T14.1).

A thin argparse-based wrapper around the core pipeline.  Each subcommand
delegates to the corresponding :mod:`xinmatch.core` routine; no
algorithms are implemented at this layer.

Subcommands
-----------
import    Load a diffraction pattern file.
process   Run the automatic raw-data processing pipeline.
search    Run peak-based search-match against a reference database.
quantify  Run RIR quantitative phase analysis.
report    Render a phase-analysis report (HTML / text / markdown).
run       One-shot pipeline: import → process → search → quantify → report.

Every subcommand supports ``--help`` and a global ``--json`` flag that
switches the output from human-readable text to a structured JSON
document on stdout.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from xinmatch.core.io import load_pattern
from xinmatch.core.model import Restraints
from xinmatch.core.preprocess.auto_pipeline import auto_process
from xinmatch.core.quant.rir import rir_quantify
from xinmatch.core.report import (
    Report,
    render_html,
    render_markdown,
    render_text,
)
from xinmatch.core.report.report_model import (
    CandidateEntry,
    CandidateListSection,
    PeakListSection,
    SampleInfo,
)
from xinmatch.core.search import search_match


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
def _emit(result: dict[str, Any], as_json: bool) -> None:
    """Print *result* as JSON or a short human-readable summary."""
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return

    # Human-readable summary.
    for key, value in result.items():
        if isinstance(value, list):
            print(f"{key}: {len(value)} item(s)")
        elif isinstance(value, dict):
            print(f"{key}: {len(value)} entry(ies)")
        else:
            print(f"{key}: {value}")


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------
def cmd_import(args: argparse.Namespace) -> dict[str, Any]:
    """``xinmatch import`` — load a pattern and print basic info."""
    pattern = load_pattern(args.pattern_file)
    if args.wavelength is not None:
        pattern.wavelength = float(args.wavelength)
    return {
        "file": str(args.pattern_file),
        "n_points": int(len(pattern)),
        "two_theta_start": float(pattern.two_theta[0]) if len(pattern) else None,
        "two_theta_end": float(pattern.two_theta[-1]) if len(pattern) else None,
        "wavelength": float(pattern.wavelength),
    }


def cmd_process(args: argparse.Namespace) -> dict[str, Any]:
    """``xinmatch process`` — run the auto processing pipeline."""
    pattern = load_pattern(args.pattern_file)
    config: dict[str, Any] = {}
    if args.smooth is not None:
        config["smooth"] = args.smooth
    if args.background is not None:
        config["background"] = args.background
    if args.alpha2 is not None:
        config["strip_alpha2"] = args.alpha2
    if args.wavelength is not None:
        pattern.wavelength = float(args.wavelength)

    processed, peaks = auto_process(pattern, config=config or None)
    return {
        "file": str(args.pattern_file),
        "n_points": int(len(processed)),
        "n_peaks": len(peaks),
        "peaks": [
            {"two_theta": float(p.two_theta), "intensity": float(p.intensity)}
            for p in peaks
        ],
    }


def _load_restraints(raw: str | None) -> Restraints | None:
    if not raw:
        return None
    return Restraints.from_dict(json.loads(raw))


def cmd_search(args: argparse.Namespace) -> dict[str, Any]:
    """``xinmatch search`` — search-match against a reference database."""
    pattern = load_pattern(args.pattern_file)
    if args.wavelength is not None:
        pattern.wavelength = float(args.wavelength)
    _processed, peaks = auto_process(pattern)
    restraints = _load_restraints(args.restraints)

    conn = sqlite3.connect(args.db)
    try:
        candidates = search_match(
            peaks,
            conn,
            pattern.wavelength,
            restraints=restraints,
            top_n=args.top_n,
        )
    finally:
        conn.close()

    return {
        "file": str(args.pattern_file),
        "db": str(args.db),
        "n_peaks": len(peaks),
        "n_candidates": len(candidates),
        "candidates": [
            {
                "entry_id": c.entry.entry_id,
                "formula": c.entry.formula,
                "name": c.entry.mineral_name or "",
                "fom": float(c.fom),
            }
            for c in candidates
        ],
    }


def cmd_quantify(args: argparse.Namespace) -> dict[str, Any]:
    """``xinmatch quantify`` — RIR quantitative phase analysis."""
    intensities = json.loads(args.phases)
    rir_values = json.loads(args.rir) if args.rir else {k: 1.0 for k in intensities}
    weight_fractions = rir_quantify(intensities, rir_values)
    return {
        "weight_fractions": {k: float(v) for k, v in weight_fractions.items()},
    }


def cmd_report(args: argparse.Namespace) -> dict[str, Any]:
    """``xinmatch report`` — render a phase-analysis report.

    Reads a previously saved JSON report (produced by the ``--json``
    output of ``search`` / ``run``) or builds a minimal report from a
    pattern file.
    """
    if args.input_report and Path(args.input_report).exists():
        report = Report.from_json(args.input_report)
    else:
        pattern = load_pattern(args.pattern_file)
        _processed, peaks = auto_process(pattern)
        sample_info = SampleInfo(
            sample_name=Path(args.pattern_file).stem,
            wavelength=pattern.wavelength,
        )
        report = Report.now(
            sample_info=sample_info,
            peak_list=PeakListSection(peaks=peaks),
        )

    fmt = (args.format or "html").lower()
    if fmt == "text":
        content = render_text(report)
    elif fmt in ("md", "markdown"):
        content = render_markdown(report)
    else:
        content = render_html(report)

    out_path = args.output or (str(Path(args.pattern_file).with_suffix("")) + ".html")
    Path(out_path).write_text(content, encoding="utf-8")
    return {
        "format": fmt,
        "output": str(out_path),
        "bytes": len(content),
    }


def cmd_run(args: argparse.Namespace) -> dict[str, Any]:
    """``xinmatch run`` — one-shot full analysis pipeline."""
    pattern = load_pattern(args.pattern_file)
    if args.wavelength is not None:
        pattern.wavelength = float(args.wavelength)
    _processed, peaks = auto_process(pattern)
    restraints = _load_restraints(args.restraints)

    conn = sqlite3.connect(args.db)
    try:
        candidates = search_match(
            peaks,
            conn,
            pattern.wavelength,
            restraints=restraints,
            top_n=args.top_n,
        )
    finally:
        conn.close()

    # Quantification: top candidate with unit RIR.
    weight_fractions: dict[str, float] = {}
    if candidates:
        top = candidates[0]
        phase_name = top.entry.mineral_name or top.entry.formula or top.entry.entry_id
        main_intensity = max((p.intensity for p in peaks), default=0.0)
        if main_intensity > 0:
            weight_fractions = rir_quantify(
                {phase_name: main_intensity}, {phase_name: 1.0}
            )

    # Build report.
    sample_info = SampleInfo(
        sample_name=Path(args.pattern_file).stem,
        wavelength=pattern.wavelength,
    )
    cand_section = CandidateListSection(
        candidates=[
            CandidateEntry(
                entry_id=c.entry.entry_id,
                formula=c.entry.formula,
                name=c.entry.mineral_name or "",
                fom=c.fom,
                p_values=list(c.p_values.values()),
            )
            for c in candidates
        ]
    )
    report = Report.now(
        sample_info=sample_info,
        peak_list=PeakListSection(peaks=peaks),
        candidate_list=cand_section,
    )
    report.quant_result.weight_fractions = dict(weight_fractions)

    # Render report.
    fmt = (args.format or "html").lower()
    if fmt == "text":
        content = render_text(report)
    elif fmt in ("md", "markdown"):
        content = render_markdown(report)
    else:
        content = render_html(report)

    out_path = args.output
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(content, encoding="utf-8")

    return {
        "file": str(args.pattern_file),
        "db": str(args.db),
        "n_peaks": len(peaks),
        "n_candidates": len(candidates),
        "top_candidate": (
            candidates[0].entry.entry_id if candidates else None
        ),
        "weight_fractions": {k: float(v) for k, v in weight_fractions.items()},
        "report": str(out_path),
    }


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
def _add_json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit structured JSON instead of human-readable output.",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="xinmatch",
        description=(
            "XinMatch — powder XRD phase analysis. "
            "Subcommands: import, process, search, quantify, report, run."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- import ---
    p_import = sub.add_parser("import", help="Import a diffraction pattern file.")
    p_import.add_argument("pattern_file", help="Path to the pattern file.")
    p_import.add_argument(
        "--wavelength", type=float, default=None,
        help="Override radiation wavelength (Å).",
    )
    _add_json_flag(p_import)
    p_import.set_defaults(func=cmd_import)

    # --- process ---
    p_proc = sub.add_parser(
        "process", help="Run the automatic raw-data processing pipeline."
    )
    p_proc.add_argument("pattern_file", help="Path to the pattern file.")
    p_proc.add_argument(
        "--wavelength", type=float, default=None,
        help="Override radiation wavelength (Å).",
    )
    p_proc.add_argument(
        "--smooth", action="store_true", default=None,
        help="Enable smoothing.",
    )
    p_proc.add_argument(
        "--no-smooth", dest="smooth", action="store_false",
        help="Disable smoothing.",
    )
    p_proc.add_argument(
        "--background", action="store_true", default=None,
        help="Enable background estimation/subtraction.",
    )
    p_proc.add_argument(
        "--no-background", dest="background", action="store_false",
        help="Disable background estimation/subtraction.",
    )
    p_proc.add_argument(
        "--alpha2", action="store_true", default=None,
        help="Enable Kα2 stripping.",
    )
    p_proc.add_argument(
        "--no-alpha2", dest="alpha2", action="store_false",
        help="Disable Kα2 stripping.",
    )
    _add_json_flag(p_proc)
    p_proc.set_defaults(func=cmd_process)

    # --- search ---
    p_search = sub.add_parser(
        "search", help="Run search-match against a reference database."
    )
    p_search.add_argument("pattern_file", help="Path to the pattern file.")
    p_search.add_argument("--db", required=True, help="Path to the reference .db file.")
    p_search.add_argument(
        "--wavelength", type=float, default=None,
        help="Override radiation wavelength (Å).",
    )
    p_search.add_argument(
        "--restraints", default=None,
        help="JSON string of Restraints (see Restraints.to_dict).",
    )
    p_search.add_argument(
        "--top-n", type=int, default=20,
        help="Maximum number of candidates to return (default 20).",
    )
    _add_json_flag(p_search)
    p_search.set_defaults(func=cmd_search)

    # --- quantify ---
    p_quant = sub.add_parser(
        "quantify", help="Run RIR quantitative phase analysis."
    )
    p_quant.add_argument(
        "--phases", required=True,
        help='JSON: {"phase_name": main_peak_intensity, ...}',
    )
    p_quant.add_argument(
        "--rir", default=None,
        help='JSON: {"phase_name": rir_value, ...} (defaults to 1.0 each).',
    )
    _add_json_flag(p_quant)
    p_quant.set_defaults(func=cmd_quantify)

    # --- report ---
    p_rep = sub.add_parser("report", help="Render a phase-analysis report.")
    p_rep.add_argument(
        "pattern_file", nargs="?", default=None,
        help="Path to the pattern file (used when --input-report is absent).",
    )
    p_rep.add_argument(
        "--input-report", default=None,
        help="Path to a JSON report file (produced by search --json / run --json).",
    )
    p_rep.add_argument(
        "--output", "-o", default=None,
        help="Output report path (default: <pattern>.html).",
    )
    p_rep.add_argument(
        "--format", choices=["html", "text", "md"], default="html",
        help="Report format (default html).",
    )
    _add_json_flag(p_rep)
    p_rep.set_defaults(func=cmd_report)

    # --- run ---
    p_run = sub.add_parser(
        "run", help="One-shot pipeline: import → process → search → quantify → report."
    )
    p_run.add_argument("pattern_file", help="Path to the pattern file.")
    p_run.add_argument("--db", required=True, help="Path to the reference .db file.")
    p_run.add_argument(
        "--output", "-o", required=True, help="Output report path.",
    )
    p_run.add_argument(
        "--format", choices=["html", "text", "md"], default="html",
        help="Report format (default html).",
    )
    p_run.add_argument(
        "--wavelength", type=float, default=None,
        help="Override radiation wavelength (Å).",
    )
    p_run.add_argument(
        "--restraints", default=None,
        help="JSON string of Restraints.",
    )
    p_run.add_argument(
        "--top-n", type=int, default=20,
        help="Maximum number of candidates (default 20).",
    )
    _add_json_flag(p_run)
    p_run.set_defaults(func=cmd_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Parameters
    ----------
    argv:
        Argument list (defaults to ``sys.argv[1:]``).

    Returns
    -------
    int
        Process exit code (0 on success, non-zero on error).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = args.func(args)
    except Exception as exc:  # noqa: BLE001 — CLI top-level error boundary
        print(f"error: {exc}", file=sys.stderr)
        return 1

    _emit(result, getattr(args, "as_json", False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
