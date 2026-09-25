"""
Reading neutral citations and paragraph pinpoints, shared by the retriever, the verifier and the generator.
"""
import re
from typing import Iterable, Optional, Set, Tuple

# [2020] SGCA(I) 02 · [2019] SGHC 180 · [2021] SGHC(A) 5 · [2019] SGSTB 3
NEUTRAL_CITATION = re.compile(r"\[(\d{4})\]\s*(SG[A-Z]+)(?:\s*\(\s*([A-Z])\s*\))?\s*(\d+)", re.IGNORECASE)

# [63] · [63]-[64] · [63]–[70]
PARAGRAPH = re.compile(r"\[(\d{1,4})\](?:\s*[-–—]\s*\[(\d{1,4})\])?")

MAX_RANGE = 200  # a longer "range" is a misreading, not a pinpoint

# A judgment's own numbered paragraph, as the retriever writes it: "[63]" and an em space, like eLitigation.
# Quoted paragraphs of other judgments ("[26] Counsel for Ace submits ...") use a plain space, so they never match.
PARAGRAPH_MARK = "\u2003"
OWN_PARAGRAPH = re.compile(r"^\[(\d{1,4})\]" + PARAGRAPH_MARK, re.MULTILINE)


def neutral_citation(text: Optional[str]) -> Optional[Tuple[int, str, int]]:
    """The first neutral citation in the text, as (year, court, number): [2020] SGCA(I) 02 -> (2020, 'SGCAI', 2)."""
    match = NEUTRAL_CITATION.search(text or "")
    if not match:
        return None
    year, court, division, number = match.groups()
    return int(year), (court + (division or "")).upper(), int(number)


def neutral_citations(text: Optional[str]) -> Set[Tuple[int, str, int]]:
    """Every neutral citation in the text."""
    found = set()
    for year, court, division, number in NEUTRAL_CITATION.findall(text or ""):
        found.add((int(year), (court + (division or "")).upper(), int(number)))
    return found


def paragraph_numbers(pinpoints: Iterable[str]) -> Set[int]:
    """The paragraph numbers cited in pinpoints like '[63]' or '[63]-[64]'. Section and page pinpoints are ignored."""
    numbers: Set[int] = set()
    for pinpoint in pinpoints or []:
        for start, end in PARAGRAPH.findall(pinpoint):
            first = int(start)
            last = int(end) if end else first
            if first <= last <= first + MAX_RANGE:
                numbers.update(range(first, last + 1))
            else:
                numbers.update({first, last})
    return numbers


def own_paragraphs(text: Optional[str]) -> Set[int]:
    """The numbers of the judgment's own paragraphs in retrieved text."""
    return {int(n) for n in OWN_PARAGRAPH.findall(text or "")}


def own_paragraph_number(line: str) -> Optional[int]:
    """The paragraph number if the line starts one of the judgment's own paragraphs."""
    match = OWN_PARAGRAPH.match(line)
    return int(match.group(1)) if match else None


def format_paragraphs(numbers: Iterable[int]) -> str:
    """[63] · [63] and [64] · [63], [64] and [70]"""
    marks = [f"[{n}]" for n in sorted(numbers)]
    if len(marks) < 2:
        return "".join(marks)
    return ", ".join(marks[:-1]) + " and " + marks[-1]
