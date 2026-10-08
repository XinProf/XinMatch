"""Diffraction pattern graphics view (pyqtgraph).

T13.2 — Pattern view: multi-pattern overlay, zoom / pan, cursor tracking.

Match! references (docs/):
- ``diffpattern_basics.md`` — the diffraction pattern graphics; multiple
  patterns are stacked on top of each other; the legend in the upper-right
  corner lists sample IDs / entry names.
- ``diffpattern_zoom.md`` — mouse-wheel zoom, rubber-band area zoom and
  double-click zoom (provided here by pyqtgraph's default ViewBox
  interaction: left-drag pans, wheel zooms).
- ``diffpattern_zoom_track.md`` — "tracking": shift the viewing area while
  holding Shift / the middle mouse button (pyqtgraph default pan).
- ``options_diffpattern.md`` — "vertical line at mouse cursor position"
  (here a full crosshair: horizontal + vertical InfiniteLine plus a live
  ``(2θ, I, d)`` readout label).

Architecture boundary: the view only consumes
:class:`xinmatch.core.model.pattern.Pattern` data objects and never calls
back into ``xinmatch.core`` logic.

Implementation note: we subclass :class:`pyqtgraph.PlotWidget` (a
GraphicsView that already owns a single PlotItem) rather than building a
GraphicsView by hand — pyqtgraph 0.14's ``autoDownsample``/``clipToView``
code caches the enclosing "view" while an item first enters the scene, and
the hand-built layout resolves that cache to the GraphicsView itself.
"""

from __future__ import annotations

import contextlib
import itertools
import math

import pyqtgraph as pg
from PySide6 import QtCore

from xinmatch.core.model.pattern import Pattern

# Clean distinct colors for stacked patterns; no Match! visual assets used.
PATTERN_COLORS: tuple[str, ...] = (
    "#1f77b4",
    "#d62728",
    "#2ca02c",
    "#9467bd",
    "#ff7f0e",
    "#17becf",
    "#8c564b",
    "#e377c2",
)


class PatternView(pg.PlotWidget):
    """Widget displaying one or more overlaid experimental/reference patterns.

    Corresponds to the upper-left graphics panel in Match!'s working area
    (``docs/working_area.md``).
    """

    #: Emitted while the mouse moves over the plot; argument is the
    #: human-readable ``(2θ, I, d)`` string, mirrored into the status bar.
    cursor_moved = QtCore.Signal(str)

    def __init__(self, parent=None) -> None:
        """Set up the plot item, grid, legend and cursor crosshair."""
        super().__init__(parent)
        self._plot = self.plotItem
        self._plot.setLabel("bottom", "2θ", units="°")
        self._plot.setLabel("left", "Intensity", units="counts")
        self._plot.showGrid(x=True, y=True, alpha=0.25)
        # Match! zoom/tracking: left-drag pan, wheel zoom (diffpattern_zoom.md).
        self._plot.setMouseEnabled(x=True, y=True)

        # Upper-right legend listing each overlaid pattern (diffpattern_basics.md).
        self._legend = self._plot.addLegend(offset=(12, 12))

        # Crosshair: horizontal + vertical InfiniteLine following the mouse
        # (Match! "vertical line at mouse cursor position", options_diffpattern.md).
        self._vline = pg.InfiniteLine(angle=90, pen=pg.mkPen("#555555", dash=[4, 3]))
        self._hline = pg.InfiniteLine(angle=0, pen=pg.mkPen("#555555", dash=[4, 3]))
        self._plot.addItem(self._vline, ignoreBounds=True)
        self._plot.addItem(self._hline, ignoreBounds=True)
        self._readout = pg.TextItem(anchor=(0, 1), color="#222222")
        self._plot.addItem(self._readout, ignoreBounds=True)

        self._records: dict[str, dict] = {}
        self._counter = itertools.count(1)

        self.scene().sigMouseMoved.connect(self._on_scene_mouse_moved)

    # ------------------------------------------------------------------
    # Pattern management
    # ------------------------------------------------------------------
    def add_pattern(self, pattern: Pattern, name: str | None = None,
                    color: str | None = None) -> str:
        """Overlay *pattern*; returns a handle used by :meth:`remove_pattern`.

        Multiple patterns are stacked on top of each other exactly like in
        Match! (``diffpattern_basics.md``, "Multiple diffraction patterns").
        Each curve uses ``autoDownsample`` + ``clipToView`` so that a
        50 000-point trace stays responsive.
        """
        key = f"P{next(self._counter)}"
        label = name or str(pattern.metadata.get("sample_id") or f"Pattern {key}")
        pen_color = color or PATTERN_COLORS[len(self._records) % len(PATTERN_COLORS)]
        # NOTE: clipToView is enabled via opts *after* addItem.  On
        # pyqtgraph 0.13.x + PySide6 6.11, constructing with clipToView=True
        # makes the first synchronous viewRangeChanged() (fired while the
        # item enters the scene, before it is reparented to the ViewBox's
        # child group) resolve the enclosing GraphicsView as if it were the
        # ViewBox and crash in ``autoRangeEnabled()``.
        curve = pg.PlotDataItem(
            pattern.two_theta,
            pattern.intensity,
            pen=pg.mkPen(pen_color, width=1.2),
            name=label,
            autoDownsample=True,
            connect="all",
        )
        self._plot.addItem(curve)
        curve.opts["clipToView"] = True
        self._legend.addItem(curve, label)
        self._records[key] = {
            "pattern": pattern,
            "curve": curve,
            "name": label,
            "color": pen_color,
        }
        self._plot.enableAutoRange()
        return key

    def remove_pattern(self, key: str) -> None:
        """Remove the pattern previously added under *key* (no-op if absent)."""
        rec = self._records.pop(key, None)
        if rec is None:
            return
        self._plot.removeItem(rec["curve"])
        with contextlib.suppress(KeyError, ValueError):
            self._legend.removeItem(rec["name"])
        self._plot.enableAutoRange()

    def patterns(self) -> dict[str, Pattern]:
        """Mapping of handle -> :class:`Pattern` currently displayed."""
        return {k: v["pattern"] for k, v in self._records.items()}

    def clear(self) -> None:
        """Remove all overlaid patterns."""
        for key in list(self._records):
            self.remove_pattern(key)

    # ------------------------------------------------------------------
    # Cursor tracking
    # ------------------------------------------------------------------
    def set_crosshair_position(self, x: float, y: float) -> None:
        """Place the crosshair at data coords (*x* = 2θ°, *y* = intensity).

        Updates the two InfiniteLines, the readout label (2θ, I, plus
        d-spacing from the anchor pattern's wavelength via Bragg's law) and
        emits :attr:`cursorMoved`.
        """
        self._vline.setPos(x)
        self._hline.setPos(y)
        wavelength = self._anchor_wavelength()
        d = math.nan
        if wavelength and 0.0 < x < 180.0:
            sin_theta = math.sin(math.radians(x) / 2.0)
            if sin_theta > 0.0:
                d = wavelength / (2.0 * sin_theta)
        text = f"2θ = {x:8.3f}°   I = {y:12.1f}   d = {d:7.3f} Å"
        self._readout.setText(text)
        (x0, x1), (y0, y1) = self._plot.vb.viewRange()
        self._readout.setPos(x0 + (x1 - x0) * 0.01, y1 - (y1 - y0) * 0.02)
        self.cursor_moved.emit(text)

    def _anchor_wavelength(self) -> float:
        """Wavelength of the bottom-most ("anchor") pattern, like in Match!."""
        for rec in self._records.values():
            return float(rec["pattern"].wavelength)
        return 0.0

    def _on_scene_mouse_moved(self, scene_pos) -> None:
        """Map a scene-coordinate mouse event to data coords and update."""
        view_pos = self._plot.vb.mapSceneToView(scene_pos)
        (x0, x1), (y0, y1) = self._plot.vb.viewRange()
        if not (x0 <= view_pos.x() <= x1 and y0 <= view_pos.y() <= y1):
            return
        self.set_crosshair_position(view_pos.x(), view_pos.y())
