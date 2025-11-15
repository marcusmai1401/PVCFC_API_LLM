"""
Test H-5: Citation Regex - Verify both [Doc X] and [Doc X, p.Y] formats work
"""
import sys

sys.path.insert(0, "C:/Users/Admin/Desktop/Code - API_LLM_PVCFC")

from app.rag.generator import GeneratorConfig, ResponseGenerator
from app.rag.retriever import RetrievalResult


def test_citation_extraction_both_formats():
    """Test that both [Doc X] and [Doc X, p.Y] formats are parsed"""

    # Create generator
    config = GeneratorConfig()
    generator = ResponseGenerator(config=config)

    # Mock doc_mapping
    doc_mapping = {
        1: RetrievalResult(
            chunk_id="chunk1",
            doc_id="doc1",
            text="Text about pressure",
            score=0.9,
            source="test.pdf",
            page=10,
            metadata={"page": 10},
        ),
        2: RetrievalResult(
            chunk_id="chunk2",
            doc_id="doc2",
            text="Text about temperature",
            score=0.8,
            source="test2.pdf",
            page=20,
            metadata={"page": 20},
        ),
    }

    # Answer with BOTH formats
    answer = "According to [Doc 1], the pressure is 150 psi [Doc 2, p.5]. The specifications [Doc 1] confirm this."

    # Extract citations
    citations = generator._extract_citations(answer, doc_mapping)

    print("\n=== Test H-5: Citation Regex Both Formats ===")
    print(f"Answer: {answer}")
    print(f"Extracted {len(citations)} citations:")
    for i, cit in enumerate(citations, 1):
        print(f"  [{i}] doc_id={cit.doc_id}, page={cit.page}")

    # Assertions
    assert (
        len(citations) >= 2
    ), f"Should extract at least 2 citations (Doc 1 appears twice), got {len(citations)}"

    # Check Doc 1 citation (without explicit page)
    doc1_cits = [c for c in citations if c.doc_id == "doc1"]
    assert len(doc1_cits) >= 1, "Should have at least 1 citation for Doc 1"
    doc1_cit = doc1_cits[0]
    assert doc1_cit.page in [
        10,
        None,
    ], f"Doc 1 page should be 10 (from metadata) or None, got {doc1_cit.page}"

    # Check Doc 2 citation (with explicit page 5)
    doc2_cits = [c for c in citations if c.doc_id == "doc2"]
    assert (
        len(doc2_cits) == 1
    ), f"Should have 1 citation for Doc 2, got {len(doc2_cits)}"
    doc2_cit = doc2_cits[0]
    assert (
        doc2_cit.page == 5
    ), f"Doc 2 page should be 5 (from citation), got {doc2_cit.page}"

    print("\n✅ CITATION REGEX TEST PASSED")
    print(f"   - [Doc X] format: ✓ Parsed (Doc 1)")
    print(f"   - [Doc X, p.Y] format: ✓ Parsed (Doc 2, p.5)")
    print(f"   - Explicit page override: ✓ (page=5 instead of metadata page=20)")


def test_citation_footnote_style():
    """Test footnote style [1], [2] citations"""

    config = GeneratorConfig()
    generator = ResponseGenerator(config=config)

    doc_mapping = {
        1: RetrievalResult(
            chunk_id="chunk1",
            doc_id="doc1",
            text="Text",
            score=0.9,
            source="test.pdf",
            page=10,
            metadata={},
        ),
        2: RetrievalResult(
            chunk_id="chunk2",
            doc_id="doc2",
            text="Text",
            score=0.8,
            source="test2.pdf",
            page=20,
            metadata={},
        ),
    }

    # Footnote style
    answer = "The pressure is 150 psi [1]. The temperature is 200F [2]."

    citations = generator._extract_citations(answer, doc_mapping)

    print("\n=== Test H-5: Footnote Style Citations ===")
    print(f"Answer: {answer}")
    print(f"Extracted {len(citations)} citations:")
    for i, cit in enumerate(citations, 1):
        print(f"  [{i}] doc_id={cit.doc_id}, page={cit.page}")

    assert (
        len(citations) == 2
    ), f"Should extract 2 footnote citations, got {len(citations)}"

    print("\n✅ FOOTNOTE CITATION TEST PASSED")
    print(f"   - [1] format: ✓ Parsed")
    print(f"   - [2] format: ✓ Parsed")


if __name__ == "__main__":
    test_citation_extraction_both_formats()
    test_citation_footnote_style()
    print("\n" + "=" * 50)
    print("ALL H-5 TESTS PASSED ✅")
    print("H-5 is NOT an issue - regex already correct!")
    print("=" * 50)
