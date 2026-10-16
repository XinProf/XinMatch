"""Merge XinMatch project markdown docs into a single organized MD file.

Keeps original content verbatim, adds front matter, TOC and category headers.
"""
from pathlib import Path

ROOT = Path(r"D:\Project\XRD\XinMatch")
OUT = ROOT / "XinMatch项目文档合集.md"

# (relative path, short title for TOC, category)
CATEGORIES = [
    (
        "第一部分 · 项目总览",
        [
            ("README.md", "README — 项目简介"),
            ("ROADMAP_v3.md", "实施路线图 v3.0（合并版）"),
            ("docs/STATUS.md", "Implementation status（实施状态）"),
            ("docs/HANDOVER-20261012.md", "项目转交记录（阶段性总结 · 2026-10-12）"),
            ("docs/HANDOVER.md", "项目转交记录（2026-10-08）"),
        ],
    ),
    (
        "第二部分 · 技术方案与合规",
        [
            ("00_TECH_STACK_ANALYSIS.md", "参考软件技术栈勘察报告"),
            ("01_方案对比与补充.md", "方案对比与补充（评审合并）"),
            ("docs/CONVENTIONS.md", "跨平台编码规范（T0.7）"),
        ],
    ),
    (
        "第三部分 · 功能与算法模型",
        [
            ("FUNCTION_MAP.md", "功能清单（自动提取自帮助数据库）"),
            ("FOM_MODEL.md", "FoM（Figure-of-Merit）定量结构"),
        ],
    ),
    (
        "第四部分 · 打包与工程基线",
        [
            ("docs/PACKAGING.md", "Windows PyInstaller 打包说明"),
            ("docs/打包交付说明-v1.0.0.md", "v1.0.0 打包交付说明"),
            ("docs/mypy_baseline.md", "mypy 类型检查基线（T0.6）"),
        ],
    ),
    (
        "第五部分 · 参考数据库（COD）",
        [
            ("docs/COD多库挂载说明.md", "参考数据库多库挂载说明（v1.0.0）"),
            ("docs/COD全库优选去重库治理.md", "COD 全库优选去重库治理"),
        ],
    ),
    (
        "第六部分 · 检索算法（FPFM）",
        [
            ("docs/fpfm_mechanism.md", "FPFM 机制说明（全谱拟合检索）"),
            ("docs/fpfm_research_notes.md", "FPFM 机制调研笔记"),
        ],
    ),
    (
        "第七部分 · 样品集、测试与质量",
        [
            ("docs/样品集扩充计划-T0.3-T0.4.md", "样品集扩充计划（T0.3 / T0.4）"),
            ("docs/sample_expansion_20261011.md", "样品集扩充验收记录（2026-10-11）"),
            ("docs/l3_traceup_report.md", "L3 黄金基线追平报告（任务 A）"),
            ("docs/pytest_full_run_hang_rootcause.md", "全量 pytest 挂起根因分析与最小修复"),
            ("tests/baseline/match/README.md", "黄金基线目录说明（tests/baseline/match/）"),
            ("tests/fixtures/SAMPLE_INDEX.md", "XRD 样本谱图清单（SAMPLE_INDEX）"),
        ],
    ),
]


def slugify(title: str) -> str:
    """GitHub-style anchor slug for Chinese+ASCII titles."""
    import unicodedata

    s = title.strip().lower()
    s = unicodedata.normalize("NFKC", s)
    out = []
    for ch in s:
        if ch.isalnum() or ch in "_-":
            out.append(ch)
        elif ch.isspace():
            out.append("-")
    slug = "".join(out).strip("-")
    return slug


def read_md(rel: str) -> str:
    p = ROOT / rel
    text = p.read_text(encoding="utf-8-sig")
    return text.rstrip("\n")


def build() -> str:
    lines = []
    lines.append("# XinMatch 项目文档合集")
    lines.append("")
    lines.append(
        "> **整理日期**：2026-10-12　**整理方式**：现行文档去重整理"
    )
    lines.append(
        "> **收录范围**：XinMatch 项目现行有效 Markdown 文档 23 份，按主题分类合并，"
        "每份文档保留原文内容。"
    )
    lines.append(
        "> **去重说明**：已去除历史版本 `ROADMAP.md`（v1）与 `ROADMAP_v2_综合升级版.md`；"
        "`FUNCTION_MAP_v43.md` 与 `FUNCTION_MAP.md` 内容相同，仅保留一份；"
        "docs/ 下 `l3_golden_*.html/.json` 为程序化报告产物，未纳入本文档。"
    )
    lines.append("")
    lines.append("## 目录")
    lines.append("")
    for cat, docs in CATEGORIES:
        lines.append(f"- {cat}")
        for i, (rel, title) in enumerate(docs, 1):
            anchor = slugify(title)
            lines.append(f"  - {i}. [{title}](#{anchor})")
    lines.append("")
    lines.append("---")
    lines.append("")

    for cat, docs in CATEGORIES:
        lines.append(f"## {cat}")
        lines.append("")
        for rel, title in docs:
            content = read_md(rel)
            lines.append(f"> **来源文档**：`{rel}`")
            lines.append("")
            lines.append(content)
            lines.append("")
            lines.append("---")
            lines.append("")
    return "\n".join(lines)


def main() -> None:
    text = build()
    OUT.write_text(text, encoding="utf-8")
    n_docs = sum(len(docs) for _, docs in CATEGORIES)
    print(f"written: {OUT}")
    print(f"docs merged: {n_docs}")
    print(f"size: {len(text.encode('utf-8'))} bytes, {text.count(chr(10)) + 1} lines")


if __name__ == "__main__":
    main()
