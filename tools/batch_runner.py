"""Config-driven batch search-match runner (T14.3).

Runs the full XinMatch pipeline for a *list* of samples described by a
JSON or YAML configuration file::

    load_pattern  →  auto_process  →  search_match  →  Report (HTML/MD/TXT)

This script is a thin orchestration layer: it calls the same :mod:`xinmatch.core`
APIs as ``xinmatch run`` (see :mod:`xinmatch.cli.main`) and implements no
algorithm of its own.

Usage
-----
::

    python tools/batch_runner.py config.yaml
    python tools/batch_runner.py config.json

Configuration schema
---------------------
.. code-block:: yaml

    # One entry per sample. ``path`` is required; ``name`` defaults to the
    # file stem; ``wavelength`` overrides the pattern's own wavelength.
    samples:
      - name: 1-1
        path: samples/1-1.txt
      - path: samples/2-1.xy
        wavelength: 1.5406

    # Optional: forwarded verbatim to auto_process() (see auto_pipeline
    # DEFAULT_CONFIG for all recognised keys).
    preprocess:
      smooth: true
      background: true
      strip_alpha2: false
      peak_sensitivity: medium

    # Reference-database search parameters.
    search:
      db: data/cod_inorganics.db      # required
      top_n: 20
      window_deg: 0.3
      # FoM weights override (all keys optional — missing keys keep the
      # the reference software defaults).
      weights:
        peakpos: 0.2275
        intensity: 0.1112
      # Optional: restraints dict (see Restraints.from_dict).

    output:
      dir: out/batch                   # per-sample reports land here
      formats: [html, md, txt]         # subset of html / md / txt
      summary: out/batch/batch_summary.md   # optional; default {dir}/...

Behaviour
---------
* Relative paths in the config (samples, db, output) are resolved against the
  **config file's directory** — the config is self-contained and portable.
* A single sample failing (missing file, unsupported format, search error)
  does **not** stop the batch: the error is recorded on that sample's result
  and the runner continues with the next sample.
* A machine-readable ``batch_summary.json`` is written next to the Markdown
  summary so downstream tools (acceptance reports, dashboards) can consume
  the results without parsing Markdown.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Allow ``python tools/batch_runner.py config.yaml`` to run directly from the
# project root without an editable install on sys.path.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from xinmatch.core.io import load_pattern
from xinmatch.core.model import Restraints
from xinmatch.core.preprocess.auto_pipeline import auto_process
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
from xinmatch.core.search.fom_criteria import FomWeights

__all__ = [
    "SampleResult",
    "BatchResult",
    "load_config",
    "run_sample",
    "run_batch",
    "write_summary",
    "main",
]

# Format name -> (render function, file extension).
_RENDERERS: dict[str, tuple[Any, str]] = {
    "html": (render_html, ".html"),
    "md": (render_markdown, ".md"),
    "markdown": (render_markdown, ".md"),
    "txt": (render_text, ".txt"),
    "text": (render_text, ".txt"),
}


# --------------------------------------------------------------------------- #
# Result containers
# --------------------------------------------------------------------------- #
@dataclass
class SampleResult:
    """Outcome of running the pipeline on one sample."""

    sample_name: str
    pattern_path: str
    n_peaks: int = 0
    n_candidates: int = 0
    top_entry_id: str | None = None
    top_formula: str | None = None
    top_name: str | None = None
    top_fom: float | None = None
    report_files: dict[str, str] = field(default_factory=dict)
    error: str | None = None

    @property
    def ok(self) -> bool:
        """True when the sample ran without errors."""
        return self.error is None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BatchResult:
    """Aggregated outcome of a batch run."""

    samples: list[SampleResult] = field(default_factory=list)
    output_dir: str = ""
    summary_path: str | None = None
    json_summary_path: str | None = None

    @property
    def n_ok(self) -> int:
        return sum(1 for s in self.samples if s.ok)

    @property
    def n_failed(self) -> int:
        return sum(1 for s in self.samples if not s.ok)

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_dir": self.output_dir,
            "summary_path": self.summary_path,
            "json_summary_path": self.json_summary_path,
            "n_ok": self.n_ok,
            "n_failed": self.n_failed,
            "samples": [s.to_dict() for s in self.samples],
        }


# --------------------------------------------------------------------------- #
# Configuration loading
# --------------------------------------------------------------------------- #
def load_config(path: str | Path) -> tuple[dict[str, Any], Path]:
    """Load a JSON or YAML batch configuration.

    The format is chosen by file extension (``.yaml``/``.yml`` → YAML,
    anything else → JSON).

    Returns
    -------
    tuple[dict, Path]
        ``(config_dict, config_directory)`` — the directory is used to
        resolve relative paths inside the config.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If the file is empty, has no parseable content, or YAML is
        requested but ``pyyaml`` is not installed.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"config not found: {p}")

    text = p.read_text(encoding="utf-8-sig")
    suffix = p.suffix.lower()

    if suffix in {".yaml", ".yml"}:
        try:
            import yaml  # noqa: PLC0415 — lazy import; pyyaml is optional at runtime
        except ImportError as exc:
            raise ValueError(
                "YAML config requested but pyyaml is not installed; "
                "install it or use a JSON config."
            ) from exc
        config = yaml.safe_load(text)
    else:
        config = json.loads(text)

    if not isinstance(config, dict):
        raise ValueError(f"config must be a mapping/object, got {type(config).__name__}")
    return config, p.parent


def _resolve(base_dir: Path, value: str | Path | None) -> Path | None:
    """Resolve *value* against *base_dir* unless it is already absolute."""
    if value is None:
        return None
    p = Path(value)
    if not p.is_absolute():
        p = base_dir / p
    return p


# --------------------------------------------------------------------------- #
# Per-sample pipeline
# --------------------------------------------------------------------------- #
def run_sample(
    sample_cfg: dict[str, Any],
    *,
    config_dir: Path,
    preprocess_cfg: dict[str, Any] | None,
    search_cfg: dict[str, Any],
    out_dir: Path,
    formats: list[str],
) -> SampleResult:
    """Run load → preprocess → search → report for one sample.

    Any exception raised along the way is caught and recorded on the
    returned :class:`SampleResult` (the caller decides how to aggregate).
    """
    rel_path = sample_cfg.get("path")
    if not rel_path:
        raise ValueError("sample entry is missing required key 'path'")

    pattern_path = _resolve(config_dir, str(rel_path))
    sample_name = str(sample_cfg.get("name") or Path(str(rel_path)).stem)
    result = SampleResult(sample_name=sample_name, pattern_path=str(pattern_path))

    # 1. Load the pattern (format auto-detected by core/io).
    pattern = load_pattern(pattern_path)
    wavelength = sample_cfg.get("wavelength")
    if wavelength is not None:
        pattern.wavelength = float(wavelength)

    # 2. Automatic preprocessing pipeline.
    _processed, peaks = auto_process(pattern, config=preprocess_cfg)
    result.n_peaks = len(peaks)

    # 3. Search-match against the reference DB (per-sample connection keeps
    #    one bad sample from poisoning the shared connection).
    db_path = _resolve(config_dir, str(search_cfg["db"]))
    weights_raw = search_cfg.get("weights")
    weights = FomWeights(**weights_raw) if isinstance(weights_raw, dict) else None

    restraints_raw = search_cfg.get("restraints")
    restraints = (
        Restraints.from_dict(restraints_raw)
        if isinstance(restraints_raw, dict)
        else None
    )

    conn = sqlite3.connect(str(db_path))
    try:
        candidates = search_match(
            peaks,
            conn,
            pattern.wavelength,
            restraints=restraints,
            weights=weights,
            window_deg=float(search_cfg.get("window_deg", 0.3)),
            top_n=int(search_cfg.get("top_n", 20)),
        )
    finally:
        conn.close()

    result.n_candidates = len(candidates)
    if candidates:
        top = candidates[0]
        result.top_entry_id = top.entry.entry_id
        result.top_formula = top.entry.formula or None
        result.top_name = top.entry.mineral_name or None
        result.top_fom = float(top.fom)

    # 4. Build the report model and render every requested format.
    sample_info = SampleInfo(
        sample_name=sample_name,
        wavelength=pattern.wavelength,
    )
    cand_section = CandidateListSection(
        candidates=[
            CandidateEntry(
                entry_id=c.entry.entry_id,
                formula=c.entry.formula or "",
                name=c.entry.mineral_name or "",
                fom=float(c.fom),
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

    out_dir.mkdir(parents=True, exist_ok=True)
    for fmt in formats:
        renderer, ext = _RENDERERS[fmt]
        out_path = out_dir / f"{sample_name}{ext}"
        out_path.write_text(renderer(report), encoding="utf-8")
        result.report_files[fmt] = str(out_path)

    return result


# --------------------------------------------------------------------------- #
# Batch runner
# --------------------------------------------------------------------------- #
def _validate_config(config: dict[str, Any]) -> None:
    """Raise ValueError for structurally invalid configs (before any I/O)."""
    samples = config.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("config must define a non-empty 'samples' list")
    search_cfg = config.get("search")
    if not isinstance(search_cfg, dict) or not search_cfg.get("db"):
        raise ValueError("config['search']['db'] (reference .db path) is required")


def run_batch(config: dict[str, Any], config_dir: Path | None = None) -> BatchResult:
    """Run the pipeline for every sample in *config*.

    Parameters
    ----------
    config:
        Parsed configuration (see module docstring for the schema).
    config_dir:
        Directory relative to which config-relative paths are resolved.
        Defaults to the current working directory (use this when the
        config was loaded via :func:`load_config` to keep the config
        portable).
    """
    _validate_config(config)
    base_dir = config_dir or Path.cwd()

    search_cfg = config.get("search", {})
    preprocess_cfg = config.get("preprocess") or None

    output_cfg = config.get("output") or {}
    out_dir = _resolve(base_dir, str(output_cfg.get("dir", "batch_out")))
    assert out_dir is not None  # for type checkers; str() never yields None
    formats_raw = output_cfg.get("formats", ["html"])
    formats: list[str] = []
    for fmt in formats_raw:
        key = str(fmt).lower()
        if key not in _RENDERERS:
            raise ValueError(
                f"unknown report format {fmt!r}; choose from html, md, txt"
            )
        # Normalise aliases ("markdown" -> "md", "text" -> "txt") so the
        # on-disk extension in the summary stays canonical.
        formats.append("md" if key == "markdown" else "txt" if key == "text" else key)

    batch = BatchResult(output_dir=str(out_dir))

    for sample_cfg in config["samples"]:
        name = sample_cfg.get("name") or Path(str(sample_cfg.get("path", "?"))).stem
        print(f"[{name}] running ...", flush=True)
        try:
            result = run_sample(
                sample_cfg,
                config_dir=base_dir,
                preprocess_cfg=preprocess_cfg,
                search_cfg=search_cfg,
                out_dir=out_dir,
                formats=formats,
            )
        except Exception as exc:  # noqa: BLE001 — per-sample error boundary
            result = SampleResult(
                sample_name=str(name),
                pattern_path=str(sample_cfg.get("path", "")),
                error=f"{type(exc).__name__}: {exc}",
            )

        batch.samples.append(result)
        if result.ok:
            top = (
                f"{result.top_entry_id} ({result.top_formula}) "
                f"FoM={result.top_fom:.4f}"
                if result.top_entry_id
                else "no candidates"
            )
            print(
                f"[{result.sample_name}] OK: {result.n_peaks} peaks, "
                f"{result.n_candidates} candidates, top: {top}",
                flush=True,
            )
        else:
            print(f"[{result.sample_name}] FAILED: {result.error}", flush=True)

    # Summary artefacts.  An explicit ``output.summary`` is resolved against
    # the config dir; by default the summary lands *inside* the output dir.
    summary_rel = output_cfg.get("summary")
    summary_path = (
        _resolve(config_dir, str(summary_rel))
        if summary_rel is not None
        else out_dir / "batch_summary.md"
    )
    if summary_path is not None:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        batch.summary_path = str(summary_path)
        batch.json_summary_path = str(summary_path.with_suffix(".json"))
        write_summary(batch, summary_path)

    return batch


# --------------------------------------------------------------------------- #
# Summary writers
# --------------------------------------------------------------------------- #
def _fmt_fom(v: float | None) -> str:
    return f"{v:.4f}" if v is not None else "—"


def write_summary(batch: BatchResult, path: Path) -> None:
    """Write the batch summary as Markdown and a sidecar JSON file."""
    lines = [
        "# XinMatch Batch Run Summary",
        "",
        f"- samples: {len(batch.samples)}  (ok: {batch.n_ok}, failed: {batch.n_failed})",
        f"- output dir: `{batch.output_dir}`",
        "",
        "| Sample | Peaks | Top entry | Formula | Name | FoM | Status |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in batch.samples:
        status = "OK" if s.ok else f"ERROR: {s.error}"
        lines.append(
            f"| {s.sample_name} | {s.n_peaks} | "
            f"{s.top_entry_id or '—'} | {s.top_formula or '—'} | "
            f"{s.top_name or '—'} | {_fmt_fom(s.top_fom)} | {status} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if batch.json_summary_path is not None:
        Path(batch.json_summary_path).write_text(
            json.dumps(batch.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``python tools/batch_runner.py config.yaml``."""
    parser = argparse.ArgumentParser(
        description="Batch XinMatch search-match driven by a JSON/YAML config.",
    )
    parser.add_argument("config", help="Path to the batch config (.yaml/.yml/.json).")
    args = parser.parse_args(argv)

    try:
        config, config_dir = load_config(args.config)
        batch = run_batch(config, config_dir=config_dir)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print("")
    print(
        f"Batch finished: {batch.n_ok} ok, {batch.n_failed} failed "
        f"(total {len(batch.samples)})."
    )
    if batch.summary_path:
        print(f"Summary: {batch.summary_path}")
    return 0 if batch.n_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
