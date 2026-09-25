"""
Data models for Bundle of Authorities Autobot.
"""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AuthorityCategory(str, Enum):
    SINGAPORE_CASES = "Singapore Cases"
    SINGAPORE_STATUTES = "Singapore Statutes"
    REGULATIONS = "Regulations / Statutory Instruments"
    FOREIGN_CASES = "Foreign Cases"
    FOREIGN_STATUTES = "Foreign Statutes"
    SECONDARY_SOURCES = "Secondary Sources"
    MISCELLANEOUS = "Miscellaneous"


class RetrievalStatus(str, Enum):
    VERIFIED_MATCH = "VERIFIED_MATCH"
    MANUAL_PLACEHOLDER = "MANUAL_PLACEHOLDER"
    PENDING = "PENDING"
    UNVERIFIED = "UNVERIFIED"


class FootnoteItem(BaseModel):
    footnote_id: int
    raw_text: str
    referencing_sentence: Optional[str] = None
    is_authority: bool = True
    non_authority_reason: Optional[str] = None


class AuthorityItem(BaseModel):
    id: str
    raw_citation: str
    title: str
    citation: Optional[str] = None
    year: Optional[int] = None
    short_name: Optional[str] = None
    category: AuthorityCategory = AuthorityCategory.MISCELLANEOUS
    pinpoints: List[str] = Field(default_factory=list)
    source_footnote_ids: List[int] = Field(default_factory=list)
    relevance: Optional[str] = None
    retrieval_status: RetrievalStatus = RetrievalStatus.PENDING
    retrieval_note: Optional[str] = None
    retrieved_text: Optional[str] = None
    included: bool = True


class GroupConfig(BaseModel):
    id: str
    title: str
    order: int
    visible: bool = True
    merged_into: Optional[str] = None


class CaseMetadata(BaseModel):
    """The cover page. It starts blank, so no example party can slip into a real bundle."""
    court_name: str = ""
    case_number: str = ""
    matter_description: str = ""
    claimant_name: str = ""
    claimant_uen: Optional[str] = None
    respondent_name: str = ""
    respondent_uen: Optional[str] = None
    document_title: str = "CLAIMANT'S BUNDLE OF AUTHORITIES"
    dated_date: str = ""
    claimant_solicitors: str = ""
    respondent_solicitors: str = ""


class ParseRequestOptions(BaseModel):
    include_sentence_context: bool = False
    custom_group_order: Optional[List[str]] = None
    merged_groups: Optional[Dict[str, str]] = None


class ParseResponse(BaseModel):
    total_footnotes: int
    filtered_evidence_count: int
    authorities: List[AuthorityItem]
    group_configs: List[GroupConfig]
    detected_metadata: Optional[CaseMetadata] = None
