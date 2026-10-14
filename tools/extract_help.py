"""Extract the reference software's Qt help (.qch) into Markdown topics.

T0.1 extracted the 4.2.329 help into ``docs/third-party-help/``; this script
is the reusable extractor so T0.2 can re-run it against a newer installed
version and diff the two topic sets.

Usage::

    python tools/extract_help.py --qch <path.qch> --out <dir> [--version <label>]

The output tree mirrors the old one: one ``.md`` per help topic, named by
stripping the ``idh_`` prefix from the source file name (matching the 4.2.329
extraction's naming, so the version diff aligns 1:1).
"""

from __future__ import annotations

import argparse
import sqlite3
import struct
import zlib
from html.parser import HTMLParser
from pathlib import Path

_QCH_VERSION = "4.3 Build 360"


def quncompress(data: bytes) -> bytes:
    """Qt ``qUncompress``: 4-byte big-endian length + zlib stream."""
    size = struct.unpack(">I", data[:4])[0]
    out = zlib.decompress(data[4:])
    if len(out) != size:
        raise ValueError(f"declared {size} bytes, got {len(out)}")
    return out


class HtmlToMarkdown(HTMLParser):
    """Minimal HTML->Markdown converter (stdlib only).

    Produces clean text comparable to the 4.2.329 extraction: heading
    levels, paragraphs, lists, bold/italic, links and code blocks are
    preserved; tables are flattened to pipe-delimited rows.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self._in_pre = False
        self._in_code = False
        self._in_li = False
        self._in_table_row = False
        self._row_cells: list[str] = []
        self._cell: list[str] = []
        self._skip_depth = 0
        self._pending_blank = False

    def _emit(self, text: str) -> None:
        if self._pending_blank:
            if text.strip():
                self.out.append("")
            self._pending_blank = False
        self.out.append(text)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag in ("script", "style", "nav", "head"):
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "h1":
            self._emit("\n# ")
        elif tag == "h2":
            self._emit("\n## ")
        elif tag == "h3":
            self._emit("\n### ")
        elif tag == "h4":
            self._emit("\n#### ")
        elif tag in ("p", "div", "table", "ul", "ol", "dl"):
            self._pending_blank = True
        elif tag == "br":
            self._emit("\n")
        elif tag == "li":
            self._in_li = True
            self._emit("\n- ")
        elif tag == "tr":
            self._in_table_row = True
            self._row_cells = []
        elif tag in ("td", "th"):
            self._cell = []
        elif tag in ("b", "strong"):
            self._emit("**")
        elif tag in ("i", "em"):
            self._emit("*")
        elif tag == "code":
            self._in_code = True
            self._emit("`")
        elif tag == "pre":
            self._in_pre = True
            self._emit("\n```\n")
        elif tag == "a":
            href = a.get("href", "")
            if href:
                self._emit("[")
                self._href = href
            else:
                self._href = ""

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "nav", "head"):
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag in ("h1", "h2", "h3", "h4"):
            self._emit("\n")
        elif tag == "li":
            self._in_li = False
        elif tag == "tr":
            self._in_table_row = False
            self._emit("\n| " + " | ".join("".join(c).strip() for c in self._row_cells) + " |")
        elif tag in ("td", "th"):
            self._row_cells.append("".join(self._cell))
            self._cell = []
        elif tag in ("b", "strong"):
            self._emit("**")
        elif tag in ("i", "em"):
            self._emit("*")
        elif tag == "code":
            self._in_code = False
            self._emit("`")
        elif tag == "pre":
            self._in_pre = False
            self._emit("\n```\n")
        elif tag == "a" and getattr(self, "_href", ""):
            self._emit(f"]({self._href})")
            self._href = ""

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_table_row:
            self._cell.append(data)
            return
        if self._in_pre:
            self.out.append(data)
            return
        self._emit(data)

    def result(self) -> str:
        text = "".join(self.out)
        # collapse 3+ blank lines
        import re

        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip() + "\n"


def extract(qch: str, out_dir: Path, version: str) -> dict[str, str]:
    """Extract all .htm help topics into Markdown files.

    Returns {topic_stem: title} for every extracted topic.
    """
    db = sqlite3.connect(qch)
    cur = db.cursor()
    cur.execute(
        "SELECT f.Name, f.Title, d.Data FROM FileNameTable f "
        "JOIN FileDataTable d ON d.Id = f.FileId "
        "WHERE f.Name LIKE '%.htm' ORDER BY f.Name"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    titles: dict[str, str] = {}
    for name, title, data in cur.fetchall():
        if not data:
            continue
        stem = name[:-4]
        if stem.startswith("idh_"):
            stem = stem[4:]
        md_name = f"{stem}.md"
        try:
            html = quncompress(data).decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {name}: decompress failed ({exc})")
            continue
        conv = HtmlToMarkdown()
        conv.feed(html)
        body = conv.result()
        header = f"# {title}\n\n> Source: reference software help, version {version} (topic `{name}`).\n"
        (out_dir / md_name).write_text(header + body, encoding="utf-8")
        titles[md_name] = title
    db.close()
    return titles


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--qch", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--version", default=_QCH_VERSION)
    args = ap.parse_args()

    titles = extract(args.qch, Path(args.out), args.version)
    print(f"extracted {len(titles)} topics -> {args.out}")


if __name__ == "__main__":
    main()
