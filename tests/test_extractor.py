import os
from boa_core.extractor import extract_docx_footnotes, split_composite_footnote
from conftest import requires_memo

@requires_memo
def test_memo_extraction():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    memo_path = os.path.join(base_dir, "Example docs for BOA", "Example memo with a certain order for list of authorities that can be used for BOAs (but no BOA).docx")
    assert os.path.exists(memo_path), "Memo file not found"
    
    footnotes = extract_docx_footnotes(memo_path, include_sentence_context=True)
    print(f"Total footnotes extracted: {len(footnotes)}")
    assert len(footnotes) > 90
    
    authorities = [fn for fn in footnotes if fn.is_authority]
    evidence = [fn for fn in footnotes if not fn.is_authority]
    
    print(f"Legal authority candidates: {len(authorities)}")
    print(f"Filtered factual / evidence citations: {len(evidence)}")
    
    # Check that known exhibits are filtered
    for ev in evidence[:5]:
        print(f"  [Filtered] Footnote {ev.footnote_id}: {ev.raw_text[:70]} ({ev.non_authority_reason})")
        assert "Exhibit" in ev.raw_text or "Record" in ev.raw_text or "Notice" in ev.raw_text or "Procedural" in ev.raw_text
        
    # Check composite footnote splitting
    sample_composite = "UK Arbitration Act 1996, s 81(1)(a); See also J DM Lew and O Mardsen, 'Arbitrability', in J D M Lew...; and M. Danov, 'The Law...'"
    chunks = split_composite_footnote(sample_composite)
    print(f"\nComposite split into {len(chunks)} chunks:")
    for c in chunks:
        print("  -", c[:60])
    assert len(chunks) == 3

if __name__ == "__main__":
    test_memo_extraction()
    print("\nAll extraction tests passed!")
