"""
Footnote extractor for .docx legal documents.
Deterministically extracts footnotes, maps referencing sentences,
filters out factual evidentiary citations (Exhibits, Record references),
and splits composite footnotes into individual authority candidates.
"""
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import List, Tuple, Optional, Dict
from .models import FootnoteItem

# XML Namespaces for docx
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}

# Regular expressions for evidentiary/factual record citations
EVIDENCE_PATTERNS = [
    re.compile(r"^(Claimant|Respondent|Plaintiff|Defendant)\s+Exhibit\b", re.IGNORECASE),
    re.compile(r"^Exhibit\s+[A-Z0-9\-]+", re.IGNORECASE),
    re.compile(r"\bRecord\s+at\s+pp?\.?\s*\d+", re.IGNORECASE),
    re.compile(r"^(Claimant|Respondent|Plaintiff|Defendant)’?s?\s+Notice\s+of\s+Arbitration", re.IGNORECASE),
    re.compile(r"^Notice\s+of\s+Arbitration\b", re.IGNORECASE),
    re.compile(r"^Procedural\s+Order\s+No\.?\s*\d+", re.IGNORECASE),
    re.compile(r"^Affidavit\s+of\b", re.IGNORECASE),
    re.compile(r"^Core\s+Bundle\b", re.IGNORECASE),
    re.compile(r"^Agreed\s+Bundle\b", re.IGNORECASE),
    re.compile(r"^Bundle\s+of\s+Pleadings\b", re.IGNORECASE),
    re.compile(r"^Statement\s+of\s+Claim\b", re.IGNORECASE),
    re.compile(r"^Defence\s+and\s+Counterclaim\b", re.IGNORECASE),
]


def extract_docx_footnotes(docx_path: str, include_sentence_context: bool = False) -> List[FootnoteItem]:
    """
    Extracts all footnotes from a .docx file and filters factual evidence.
    """
    footnotes_map: Dict[int, str] = {}
    referencing_sentences: Dict[int, str] = {}

    with zipfile.ZipFile(docx_path, "r") as z:
        # 1. Parse footnotes.xml
        if "word/footnotes.xml" in z.namelist():
            xml_content = z.read("word/footnotes.xml")
            root = ET.fromstring(xml_content)
            for fn in root.findall(".//w:footnote", NS):
                fn_id_str = fn.attrib.get(f"{{{W_NS}}}id")
                fn_type = fn.attrib.get(f"{{{W_NS}}}type")
                if not fn_id_str:
                    continue
                fn_id = int(fn_id_str)
                # Skip separator (-1) and continuationSeparator (0)
                if fn_id <= 0 or fn_type in ["separator", "continuationSeparator"]:
                    continue

                texts = [node.text for node in fn.findall(".//w:t", NS) if node.text]
                clean_text = "".join(texts).strip()
                # Clean multiple spaces or weird whitespace
                clean_text = re.sub(r"\s+", " ", clean_text)
                if clean_text:
                    footnotes_map[fn_id] = clean_text

        # 2. Parse document.xml for referencing sentence if requested
        if include_sentence_context and "word/document.xml" in z.namelist():
            doc_xml = z.read("word/document.xml")
            doc_root = ET.fromstring(doc_xml)
            for p in doc_root.findall(".//w:p", NS):
                # Check if this paragraph contains a footnote reference
                fn_refs = p.findall(".//w:footnoteReference", NS)
                if not fn_refs:
                    continue
                # Get paragraph text
                p_texts = [node.text for node in p.findall(".//w:t", NS) if node.text]
                full_p_text = "".join(p_texts).strip()
                for ref in fn_refs:
                    ref_id_str = ref.attrib.get(f"{{{W_NS}}}id")
                    if ref_id_str:
                        ref_id = int(ref_id_str)
                        referencing_sentences[ref_id] = full_p_text

    # 3. Build FootnoteItem objects and classify evidence
    results: List[FootnoteItem] = []
    for fn_id in sorted(footnotes_map.keys()):
        text = footnotes_map[fn_id]
        ref_sentence = referencing_sentences.get(fn_id)
        
        is_evidence, reason = check_if_evidence(text)
        results.append(
            FootnoteItem(
                footnote_id=fn_id,
                raw_text=text,
                referencing_sentence=ref_sentence,
                is_authority=not is_evidence,
                non_authority_reason=reason
            )
        )

    return results


def check_if_evidence(text: str) -> Tuple[bool, Optional[str]]:
    """
    Checks if a footnote is an evidentiary factual citation.
    """
    cleaned = text.strip()
    for pattern in EVIDENCE_PATTERNS:
        if pattern.search(cleaned):
            # Check if this is a composite footnote that ALSO has an authority
            # e.g., "See Exhibit C1; and Rainy Sky SA v Kookmin Bank [2011] UKSC 50"
            if ";" in cleaned and any(term in cleaned for term in ["v", "Act", "Rules", "Ltd", "[19", "[20"]):
                return False, None
            return True, f"Factual / Record citation matching '{pattern.pattern}'"

    # Additional check: pure "Record at p X" or "Notice of Arbitration"
    if cleaned.lower().startswith("claimant’s notice") or cleaned.lower().startswith("respondent's notice"):
        return True, "Factual notice citation"

    return False, None


def split_composite_footnote(text: str) -> List[str]:
    """
    Splits composite footnotes (e.g., citing multiple cases/statutes separated by semicolons).
    Preserves embedded parentheses and brackets.
    """
    # Regex split on semicolon followed by optional conjunctions like "and", "or", "See also"
    chunks = re.split(r";\s*(?:and\s+|or\s+|See\s+also\s+|see\s+also\s+|also\s+)?", text)
    cleaned_chunks = []
    for c in chunks:
        c_clean = c.strip()
        # Remove leading "See also", "See", "and "
        c_clean = re.sub(r"^(?:See\s+also|see\s+also|See|see|and)\s+", "", c_clean).strip()
        if c_clean:
            cleaned_chunks.append(c_clean)
    return cleaned_chunks if cleaned_chunks else [text]
