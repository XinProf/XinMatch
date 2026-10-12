"""Convert the merged XinMatch project MD into a formatted DOCX.

Handles headings, paragraphs, blockquotes, fenced/indented code, pipe tables,
bulleted/ordered lists (with native Word numbering), inline markdown
(bold/italic/code/links), emoji -> neutral text mapping, Chinese smart quotes,
a refreshable Word TOC field, A4 layout, and per-section page numbering.

Output: D:\\Project\\XRD\\XinMatch\\XinMatch项目文档合集.docx
"""
from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

SRC = Path(r"D:\Project\XRD\XinMatch\XinMatch项目文档合集.md")
OUT = Path(r"D:\Project\XRD\XinMatch\XinMatch项目文档合集.docx")

# ---------------------------------------------------------------------------
# emoji -> neutral text/symbol mapping (Word deliverable keeps a formal look)
# ---------------------------------------------------------------------------
EMOJI_MAP = {
    "\U00002705": "✓",   # ✅
    "\U0001F7E1": "◐",   # 🟡
    "\U0001F534": "●",   # 🔴
    "\U0001F7E2": "○",   # 🟢
    "\U00002B50": "★",   # ⭐
    "\U00002B1C": "□",   # ⬜
    "\U0000274C": "✗",   # ❌
    "\U000026D4": "×",   # ⛔
    "\U000026A0": "▲",   # ⚠
    "\U0000FE0F": "",     # variation selector (strip)
    "\U0001F4DA": "[参考]",  # 📚
    "\U0001F3ED": "[参考]",  # 🏭
    "\U000023F3": "…",    # ⏳
}
EMOJI_RE = re.compile("|".join(re.escape(c) for c in EMOJI_MAP))


def map_emoji(text: str) -> str:
    return EMOJI_RE.sub(lambda m: EMOJI_MAP[m.group(0)], text)


# ---------------------------------------------------------------------------
# Chinese quote normalization
# ---------------------------------------------------------------------------
HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u20000-\u2a6df\uf400-\ufaff]")
LETTER_RE = re.compile(r"[A-Za-z]")


def is_chinese_paragraph(text: str) -> bool:
    han = len(HAN_RE.findall(text))
    letters = len(LETTER_RE.findall(text))
    return han * 2 > letters


def normalize_cn_quotes(text: str, state: list[int]) -> str:
    """Replace ASCII double quotes with Chinese quotes; state = [open?]."""
    out = []
    for ch in text:
        if ch == '"':
            if state[0]:
                out.append("\u201d")
                state[0] = 0
            else:
                out.append("\u201c")
                state[0] = 1
        else:
            out.append(ch)
    return "".join(out)


# ---------------------------------------------------------------------------
# inline markdown tokenizer
# ---------------------------------------------------------------------------
TOKEN_RE = re.compile(
    r"(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`|\[[^\]]*\]\([^)]*\)|~~[^~]+~~)",
    re.S,
)

LINK_RE = re.compile(r"^\[([^\]]*)\]\(([^)]*)\)$")


def split_inline(text: str):
    """Yield (kind, content) tokens: 'text','bold','italic','code','link','strike'."""
    pos = 0
    for m in TOKEN_RE.finditer(text):
        if m.start() > pos:
            yield ("text", text[pos : m.start()])
        tok = m.group(0)
        if tok.startswith("**") and tok.endswith("**"):
            yield ("bold", tok[2:-2])
        elif tok.startswith("*") and tok.endswith("*") and len(tok) > 2:
            yield ("italic", tok[1:-1])
        elif tok.startswith("`") and tok.endswith("`"):
            yield ("code", tok[1:-1])
        elif tok.startswith("~~") and tok.endswith("~~"):
            yield ("strike", tok[2:-2])
        elif tok.startswith("["):
            lm = LINK_RE.match(tok)
            if lm:
                yield ("link", (lm.group(1), lm.group(2)))
            else:
                yield ("text", tok)
        else:
            yield ("text", tok)
        pos = m.end()
    if pos < len(text):
        yield ("text", text[pos:])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def set_run_fonts(run, ascii_font: str, east_font: str) -> None:
    run.font.name = ascii_font  # sets ascii + hAnsi
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.insert(0, rFonts)
    rFonts.set(qn("w:ascii"), ascii_font)
    rFonts.set(qn("w:hAnsi"), ascii_font)
    rFonts.set(qn("w:eastAsia"), east_font)


def style_fonts(style, ascii_font: str, east_font: str) -> None:
    rPr = style.element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.insert(0, rFonts)
    rFonts.set(qn("w:ascii"), ascii_font)
    rFonts.set(qn("w:hAnsi"), ascii_font)
    rFonts.set(qn("w:eastAsia"), east_font)


def add_keep_next(pf_el) -> None:
    if pf_el.find(qn("w:keepNext")) is None:
        pf_el.insert(0, OxmlElement("w:keepNext"))


def set_first_line_chars(p_pr, chars: int, dxa: int | None = None) -> None:
    ind = p_pr.find(qn("w:ind"))
    if ind is None:
        ind = OxmlElement("w:ind")
        p_pr.append(ind)
    if chars:
        ind.set(qn("w:firstLineChars"), str(chars))
        if dxa is not None:
            ind.set(qn("w:firstLine"), str(dxa))
    else:
        ind.set(qn("w:firstLineChars"), "0")
        ind.set(qn("w:firstLine"), "0")


# ---------------------------------------------------------------------------
# document builder
# ---------------------------------------------------------------------------
class Builder:
    def __init__(self) -> None:
        self.doc = Document()
        self._setup_page()
        self._setup_styles()
        # numbering ids picked from template numbering.xml
        self.num_bullet, self.num_decimal = self._pick_numbering()
        self.quote_state: list[int] = [0]
        self._body_section_added = False

    # -- page setup -------------------------------------------------------
    def _setup_page(self) -> None:
        sec = self.doc.sections[0]
        sec.page_width = Cm(21.0)
        sec.page_height = Cm(29.7)
        for attr in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
            setattr(sec, attr, Cm(2.5))

    # -- styles -----------------------------------------------------------
    def _setup_styles(self) -> None:
        styles = self.doc.styles

        # Normal
        normal = styles["Normal"]
        normal.font.size = Pt(12)
        normal.font.color.rgb = RGBColor(0, 0, 0)
        style_fonts(normal, "Times New Roman", "宋体")
        pf = normal.paragraph_format
        pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pf.line_spacing = 1.5
        pf.space_before = Pt(0)
        pf.space_after = Pt(0)
        set_first_line_chars(normal.element.get_or_add_pPr(), 200, 480)

        # Title
        title = styles["Title"]
        title.font.size = Pt(18)
        title.font.bold = True
        title.font.color.rgb = RGBColor(0, 0, 0)
        style_fonts(title, "Times New Roman", "黑体")
        tpf = title.paragraph_format
        tpf.alignment = WD_ALIGN_PARAGRAPH.CENTER
        tpf.space_after = Pt(18)
        tpf.space_before = Pt(0)

        # Headings 1..4
        heading_specs = {
            "Heading 1": (16, Pt(14), Pt(6)),
            "Heading 2": (14, Pt(11), Pt(5)),
            "Heading 3": (12, Pt(9), Pt(4)),
            "Heading 4": (12, Pt(6), Pt(3)),
        }
        for name, (size, before, after) in heading_specs.items():
            st = styles[name]
            st.font.size = Pt(size)
            st.font.bold = True
            st.font.color.rgb = RGBColor(0, 0, 0)
            st.font.italic = False
            style_fonts(st, "Times New Roman", "黑体")
            hpf = st.paragraph_format
            hpf.space_before = before
            hpf.space_after = after
            hpf.line_spacing = 1.0
            hpf.alignment = WD_ALIGN_PARAGRAPH.LEFT
            add_keep_next(st.element.get_or_add_pPr())

        # Quote
        if "Quote" in [s.name for s in styles]:
            quote = styles["Quote"]
        else:
            quote = styles.add_style("Quote", WD_STYLE_TYPE.PARAGRAPH)
        quote.base_style = styles["Normal"]
        quote.font.size = Pt(12)
        quote.font.color.rgb = RGBColor(0, 0, 0)
        style_fonts(quote, "Times New Roman", "宋体")
        qpf = quote.paragraph_format
        qpf.left_indent = Cm(0.74)
        qpf.first_line_indent = Cm(0)
        qpf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        qpf.line_spacing = 1.5
        set_first_line_chars(quote.element.get_or_add_pPr(), 0, 0)

        # Code (paragraph) -- literal style name, exempt from quote audit
        code = styles.add_style("Code", WD_STYLE_TYPE.PARAGRAPH)
        code.base_style = styles["Normal"]
        code.font.size = Pt(10.5)
        code.font.color.rgb = RGBColor(0, 0, 0)
        style_fonts(code, "Consolas", "宋体")
        cpf = code.paragraph_format
        cpf.alignment = WD_ALIGN_PARAGRAPH.LEFT
        cpf.line_spacing = 1.0
        cpf.space_before = Pt(0)
        cpf.space_after = Pt(0)
        cpf.left_indent = Cm(0)
        cpf.first_line_indent = Cm(0)
        set_first_line_chars(code.element.get_or_add_pPr(), 0, 0)

        # CodeChar (character) -- literal style name
        cchar = styles.add_style("CodeChar", WD_STYLE_TYPE.CHARACTER)
        cchar.font.size = Pt(10.5)
        cchar.font.color.rgb = RGBColor(0, 0, 0)
        style_fonts(cchar, "Consolas", "宋体")

        # TableText
        ttext = styles.add_style("TableText", WD_STYLE_TYPE.PARAGRAPH)
        ttext.base_style = styles["Normal"]
        ttext.font.size = Pt(10.5)
        ttext.font.color.rgb = RGBColor(0, 0, 0)
        style_fonts(ttext, "Times New Roman", "宋体")
        tpf2 = ttext.paragraph_format
        tpf2.alignment = WD_ALIGN_PARAGRAPH.LEFT
        tpf2.line_spacing = 1.0
        tpf2.space_before = Pt(0)
        tpf2.space_after = Pt(0)
        set_first_line_chars(ttext.element.get_or_add_pPr(), 0, 0)

        # List Paragraph: no first-line indent
        lp = styles["List Paragraph"]
        set_first_line_chars(lp.element.get_or_add_pPr(), 0, 0)

    def _pick_numbering(self) -> tuple[int, int]:
        """Find a bullet numId and a decimal numId in the template numbering.xml."""
        numbering = self.doc.part.numbering_part.element if self.doc.part.numbering_part else None
        if numbering is None:
            return 5, 1
        ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        num_bullet = num_decimal = None
        for num in numbering.findall(f"{{{ns}}}num"):
            nid = num.get(f"{{{ns}}}numId")
            absref = num.find(f"{{{ns}}}abstractNumId")
            if absref is None:
                continue
            aid = absref.get(f"{{{ns}}}val")
            for abstract in numbering.findall(f"{{{ns}}}abstractNum"):
                if abstract.get(f"{{{ns}}}abstractNumId") != aid:
                    continue
                lvl0 = abstract.find(f"{{{ns}}}lvl")
                if lvl0 is not None:
                    fmt = lvl0.find(f"{{{ns}}}numFmt")
                    if fmt is not None:
                        val = fmt.get(f"{{{ns}}}val")
                        if val == "bullet" and num_bullet is None:
                            num_bullet = int(nid)
                        elif val == "decimal" and num_decimal is None:
                            num_decimal = int(nid)
                break
        return (num_bullet or 5, num_decimal or 1)

    # -- low-level paragraph writers ---------------------------------------
    def _write_inline(self, p, text: str, *, east_font: str, ascii_font: str,
                      base_bold: bool = False, base_italic: bool = False,
                      normalize_quotes: bool = False) -> None:
        if normalize_quotes:
            text = normalize_cn_quotes(text, self.quote_state)
        text = map_emoji(text)
        for kind, content in split_inline(text):
            if kind == "text":
                run = p.add_run(content)
                run.bold = base_bold
                run.italic = base_italic
                set_run_fonts(run, ascii_font, east_font)
            elif kind == "bold":
                self._write_inline(p, content, east_font=east_font, ascii_font=ascii_font,
                                   base_bold=True, base_italic=base_italic,
                                   normalize_quotes=False)
            elif kind == "italic":
                self._write_inline(p, content, east_font=east_font, ascii_font=ascii_font,
                                   base_bold=base_bold, base_italic=True,
                                   normalize_quotes=False)
            elif kind == "strike":
                run = p.add_run(content)
                run.bold = base_bold
                run.italic = base_italic
                run.font.strike = True
                set_run_fonts(run, ascii_font, east_font)
            elif kind == "code":
                run = p.add_run(content)
                run.bold = base_bold
                run.italic = base_italic
                run.style = self.doc.styles["CodeChar"]
                set_run_fonts(run, "Consolas", "宋体")
            elif kind == "link":
                text_part, url = content
                if url.startswith(("http://", "https://")):
                    run = p.add_run(text_part)
                    run.bold = base_bold
                    run.italic = base_italic
                    set_run_fonts(run, ascii_font, east_font)
                    rPr = run._element.get_or_add_rPr()
                    style = rPr.find(qn("w:rStyle"))
                    if style is None:
                        style = OxmlElement("w:rStyle")
                        rPr.insert(0, style)
                    style.set(qn("w:val"), "Hyperlink")
                    rId = self.doc.part.relate_to(
                        url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
                        is_external=True,
                    )
                    hlink = OxmlElement("w:hyperlink")
                    hlink.set(qn("r:id"), rId)
                    run._element.getparent().replace(run._element, hlink)
                    hlink.append(run._element)
                else:
                    # internal file reference -> plain text path
                    run = p.add_run(text_part or url)
                    run.bold = base_bold
                    run.italic = base_italic
                    set_run_fonts(run, ascii_font, east_font)

    def add_paragraph(self, text: str, style: str = "Normal") -> None:
        p = self.doc.add_paragraph(style=style)
        east = "黑体" if style.startswith("Heading") or style == "Title" else "宋体"
        normalize = is_chinese_paragraph(text)
        self.quote_state = [0]
        self._write_inline(p, text, east_font=east, ascii_font="Times New Roman",
                           normalize_quotes=normalize)

    def add_heading(self, text: str, level: int) -> None:
        style = {1: "Heading 1", 2: "Heading 2", 3: "Heading 3"}.get(level, "Heading 4")
        self.add_paragraph(text, style=style)

    def add_title(self, text: str) -> None:
        self.add_paragraph(text, style="Title")

    def add_quote(self, text: str) -> None:
        self.add_paragraph(text, style="Quote")

    def add_code_lines(self, lines: list[str]) -> None:
        for line in lines:
            p = self.doc.add_paragraph(style="Code")
            run = p.add_run(line)
            set_run_fonts(run, "Consolas", "宋体")
            run.font.size = Pt(10.5)

    def add_list_item(self, text: str, ordered: bool, level: int) -> None:
        p = self.doc.add_paragraph(style="List Paragraph")
        pPr = p._p.get_or_add_pPr()
        numPr = OxmlElement("w:numPr")
        ilvl = OxmlElement("w:ilvl")
        ilvl.set(qn("w:val"), "0")
        numId = OxmlElement("w:numId")
        numId.set(qn("w:val"), str(self.num_decimal if ordered else self.num_bullet))
        numPr.append(ilvl)
        numPr.append(numId)
        pPr.append(numPr)
        ind = pPr.find(qn("w:ind"))
        if ind is None:
            ind = OxmlElement("w:ind")
            pPr.append(ind)
        ind.set(qn("w:left"), str(720 * (level + 1)))
        ind.set(qn("w:firstLine"), "0")
        ind.set(qn("w:firstLineChars"), "0")
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        normalize = is_chinese_paragraph(text)
        self.quote_state = [0]
        self._write_inline(p, text, east_font="宋体", ascii_font="Times New Roman",
                           normalize_quotes=normalize)

    # -- tables -------------------------------------------------------------
    def add_table(self, header: list[str], rows: list[list[str]]) -> None:
        ncols = max(len(header), *(len(r) for r in rows)) if rows else len(header)
        header = header + [""] * (ncols - len(header))
        rows = [r + [""] * (ncols - len(r)) for r in rows]
        table = self.doc.add_table(rows=1 + len(rows), cols=ncols, style="Table Grid")
        table.alignment = WD_TABLE_ALIGNMENT.LEFT
        table.autofit = False
        # full content width: A4 21cm - 5cm margins = 16cm = 9072 twips
        content_twips = 9072
        col_twips = content_twips // ncols
        # grid
        grid = table._tbl.tblGrid
        for gc in grid.findall(qn("w:gridCol")):
            gc.set(qn("w:w"), str(col_twips))
        # tblW full width
        tblPr = table._tbl.tblPr
        tblW = tblPr.find(qn("w:tblW"))
        if tblW is None:
            tblW = OxmlElement("w:tblW")
            tblStyle = tblPr.find(qn("w:tblStyle"))
            if tblStyle is not None:
                tblStyle.addnext(tblW)
            else:
                tblPr.insert(0, tblW)
        tblW.set(qn("w:w"), str(content_twips))
        tblW.set(qn("w:type"), "dxa")

        def fill_cell(cell, text: str, is_header: bool) -> None:
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = cell.paragraphs[0]
            p.style = self.doc.styles["TableText"]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if is_header else WD_ALIGN_PARAGRAPH.LEFT
            self.quote_state = [0]
            normalize = is_chinese_paragraph(text)
            self._write_inline(p, text, east_font="宋体", ascii_font="Times New Roman",
                               normalize_quotes=normalize, base_bold=is_header)

        for j, h in enumerate(header):
            fill_cell(table.cell(0, j), h, True)
        for i, row in enumerate(rows, start=1):
            for j, val in enumerate(row):
                fill_cell(table.cell(i, j), val, False)

        # header shading + row props
        def shade_cell(cell, fill: str) -> None:
            tcPr = cell._tc.get_or_add_tcPr()
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"), fill)
            vAlign = tcPr.find(qn("w:vAlign"))
            if vAlign is not None:
                vAlign.addprevious(shd)
            else:
                tcPr.append(shd)

        for cell in table.rows[0].cells:
            shade_cell(cell, "D9D9D9")
        for row in table.rows:
            trPr = row._tr.get_or_add_trPr()
            cantSplit = OxmlElement("w:cantSplit")
            trPr.append(cantSplit)
            if row is table.rows[0]:
                tblHeader = OxmlElement("w:tblHeader")
                trPr.append(tblHeader)

    # -- TOC field ----------------------------------------------------------
    def add_toc_field(self) -> None:
        p = self.doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.0
        begin = OxmlElement("w:r")
        fld = OxmlElement("w:fldChar")
        fld.set(qn("w:fldCharType"), "begin")
        fld.set(qn("w:dirty"), "true")
        begin.append(fld)
        instr = OxmlElement("w:r")
        instr_text = OxmlElement("w:instrText")
        instr_text.set(qn("xml:space"), "preserve")
        instr_text.text = ' TOC \\o "1-2" \\h \\z \\u '
        instr.append(instr_text)
        sep = OxmlElement("w:r")
        fld2 = OxmlElement("w:fldChar")
        fld2.set(qn("w:fldCharType"), "separate")
        sep.append(fld2)
        placeholder = OxmlElement("w:r")
        placeholder_text = OxmlElement("w:t")
        placeholder_text.text = "（目录将在打开文档时自动更新）"
        placeholder.append(placeholder_text)
        end = OxmlElement("w:r")
        fld3 = OxmlElement("w:fldChar")
        fld3.set(qn("w:fldCharType"), "end")
        end.append(fld3)
        for el in (begin, instr, sep, placeholder, end):
            r_pr = OxmlElement("w:rPr")
            r_fonts = OxmlElement("w:rFonts")
            r_fonts.set(qn("w:ascii"), "Times New Roman")
            r_fonts.set(qn("w:hAnsi"), "Times New Roman")
            r_fonts.set(qn("w:eastAsia"), "宋体")
            r_pr.append(r_fonts)
            el.insert(0, r_pr)
            p._p.append(el)

    # -- sections -----------------------------------------------------------
    def ensure_body_section(self) -> None:
        if self._body_section_added:
            return
        self._body_section_added = True
        self.doc.add_section(WD_SECTION.NEW_PAGE)
        sec2 = self.doc.sections[-1]
        sec2.page_width = Cm(21.0)
        sec2.page_height = Cm(29.7)
        for attr in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
            setattr(sec2, attr, Cm(2.5))
        # page numbering starts at 1 in the body section
        sectPr = sec2._sectPr
        pgNumType = OxmlElement("w:pgNumType")
        pgNumType.set(qn("w:start"), "1")
        sectPr.append(pgNumType)
        # footer with centered page number
        sec2.footer.is_linked_to_previous = False
        footer_p = sec2.footer.paragraphs[0]
        footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        fldSimple = OxmlElement("w:fldSimple")
        fldSimple.set(qn("w:instr"), " PAGE ")
        run = OxmlElement("w:r")
        rPr = OxmlElement("w:rPr")
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), "21")
        rPr.append(sz)
        run.append(rPr)
        t = OxmlElement("w:t")
        t.text = "1"
        run.append(t)
        fldSimple.append(run)
        footer_p._p.append(fldSimple)
        # section 1 footer stays empty
        sec1 = self.doc.sections[0]
        sec1.footer.is_linked_to_previous = False


# ---------------------------------------------------------------------------
# markdown block parser
# ---------------------------------------------------------------------------
ORDERED_RE = re.compile(r"^\s*(\d+)[.)]\s+(.*)$")
BULLET_RE = re.compile(r"^\s*[-*+]\s+(.*)$")


def parse_and_build(builder: Builder) -> None:
    lines = SRC.read_text(encoding="utf-8").splitlines()
    i = 0
    n = len(lines)
    first_h1_done = False
    in_toc_after_dir = False
    toc_inserted = False

    def heading_level(line: str) -> int:
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        return (len(m.group(1)), m.group(2)) if m else None

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # skip the manual TOC list after "## 目录"
        if in_toc_after_dir:
            if stripped == "":
                pass
            elif stripped == "---":
                if not toc_inserted:
                    builder.add_toc_field()
                    builder.ensure_body_section()
                    toc_inserted = True
                in_toc_after_dir = False
            else:
                i += 1
                continue

        if stripped == "":
            i += 1
            continue

        # horizontal rule
        if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", stripped):
            i += 1
            continue

        # headings
        hl = heading_level(line)
        if hl:
            level, text = hl
            if not first_h1_done and level == 1:
                builder.add_title(text)
                first_h1_done = True
            else:
                builder.add_heading(text, min(level, 4))
            if level == 2 and text.strip() == "目录":
                in_toc_after_dir = True
            i += 1
            continue

        # fenced code
        if stripped.startswith("```"):
            i += 1
            code_lines = []
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < n:
                i += 1  # closing fence
            builder.add_code_lines(code_lines)
            continue

        # pipe table
        if stripped.startswith("|") and i + 1 < n:
            nxt = lines[i + 1].strip()
            if re.fullmatch(r"\|[\s:|-]+\|", nxt) and "|" in nxt:
                header = [c.strip() for c in stripped.strip("|").split("|")]
                i += 2
                rows = []
                while i < n and lines[i].strip().startswith("|"):
                    cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                    rows.append(cells)
                    i += 1
                builder.add_table(header, rows)
                continue

        # blockquote
        if stripped.startswith(">"):
            quote_lines = []
            while i < n and lines[i].strip().startswith(">"):
                quote_lines.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            builder.add_quote(" ".join(quote_lines).strip())
            continue

        # lists
        om = ORDERED_RE.match(line)
        bm = BULLET_RE.match(line)
        if om or bm:
            items = []  # (level, ordered, text)
            while i < n:
                cur = lines[i]
                cs = cur.strip()
                if cs == "":
                    break
                co = ORDERED_RE.match(cur)
                cb = BULLET_RE.match(cur)
                if not (co or cb):
                    break
                indent = len(cur) - len(cur.lstrip())
                level = indent // 2
                if co and not cb:
                    items.append((level, True, co.group(2)))
                else:
                    items.append((level, False, cb.group(1)))
                i += 1
            # following indented lines belong to a code block (handled next loop)
            for level, ord_, text in items:
                builder.add_list_item(text, ord_, level)
            continue

        # indented code
        if stripped.startswith("    ") or line.startswith("\t"):
            code_lines = []
            while i < n:
                cur = lines[i]
                if cur.strip() == "":
                    i += 1
                    break
                if cur.startswith("    ") or cur.startswith("\t"):
                    code_lines.append(cur[4:] if cur.startswith("    ") else cur[1:])
                    i += 1
                else:
                    break
            builder.add_code_lines(code_lines)
            continue

        # normal paragraph: collect consecutive lines
        para_lines = []
        while i < n:
            cur = lines[i]
            cs = cur.strip()
            if cs == "":
                break
            if re.match(r"^(#{1,6})\s", cur):
                break
            if cs.startswith("```") or cs.startswith("|") or cs.startswith(">"):
                break
            if ORDERED_RE.match(cur) or BULLET_RE.match(cur):
                break
            if cs.startswith("    ") or cur.startswith("\t"):
                break
            if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", cs):
                break
            para_lines.append(cur)
            i += 1
        builder.add_paragraph(" ".join(para_lines).strip())


def main() -> None:
    builder = Builder()
    parse_and_build(builder)
    # document core properties
    builder.doc.core_properties.title = "XinMatch 项目文档合集"
    builder.doc.core_properties.subject = "XinMatch 项目现行文档汇编（2026-10-12 整理）"
    builder.doc.save(str(OUT))
    print(f"written: {OUT}")
    print(f"size: {OUT.stat().st_size} bytes")


if __name__ == "__main__":
    main()
