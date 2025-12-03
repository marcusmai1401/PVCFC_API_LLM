"""
Test script for PageReranker module

Tests:
1. Load page index
2. Rank pages within a document for a query
3. Validate page existence
4. Get page text
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger

from app.rag.page_reranker import PageReranker

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")


def test_page_reranker():
    """Test PageReranker functionality"""

    print("=" * 80)
    print("Testing PageReranker Module")
    print("=" * 80)

    # Initialize reranker
    print("\n1. Initializing PageReranker...")
    reranker = PageReranker()

    # Test with a known document
    # Let's find a doc_id from the page index first
    print("\n2. Loading sample document IDs...")

    import pickle

    index_path = Path("artifacts/ingestion_production/page_bm25_index.pkl")

    if not index_path.exists():
        print(f"ERROR: Page index not found at {index_path}")
        return

    with open(index_path, "rb") as f:
        data = pickle.load(f)

    doc_ids = data["doc_ids"]
    pages = data["pages"]

    # Get unique doc_ids and their page counts
    from collections import defaultdict

    doc_page_counts = defaultdict(list)
    for doc_id, page in zip(doc_ids, pages):
        doc_page_counts[doc_id].append(page)

    print(f"\nTotal pages in index: {len(doc_ids)}")
    print(f"Total documents: {len(doc_page_counts)}")

    # Pick a document with multiple pages for testing
    test_doc_id = None
    for doc_id, page_list in sorted(
        doc_page_counts.items(), key=lambda x: len(x[1]), reverse=True
    )[:5]:
        print(f"  {doc_id}: {len(page_list)} pages")
        if test_doc_id is None:
            test_doc_id = doc_id

    if test_doc_id is None:
        print("ERROR: No documents found in index")
        return

    print(f"\nUsing test document: {test_doc_id}")
    print(f"Pages: {sorted(doc_page_counts[test_doc_id])[:10]}...")

    # Test queries
    test_queries = [
        "operating pressure",
        "temperature range",
        "specifications",
        "installation instructions",
        "safety warnings",
    ]

    print("\n3. Testing page ranking with different queries...")
    print("-" * 80)

    for query in test_queries:
        print(f"\nQuery: '{query}'")

        results = reranker.rank_pages_for_doc(
            query=query,
            doc_id=test_doc_id,
            top_k=5,
        )

        if results:
            print(f"Top {len(results)} pages:")
            for page_num, score in results:
                print(f"  Page {page_num}: score={score:.4f}")
        else:
            print("  No results found")

    # Test page validation
    print("\n4. Testing page validation...")
    print("-" * 80)

    test_page = sorted(doc_page_counts[test_doc_id])[0]
    exists = reranker.validate_page_exists(test_doc_id, test_page)
    print(f"Page {test_page} exists in doc {test_doc_id}: {exists}")

    non_existent_page = 9999
    exists = reranker.validate_page_exists(test_doc_id, non_existent_page)
    print(f"Page {non_existent_page} exists in doc {test_doc_id}: {exists}")

    # Test get page text
    print("\n5. Testing get_page_text...")
    print("-" * 80)

    text = reranker.get_page_text(test_doc_id, test_page)
    if text:
        print(f"Retrieved text from page {test_page}:")
        print(f"  Length: {len(text)} chars")
        print(f"  Preview: {text[:200]}...")
    else:
        print(f"Failed to retrieve text for page {test_page}")

    print("\n" + "=" * 80)
    print("PageReranker tests completed!")
    print("=" * 80)


if __name__ == "__main__":
    test_page_reranker()
