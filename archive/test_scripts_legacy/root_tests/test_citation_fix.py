#!/usr/bin/env python
"""Test citation page numbers after fixing page=0 handling"""

import json

from loguru import logger

from app.rag.generator import ResponseGenerator
from app.rag.hybrid_weaviate_opensearch_retriever import (
    HybridWeaviateOpenSearchRetriever,
)


def test_tag_retrieval():
    """Test that tag 04 PU 2049 returns correct page numbers"""

    # Initialize retriever
    retriever = HybridWeaviateOpenSearchRetriever()

    # Test query with tag
    query = "04 PU 2049 áp suất thiết kế là bao nhiêu?"

    print(f"\n{'='*80}")
    print(f"Testing query: {query}")
    print(f"{'='*80}\n")

    # Get retrieval results
    results = retriever.retrieve_enhanced(query, top_k=10)

    print(f"Retrieved {len(results)} results\n")

    # Check page numbers for results containing the tag
    tag_results = []
    for i, result in enumerate(results):
        if "04 PU 2049" in result.text or "PU 2049" in result.text:
            tag_results.append(result)
            print(f"Result {i+1} (contains tag):")
            print(f"  - Chunk ID: {result.chunk_id}")
            print(f"  - Page: {result.page}")
            print(f"  - Source: {result.source}")
            print(f"  - Score: {result.score:.4f}")
            print(f"  - Text preview: {result.text[:200]}...")
            print()

    # Check for page=0 issues
    zero_page_count = sum(1 for r in tag_results if r.page == 0)
    none_page_count = sum(1 for r in tag_results if r.page is None)

    print(f"\nSummary:")
    print(f"  - Total results with tag: {len(tag_results)}")
    print(f"  - Results with page=0: {zero_page_count}")
    print(f"  - Results with page=None: {none_page_count}")

    if zero_page_count > 0 or none_page_count > 0:
        logger.warning(f"⚠️  Still have invalid page numbers!")
    else:
        logger.success(f"✅ All tag results have valid page numbers!")

    return tag_results


def test_full_pipeline():
    """Test the full RAG pipeline with citation generation"""

    # Initialize retriever and generator
    retriever = HybridWeaviateOpenSearchRetriever()
    generator = ResponseGenerator()

    # Test query
    query = "04 PU 2049 áp suất thiết kế là bao nhiêu?"

    print(f"\n{'='*80}")
    print(f"Testing full pipeline with query: {query}")
    print(f"{'='*80}\n")

    # First get retrieval results
    retrieved_docs = retriever.retrieve_enhanced(query, top_k=10)

    # Transform query for generator
    from app.rag.query_transform import QueryFilters, TransformedQuery

    transformed = TransformedQuery(
        original=query,
        normalized=query,
        intent="specific_question",
        filters=QueryFilters(),
        language="vi",
    )

    # Generate response
    result = generator.generate(transformed, retrieved_docs)

    print(f"Response: {result.answer[:500]}...")
    print(f"\nCitations ({len(result.citations)}):")

    for i, citation in enumerate(result.citations, 1):
        print(f"\n  Citation {i}:")
        print(f"    - Text: {citation.text[:100]}...")
        print(f"    - Page: {citation.page}")
        print(f"    - Doc ID: {citation.doc_id}")
        print(f"    - Chunk ID: {citation.chunk_id}")

    # Check for page issues in citations
    zero_pages = [c for c in result.citations if c.page == 0]
    none_pages = [c for c in result.citations if c.page is None]

    print(f"\n{'='*80}")
    print(f"Citation Analysis:")
    print(f"  - Total citations: {len(result.citations)}")
    print(f"  - Citations with page=0: {len(zero_pages)}")
    print(f"  - Citations with page=None: {len(none_pages)}")

    if zero_pages or none_pages:
        logger.warning(f"⚠️  Found citations with invalid pages!")
        if zero_pages:
            print(f"\nCitations with page=0:")
            for c in zero_pages[:3]:  # Show first 3
                print(f"  - {c.chunk_id}: {c.text[:50]}...")
    else:
        logger.success(f"✅ All citations have valid page numbers!")

    print(f"{'='*80}\n")


def main():
    """Run all tests"""

    # Test retrieval
    print("\n" + "=" * 80)
    print("PART 1: TESTING RETRIEVAL")
    print("=" * 80)
    test_tag_retrieval()

    # Test full pipeline
    print("\n" + "=" * 80)
    print("PART 2: TESTING FULL PIPELINE")
    print("=" * 80)
    test_full_pipeline()

    print("\n✅ Test completed!")


if __name__ == "__main__":
    main()
