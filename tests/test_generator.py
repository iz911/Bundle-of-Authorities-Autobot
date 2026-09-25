import os
import zipfile
import xml.etree.ElementTree as ET
from boa_core.models import AuthorityItem, AuthorityCategory, CaseMetadata, RetrievalStatus
from boa_core.generator import build_bundle_of_authorities

def test_document_builder():
    metadata = CaseMetadata(
        court_name="IN THE STATE COURTS OF THE REPUBLIC OF SINGAPORE",
        case_number="DC/OA XXX/YYYY\nDC/SUM XXXX/YYYY",
        matter_description="In the matter of sections [X] and [Y] of the [Name of Act]",
        claimant_name="[NAME OF CLAIMANT]",
        claimant_uen="[UEN]",
        respondent_name="[NAME OF RESPONDENT]",
        respondent_uen="[UEN]",
        document_title="CLAIMANT'S BUNDLE OF AUTHORITIES",
        dated_date="Dated this [day] day of [month] [year]",
        claimant_solicitors="SOLICITORS FOR THE CLAIMANT\n[NAME OF SOLICITORS]\n[NAME OF LAW PARTNERSHIP]\n[ADDRESS]",
        respondent_solicitors="SOLICITORS FOR THE RESPONDENT\n[NAME OF SOLICITORS]\n[NAME OF LAW PARTNERSHIP]\n[ADDRESS]"
    )

    auth_statute = AuthorityItem(
        id="tab1",
        raw_citation="Rules of Court 2021, Order 15 rule 10",
        title="Rules of Court 2021",
        citation="Order 15 rule 10",
        category=AuthorityCategory.REGULATIONS,
        pinpoints=["Order 15 rule 10"],
        relevance="Provision regarding inspection by the Court.",
        retrieval_status=RetrievalStatus.VERIFIED_MATCH,
        retrieved_text=(
            "SUPREME COURT OF JUDICATURE ACT\n(CHAPTER 322)\nRULES OF COURT 2021\n"
            "Questions and inspection by Court (O. 15, r. 10)\n"
            "10.—(1) The Court may ask a witness any questions that the Court considers necessary...\n"
            "(2) The Court may inspect any object in the courtroom or elsewhere and visit any place..."
        )
    )

    auth_case = AuthorityItem(
        id="tab2",
        raw_citation="Low Yung Chyuan v The MCST Plan No. 2178 [2019] SGSTB 3",
        title="Low Yung Chyuan v The MCST Plan No. 2178",
        citation="[2019] SGSTB 3",
        category=AuthorityCategory.SINGAPORE_CASES,
        pinpoints=["[63]-[64]"],
        relevance="The Board determined the issue of whether an installation of sliding windows affected appearance.",
        retrieval_status=RetrievalStatus.VERIFIED_MATCH,
        retrieved_text=(
            "Low Yung Chyuan v The MCST Plan No. 2178\n[2019] SGSTB 3\n"
            "[63]\u2003The Respondent's submissions regarding façade uniformity were considered.\n"
            "[64]\u2003In the premises, the application is allowed."
        )
    )

    auth_foreign = AuthorityItem(
        id="tab3",
        raw_citation="Emirates Trading Agency LLC v Prime Mineral Exports Pte Ltd [2015] 1 WLR 1145",
        title="Emirates Trading Agency LLC v Prime Mineral Exports Pte Ltd",
        citation="[2015] 1 WLR 1145",
        category=AuthorityCategory.FOREIGN_CASES,
        pinpoints=["[63]-[64]", "[27]", "[40]"],
        relevance="Principles on enforceability of time-limited dispute resolution clauses.",
        retrieval_status=RetrievalStatus.MANUAL_PLACEHOLDER,
        retrieval_note="Foreign English law report. Available on ICLR / Westlaw UK."
    )

    grouped = {
        "Regulations / Statutory Instruments": [auth_statute],
        "Singapore Cases": [auth_case],
        "Foreign Cases": [auth_foreign]
    }

    import tempfile
    out_dir = os.path.join(tempfile.gettempdir(), "boa_test_output")
    os.makedirs(out_dir, exist_ok=True)
    out_docx = os.path.join(out_dir, "Generated_Test_BOA.docx")

    result_path = build_bundle_of_authorities(metadata, grouped, out_docx)
    assert os.path.exists(result_path), "Generated docx file must exist"
    print(f"[PASS] Successfully generated BOA docx at: {result_path}")

    # Inspect inside the generated docx
    with zipfile.ZipFile(result_path, 'r') as z:
        assert "word/document.xml" in z.namelist()
        doc_xml = z.read("word/document.xml")
        root = ET.fromstring(doc_xml)
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

        # Verify yellow highlights
        highlights = root.findall('.//w:highlight', ns)
        print(f"[PASS] Yellow highlights count in generated document: {len(highlights)}")
        assert len(highlights) > 0

        # Verify Tab headers
        all_text = "".join(node.text for node in root.findall('.//w:t', ns) if node.text)
        assert "Tab-1" in all_text
        assert "Tab-2" in all_text
        assert "Tab-3" in all_text
        assert "INDEX TO CLAIMANT'S BUNDLE OF AUTHORITIES" in all_text
        assert "MANUAL INSERTION REQUIRED" in all_text

    print("[PASS] All structure, yellow highlights, and index checks verified successfully!")

if __name__ == "__main__":
    test_document_builder()
