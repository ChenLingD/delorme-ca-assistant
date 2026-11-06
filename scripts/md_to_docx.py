"""Convert the submission Markdown (deliverables/Delorme_submission.md) into a Word file.

Handles the subset we use: #/##/### headings, paragraphs, '- ' bullets, pipe tables, code fences,
'> ' quotes (screenshot placeholders are shaded boxes), '---' page breaks, **bold**, *italic*, `code`.
Usage: python scripts/md_to_docx.py deliverables/Delorme_submission.md deliverables/Delorme_submission.docx
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

LATIN, CJK, MONO = "Calibri", "Microsoft YaHei", "Consolas"
ACCENT = RGBColor(0x0F, 0x5B, 0x5C)


def set_fonts(run, latin=LATIN, size=None):
    run.font.name = latin
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), CJK)
    if size:
        run.font.size = Pt(size)


def shade(el, fill):
    pr = el._tc.get_or_add_tcPr() if hasattr(el, "_tc") else el._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    pr.append(shd)


INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)")


def add_inline(par, text, size=None, color=None):
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**"):
            r = par.add_run(part[2:-2]); r.bold = True
        elif part.startswith("`"):
            r = par.add_run(part[1:-1]); set_fonts(r, MONO, size); continue
        elif part.startswith("*") and len(part) > 2:
            r = par.add_run(part[1:-1]); r.italic = True
        else:
            r = par.add_run(part)
        set_fonts(r, size=size)
        if color:
            r.font.color.rgb = color


def add_table(doc, rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    header, body = cells[0], [r for r in cells[2:]]
    ncol = len(header)
    has_header = any(header)
    allrows = ([header] if has_header else []) + body
    t = doc.add_table(rows=len(allrows), cols=ncol)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    size = 8.5 if ncol >= 6 else 9.5
    # column widths proportional to (capped) average text length, so long-text columns get room
    total = 17.4  # cm of usable width
    def vis(x: str) -> int:  # CJK characters are about twice as wide as Latin ones
        return sum(2 if ord(ch) > 0x2E80 else 1 for ch in x)
    lens = [min(60, max(6, vis(header[j]) * 1.1 + 2, sum(vis(r[j]) if j < len(r) else 0 for r in allrows) / len(allrows)))
            for j in range(ncol)]
    widths = [Cm(total * l / sum(lens)) for l in lens]
    for row in t.rows:
        for j, cell in enumerate(row.cells):
            cell.width = widths[j]
    for i, row in enumerate(allrows):
        for j in range(ncol):
            cell = t.cell(i, j)
            cell.paragraphs[0].paragraph_format.space_after = Pt(0)
            add_inline(cell.paragraphs[0], row[j] if j < len(row) else "", size=size)
            if i == 0 and has_header:
                shade(cell, "E3EEEE")
                for r in cell.paragraphs[0].runs:
                    r.bold = True
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def convert(src: Path, dst: Path) -> None:
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    for m in ("left_margin", "right_margin"):
        setattr(sec, m, Cm(1.8))
    sec.top_margin = sec.bottom_margin = Cm(1.8)
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = LATIN, Pt(10.5)
    normal.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), CJK)
    for name, size in (("Title", 22), ("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 11.5)):
        st = doc.styles[name]
        st.font.name, st.font.size, st.font.color.rgb = LATIN, Pt(size), ACCENT
        st.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), CJK)
        st.paragraph_format.keep_with_next = True
        st.paragraph_format.space_before, st.paragraph_format.space_after = Pt(12), Pt(6)

    lines = src.read_text(encoding="utf-8").splitlines()
    i, first_h1 = 0, True
    while i < len(lines):
        line = lines[i]
        if line.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                block.append(lines[i]); i += 1
            add_table(doc, block)
            continue
        if line.startswith("```"):
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(0)
                r = p.add_run(lines[i]); set_fonts(r, MONO, 9)
                i += 1
            i += 1
            continue
        s = line.strip()
        if s == "---":
            doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        elif s.startswith("# "):
            if first_h1:
                add_inline(doc.add_paragraph(style="Title"), s[2:]); first_h1 = False
            else:
                add_inline(doc.add_heading(level=1), s[2:])
        elif s.startswith("## "):
            add_inline(doc.add_heading(level=1), s[3:])
        elif s.startswith("### "):
            add_inline(doc.add_heading(level=2), s[4:])
        elif s.startswith("![") and s.endswith(")"):
            img = src.parent / s[s.index("(") + 1:-1]
            doc.add_picture(str(img), width=Cm(17.4))
        elif s.startswith("> "):
            p = doc.add_paragraph()
            txt = s[2:]
            placeholder = txt.startswith("[") and txt.endswith("]")
            add_inline(p, txt, color=RGBColor(0x88, 0x6A, 0x00) if placeholder else RGBColor(0x33, 0x33, 0x33))
            shade(p, "FFF6E0" if placeholder else "F2F2F2")
            p.paragraph_format.left_indent = Cm(0.4)
        elif s.startswith("- "):
            add_inline(doc.add_paragraph(style="List Bullet"), s[2:])
        elif s:
            add_inline(doc.add_paragraph(), s)
        i += 1
    doc.save(dst)


if __name__ == "__main__":
    convert(Path(sys.argv[1]), Path(sys.argv[2]))
    print("wrote", sys.argv[2])
