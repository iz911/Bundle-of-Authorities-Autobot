from boa_core.models import AuthorityItem, AuthorityCategory, RetrievalStatus
from boa_core.verifier import VerbatimVerifier, triage_authority
from boa_core.retriever import AuthorityRetriever

def test_statute_deterministic_verification():
    auth = AuthorityItem(
        id="1",
        raw_citation="Rules of Court 2021, Order 15 rule 10",
        title="Rules of Court 2021",
        pinpoints=["Order 15 rule 10"],
        category=AuthorityCategory.REGULATIONS
    )
    
    # 1. Exact match test
    official_content = (
        "SUPREME COURT OF JUDICATURE ACT\nRULES OF COURT 2021\n"
        "Questions and inspection by Court (O. 15, r. 10)\n"
        "10.—(1) The Court may ask a witness any questions..."
    )
    is_valid, reason = VerbatimVerifier.verify_statute(auth, "Rules of Court 2021", official_content)
    assert is_valid, f"Verification failed: {reason}"
    print("[PASS] Exact statute verification passed:", reason)
    
    # 2. Pinpoint mismatch test (e.g. asking for section 999 which does not exist)
    auth_bad_pin = AuthorityItem(
        id="2",
        raw_citation="Rules of Court 2021, Order 99 rule 999",
        title="Rules of Court 2021",
        pinpoints=["Order 99 rule 999"],
        category=AuthorityCategory.REGULATIONS
    )
    is_valid_bad, reason_bad = VerbatimVerifier.verify_statute(auth_bad_pin, "Rules of Court 2021", official_content)
    assert not is_valid_bad, "Should fail when pinpoint is missing"
    print("[PASS] Correctly rejected missing pinpoint:", reason_bad)


def test_judgment_deterministic_verification():
    auth = AuthorityItem(
        id="3",
        raw_citation="Low Yung Chyuan v The MCST Plan No. 2178 [2019] SGSTB 3",
        title="Low Yung Chyuan v The MCST Plan No. 2178",
        citation="[2019] SGSTB 3",
        pinpoints=["[63]-[64]"],
        category=AuthorityCategory.SINGAPORE_CASES
    )
    
    # 1. Valid judgment with matching neutral citation and pinpoints
    judgment_text = (
        "Low Yung Chyuan v The MCST Plan No. 2178\n[2019] SGSTB 3\n"
        "Decision Date: 02 September 2019\n"
        "[63]\u2003The Respondent's submissions...\n[64]\u2003The application is allowed."
    )
    is_valid, reason = VerbatimVerifier.verify_judgment(auth, "[2019] SGSTB 3", judgment_text)
    assert is_valid, f"Judgment verification failed: {reason}"
    print("[PASS] Exact judgment verification passed:", reason)
    
    # 2. Citation mismatch test
    is_valid_cit, reason_cit = VerbatimVerifier.verify_judgment(auth, "[2024] SGCA 99", judgment_text)
    assert not is_valid_cit
    print("[PASS] Correctly rejected mismatched citation:", reason_cit)


def test_idk_fallback_for_foreign_and_secondary():
    retriever = AuthorityRetriever(use_live_network=False)
    
    # Foreign Case
    fc = AuthorityItem(
        id="4",
        raw_citation="Emirates Trading Agency LLC v Prime Mineral Exports Pte Ltd [2015] 1 WLR 1145",
        title="Emirates Trading Agency LLC v Prime Mineral Exports Pte Ltd",
        category=AuthorityCategory.FOREIGN_CASES
    )
    retriever.retrieve(fc)
    assert fc.retrieval_status == RetrievalStatus.MANUAL_PLACEHOLDER
    assert "Foreign cases" in fc.retrieval_note and "by hand" in fc.retrieval_note
    print("[PASS] Foreign case triaged to IDK placeholder:", fc.retrieval_note[:70])
    
    # Secondary Source (Textbook)
    sec = AuthorityItem(
        id="5",
        raw_citation="Cavinder Bull SC (gen ed.), Singapore Civil Procedure Volume I",
        title="Cavinder Bull SC (gen ed.), Singapore Civil Procedure Volume I",
        category=AuthorityCategory.SECONDARY_SOURCES
    )
    retriever.retrieve(sec)
    assert sec.retrieval_status == RetrievalStatus.MANUAL_PLACEHOLDER
    assert "Books and articles" in sec.retrieval_note
    print("[PASS] Secondary source triaged to IDK placeholder:", sec.retrieval_note[:70])


if __name__ == "__main__":
    test_statute_deterministic_verification()
    test_judgment_deterministic_verification()
    test_idk_fallback_for_foreign_and_secondary()
    print("\nAll verifier and retriever tests passed successfully!")
