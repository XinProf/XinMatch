"""Convert human-exported Match! candidate-list CSVs into the canonical
baseline layout (T0.3 / T0.4).

Background
----------
The L3 golden baseline needs 20-30 standard samples.  The candidate lists
themselves **must** be produced by a human running Search-Match inside
Match! (this script never fabricates them).  What it does is normalise the
raw exports so that :func:`tools.match_baseline.load_match_csv` can read
every sample the same way:

* encoding sniffed (UTF-8 with/without BOM, then Windows-1252);
* delimiter sniffed (``;`` European default, fallback ``,``);
* European decimal commas (``0,7083``) normalised to dots (``0.7083``);
* the canonical 10-column header enforced and missing optional columns
  filled with empty / ``n.a.``;
* rows sorted by FoM descending;
* rows lacking an ``Entry`` or a parseable ``FoM`` are **reported** (line
  number + reason), not silently dropped.

The canonical output is exactly the format documented in
:mod:`tools.match_baseline`::

    Candidate list of sample <sample_id>
    Entry;Qual.;Formula sum;Name;P(peakpos.);P(I/I0);P(#peaks);P(#corr.);I scale fct.;FoM
    96-400-1849;C;Fe Li O4 P;Lithium Iron Phosphate(V);0.0098;n.a.;0.0000;n.a.;0.7128;0.8585

Usage
-----
::

    # Convert one hand-exported CSV:
    python tools/import_match_baseline.py "D:\\...\\1-1.csv"

    # Convert a whole folder of hand exports into tests/baseline/match/:
    python tools/import_match_baseline.py "D:\\Project\\XRD\\test_xrd\\match-candidate list-jingzhun"
    python tools/import_match_baseline.py <dir-or-csv> -o tests/baseline/match

After conversion, verify the baseline loads with::

    python -c "from pathlib import Path; from tools.match_baseline import load_match_baseline_dir; \\
    import json; print(json.dumps({k: len(v.candidates) for k, v in load_match_baseline_dir(Path('tests/baseline/match')).items()}, indent=1))"
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Allow ``python tools/import_match_baseline.py`` to run directly from the
# project root without an editable install on sys.path.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.match_baseline import load_match_csv  # re-use for the round-trip check

__all__ = [
    "CANONICAL_HEADER",
    "ConversionResult",
    "ConversionReport",
    "convert_file",
    "convert_dir",
    "main",
]

#: The exact header that :func:`tools.match_baseline.load_match_csv` expects.
CANONICAL_HEADER: tuple[str, ...] = (
    "Entry",
    "Qual.",
    "Formula sum",
    "Name",
    "P(peakpos.)",
    "P(I/I0)",
    "P(#peaks)",
    "P(#corr.)",
    "I scale fct.",
    "FoM",
)

#: Tolerated aliases for raw headers (Match! version/export-option drift).
_HEADER_ALIASES: dict[str, str] = {
    "entry": "Entry",
    "qual": "Qual.",
    "qual.": "Qual.",
    "formula sum": "Formula sum",
    "name": "Name",
    "p(peakpos.)": "P(peakpos.)",
    "p(i/i0)": "P(I/I0)",
    "p(#peaks)": "P(#peaks)",
    "p(#corr.)": "P(#corr.)",
    "i scale fct": "I scale fct.",
    "i scale fct.": "I scale fct.",
    "fom": "FoM",
}

_NUMERIC_CELL_RE = re.compile(r"^[+-]?(\d+,\d+|\d+\.\d+|\d+)$")


# --------------------------------------------------------------------------- #
# Result containers
# --------------------------------------------------------------------------- #
@dataclass
class RowRejection:
    """A data row that could not be converted."""

    line_no: int
    reason: str
    raw: str


@dataclass
class ConversionResult:
    """Outcome of converting one raw CSV file."""

    sample_id: str
    source: Path
    output: Path | None = None
    n_rows_written: int = 0
    rejected: list[RowRejection] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.output is not None and self.n_rows_written > 0


@dataclass
class ConversionReport:
    """Aggregated outcome of a directory conversion."""

    results: list[ConversionResult] = field(default_factory=list)

    @property
    def n_files(self) -> int:
        return len(self.results)

    @property
    def n_rows(self) -> int:
        return sum(r.n_rows_written for r in self.results)

    @property
    def n_rejected(self) -> int:
        return sum(len(r.rejected) for r in self.results)


# --------------------------------------------------------------------------- #
# Raw parsing helpers
# --------------------------------------------------------------------------- #
def _read_text_snapped(path: Path) -> str:
    """Read *path* trying UTF-8-sig first, then Windows-1252."""
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _sniff_delimiter(sample_lines: list[str]) -> str:
    """Pick ``;`` when any header-looking line contains it, else ``,``."""
    for line in sample_lines[:20]:
        if ";" in line:
            return ";"
    return ","


def _norm_numeric(cell: str) -> str:
    """Normalise a numeric cell: European decimal comma → dot.

    Non-numeric text (formulas, names, ``n.a.``) is returned unchanged.
    """
    c = cell.strip()
    if _NUMERIC_CELL_RE.match(c):
        return c.replace(",", ".")
    return cell


def _parse_raw(path: Path) -> tuple[list[dict[str, str]], list[RowRejection], str]:
    """Parse a raw Match! export into canonical-column dicts.

    Returns
    -------
    tuple[list[dict], list[RowRejection], str]
        Valid rows keyed by canonical column name, rejected rows, and the
        delimiter actually used.
    """
    text = _read_text_snapped(path)
    lines = text.splitlines()
    delim = _sniff_delimiter(lines)
    rows = list(csv.reader(lines, delimiter=delim))

    # Locate the header row (must carry Entry + FoM under an alias).
    header_idx: int | None = None
    header_map: dict[int, str] = {}
    for i, row in enumerate(rows):
        norm = [c.strip() for c in row]
        mapped = {idx: _HEADER_ALIASES.get(cell.lower())
                  for idx, cell in enumerate(norm) if cell}
        targets = set(mapped.values())
        if "Entry" in targets and "FoM" in targets:
            header_idx = i
            header_map = mapped
            break

    if header_idx is None:
        raise ValueError(f"{path}: no header row with Entry + FoM found")

    valid: list[dict[str, str]] = []
    rejected: list[RowRejection] = []

    for row_no, row in enumerate(rows[header_idx + 1 :], start=header_idx + 2):
        if not row or all(not c.strip() for c in row):
            continue
        padded = row + [""] * (len(header_map) - len(row))
        record = {col: "" for col in CANONICAL_HEADER}
        for idx, col in header_map.items():
            if col is None:
                continue
            cell = padded[idx].strip() if idx < len(padded) else ""
            # P-value / numeric columns get decimal-comma normalisation;
            # text columns (Entry/Qual/Formula/Name) are kept verbatim.
            if col != "Entry" and col != "Qual." and col != "Formula sum" and col != "Name":
                cell = _norm_numeric(cell)
            record[col] = cell

        entry = record["Entry"].strip()
        fom_raw = record["FoM"].strip()
        if not entry:
            rejected.append(RowRejection(row_no, "empty Entry", delim.join(row)))
            continue
        try:
            fom = float(fom_raw.replace(",", ".")) if fom_raw else float("nan")
        except ValueError:
            rejected.append(
                RowRejection(row_no, f"unparseable FoM {fom_raw!r}", delim.join(row))
            )
            continue
        if fom != fom:  # NaN
            rejected.append(RowRejection(row_no, "missing FoM", delim.join(row)))
            continue
        record["_fom"] = fom  # scratch field for sorting
        valid.append(record)

    return valid, rejected, delim


def _fmt_p(value: str) -> str:
    """Format one P-value cell: ``n.a.`` when missing/empty else 4dp."""
    v = value.strip()
    if not v or v.lower() in {"n.a.", "na", "n/a", "-"}:
        return "n.a."
    try:
        return f"{float(v):.4f}"
    except ValueError:
        return "n.a."


# --------------------------------------------------------------------------- #
# Public conversion API
# --------------------------------------------------------------------------- #
def convert_file(
    in_path: str | Path,
    out_path: str | Path | None = None,
    *,
    sample_id: str | None = None,
) -> ConversionResult:
    """Convert one raw Match! candidate CSV into the canonical layout.

    Parameters
    ----------
    in_path:
        Raw CSV exported by Match!.
    out_path:
        Destination file.  Defaults to
        ``tests/baseline/match/<stem>.csv`` relative to the current
        working directory.
    sample_id:
        Override the sample id (defaults to the input file stem).

    Returns
    -------
    ConversionResult
    """
    in_p = Path(in_path)
    sid = sample_id or in_p.stem
    result = ConversionResult(sample_id=sid, source=in_p)

    valid, rejected, _delim = _parse_raw(in_p)
    result.rejected = rejected

    # Sort by FoM descending (loader re-sorts too; we write it already sorted).
    valid.sort(key=lambda r: r["_fom"], reverse=True)

    out_p = Path(out_path) if out_path is not None else Path("tests/baseline/match") / f"{sid}.csv"
    out_p.parent.mkdir(parents=True, exist_ok=True)

    lines = [f"Candidate list of sample {sid}", ";".join(CANONICAL_HEADER)]
    for rec in valid:
        cells = [
            rec["Entry"],
            rec["Qual."],
            rec["Formula sum"],
            rec["Name"],
            _fmt_p(rec["P(peakpos.)"]),
            _fmt_p(rec["P(I/I0)"]),
            _fmt_p(rec["P(#peaks)"]),
            _fmt_p(rec["P(#corr.)"]),
            _fmt_p(rec["I scale fct."]),
            f"{rec['_fom']:.4f}",
        ]
        lines.append(";".join(cells))

    out_p.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    result.output = out_p
    result.n_rows_written = len(valid)
    return result


def convert_dir(
    in_dir: str | Path,
    out_dir: str | Path = "tests/baseline/match",
) -> ConversionReport:
    """Convert every ``*.csv`` in *in_dir* into *out_dir*."""
    src = Path(in_dir)
    dst = Path(out_dir)
    report = ConversionReport()
    for csv_file in sorted(src.glob("*.csv")):
        res = convert_file(csv_file, dst / f"{csv_file.stem}.csv")
        report.results.append(res)
    return report


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``python tools/import_match_baseline.py <csv-or-dir>``."""
    parser = argparse.ArgumentParser(
        description="Normalise Match! candidate-list exports into tests/baseline/match/.",
    )
    parser.add_argument(
        "input",
        help="Raw Match! candidate-list CSV, or a directory of such CSVs.",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default="tests/baseline/match",
        help="Output directory for canonical CSVs (default: tests/baseline/match).",
    )
    args = parser.parse_args(argv)

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"error: {in_path} does not exist", file=sys.stderr)
        return 2

    if in_path.is_dir():
        report = convert_dir(in_path, args.output_dir)
        for res in report.results:
            status = "OK" if res.ok else "EMPTY"
            print(
                f"[{status}] {res.sample_id}: {res.n_rows_written} rows written "
                f"-> {res.output}"
            )
            for rej in res.rejected:
                print(f"    rejected line {rej.line_no}: {rej.reason}")
        print("")
        print(
            f"Converted {report.n_files} file(s): {report.n_rows} rows, "
            f"{report.n_rejected} rejected."
        )
        # Round-trip sanity check against the production loader.
        from tools.match_baseline import load_match_baseline_dir

        loaded = load_match_baseline_dir(Path(args.output_dir))
        print(f"Loader check: {len(loaded)} sample(s) loadable from {args.output_dir}.")
        return 0 if report.n_files else 1

    result = convert_file(in_path, Path(args.output_dir) / f"{in_path.stem}.csv")
    print(f"[{'OK' if result.ok else 'EMPTY'}] {result.sample_id}: {result.n_rows_written} rows -> {result.output}")
    for rej in result.rejected:
        print(f"    rejected line {rej.line_no}: {rej.reason}")
    # Round-trip sanity check.
    loaded = load_match_csv(result.output)
    print(f"Loader check: {len(loaded.candidates)} candidates parsed back.")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
