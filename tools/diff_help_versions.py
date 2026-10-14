"""Diff two extractions of the reference-software help library (T0.2).

Compares the 4.2.329 topic set (``docs/third-party-help/``) against a newer
extraction (e.g. ``docs-4.3.360/``) and writes a structured markdown report.

Two comparison layers, because the 4.2.329 extraction was lossy (bold and
link markup dropped) while the current extractor preserves markup:

* *markup-level* changes — anything differs after whitespace normalization
  (mostly converter fidelity, not real doc changes);
* *substantive* changes — still differ after stripping all markdown
  formatting; these are real content edits between the versions.

Usage::

    python tools/diff_help_versions.py --old <dir> --new <dir> --out <report.md>
"""

from __future__ import annotations

import argparse
import difflib
import re
from pathlib import Path

# Bookkeeping topics that are not user-facing documentation.
_NOISE = {"Default", "toc"}


def _strip_provenance(text: str) -> list[str]:
    return [line for line in text.splitlines() if not line.strip().startswith("> Source:")]


def normalize(text: str) -> str:
    """Whitespace-collapsed body (provenance line removed)."""
    return re.sub(r"\s+", " ", "\n".join(_strip_provenance(text))).strip()


def strip_markup(text: str) -> str:
    """Remove markdown formatting so only words remain."""
    s = normalize(text)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)  # links -> label
    s = re.sub(r"`+", "", s)                         # code spans
    s = s.replace("**", "").replace("*", "")         # bold/italic
    s = re.sub(r"^#+\s*", "", s, flags=re.M)         # heading markers
    s = re.sub(r"^\s*[-|]\s*", "", s, flags=re.M)    # list/table markers
    return re.sub(r"\s+", " ", s).strip()


def changed_percent(old: str, new: str) -> float:
    sm = difflib.SequenceMatcher(None, old, new)
    return round((1 - sm.ratio()) * 100, 1)


def topic_summary(path: Path) -> str:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for line in lines:
        s = line.strip()
        if s and not s.startswith(("#", ">")):
            return s[:120]
    return ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    old_dir, new_dir = Path(args.old), Path(args.new)
    old_files = {p.name: p for p in old_dir.glob("*.md")}
    new_files = {p.name: p for p in new_dir.glob("*.md")}

    added = sorted(set(new_files) - set(old_files))
    removed = sorted(set(old_files) - set(new_files))
    common = sorted(set(old_files) & set(new_files))

    markup_changed: list[tuple[str, float]] = []
    substantive: list[tuple[str, float]] = []
    for name in common:
        old_t = old_files[name].read_text(encoding="utf-8")
        new_t = new_files[name].read_text(encoding="utf-8")
        if normalize(old_t) != normalize(new_t):
            markup_changed.append((name, changed_percent(normalize(old_t), normalize(new_t))))
        if strip_markup(old_t) != strip_markup(new_t):
            substantive.append((name, changed_percent(strip_markup(old_t), strip_markup(new_t))))
    markup_changed.sort(key=lambda x: -x[1])
    substantive.sort(key=lambda x: -x[1])

    lines: list[str] = [
        "# 参考软件 帮助库版本差异分析（4.2.329 vs 最新版）",
        "",
        f"> 旧版：{old_dir}（4.2.329 提取，{len(old_files)} 主题）",
        f"> 新版：{new_dir}（最新版提取，{len(new_files)} 主题）",
        f"> 生成：{__import__('datetime').date.today().isoformat()}（T0.2）",
        "",
        "> 注：4.2.329 提取丢失加粗/链接等标记，故报告区分「标记级差异」（提取器保真度差异）",
        "> 与「实质文本变更」（剥离全部 Markdown 标记后仍不同的内容）两层。",
        "",
        "## 摘要",
        "",
        "| 类别 | 数量 |",
        "|---|---|",
        f"| 新增主题 | {len(added)} |",
        f"| 删除主题 | {len(removed)} |",
        f"| 实质文本变更 | {len(substantive)} |",
        f"| 仅标记级差异（实质文本相同） | {len(markup_changed) - len(substantive)} |",
        f"| 内容完全不变 | {len(common) - len(markup_changed)} |",
        "",
    ]

    if added:
        lines += ["## 新增主题", ""]
        for name in added:
            lines += [f"- **{name}** — {topic_summary(new_dir / name)}", ""]
    if removed:
        lines += ["## 删除主题", ""]
        for name in removed:
            lines += [f"- {name}", ""]
    if substantive:
        lines += ["## 实质文本变更主题（按变化程度降序）", "", "| 主题 | 变化 % |", "|---|---|"]
        for name, pct in substantive:
            lines.append(f"| {name} | {pct} |")
        lines += ["", "> 变化 % 为剥离标记后文本的差异比例；比例高通常意味着该主题在最新版中被重写或扩充。", ""]
    if markup_changed:
        lines += [
            "## 仅标记级差异的主题（实质文本相同）",
            "",
            f"以下 {len(markup_changed) - len(substantive)} 篇在剥离格式标记后内容一致，差异全部来自"
            "提取器保真度（旧版丢失加粗/链接），不构成功能变更：",
            "",
        ]
        markup_only = [n for n, _ in markup_changed if n not in {x[0] for x in substantive}]
        lines += [", ".join(markup_only[:40]), ""]
        if len(markup_only) > 40:
            lines += [f"… 其余 {len(markup_only) - 40} 篇略。", ""]

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(
        f"report -> {args.out}  (added={len(added)} removed={len(removed)} "
        f"substantive={len(substantive)} markup-only={len(markup_changed) - len(substantive)})"
    )


if __name__ == "__main__":
    main()
