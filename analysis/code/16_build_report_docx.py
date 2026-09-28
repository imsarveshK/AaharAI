"""
Build the typeset report version of the paper.

Where 12_build_docx.py produces a double-spaced review manuscript, this produces
the laid-out article: the form the paper takes once a journal has typeset it.

The layout follows conventions measured from three open-access Q1 papers in this
field: Jia et al. (BMC Medicine 2024), Bennett et al. (Obesity Reviews 2024) and
Trude et al. (Nutrition Reviews 2022). All three set the body in two justified
columns at roughly 8 to 10 pt on about 12 pt of leading, run a head with authors
and page number above a rule, and rule their tables horizontally only, with no
vertical lines and no grid.

Title, authors and abstract span the full measure; the body runs in two columns;
tables and figures too wide for one column break back to full width and return.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "paper"
FIGDIR = ROOT / "analysis/output/figures"
OUT = PAPER / "manuscript_report.docx"

# Reuse the parsing already written for the manuscript build.
_spec = importlib.util.spec_from_file_location(
    "manuscript_builder", Path(__file__).parent / "12_build_docx.py")
mb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mb)

# ---- page and type -----------------------------------------------------------
PAGE_W, PAGE_H = Cm(21.0), Cm(29.7)
MARGIN_X, MARGIN_TOP, MARGIN_BOT = Cm(1.8), Cm(1.9), Cm(2.0)
GUTTER_CM = 0.62
CONTENT_W_CM = 21.0 - 2 * 1.8
COL_W_CM = (CONTENT_W_CM - GUTTER_CM) / 2

SERIF = "Times New Roman"
SANS = "Arial"
BODY_PT, BODY_LEAD = Pt(9.5), Pt(12)
SMALL_PT = Pt(8.5)
TABLE_PT = Pt(7.5)
CAPTION_PT = Pt(8)

INK = RGBColor(0x00, 0x00, 0x00)
MUTED = RGBColor(0x44, 0x44, 0x44)

RUNNING_HEAD = "Kulkarni et al."
SHORT_TITLE = "Digital food retail and the Indian household food basket"

# Which blocks span the full measure rather than sitting in a column.
FULL_WIDTH_FIGURES = {1, 2, 3, 4}
FULL_WIDTH_TABLES = {1, 2, 3, 4, 5}


# ---- low-level XML helpers ---------------------------------------------------

def set_columns(section, num: int, space_cm: float = GUTTER_CM) -> None:
    sectPr = section._sectPr
    cols = sectPr.find(qn("w:cols"))
    if cols is None:
        cols = OxmlElement("w:cols")
        sectPr.append(cols)
    cols.set(qn("w:num"), str(num))
    cols.set(qn("w:space"), str(int(space_cm * 567)))   # cm -> twips
    cols.set(qn("w:equalWidth"), "1")


def configure_page(section) -> None:
    section.page_width, section.page_height = PAGE_W, PAGE_H
    section.left_margin = section.right_margin = MARGIN_X
    section.top_margin, section.bottom_margin = MARGIN_TOP, MARGIN_BOT
    section.header_distance = Cm(1.0)


def horizontal_rule(paragraph, position: str = "bottom", size: int = 6) -> None:
    pPr = paragraph._p.get_or_add_pPr()
    borders = pPr.find(qn("w:pBdr"))
    if borders is None:
        borders = OxmlElement("w:pBdr")
        pPr.append(borders)
    edge = OxmlElement(f"w:{position}")
    edge.set(qn("w:val"), "single")
    edge.set(qn("w:sz"), str(size))
    edge.set(qn("w:space"), "2")
    edge.set(qn("w:color"), "000000")
    borders.append(edge)


def running_head(section, first: bool = False) -> None:
    """Authors left, page number right, over a hairline rule."""
    header = section.header
    header.is_linked_to_previous = False
    p = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
    for r in list(p.runs):
        r._r.getparent().remove(r._r)
    pf = p.paragraph_format
    pf.line_spacing = 1.0
    pf.space_after = Pt(6)
    # One right tab at the measure sets the page number flush right.
    tabs = p._p.get_or_add_pPr()
    tabsEl = OxmlElement("w:tabs")
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "right")
    tab.set(qn("w:pos"), str(int(CONTENT_W_CM * 567)))
    tabsEl.append(tab)
    tabs.append(tabsEl)

    left = p.add_run(f"{RUNNING_HEAD}\t")
    left.italic = True
    left.font.name, left.font.size, left.font.color.rgb = SERIF, SMALL_PT, MUTED

    num = p.add_run()
    num.font.name, num.font.size, num.font.color.rgb = SERIF, SMALL_PT, MUTED
    for kind, text in [("begin", None), ("instr", " PAGE "), ("end", None)]:
        el = OxmlElement("w:instrText") if kind == "instr" else OxmlElement("w:fldChar")
        if kind == "instr":
            el.set(qn("xml:space"), "preserve")
            el.text = text
        else:
            el.set(qn("w:fldCharType"), kind)
        num._r.append(el)
    horizontal_rule(p, "bottom", 4)


def new_flow_section(doc: Document, columns: int):
    """Continuous break that switches the column count mid-page."""
    sec = doc.add_section(WD_SECTION.CONTINUOUS)
    configure_page(sec)
    set_columns(sec, columns)
    sec.header.is_linked_to_previous = True
    return sec


# ---- paragraph builders ------------------------------------------------------

def body_style(doc: Document) -> None:
    st = doc.styles["Normal"]
    st.font.name, st.font.size, st.font.color.rgb = SERIF, BODY_PT, INK
    rpr = st.element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.append(rf)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rf.set(qn(a), SERIF)
    pf = st.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf.line_spacing = BODY_LEAD
    pf.space_before = pf.space_after = Pt(0)
    pf.widow_control = True


def para(doc, text, *, size=None, italic=False, bold=False, align=None,
         space_before=Pt(0), space_after=Pt(0), lead=None, indent=None,
         hanging=None, keep=False):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.alignment = align if align is not None else WD_ALIGN_PARAGRAPH.JUSTIFY
    pf.line_spacing = lead or BODY_LEAD
    pf.space_before, pf.space_after = space_before, space_after
    if indent is not None:
        pf.first_line_indent = indent
    if hanging is not None:
        pf.left_indent, pf.first_line_indent = hanging, -hanging
    pf.keep_with_next = keep
    mb.add_runs(p, text, size=size or BODY_PT, base_italic=italic)
    if bold:
        for r in p.runs:
            r.bold = True
    return p


def section_heading(doc, text, level):
    return para(doc, text, size=Pt(10) if level == 2 else Pt(9.5), bold=True,
                italic=(level >= 3), align=WD_ALIGN_PARAGRAPH.LEFT,
                space_before=Pt(10 if level == 2 else 8), space_after=Pt(3),
                lead=Pt(11), keep=True)


# ---- tables in journal style -------------------------------------------------

def cell_rule(cell, edge: str, size: int = 6) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    borders = tcPr.find(qn("w:tcBorders"))
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tcPr.append(borders)
    el = OxmlElement(f"w:{edge}")
    el.set(qn("w:val"), "single")
    el.set(qn("w:sz"), str(size))
    el.set(qn("w:color"), "000000")
    borders.append(el)


def add_table(doc, number, rows):
    """Journal table: horizontal rules only, no vertical lines, no grid."""
    para(doc, f"**Table {number}.** {mb.TABLE_TITLES[number]}", size=CAPTION_PT,
         align=WD_ALIGN_PARAGRAPH.LEFT, lead=Pt(9.5),
         space_before=Pt(8), space_after=Pt(3), keep=True)

    ncols = max(len(r) for r in rows)
    table = doc.add_table(rows=0, cols=ncols)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.autofit = False
    # No table style: borders are drawn per cell so only horizontal rules appear.
    label_w = min(4.9, CONTENT_W_CM * 0.30)
    num_w = (CONTENT_W_CM - label_w) / max(ncols - 1, 1)
    widths = [Cm(label_w)] + [Cm(num_w)] * (ncols - 1)

    last = len(rows) - 1
    for i, cells in enumerate(rows):
        row = table.add_row()
        for j in range(ncols):
            cell = row.cells[j]
            cell.width = widths[j]
            p = cell.paragraphs[0]
            pf = p.paragraph_format
            pf.line_spacing = Pt(9)
            pf.space_before = pf.space_after = Pt(1.5)
            pf.alignment = (WD_ALIGN_PARAGRAPH.LEFT if j == 0
                            else WD_ALIGN_PARAGRAPH.RIGHT)
            run = p.add_run((cells[j] if j < len(cells) else "").replace("*", ""))
            run.bold = (i == 0)
            run.font.name, run.font.size = SERIF, TABLE_PT
            if i == 0:
                cell_rule(cell, "top", 8)       # rule above the header
                cell_rule(cell, "bottom", 6)    # rule below the header
            if i == last:
                cell_rule(cell, "bottom", 8)    # closing rule
        trPr = row._tr.get_or_add_trPr()
        trPr.append(OxmlElement("w:cantSplit"))
        if i == 0:
            trPr.append(OxmlElement("w:tblHeader"))

    para(doc, f"*Note.* {mb.TABLE_NOTES[number]}", size=Pt(7.5),
         align=WD_ALIGN_PARAGRAPH.LEFT, lead=Pt(9), space_before=Pt(3),
         space_after=Pt(9))


def add_figure(doc, number, width_cm):
    stem, caption = mb.FIGURE_CAPTIONS[number]
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = p.paragraph_format
    # Leave line spacing at single-multiple. An exact point value clips an inline
    # image to that height, which silently reduces every figure to a sliver.
    pf.line_spacing = WD_LINE_SPACING.SINGLE
    pf.space_before, pf.space_after = Pt(8), Pt(3)
    pf.keep_with_next = True
    p.add_run().add_picture(str(FIGDIR / f"{stem}.png"), width=Cm(width_cm))
    para(doc, f"**Figure {number}.** {caption}", size=CAPTION_PT,
         align=WD_ALIGN_PARAGRAPH.LEFT, lead=Pt(9.5), space_after=Pt(9))


# ---- front matter ------------------------------------------------------------

def front_matter(doc, parts):
    para(doc, parts["title"], size=Pt(17), bold=True,
         align=WD_ALIGN_PARAGRAPH.LEFT, lead=Pt(20), space_after=Pt(9))

    authors = doc.add_paragraph()
    authors.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    authors.paragraph_format.line_spacing = Pt(12)
    authors.paragraph_format.space_after = Pt(3)
    for i, (name, marker, corresponding) in enumerate(mb.AUTHORS):
        if i:
            sep = authors.add_run(", ")
            sep.font.name, sep.font.size = SERIF, Pt(10.5)
        r = authors.add_run(name)
        r.font.name, r.font.size = SERIF, Pt(10.5)
        sup = authors.add_run(marker + ("*" if corresponding else ""))
        sup.font.superscript = True
        sup.font.name, sup.font.size = SERIF, Pt(10.5)

    for marker, text in mb.AFFILIATIONS:
        aff = doc.add_paragraph()
        aff.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        aff.paragraph_format.line_spacing = Pt(10)
        aff.paragraph_format.space_after = Pt(1)
        sup = aff.add_run(marker)
        sup.font.superscript = True
        sup.font.name, sup.font.size, sup.font.color.rgb = SERIF, SMALL_PT, MUTED
        r = aff.add_run(" " + text)
        r.italic = True
        r.font.name, r.font.size, r.font.color.rgb = SERIF, SMALL_PT, MUTED

    corresponding = next(n for n, _, c in mb.AUTHORS if c)
    para(doc, f"* Corresponding author: {corresponding}, {mb.CORRESPONDING_CONTACT}",
         size=SMALL_PT, italic=True, align=WD_ALIGN_PARAGRAPH.LEFT,
         lead=Pt(10), space_after=Pt(10))

    # Abstract, ruled above and below and set across the full measure.
    head = para(doc, "Abstract", size=Pt(9), bold=True,
                align=WD_ALIGN_PARAGRAPH.LEFT, lead=Pt(11),
                space_before=Pt(2), space_after=Pt(4), keep=True)
    horizontal_rule(head, "top", 8)
    for block in parts["abstract"].split("\n\n"):
        para(doc, block.strip(), size=Pt(9), lead=Pt(11), space_after=Pt(4))
    kw = para(doc, f"**Keywords:** {parts['keywords']}", size=Pt(9),
              align=WD_ALIGN_PARAGRAPH.LEFT, lead=Pt(11),
              space_before=Pt(2), space_after=Pt(10))
    horizontal_rule(kw, "bottom", 8)


# ---- body flow ---------------------------------------------------------------

def render_body(doc, text, tables):
    """Two-column body that drops to full width for wide tables and figures.

    Each change of column count is a section break, and a break that lands low on
    a page pushes the following block to the next page, stranding what is above
    it. So when two full-width items are separated by only a block or two of
    text, the flow stays at full width across that text rather than switching
    back and forth. COALESCE_WINDOW is how far ahead it looks.
    """
    COALESCE_WINDOW = 5

    blocks = [b.strip() for b in re.split(r"\n\s*\n", text.strip())
              if b.strip() and not set(b.strip()) <= set("-*_ ")]

    # Which full-width items each block triggers, in citation order.
    pending_f, pending_t = set(mb.FIGURE_ANCHORS), set(mb.TABLE_ANCHORS)
    attached: list[tuple[list[int], list[int]]] = []
    for block in blocks:
        figs = [n for n in sorted(pending_f) if mb.FIGURE_ANCHORS[n] in block]
        tabs = [n for n in sorted(pending_t) if mb.TABLE_ANCHORS[n] in block
                and n in tables]
        pending_f -= set(figs)
        pending_t -= set(tabs)
        attached.append((figs, tabs))

    def wide_at(i: int) -> bool:
        figs, tabs = attached[i]
        return (any(n in FULL_WIDTH_FIGURES for n in figs)
                or any(n in FULL_WIDTH_TABLES for n in tabs))

    mode = 2

    def to(cols: int):
        nonlocal mode
        if cols != mode:
            new_flow_section(doc, cols)
            mode = cols

    placed_f, placed_t = set(), set()
    for i, block in enumerate(blocks):
        # Hold full width through short text that sits between two wide items.
        upcoming = any(wide_at(j) for j in
                       range(i, min(i + COALESCE_WINDOW + 1, len(blocks))))
        to(1 if (mode == 1 and upcoming) else 2)

        if block.startswith("### "):
            section_heading(doc, block[4:].strip(), 3)
        elif block.startswith("## "):
            section_heading(doc, block[3:].strip(), 2)
        elif block.startswith("- "):
            for line in block.split("\n"):
                if line.strip().startswith("- "):
                    para(doc, "\u2022  " + line.strip()[2:], hanging=Cm(0.35),
                         space_after=Pt(1))
        else:
            para(doc, block.replace("\n", " "))

        figs, tabs = attached[i]
        for n in figs:
            to(1 if n in FULL_WIDTH_FIGURES else 2)
            add_figure(doc, n, CONTENT_W_CM - 1.2 if n in FULL_WIDTH_FIGURES
                       else COL_W_CM - 0.2)
            placed_f.add(n)
        for n in tabs:
            to(1 if n in FULL_WIDTH_TABLES else 2)
            add_table(doc, n, tables[n])
            placed_t.add(n)

    to(2)
    return placed_f, placed_t


def build() -> Document:
    parts = mb.split_manuscript((PAPER / "manuscript.md").read_text())
    tables = mb.parse_markdown_tables((PAPER / "tables.md").read_text())

    doc = Document()
    body_style(doc)

    # Front matter spans the measure.
    first = doc.sections[0]
    configure_page(first)
    set_columns(first, 1)
    running_head(first)
    front_matter(doc, parts)

    # Body in two columns.
    new_flow_section(doc, 2)
    placed_f, placed_t = render_body(doc, parts["body"], tables)

    for n in sorted(set(mb.FIGURE_CAPTIONS) - placed_f):
        add_figure(doc, n, COL_W_CM - 0.2)
    for n in sorted(set(tables) - placed_t):
        add_table(doc, n, tables[n])

    section_heading(doc, "Declarations", 2)
    for raw in re.split(r"\n\s*\n", parts["declarations"].strip()):
        block = raw.strip()
        if block and not set(block) <= set("-*_ "):
            para(doc, block.replace("\n", " "), size=SMALL_PT, lead=Pt(10.5),
                 space_after=Pt(3))

    section_heading(doc, "References", 2)
    for ref in [r.strip() for r in parts["references"].split("\n\n") if r.strip()]:
        para(doc, ref.replace("\n", " "), size=Pt(8), lead=Pt(9.5),
             hanging=Cm(0.5), align=WD_ALIGN_PARAGRAPH.LEFT, space_after=Pt(3))
    return doc


def main() -> int:
    doc = build()
    doc.save(OUT)
    print(f"wrote {OUT.name}  ({OUT.stat().st_size/1024:.0f} KB)")
    print(f"  A4, two columns at {COL_W_CM:.2f} cm, {BODY_PT.pt} pt on "
          f"{BODY_LEAD.pt} pt, justified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
