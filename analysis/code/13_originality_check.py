"""
Flag verbatim overlap between the manuscript and its source documents.

Similarity software matches strings of consecutive words, so this reproduces that
test directly: every n-word shingle of the manuscript is compared against the
official questionnaire, estimation manual, survey report and unit-level data note.
Anything that matches and is not inside a marked quotation is reported for rewording.

Quoted material is expected to match and is excluded, since a quotation with an
attribution is a citation, not an overlap to remove.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANUSCRIPT = ROOT / "paper/manuscript.md"
SOURCE_DIR = Path("/tmp/srctext")

# Similarity reports typically surface runs of this length upward.
SHINGLE = 8


def normalise(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[‘’]", "'", text)
    text = re.sub(r"[“”]", '"', text)
    text = re.sub(r"[^a-z0-9'\s]", " ", text)
    return text.split()


def shingles(words: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


# A genuine inline quotation in this manuscript is a phrase or a sentence, not
# paragraphs. Without a cap, an opening quote pairs with the *next* quote mark
# anywhere in the text and swallows everything between them, which silently
# excludes most of the manuscript from the comparison.
MAX_QUOTE_CHARS = 400


def quoted_spans(md: str) -> list[str]:
    """Text inside double quotes is a citation, not an overlap to remove."""
    spans = re.findall(r'"([^"\n]{20,%d})"' % MAX_QUOTE_CHARS, md)
    return spans


def main() -> int:
    md = MANUSCRIPT.read_text()
    body = md.split("## References")[0]

    quoted_words = set()
    for span in quoted_spans(body):
        quoted_words |= shingles(normalise(span), SHINGLE)

    manuscript_words = normalise(body)
    manuscript_shingles = shingles(manuscript_words, SHINGLE)

    findings: dict[str, set[tuple[str, ...]]] = {}
    for src in sorted(SOURCE_DIR.glob("*.txt")):
        src_shingles = shingles(normalise(src.read_text(errors="replace")), SHINGLE)
        hits = (manuscript_shingles & src_shingles) - quoted_words
        if hits:
            findings[src.stem] = hits

    total = sum(len(v) for v in findings.values())
    pct = 100.0 * total / max(len(manuscript_shingles), 1)
    print(f"manuscript {SHINGLE}-word shingles : {len(manuscript_shingles):,}")
    print(f"quoted shingles excluded          : {len(quoted_words):,}")
    print(f"unquoted overlaps with sources    : {total} ({pct:.2f}%)")
    if not findings:
        print("\nNo unquoted run of eight or more words matches any source document.")
        return 0
    print()
    for name, hits in findings.items():
        print(f"[{name}] {len(hits)} run(s):")
        for h in sorted(hits)[:20]:
            print("   ...", " ".join(h), "...")
    return 1


if __name__ == "__main__":
    sys.exit(main())
