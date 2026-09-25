"""The check against official sources, and what reaches the Word bundle. Runs offline: eLitigation is faked."""
import io
import os
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import docx
import pytest
import requests
from fastapi.testclient import TestClient

from boa_core import retriever as retriever_module
from boa_core.citations import format_paragraphs, neutral_citation, paragraph_numbers
from boa_core.generator import build_bundle_of_authorities
from boa_core.models import AuthorityCategory, AuthorityItem, CaseMetadata, RetrievalStatus
from boa_core.retriever import AuthorityRetriever, elitigation_url, judgment_text
from boa_core.sorter import sort_and_group_authorities

W = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

ELITIGATION_PAGE = """
<html><body>
<nav>Home · Judgments · Search 63 results</nav>
<div id="divJudgement">
  <div class="text-center">In the COURT OF APPEAL of the republic of singapore</div>
  <div class="text-center">[2020] SGCA(I) 02</div>
  <div class="text-center">Quoine Pte Ltd <i>v</i> B2C2 Ltd</div>
  <div class="Judg-1 mb-3">62\u2003The contract said nothing about <i>reversal</i> of trades.</div>
  <div class="Judg-1 mb-3">63\u2003Further, in determining whether notice had to be given, we have regard to the clauses.</div>
  <div class="Judg-Quote-0">[63] Quoted from another judgment, which uses its own numbering.</div>
  <div class="Judg-Quote-0">[65] Also quoted from another judgment.</div>
  <div class="Judg-1 mb-3">64\u2003Accordingly, Quoine was in breach.</div>
  <div class="Judg-1 mb-3">66\u2003See the article in the <span>Oxford Business Law Blog</span><div>, 8 November 2019</div> (accessed).</div>
  <div class="Judg-1 mb-3">163\u2003The dissent reads s 63 differently.</div>
</div>
<footer>Copyright 2026</footer>
</body></html>
"""


class FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text
        self.encoding = "utf-8"
        self.apparent_encoding = "utf-8"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


@pytest.fixture
def elitigation(monkeypatch):
    """Serves pages by address; anything else is 'not on eLitigation'. Records every address asked for."""
    pages = {}
    asked = []

    def fake_get(url, headers=None, timeout=None):
        asked.append(url)
        return FakeResponse(200, pages[url]) if url in pages else FakeResponse(404, "Not found")

    monkeypatch.setattr(retriever_module.requests, "get", fake_get)
    return pages, asked


def case(citation="[2020] SGCA(I) 02", pinpoints=("[63]",), title="Quoine Pte Ltd v B2C2 Ltd"):
    return AuthorityItem(id="c", raw_citation=f"{title} {citation}", title=title, citation=citation,
                         pinpoints=list(pinpoints), category=AuthorityCategory.SINGAPORE_CASES)


# ---------- Citations ----------

def test_neutral_citations_and_paragraphs_are_read_exactly():
    assert neutral_citation("[2020] SGCA(I) 02") == (2020, "SGCAI", 2)
    assert neutral_citation("Spandeck [2007] SGCA 37; [2007] 4 SLR(R) 100") == (2007, "SGCA", 37)
    assert neutral_citation("[2007] 4 SLR(R) 100") is None
    assert paragraph_numbers(["[63]", "[65]–[67]", "s 63", "p 12"]) == {63, 65, 66, 67}
    assert format_paragraphs({64, 63}) == "[63] and [64]"


def test_elitigation_address():
    assert elitigation_url(case()) == "https://www.elitigation.sg/gd/s/2020_SGCAI_2"
    assert elitigation_url(case(citation="[2007] 4 SLR(R) 100")) is None


# ---------- Only real, verified text is ever used ----------

@pytest.mark.parametrize("authority", [
    case(),
    case(citation="[2019] SGSTB 3", pinpoints=("[63]", "[64]"), title="Low Yung Chyuan v The MCST Plan No. 2178"),
    AuthorityItem(id="s", raw_citation="SIAC Rules 2016 Rule 28.2", title="Arbitration Rules of the Singapore International Arbitration Centre",
                  citation="(SIAC Rules 2016)", pinpoints=["Rule 28.2"], category=AuthorityCategory.REGULATIONS),
    AuthorityItem(id="r", raw_citation="Rules of Court 2021, Order 15 rule 10", title="Rules of Court 2021",
                  pinpoints=["Order 15 rule 10"], category=AuthorityCategory.REGULATIONS),
])
def test_nothing_is_verified_from_text_kept_in_the_code(elitigation, authority):
    AuthorityRetriever().retrieve(authority)
    assert authority.retrieval_status == RetrievalStatus.MANUAL_PLACEHOLDER
    assert authority.retrieved_text is None


def test_legislation_and_foreign_sources_are_not_sent_anywhere(elitigation):
    _, asked = elitigation
    for category in [AuthorityCategory.SINGAPORE_STATUTES, AuthorityCategory.REGULATIONS, AuthorityCategory.FOREIGN_CASES,
                     AuthorityCategory.FOREIGN_STATUTES, AuthorityCategory.SECONDARY_SOURCES, AuthorityCategory.MISCELLANEOUS]:
        item = AuthorityItem(id="x", raw_citation="Act 2001 s 1", title="Some Act 2001", pinpoints=["s 1"], category=category)
        AuthorityRetriever().retrieve(item)
        assert item.retrieval_status == RetrievalStatus.MANUAL_PLACEHOLDER
        assert "by hand" in item.retrieval_note
    assert asked == []


def test_a_judgment_on_elitigation_is_verified_paragraph_by_paragraph(elitigation):
    pages, _ = elitigation
    pages["https://www.elitigation.sg/gd/s/2020_SGCAI_2"] = ELITIGATION_PAGE
    item = case(pinpoints=("[63]", "[64]"))
    AuthorityRetriever().retrieve(item)
    assert item.retrieval_status == RetrievalStatus.VERIFIED_MATCH
    assert "elitigation.sg/gd/s/2020_SGCAI_2" in item.retrieval_note
    assert "[63]\u2003Further, in determining" in item.retrieved_text
    assert "Home · Judgments" not in item.retrieved_text  # the site's menus stay out of the bundle
    assert "reversal of trades" in item.retrieved_text


def test_a_missing_paragraph_sends_the_judgment_to_a_placeholder(elitigation):
    pages, _ = elitigation
    pages["https://www.elitigation.sg/gd/s/2020_SGCAI_2"] = ELITIGATION_PAGE
    item = case(pinpoints=("[63]", "[65]"))
    AuthorityRetriever().retrieve(item)
    assert item.retrieval_status == RetrievalStatus.MANUAL_PLACEHOLDER
    assert item.retrieval_note.startswith("Paragraph [65] wasn’t found")
    assert "only contains" not in item.retrieval_note


def test_a_quoted_paragraph_never_counts_as_the_judgments_own(elitigation):
    pages, _ = elitigation
    pages["https://www.elitigation.sg/gd/s/2020_SGCAI_2"] = ELITIGATION_PAGE
    item = case(pinpoints=("[65]",))  # [65] appears only inside a quotation
    AuthorityRetriever().retrieve(item)
    assert item.retrieval_status == RetrievalStatus.MANUAL_PLACEHOLDER


def test_a_page_for_another_case_is_not_used(elitigation):
    pages, _ = elitigation
    pages["https://www.elitigation.sg/gd/s/2020_SGCAI_2"] = ELITIGATION_PAGE.replace("[2020] SGCA(I) 02", "[2019] SGHC 7")
    item = case()
    AuthorityRetriever().retrieve(item)
    assert item.retrieval_status == RetrievalStatus.MANUAL_PLACEHOLDER


def test_unreachable_and_missing_judgments_say_so(monkeypatch):
    def down(*args, **kwargs):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(retriever_module.requests, "get", down)
    item = case()
    AuthorityRetriever().retrieve(item)
    assert item.retrieval_note.startswith("eLitigation couldn’t be reached")

    no_neutral = case(citation="[2007] 4 SLR(R) 100", title="Spandeck Engineering v DSTA")
    AuthorityRetriever().retrieve(no_neutral)
    assert "neutral citation" in no_neutral.retrieval_note


def test_judgment_text_numbers_only_numbered_paragraphs():
    text = judgment_text(ELITIGATION_PAGE)
    assert text.splitlines()[:2] == ["In the COURT OF APPEAL of the republic of singapore", "[2020] SGCA(I) 02"]
    assert "[163]\u2003The dissent reads s 63 differently." in text
    # a paragraph with a block inside it stays one numbered paragraph
    assert "[66]\u2003See the article in the Oxford Business Law Blog, 8 November 2019 (accessed)." in text.splitlines()
    assert judgment_text("<html><body>No judgment here</body></html>") == ""


# ---------- The Word bundle ----------

def highlighted_texts(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    texts = []
    for run in root.iter(f"{{{W['w']}}}r"):
        if run.find("w:rPr/w:highlight", W) is not None:
            texts.append("".join(t.text or "" for t in run.findall("w:t", W)))
    return texts


def test_only_the_cited_paragraphs_are_highlighted():
    item = case(pinpoints=("[63]",))
    item.retrieval_status = RetrievalStatus.VERIFIED_MATCH
    item.retrieved_text = judgment_text(ELITIGATION_PAGE)
    out = os.path.join(tempfile.mkdtemp(), "bundle.docx")
    build_bundle_of_authorities(CaseMetadata(), {"Singapore Cases": [item]}, out)
    marked = [t for t in highlighted_texts(out) if t != "[63]"]  # the pinpoint line under the tab heading
    assert marked == ["[63]\u2003Further, in determining whether notice had to be given, we have regard to the clauses."]


def test_placeholder_sheets_speak_plainly():
    item = AuthorityItem(id="f", raw_citation="Donoghue v Stevenson [1932] AC 562", title="Donoghue v Stevenson",
                         category=AuthorityCategory.FOREIGN_CASES)
    AuthorityRetriever().retrieve(item)
    out = os.path.join(tempfile.mkdtemp(), "bundle.docx")
    build_bundle_of_authorities(CaseMetadata(), {"Foreign Cases": [item]}, out)
    with zipfile.ZipFile(out) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    text = "".join(t.text or "" for t in root.iter(f"{{{W['w']}}}t"))
    assert "Why this is a placeholder:" in text
    assert "Foreign cases aren’t available from a free official source" in text
    for jargon in ["IDK", "FAIL-SAFE", "enforcer", "Triage"]:
        assert jargon not in text


def test_unchecked_authorities_are_flagged_in_the_index():
    item = case()
    out = os.path.join(tempfile.mkdtemp(), "bundle.docx")
    build_bundle_of_authorities(CaseMetadata(), {"Singapore Cases": [item]}, out)
    with zipfile.ZipFile(out) as z:
        text = z.read("word/document.xml").decode("utf-8")
    assert "[Manual Tab Insertion Required]" in text


# ---------- Order of sections ----------

def test_a_combined_section_keeps_its_place_in_the_order():
    items = [
        AuthorityItem(id="1", raw_citation="", title="A case", category=AuthorityCategory.SINGAPORE_CASES),
        AuthorityItem(id="2", raw_citation="", title="A foreign case", category=AuthorityCategory.FOREIGN_CASES),
        AuthorityItem(id="3", raw_citation="", title="A foreign act", category=AuthorityCategory.FOREIGN_STATUTES),
        AuthorityItem(id="4", raw_citation="", title="A book", category=AuthorityCategory.SECONDARY_SOURCES),
    ]
    merged = {"Foreign Cases": "Foreign Authorities", "Foreign Statutes": "Foreign Authorities"}
    grouped = sort_and_group_authorities(items, merged_groups=merged)
    assert list(grouped) == ["Singapore Cases", "Foreign Authorities", "Secondary Sources"]
    assert [a.title for a in grouped["Foreign Authorities"]] == ["A foreign act", "A foreign case"]

    order = ["Secondary Sources", "Foreign Statutes", "Singapore Cases", "Foreign Cases"]
    grouped = sort_and_group_authorities(items, custom_order=order, merged_groups=merged)
    assert list(grouped) == ["Secondary Sources", "Foreign Authorities", "Singapore Cases"]


# ---------- Uploads start with a blank cover page ----------

def test_an_uploaded_draft_gets_a_blank_cover_page():
    from app import app

    document = docx.Document()
    document.add_paragraph("A draft with no footnotes.")
    buffer = io.BytesIO()
    document.save(buffer)
    client = TestClient(app)
    response = client.post("/api/upload", files={"file": ("draft.docx", buffer.getvalue(), "application/octet-stream")})
    assert response.status_code == 200
    cover = response.json()["detected_metadata"]
    assert cover["claimant_name"] == "" and cover["respondent_name"] == "" and cover["court_name"] == ""
    assert cover["claimant_uen"] is None
    assert cover["document_title"] == "CLAIMANT'S BUNDLE OF AUTHORITIES"
