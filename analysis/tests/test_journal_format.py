"""
Check the manuscript against the submission requirements it is formatted for.

Sources for the limits, from Elsevier's author guidance: structured abstracts of
up to 250 words; 3 to 5 highlights of at most 85 characters including spaces;
sections numbered 1., 1.1., 1.2.; every table and figure cited in the text.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MD = (ROOT / "paper/manuscript.md").read_text()

ABSTRACT_WORD_LIMIT = 250
HIGHLIGHT_CHAR_LIMIT = 85
HIGHLIGHT_MIN, HIGHLIGHT_MAX = 3, 5
N_TABLES, N_FIGURES = 5, 4


def abstract() -> str:
    text = MD[MD.index("**Background.**"):MD.index("**Keywords:**")]
    return re.sub(r"\*\*(Background|Methods|Results|Conclusions)\.\*\*", "", text)


def highlights() -> list[str]:
    block = MD.split("## Highlights", 1)[1].split("---")[0]
    return [l[2:].strip() for l in block.strip().split("\n") if l.startswith("- ")]


def test_abstract_within_word_limit() -> None:
    n = len(abstract().split())
    assert n <= ABSTRACT_WORD_LIMIT, f"abstract is {n} words, limit {ABSTRACT_WORD_LIMIT}"


def test_abstract_is_structured() -> None:
    for label in ("Background", "Methods", "Results", "Conclusions"):
        assert f"**{label}.**" in MD, f"abstract lacks a {label} heading"


def test_highlight_count() -> None:
    n = len(highlights())
    assert HIGHLIGHT_MIN <= n <= HIGHLIGHT_MAX, f"{n} highlights; allowed 3 to 5"


@pytest.mark.parametrize("text", highlights())
def test_highlight_length(text: str) -> None:
    assert len(text) <= HIGHLIGHT_CHAR_LIMIT, \
        f"highlight is {len(text)} characters, limit {HIGHLIGHT_CHAR_LIMIT}: {text!r}"


def test_sections_are_numbered() -> None:
    tops = re.findall(r"^## (\d+)\. ", MD, re.M)
    assert tops == [str(i) for i in range(1, len(tops) + 1)], \
        f"top-level sections are not consecutively numbered: {tops}"
    subs = re.findall(r"^### (\d+)\.(\d+) ", MD, re.M)
    for parent in {p for p, _ in subs}:
        got = [int(c) for p, c in subs if p == parent]
        assert got == list(range(1, len(got) + 1)), \
            f"subsections of section {parent} are not consecutive: {got}"


@pytest.mark.parametrize("n", range(1, N_TABLES + 1))
def test_every_table_is_cited(n: int) -> None:
    body = MD.split("## References")[0]
    assert re.search(rf"\(Table {n}[,)]|\bTable {n}\b", body), f"Table {n} is never cited"


@pytest.mark.parametrize("n", range(1, N_FIGURES + 1))
def test_every_figure_is_cited(n: int) -> None:
    body = MD.split("## References")[0]
    assert re.search(rf"\(Figure {n}[A-B,)]|\bFigure {n}\b", body), \
        f"Figure {n} is never cited"


def test_keyword_count() -> None:
    line = MD.split("**Keywords:**", 1)[1].split("\n")[0]
    separator = ";" if ";" in line else ","
    kws = [k.strip() for k in line.split(separator) if k.strip()]
    assert 3 <= len(kws) <= 8, f"{len(kws)} keywords; expected between 3 and 8"
