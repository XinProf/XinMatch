"""XinMatch — Open-source powder XRD phase analysis platform.

Top-level public API for programmatic use.  All heavy lifting is
delegated to the :mod:`xinmatch.core` subpackages; this module only
re-exports the most commonly used symbols and provides three
convenience functions that chain the core pipeline steps:

* :func:`load_and_preprocess` — import a pattern file and run the
  automatic raw-data processing pipeline.
* :func:`identify_phase` — run search-match against a reference
  database and return ranked candidates.
* :func:`full_analysis` — one-shot import → process → search →
  quantify → report pipeline.
"""

from __future__ import annotations

import importlib.metadata
import sqlite3
from pathlib import Path
from typing import Any

from xinmatch.core.io import load_pattern as _load_pattern
from xinmatch.core.model import (
    CellParams,
    Entry,
    Pattern,
    Peak,
    Phase,
    Project,
    Restraints,
)
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
from xinmatch.core.search import CandidateResult
from xinmatch.core.search import search_match as _search_match

try:
    __version__ = importlib.metadata.version("xinmatch")
except importlib.metadata.PackageNotFoundError:  # pragma: no cover - source tree / frozen
    # Running from a source checkout that was never ``pip install``-ed (or from a
    # frozen bundle stripped of dist-info): keep the package importable.  Keep in
    # sync with ``[project] version`` in pyproject.toml and ``xinmatch.spec``.
    __version__ = "1.7.1"

__all__ = [
    "__version__",
    # data models
    "Pattern",
    "Peak",
    "Entry",
    "CellParams",
    "Phase",
    "Restraints",
    "Project",
    "Report",
    "CandidateResult",
    "CandidateEntry",
    # core functions
    "load_pattern",
    "preprocess",
    "search_match",
    "quantify",
    "generate_report",
    # high-level pipeline
    "load_and_preprocess",
    "identify_phase",
    "full_analysis",
]


# ---------------------------------------------------------------------------
# Core function re-exports (thin wrappers for a stable top-level surface)
# ---------------------------------------------------------------------------
def load_pattern(path: str | Path) -> Pattern:
    """Auto-detect format and load a diffraction pattern from disk.

    See :func:`xinmatch.core.io.load_pattern`.
    """
    return _load_pattern(path)


def preprocess(pattern: Pattern, **kwargs: Any) -> tuple[Pattern, list[Peak]]:
    """Run the automatic raw-data processing pipeline.

    *kwargs* are merged on top of the default pipeline config
    (``smooth``, ``background``, ``strip_alpha2``, ``peak_search``, …).

    Returns
    -------
    tuple[Pattern, list[Peak]]
        The processed pattern and the detected peak list.
    """
    return auto_process(pattern, config=kwargs or None)


def search_match(
    exp_peaks: list[Peak],
    conn: sqlite3.Connection,
    wavelength: float,
    **kwargs: Any,
) -> list[CandidateResult]:
    """Run a full peak-based search-match.

    See :func:`xinmatch.core.search.search_match`.
    """
    return _search_match(exp_peaks, conn, wavelength, **kwargs)


def quantify(
    pattern_intensity_by_phase: dict[str, float],
    rir_values: dict[str, float],
    **kwargs: Any,
) -> dict[str, float]:
    """Compute weight fractions via the RIR method.

    See :func:`xinmatch.core.quant.rir.rir_quantify`.
    """
    return rir_quantify(pattern_intensity_by_phase, rir_values, **kwargs)


def generate_report(
    report: Report,
    fmt: str = "html",
    output_path: str | Path | None = None,
) -> str:
    """Render a :class:`Report` to a string (and optionally to disk).

    Parameters
    ----------
    report:
        The report to render.
    fmt:
        Output format: ``"html"`` (default), ``"text"``, or ``"md"``.
    output_path:
        When given, the rendered string is also written to this path.

    Returns
    -------
    str
        The rendered report content.
    """
    fmt = fmt.lower()
    if fmt == "text":
        content = render_text(report)
    elif fmt in ("md", "markdown"):
        content = render_markdown(report)
    else:
        content = render_html(report)

    if output_path is not None:
        Path(output_path).write_text(content, encoding="utf-8")
    return content


# ---------------------------------------------------------------------------
# High-level pipeline helpers
# ---------------------------------------------------------------------------
def load_and_preprocess(path: str | Path, **kwargs: Any) -> Pattern:
    """Import a pattern file and run the auto processing pipeline.

    Convenience wrapper around :func:`load_pattern` + :func:`preprocess`.
    *kwargs* are forwarded to the pipeline config.

    Returns
    -------
    Pattern
        The processed diffraction pattern.
    """
    pattern = _load_pattern(path)
    processed, _peaks = auto_process(pattern, config=kwargs or None)
    return processed


def identify_phase(
    pattern: Pattern,
    db_path: str | Path,
    *,
    restraints: Restraints | None = None,
    top_n: int = 20,
) -> list[CandidateResult]:
    """Run search-match against a reference database.

    The pattern is auto-processed (smoothing → background → Kα2 strip →
    peak search) to obtain the experimental peak list, which is then
    matched against the SQLite database at *db_path*.

    Parameters
    ----------
    pattern:
        The (raw or processed) diffraction pattern.
    db_path:
        Path to the reference ``.db`` file.
    restraints:
        Optional :class:`Restraints` for pre-search filtering.
    top_n:
        Maximum number of ranked candidates to return.

    Returns
    -------
    list[CandidateResult]
        FoM-ranked candidates, length ``<= top_n``.
    """
    _processed, peaks = auto_process(pattern)
    if not peaks:
        return []

    conn = sqlite3.connect(str(db_path))
    try:
        return _search_match(
            peaks,
            conn,
            pattern.wavelength,
            restraints=restraints,
            top_n=top_n,
        )
    finally:
        conn.close()


def full_analysis(
    pattern_file: str | Path,
    db_path: str | Path,
    *,
    output_report: str | Path | None = None,
    top_n: int = 20,
) -> dict[str, Any]:
    """Run the full one-shot analysis pipeline.

    Steps: load pattern → auto process → search-match → (optional)
    report rendering.

    Quantification is performed with the top-ranked candidate as the
    sole phase and a unit RIR, which gives a baseline weight fraction
    of 1.0.  For multi-phase quantification call :func:`quantify`
    directly with explicit per-phase intensities and RIR values.

    Parameters
    ----------
    pattern_file:
        Path to the diffraction data file.
    db_path:
        Path to the reference ``.db`` file.
    output_report:
        Optional path to write the rendered report.  The format is
        inferred from the suffix (``.html`` / ``.txt`` / ``.md``).
    top_n:
        Number of search-match candidates to retain.

    Returns
    -------
    dict
        A result dictionary with keys ``pattern_file``, ``db_path``,
        ``n_peaks``, ``n_candidates``, ``candidates`` (list of
        ``{entry_id, formula, name, fom}``), ``weight_fractions``,
        ``report`` (the :class:`Report` object), and ``report_file``
        when *output_report* was given.
    """
    pattern = _load_pattern(pattern_file)
    processed, peaks = auto_process(pattern)

    conn = sqlite3.connect(str(db_path))
    try:
        candidates = _search_match(
            peaks,
            conn,
            pattern.wavelength,
            top_n=top_n,
        )
    finally:
        conn.close()

    # --- Quantification (single top-candidate baseline) -------------
    weight_fractions: dict[str, float] = {}
    if candidates:
        top = candidates[0]
        phase_name = top.entry.mineral_name or top.entry.formula or top.entry.entry_id
        # Use the strongest experimental peak intensity as the main-peak
        # intensity; RIR defaults to 1.0 → weight fraction = 1.0.
        main_intensity = max((p.intensity for p in peaks), default=0.0)
        if main_intensity > 0:
            weight_fractions = rir_quantify({phase_name: main_intensity}, {phase_name: 1.0})

    # --- Build the report -------------------------------------------
    sample_info = SampleInfo(
        sample_name=Path(pattern_file).stem,
        wavelength=pattern.wavelength,
    )
    peak_section = PeakListSection(peaks=peaks)
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
        peak_list=peak_section,
        candidate_list=cand_section,
    )
    report.quant_result.weight_fractions = dict(weight_fractions)

    result: dict[str, Any] = {
        "pattern_file": str(pattern_file),
        "db_path": str(db_path),
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
        "weight_fractions": dict(weight_fractions),
        "report": report,
    }

    if output_report is not None:
        out = Path(output_report)
        suffix = out.suffix.lstrip(".").lower()
        if suffix in ("md", "markdown"):
            out.write_text(render_markdown(report), encoding="utf-8")
        elif suffix in ("txt", "text"):
            out.write_text(render_text(report), encoding="utf-8")
        else:
            out.write_text(render_html(report), encoding="utf-8")
        result["report_file"] = str(output_report)

    return result
