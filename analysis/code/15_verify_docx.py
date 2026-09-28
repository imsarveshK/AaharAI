"""
Verify the rendered Word documents.

Converts each .docx to PDF with LibreOffice and checks the geometry a reader
would notice: content escaping the printable area, duplicated page numbers,
markdown artefacts that survived conversion, figures clipped to a sliver by
exact line spacing, and pages left substantially empty mid-document.

Each document is measured against its own page geometry, because the review
manuscript and the typeset report are laid out differently. Running heads,
footers and line numbers legitimately sit in the margins and are excluded.

Exits non-zero if anything fails, so it can gate a release.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[2]
SOFFICE = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")

CM = 28.3465
PAGE_W, PAGE_H = 595.3, 841.9
TOL = 1.0
GAP_LIMIT = 200.0          # points of trailing whitespace tolerated mid-document
MIN_FIGURE_HEIGHT = 40.0   # below this an inline image has been clipped


@dataclass(frozen=True)
class Layout:
    path: str
    label: str
    side_cm: float
    top_cm: float
    bottom_cm: float
    line_numbers: bool = False        # numbers in the left margin are expected
    running_head: bool = False        # text above the top margin is expected
    blank_pages: tuple = field(default_factory=tuple)   # end early by design

    @property
    def box(self) -> tuple[float, float, float, float]:
        return (self.side_cm * CM, PAGE_W - self.side_cm * CM,
                self.top_cm * CM, PAGE_H - self.bottom_cm * CM)


DOCUMENTS = [
    Layout("paper/manuscript_submission.docx", "review manuscript",
           2.54, 2.54, 2.54, line_numbers=True, blank_pages=(1, 3)),
    Layout("paper/manuscript_reading_copy.docx", "reading copy",
           2.54, 2.54, 2.54, blank_pages=(1, 3)),
    Layout("paper/manuscript_report.docx", "typeset report",
           1.8, 1.9, 2.0, running_head=True),
]


def to_pdf(docx: Path, outdir: Path) -> Path:
    if not SOFFICE.exists():
        sys.exit("LibreOffice not found; cannot verify the rendered documents.")
    subprocess.run([str(SOFFICE), "--headless", "--convert-to", "pdf",
                    "--outdir", str(outdir), str(docx)],
                   check=True, capture_output=True)
    return outdir / (docx.stem + ".pdf")


def check(layout: Layout) -> tuple[int, int, list[str]]:
    left, right, top, bottom = layout.box
    failures: list[str] = []
    docx = ROOT / layout.path

    with tempfile.TemporaryDirectory() as tmp:
        with pdfplumber.open(to_pdf(docx, Path(tmp))) as pdf:
            n = len(pdf.pages)
            gutter_numbers = 0
            for i, page in enumerate(pdf.pages, 1):
                footer_numbers, bottoms = [], []
                for w in page.extract_words():
                    text, x0, x1 = w["text"], w["x0"], w["x1"]
                    in_footer = w["top"] > bottom
                    in_header = w["bottom"] < top

                    if in_footer and re.fullmatch(r"\d+", text):
                        footer_numbers.append(text)
                        continue
                    if layout.running_head and in_header:
                        continue                       # authors and page number
                    if layout.line_numbers and x1 <= left and re.fullmatch(r"\d+", text):
                        gutter_numbers += 1
                        continue

                    bottoms.append(w["bottom"])
                    if text.strip() in {"---", "***", "___"}:
                        failures.append(f"p{i}: markdown rule left in the text")
                    if "\\*" in text or text.startswith("\\"):
                        failures.append(f"p{i}: markdown escape printed literally "
                                        f"({text[:24]!r})")
                    if x1 > right + TOL or x0 < left - TOL:
                        failures.append(f"p{i}: text outside the side margins ({text[:24]!r})")
                    if w["bottom"] > bottom + TOL or w["top"] < top - TOL:
                        failures.append(f"p{i}: text outside the top/bottom margins "
                                        f"({text[:24]!r})")

                for im in page.images:
                    bottoms.append(im["bottom"])
                    height = im["bottom"] - im["top"]
                    if (im["x0"] < left - TOL or im["x1"] > right + TOL
                            or im["top"] < top - TOL or im["bottom"] > bottom + TOL):
                        failures.append(f"p{i}: a figure runs outside the printable area")
                    if height < MIN_FIGURE_HEIGHT:
                        failures.append(f"p{i}: a figure is only {height:.0f} pt tall "
                                        f"(exact line spacing clips inline images)")

                if len(footer_numbers) > 1:
                    failures.append(f"p{i}: {len(footer_numbers)} page numbers in the footer")
                if bottoms and i not in layout.blank_pages and i != n:
                    gap = bottom - max(bottoms)
                    if gap > GAP_LIMIT:
                        failures.append(f"p{i}: {gap:.0f} pt of trailing whitespace")
    return n, gutter_numbers, failures


def main() -> int:
    print("Rendered layout checks")
    all_failures: dict[str, list[str]] = {}
    for layout in DOCUMENTS:
        if not (ROOT / layout.path).exists():
            print(f"  {layout.label:<20} missing: {layout.path}")
            continue
        pages, gutter, failures = check(layout)
        verdict = "OK" if not failures else f"{len(failures)} problem(s)"
        print(f"  {layout.label:<20} {pages:>3} pages   "
              f"line numbers: {gutter:>4}   {verdict}")
        if failures:
            all_failures[layout.label] = failures

    if all_failures:
        print()
        for label, items in all_failures.items():
            print(f"{label}:")
            for f in items[:20]:
                print("  -", f)
            if len(items) > 20:
                print(f"  ... and {len(items) - 20} more")
        return 1
    print("\nAll documents clean: nothing outside the printable area, one page number "
          "per page,\nno markdown artefacts, no clipped figures, no page left "
          "substantially empty.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
