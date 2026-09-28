"""
Audit the manuscript for the textual patterns that read as machine-written.

Two kinds of check. The first is a scan for the named patterns in the no-ai-slop
skill: banned vocabulary, empty phrases, binary contrasts, importance puffery,
trailing -ing analysis, and the rest. The second is quantitative: detectors key on
low variation, so sentence-length spread, repeated openers and transition density
are measured rather than guessed at.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANUSCRIPT = ROOT / "paper/manuscript.md"

# "robust" is banned as a vague adjective ("a robust solution"), not as the
# statistical term of art. "Robustness check", "cluster-robust" and "robust
# standard errors" are the field's standard names for specific procedures and
# are exempted rather than reworded into something less precise.
ROBUST_EXEMPT = re.compile(r"robustness check|cluster-robust|robust standard error"
                           r"|robustness (?:of|to)", re.I)

BANNED = ["delve", "foster", "leverage", "utilize", "utilise", "facilitate",
          "empower", "streamline", "robust", "cutting-edge", "paradigm shift",
          "game changer", "tapestry", "realm", "beacon", "multifaceted",
          "meticulous", "intricate", "paramount", "transformative", "elevate",
          "embark", "supercharge", "harness", "ever-evolving"]
EMPTY = ["it's worth noting", "it is worth noting", "it's important to note",
         "at the end of the day", "when it comes to", "at its core",
         "in today's world", "in the age of", "the reality is", "the truth is",
         "in terms of", "going forward", "in this article", "let's dive in"]
PUFFERY = ["stands as a testament", "marks a pivotal moment", "plays a vital role",
           "solidifies its position", "underscores", "highlighting the",
           "showcasing", "reflecting the", "serves as a"]
METADISCOURSE = ["the key point is", "as you can see", "this distinction matters",
                 "in other words", "that said", "it should be noted"]
WEASEL = ["experts agree", "industry reports suggest", "many argue",
          "widely regarded as", "studies show", "research suggests"]
TRANSITIONS = ["furthermore", "moreover", "additionally", "in conclusion",
               "overall", "ultimately", "notably", "importantly", "consequently",
               "nevertheless", "nonetheless", "thus", "hence"]
BINARY = re.compile(r"\b(is|was|are|were)\s+not\s+(just\s+)?[a-z]+[,.]?\s+(it|they)'?s\b"
                    r"|the question isn'?t", re.I)


def body_text(md: str) -> str:
    text = md.split("## References")[0]
    text = text.split("## Highlights")[-1]
    text = re.sub(r"^#{1,6} .*$", "", text, flags=re.M)      # headings
    text = re.sub(r"^\s*[-*]\s.*$", "", text, flags=re.M)    # bullets
    text = re.sub(r"^\s*\|.*$", "", text, flags=re.M)        # tables
    text = re.sub(r"`[^`]*`", "", text)
    return text


def sentences(text: str) -> list[str]:
    text = re.sub(r"\b([A-Z])\.", r"\1", text)               # initials
    text = text.replace("et al.", "et al")
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z(])", text)
    return [s.strip() for s in parts if len(s.split()) >= 4]


def scan(label: str, needles: list[str], text: str) -> int:
    low = ROBUST_EXEMPT.sub(" ", text).lower()
    hits = [(n, low.count(n)) for n in needles if n in low]
    total = sum(c for _, c in hits)
    mark = "clean" if not hits else ", ".join(f"{n} x{c}" for n, c in hits)
    print(f"  {label:<26} {total:>3}   {mark}")
    return total


def main() -> int:
    md = MANUSCRIPT.read_text()
    text = body_text(md)
    sents = sentences(text)

    print("PATTERN SCAN")
    flagged = 0
    flagged += scan("banned vocabulary", BANNED, text)
    flagged += scan("empty phrases", EMPTY, text)
    flagged += scan("importance puffery", PUFFERY, text)
    flagged += scan("interpretive metadiscourse", METADISCOURSE, text)
    flagged += scan("weasel attribution", WEASEL, text)
    binaries = BINARY.findall(text)
    print(f"  {'binary contrasts':<26} {len(binaries):>3}   "
          f"{'clean' if not binaries else binaries[:3]}")
    flagged += len(binaries)
    em = text.count("—")
    print(f"  {'em dashes':<26} {em:>3}   {'clean' if em <= 2 else 'reduce'}")

    print("\nTRANSITION DENSITY  (formulaic connectors per 1,000 words)")
    words = len(text.split())
    low = text.lower()
    tcount = sum(len(re.findall(rf"\b{t}\b", low)) for t in TRANSITIONS)
    used = {t: len(re.findall(rf"\b{t}\b", low)) for t in TRANSITIONS}
    used = {k: v for k, v in used.items() if v}
    print(f"  {tcount} in {words:,} words = {1000*tcount/words:.1f} per 1,000")
    print(f"  {used if used else 'none'}")

    print("\nSENTENCE VARIATION  (uniformity is the machine tell)")
    lens = [len(s.split()) for s in sents]
    print(f"  sentences            {len(lens)}")
    print(f"  mean length          {statistics.mean(lens):.1f} words")
    print(f"  std deviation        {statistics.pstdev(lens):.1f}")
    print(f"  coeff. of variation  {statistics.pstdev(lens)/statistics.mean(lens):.2f}"
          f"   (human academic prose typically 0.40-0.65)")
    print(f"  range                {min(lens)} to {max(lens)} words")
    short = sum(1 for l in lens if l <= 12)
    long_ = sum(1 for l in lens if l >= 35)
    print(f"  <=12 words           {short} ({100*short/len(lens):.0f}%)")
    print(f"  >=35 words           {long_} ({100*long_/len(lens):.0f}%)")

    print("\nREPEATED SENTENCE OPENERS  (first two words)")
    openers = Counter(" ".join(s.split()[:2]).lower().strip(",") for s in sents)
    rep = [(o, c) for o, c in openers.most_common(8) if c > 2]
    for o, c in rep:
        print(f"  {c:>3}x  {o}")
    if not rep:
        print("  none repeated more than twice")

    print("\nPARAGRAPH VARIATION")
    paras = [p for p in re.split(r"\n\s*\n", text) if len(p.split()) > 15]
    plens = [len(p.split()) for p in paras]
    print(f"  paragraphs {len(plens)}, mean {statistics.mean(plens):.0f} words, "
          f"CV {statistics.pstdev(plens)/statistics.mean(plens):.2f}, "
          f"range {min(plens)}-{max(plens)}")

    print(f"\nTOTAL PATTERN HITS: {flagged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
