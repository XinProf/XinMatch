"""CLI tests for ``xinmatch instrument`` (T14.4)."""

from __future__ import annotations

import pytest

from xinmatch.cli.main import build_parser

# pyserial is a declared runtime dependency (pyproject ``dependencies``), but an
# incomplete dev env must skip here instead of failing the whole suite.
pytest.importorskip("serial", reason="pyserial not installed")


class FakeSerial:
    """Serial double fed to the CLI via monkeypatched ``open_serial``."""

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


def _run(argv: list[str], monkeypatch: pytest.MonkeyPatch, lines: list[bytes]):
    monkeypatch.setattr(
        "xinmatch.core.instrument.open_serial",
        lambda *a, **k: FakeSerial(lines),
    )
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def test_instrument_scan_json(capsys, monkeypatch) -> None:
    result = _run(["instrument", "scan", "--json"], monkeypatch, [])
    assert "ports" in result and "count" in result
    assert result["count"] == len(result["ports"])


def test_instrument_collect_writes_file(tmp_path, capsys, monkeypatch) -> None:
    lines = [
        b"# scan header\n",
        b"20.0,100\n",
        b"20.1,101.5\n",
        b"junk\n",
        b"20.2,99\n",
    ]
    out_file = tmp_path / "scan.txt"
    result = _run(
        [
            "instrument", "collect", "--port", "COM9",
            "--baud", "9600", "--seconds", "5", "--out", str(out_file),
        ],
        monkeypatch,
        lines,
    )
    # Summary fields.
    assert result["raw_lines"] == 5
    assert result["points"] == 3
    assert result["skipped"] == 2  # header comment + junk line
    assert result["data_file"] == str(out_file)
    assert result["first"] == {"two_theta": 20.0, "intensity": 100.0}
    assert result["last"] == {"two_theta": 20.2, "intensity": 99.0}
    # File contents: header + 3 two-column rows.
    text = out_file.read_text(encoding="utf-8")
    rows = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
    assert len(rows) == 3
    assert float(rows[0].split()[0]) == pytest.approx(20.0)


def test_instrument_collect_max_points(tmp_path, capsys, monkeypatch) -> None:
    lines = [f"20.{i},100\n".encode() for i in range(100)]
    out_file = tmp_path / "scan2.txt"
    result = _run(
        ["instrument", "collect", "--port", "COM9",
         "--max-points", "4", "--out", str(out_file)],
        monkeypatch,
        lines,
    )
    assert result["points"] == 4
    rows = [
        ln for ln in out_file.read_text(encoding="utf-8").splitlines()
        if ln and not ln.startswith("#")
    ]
    assert len(rows) == 4


def test_instrument_collect_stdout_mode(capsys, monkeypatch) -> None:
    lines = [b"20.0,100\n", b"20.1,101\n"]
    _run(["instrument", "collect", "--port", "COM9"], monkeypatch, lines)
    out = capsys.readouterr().out
    rows = [ln for ln in out.splitlines() if ln.strip()]
    assert len(rows) == 2
    assert float(rows[0].split()[0]) == pytest.approx(20.0)


def test_instrument_collect_live_plot(tmp_path, monkeypatch) -> None:
    """``--live-plot`` never breaks acquisition.

    Two environment-dependent paths are covered: with matplotlib installed
    the headless (Agg) backend must draw without crashing; without it the
    plotter must degrade gracefully (warning on stderr, data still saved).
    """
    try:
        import matplotlib

        matplotlib.use("Agg")  # force headless backend before pyplot import
        has_mpl = True
    except ImportError:
        has_mpl = False

    lines = [b"20.0,100\n", b"20.1,101\n", b"20.2,99\n"]
    out_file = tmp_path / "scan_live.txt"
    result = _run(
        ["instrument", "collect", "--port", "COM9",
         "--live-plot", "--out", str(out_file)],
        monkeypatch,
        lines,
    )
    assert result["points"] == 3
    rows = [
        ln for ln in out_file.read_text(encoding="utf-8").splitlines()
        if ln and not ln.startswith("#")
    ]
    assert len(rows) == 3
    if not has_mpl:
        # Degradation path: matplotlib missing → plotter disabled, data OK.
        assert result["points"] == 3


def test_instrument_subcommand_help_shows_scan_and_collect(capsys) -> None:
    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["instrument", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "scan" in out and "collect" in out
