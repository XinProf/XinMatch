"""Unit tests for the serial data collector (T14.4).

All parsing / streaming tests run against a fake serial object exposing
``readline()`` — no hardware or real COM port is required.
"""

from __future__ import annotations

import threading

import pytest

from xinmatch.core.instrument.collector import (
    DataPoint,
    SerialCollector,
    iter_lines,
    parse_point,
)


class FakeSerial:
    """Minimal serial double: an iterable of bytes lines + close() state."""

    def __init__(self, lines: list[bytes]) -> None:
        self._lines = iter(lines)
        self.closed = False

    def readline(self) -> bytes:
        try:
            return next(self._lines)
        except StopIteration:
            return b""

    def close(self) -> None:
        self.closed = True


# ---------------------------------------------------------------------------
# parse_point
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("31.770, 512.0", DataPoint(31.770, 512.0)),
        ("31.770 512.0", DataPoint(31.770, 512.0)),
        ("31.770\t512.0", DataPoint(31.770, 512.0)),
        ("31.770,512.0", DataPoint(31.770, 512.0)),
        ("31.770，512.0", DataPoint(31.770, 512.0)),  # full-width comma
        ("  31.77 ; 512.0  ", DataPoint(31.77, 512.0)),
        ("-1.234e2 +5.678e1", DataPoint(-123.4, 56.78)),  # scientific
        ("ANGLE,COUNTS\n20.0,100.0", DataPoint(20.0, 100.0)),  # header + data
        ("20.0,100.0 extra", DataPoint(20.0, 100.0)),  # trailing junk ignored
    ],
)
def test_parse_point_valid(raw: str, expected: DataPoint) -> None:
    point = parse_point(raw)
    assert point is not None
    assert point.two_theta == pytest.approx(expected.two_theta)
    assert point.intensity == pytest.approx(expected.intensity)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "# comment line",
        "// comment",
        "; comment",
        "just words here",
        "31.770",  # only one number
        "one,two,three",
    ],
)
def test_parse_point_skipped(raw: str) -> None:
    assert parse_point(raw) is None


def test_parse_point_rejects_lone_sign() -> None:
    # "20.0,-" must not parse "-" as a number.
    assert parse_point("20.0, -") is None


# ---------------------------------------------------------------------------
# iter_lines
# ---------------------------------------------------------------------------
def test_iter_lines_yields_all_until_eof() -> None:
    fake = FakeSerial([b"10,1\n", b"11,2\n", b"12,3\n"])
    lines = list(iter_lines(fake))
    assert lines == ["10,1", "11,2", "12,3"]


def test_iter_lines_respects_max_lines() -> None:
    fake = FakeSerial([b"10,1\n"] * 10)
    lines = list(iter_lines(fake, max_lines=3))
    assert len(lines) == 3


def test_iter_lines_respects_stop_event() -> None:
    fake = FakeSerial([b"10,1\n"] * 100)
    stop = threading.Event()
    stop.set()
    assert list(iter_lines(fake, stop_event=stop)) == []


def test_iter_lines_handles_binary_read_error() -> None:
    class BrokenSerial:
        def readline(self) -> bytes:
            raise OSError("port gone")

    assert list(iter_lines(BrokenSerial())) == []


# ---------------------------------------------------------------------------
# SerialCollector
# ---------------------------------------------------------------------------
def test_collect_parses_points_and_counts_skips() -> None:
    fake = FakeSerial(
        [
            b"# header\n",
            b"10.0, 100\n",
            b"10.1,101.5\n",
            b"garbage\n",
            b"10.2,102\n",
        ]
    )
    collector = SerialCollector(fake)
    points = collector.collect()
    assert collector.n_raw_lines == 5
    assert collector.n_parsed == 3
    assert collector.n_skipped == 2
    assert collector.n_points == 3
    assert points == [
        DataPoint(10.0, 100.0),
        DataPoint(10.1, 101.5),
        DataPoint(10.2, 102.0),
    ]


def test_collect_stops_at_max_points() -> None:
    fake = FakeSerial([b"10.0,100\n", b"10.1,101\n", b"10.2,102\n", b"10.3,103\n"])
    collector = SerialCollector(fake)
    collector.collect(max_points=2)
    assert collector.n_points == 2
    assert collector.points[-1] == DataPoint(10.1, 101.0)


def test_collect_invokes_on_point_inline() -> None:
    fake = FakeSerial([b"10.0,100\n", b"10.1,101\n"])
    seen: list[DataPoint] = []
    collector = SerialCollector(fake, on_point=seen.append)
    collector.collect()
    assert seen == collector.points
    assert len(seen) == 2


def test_write_points_two_column_format() -> None:
    fake = FakeSerial([b"10.0,100\n", b"10.1,101.25\n"])
    collector = SerialCollector(fake)
    collector.collect()
    from io import StringIO

    buf = StringIO()
    collector.write_points(buf, header="# T14.4 scan")
    text = buf.getvalue()
    assert text.startswith("# T14.4 scan\n")
    data_lines = text.splitlines()[1:]
    assert len(data_lines) == 2
    # Two-column, round-trippable numbers.
    toks = data_lines[0].split()
    assert len(toks) == 2
    assert float(toks[0]) == pytest.approx(10.0)
    assert float(toks[1]) == pytest.approx(100.0)


def test_collector_datafile_roundtrip_via_load_pattern(tmp_path) -> None:
    """The written ASCII file must be importable by the pattern loader."""
    from xinmatch.core.io import load_pattern

    fake = FakeSerial([b"20.0,100\n", b"20.1,120\n", b"20.2,90\n"])
    collector = SerialCollector(fake)
    collector.collect()
    out = tmp_path / "scan.txt"
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        collector.write_points(fh)
    pattern = load_pattern(str(out))
    assert pattern is not None
    assert len(pattern.two_theta) == 3
    assert len(pattern.intensity) == 3
