"""XinMatch command-line interface (T14.1).

A thin argparse-based wrapper around the core pipeline.  Each subcommand
delegates to the corresponding :mod:`xinmatch.core` routine; no
algorithms are implemented at this layer.

Subcommands
-----------
import     Load a diffraction pattern file.
process    Run the automatic raw-data processing pipeline.
search     Run peak-based search-match against a reference database.
quantify   Run RIR quantitative phase analysis.
report     Render a phase-analysis report (HTML / text / markdown).
run        One-shot pipeline: import → process → search → quantify → report.
batch      Run a JSON/YAML batch config over multiple samples (T14.3).
instrument Serial instrument control: scan ports / collect data (T14.4).

Every subcommand supports ``--help`` and a global ``--json`` flag that
switches the output from human-readable text to a structured JSON
document on stdout.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from xinmatch.core.batch import load_config as load_batch_config
from xinmatch.core.batch import run_batch
from xinmatch.core.db.multi_db import (
    add_external_library,
    list_libraries,
    open_search_database,
    remove_external_library,
)
from xinmatch.core.instrument.collector import DataPoint  # no serial import
from xinmatch.core.io import load_pattern
from xinmatch.core.model import Peak, Restraints
from xinmatch.core.model.element_symbols import restraints_from_sample_elements
from xinmatch.core.preprocess.auto_pipeline import auto_process
from xinmatch.core.quant.rir import rir_quantify
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
from xinmatch.core.search.fpfm import search_match_fpfm, to_candidates


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
def _emit(result: dict[str, Any], as_json: bool) -> None:
    """Print *result* as JSON or a short human-readable summary."""
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return

    # Human-readable summary.
    for key, value in result.items():
        if isinstance(value, list):
            print(f"{key}: {len(value)} item(s)")
        elif isinstance(value, dict):
            print(f"{key}: {len(value)} entry(ies)")
        else:
            print(f"{key}: {value}")


@contextlib.contextmanager
def _progress_to_stderr() -> Iterator[None]:
    """把核心层写往 stdout 的进度行临时改道到 stderr。

    ``core.batch.run_batch`` 用 ``print`` 报告逐样本进度（``[name] running …``
    / ``[name] OK …``）。``batch --json`` 约定 stdout 是一个完整、可被
    ``json.loads`` 直接解析的 JSON 文档；进度行混进去会让下游脚本解析失败
    （实测 ``JSONDecodeError``）。JSON 模式下改道到 stderr：终端里仍然看得见
    进度，机器读取的 stdout 保持纯净。

    ``print()`` 在调用时读取 ``sys.stdout``，因此此处的重定向对核心层的
    进度输出有效；C 扩展直接写 fd 1 的情况不在覆盖范围内（当前无此路径）。
    """
    with contextlib.redirect_stdout(sys.stderr):
        yield


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------
def cmd_import(args: argparse.Namespace) -> dict[str, Any]:
    """``xinmatch import`` — load a pattern and print basic info."""
    pattern = load_pattern(args.pattern_file)
    if args.wavelength is not None:
        pattern.wavelength = float(args.wavelength)
    return {
        "file": str(args.pattern_file),
        "n_points": int(len(pattern)),
        "two_theta_start": float(pattern.two_theta[0]) if len(pattern) else None,
        "two_theta_end": float(pattern.two_theta[-1]) if len(pattern) else None,
        "wavelength": float(pattern.wavelength),
    }


def cmd_process(args: argparse.Namespace) -> dict[str, Any]:
    """``xinmatch process`` — run the auto processing pipeline."""
    pattern = load_pattern(args.pattern_file)
    config: dict[str, Any] = {}
    if args.smooth is not None:
        config["smooth"] = args.smooth
    if args.background is not None:
        config["background"] = args.background
    if args.alpha2 is not None:
        config["strip_alpha2"] = args.alpha2
    if args.wavelength is not None:
        pattern.wavelength = float(args.wavelength)

    processed, peaks = auto_process(pattern, config=config or None)
    return {
        "file": str(args.pattern_file),
        "n_points": int(len(processed)),
        "n_peaks": len(peaks),
        "peaks": [
            {"two_theta": float(p.two_theta), "intensity": float(p.intensity)}
            for p in peaks
        ],
    }


def _load_restraints(
    raw: str | None, sample_elements: str | None = None,
) -> Restraints | None:
    """构造检索约束：快捷「样品元素」与完整 Restraints JSON 二选一。

    两者由 argparse 互斥组保证不会同时给出（同时给出直接 usage error）。
    快捷参数走 core 的补集语义（检出元素保持 OPTIONAL、其余全部 EXCLUDE），
    见基准报告 §20.5 / §24 / §25；把检出元素标成 REQUIRED 是错的 ——
    ``elements_allowed`` 是「必须全含」。
    """
    if sample_elements:
        return restraints_from_sample_elements(sample_elements)
    if not raw:
        return None
    return Restraints.from_dict(json.loads(raw))


def cmd_search(args: argparse.Namespace) -> dict[str, Any]:
    """``xinmatch search`` — search-match against a reference database.

    两种模式（``--mode``）：

    * ``peaks``（默认）：自动寻峰 → 峰列表 FoM 检索；
    * ``fpfm``：FPFM 全谱拟合检索，直接对原始谱做剖面拟合，不寻峰。
      可用 ``--single-kalpha`` 关闭 Kα2 伴线——合成谱 / 已剥离 Kα2 的数据
      必须单线模型，否则正确相会被压低（见
      ``docs/fpfm_mechanism.md`` §8.1）。
    """
    pattern = load_pattern(args.pattern_file)
    if args.wavelength is not None:
        pattern.wavelength = float(args.wavelength)

    if args.mode == "smpf":
        # Pre-v1.6.1 legacy mode name (SMPF → FPFM rename); silently accepted.
        args.mode = "fpfm"
    fpfm = args.mode == "fpfm"
    # getattr 兼容直接构造 Namespace 调用 cmd_search 的场景（parser 一定带
    # 该属性，但库内调用/单测未必）。
    sample_elements = getattr(args, "sample_elements", None)
    if fpfm and sample_elements:
        # 不继承 --restraints 的历史静默忽略：填了约束却没生效是更糟的失败。
        raise ValueError(
            "--sample-elements 只在 peaks 模式（默认）生效：FPFM 全谱拟合"
            "目前不接元素约束。请去掉 --mode fpfm 再试。"
        )
    peaks: list[Peak] = []
    if not fpfm:
        # FPFM 直接拟合原始谱，不做（也不该做）自动预处理。
        _processed, peaks = auto_process(pattern)
    restraints = _load_restraints(args.restraints, sample_elements)

    # ``--db`` 只接受 ``.xinDB``（v3.0.0 起旧格式已移除）。
    conn = open_search_database(args.db)
    try:
        if fpfm:
            # Kα 模型只解析一次：<=0 的 Kα1 跟随图谱自身波长（Co/Mo 靶数据
            # 无需手动改设置）；--single-kalpha → kalpha2=None 单线模型。
            ka1 = float(args.kalpha1)
            if ka1 <= 0.0:
                ka1 = pattern.wavelength
            ka2 = None if args.single_kalpha else float(args.kalpha2)
            raw = search_match_fpfm(
                pattern,
                conn,
                wavelength_kalpha1=ka1,
                wavelength_kalpha2=ka2,
                prescreen_top_n=args.prescreen_n,
                top_n=args.top_n,
            )
            # Shared adapter — same mapping as GUI / batch (no third copy).
            candidates = to_candidates(raw)
        else:
            candidates = search_match(
                peaks,
                conn,
                pattern.wavelength,
                restraints=restraints,
                top_n=args.top_n,
            )
    finally:
        conn.close()

    result: dict[str, Any] = {
        "file": str(args.pattern_file),
        "db": str(args.db),
        "mode": "fpfm" if fpfm else "peaks",
        "n_peaks": len(peaks),
        "n_candidates": len(candidates),
        "candidates": [
            {
                "entry_id": c.entry.entry_id,
                "formula": c.entry.formula,
                "name": c.entry.mineral_name or "",
                "fom": float(c.fom),
            }
            for c in candidates
        ],
    }
    if fpfm:
        # FPFM 模式下回显实际使用的 Kα 模型，便于用户核对设置是否生效。
        result["kalpha"] = {
            "double_line": ka2 is not None,
            "kalpha1": ka1,
            "kalpha2": ka2,
        }
    if sample_elements:
        # 只在显式给出时回显，默认输出逐项不变（便于脚本比对基线）。
        result["sample_elements"] = sample_elements
    return result


def cmd_quantify(args: argparse.Namespace) -> dict[str, Any]:
    """``xinmatch quantify`` — RIR quantitative phase analysis."""
    intensities = json.loads(args.phases)
    rir_values = json.loads(args.rir) if args.rir else {k: 1.0 for k in intensities}
    weight_fractions = rir_quantify(intensities, rir_values)
    return {
        "weight_fractions": {k: float(v) for k, v in weight_fractions.items()},
    }


def _load_report_json(path: str) -> Report:
    """Read a report JSON file written by :meth:`Report.to_json`.

    ``Report.from_dict`` is deliberately lenient (missing sections fall back to
    empty objects), so a *different* JSON document — e.g. the result summary
    printed by ``search --json`` / ``run --json`` — would silently produce an
    empty report.  Validate the shape here and fail with an actionable message
    instead (the CLI is the user-facing boundary).
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"report file not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"report file is not valid JSON: {p} ({exc})") from exc
    if not isinstance(data, dict) or not (
        {"sample_info", "peak_list", "candidate_list"} & set(data)
    ):
        raise ValueError(
            f"{p} 不是 XinMatch 报告 JSON（缺 sample_info / peak_list / "
            "candidate_list 段）。--input-report 需要 Report.to_json() 写出的"
            "文件；search / run 的 --json 输出是检索结果摘要，不含报告章节。"
        )
    return Report.from_dict(data)


def cmd_report(args: argparse.Namespace) -> dict[str, Any]:
    """``xinmatch report`` — render a phase-analysis report.

    Reads a report JSON file written by :meth:`Report.to_json` (``--input-report``)
    or builds a minimal report from a pattern file.
    """
    fmt = (args.format or "html").lower()
    ext = "txt" if fmt == "text" else ("md" if fmt in ("md", "markdown") else "html")

    if args.input_report:
        report = _load_report_json(args.input_report)
        default_out = Path(args.input_report).with_name(
            Path(args.input_report).stem + f"-report.{ext}"
        )
    elif args.pattern_file:
        pattern = load_pattern(args.pattern_file)
        _processed, peaks = auto_process(pattern)
        sample_info = SampleInfo(
            sample_name=Path(args.pattern_file).stem,
            wavelength=pattern.wavelength,
        )
        report = Report.now(
            sample_info=sample_info,
            peak_list=PeakListSection(peaks=peaks),
        )
        default_out = Path(args.pattern_file).with_suffix(f".{ext}")
    else:
        raise ValueError(
            "report 需要 positional pattern_file 或 --input-report <report.json> "
            "中的一个（得到的是 None）。"
        )

    if fmt == "text":
        content = render_text(report)
    elif fmt in ("md", "markdown"):
        content = render_markdown(report)
    else:
        content = render_html(report)

    out_path = Path(args.output) if args.output else default_out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return {
        "format": fmt,
        "output": str(out_path),
        "bytes": len(content),
    }


def cmd_run(args: argparse.Namespace) -> dict[str, Any]:
    """``xinmatch run`` — one-shot full analysis pipeline."""
    pattern = load_pattern(args.pattern_file)
    if args.wavelength is not None:
        pattern.wavelength = float(args.wavelength)
    _processed, peaks = auto_process(pattern)
    sample_elements = getattr(args, "sample_elements", None)
    restraints = _load_restraints(args.restraints, sample_elements)

    conn = open_search_database(args.db)
    try:
        candidates = search_match(
            peaks,
            conn,
            pattern.wavelength,
            restraints=restraints,
            top_n=args.top_n,
        )
    finally:
        conn.close()

    # Quantification: top candidate with unit RIR.
    weight_fractions: dict[str, float] = {}
    if candidates:
        top = candidates[0]
        phase_name = top.entry.mineral_name or top.entry.formula or top.entry.entry_id
        main_intensity = max((p.intensity for p in peaks), default=0.0)
        if main_intensity > 0:
            weight_fractions = rir_quantify(
                {phase_name: main_intensity}, {phase_name: 1.0}
            )

    # Build report.
    sample_info = SampleInfo(
        sample_name=Path(args.pattern_file).stem,
        wavelength=pattern.wavelength,
    )
    cand_section = CandidateListSection(
        candidates=[
            CandidateEntry(
                entry_id=c.entry.entry_id,
                formula=c.entry.formula,
                name=c.entry.mineral_name or "",
                fom=c.fom,
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
    report.quant_result.weight_fractions = dict(weight_fractions)

    # Render report.
    fmt = (args.format or "html").lower()
    if fmt == "text":
        content = render_text(report)
    elif fmt in ("md", "markdown"):
        content = render_markdown(report)
    else:
        content = render_html(report)

    out_path = args.output
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(content, encoding="utf-8")

    result: dict[str, Any] = {
        "file": str(args.pattern_file),
        "db": str(args.db),
        "n_peaks": len(peaks),
        "n_candidates": len(candidates),
        "top_candidate": (
            candidates[0].entry.entry_id if candidates else None
        ),
        "weight_fractions": {k: float(v) for k, v in weight_fractions.items()},
        "report": str(out_path),
    }
    if sample_elements:
        # 与 cmd_search 保持一致：只在显式给出时回显，默认输出零变化。
        result["sample_elements"] = sample_elements
    return result


def cmd_batch(args: argparse.Namespace) -> dict[str, Any]:
    """``xinmatch batch`` — run a JSON/YAML batch config (T14.3).

    Delegates to :mod:`xinmatch.core.batch`; per-sample reports and the
    batch summary are written to the paths in the config's ``output``
    block.  Returns the aggregated batch result (JSON when ``--json``).

    ``core.batch.run_batch`` prints human-readable progress lines to stdout;
    in ``--json`` mode those are redirected to stderr so stdout stays one
    parseable JSON document (see :func:`_progress_to_stderr`).
    """
    config, config_dir = load_batch_config(args.config)
    if getattr(args, "as_json", False):
        with _progress_to_stderr():
            batch = run_batch(config, config_dir=config_dir)
    else:
        batch = run_batch(config, config_dir=config_dir)
    return batch.to_dict()


# ---------------------------------------------------------------------------
# instrument (T14.4)
# ---------------------------------------------------------------------------
class _LivePlotter:
    """Minimal matplotlib live-plot helper for ``instrument collect``.

    Appends points as they arrive and refreshes the axes in batches.
    matplotlib is imported lazily; if it is unavailable the constructor
    degrades to a no-op (``enabled=False``) instead of raising, so a
    headless / stripped environment can still collect data.
    """

    def __init__(self) -> None:
        self.enabled = False
        self._xs: list[float] = []
        self._ys: list[float] = []
        self._line: Any = None
        self._fig: Any = None
        self._ax: Any = None
        try:
            import matplotlib.pyplot as plt  # noqa: PLC0415

            if not plt.isinteractive():
                plt.ion()
            self._fig, self._ax = plt.subplots(figsize=(8, 4))
            self._ax.set_xlabel("2θ (°)")
            self._ax.set_ylabel("Intensity (counts)")
            self._ax.set_title("XinMatch — serial data stream")
            (self._line,) = self._ax.plot([], [], "-", lw=1.0)
            self.enabled = True
        except ImportError:  # pragma: no cover — env-dependent
            print(
                "warning: matplotlib not available — live plot disabled "
                "(data collection continues)",
                file=sys.stderr,
            )

    def append(self, point: DataPoint) -> None:
        if not self.enabled:
            return
        self._xs.append(point.two_theta)
        self._ys.append(point.intensity)
        # Refresh in batches to keep the UI responsive on fast streams.
        if len(self._xs) % 25 == 0:
            self._line.set_data(self._xs, self._ys)
            self._ax.relim()
            self._ax.autoscale_view()
            self._fig.canvas.draw_idle()
            self._fig.canvas.flush_events()

    def finish(self) -> None:
        if not self.enabled or not self._xs:
            return
        self._line.set_data(self._xs, self._ys)
        self._ax.relim()
        self._ax.autoscale_view()
        self._fig.canvas.draw()
        try:
            import matplotlib.pyplot as plt  # noqa: PLC0415

            plt.show(block=False)
        except ImportError:  # pragma: no cover
            pass


def cmd_libraries(args: argparse.Namespace) -> dict[str, Any]:
    """``xinmatch libraries`` — list / mount / unmount ``.xinDB`` reference libraries.

    Actions (mutually exclusive, default = list):

    * ``--add PATH``   mount a ``.xinDB`` file from any folder;
    * ``--remove ID``  unmount a previously added library (file untouched).

    v3.0.0 只支持 ``.xinDB``：旧的 ``.sqlite`` / ``.db`` 库（含 PDF-2 dump 与
    PolyXRD phases 库）已经不能挂载，也没有"建转换索引"这一步了 —— 列存库是
    自包含的，挂上即可检索。
    """
    action = "list"
    payload: dict[str, Any] = {}

    if args.add:
        action = "add"
        ext = add_external_library(args.add, label=args.label)
        payload = {
            "library": {
                "id": ext.id,
                "path": str(ext.path),
                "label": ext.display_name,
            }
        }
    elif args.remove:
        action = "remove"
        payload = {"removed": remove_external_library(args.remove), "id": args.remove}

    records = [
        {
            "id": r.id,
            "name": r.display_name,
            "kind": r.kind,
            "path": str(r.path),
            "available": r.available,
            "default": r.default,
            "external": r.external,
            "entries": r.entry_count,
            "reason": r.unavailable_reason,
        }
        for r in list_libraries()
    ]

    if not getattr(args, "as_json", False):
        print(f"{'ID':<20} {'OK':<3} {'ENTRIES':>9}  {'':<7} PATH")
        for rec in records:
            flag = "yes" if rec["available"] else "no"
            tag = "默认" if rec["default"] else ("外部" if rec["external"] else "")
            entries = rec["entries"] if rec["entries"] is not None else "-"
            print(f"{rec['id']:<20} {flag:<3} {entries:>9}  {tag:<7} {rec['path']}")
            if rec["reason"]:
                print(f"{'':<20} {'':<3} {'':>9}  {'':<7} └─ {rec['reason']}")
        # 表格已经是完整的人类可读输出，不需要 _emit 再重复一遍
        # "action: list / libraries: N item(s)" 的通用摘要。
        if action == "add":
            print(f"已挂载：{payload['library']['id']}  {payload['library']['path']}")
        elif action == "remove":
            print(
                f"已移除挂载：{args.remove}（removed={payload['removed']}；"
                "库文件不会被删除）"
            )
        args._output_printed = True
    return {"action": action, **payload, "libraries": records}


def cmd_instrument_scan(args: argparse.Namespace) -> dict[str, Any]:
    """``xinmatch instrument scan`` — enumerate visible serial ports.

    Returns the port list; each entry carries ``device``, ``description``
    and ``hwid``.  When no serial stack is available the result is an
    empty list with a warning (not an error), so scripts can degrade
    gracefully on machines without serial hardware.
    """
    from xinmatch.core.instrument import list_serial_ports

    ports = list_serial_ports()
    return {"ports": [p.to_dict() for p in ports], "count": len(ports)}


def cmd_instrument_collect(args: argparse.Namespace) -> dict[str, Any]:
    """``xinmatch instrument collect`` — stream points from a serial port.

    Opens the port, reads ASCII lines, parses each into (2θ, I) and
    persists them to ``--out`` (two-column ASCII, one point per line).
    ``--seconds`` / ``--max-points`` bound the acquisition; Ctrl+C stops
    early.  When ``--out`` is omitted the points go to stdout as JSON
    lines (with ``--json``, the full summary is printed at the end).
    """
    from xinmatch.core.instrument import (
        DataPoint,  # noqa: F401 — used in _on_point type annotation
        SerialCollector,
        SerialConfig,
        open_serial,
    )

    config = SerialConfig(
        port=args.port,
        baudrate=args.baudrate,
        bytesize=args.bytesize,
        parity=args.parity,
        stopbits=args.stopbits,
        timeout=args.timeout,
    )
    serial_obj = open_serial(
        config.port,
        baudrate=config.baudrate,
        bytesize=config.bytesize,
        parity=config.parity,
        stopbits=config.stopbits,
        timeout=config.timeout,
    )
    collector: SerialCollector | None = None

    # Optional live plotting (ROADMAP T14.4 acceptance: "能接收串口数据流
    # 并实时绘制").  matplotlib is lazy-imported; without it the flag degrades
    # to the verbose progress line instead of failing the acquisition.
    live_plot = _LivePlotter() if args.live_plot else None

    def _on_point(point: DataPoint) -> None:
        # Real-time progress on stderr so stdout stays clean for data/JSON.
        if args.verbose and collector is not None:
            print(
                f"\rpoints={collector.n_parsed} skipped={collector.n_skipped} "
                f"last=({point.two_theta:.4f}, {point.intensity:.4f})",
                end="",
                file=sys.stderr,
            )
        if live_plot is not None:
            live_plot.append(point)

    collector = SerialCollector(serial_obj, on_point=_on_point)
    try:
        collector.collect(
            seconds=args.seconds if args.seconds > 0 else None,
            max_points=args.max_points if args.max_points > 0 else None,
        )
    except KeyboardInterrupt:
        if args.verbose:
            print(file=sys.stderr)
    finally:
        serial_obj.close()
        if live_plot is not None:
            live_plot.finish()

    if args.verbose:
        print(file=sys.stderr)

    # Persist to file (two-column ASCII, importable by XinMatch).
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8", newline="\n") as fh:
            collector.write_points(fh)
        data_path = str(out_path)
    else:
        data_path = None
        if args.as_json:
            for p in collector.points:
                print(json.dumps(p.to_dict()))
        else:
            for p in collector.points:
                print(f"{p.two_theta:.5f} {p.intensity:.4f}")

    return {
        "port": config.port,
        "raw_lines": collector.n_raw_lines,
        "points": collector.n_parsed,
        "skipped": collector.n_skipped,
        "data_file": data_path,
        "first": (
            collector.points[0].to_dict() if collector.points else None
        ),
        "last": (
            collector.points[-1].to_dict() if collector.points else None
        ),
    }


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
def _add_json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit structured JSON instead of human-readable output.",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="xinmatch",
        description=(
            "XinMatch — powder XRD phase analysis. Subcommands: import, "
            "process, search, quantify, report, run, batch, libraries, "
            "instrument."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- global --version（v3.4.0 联合计划 X-5：`--version` 必须直接报版本号） ---
    # 冻结包尤其需要它：没有 pyproject.toml 时，唯一可靠的版本来源就是
    # xinmatch.__version__（冻结态取 __init__._FALLBACK_VERSION）。
    def _version_string() -> str:
        from xinmatch import __version__

        return f"xinmatch {__version__}"

    parser.add_argument(
        "--version", "-V", action="version", version=_version_string(),
        help="Print the XinMatch version and exit.",
    )

    # --- import ---
    p_import = sub.add_parser("import", help="Import a diffraction pattern file.")
    p_import.add_argument("pattern_file", help="Path to the pattern file.")
    p_import.add_argument(
        "--wavelength", type=float, default=None,
        help="Override radiation wavelength (Å).",
    )
    _add_json_flag(p_import)
    p_import.set_defaults(func=cmd_import)

    # --- process ---
    p_proc = sub.add_parser(
        "process", help="Run the automatic raw-data processing pipeline."
    )
    p_proc.add_argument("pattern_file", help="Path to the pattern file.")
    p_proc.add_argument(
        "--wavelength", type=float, default=None,
        help="Override radiation wavelength (Å).",
    )
    p_proc.add_argument(
        "--smooth", action="store_true", default=None,
        help="Enable smoothing.",
    )
    p_proc.add_argument(
        "--no-smooth", dest="smooth", action="store_false",
        help="Disable smoothing.",
    )
    p_proc.add_argument(
        "--background", action="store_true", default=None,
        help="Enable background estimation/subtraction.",
    )
    p_proc.add_argument(
        "--no-background", dest="background", action="store_false",
        help="Disable background estimation/subtraction.",
    )
    p_proc.add_argument(
        "--alpha2", action="store_true", default=None,
        help="Enable Kα2 stripping.",
    )
    p_proc.add_argument(
        "--no-alpha2", dest="alpha2", action="store_false",
        help="Disable Kα2 stripping.",
    )
    _add_json_flag(p_proc)
    p_proc.set_defaults(func=cmd_process)

    # --- search ---
    p_search = sub.add_parser(
        "search", help="Run search-match against a reference database."
    )
    p_search.add_argument("pattern_file", help="Path to the pattern file.")
    p_search.add_argument(
        "--db", required=True,
        help="Path to the reference library (.xinDB file).",
    )
    p_search.add_argument(
        "--wavelength", type=float, default=None,
        help="Override radiation wavelength (Å).",
    )
    # 元素约束两种写法互斥：完整 JSON（表达力强但要手写 113 个 EXCLUDE 键）
    # vs 「样品元素」快捷参数（一行文本，走 core 的补集语义）。同时给出时
    # argparse 直接报 usage error，不靠 _load_restraints 里的静默优先级。
    p_search_chem = p_search.add_mutually_exclusive_group()
    p_search_chem.add_argument(
        "--restraints", default=None,
        help="JSON string of Restraints (see Restraints.to_dict).",
    )
    p_search_chem.add_argument(
        "--sample-elements", default=None, metavar="SYMBOLS",
        help="XRF/EDS 检出的元素符号（如 'Zn Al Ca O F'，空格/逗号/顿号分隔）；"
             "其余元素自动标为排除（EXCLUDE），检出元素保持可选。与 --restraints"
             " 互斥；只在 peaks 模式生效（--mode fpfm 下会明确报错）。大库"
             "（>=20 万相）建议填写，见基准报告 §23 / §24。",
    )
    p_search.add_argument(
        "--top-n", type=int, default=20,
        help="Maximum number of candidates to return (default 20).",
    )
    p_search.add_argument(
        "--mode", choices=("peaks", "fpfm", "smpf"), default="peaks",
        help="检索模式：peaks=峰列表 FoM（默认，先寻峰）；fpfm=FPFM 全谱拟合"
        "（不寻峰，直接拟合原始谱；v1.6.1 前的旧称 smpf 仍被接受）。",
    )
    p_search.add_argument(
        "--single-kalpha", action="store_true",
        help="FPFM 模式：关闭 Kα2 伴线（单线模型）。合成谱 / 已剥离 Kα2 的"
        "数据必须加此开关，否则正确相排名被压低。",
    )
    p_search.add_argument(
        "--kalpha1", type=float, default=0.0,
        help="FPFM 模式：Kα1 波长（Å，默认 0 = 跟随图谱自身波长）。",
    )
    p_search.add_argument(
        "--kalpha2", type=float, default=1.5444,
        help="FPFM 模式：Kα2 波长（Å，默认 Cu 1.5444）。",
    )
    p_search.add_argument(
        "--prescreen-n", type=int, default=None,
        help="FPFM 模式：峰列表预筛保留的候选数（默认用内置值 150）。",
    )
    _add_json_flag(p_search)
    p_search.set_defaults(func=cmd_search)

    # --- quantify ---
    p_quant = sub.add_parser(
        "quantify", help="Run RIR quantitative phase analysis."
    )
    p_quant.add_argument(
        "--phases", required=True,
        help='JSON: {"phase_name": main_peak_intensity, ...}',
    )
    p_quant.add_argument(
        "--rir", default=None,
        help='JSON: {"phase_name": rir_value, ...} (defaults to 1.0 each).',
    )
    _add_json_flag(p_quant)
    p_quant.set_defaults(func=cmd_quantify)

    # --- report ---
    p_rep = sub.add_parser("report", help="Render a phase-analysis report.")
    p_rep.add_argument(
        "pattern_file", nargs="?", default=None,
        help="Path to the pattern file (used when --input-report is absent).",
    )
    p_rep.add_argument(
        "--input-report", default=None,
        help="Path to a JSON report file (produced by search --json / run --json).",
    )
    p_rep.add_argument(
        "--output", "-o", default=None,
        help="Output report path (default: <pattern>.html).",
    )
    p_rep.add_argument(
        "--format", choices=["html", "text", "md"], default="html",
        help="Report format (default html).",
    )
    _add_json_flag(p_rep)
    p_rep.set_defaults(func=cmd_report)

    # --- run ---
    p_run = sub.add_parser(
        "run", help="One-shot pipeline: import → process → search → quantify → report."
    )
    p_run.add_argument("pattern_file", help="Path to the pattern file.")
    p_run.add_argument(
        "--db", required=True,
        help="Path to the reference library (.xinDB file).",
    )
    p_run.add_argument(
        "--output", "-o", required=True, help="Output report path.",
    )
    p_run.add_argument(
        "--format", choices=["html", "text", "md"], default="html",
        help="Report format (default html).",
    )
    p_run.add_argument(
        "--wavelength", type=float, default=None,
        help="Override radiation wavelength (Å).",
    )
    p_run_chem = p_run.add_mutually_exclusive_group()
    p_run_chem.add_argument(
        "--restraints", default=None,
        help="JSON string of Restraints.",
    )
    p_run_chem.add_argument(
        "--sample-elements", default=None, metavar="SYMBOLS",
        help="XRF/EDS 检出的元素符号（如 'Zn Al Ca O F'）；其余元素自动排除。"
             "与 --restraints 互斥，语义同 search --sample-elements。",
    )
    p_run.add_argument(
        "--top-n", type=int, default=20,
        help="Maximum number of candidates (default 20).",
    )
    _add_json_flag(p_run)
    p_run.set_defaults(func=cmd_run)

    # --- batch ---
    p_batch = sub.add_parser(
        "batch", help="Run a JSON/YAML batch config over multiple samples (T14.3)."
    )
    p_batch.add_argument(
        "config", help="Path to the batch config (.yaml/.yml/.json).",
    )
    _add_json_flag(p_batch)
    p_batch.set_defaults(func=cmd_batch)

    # --- libraries (v3.0.0: .xinDB only) ---
    p_lib = sub.add_parser(
        "libraries",
        help="List / mount / unmount .xinDB reference libraries (any folder).",
        description=(
            "Manage reference libraries.  Without an action the current registry is "
            "listed; --add mounts a .xinDB file from any folder; --remove unmounts "
            "(the library file is never touched)."
        ),
    )
    p_lib.add_argument("--label", help="Display label for --add (default: file stem).")
    # --add / --remove 是互斥动作（默认 = 列出）；同时给出时 argparse 直接报
    # usage error（exit 2），而不是静默只执行 --add。
    p_lib_actions = p_lib.add_mutually_exclusive_group()
    p_lib_actions.add_argument(
        "--add", metavar="PATH", help="Mount a .xinDB file from any folder."
    )
    p_lib_actions.add_argument(
        "--remove", metavar="ID", help="Unmount the given library id."
    )
    _add_json_flag(p_lib)
    p_lib.set_defaults(func=cmd_libraries)

    # --- instrument (T14.4) ---
    p_inst = sub.add_parser(
        "instrument",
        help="Serial instrument control: scan ports / collect data (T14.4).",
    )
    inst_sub = p_inst.add_subparsers(dest="instrument_action", required=True)

    p_scan = inst_sub.add_parser("scan", help="Enumerate visible serial ports.")
    _add_json_flag(p_scan)
    p_scan.set_defaults(func=cmd_instrument_scan)

    p_collect = inst_sub.add_parser(
        "collect", help="Stream (2θ, I) points from a serial port to a file."
    )
    p_collect.add_argument("--port", required=True, help="Serial port (COM3 / /dev/ttyUSB0).")
    p_collect.add_argument("--baud", dest="baudrate", type=int, default=9600,
                           help="Baud rate (default 9600).")
    p_collect.add_argument("--bytesize", type=int, default=8,
                           choices=(5, 6, 7, 8), help="Data bits (default 8).")
    p_collect.add_argument("--parity", default="N", choices=("N", "E", "O", "M", "S"),
                           help="Parity (default N).")
    p_collect.add_argument("--stopbits", type=float, default=1.0,
                           choices=(1.0, 1.5, 2.0), help="Stop bits (default 1).")
    p_collect.add_argument("--timeout", type=float, default=1.0,
                           help="Read-line timeout seconds (default 1.0).")
    p_collect.add_argument("--seconds", type=float, default=0.0,
                           help="Stop after N seconds (0 = no time cap).")
    p_collect.add_argument("--max-points", type=int, default=0,
                           help="Stop after N parsed points (0 = no cap).")
    p_collect.add_argument("--out", "-o", default=None,
                           help="Output two-column ASCII file (default: stdout).")
    p_collect.add_argument("--verbose", action="store_true",
                           help="Print live progress to stderr.")
    p_collect.add_argument("--live-plot", action="store_true",
                           help="Plot points in real time (matplotlib; "
                                "degrades gracefully when unavailable).")
    _add_json_flag(p_collect)
    p_collect.set_defaults(func=cmd_instrument_collect)

    return parser


def _configure_stdio() -> None:
    """Force UTF-8 on stdout/stderr so help texts containing non-ASCII
    characters (e.g. "Å") do not crash on Windows GBK consoles / PyInstaller
    bundles (UnicodeEncodeError).  Lossy replacement keeps the CLI usable
    even if the terminal cannot display the glyph."""
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            with contextlib.suppress(OSError, ValueError):
                stream.reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Parameters
    ----------
    argv:
        Argument list (defaults to ``sys.argv[1:]``).

    Returns
    -------
    int
        Process exit code (0 on success, non-zero on error).
    """
    _configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = args.func(args)
    except FileNotFoundError as exc:
        # 输入文件 / 库文件不存在是最常见的用户错误；核心层有的抛
        # ``FileNotFoundError(path)``（消息只有路径），这里补一句中文前缀，
        # 已有的 "not found" 消息（如 open_search_database）保持原样。
        message = str(exc)
        if "not found" not in message.lower() and "不存在" not in message:
            message = f"文件不存在：{message}"
        print(f"error: {message}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — CLI top-level error boundary
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # 少数子命令（libraries 文本模式）自己打印了表格/结果，跳过通用摘要，
    # 避免同一份信息输出两遍；--json 模式永远走 _emit。
    if not getattr(args, "_output_printed", False):
        _emit(result, getattr(args, "as_json", False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
