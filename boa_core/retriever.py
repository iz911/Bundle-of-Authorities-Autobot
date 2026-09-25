"""
Looks up Singapore judgments on eLitigation and sends every other authority to a placeholder sheet.

Only text actually fetched from eLitigation is ever used, and only after the verifier has confirmed it is the
judgment cited and contains every cited paragraph. Nothing is typed in or kept on file here: an authority that
can't be found and verified gets a placeholder sheet for the lawyer to fill by hand.

Legislation isn't looked up yet. Singapore Statutes Online needs a reader of its own, and until one is built
statutes and regulations get placeholder sheets too.
"""
import re
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from .citations import PARAGRAPH_MARK, neutral_citation
from .models import AuthorityCategory, AuthorityItem, RetrievalStatus
from .verifier import INSERT_BY_HAND, triage_authority

ELITIGATION_JUDGMENTS = "https://www.elitigation.sg/gd/s"
TIMEOUT_SECONDS = 10

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (Legal-BOA-Autobot/1.0)"
}

NOT_LOOKED_UP = {
    AuthorityCategory.SINGAPORE_STATUTES:
        "Legislation isn’t looked up automatically yet. Insert the cited provisions by hand from Singapore Statutes Online.",
    AuthorityCategory.REGULATIONS:
        "Subsidiary legislation and rules aren’t looked up automatically yet. Insert the cited provisions by hand.",
    AuthorityCategory.FOREIGN_CASES:
        "Foreign cases aren’t available from a free official source. Insert the report by hand, for example from Westlaw, Lexis or the ICLR.",
    AuthorityCategory.FOREIGN_STATUTES:
        "Foreign legislation isn’t looked up. Insert it by hand from the official source for that country.",
    AuthorityCategory.SECONDARY_SOURCES:
        "Books and articles aren’t looked up. Insert the cited pages by hand.",
    AuthorityCategory.MISCELLANEOUS:
        "This kind of source isn’t looked up. Insert it by hand.",
}
CHECKING_OFF = f"Not looked up, because checking was switched off. {INSERT_BY_HAND}"
NO_NEUTRAL_CITATION = (
    "Only judgments with a neutral citation, such as [2020] SGCA 2, can be looked up on eLitigation. "
    + INSERT_BY_HAND
)
NOT_ON_ELITIGATION = (
    "This judgment isn’t on eLitigation. It may be reported only in the law reports or available only on LawNet. "
    + INSERT_BY_HAND
)
UNREACHABLE = "eLitigation couldn’t be reached. Run the check again, or insert the report by hand."

BLOCKS = {"div", "p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th", "table", "tr", "tbody", "ul", "ol", "blockquote"}
NUMBERED = re.compile(r"^(\d{1,4})[\u2002\u2003\u00a0\s]+(\S.*)$", re.DOTALL)


def elitigation_url(authority: AuthorityItem) -> Optional[str]:
    """The eLitigation address for the authority's neutral citation, e.g. [2020] SGCA(I) 02 -> .../2020_SGCAI_2."""
    found = neutral_citation(authority.citation) or neutral_citation(authority.raw_citation)
    if not found:
        return None
    year, court, number = found
    return f"{ELITIGATION_JUDGMENTS}/{year}_{court}_{number}"


def _has_block_child(tag: Tag) -> bool:
    return any(isinstance(child, Tag) and (child.name in BLOCKS or _has_block_child(child)) for child in tag.children)


def _is_judgment_block(tag: Tag) -> bool:
    """eLitigation's own paragraph, quote and heading blocks (class "Judg-..."), each read whole."""
    return tag.name in BLOCKS and any(c.startswith("Judg-") for c in (tag.get("class") or []))


def _is_line(tag: Tag) -> bool:
    return tag.name in BLOCKS and (_is_judgment_block(tag) or not _has_block_child(tag))


def judgment_text(html: str) -> str:
    """
    The judgment on an eLitigation page, one block per line, without the site's menus.
    The judgment's own numbered paragraphs are written "[63]" + an em space, so pinpoints can be checked and
    highlighted exactly, and quotations of other judgments' paragraphs are never mistaken for them.
    A paragraph with a block inside it (a link, a list) stays one paragraph.
    """
    body = BeautifulSoup(html, "html.parser").select_one("#divJudgement")
    if body is None:
        return ""

    lines: List[str] = []
    for tag in body.find_all(_is_line):
        if tag.find_parent(_is_judgment_block):
            continue  # already read as part of its paragraph
        text = re.sub(r"\s+", " ", "".join(s for s in tag.strings if not isinstance(s, Comment))).strip()
        if not text:
            continue
        numbered = NUMBERED.match(text)
        if numbered and "Judg-1" in (tag.get("class") or []):
            text = f"[{numbered.group(1)}]{PARAGRAPH_MARK}{numbered.group(2)}"
        lines.append(text)
    return "\n".join(lines)


class AuthorityRetriever:
    """Looks up each authority, or explains why it gets a placeholder sheet."""

    def __init__(self, use_live_network: bool = True):
        self.use_live_network = use_live_network

    @staticmethod
    def _placeholder(authority: AuthorityItem, note: str) -> AuthorityItem:
        authority.retrieval_status = RetrievalStatus.MANUAL_PLACEHOLDER
        authority.retrieval_note = note
        authority.retrieved_text = None
        return authority

    def retrieve(self, authority: AuthorityItem) -> AuthorityItem:
        if authority.category != AuthorityCategory.SINGAPORE_CASES:
            return self._placeholder(authority, NOT_LOOKED_UP.get(authority.category, NOT_LOOKED_UP[AuthorityCategory.MISCELLANEOUS]))
        if not self.use_live_network:
            return self._placeholder(authority, CHECKING_OFF)

        url = elitigation_url(authority)
        if not url:
            return self._placeholder(authority, NO_NEUTRAL_CITATION)

        try:
            payload = self._fetch_judgment(url, authority)
        except requests.RequestException:
            return self._placeholder(authority, UNREACHABLE)
        if payload is None:
            return self._placeholder(authority, NOT_ON_ELITIGATION)

        status, note, text = triage_authority(authority, payload)
        authority.retrieval_status = status
        authority.retrieval_note = note
        authority.retrieved_text = text
        return authority

    def _fetch_judgment(self, url: str, authority: AuthorityItem) -> Optional[Dict[str, Any]]:
        """The judgment from eLitigation, or None if eLitigation doesn't have it."""
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT_SECONDS)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding if not resp.encoding or resp.encoding.lower() == "iso-8859-1" else resp.encoding
        content = judgment_text(resp.text)
        if not content:
            return None
        return {
            "title": authority.title,
            "citation": "",
            "content": content,
            "source": url.replace("https://www.", ""),
        }


def retrieve_all(authorities: List[AuthorityItem], use_live_network: bool = True) -> List[AuthorityItem]:
    """Retrieves and triages all authorities in a list."""
    retriever = AuthorityRetriever(use_live_network=use_live_network)
    for auth in authorities:
        retriever.retrieve(auth)
    return authorities
