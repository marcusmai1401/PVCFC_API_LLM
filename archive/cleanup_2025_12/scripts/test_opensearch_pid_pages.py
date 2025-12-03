"""Test OpenSearch BM25 retrieval for P&ID tags to verify page correctness"""
import json

import requests

# Test cases
TEST_CASES = [
    {"name": "Test 1: FIC-310", "query": "FIC-310", "expected_page": 9},
    {"name": "Test 2: PIC-560", "query": "PIC-560", "expected_page": 14},
    {"name": "Test 3: TIC-460", "query": "TIC-460", "expected_page": 10},
    {"name": "Test 4: LIC-520", "query": "LIC-520", "expected_page": 12},
]

print("=" * 70)
print("TESTING P&ID TAG PAGES (OpenSearch BM25)")
print("=" * 70)

results = {"total": len(TEST_CASES), "passed": 0, "failed": 0, "details": []}

for test in TEST_CASES:
    print("\n" + "=" * 70)
    print(test["name"])
    print("=" * 70)
    print(f"Query: {test['query']}")
    print(f"Expected page: {test['expected_page']}")

    # Search OpenSearch
    search_query = {
        "size": 10,
        "_source": ["chunk_id", "doc_id", "page", "page_start", "text"],
        "query": {"match": {"text": test["query"]}},
    }

    response = requests.post(
        "http://localhost:9200/rag_chunks/_search",
        json=search_query,
        headers={"Content-Type": "application/json"},
    )
    data = response.json()
    hits = data.get("hits", {}).get("hits", [])

    if not hits:
        print("❌ FAILED: No results from OpenSearch")
        results["failed"] += 1
        results["details"].append(
            {
                "test": test["name"],
                "status": "FAILED",
                "reason": "No results",
                "expected_page": test["expected_page"],
                "actual_page": None,
            }
        )
        continue

    print(f"\nFound {len(hits)} results")
    print("\nTop 5 results:")
    for i, hit in enumerate(hits[:5], 1):
        source = hit["_source"]
        page = source.get("page")
        score = hit["_score"]
        text_preview = source.get("text", "")[:80].replace("\n", " ")
        print(f"  {i}. page={page}, score={score:.4f}, text={text_preview}...")

    # Check top result
    top_hit = hits[0]
    actual_page = top_hit["_source"].get("page")

    if actual_page == test["expected_page"]:
        print(f"\n✅ PASSED: Page matches (page={actual_page})")
        results["passed"] += 1
        results["details"].append(
            {
                "test": test["name"],
                "status": "PASSED",
                "expected_page": test["expected_page"],
                "actual_page": actual_page,
            }
        )
    else:
        print(
            f"\n❌ FAILED: Page mismatch (expected={test['expected_page']}, got={actual_page})"
        )
        results["failed"] += 1
        results["details"].append(
            {
                "test": test["name"],
                "status": "FAILED",
                "reason": "Page mismatch",
                "expected_page": test["expected_page"],
                "actual_page": actual_page,
            }
        )

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"Total tests: {results['total']}")
print(f"Passed: {results['passed']} ✅")
print(f"Failed: {results['failed']} ❌")
print(f"Success rate: {100 * results['passed'] / results['total']:.1f}%")

print("\n" + "=" * 70)
print("DETAILED RESULTS")
print("=" * 70)
for detail in results["details"]:
    status_icon = "✅" if detail["status"] == "PASSED" else "❌"
    print(f"{status_icon} {detail['test']}")
    print(f"   Expected: page {detail['expected_page']}")
    print(f"   Actual: page {detail.get('actual_page', 'N/A')}")
    if detail["status"] == "FAILED":
        print(f"   Reason: {detail.get('reason', 'Unknown')}")
    print()

# Save results
output_file = "artifacts/opensearch_pid_test_results.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"Results saved to: {output_file}")

if results["passed"] == results["total"]:
    print("\n🎉 ALL TESTS PASSED - OPENSEARCH INDEX IS CORRECT!")
    exit(0)
else:
    print(f"\n⚠️  {results['failed']} TEST(S) FAILED!")
    exit(1)
