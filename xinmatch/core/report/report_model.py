"""Report data model for XinMatch (T12.1).

Defines the structured data containers that mirror the chapters of a
Match! phase-analysis report (see ``docs/report_basics.md`` and
``docs/report_options.md``):

* :class:`SampleInfo`           — sample / instrument metadata header
* :class:`CandidateEntry`      — lightweight candidate-phase row
* :class:`PeakListSection`     — experimental peak list
* :class:`CandidateListSection` — candidate phase list
* :class:`SelectedPhasesSection` — phases selected as matching
* :class:`QuantResultSection`  — RIR / Rietveld weight fractions
* :class:`RFactorSection`      — profile agreement factors (Rwp, Rp, …)
* :class:`Report`              — top-level container with JSON I/O

The data model is intentionally **GUI-free** and uses only dataclasses,
the standard library, and the existing :mod:`xinmatch.core.model` types.
File I/O (``to_json`` / ``from_json``) is permitted at this layer — the
"algorithm layer does not read/write files" constraint applies to the
search/quant/refine engines, not to the report layer.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from xinmatch.core.model import Peak, Phase


# ---------------------------------------------------------------------------
# Section dataclasses
# ---------------------------------------------------------------------------
@dataclass
class SampleInfo:
    """Sample / instrument metadata header (Match! *Sample data* chapter).

    Parameters
    ----------
    sample_name:
        Free-form sample label.
    operator:
        Operator name.
    date:
        Collection date (ISO string, e.g. ``"2026-10-07"``).
    instrument:
        Diffractometer identifier.
    wavelength:
        Radiation wavelength in Å.
    sample_preparation:
        Free-form preparation notes.
    comments:
        Free-form additional comments.
    """

    sample_name: str = ""
    operator: str = ""
    date: str = ""
    instrument: str = ""
    wavelength: float | None = None
    sample_preparation: str = ""
    comments: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SampleInfo:
        return cls(
            sample_name=str(d.get("sample_name", "")),
            operator=str(d.get("operator", "")),
            date=str(d.get("date", "")),
            instrument=str(d.get("instrument", "")),
            wavelength=d.get("wavelength"),
            sample_preparation=str(d.get("sample_preparation", "")),
            comments=str(d.get("comments", "")),
        )


@dataclass
class CandidateEntry:
    """Lightweight candidate-phase row.

    The full :mod:`xinmatch.core.search` candidate result is not always
    available (the search module is optional / may evolve), so the report
    layer stores this simplified projection.

    Parameters
    ----------
    entry_id:
        Reference-database identifier (e.g. COD number, ICDD card).
    formula:
        Chemical formula sum (e.g. ``"Si O2"``).
    name:
        Mineral / trivial name.
    fom:
        Figure of merit (any of the Match! FoM variants — single scalar).
    p_values:
        Per-peak P-values (length = number of correlated peaks).  Empty
        list when not applicable.
    """

    entry_id: str
    formula: str
    name: str = ""
    fom: float = 0.0
    p_values: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "formula": self.formula,
            "name": self.name,
            "fom": float(self.fom),
            "p_values": [float(v) for v in self.p_values],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CandidateEntry:
        return cls(
            entry_id=str(d["entry_id"]),
            formula=str(d.get("formula", "")),
            name=str(d.get("name", "")),
            fom=float(d.get("fom", 0.0)),
            p_values=[float(v) for v in d.get("p_values", [])],
        )


@dataclass
class PeakListSection:
    """Experimental peak list chapter.

    Wraps a ``list[Peak]``; serialization delegates to :meth:`Peak.to_dict`.
    """

    peaks: list[Peak] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"peaks": [p.to_dict() for p in self.peaks]}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PeakListSection:
        return cls(peaks=[Peak.from_dict(p) for p in d.get("peaks", [])])


@dataclass
class CandidateListSection:
    """Candidate phase list chapter."""

    candidates: list[CandidateEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"candidates": [c.to_dict() for c in self.candidates]}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CandidateListSection:
        return cls(
            candidates=[CandidateEntry.from_dict(c) for c in d.get("candidates", [])]
        )


@dataclass
class SelectedPhasesSection:
    """Selected (matching) phases chapter.

    Stores ``list[Phase]``; Phase embeds the full reference :class:`Entry`
    so the report can render formula / name / cell / etc.
    """

    phases: list[Phase] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"phases": [p.to_dict() for p in self.phases]}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SelectedPhasesSection:
        return cls(phases=[Phase.from_dict(p) for p in d.get("phases", [])])


@dataclass
class QuantResultSection:
    """Quantitative analysis chapter.

    Parameters
    ----------
    weight_fractions:
        Mapping ``{phase_name: weight fraction in [0, 1]}``.
    """

    weight_fractions: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "weight_fractions": {
                k: float(v) for k, v in self.weight_fractions.items()
            }
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> QuantResultSection:
        return cls(
            weight_fractions={
                str(k): float(v)
                for k, v in d.get("weight_fractions", {}).items()
            }
        )


@dataclass
class RFactorSection:
    """Profile agreement factors (Rietveld / pattern-fit).

    All values are dimensionless *fractions* (e.g. Rwp = 0.0543 means
    5.43 %).  ``None`` when a factor was not computed.
    """

    rwp: float | None = None
    rp: float | None = None
    rexp: float | None = None
    chi2: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rwp": self.rwp,
            "rp": self.rp,
            "rexp": self.rexp,
            "chi2": self.chi2,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RFactorSection:
        return cls(
            rwp=d.get("rwp"),
            rp=d.get("rp"),
            rexp=d.get("rexp"),
            chi2=d.get("chi2"),
        )


# ---------------------------------------------------------------------------
# Top-level Report container
# ---------------------------------------------------------------------------
@dataclass
class Report:
    """Top-level phase-analysis report.

    Combines all chapters described in ``docs/report_basics.md``.  Use
    :meth:`to_json` / :meth:`from_json` for on-disk serialisation; the
    intermediate :meth:`to_dict` / :meth:`from_dict` round-trips through
    JSON-serialisable plain data.

    Parameters
    ----------
    sample_info:
        :class:`SampleInfo` header.
    peak_list:
        :class:`PeakListSection`.
    candidate_list:
        :class:`CandidateListSection`.
    selected_phases:
        :class:`SelectedPhasesSection`.
    quant_result:
        :class:`QuantResultSection`.
    r_factors:
        :class:`RFactorSection`.
    timestamp:
        ISO-8601 timestamp string (UTC).  ``None`` until :meth:`now` is
        called or the value is set explicitly.
    """

    sample_info: SampleInfo = field(default_factory=SampleInfo)
    peak_list: PeakListSection = field(default_factory=PeakListSection)
    candidate_list: CandidateListSection = field(default_factory=CandidateListSection)
    selected_phases: SelectedPhasesSection = field(
        default_factory=SelectedPhasesSection
    )
    quant_result: QuantResultSection = field(default_factory=QuantResultSection)
    r_factors: RFactorSection = field(default_factory=RFactorSection)
    timestamp: str | None = None

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict representation of the report."""
        return {
            "sample_info": self.sample_info.to_dict(),
            "peak_list": self.peak_list.to_dict(),
            "candidate_list": self.candidate_list.to_dict(),
            "selected_phases": self.selected_phases.to_dict(),
            "quant_result": self.quant_result.to_dict(),
            "r_factors": self.r_factors.to_dict(),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Report:
        """Inverse of :meth:`to_dict`."""
        return cls(
            sample_info=SampleInfo.from_dict(d.get("sample_info", {})),
            peak_list=PeakListSection.from_dict(d.get("peak_list", {})),
            candidate_list=CandidateListSection.from_dict(d.get("candidate_list", {})),
            selected_phases=SelectedPhasesSection.from_dict(
                d.get("selected_phases", {})
            ),
            quant_result=QuantResultSection.from_dict(d.get("quant_result", {})),
            r_factors=RFactorSection.from_dict(d.get("r_factors", {})),
            timestamp=d.get("timestamp"),
        )

    def to_json(self, path: str | Path) -> None:
        """Serialise the report to a UTF-8 JSON file.

        Parameters
        ----------
        path:
            Destination file path.  Parent directory is not created
            automatically; the caller must ensure it exists.
        """
        p = Path(path)
        p.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def from_json(cls, path: str | Path) -> Report:
        """Load a report from a JSON file written by :meth:`to_json`."""
        p = Path(path)
        return cls.from_dict(json.loads(p.read_text(encoding="utf-8")))

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    @classmethod
    def now(cls, **kwargs: Any) -> Report:
        """Build a new :class:`Report` stamped with the current UTC time.

        Any field of the report can be supplied as a keyword argument; the
        corresponding section is replaced wholesale.
        """
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return cls(timestamp=ts, **kwargs)
