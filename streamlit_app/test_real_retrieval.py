"""
Test that the UI components can retrieve real PDF content
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Test direct retrieval
from app.rag.indexers.bm25_indexer import BM25Indexer

print("=" * 60)
print("TESTING BM25 RETRIEVAL")
print("=" * 60)

# Load BM25 index
bm25 = BM25Indexer()
index_path = project_root / "artifacts" / "index" / "bm25"

print(f"\nLoading BM25 index from: {index_path}")

try:
    bm25.load_index(str(index_path))
    print("✅ BM25 index loaded successfully")

    # Test queries
    test_queries = [
        "CO2 compressor",
        "steam turbine",
        "SPECIAL PURPOSE STEAM TURBINE DATA SHEET",
        "KT06101",
    ]

    for query in test_queries:
        print(f"\n" + "-" * 40)
        print(f"Query: {query}")
        results = bm25.search(query, top_k=2)

        if results:
            for i, result in enumerate(results, 1):
                print(f"\nResult {i}:")
                print(f"  Score: {result['score']:.3f}")
                print(f"  Doc: {result['metadata'].get('doc_id', 'Unknown')}")
                print(f"  Content preview: {result['text'][:200]}...")
        else:
            print("  ❌ No results found")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()

# Now test what the Gemini integration sees
print("\n" + "=" * 60)
print("TESTING GEMINI INTEGRATION RETRIEVAL")
print("=" * 60)

try:
    # Do a quick test without calling Gemini
    import time

    from components.rag_gemini_direct import process_with_gemini_direct

    start = time.time()

    # Mock the Gemini client to avoid API calls
    def mock_generate(*args, **kwargs):
        class MockResponse:
            content = "Mock response for testing retrieval"

        return MockResponse()

    # Patch the function temporarily
    import components.rag_gemini_direct as rgd

    from app.services.llm_client import GeminiClient

    original_generate = GeminiClient.generate
    GeminiClient.generate = mock_generate

    try:
        result = process_with_gemini_direct(
            query="CO2 compressor specifications", max_tokens=50, temperature=0.1
        )

        print("\nRetrieved documents in UI:")
        for i, doc in enumerate(result.get("retrieved_docs", []), 1):
            print(f"\nDoc {i}:")
            print(f"  Title: {doc.get('title', 'Unknown')}")
            print(f"  Source: {doc.get('source', 'Unknown')}")
            print(f"  Score: {doc.get('score', 0):.3f}")
            print(f"  Content preview: {doc.get('content', '')[:200]}...")

    finally:
        # Restore original
        GeminiClient.generate = original_generate

except Exception as e:
    print(f"❌ Error testing Gemini integration: {e}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
