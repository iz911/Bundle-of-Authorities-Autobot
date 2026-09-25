import os
from boa_core.extractor import extract_docx_footnotes
from boa_core.resolver import resolve_citations
from boa_core.classifier import classify_all
from boa_core.models import AuthorityCategory
from conftest import requires_memo

@requires_memo
def test_memo_resolution_and_classification():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    memo_path = os.path.join(base_dir, "Example docs for BOA", "Example memo with a certain order for list of authorities that can be used for BOAs (but no BOA).docx")
    footnotes = extract_docx_footnotes(memo_path, include_sentence_context=True)
    authorities = resolve_citations(footnotes)
    classify_all(authorities)
    
    print(f"Total resolved unique authorities: {len(authorities)}")
    assert len(authorities) > 15
    
    # Group breakdown
    counts = {}
    for a in authorities:
        counts[a.category.value] = counts.get(a.category.value, 0) + 1
        
    print("\n--- Authority Breakdown by Category ---")
    for cat, count in counts.items():
        print(f"  {cat}: {count}")
        
    # Check specific resolved cases from memo
    emirates = next((a for a in authorities if "Emirates Trading" in a.title or (a.short_name and "Emirates" in a.short_name)), None)
    assert emirates is not None, "Emirates Trading should be resolved"
    print(f"\nResolved 'Emirates Trading':")
    print(f"  Title: {emirates.title}")
    print(f"  Citation: {emirates.citation}")
    print(f"  Category: {emirates.category}")
    print(f"  Source Footnotes count: {len(emirates.source_footnote_ids)}")
    print(f"  Aggregated Pinpoints: {emirates.pinpoints}")
    assert len(emirates.pinpoints) > 1
    assert len(emirates.source_footnote_ids) > 1

    # Check cross-ref like Ohpen Operations
    ohpen = next((a for a in authorities if "Ohpen" in a.title), None)
    assert ohpen is not None
    print(f"\nResolved 'Ohpen Operations':")
    print(f"  Title: {ohpen.title}")
    print(f"  Pinpoints: {ohpen.pinpoints}")
    print(f"  Source footnotes: {ohpen.source_footnote_ids}")

    # Check UK Arbitration Act 1996
    uk_arb = next((a for a in authorities if "Arbitration Act 1996" in a.title or "Arbitration Act 1996" in a.raw_citation), None)
    assert uk_arb is not None
    print(f"\nResolved UK Arbitration Act 1996:")
    print(f"  Category: {uk_arb.category}")
    print(f"  Pinpoints: {uk_arb.pinpoints}")

    # Check SIAC Rules
    siac = next((a for a in authorities if "SIAC" in a.title or "SIAC" in a.raw_citation), None)
    assert siac is not None
    print(f"\nResolved SIAC Rules:")
    print(f"  Category: {siac.category}")
    print(f"  Pinpoints: {siac.pinpoints}")

if __name__ == "__main__":
    test_memo_resolution_and_classification()
    print("\nAll resolution and classification tests passed!")
