"""Direct retrieval test for P&ID tags to verify correct page retrieval"""
import sys

sys.path.insert(0, "C:/Users/Admin/Desktop/Code - API_LLM_PVCFC")

from app.rag.hybrid_with_tags_retriever import HybridWithTagsRetriever

# Initialize retriever
print("Initializing retriever...")
retriever = HybridWithTagsRetriever()

# Test cases
TEST_CASES = [
    {"name": "Test 1: FIC-310", "query": "FIC-310", "expected_page": 9},
    {"name": "Test 2: PIC-560", "query": "PIC-560", "expected_page": 14},
    {"name": "Test 3: TIC-460", "query": "TIC-460", "expected_page": 10},
    {"name": "Test 4: LIC-520", "query": "LIC-520", "expected_page": 12},
]

print("=" * 70)
print("TESTING P&ID TAG RETRIEVAL (DIRECT)")
print("=" * 70)

results = {"total": len(TEST_CASES), "passed": 0, "failed": 0}

for test in TEST_CASES:
    print("\n" + "=" * 70)
    print(test["name"])
    print("=" * 70)
    print(f"Query: {test['query']}")
    print(f"Expected page: {test['expected_page']}")

    # Retrieve with PID mode
    chunks = retriever.retrieve(
        query=test["query"], top_k=10, filters=None, query_type="pid"  # Force PID mode
    )

    if not chunks:
        print("❌ FAILED: No chunks retrieved")
        results["failed"] += 1
        continue

    print(f"\nRetrieved {len(chunks)} chunks")
    print("\nTop 5 chunks:")
    for i, chunk in enumerate(chunks[:5], 1):
        page = (
            chunk.get("page")
            or chunk.get("metadata", {}).get("page")
            or chunk.get("page_start")
        )
        print(
            f"  {i}. page={page}, score={chunk.get('score', 0):.4f}, chunk_id={chunk.get('chunk_id', 'unknown')[:80]}..."
        )

    # Check top result
    top_chunk = chunks[0]
    actual_page = (
        top_chunk.get("page")
        or top_chunk.get("metadata", {}).get("page")
        or top_chunk.get("page_start")
    )

    if actual_page == test["expected_page"]:
        print(f"\n✅ PASSED: Page matches (page={actual_page})")
        results["passed"] += 1
    else:
        print(
            f"\n❌ FAILED: Page mismatch (expected={test['expected_page']}, got={actual_page})"
        )
        results["failed"] += 1

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"Total: {results['total']}")
print(f"Passed: {results['passed']} ✅")
print(f"Failed: {results['failed']} ❌")
print(f"Success rate: {100 * results['passed'] / results['total']:.1f}%")

if results["passed"] == results["total"]:
    print("\n🎉 ALL TESTS PASSED - INDEX IS WORKING CORRECTLY!")
else:
    print(f"\n⚠️  {results['failed']} test(s) failed")
