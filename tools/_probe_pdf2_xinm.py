"""PDF-2 真实链路验收（联合计划 S2）：真实 PDF2 条目 + 真实 COD 相 → ``.xinm``。

为什么单列一个探针：``tests/io/test_xinm.py`` 里 ``test_export_pdf2_entry_is_pdf2_source``
用的是**合成** PDF2 条目（``Entry`` 手搓），只覆盖 ``_classify_entry`` 的分支，
不证明「真实 PDF2 库里的 ``PDF2-XXXXXX`` 条目走真实读库路径（``fetch_entry``）→ 导出」
这条链路成立。S2 要的正是后者：接入 PDF2 ``.xinDB`` 后，真实条目能否正确落成
``source="pdf2"``、``structural=false``、不把任何 ICDD 衍生物写进 ``.xinm``。

用法::

    python -m tools._probe_pdf2_xinm \
        --pdf2-db "D:/Project/XRD/XinMatch-DataBase/data/PDF2-20040317.xinDB" \
        --cod-db  "D:/Project/XRD/XinMatch-DataBase/data/COD-Inorg-20261020.xinDB" \
        --spectrum "D:/Project/XRD/test_xrd/txt/5-1.txt" \
        --out ".scratch/s2_pdf2_accept.xinm"

退出码 0 = 全部检查通过，1 = 有 FAIL（逐条打印）。
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np  # noqa: E402

from xinmatch.core.db.reader_v3 import XinDBReader  # noqa: E402
from xinmatch.core.io import load_pattern  # noqa: E402
from xinmatch.core.io.xinm import export_xinm  # noqa: E402
from xinmatch.core.model.entry import CellParams, Entry  # noqa: E402
from xinmatch.core.model.phase import Phase  # noqa: E402
from xinmatch.core.model.project import Project  # noqa: E402
from xinmatch.core.peak.peak_search import find_peaks  # noqa: E402


def _entry_from_reader(reader: XinDBReader, entry_id: str) -> Entry:
    """库 dict → Entry（导出侧只用到 id/formula/mineral/cell/space_group）。"""
    m = reader.fetch_entry(entry_id)
    if m is None:
        raise SystemExit(f"条目不存在或无可读峰：{entry_id}")
    cell = None
    if m["cell_a"] and m["cell_b"] and m["cell_c"]:
        cell = CellParams(
            a=m["cell_a"], b=m["cell_b"], c=m["cell_c"],
            alpha=m["cell_alpha"], beta=m["cell_beta"], gamma=m["cell_gamma"],
        )
    return Entry(
        entry_id=m["entry_id"],
        formula=m["formula"],
        d_spacings=np.array(m["peaks_d_list"], dtype=np.float64),
        intensities=np.array(m["peaks_i_list"], dtype=np.float64),
        mineral_name=m["mineral_name"] or None,
        cell=cell,
        space_group=m["space_group"] or None,
    )


def _check(name: str, ok: bool, detail: str = "") -> tuple[str, bool, str]:
    return (name, ok, detail)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pdf2-db", required=True, type=Path)
    ap.add_argument("--cod-db", required=True, type=Path)
    ap.add_argument("--spectrum", required=True, type=Path)
    ap.add_argument("--pdf2-id", default="PDF2-010837", help="真实 PDF2 卡号（默认方解石 01-0837）")
    ap.add_argument("--cod-id", default="96-210-0189", help="真实 COD 相（默认方解石）")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)

    args.out.parent.mkdir(parents=True, exist_ok=True)

    pat = load_pattern(args.spectrum)
    peaks = find_peaks(pat.two_theta, pat.intensity)
    print(f"谱图：{args.spectrum.name}  {pat.two_theta.size} 点，检出 {len(peaks)} 峰，"
          f"λ={pat.wavelength}")

    with XinDBReader(args.pdf2_db) as pr:
        ok, reason = pr.probe()
        if not ok:
            raise SystemExit(f"PDF2 库 probe 失败：{reason}")
        pdf2_entry = _entry_from_reader(pr, args.pdf2_id)
    with XinDBReader(args.cod_db) as cr:
        ok, reason = cr.probe()
        if not ok:
            raise SystemExit(f"COD 库 probe 失败：{reason}")
        cod_entry = _entry_from_reader(cr, args.cod_id)

    print(f"PDF2 相：{pdf2_entry.entry_id}  {pdf2_entry.formula}  "
          f"cell={'有' if pdf2_entry.cell else 'NULL'}  n_peaks={pdf2_entry.n_peaks}")
    print(f"COD  相：{cod_entry.entry_id}  {cod_entry.formula}  "
          f"space_group={cod_entry.space_group}")

    project = Project(
        patterns=[pat],
        peaks=peaks,
        candidates=[(cod_entry, 0.90), (pdf2_entry, 0.86)],
        selected_phases=[
            Phase(entry=cod_entry, scale_factor=1.0),
            Phase(entry=pdf2_entry, scale_factor=1.0),
        ],
    )

    report = export_xinm(
        project, args.out, app_version="3.4.0-s2accept", cod_root=None)
    print(f"\n导出：{report.summary}")
    for info in report.phases:
        print(f"  - {info.entry_id:<16} source={info.source:<11} "
              f"structural={info.structural} cif={info.cif_member} reason={info.reason!r}")

    # ---- 读回 .xinm 做硬检查 ----
    with zipfile.ZipFile(args.out) as zf:
        names = zf.namelist()
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
    by_id = {p["entry_id"]: p for p in manifest["phases"]}
    p2 = by_id.get(args.pdf2_id, {})
    c1 = by_id.get(args.cod_id, {})
    cif_members = [n for n in names if n.startswith("cifs/")]
    cand_by_id = {c["entry_id"]: c for c in manifest.get("candidates_summary", [])}

    checks = [
        _check("PDF2 相 source == 'pdf2'", p2.get("source") == "pdf2", str(p2.get("source"))),
        _check("PDF2 相 structural == False", p2.get("structural") is False, str(p2.get("structural"))),
        _check("PDF2 相 cif_file == None", p2.get("cif_file") is None, str(p2.get("cif_file"))),
        _check("PDF2 相 reason 含 'PDF-2'", "PDF-2" in (p2.get("reason") or ""), repr(p2.get("reason"))),
        _check("PDF2 相不带参考峰表(d_spacings/intensities/peaks)",
               not ({"d_spacings", "intensities", "peaks"} & set(p2.keys())),
               str(sorted(set(p2.keys())))),
        _check("COD 相 source == 'cod'", c1.get("source") == "cod", str(c1.get("source"))),
        _check("COD 相 structural == True", c1.get("structural") is True, str(c1.get("structural"))),
        _check("COD 相 cif_file 指向 .cif", (c1.get("cif_file") or "").endswith(".cif"), str(c1.get("cif_file"))),
        _check("zip 含 manifest.json + pattern/pattern.csv",
               "manifest.json" in names and "pattern/pattern.csv" in names, str(names)),
        _check("cifs/ 只有 COD 那一份（无 PDF2 衍生文件）",
               len(cif_members) == 1 and not any("PDF2" in n.upper() or "010837" in n for n in cif_members),
               str(cif_members)),
        _check("candidates_summary 里 PDF2 相 source == 'pdf2'",
               cand_by_id.get(args.pdf2_id, {}).get("source") == "pdf2",
               str(cand_by_id.get(args.pdf2_id, {}).get("source"))),
    ]

    print("\n==== S2 验收检查 ====")
    all_ok = True
    for name, ok, detail in checks:
        all_ok &= ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}"
              + (f"   ({detail})" if (detail and not ok) else ""))
    print(f"\n结论：{'全部通过' if all_ok else '存在 FAIL'}  ({sum(1 for _, o, _ in checks if o)}/{len(checks)})")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
