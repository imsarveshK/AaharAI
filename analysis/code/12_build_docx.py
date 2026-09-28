"""
Build the submission-ready Word manuscript.

Formatted to the conventions Elsevier and comparable Q1 journals ask for in a
review copy: A4, 2.54 cm margins, 12 pt Times New Roman, double line spacing,
continuous line numbers, page numbers, left-aligned body text, numbered sections,
table captions above and figure captions below.

Layout is entirely paragraph-flow: no floating frames, no text boxes, no absolute
positioning. Word reflows the document, so nothing can overlap. Figures are scaled
to the printable width so none can overrun a margin.
"""
from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "paper"
FIGDIR = ROOT / "analysis/output/figures"
OUT = PAPER / "manuscript_submission.docx"        # journal copy
OUT_CLEAN = PAPER / "manuscript_reading_copy.docx"  # co-author copy

# A4 with 2.54 cm margins leaves 15.92 cm of printable width. Figures are held a
# little inside that so no rounding can push one past a margin.
PAGE_W, PAGE_H = Cm(21.0), Cm(29.7)
MARGIN = Cm(2.54)
CONTENT_W_CM = 21.0 - 2 * 2.54
# Figures are set narrower than the text column. At full column width a figure
# plus caption fills close to half a double-spaced page, so it is displaced
# whenever it will not fit in what remains, leaving the preceding page half
# empty. 13.7 cm keeps every figure legible while shrinking that block enough to
# fit far more often. FIGURE_WIDTHS_CM overrides it per figure where needed.
FIG_W = Cm(13.7)

# How many leading table rows are held to the caption, so a caption is never left
# at the foot of a page above a header and one lone row.
KEEP_ROWS_WITH_CAPTION = 2

# Author list. Affiliations are placeholders: all four are marked to a single
# affiliation, which is the common case; split the markers if they differ.
AUTHORS = [
    ("Pratik Kulkarni", "1", True),      # True marks the corresponding author
    ("Sarvesh Kulkarni", "1", False),
    ("Shivraj More", "1", False),
    ("Atharva Mohite", "1", False),
]
AFFILIATIONS = [
    ("1", "Department of Computer Science and Engineering, "
          "SKN Sinhgad College of Engineering, Pandharpur, Maharashtra, India"),
]
CORRESPONDING_CONTACT = "pratikkulkarni8550@gmail.com"

BODY_FONT = "Times New Roman"
BODY_SIZE = Pt(12)
TABLE_SIZE = Pt(9)
CAPTION_SIZE = Pt(10)

FIGURE_CAPTIONS = {
    1: ("fig1_adoption",
        "Online purchasing by domain and sector (A), and adoption of online food "
        "buying across deciles of monthly per capita consumption expenditure (B). "
        "Bars and bands are 95% confidence intervals."),
    2: ("fig2_category_mix",
        "Share of the 19,842 households buying any food online who bought each "
        "category, with 95% confidence intervals. Groceries used a 30-day reference "
        "period and the other categories 7 days, so it is not comparable with them."),
    3: ("fig3_budget_shares",
        "Adjusted difference in each food group's share of the household food budget "
        "between households that did and did not buy food online, in percentage "
        "points, with 95% confidence intervals."),
    4: ("fig4_robustness",
        "The vegetable and packaged-processed-food contrasts across five "
        "specifications, in percentage points of the food budget."),
}

# Figures and tables are placed after the paragraph that first cites them.
FIGURE_ANCHORS = {1: "Figure 1A", 2: "Figure 2", 3: "Figure 3", 4: "Figure 4"}
TABLE_ANCHORS = {1: "Table 1", 2: "Table 2", 3: "Table 3", 4: "Table 4", 5: "Table 5"}

TABLE_TITLES = {
    1: "Household characteristics by online food purchase status.",
    2: "Prevalence of online purchasing, by domain and sector.",
    3: "Adoption of online food purchasing (survey-weighted logistic regression).",
    4: "Food budget composition, in percentage points of the food budget.",
    5: "Levels, quantities and unit values.",
}
TABLE_NOTES = {
    1: "Weighted estimates with design-based standard errors in parentheses. "
       "MPCE is monthly per capita consumption expenditure.",
    2: "Groceries was asked over a 30-day reference period; the other eight food "
       "categories over 7 days. Standard errors in parentheses.",
    3: "Reference levels: social group Others, religion Hinduism, household type "
       "Others. State and survey-month fixed effects included and not shown.",
    4: "Adjusted differences are coefficients on any online food purchase from "
       "weighted linear models with the full covariate set and state and "
       "survey-month fixed effects. Matched differences come from coarsened exact "
       "matching on state, sector, MPCE decile, education band, household-size band "
       "and household internet use. E-values are computed on the ratio of matched "
       "shares. Positive values indicate a larger share among online buyers. The "
       "share models use 261,887 households, since a budget share is undefined for "
       "the eight households reporting no food expenditure.",
    5: "Log outcomes are natural logarithms of one plus the per-capita 30-day value, "
       "so coefficients approximate proportional differences. Weighted levels for "
       "the same outcomes are in Table 1.",
}


# --------------------------------------------------------------------------- #
# Document chrome
# --------------------------------------------------------------------------- #

def configure_styles(doc: Document) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = BODY_SIZE
    normal.font.color.rgb = RGBColor(0, 0, 0)
    rpr = normal.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), BODY_FONT)

    pf = normal.paragraph_format
    pf.line_spacing = 2.0
    pf.space_after = Pt(0)
    pf.space_before = Pt(0)
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf.widow_control = True


def configure_section(section, line_numbers: bool = True) -> None:
    section.page_width, section.page_height = PAGE_W, PAGE_H
    for side in ("top", "bottom", "left", "right"):
        setattr(section, f"{side}_margin", MARGIN)
    if line_numbers:
        ln = OxmlElement("w:lnNumType")
        ln.set(qn("w:countBy"), "1")
        ln.set(qn("w:restart"), "continuous")
        ln.set(qn("w:distance"), "360")
        section._sectPr.append(ln)


def add_page_numbers(section) -> None:
    """Centre a PAGE field in the footer.

    add_section clones the previous sectPr, so a later section can share the
    earlier section's footer part. Unlinking first, and clearing whatever the
    part already holds, keeps exactly one page number per page.
    """
    footer = section.footer
    footer.is_linked_to_previous = False
    p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    for run in list(p.runs):
        run._r.getparent().remove(run._r)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.line_spacing = 1.0
    run = p.add_run()
    run.font.name = BODY_FONT
    run.font.size = Pt(10)
    for instr, kind in [(None, "begin"), ("PAGE", "instr"), (None, "end")]:
        el = OxmlElement("w:fldChar") if kind != "instr" else OxmlElement("w:instrText")
        if kind == "instr":
            el.set(qn("xml:space"), "preserve")
            el.text = " PAGE "
        else:
            el.set(qn("w:fldCharType"), kind)
        run._r.append(el)


def suppress_line_numbers(paragraph) -> None:
    """Turn line numbering off for one paragraph.

    Section-level numbering leaks onto the title page when the following section
    break is continuous, so the title page paragraphs opt out individually. This
    is the setting Word itself uses and it survives the round trip.
    """
    pPr = paragraph._p.get_or_add_pPr()
    pPr.append(OxmlElement("w:suppressLineNumbers"))


def keep_with_next(paragraph) -> None:
    paragraph.paragraph_format.keep_with_next = True


# --------------------------------------------------------------------------- #
# Inline markdown
# --------------------------------------------------------------------------- #

INLINE = re.compile(r"(\*\*.+?\*\*|\*[^*\n]+?\*|`[^`\n]+?`)")


def add_runs(paragraph, text: str, size: Pt | None = None,
             base_italic: bool = False) -> None:
    """Render **bold**, *italic* and `code` into runs of one paragraph."""
    text = text.replace("‑", "-")
    for part in INLINE.split(text):
        if not part:
            continue
        bold = italic = mono = False
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            part, bold = part[2:-2], True
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            part, italic = part[1:-1], True
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            part, mono = part[1:-1], True
        run = paragraph.add_run(part)
        run.bold = bold
        run.italic = italic or base_italic
        run.font.name = "Courier New" if mono else BODY_FONT
        run.font.size = (size or BODY_SIZE) if not mono else Pt((size or BODY_SIZE).pt - 1)


def body_paragraph(doc: Document, text: str, *, size=None, italic=False,
                   space_after=Pt(0), indent_first=False, align=None) -> object:
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after = space_after
    if align is not None:
        pf.alignment = align
    if indent_first:
        pf.first_line_indent = Cm(0.75)
    add_runs(p, text, size=size, base_italic=italic)
    return p


def heading(doc: Document, text: str, level: int) -> object:
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.LEFT     # never justify a heading
    pf.space_before = Pt(18 if level == 1 else 12)
    pf.space_after = Pt(6)
    pf.keep_with_next = True
    run = p.add_run(text)
    run.bold = True
    run.italic = level >= 3
    run.font.name = BODY_FONT
    run.font.size = Pt(14 if level == 1 else 12)
    return p


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #

def parse_markdown_tables(text: str) -> dict[int, list[list[str]]]:
    """Pull the numbered tables out of paper/tables.md as rows of cells."""
    tables: dict[int, list[list[str]]] = {}
    for m in re.finditer(r"## Table (\d+)\.[^\n]*\n(.*?)(?=\n## |\Z)", text, re.S):
        number = int(m.group(1))
        rows = []
        for line in m.group(2).split("\n"):
            line = line.strip()
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue          # the markdown alignment rule
            rows.append(cells)
        if rows:
            tables[number] = rows
    return tables


def set_cell_borders(cell) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "bottom"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "6")
        el.set(qn("w:color"), "000000")
        borders.append(el)
    tcPr.append(borders)


def add_table(doc: Document, number: int, rows: list[list[str]]) -> None:
    caption = doc.add_paragraph()
    caption.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    caption.paragraph_format.space_before = Pt(12)
    caption.paragraph_format.space_after = Pt(4)
    caption.paragraph_format.line_spacing = 1.0
    caption.paragraph_format.keep_with_next = True
    r = caption.add_run(f"Table {number}. ")
    r.bold = True
    r.font.name, r.font.size = BODY_FONT, CAPTION_SIZE
    add_runs(caption, TABLE_TITLES[number], size=CAPTION_SIZE)

    ncols = max(len(r) for r in rows)
    table = doc.add_table(rows=0, cols=ncols)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.autofit = False

    # The label column carries the text; numeric columns share what is left.
    label_w = min(5.2, CONTENT_W_CM * 0.34)
    num_w = (CONTENT_W_CM - label_w) / max(ncols - 1, 1)
    widths = [Cm(label_w)] + [Cm(num_w)] * (ncols - 1)

    for i, cells in enumerate(rows):
        row = table.add_row()
        for j in range(ncols):
            cell = row.cells[j]
            cell.width = widths[j]
            text = cells[j] if j < len(cells) else ""
            text = text.replace("*", "")
            p = cell.paragraphs[0]
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.space_before = Pt(1)
            if j > 0:
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            run = p.add_run(text)
            run.bold = (i == 0)
            run.font.name = BODY_FONT
            run.font.size = TABLE_SIZE
        trPr = row._tr.get_or_add_trPr()
        trPr.append(OxmlElement("w:cantSplit"))   # never break one row across pages
        if i == 0:
            trPr.append(OxmlElement("w:tblHeader"))   # repeat header on each page
        if i <= KEEP_ROWS_WITH_CAPTION:
            # Hold the header and the first rows to the caption above them.
            for cell_p in row.cells[0].paragraphs:
                cell_p.paragraph_format.keep_with_next = True

    note = doc.add_paragraph()
    note.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    note.paragraph_format.space_before = Pt(4)
    note.paragraph_format.space_after = Pt(12)
    note.paragraph_format.line_spacing = 1.0
    note.paragraph_format.keep_together = True   # never split the note itself
    nr = note.add_run("Note. ")
    nr.italic = True
    nr.font.name, nr.font.size = BODY_FONT, Pt(9)
    add_runs(note, TABLE_NOTES[number], size=Pt(9))


def add_figure(doc: Document, number: int) -> None:
    stem, caption = FIGURE_CAPTIONS[number]
    holder = doc.add_paragraph()
    holder.alignment = WD_ALIGN_PARAGRAPH.CENTER
    holder.paragraph_format.space_before = Pt(6)
    holder.paragraph_format.space_after = Pt(4)
    holder.paragraph_format.line_spacing = 1.0
    holder.paragraph_format.keep_with_next = True
    holder.add_run().add_picture(str(FIGDIR / f"{stem}.png"), width=FIG_W)

    cap = doc.add_paragraph()
    cap.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    cap.paragraph_format.space_after = Pt(12)
    cap.paragraph_format.line_spacing = 1.0
    r = cap.add_run(f"Figure {number}. ")
    r.bold = True
    r.font.name, r.font.size = BODY_FONT, CAPTION_SIZE
    add_runs(cap, caption, size=CAPTION_SIZE)


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #

def split_manuscript(md: str) -> dict:
    title = md.split("\n", 1)[0].lstrip("# ").strip()
    abstract = md.split("## Abstract", 1)[1].split("**Keywords:**")[0].strip()
    keywords = md.split("**Keywords:**", 1)[1].split("\n")[0].strip()
    highlights = [l[2:].strip() for l in
                  md.split("## Highlights", 1)[1].split("---")[0].strip().split("\n")
                  if l.startswith("- ")]
    main = md.split("## Highlights", 1)[1].split("---", 2)[-1]
    body, refs = main.split("## References", 1)
    body, decls = body.split("## Declarations", 1)
    return {"title": title, "abstract": abstract, "keywords": keywords,
            "highlights": highlights, "body": body.strip(),
            "declarations": decls.strip().rstrip("-").strip(),
            "references": refs.strip()}


def title_page(doc: Document, parts: dict) -> None:
    # Everything on the title page is left-aligned: justifying a title or an
    # affiliation stretches a short line across the column.
    first = len(doc.paragraphs)

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(18)
    p.paragraph_format.line_spacing = 1.5
    run = p.add_run(parts["title"])
    run.bold = True
    run.font.name, run.font.size = BODY_FONT, Pt(16)

    def label(text: str) -> None:
        h = doc.add_paragraph()
        h.paragraph_format.space_before = Pt(12)
        h.paragraph_format.space_after = Pt(2)
        h.paragraph_format.line_spacing = 1.0
        r = h.add_run(text)
        r.bold = True
        r.font.name, r.font.size = BODY_FONT, Pt(11)

    def value(text: str, italic: bool = False) -> None:
        v = doc.add_paragraph()
        v.paragraph_format.space_after = Pt(0)
        v.paragraph_format.line_spacing = 1.0
        add_runs(v, text, size=Pt(11), base_italic=italic)

    # Authors, with affiliation markers and an asterisk on the corresponding author.
    label("Authors")
    authors = doc.add_paragraph()
    authors.paragraph_format.space_after = Pt(0)
    authors.paragraph_format.line_spacing = 1.0
    for i, (name, marker, corresponding) in enumerate(AUTHORS):
        if i:
            sep = authors.add_run(", ")
            sep.font.name, sep.font.size = BODY_FONT, Pt(11)
        r = authors.add_run(name)
        r.font.name, r.font.size = BODY_FONT, Pt(11)
        sup = authors.add_run(marker + ("*" if corresponding else ""))
        sup.font.superscript = True
        sup.font.name, sup.font.size = BODY_FONT, Pt(11)

    label("Affiliations")
    for marker, text in AFFILIATIONS:
        v = doc.add_paragraph()
        v.paragraph_format.space_after = Pt(0)
        v.paragraph_format.line_spacing = 1.0
        sup = v.add_run(marker)
        sup.font.superscript = True
        sup.font.name, sup.font.size = BODY_FONT, Pt(11)
        add_runs(v, " " + text, size=Pt(11))

    corresponding = next(n for n, _, c in AUTHORS if c)
    label("Corresponding author")
    value(f"* {corresponding}, {CORRESPONDING_CONTACT}")

    label("Word count")
    abstract_words = len(re.sub(r"\*\*(Background|Methods|Results|Conclusions)\.\*\*",
                                "", parts["abstract"]).split())
    value(f"Main text {len(parts['body'].split()):,} words; "
          f"abstract {abstract_words} words; 5 tables; 4 figures")

    note = doc.add_paragraph()
    note.paragraph_format.space_before = Pt(24)
    note.paragraph_format.line_spacing = 1.0
    add_runs(note, "Bracketed fields are to be completed before submission.",
             size=Pt(10), base_italic=True)

    for para in doc.paragraphs[first:]:
        para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        suppress_line_numbers(para)


def render_block(doc: Document, text: str, figures: dict, tables: dict,
                 placed_f: set, placed_t: set) -> None:
    """Render one markdown block, then any figure or table it first cites."""
    for raw in re.split(r"\n\s*\n", text.strip()):
        block = raw.strip()
        if not block or set(block) <= set("-*_ "):
            continue          # markdown horizontal rule, not content
        if block.startswith("### "):
            heading(doc, block[4:].strip(), 3)
        elif block.startswith("## "):
            heading(doc, block[3:].strip(), 2)
        elif block.startswith("- "):
            for line in block.split("\n"):
                if not line.strip().startswith("- "):
                    continue
                p = doc.add_paragraph(style="List Bullet")
                p.paragraph_format.line_spacing = 2.0
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.left_indent = Cm(0.75)
                add_runs(p, line.strip()[2:])
        else:
            body_paragraph(doc, block.replace("\n", " "))

        for n, anchor in FIGURE_ANCHORS.items():
            if n not in placed_f and anchor in block:
                add_figure(doc, n)
                placed_f.add(n)
        for n, anchor in TABLE_ANCHORS.items():
            if n not in placed_t and anchor in block and n in tables:
                add_table(doc, n, tables[n])
                placed_t.add(n)


def build(line_numbers: bool = True) -> Document:
    """Assemble the manuscript.

    Journals ask for continuous line numbering so reviewers can cite a line, so
    the submission copy carries it. A reading copy for co-authors does not need
    it, hence the switch.
    """
    parts = split_manuscript((PAPER / "manuscript.md").read_text())
    tables = parse_markdown_tables((PAPER / "tables.md").read_text())

    doc = Document()
    configure_styles(doc)
    configure_section(doc.sections[0], line_numbers=False)
    add_page_numbers(doc.sections[0])
    title_page(doc, parts)

    # A NEW_PAGE section break starts the body on its own page without the extra
    # empty paragraph that add_page_break leaves behind. That paragraph belongs to
    # the numbered section and would print line number 1 at the foot of the title
    # page, which is exactly the leak this avoids.
    sec = doc.add_section(WD_SECTION.NEW_PAGE)
    configure_section(sec, line_numbers=line_numbers)
    add_page_numbers(sec)

    heading(doc, "Abstract", 2)
    for para in parts["abstract"].split("\n\n"):
        body_paragraph(doc, para.strip(), space_after=Pt(6))
    kw = doc.add_paragraph()
    kw.paragraph_format.space_before = Pt(6)
    r = kw.add_run("Keywords: ")
    r.bold = True
    r.font.name, r.font.size = BODY_FONT, BODY_SIZE
    add_runs(kw, parts["keywords"])

    heading(doc, "Highlights", 2)
    for h in parts["highlights"]:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.line_spacing = 2.0
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.left_indent = Cm(0.75)
        add_runs(p, h)

    doc.add_page_break()
    placed_f: set[int] = set()
    placed_t: set[int] = set()
    render_block(doc, parts["body"], FIGURE_CAPTIONS, tables, placed_f, placed_t)

    # Anything never cited by name still belongs in the document.
    for n in sorted(set(FIGURE_CAPTIONS) - placed_f):
        add_figure(doc, n)
    for n in sorted(set(tables) - placed_t):
        add_table(doc, n, tables[n])

    heading(doc, "Declarations", 2)
    render_block(doc, parts["declarations"], {}, {}, set(), set())

    heading(doc, "References", 2)
    for ref in [r.strip() for r in parts["references"].split("\n\n") if r.strip()]:
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.left_indent = Cm(1.0)
        pf.first_line_indent = Cm(-1.0)   # hanging indent
        pf.space_after = Pt(6)
        pf.line_spacing = 2.0
        pf.alignment = WD_ALIGN_PARAGRAPH.LEFT   # hanging-indent refs read badly justified
        add_runs(p, ref.replace("\n", " "))

    return doc


def main() -> int:
    for path, numbered in [(OUT, True), (OUT_CLEAN, False)]:
        build(line_numbers=numbered).save(path)
        kind = "with line numbers" if numbered else "no line numbers"
        print(f"wrote {path.name:<32} {path.stat().st_size/1024:>4.0f} KB  ({kind})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
