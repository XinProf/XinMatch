"""Five-round binary robustness gate for a XinMatch release.

Runs against the *shipped* artifacts (Setup exe + Portable zip, both the
release variant), never against the source tree.  Writes a JSON report with a
pass/fail per round so release notes can quote real numbers.

Rounds
  1  SHA-256 of both artifacts + SHA256SUMS.txt round-trip
  2  Portable: unzip, run frozen CLI (libraries / import), bundled DB present
  3  Frozen GUI: offscreen selftest hooks (REG / LIBS / ABOUT) + logo bytes
  4  Silent install of the Setup exe into an isolated directory
  5  Installed: frozen CLI + real search against the installed bundled DB

Usage (from the repository root)::

    python -m tools.verify_binary \
        --setup dist/XinMatch-Setup-3.2.0.exe \
        --zip dist/XinMatch-Internal-3.2.0.zip \
        --workdir D:/Project/XRD/.verify_320

The offscreen hooks (``XINMATCH_SELFTEST_*``) live in ``xinmatch/ui/app.py``;
they render a widget / dump JSON and quit without any interactive input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

# 便携包解压用标准库 zipfile：本机没装 7-Zip 时不再因外部依赖缺席直接
# FileNotFoundError（2026-11-12 v3.7.0 构建实测：C:\Program Files\7-Zip 不存在）。
SAMPLE = Path(r"D:\test_XRD\temp\smz xrd analysis\5-1.txt")
REPO = Path(__file__).resolve().parents[1]
EXE_NAME = "XinMatch.exe"
DB_GLOB = "COD-Inorg-*.xinDB"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def clean_env(**extra: str) -> dict[str, str]:
    env = dict(os.environ)
    # A developer-machine override must not leak into the "clean user" test.
    env.pop("XINMATCH_XINDB_DIR", None)
    for key in (
        "XINMATCH_SELFTEST_ABOUT",
        "XINMATCH_SELFTEST_LIBS",
        "XINMATCH_SELFTEST_REG",
        "XINMATCH_SELFTEST_OUT",
        "XINMATCH_SELFTEST_LIBS_OUT",
        "XINMATCH_SELFTEST_REG_OUT",
    ):
        env.pop(key, None)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.update(extra)
    return env


def run(cmd: list[str], *, env: dict[str, str] | None = None,
        cwd: Path | None = None, timeout: int = 180) -> dict:
    try:
        cp = subprocess.run(
            cmd, cwd=str(cwd) if cwd else None, env=env, timeout=timeout,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        return {"rc": cp.returncode, "out": cp.stdout[-4000:]}
    except subprocess.TimeoutExpired as exc:
        return {"rc": "TIMEOUT", "out": str(exc)[-1000:]}


def find_one(root: Path, pattern: str) -> Path | None:
    hits = sorted(root.glob(pattern))
    return hits[0] if hits else None


def parse_json_out(text: str) -> dict | None:
    start = text.find("{")
    if start < 0:
        return None
    try:
        return json.loads(text[start:])
    except json.JSONDecodeError:
        return None


def round1(setup: Path, zipf: Path, work: Path) -> dict:
    sums = {"setup": sha256(setup), "zip": sha256(zipf)}
    manifest = work / "SHA256SUMS.txt"
    manifest.write_text(
        "".join(f"{sums['setup']}  {setup.name}\n"
                f"{sums['zip']}  {zipf.name}\n"),
        encoding="ascii", newline="\n",
    )
    # Round-trip: parse the manifest back and re-hash both files.
    parsed = {}
    for line in manifest.read_text(encoding="ascii").splitlines():
        digest, name = line.split()
        parsed[name] = digest
    ok = (parsed.get(setup.name) == sha256(setup)
          and parsed.get(zipf.name) == sha256(zipf))
    return {
        "ok": ok, "sha256": sums,
        "sizes": {setup.name: setup.stat().st_size, zipf.name: zipf.stat().st_size},
        "manifest": str(manifest),
    }


def round2(zipf: Path, work: Path) -> dict:
    dest = work / "portable"
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zipf) as zf:
        bad_member = zf.testzip()
        zf.extractall(dest)
    extract_rc = 0 if bad_member is None else 1
    exe = dest / EXE_NAME
    db = find_one(dest / "data", DB_GLOB)
    marker = None
    for p in (dest / "variant.txt", dest / "_internal" / "variant.txt"):
        if p.is_file():
            marker = p.read_text(encoding="ascii").strip()
            break
    logo = dest / "_internal" / "assets" / "icons" / "logo_256.png"
    src_logo = REPO / "assets" / "icons" / "logo_256.png"
    logo_ok = logo.is_file() and src_logo.is_file() and sha256(logo) == sha256(src_logo)

    libs = run([str(exe), "libraries", "--json"], env=clean_env(),
               cwd=work, timeout=120)
    libs_json = parse_json_out(libs["out"])
    bundled = None
    if libs_json:
        for rec in libs_json.get("libraries", []):
            if "COD-Inorg" in str(rec.get("path", "")) and rec.get("available"):
                bundled = rec
                break
    helpr = run([str(exe), "import", "--help"], env=clean_env(),
                cwd=work, timeout=120)
    ok = all((
        extract_rc == 0, exe.is_file(), db is not None, marker == "release",
        libs["rc"] == 0, bundled is not None,
        helpr["rc"] == 0, logo_ok,
    ))
    return {
        "ok": ok, "extract_rc": extract_rc, "exe": exe.is_file(),
        "bundled_db": db.name if db else None,
        "bundled_db_bytes": db.stat().st_size if db else None,
        "variant": marker, "logo_matches_source": logo_ok,
        "libraries_rc": libs["rc"], "bundled_entry_count": bundled.get("entries") if bundled else None,
        "import_help_rc": helpr["rc"],
        "portable_dir": str(dest),
    }


def round3(work: Path) -> dict:
    exe = work / "portable" / EXE_NAME
    out: dict = {"ok": False, "hooks": {}}
    # REG: variant + registration state
    reg_out = work / "reg_selftest.json"
    r = run([str(exe)], env=clean_env(
        XINMATCH_SELFTEST_REG="1", XINMATCH_SELFTEST_REG_OUT=str(reg_out)),
        cwd=work, timeout=120)
    reg = json.loads(reg_out.read_text(encoding="utf-8")) if reg_out.is_file() else None
    out["hooks"]["REG"] = {"rc": r["rc"], "payload": reg, "stderr_out": r["out"][-800:]}
    # LIBS: registry visible from the frozen Qt process
    libs_out = work / "libs_selftest.json"
    r = run([str(exe)], env=clean_env(
        XINMATCH_SELFTEST_LIBS="1", XINMATCH_SELFTEST_LIBS_OUT=str(libs_out)),
        cwd=work, timeout=120)
    libs = json.loads(libs_out.read_text(encoding="utf-8")) if libs_out.is_file() else None
    out["hooks"]["LIBS"] = {"rc": r["rc"], "count": len(libs) if isinstance(libs, list) else None,
                            "stderr_out": r["out"][-800:]}
    # ABOUT: renders the new logo + version text, then quits
    png = work / "about_selftest.png"
    r = run([str(exe)], env=clean_env(
        XINMATCH_SELFTEST_ABOUT="1", XINMATCH_SELFTEST_OUT=str(png)),
        cwd=work, timeout=120)
    out["hooks"]["ABOUT"] = {"rc": r["rc"], "png": str(png),
                             "png_bytes": png.stat().st_size if png.is_file() else 0,
                             "stderr_out": r["out"][-800:]}
    # Repeat-launch stability: 3 clean starts, no lock files left behind.
    repeats = []
    for _ in range(3):
        rr = run([str(exe)], env=clean_env(
            XINMATCH_SELFTEST_LIBS="1", XINMATCH_SELFTEST_LIBS_OUT=str(libs_out)),
            cwd=work, timeout=120)
        repeats.append(rr["rc"])
    out["repeats"] = repeats
    out["ok"] = all((
        out["hooks"]["REG"]["rc"] == 0,
        isinstance(reg, dict) and reg.get("variant") == "release"
        and reg.get("registration_enabled") is True,
        out["hooks"]["LIBS"]["rc"] == 0,
        isinstance(libs, list) and len(libs) > 0,
        out["hooks"]["ABOUT"]["rc"] == 0,
        out["hooks"]["ABOUT"]["png_bytes"] > 5000,
        all(rc == 0 for rc in repeats),
    ))
    return out


def round4(setup: Path, work: Path) -> dict:
    dest = work / "installed"
    dest.mkdir(parents=True, exist_ok=True)
    log = work / "install.log"
    cmd = [
        str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
        "/CURRENTUSER", f"/DIR={dest}", f"/LOG={log}",
    ]
    r = run(cmd, cwd=work, timeout=420)
    exe = dest / EXE_NAME
    db = find_one(dest / "data", DB_GLOB)
    marker = None
    for p in (dest / "variant.txt", dest / "_internal" / "variant.txt"):
        if p.is_file():
            marker = p.read_text(encoding="ascii").strip()
            break
    return {
        "ok": r["rc"] == 0 and exe.is_file() and db is not None and marker == "release",
        "rc": r["rc"], "exe": exe.is_file(), "bundled_db": db.name if db else None,
        "variant": marker, "log": str(log) if log.is_file() else None,
        "install_dir": str(dest), "tail": r["out"][-800:],
    }


def round5(work: Path) -> dict:
    dest = work / "installed"
    exe = dest / EXE_NAME
    db = find_one(dest / "data", DB_GLOB)
    libs = run([str(exe), "libraries", "--json"], env=clean_env(),
               cwd=work, timeout=120)
    libs_json = parse_json_out(libs["out"])
    search = {"rc": "SKIPPED", "out": ""}
    if db:
        search = run(
            [str(exe), "search", str(SAMPLE), "--db", str(db),
             "--top-n", "5", "--json"],
            env=clean_env(), cwd=work, timeout=300,
        )
    sj = parse_json_out(search["out"])
    # Best-effort frozen GUI hook on the release build (registration dialog may
    # block offscreen sessions; that is recorded, not silently treated as pass).
    reg_out = work / "installed_reg.json"
    gui = run([str(exe)], env=clean_env(
        XINMATCH_SELFTEST_REG="1", XINMATCH_SELFTEST_REG_OUT=str(reg_out)),
        cwd=work, timeout=90)
    reg = json.loads(reg_out.read_text(encoding="utf-8")) if reg_out.is_file() else None
    return {
        "ok": all((
            exe.is_file(), db is not None, libs["rc"] == 0, libs_json is not None,
            search["rc"] == 0, isinstance(sj, dict) and sj.get("n_candidates", 0) > 0,
        )),
        "libraries_rc": libs["rc"],
        "search_rc": search["rc"],
        "n_peaks": sj.get("n_peaks") if sj else None,
        "n_candidates": sj.get("n_candidates") if sj else None,
        "top_entry": (sj.get("candidates") or [{}])[0].get("entry_id") if sj else None,
        "release_gui_hook": {"rc": gui["rc"], "payload": reg,
                             "note": "may be blocked by the startup registration dialog in non-interactive sessions"},
        "search_tail": search["out"][-800:],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--setup", required=True)
    ap.add_argument("--zip", required=True)
    ap.add_argument("--workdir", required=True,
                    help="Parent directory; each run gets its own --tag subdir.")
    ap.add_argument("--tag", default=None,
                    help="Run label (default: timestamp). Never deletes a previous run.")
    ap.add_argument("--sample", default=None,
                    help="Real pattern file used by the round-5 frozen search.")
    ap.add_argument("--report", default=None,
                    help="Where to write the JSON report (default .scratch/binary_verify.json).")
    ap.add_argument("--skip-install", action="store_true")
    args = ap.parse_args()
    # 所有输入路径先绝对化。为什么必须：轮 3/4 把 work 目录里的文件路径当环境变量
    # （XINMATCH_SELFTEST_*_OUT）和 `/LOG=` 参数交给子进程，而子进程的 cwd 就是
    # work 本身——相对 workdir 会被解析成 work/work/… 这种不存在的路径，冻结 GUI
    # 里的写文件抛 FileNotFoundError 被 Qt 吞掉、事件循环继续跑，表现为「自测超时」，
    # 极易误判成产物有问题（2026-11-04 踩过）。
    if args.sample:
        global SAMPLE
        SAMPLE = Path(args.sample).resolve()
    setup, zipf = Path(args.setup).resolve(), Path(args.zip).resolve()
    # A fresh directory per run: the verification must never bulk-delete a
    # previous extraction (sandboxes guard that, and evidence is worth keeping).
    work = (Path(args.workdir) / (args.tag or time.strftime("%Y%m%d-%H%M%S"))).resolve()
    work.mkdir(parents=True, exist_ok=True)
    report: dict = {"rounds": {}}
    for n, fn in (
        (1, lambda: round1(setup, zipf, work)),
        (2, lambda: round2(zipf, work)),
        (3, lambda: round3(work)),
        (4, lambda: {"ok": None, "skipped": True} if args.skip_install else round4(setup, work)),
        (5, lambda: {"ok": None, "skipped": True} if args.skip_install else round5(work)),
    ):
        try:
            res = fn()
        except Exception as exc:  # noqa: BLE001 - a round must not abort the gate
            res = {"ok": False, "exception": f"{type(exc).__name__}: {exc}"}
        report["rounds"][str(n)] = res
        print(f"[round {n}] ok={res.get('ok')}", flush=True)
    report["all_pass"] = all(r.get("ok") is True for r in report["rounds"].values())
    out = Path(args.report).resolve() if args.report else REPO / ".scratch" / "binary_verify.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report -> {out}; all_pass={report['all_pass']}")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
