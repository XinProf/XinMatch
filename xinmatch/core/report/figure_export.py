"""Pattern figure exporters (T12.3).

Renders diffraction patterns to bitmap / vector image files using
matplotlib with the headless ``Agg`` backend (no GUI dependency).

Implements the exports described in ``docs/export_pattern-graphics.md``:

* :func:`export_pattern_png`        — single pattern → PNG
* :func:`export_pattern_svg`        — single pattern → SVG (vector)
* :func:`export_multi_pattern_png`  — multi-pattern stacked plot → PNG
* :func:`export_peaks_png`          — pattern + peak markers → PNG

matplotlib is an **optional** dependency: it is not declared in
``pyproject.toml`` (left to the user).  Each public function imports it
lazily and raises :class:`ImportError` with install instructions when
the package is missing.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xinmatch.core.model import Pattern, Peak


# ---------------------------------------------------------------------------
# Lazy matplotlib import
# ---------------------------------------------------------------------------
def _import_matplotlib():
    """Import matplotlib + pyplot, switching to the Agg backend.

    Raises
    ------
    ImportError
        If matplotlib is not installed.
    """
    import importlib

    mpl = importlib.import_module("matplotlib")
    mpl.use("Agg")  # headless backend — no GUI required
    plt = importlib.import_module("matplotlib.pyplot")
    return mpl, plt


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def export_pattern_png(
    pattern: Pattern,
    output_path: str | Path,
    *,
    dpi: int = 300,
    title: str | None = None,
) -> None:
    """Render a single diffraction pattern to a PNG file.

    Corresponds to Match!'s *Export → Pattern graphics → PNG* command
    (see ``docs/export_pattern-graphics.md``).

    Parameters
    ----------
    pattern:
        :class:`xinmatch.core.model.Pattern` to plot.
    output_path:
        Destination PNG file path.  The file extension is not changed
        automatically — pass a path ending in ``.png``.
    dpi:
        Resolution in dots per inch (Match! default ≈ 300).
    title:
        Optional plot title.  ``None`` for no title.
    """
    mpl, plt = _import_matplotlib()
    fig, ax = plt.subplots(figsize=(10, 5))
    try:
        ax.plot(pattern.two_theta, pattern.intensity, lw=0.8, color="#1f4e79")
        ax.set_xlabel("2θ (°)")
        ax.set_ylabel("Intensity (counts)")
        if title is not None:
            ax.set_title(title)
        fig.tight_layout()
        fig.savefig(str(output_path), dpi=dpi, format="png")
    finally:
        plt.close(fig)


def export_pattern_svg(
    pattern: Pattern,
    output_path: str | Path,
    *,
    title: str | None = None,
) -> None:
    """Render a single diffraction pattern to an SVG vector file.

    SVG matches Match!'s recommended vector format for transferring
    plots to word processors (see ``docs/export_pattern-graphics.md``).

    Parameters
    ----------
    pattern:
        :class:`xinmatch.core.model.Pattern` to plot.
    output_path:
        Destination SVG file path.
    title:
        Optional plot title.
    """
    mpl, plt = _import_matplotlib()
    fig, ax = plt.subplots(figsize=(10, 5))
    try:
        ax.plot(pattern.two_theta, pattern.intensity, lw=0.8, color="#1f4e79")
        ax.set_xlabel("2θ (°)")
        ax.set_ylabel("Intensity (counts)")
        if title is not None:
            ax.set_title(title)
        fig.tight_layout()
        fig.savefig(str(output_path), format="svg")
    finally:
        plt.close(fig)


def export_multi_pattern_png(
    patterns: list[Pattern],
    output_path: str | Path,
    *,
    labels: list[str] | None = None,
    dpi: int = 300,
    offset_mode: str = "stacked",
) -> None:
    """Render multiple diffraction patterns to a single stacked PNG.

    Patterns are offset vertically so that overlapping peaks can be
    compared visually (Match! *stacked plot* style).

    Parameters
    ----------
    patterns:
        List of :class:`Pattern` objects to plot (length ≥ 1).
    output_path:
        Destination PNG file path.
    labels:
        Optional legend labels.  If supplied, must match ``len(patterns)``.
    dpi:
        Resolution in dots per inch.
    offset_mode:
        ``"stacked"`` (default) offsets each pattern vertically by the
        previous pattern's intensity range.  ``"overlay"`` plots all
        patterns on the same axis with no offset.

    Raises
    ------
    ValueError
        If ``patterns`` is empty or ``labels`` length does not match
        ``patterns``.
    """
    if not patterns:
        raise ValueError("patterns must contain at least one Pattern")
    if labels is not None and len(labels) != len(patterns):
        raise ValueError(
            f"labels length ({len(labels)}) does not match "
            f"patterns length ({len(patterns)})"
        )
    if offset_mode not in ("stacked", "overlay"):
        raise ValueError(
            f"unknown offset_mode {offset_mode!r}; "
            "expected 'stacked' or 'overlay'"
        )

    mpl, plt = _import_matplotlib()
    fig, ax = plt.subplots(figsize=(10, 6))
    try:
        offset = 0.0
        for i, p in enumerate(patterns):
            y = p.intensity
            if offset_mode == "stacked" and i > 0:
                # Step each trace up by the previous trace's range plus
                # a 10 % margin so peaks do not overlap.
                prev = patterns[i - 1].intensity
                offset += float(prev.max() - prev.min()) * 1.1
                y = y + offset
            label = labels[i] if labels else None
            ax.plot(p.two_theta, y, lw=0.7, label=label)
        ax.set_xlabel("2θ (°)")
        ax.set_ylabel("Intensity (counts)")
        if labels:
            ax.legend(loc="upper right", fontsize=8)
        fig.tight_layout()
        fig.savefig(str(output_path), dpi=dpi, format="png")
    finally:
        plt.close(fig)


def export_peaks_png(
    pattern: Pattern,
    peaks: list[Peak],
    output_path: str | Path,
    *,
    dpi: int = 300,
) -> None:
    """Render the diffraction pattern with peak positions marked.

    Pattern intensity is plotted as a continuous line; each peak is
    annotated with a vertical stem and tick at its 2θ position.

    Corresponds to Match!'s on-screen pattern graphics with the peak
    list overlaid (see ``docs/report_basics.md`` — *Peak list* chapter
    + pattern graphics export).

    Parameters
    ----------
    pattern:
        :class:`Pattern` to plot as a continuous trace.
    peaks:
        List of :class:`Peak` to overlay as markers.
    output_path:
        Destination PNG file path.
    dpi:
        Resolution in dots per inch.
    """
    import numpy as np  # noqa: F401  — numpy is a hard dep of Pattern

    mpl, plt = _import_matplotlib()
    fig, ax = plt.subplots(figsize=(10, 5))
    try:
        ax.plot(pattern.two_theta, pattern.intensity, lw=0.8, color="#1f4e79",
                label="Pattern")
        if peaks:
            xs = [p.two_theta for p in peaks]
            ys = [p.intensity for p in peaks]
            # Clip peak intensities to the visible pattern range so stems
            # do not dominate the plot.
            ymax = float(pattern.intensity.max())
            stem_y = [min(y, ymax) for y in ys]
            ax.vlines(xs, ymin=0, ymax=stem_y, colors="#c0504d",
                      linestyles="dashed", lw=0.9, label="Peaks")
            ax.scatter(xs, stem_y, marker="|", color="#c0504d", s=30)
        ax.set_xlabel("2θ (°)")
        ax.set_ylabel("Intensity (counts)")
        if peaks:
            ax.legend(loc="upper right", fontsize=8)
        fig.tight_layout()
        fig.savefig(str(output_path), dpi=dpi, format="png")
    finally:
        plt.close(fig)
