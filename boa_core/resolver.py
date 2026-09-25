"""
Cross-reference resolver, pinpoint aggregator, and citation normalizer.
Resolves (n X), ibid, and short-form citations back to their primary authority,
extracts and aggregates pinpoints, and deduplicates authorities.
"""
import re
import uuid
from typing import List, Dict, Optional, Tuple, Set
from .models import AuthorityItem, FootnoteItem, AuthorityCategory, RetrievalStatus
from .extractor import split_composite_footnote

# Regex patterns for citation analysis
SHORT_FORM_DEF_RE = re.compile(r'[\(\[\{][“"‘\']\s*([^”"’\']+)\s*[”"’\'][\)\]\}]')
BACK_REF_N_RE = re.compile(r'^(.*?)\s*\(n(?:ote)?\s*(\d+)\)\s*(.*)$', re.IGNORECASE)
IBID_RE = re.compile(r'^\s*ibid\.?\s*(.*)$', re.IGNORECASE)
SUPRA_RE = re.compile(r'^(.*?)\s+supra\b\s*(.*)$', re.IGNORECASE)

# Neutral citation pattern (e.g. [2019] SGSTB 3, [2024] UKSC 41, [2015] 1 WLR 1145, [1992] 2 AC 128)
CITATION_RE = re.compile(
    r'(\[?(?:18|19|20)\d{2}\]?\s*(?:\d+\s+)?[A-Za-z\(\)\.\s/]+?\s+\d+)',
    re.IGNORECASE
)

# Pinpoint patterns
PINPOINT_BRACKET_RE = re.compile(r'(\[\d+\](?:\s*[-–—to]+\s*\[?\d+\]?)?)')
PINPOINT_SECTION_RE = re.compile(r'\b(ss?\.?\s*\d+[a-zA-Z0-9\(\)]*(?:\s*[-–—to]+\s*\d+[a-zA-Z0-9\(\)]*)?)', re.IGNORECASE)
PINPOINT_RULE_RE = re.compile(r'\b((?:Order\s+\d+\s+)?rule\s+\d+(?:\.\d+)?(?:\(\w+\))?)', re.IGNORECASE)
PINPOINT_PAGE_RE = re.compile(r'\b(?:at\s+|pp?\.?\s*)(\d+(?:[-–—]\d+)?)', re.IGNORECASE)
PINPOINT_PARA_RE = re.compile(r'\b(?:para\.?|paragraph)\s*(\d+(?:/\d+)?(?:\(\w+\))?)', re.IGNORECASE)


def clean_text_quotes(text: str) -> str:
    """Normalizes curly quotes, hyphens, and whitespace."""
    t = text.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    t = t.replace('–', '-').replace('—', '-')
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def extract_pinpoints(text: str) -> Tuple[List[str], str]:
    """
    Extracts pinpoints (e.g., [63]-[64], s 30(1)(c), Order 15 rule 10, p 138)
    and returns (pinpoints_list, remaining_citation_text).
    """
    pinpoints: List[str] = []
    
    # 1. Bracket pinpoints like [63]-[64] or [27], [40], and [48]
    bracket_matches = PINPOINT_BRACKET_RE.findall(text)
    for m in bracket_matches:
        m_str = m.strip()
        # Filter out standalone 4-digit years like [2015], [1992], [2024]
        if re.match(r'^\[(?:18|19|20)\d{2}\]$', m_str):
            continue
        pinpoints.append(m_str)
        
    # 2. Section pinpoints like s 30(1)(c), s 12(1)
    section_matches = PINPOINT_SECTION_RE.findall(text)
    for m in section_matches:
        pinpoints.append(m.strip())

    # 3. Rule pinpoints like Order 15 rule 10, Rule 28.2
    rule_matches = PINPOINT_RULE_RE.findall(text)
    for m in rule_matches:
        pinpoints.append(m.strip())

    # 4. Paragraph like para 15/10
    para_matches = PINPOINT_PARA_RE.findall(text)
    for m in para_matches:
        pinpoints.append(f"para {m.strip()}")

    # 5. Page references like at p 543-542 or at 502
    page_matches = PINPOINT_PAGE_RE.findall(text)
    for m in page_matches:
        pinpoints.append(f"p {m.strip()}")

    # If the text ends with a loose page number after law report citation (e.g., "Walford v Miles [1992] 2 AC 128 138")
    # check trailing number
    trailing_page_match = re.search(r'\[(?:18|19|20)\d{2}\][^,]+\s+(\d{2,4})\s*$', text)
    if trailing_page_match:
        loose_page = trailing_page_match.group(1)
        if not any(loose_page in p for p in pinpoints):
            pinpoints.append(f"p {loose_page}")

    # Remove duplicates preserving order
    seen: Set[str] = set()
    unique_pinpoints = []
    for p in pinpoints:
        if p not in seen:
            seen.add(p)
            unique_pinpoints.append(p)

    return unique_pinpoints, text


def canonicalize_title(title: str) -> str:
    """Creates a canonical key for matching authorities across footnotes."""
    t = clean_text_quotes(title).lower()
    # Remove citation portions or trailing years
    t = re.sub(r'\[(?:18|19|20)\d{2}\].*$', '', t)
    t = re.sub(r'\(.*?\)', '', t)
    t = re.sub(r'[^a-z0-9\s]', '', t)
    return re.sub(r'\s+', ' ', t).strip()


class CitationRegistry:
    """Maintains indexed authorities by footnote ID, short name, and canonical title."""
    def __init__(self):
        self.by_fn_id: Dict[int, AuthorityItem] = {}
        self.by_short_name: Dict[str, AuthorityItem] = {}
        self.by_canonical_title: Dict[str, AuthorityItem] = {}
        self.all_authorities: Dict[str, AuthorityItem] = {} # id -> AuthorityItem
        self.last_seen_authority: Optional[AuthorityItem] = None

    def register(self, authority: AuthorityItem, fn_id: int):
        self.all_authorities[authority.id] = authority
        self.by_fn_id[fn_id] = authority
        self.last_seen_authority = authority
        
        canon = canonicalize_title(authority.title)
        if canon:
            self.by_canonical_title[canon] = authority
            
        if authority.short_name:
            self.by_short_name[authority.short_name.lower().strip()] = authority

    def find_match(self, name_or_ref: str, fn_ref_num: Optional[int] = None) -> Optional[AuthorityItem]:
        # 1. By footnote back-reference number e.g. (n 7)
        if fn_ref_num is not None:
            # Check exact fn_id or nearby offsets (+/- 1)
            for candidate_id in [fn_ref_num, fn_ref_num + 1, fn_ref_num - 1]:
                if candidate_id in self.by_fn_id:
                    return self.by_fn_id[candidate_id]
                    
        # 2. By short name
        cleaned_name = clean_text_quotes(name_or_ref).lower().strip()
        if cleaned_name in self.by_short_name:
            return self.by_short_name[cleaned_name]

        # 3. By canonical title prefix match
        canon = canonicalize_title(name_or_ref)
        if canon in self.by_canonical_title:
            return self.by_canonical_title[canon]
            
        for c_title, auth in self.by_canonical_title.items():
            if canon in c_title or c_title in canon:
                return auth
                
        for s_name, auth in self.by_short_name.items():
            if s_name in cleaned_name or cleaned_name in s_name:
                return auth

        return None


def resolve_citations(footnotes: List[FootnoteItem]) -> List[AuthorityItem]:
    """
    Parses all footnotes into resolved, deduplicated AuthorityItem objects with aggregated pinpoints.
    """
    registry = CitationRegistry()

    for fn in footnotes:
        if not fn.is_authority:
            continue

        raw_text = clean_text_quotes(fn.raw_text)
        chunks = split_composite_footnote(raw_text)

        for chunk in chunks:
            chunk = clean_text_quotes(chunk)
            if not chunk:
                continue

            # 1. Check if chunk is an "ibid" reference
            ibid_match = IBID_RE.match(chunk)
            if ibid_match:
                pinpoints, _ = extract_pinpoints(ibid_match.group(1))
                if registry.last_seen_authority:
                    auth = registry.last_seen_authority
                    auth.pinpoints.extend([p for p in pinpoints if p not in auth.pinpoints])
                    if fn.footnote_id not in auth.source_footnote_ids:
                        auth.source_footnote_ids.append(fn.footnote_id)
                continue

            # 2. Check if chunk is a back-reference (n X) e.g. "Emirates Trading (n 5) [27]"
            n_match = BACK_REF_N_RE.match(chunk)
            if n_match:
                ref_name = n_match.group(1).strip()
                ref_num = int(n_match.group(2))
                trailing = n_match.group(3)
                pinpoints, _ = extract_pinpoints(trailing)

                matched_auth = registry.find_match(ref_name, fn_ref_num=ref_num)
                if matched_auth:
                    matched_auth.pinpoints.extend([p for p in pinpoints if p not in matched_auth.pinpoints])
                    if fn.footnote_id not in matched_auth.source_footnote_ids:
                        matched_auth.source_footnote_ids.append(fn.footnote_id)
                    registry.last_seen_authority = matched_auth
                    continue

            # 3. Check if chunk is a supra reference e.g. "Yam Seng supra [144]"
            supra_match = SUPRA_RE.match(chunk)
            if supra_match:
                ref_name = supra_match.group(1).strip()
                trailing = supra_match.group(2)
                pinpoints, _ = extract_pinpoints(trailing)

                matched_auth = registry.find_match(ref_name)
                if matched_auth:
                    matched_auth.pinpoints.extend([p for p in pinpoints if p not in matched_auth.pinpoints])
                    if fn.footnote_id not in matched_auth.source_footnote_ids:
                        matched_auth.source_footnote_ids.append(fn.footnote_id)
                    registry.last_seen_authority = matched_auth
                    continue

            # 4. Check if chunk is a standalone short name e.g. "RFS Act, s 12(1)" or "SIAC Rules 2016, Rule 31.1"
            # Extract pinpoints first
            pinpoints, remaining_chunk = extract_pinpoints(chunk)
            short_match = registry.find_match(remaining_chunk)
            if short_match:
                short_match.pinpoints.extend([p for p in pinpoints if p not in short_match.pinpoints])
                if fn.footnote_id not in short_match.source_footnote_ids:
                    short_match.source_footnote_ids.append(fn.footnote_id)
                registry.last_seen_authority = short_match
                continue

            # 5. This is a primary / first-time cited authority!
            # Extract any defined short-form in parentheses e.g. (“Emirates Trading”)
            short_name = None
            short_def_match = SHORT_FORM_DEF_RE.search(chunk)
            if short_def_match:
                short_name = short_def_match.group(1).strip()
                # Remove definition from title
                chunk_without_def = SHORT_FORM_DEF_RE.sub('', chunk).strip()
            else:
                chunk_without_def = chunk

            # Clean citation and title
            auth_title, auth_citation, auth_year = parse_title_and_citation(chunk_without_def)

            # Check if this primary authority was already added under same canonical title
            canon = canonicalize_title(auth_title)
            if canon in registry.by_canonical_title:
                existing = registry.by_canonical_title[canon]
                existing.pinpoints.extend([p for p in pinpoints if p not in existing.pinpoints])
                if fn.footnote_id not in existing.source_footnote_ids:
                    existing.source_footnote_ids.append(fn.footnote_id)
                registry.last_seen_authority = existing
                continue

            # Create new authority item
            auth_item = AuthorityItem(
                id=str(uuid.uuid4())[:8],
                raw_citation=chunk,
                title=auth_title,
                citation=auth_citation,
                year=auth_year,
                short_name=short_name,
                pinpoints=pinpoints,
                source_footnote_ids=[fn.footnote_id],
                retrieval_status=RetrievalStatus.PENDING,
            )
            registry.register(auth_item, fn.footnote_id)

    # Return deduplicated authorities list
    return list(registry.all_authorities.values())


def parse_title_and_citation(raw_text: str) -> Tuple[str, Optional[str], Optional[int]]:
    """
    Separates the authority title (e.g. parties or act name) from citation and year.
    """
    text = clean_text_quotes(raw_text)

    # Extract year if present
    year = None
    year_match = re.search(r'\b(18\d{2}|19\d{2}|20\d{2})\b', text)
    if year_match:
        year = int(year_match.group(1))

    # Check for neutral citation pattern
    # e.g., "Emirates Trading Agency LLC v Prime Mineral Exports Pte Ltd [2015] 1 WLR 1145"
    cit_match = re.search(r'(\[(?:18|19|20)\d{2}\].*?|\((?:18|19|20)\d{2}\).*?)$', text)
    if cit_match:
        citation = cit_match.group(1).strip()
        title = text[:cit_match.start()].strip()
        # Clean title trailing punctuation or 'v'
        title = re.sub(r'[,;\s]+$', '', title)
        if title:
            return title, citation, year

    # If it's a statute e.g. "Rules of Court 2021, Order 15 rule 10" or "UK Arbitration Act 1996, s 30(1)(c)"
    statute_match = re.match(r'^(.*?Act\s+\d{4}|.*?Rules\s+\d{4}|.*?Regulations\s+\d{4}|.*?Code\s+\d{4}|.*?Rules\s+of\s+Court\s+\d{4})', text, re.IGNORECASE)
    if statute_match:
        title = statute_match.group(1).strip()
        citation = text[len(title):].strip().lstrip(',').strip()
        return title, citation if citation else None, year

    # Secondary sources with author and title:
    # e.g., "Cavinder Bull SC (gen ed.), Singapore Civil Procedure Volume I (Sweet & Maxwell, 2022)"
    if '(' in text and ')' in text:
        return text, None, year

    return text, None, year
