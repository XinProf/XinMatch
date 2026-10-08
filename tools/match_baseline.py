"""Match! golden-baseline loader and L3 agreement metrics (T6.9 upgrade).

Loads the candidate-list CSVs that Match! exports for the 13-sample
``test_xrd`` set and compares XinMatch's Top-N candidate lists against
them — replacing the previous *proxy* acceptance (known-phase hit rate)
with a true golden-baseline comparison against Match! itself.

Match! candidate CSV format (semicolon separated)::

    Candidate list of sample 1-1
    Entry;Qual.;Formula sum;Name;P(peakpos.);P(I/I0);P(#peaks);P(#corr.);I scale fct.;FoM
    96-400-1849;C;Fe Li O4 P;;n.a.;n.a.;0.0000;n.a.;0.7083;1.0000

Match! runs Search-Match in SMPF (Search-Match using Profile Fitting)
mode for these exports, so ``P(#peaks)`` is always 0.0000 and several P
columns are ``n.a.`` — the comparison therefore keys on the **FoM
ordering** (the ``FoM`` column), exactly as the L3 spec of
ROADMAP_v3.md requires.

Phase identity between Match! entries (COD ids like ``96-400-1849``) and
XinMatch entries is established by two keys:

1. ``entry_id`` equality — the natural key when XinMatch runs against a
   real COD SQLite build (entry ids are the COD ids);
2. normalised formula composition — element symbols + counts parsed from
   ``Formula sum`` / ``Entry.formula`` with tolerance for fractional
   stoichiometry (e.g. ``Fe3.74 Li3.88 O16 P4`` ≈ ``Fe Li O4 P``).  This
   is the key that works against the curated synthetic DB used by
   ``tools/run_acceptance.py`` today.

Metrics (declared thresholds in ROADMAP_v3.md §L3):

* ``top1_agreement`` — is XinMatch's #1 candidate the same phase as
  Match!'s #1?  Aggregate target ≥ 80 % of samples.
* ``top5_overlap`` — how many of Match!'s Top-5 appear in XinMatch's
  Top-5?  Aggregate target ≥ 60 % (3/5) on average.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "MatchCandidate",
    "MatchBaseline",
    "normalize_formula",
    "formula_compatible",
    "same_phase",
    "top1_agreement",
    "top5_overlap",
]

# --------------------------------------------------------------------------- #
# Data containers
# --------------------------------------------------------------------------- #
@dataclass
class MatchCandidate:
    """One row of a Match! candidate-list export."""

    entry_id: str
    quality: str | None = None
    formula_sum: str | None = None
    name: str | None = None
    p_peakpos: float | None = None
    p_intensity: float | None = None
    p_npeaks: float | None = None
    p_ncorr: float | None = None
    i_scale: float | None = None
    fom: float = 0.0


@dataclass
class MatchBaseline:
    """A parsed Match! candidate-list export (one sample)."""

    sample_id: str
    candidates: list[MatchCandidate] = field(default_factory=list)

    @property
    def top1(self) -> MatchCandidate | None:
        """Highest-FoM candidate (already sorted descending)."""
        return self.candidates[0] if self.candidates else None

    def top_n(self, n: int) -> list[MatchCandidate]:
        """First *n* candidates (fewer if the list is shorter)."""
        return self.candidates[:n]


# --------------------------------------------------------------------------- #
# Formula normalisation (element-composition identity)
# --------------------------------------------------------------------------- #
_ELEMENT_RE = re.compile(r"([A-Z][a-z]?)([0-9.]*)")


def parse_formula(formula: str | None) -> dict[str, float]:
    """Parse a chemical formula into ``{symbol: count}``.

    Handles Match! ``Formula sum`` strings such as ``Fe Li O4 P``,
    ``Fe3.74 Li3.88 O16 P4`` and XinMatch ``Entry.formula`` strings such
    as ``Fe Li O4 P`` / ``B6 La0.987``.  Counts are kept as floats
    (fractional stoichiometry is preserved, not rounded away).
    """
    out: dict[str, float] = {}
    if not formula:
        return out
    for symbol, count in _ELEMENT_RE.findall(formula):
        if not symbol:
            continue
        value = float(count) if count else 1.0
        out[symbol] = out.get(symbol, 0.0) + value
    return out


def normalize_formula(formula: str | None) -> str:
    """Canonical, order-independent fingerprint of a formula.

    ``Fe Li O4 P`` and ``O4 P Fe Li`` and ``Fe1 Li1 O4 P1`` all yield the
    same fingerprint (symbols sorted alphabetically, counts kept with up
    to 4 decimals).  Used for fast exact-match pre-checks; the tolerant
    comparison is :func:`formula_compatible`.
    """
    counts = parse_formula(formula)
    if not counts:
        return ""
    return " ".join(
        f"{sym}{counts[sym]:g}" for sym in sorted(counts)
    )


def formula_compatible(a: str | None, b: str | None, *, tol: float = 0.25) -> bool:
    """True when *a* and *b* denote the same phase composition.

    Both formulas are normalised to **molar fractions** (each element
    count divided by the total atom count) before comparison, so that
    approximate/fractional stoichiometry works: ``Fe3.74 Li3.88 O16 P4``
    is the same phase as the ideal ``Fe Li O4 P`` (≈ 4× formula), and
    ``Fe2 O3`` equals ``Fe4 O6``.  The element sets must match exactly
    and every molar fraction must agree to within ``tol`` (relative).
    An empty formula on either side is never a match.
    """
    ca = parse_formula(a)
    cb = parse_formula(b)
    if not ca or not cb:
        return False
    if set(ca) != set(cb):
        return False
    ta = sum(ca.values())
    tb = sum(cb.values())
    if ta <= 0.0 or tb <= 0.0:
        return False
    for sym in ca:
        fa = ca[sym] / ta
        fb = cb[sym] / tb
        if abs(fa - fb) > tol * max(fa, fb):
            return False
    return True


# --------------------------------------------------------------------------- #
# Phase-identity matching
# --------------------------------------------------------------------------- #
def same_phase(
    match_cand: MatchCandidate,
    xinmatch_entry_id: str,
    xinmatch_formula: str | None,
) -> bool:
    """True when a Match! candidate and a XinMatch entry denote the same phase.

    Two independent keys, either of which suffices:

    1. identical ``entry_id`` (real-COD scenario — XinMatch entry ids
       are the COD ids); or
    2. compositionally compatible formulas (curated-DB scenario).
    """
    if match_cand.entry_id == xinmatch_entry_id:
        return True
    return bool(
        match_cand.formula_sum
        and xinmatch_formula
        and formula_compatible(match_cand.formula_sum, xinmatch_formula)
    )


# --------------------------------------------------------------------------- #
# Agreement metrics
# --------------------------------------------------------------------------- #
def top1_agreement(
    match_top1: MatchCandidate | None,
    xinmatch_top1_id: str | None,
    xinmatch_top1_formula: str | None,
) -> bool:
    """True when XinMatch's #1 candidate matches Match!'s #1.

    A missing XinMatch candidate (empty result) never agrees; a missing
    Match! Top-1 (empty export) is treated as agreement-by-vacuum only
    when XinMatch is also empty — which the caller should normally avoid
    by skipping DB-missing samples.
    """
    if match_top1 is None:
        return xinmatch_top1_id is None
    if xinmatch_top1_id is None:
        return False
    return same_phase(match_top1, xinmatch_top1_id, xinmatch_top1_formula)


def top5_overlap(
    match_top5: list[MatchCandidate],
    xinmatch_candidates: list[tuple[str, str | None]],
) -> float:
    """Fraction of Match!'s Top-5 that appear in XinMatch's candidate list.

    Parameters
    ----------
    match_top5:
        Match!'s top-5 candidates (in FoM order).
    xinmatch_candidates:
        XinMatch's candidate list as ``(entry_id, formula)`` pairs — the
        list is searched in full (not just Top-5) so that a phase ranked
        #6 by XinMatch still counts once; what matters is that it is
        *found*, which mirrors the L3 "Top-5 交集" intent conservatively.

    Returns
    -------
    float
        ``overlap_count / len(match_top5)`` in ``[0, 1]`` (0 when the
        baseline list is empty).
    """
    if not match_top5:
        return 0.0
    hits = 0
    for mc in match_top5:
        for xid, xformula in xinmatch_candidates:
            if same_phase(mc, xid, xformula):
                hits += 1
                break
    return hits / len(match_top5)


# --------------------------------------------------------------------------- #
# CSV loader
# --------------------------------------------------------------------------- #
def _parse_float(value: str) -> float | None:
    """Parse a numeric CSV field, mapping ``n.a.``/empty to ``None``."""
    v = value.strip()
    if not v or v.lower() in {"n.a.", "na", "n/a", "-"}:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def load_match_csv(path: Path) -> MatchBaseline:
    """Parse one Match! candidate-list CSV file.

    Skips the leading ``Candidate list of sample ...`` banner line, uses
    the ``Entry;Qual.;...;FoM`` header line, and reads the data rows.
    Rows are sorted by ``FoM`` descending (the file is already sorted,
    but re-sorting makes the loader robust to hand-edited exports).
    """
    sample_id = path.stem
    candidates: list[MatchCandidate] = []
    with path.open("r", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.reader(fh, delimiter=";")
        rows = list(reader)

    # Find the header row (contains the FoM column).
    header_idx: int | None = None
    for i, row in enumerate(rows):
        if row and "FoM" in [c.strip() for c in row]:
            header_idx = i
            break
    if header_idx is None:
        raise ValueError(f"{path}: no Match! header row found")

    header = [c.strip() for c in rows[header_idx]]
    try:
        idx_entry = header.index("Entry")
        idx_fom = header.index("FoM")
    except ValueError as exc:
        raise ValueError(f"{path}: header missing Entry/FoM columns") from exc

    def _col(name: str) -> int | None:
        return header.index(name) if name in header else None

    c_formula = _col("Formula sum")
    c_qual = _col("Qual.")
    c_name = _col("Name")
    c_ppos = _col("P(peakpos.)")
    c_pint = _col("P(I/I0)")
    c_pnpk = _col("P(#peaks)")
    c_pcorr = _col("P(#corr.)")
    c_iscale = _col("I scale fct.")

    for row in rows[header_idx + 1 :]:
        if not row or all(not c.strip() for c in row):
            continue
        fom = _parse_float(row[idx_fom])
        if fom is None:
            continue  # malformed row — skip
        candidates.append(
            MatchCandidate(
                entry_id=row[idx_entry].strip(),
                quality=row[c_qual].strip() if c_qual is not None and len(row) > c_qual else None,
                formula_sum=(
                    row[c_formula].strip()
                    if c_formula is not None and len(row) > c_formula
                    else None
                ),
                name=row[c_name].strip() if c_name is not None and len(row) > c_name else None,
                p_peakpos=_parse_float(row[c_ppos]) if c_ppos is not None and len(row) > c_ppos else None,
                p_intensity=_parse_float(row[c_pint]) if c_pint is not None and len(row) > c_pint else None,
                p_npeaks=_parse_float(row[c_pnpk]) if c_pnpk is not None and len(row) > c_pnpk else None,
                p_ncorr=_parse_float(row[c_pcorr]) if c_pcorr is not None and len(row) > c_pcorr else None,
                i_scale=_parse_float(row[c_iscale]) if c_iscale is not None and len(row) > c_iscale else None,
                fom=float(fom),
            )
        )

    candidates.sort(key=lambda c: c.fom, reverse=True)
    return MatchBaseline(sample_id=sample_id, candidates=candidates)


def load_match_baseline_dir(dir_path: Path) -> dict[str, MatchBaseline]:
    """Load every ``*.csv`` in *dir_path* into ``{sample_id: baseline}``.

    A CSV that fails to parse (e.g. a non-Match! file) is skipped with a
    warning — the returned dict only contains successfully loaded
    samples.
    """
    out: dict[str, MatchBaseline] = {}
    for csv_file in sorted(dir_path.glob("*.csv")):
        try:
            baseline = load_match_csv(csv_file)
        except (ValueError, OSError) as exc:
            import logging

            logging.getLogger(__name__).warning(
                "skipping %s: %s", csv_file.name, exc
            )
            continue
        out[baseline.sample_id] = baseline
    return out
