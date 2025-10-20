#!/usr/bin/env python
"""Quick test for page number preservation in retrieval"""

from loguru import logger

from app.rag.hybrid_weaviate_opensearch_retriever import (
    HybridWeaviateOpenSearchRetriever,
)


def test_tag_pages():
    """Test that tag 04 PU 2049 preserves page numbers through retrieval"""

    # Initialize retriever
    retriever = HybridWeaviateOpenSearchRetriever()

    # Test query with tag
    query = "04 PU 2049 áp suất thiết kế"

    print(f"\nTesting: {query}")
    print("=" * 60)

    # Get results
    results = retriever.retrieve_enhanced(query, top_k=10)

    # Check results with the tag
    tag_results = []
    for i, result in enumerate(results):
        if "PU 2049" in result.text or "04 PU 2049" in result.text:
            tag_results.append(result)
            print(f"\nResult {i+1}:")
            print(f"  Chunk: {result.chunk_id}")
            print(f"  Page: {result.page}")
            print(f"  Score: {result.score:.4f}")
            print(f"  Source: {result.source}")

    # Summary
    print("\n" + "=" * 60)
    print(f"Found {len(tag_results)} results with tag")

    page_issues = []
    for r in tag_results:
        if r.page == 0 or r.page is None:
            page_issues.append(r)

    if page_issues:
        print(f"\n❌ Found {len(page_issues)} results with page issues:")
        for r in page_issues:
            print(f"  - {r.chunk_id}: page={r.page}")
    else:
        print("\n✅ All tag results have valid page numbers!")

    return len(page_issues) == 0


if __name__ == "__main__":
    success = test_tag_pages()
    exit(0 if success else 1)
