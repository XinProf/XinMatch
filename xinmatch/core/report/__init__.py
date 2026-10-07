"""XinMatch report module (T12.1 / T12.2 / T12.3).

Public API:

* Data model: :class:`Report`, :class:`SampleInfo`, :class:`CandidateEntry`,
  plus per-chapter section dataclasses.
* Renderers: :func:`render_html`, :func:`render_text`,
  :func:`render_markdown`, :func:`render_pdf`.
* Figure exporters: :func:`export_pattern_png`,
  :func:`export_pattern_svg`, :func:`export_multi_pattern_png`,
  :func:`export_peaks_png`.

All routines are GUI-free; matplotlib (when used) runs in the Agg
backend, and weasyprint / matplotlib are lazy optional dependencies.
"""

from .figure_export import (
    export_multi_pattern_png,
    export_pattern_png,
    export_pattern_svg,
    export_peaks_png,
)
from .render import (
    render_html,
    render_markdown,
    render_pdf,
    render_text,
)
from .report_model import (
    CandidateEntry,
    CandidateListSection,
    PeakListSection,
    QuantResultSection,
    Report,
    RFactorSection,
    SampleInfo,
    SelectedPhasesSection,
)

__all__ = [
    # Data model
    "Report",
    "SampleInfo",
    "CandidateEntry",
    "PeakListSection",
    "CandidateListSection",
    "SelectedPhasesSection",
    "QuantResultSection",
    "RFactorSection",
    # Renderers
    "render_html",
    "render_text",
    "render_markdown",
    "render_pdf",
    # Figure exporters
    "export_pattern_png",
    "export_pattern_svg",
    "export_multi_pattern_png",
    "export_peaks_png",
]
