"""
Classifier for legal authorities into 7 distinct groups:
1. Singapore Cases
2. Singapore Statutes
3. Regulations / Statutory Instruments
4. Foreign Cases
5. Foreign Statutes
6. Secondary Sources
7. Miscellaneous
"""
import re
from typing import List
from .models import AuthorityItem, AuthorityCategory

# Singapore Neutral Citations & Law Reports
SG_CASE_PATTERNS = [
    re.compile(r'\b(?:\[(?:18|19|20)\d{2}\]\s*)?SG(?:CA|HC|HCF|HCR|DC|MC|STB|IPOS|CIR)\b', re.IGNORECASE),
    re.compile(r'\b(?:\[(?:18|19|20)\d{2}\]\s*)?\d*\s*SLR(?:\(R\))?\b', re.IGNORECASE),
    re.compile(r'\b(?:MCST|Management\s+Corporation\s+Strata\s+Title)\b', re.IGNORECASE),
    re.compile(r'\bStrata\s+Titles\s+Boards?\b', re.IGNORECASE),
    re.compile(r'\bSingapore\s+Law\s+Reports?\b', re.IGNORECASE),
]

# Foreign Courts & Law Reports (primarily UK/Commonwealth)
FOREIGN_CASE_PATTERNS = [
    re.compile(r'\b(?:UKSC|EWCA|EWHC|UKHL|UKPC|HCA|FCA|HKCFA|HKCA)\b', re.IGNORECASE),
    re.compile(r'\b(?:\[(?:18|19|20)\d{2}\]|\((?:18|19|20)\d{2}\))\s*(?:\d+\s+)?(?:WLR|All\s+ER|AC|Ch|QB|KB|Lloyd[’\']s\s+Rep|FSR|App\s+Cas|LT)\b', re.IGNORECASE),
    re.compile(r'\b(?:EWHC\s+\d+\s*\((?:Comm|TCC|Ch|QB|Admin)\))\b', re.IGNORECASE),
]

# Regulations & Rules
REGULATION_PATTERNS = [
    re.compile(r'\b(?:Rules\s+of\s+Court\s+(?:2021|\d{4})|Rules\s+of\s+the\s+Supreme\s+Court)\b', re.IGNORECASE),
    re.compile(r'\b(?:Arbitration\s+Rules\s+of\s+the\s+Singapore\s+International\s+Arbitration\s+Centre|SIAC\s+Rules)\b', re.IGNORECASE),
    re.compile(r'\b(?:Subsidiary\s+Legislation|Gazette\s+Notification|Gazette\s+Order|Practice\s+Directions?)\b', re.IGNORECASE),
    re.compile(r'\b(?:Regulations?\s+\d{4}|Rules\s+\d{4})\b', re.IGNORECASE),
]

# Foreign Statutes
FOREIGN_STATUTE_PATTERNS = [
    re.compile(r'\b(?:UK\s+|English\s+|British\s+)(?:Arbitration|Misrepresentation|Companies|Sale\s+of\s+Goods|Contracts?)\s+Act\b', re.IGNORECASE),
    re.compile(r'\b(?:Civil\s+Procedure\s+Rules\s+1998|CPR\s+1998)\b', re.IGNORECASE),
    re.compile(r'\b(?:Arbitration\s+Act\s+1996|Misrepresentation\s+Act\s+1967)\b', re.IGNORECASE),
]

# Singapore Statutes
SG_STATUTE_PATTERNS = [
    re.compile(r'\b(?:Building\s+Maintenance\s+and\s+Strata\s+Management\s+Act|BMSMA)\b', re.IGNORECASE),
    re.compile(r'\b(?:International\s+Arbitration\s+Act|IAA)\b', re.IGNORECASE),
    re.compile(r'\b(?:Civil\s+Law\s+Act|Supreme\s+Court\s+of\s+Judicature\s+Act|SCJA)\b', re.IGNORECASE),
    re.compile(r'\b(?:Evidence\s+Act|Penal\s+Code|Companies\s+Act|Insolvency,\s+Restructuring\s+and\s+Dissolution\s+Act|IRDA)\b', re.IGNORECASE),
    re.compile(r'\bAct\s+(?:19\d{2}|20\d{2})\b', re.IGNORECASE),
]

# Secondary Sources
SECONDARY_PATTERNS = [
    re.compile(r'\b(?:gen\s+ed|ed\.|editors?|Sweet\s+&\s+Maxwell|Kluwer\s+Law|Butterworths|Oxford\s+University\s+Press|LexisNexis)\b', re.IGNORECASE),
    re.compile(r'\b(?:Modern\s+Law\s+Review|L\.M\.C\.L\.Q\.|Singapore\s+Academy\s+of\s+Law\s+Journal|SALJ|Sing\s+JLS|Cambridge\s+Law\s+Journal)\b', re.IGNORECASE),
    re.compile(r'\b(?:Singapore\s+Civil\s+Procedure|Chitty\s+on\s+Contracts|Russell\s+on\s+Arbitration|Benjamin[’\']s\s+Sale\s+of\s+Goods)\b', re.IGNORECASE),
    re.compile(r'\b\(\d{4}\)\s*\d*\s*[A-Z\.]+\s*,\s*\d+\b'), # Journal pattern (2008) L.M.C.L.Q., 536
]


def classify_authority(authority: AuthorityItem) -> AuthorityCategory:
    """
    Classifies an AuthorityItem into one of 7 categories.
    """
    full_text = f"{authority.title} {authority.raw_citation} {authority.citation or ''}"

    # 1. Check Regulations & Rules (SIAC Rules, Rules of Court 2021)
    for pat in REGULATION_PATTERNS:
        if pat.search(full_text):
            return AuthorityCategory.REGULATIONS

    # 2. Check Singapore Cases
    for pat in SG_CASE_PATTERNS:
        if pat.search(full_text):
            return AuthorityCategory.SINGAPORE_CASES

    # 3. Check Foreign Statutes
    for pat in FOREIGN_STATUTE_PATTERNS:
        if pat.search(full_text):
            return AuthorityCategory.FOREIGN_STATUTES

    # 4. Check Foreign Cases
    for pat in FOREIGN_CASE_PATTERNS:
        if pat.search(full_text):
            return AuthorityCategory.FOREIGN_CASES

    # 5. Check Secondary Sources
    for pat in SECONDARY_PATTERNS:
        if pat.search(full_text):
            return AuthorityCategory.SECONDARY_SOURCES

    # 6. Check Singapore Statutes (if mentions Act and not already flagged foreign)
    if "Act" in authority.title or (authority.citation and "Act" in authority.citation):
        if not any(f in full_text for f in ["UK", "English", "1996", "1967", "CPR", "Australia"]):
            for pat in SG_STATUTE_PATTERNS:
                if pat.search(full_text):
                    return AuthorityCategory.SINGAPORE_STATUTES
            return AuthorityCategory.SINGAPORE_STATUTES

    # Fallback checks based on common markers
    if " v " in authority.title or " v. " in authority.title or " v " in authority.raw_citation:
        # Default unclassified cases
        return AuthorityCategory.FOREIGN_CASES

    if any(term in full_text.lower() for term in ["article", "essay", "in j d m lew", "journal", "review", "press"]):
        return AuthorityCategory.SECONDARY_SOURCES

    return AuthorityCategory.MISCELLANEOUS


def classify_all(authorities: List[AuthorityItem]) -> List[AuthorityItem]:
    """Classifies a list of authorities in-place and returns them."""
    for auth in authorities:
        auth.category = classify_authority(auth)
    return authorities
