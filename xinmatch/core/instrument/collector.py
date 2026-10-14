"""Serial data collector for diffraction instruments (T14.4).

Reads a stream of ASCII lines from a serial port, parses each line into a
(2θ, intensity) point and emits it through a callback so a GUI / CLI can
render or persist it in real time.  The collector is **injectable**: it
works with any object exposing ``readline()`` (a real ``serial.Serial``,
a ``loop://`` URL, or a test double), which keeps the parsing logic fully
unit-testable without hardware.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, TextIO

logger = logging.getLogger(__name__)

__all__ = [
    "DataPoint",
    "SerialConfig",
    "parse_point",
    "iter_lines",
    "SerialCollector",
]


@dataclass(frozen=True)
class DataPoint:
    """One parsed (2θ, intensity) measurement."""

    two_theta: float
    intensity: float

    def to_dict(self) -> dict[str, float]:
        return {"two_theta": self.two_theta, "intensity": self.intensity}


@dataclass(frozen=True)
class SerialConfig:
    """Serial connection parameters (subset of pyserial's ``Serial``)."""

    port: str
    baudrate: int = 9600
    bytesize: int = 8
    parity: str = "N"
    stopbits: float = 1.0
    timeout: float | None = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "port": self.port,
            "baudrate": self.baudrate,
            "bytesize": self.bytesize,
            "parity": self.parity,
            "stopbits": self.stopbits,
        }


#: 2θ delimiter — an instrument may emit "31.770, 512.0", "31.770 512.0"
#: or "31.770\t512.0"; we accept any of them (plus the full-width comma
#: some Chinese-lab exports use).
_DELIMS = (",", "\t", "，", ";", " ")


def parse_point(line: str) -> DataPoint | None:
    """Parse one ASCII line into a :class:`DataPoint`.

    The line must contain exactly two numeric fields separated by a
    comma, semicolon, tab or space (leading non-numeric tokens such as a
    header marker are tolerated if the two numbers are still findable).
    Returns ``None`` for blank lines, comment lines (starting with ``#``
    or ``//``) or lines with fewer than two numbers.
    """
    text = line.strip()
    if not text or text.startswith(("#", "//", ";")):
        return None
    # Collect every numeric token in order, then take the first two.
    tokens = _numeric_tokens(text)
    if len(tokens) < 2:
        return None
    try:
        tt = float(tokens[0])
        intensity = float(tokens[1])
    except ValueError:  # pragma: no cover — _numeric_tokens already filtered
        return None
    return DataPoint(two_theta=tt, intensity=intensity)


def _numeric_tokens(text: str) -> list[str]:
    """Return the numeric tokens of *text* in order (supports ±/e notation)."""
    out: list[str] = []
    cur = ""
    for ch in text:
        if ch.isdigit() or ch in ".+-eE":
            cur += ch
        else:
            if cur:
                out.append(cur)
                cur = ""
    if cur:
        out.append(cur)
    # Drop tokens that are not valid numbers (e.g. a bare "-" or "e+").
    valid: list[str] = []
    for tok in out:
        try:
            float(tok)
        except ValueError:
            continue
        valid.append(tok)
    return valid


def iter_lines(
    serial_obj: Any,
    *,
    stop_event: threading.Event | None = None,
    max_lines: int | None = None,
) -> Iterator[str]:
    """Yield raw lines from *serial_obj* until EOF / stop / max_lines.

    ``serial_obj`` may be any object with ``readline()`` (real serial,
    ``loop://`` URL, or a test double).  Blank lines are yielded as-is;
    the caller decides how to treat them.
    """
    count = 0
    while True:
        if stop_event is not None and stop_event.is_set():
            break
        if max_lines is not None and count >= max_lines:
            break
        try:
            raw = serial_obj.readline()
        except Exception as exc:  # noqa: BLE001 — serial read boundary
            logger.warning("serial readline error: %s", exc)
            break
        if not raw:
            break  # EOF / timeout with nothing received
        count += 1
        yield raw.decode(errors="replace").rstrip("\r\n")


class SerialCollector:
    """Streaming collector turning serial lines into data points.

    Usage::

        collector = SerialCollector(serial_obj, on_point=callback)
        collector.collect(seconds=30)          # stop after 30 s
        points = collector.points              # everything accumulated

    ``on_point`` is invoked synchronously on the collecting thread as soon
    as a point is parsed — a GUI can append to a live curve from there
    (use a queued slot / signal), and a CLI can flush it to disk.
    """

    def __init__(
        self,
        serial_obj: Any,
        *,
        on_point: Callable[[DataPoint], None] | None = None,
    ) -> None:
        self._serial = serial_obj
        self._on_point = on_point
        self.points: list[DataPoint] = []
        self.n_raw_lines = 0
        self.n_parsed = 0
        self.n_skipped = 0

    @property
    def n_points(self) -> int:
        return len(self.points)

    def collect(
        self,
        *,
        seconds: float | None = None,
        max_points: int | None = None,
        stop_event: threading.Event | None = None,
    ) -> list[DataPoint]:
        """Read and parse points until a stop condition is met.

        Parameters
        ----------
        seconds:
            Stop after this many wall-clock seconds (None = no time cap).
        max_points:
            Stop after this many parsed points (None = no point cap).
        stop_event:
            External stop signal (e.g. user cancelled the acquisition).

        Returns
        -------
        list[DataPoint]
            All points accumulated during this call (also available via
            :attr:`points`).
        """
        deadline = time.monotonic() + seconds if seconds else None
        for raw in iter_lines(self._serial, stop_event=stop_event):
            self.n_raw_lines += 1
            point = parse_point(raw)
            if point is None:
                self.n_skipped += 1
                continue
            self.points.append(point)
            self.n_parsed += 1
            if self._on_point is not None:
                self._on_point(point)
            if max_points is not None and self.n_parsed >= max_points:
                break
            if deadline is not None and time.monotonic() >= deadline:
                break
        return self.points

    def write_points(self, out: TextIO, *, header: str = "") -> None:
        """Persist accumulated points to a 2-column ASCII file.

        Format matches the two-column ASCII importers
        (:mod:`xinmatch.core.io.free`): ``two_theta intensity`` per line.
        """
        if header:
            out.write(header.rstrip("\n") + "\n")
        for p in self.points:
            out.write(f"{p.two_theta:.5f} {p.intensity:.4f}\n")
