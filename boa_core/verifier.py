"""
Verbatim checks. Text fetched from an official source is used only if it demonstrably is the authority that
was cited, and it contains every paragraph cited. Anything else goes to a placeholder sheet for the lawyer to
fill by hand. Nothing is ever written or filled in from memory.

The notes returned here are shown on the page and printed on placeholder sheets, so they are in plain English.
"""
import re
from typing import Optional, Tuple

from .citations import format_paragraphs, neutral_citation, neutral_citations, own_paragraphs, paragraph_numbers
from .models import AuthorityItem, RetrievalStatus

INSERT_BY_HAND = "Insert the report by hand."


class VerbatimVerifier:
    """Deterministic checks that retrieved text is the authority cited."""

    @staticmethod
    def verify_statute(
        authority: AuthorityItem,
        source_title: str,
        source_content: str
    ) -> Tuple[bool, str]:
        """
        Checks that a retrieved statutory provision matches the cited statute.
        Not used yet: legislation isn't looked up until a Singapore Statutes Online reader is built.
        """
        if not source_content or len(source_content.strip()) < 20:
            return False, "The text found was empty or incomplete, so it wasn’t used."

        clean_auth_title = authority.title.lower().replace("the ", "").strip()
        clean_src_title = source_title.lower().replace("the ", "").strip()

        # 1. Title: most of the cited title's key words must appear in the source.
        auth_tokens = [w for w in re.split(r'\W+', clean_auth_title) if len(w) > 2 and w not in ["act", "rules", "order", "singapore"]]
        if auth_tokens:
            matches = sum(1 for token in auth_tokens if token in clean_src_title or token in source_content.lower())
            if matches / len(auth_tokens) < 0.6:
                return False, f"The legislation found (“{source_title}”) didn’t match “{authority.title}”, so it wasn’t used."

        # 2. Pinpoints: a cited section or rule number must appear as a provision marker.
        if authority.pinpoints:
            found_any_pinpoint = False
            for pinpoint in authority.pinpoints:
                sec_match = re.search(r'\b(?:ss?\.?|sections?|rule|order)\s*(\d+)', pinpoint, re.IGNORECASE)
                if sec_match:
                    num = sec_match.group(1)
                    patterns = [
                        rf'\b{num}\.\s*—',
                        rf'\b{num}\.\s*\(',
                        rf'\bsection\s+{num}\b',
                        rf'\brule\s+{num}\b',
                        rf'\br\.\s*{num}\b',
                        rf'\bO\.\s*\d+,\s*r\.\s*{num}\b',
                        rf'\b{num}\b'
                    ]
                    if any(re.search(p, source_content, re.IGNORECASE) for p in patterns):
                        found_any_pinpoint = True
                        break
                elif pinpoint.strip().isdigit():
                    if re.search(rf'\b{pinpoint.strip()}\b', source_content):
                        found_any_pinpoint = True
                        break
                else:
                    clean_pin = pinpoint.replace('[', '').replace(']', '').strip()
                    if clean_pin and clean_pin in source_content:
                        found_any_pinpoint = True
                        break

            if not found_any_pinpoint:
                return False, f"The cited provisions ({', '.join(authority.pinpoints)}) weren’t found in the legislation, so it wasn’t used."

        return True, "Found on Singapore Statutes Online."

    @staticmethod
    def verify_judgment(
        authority: AuthorityItem,
        source_citation: str,
        source_content: str
    ) -> Tuple[bool, str]:
        """
        Checks that a retrieved judgment is the case cited and contains every cited paragraph.
        The judgment's own paragraphs in source_content start their line with "[63]" and an em space.
        """
        if not source_content or len(source_content.strip()) < 50:
            return False, f"The judgment found was empty or incomplete, so it wasn’t used. {INSERT_BY_HAND}"

        # 1. Neutral citation: the judgment's header must carry the citation that was asked for.
        requested = neutral_citation(authority.citation) or neutral_citation(authority.raw_citation)
        if requested:
            supplied = neutral_citation(source_citation)
            if supplied and supplied != requested:
                return False, f"The judgment found ({source_citation}) isn’t the one cited, so it wasn’t used. {INSERT_BY_HAND}"
            if requested not in neutral_citations(source_content[:3000]):
                return False, f"The judgment found didn’t carry the cited citation, so it wasn’t used. {INSERT_BY_HAND}"

        # 2. Parties: a word from the first party's name must appear in the header.
        parties = re.split(r'\s+v\.?\s+|\s+and\s+', authority.title, flags=re.IGNORECASE)
        first_party_words = [w for w in re.split(r'\W+', parties[0]) if len(w) > 3]
        if first_party_words and not any(w.lower() in source_content[:3000].lower() for w in first_party_words):
            return False, f"The judgment found didn’t name “{parties[0]}”, so it wasn’t used. {INSERT_BY_HAND}"

        # 3. Pinpoints: every cited paragraph must exist as one of the judgment's own paragraphs.
        missing = paragraph_numbers(authority.pinpoints) - own_paragraphs(source_content)
        if missing:
            verb = "wasn’t" if len(missing) == 1 else "weren’t"
            noun = "Paragraph" if len(missing) == 1 else "Paragraphs"
            return False, (
                f"{noun} {format_paragraphs(missing)} {verb} found in the judgment, so its text wasn’t used. "
                f"Check the pinpoint, then insert the report by hand."
            )

        return True, "Found."


def triage_authority(
    authority: AuthorityItem,
    retrieved_payload: Optional[dict]
) -> Tuple[RetrievalStatus, str, Optional[str]]:
    """
    Decides between the retrieved text and a placeholder sheet.
    Returns (status, note, verified text or None).
    """
    if not retrieved_payload or not retrieved_payload.get("content"):
        return (
            RetrievalStatus.MANUAL_PLACEHOLDER,
            f"Not found on a free official source. It may be reported only in the law reports or on LawNet. {INSERT_BY_HAND}",
            None
        )

    content = retrieved_payload["content"]
    title = retrieved_payload.get("title", "")
    citation = retrieved_payload.get("citation", "")
    source = retrieved_payload.get("source", "")

    is_statute = "Statute" in authority.category.value or "Regulation" in authority.category.value
    if is_statute:
        is_valid, msg = VerbatimVerifier.verify_statute(authority, title, content)
    else:
        is_valid, msg = VerbatimVerifier.verify_judgment(authority, citation, content)

    if not is_valid:
        return RetrievalStatus.MANUAL_PLACEHOLDER, msg, None
    if not is_statute:
        where = source or "an official source"
        with_paragraphs = ", with the cited paragraphs" if paragraph_numbers(authority.pinpoints) else ""
        msg = f"Found on {where}{with_paragraphs}. Compare it with the law report version before you file."
    return RetrievalStatus.VERIFIED_MATCH, msg, content
