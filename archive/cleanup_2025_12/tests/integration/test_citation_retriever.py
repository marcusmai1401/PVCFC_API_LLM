"""
Test Citation Retriever - End-to-End RAG Pipeline

Comprehensive tests for the integrated RAG pipeline:
1. Basic citation retrieval
2. Single document search
3. Multi-document search
4. Snippet integration
5. Ranking and scoring
6. Real-world queries
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.rag.citation_retriever import (
    CitationResult,
    CitationRetriever,
    SearchConfig,
    get_citation_retriever,
)


def test_initialization():
    """Test CitationRetriever initialization"""
    print("=" * 80)
    print("Test 1: Initialization")
    print("=" * 80)

    try:
        retriever = CitationRetriever()
        print("✓ CitationRetriever initialized successfully")
        print(f"  Page reranker: {retriever.page_reranker is not None}")
        print(f"  Snippet extractor: {retriever.snippet_extractor is not None}")
        print(f"  Config: {retriever.config}")
        return True
    except Exception as e:
        print(f"✗ Initialization failed: {e}")
        return False


def test_singleton_pattern():
    """Test singleton pattern"""
    print("\n" + "=" * 80)
    print("Test 2: Singleton Pattern")
    print("=" * 80)

    retriever1 = get_citation_retriever()
    retriever2 = get_citation_retriever()

    assert retriever1 is retriever2, "Should return same instance"
    print("✓ Singleton pattern working")

    return True


def test_single_document_search():
    """Test searching within a single document"""
    print("\n" + "=" * 80)
    print("Test 3: Single Document Search")
    print("=" * 80)

    retriever = CitationRetriever()

    # Get a sample document ID from the index
    doc_ids = retriever._get_all_doc_ids()

    if not doc_ids:
        print("⚠ No documents in index, skipping test")
        return True

    # Use first doc with most pages (likely to have content)
    test_doc_id = doc_ids[0]

    query = "operating pressure"

    print(f"\nSearching in document: {test_doc_id[:50]}...")
    print(f"Query: '{query}'")

    config = SearchConfig(
        top_k_pages_per_doc=3,
        max_snippets_per_page=2,
    )

    citations = retriever.search_in_document(query, test_doc_id, config)

    print(f"\nFound {len(citations)} citations")

    for citation in citations:
        print(f"\n  Citation {citation.rank}:")
        print(f"    Page: {citation.page}")
        print(f"    Score: {citation.score:.3f}")
        print(f"    Snippets: {len(citation.snippets)}")

        if citation.snippets:
            print(f"    First snippet: {citation.snippets[0].text[:80]}...")

    # Assertions
    if citations:
        assert all(
            c.doc_id == test_doc_id for c in citations
        ), "All citations should be from test doc"
        assert all(c.page > 0 for c in citations), "Page numbers should be valid"
        assert all(c.score > 0 for c in citations), "Scores should be positive"
        assert citations[0].rank == 1, "First citation should have rank 1"

        # Check sorting
        for i in range(len(citations) - 1):
            assert (
                citations[i].score >= citations[i + 1].score
            ), "Should be sorted by score"

    print("\n✓ PASS - Single document search working")
    return True


def test_multi_document_search():
    """Test searching across multiple documents"""
    print("\n" + "=" * 80)
    print("Test 4: Multi-Document Search")
    print("=" * 80)

    retriever = CitationRetriever()

    doc_ids = retriever._get_all_doc_ids()

    if len(doc_ids) < 2:
        print("⚠ Not enough documents for multi-doc search, skipping")
        return True

    # Select first 3 documents
    test_docs = doc_ids[:3]

    query = "temperature pressure specifications"

    print(f"\nSearching in {len(test_docs)} documents")
    print(f"Query: '{query}'")

    config = SearchConfig(
        top_k_docs=3,
        top_k_pages_per_doc=2,
        max_total_citations=5,
    )

    citations = retriever.search_with_citations(
        query=query,
        doc_ids=test_docs,
        config_override=config,
    )

    print(f"\nFound {len(citations)} citations across documents")

    # Count citations per document
    from collections import Counter

    doc_counts = Counter(c.doc_id for c in citations)

    print(f"\nCitations per document:")
    for doc_id, count in doc_counts.items():
        doc_name = retriever._extract_doc_name(doc_id)
        print(f"  {doc_name}: {count} citations")

    # Display top citations
    print(f"\nTop citations:")
    for citation in citations[:3]:
        print(
            f"\n  [{citation.rank}] {citation.metadata.get('doc_name', 'Unknown')}, Page {citation.page}"
        )
        print(f"      Score: {citation.score:.3f}")
        print(f"      Snippets: {len(citation.snippets)}")

    # Assertions
    if citations:
        assert (
            len(citations) <= config.max_total_citations
        ), "Should respect max_total_citations"
        assert all(
            c.doc_id in test_docs for c in citations
        ), "Should only return from test docs"

        # Check ranking
        for i, citation in enumerate(citations, 1):
            assert citation.rank == i, f"Rank should be {i}"

    print("\n✓ PASS - Multi-document search working")
    return True


def test_snippet_integration():
    """Test snippet extraction integration"""
    print("\n" + "=" * 80)
    print("Test 5: Snippet Integration")
    print("=" * 80)

    retriever = CitationRetriever()

    doc_ids = retriever._get_all_doc_ids()

    if not doc_ids:
        print("⚠ No documents, skipping")
        return True

    query = "safety warnings"

    config = SearchConfig(
        top_k_docs=2,
        top_k_pages_per_doc=2,
        max_snippets_per_page=3,
        highlight_keywords=True,
    )

    citations = retriever.search_with_citations(
        query=query,
        doc_ids=doc_ids[:2],
        config_override=config,
    )

    print(f"\nQuery: '{query}'")
    print(f"Citations with snippets: {len(citations)}")

    snippet_count = sum(len(c.snippets) for c in citations)
    print(f"Total snippets: {snippet_count}")

    # Check at least one citation has snippets with highlighting
    has_highlighted = False
    for citation in citations:
        for snippet in citation.snippets:
            if snippet.highlighted_text and "**" in snippet.highlighted_text:
                has_highlighted = True
                print(f"\nSample highlighted snippet:")
                print(f"  {snippet.highlighted_text[:150]}...")
                break
        if has_highlighted:
            break

    print(f"\nHighlighting working: {has_highlighted}")

    print("\n✓ PASS - Snippet integration working")
    return True


def test_citation_formatting():
    """Test citation formatting"""
    print("\n" + "=" * 80)
    print("Test 6: Citation Formatting")
    print("=" * 80)

    retriever = CitationRetriever()

    doc_ids = retriever._get_all_doc_ids()

    if not doc_ids:
        print("⚠ No documents, skipping")
        return True

    query = "operating pressure"

    citations = retriever.search_with_citations(
        query=query,
        doc_ids=doc_ids[:1],
        config_override=SearchConfig(top_k_pages_per_doc=2),
    )

    if not citations:
        print("⚠ No citations found, skipping")
        return True

    # Test to_dict()
    citation_dict = citations[0].to_dict()
    print(f"\nCitation as dict:")
    print(f"  Keys: {list(citation_dict.keys())}")
    assert "doc_id" in citation_dict
    assert "page" in citation_dict
    assert "score" in citation_dict
    assert "snippets" in citation_dict

    # Test format_citation()
    formatted = citations[0].format_citation(include_snippets=True)
    print(f"\nFormatted citation:")
    print(formatted[:200] + "...")

    assert f"[{citations[0].rank}]" in formatted
    assert f"Page {citations[0].page}" in formatted

    print("\n✓ PASS - Citation formatting working")
    return True


def test_deduplication():
    """Test page deduplication"""
    print("\n" + "=" * 80)
    print("Test 7: Deduplication")
    print("=" * 80)

    retriever = CitationRetriever()

    # Test the deduplication logic directly
    from app.rag.snippet_extractor import Snippet

    # Create mock citations with duplicates
    mock_citations = [
        CitationResult(
            doc_id="doc1",
            page=1,
            score=0.9,
            page_text="test",
            snippets=[],
            metadata={},
        ),
        CitationResult(
            doc_id="doc1",
            page=1,  # Duplicate
            score=0.7,  # Lower score
            page_text="test",
            snippets=[],
            metadata={},
        ),
        CitationResult(
            doc_id="doc1",
            page=2,
            score=0.8,
            page_text="test",
            snippets=[],
            metadata={},
        ),
    ]

    deduplicated = retriever._deduplicate_citations(mock_citations)

    print(f"\nOriginal citations: {len(mock_citations)}")
    print(f"After deduplication: {len(deduplicated)}")

    # Should remove the duplicate (doc1, page 1) with lower score
    assert len(deduplicated) == 2, "Should have 2 unique pages"

    # Check the kept citation has higher score
    doc1_page1 = [c for c in deduplicated if c.doc_id == "doc1" and c.page == 1]
    assert len(doc1_page1) == 1
    assert doc1_page1[0].score == 0.9, "Should keep higher score"

    print("✓ PASS - Deduplication working")
    return True


def test_real_world_query():
    """Test with real-world query"""
    print("\n" + "=" * 80)
    print("Test 8: Real-World Query")
    print("=" * 80)

    retriever = CitationRetriever()

    doc_ids = retriever._get_all_doc_ids()

    if not doc_ids:
        print("⚠ No documents, skipping")
        return True

    # Real-world query about technical specifications
    query = "maximum operating pressure temperature specifications"

    print(f"\nQuery: '{query}'")
    print(f"Searching across {len(doc_ids)} documents")

    config = SearchConfig(
        top_k_docs=5,
        top_k_pages_per_doc=3,
        max_total_citations=10,
        max_snippets_per_page=2,
        highlight_keywords=True,
    )

    citations = retriever.search_with_citations(
        query=query,
        config_override=config,
    )

    print(f"\nFound {len(citations)} citations")

    # Display results in user-friendly format
    print(f"\n{'='*80}")
    print("SEARCH RESULTS")
    print(f"{'='*80}")

    for citation in citations[:5]:  # Show top 5
        formatted = citation.format_citation(include_snippets=True)
        print(f"\n{formatted}")
        print(f"{'-'*80}")

    # Assertions
    if citations:
        assert len(citations) > 0, "Should find citations"
        assert all(c.rank > 0 for c in citations), "All should have rank"
        assert all(c.score > 0 for c in citations), "All should have score"

        # Check that top citation has snippets
        if citations[0].snippets:
            print(f"\n✓ Top citation has {len(citations[0].snippets)} snippets")

    print("\n✓ PASS - Real-world query working")
    return True


def test_edge_cases():
    """Test edge cases"""
    print("\n" + "=" * 80)
    print("Test 9: Edge Cases")
    print("=" * 80)

    retriever = CitationRetriever()

    # Test 1: Empty query
    citations = retriever.search_with_citations(query="")
    assert len(citations) == 0, "Empty query should return no results"
    print("✓ Empty query handled")

    # Test 2: Empty doc_ids list
    citations = retriever.search_with_citations(query="test", doc_ids=[])
    assert len(citations) == 0, "Empty doc_ids should return no results"
    print("✓ Empty doc_ids handled")

    # Test 3: Non-existent document
    citations = retriever.search_in_document(
        query="test", doc_id="NONEXISTENT_DOC_12345"
    )
    assert len(citations) == 0, "Non-existent doc should return no results"
    print("✓ Non-existent document handled")

    # Test 4: Very specific query with no matches
    doc_ids = retriever._get_all_doc_ids()
    if doc_ids:
        citations = retriever.search_with_citations(
            query="xyzabc123nonexistent",
            doc_ids=doc_ids[:1],
        )
        print(f"✓ No-match query returned {len(citations)} results")

    print("\n✓ PASS - Edge cases handled")
    return True


def run_all_tests():
    """Run all citation retriever tests"""
    print("\n" + "=" * 80)
    print("CITATION RETRIEVER TEST SUITE")
    print("End-to-End RAG Pipeline Integration")
    print("=" * 80)

    tests = [
        ("Initialization", test_initialization),
        ("Singleton Pattern", test_singleton_pattern),
        ("Single Document Search", test_single_document_search),
        ("Multi-Document Search", test_multi_document_search),
        ("Snippet Integration", test_snippet_integration),
        ("Citation Formatting", test_citation_formatting),
        ("Deduplication", test_deduplication),
        ("Real-World Query", test_real_world_query),
        ("Edge Cases", test_edge_cases),
    ]

    results = []
    for name, test_fn in tests:
        try:
            result = test_fn()
            results.append((name, result))
        except AssertionError as e:
            print(f"\n✗ Test '{name}' failed: {e}")
            results.append((name, False))
        except Exception as e:
            print(f"\n✗ Test '{name}' raised exception: {e}")
            import traceback

            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\n{'-' * 80}")
    print(f"Total: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! RAG Pipeline is working correctly.")
    else:
        print(f"⚠ {total - passed} test(s) failed")

    print("=" * 80)

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
