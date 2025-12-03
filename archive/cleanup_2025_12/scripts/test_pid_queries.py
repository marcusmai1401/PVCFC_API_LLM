"""Test P&ID tag queries to verify correct page retrieval after re-indexing"""
import json

import requests

# API endpoint
API_URL = "http://localhost:8000/ask"

# Test cases from the original audit
TEST_CASES = [
    {
        "name": "Test 1: FIC-310",
        "query": "FIC-310 nằm ở trang nào trong P&ID?",
        "expected_page": 9,
        "doc_type": "P&ID",
    },
    {
        "name": "Test 2: PIC-560",
        "query": "PIC-560 nằm ở trang nào?",
        "expected_page": 14,
        "doc_type": "P&ID",
    },
    {
        "name": "Test 3: TIC-460",
        "query": "TIC-460 nằm ở trang nào?",
        "expected_page": 10,
        "doc_type": "P&ID",
    },
    {
        "name": "Test 4: LIC-520",
        "query": "LIC-520 nằm ở trang nào?",
        "expected_page": 12,
        "doc_type": "P&ID",
    },
]

print("=" * 70)
print("TESTING P&ID TAG QUERIES")
print("=" * 70)
print(f"\nAPI endpoint: {API_URL}")
print(f"Total test cases: {len(TEST_CASES)}\n")

results = {"total": len(TEST_CASES), "passed": 0, "failed": 0, "details": []}

for i, test in enumerate(TEST_CASES, 1):
    print("=" * 70)
    print(f"{test['name']}")
    print("=" * 70)
    print(f"Query: {test['query']}")
    print(f"Expected page: {test['expected_page']}")

    try:
        # Make API request
        payload = {
            "query": test["query"],
            "query_type": "pid",
            "max_context": 5,
            "hyde": False,
            "language": "vi",
        }

        response = requests.post(API_URL, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Extract citations
        citations = data.get("citations", [])

        if not citations:
            print("❌ FAILED: No citations returned")
            results["failed"] += 1
            results["details"].append(
                {
                    "test": test["name"],
                    "status": "FAILED",
                    "reason": "No citations",
                    "expected_page": test["expected_page"],
                    "actual_page": None,
                }
            )
            print()
            continue

        # Get top citation
        top_citation = citations[0]
        actual_page = top_citation.get("page")
        doc_id = top_citation.get("doc_id", "unknown")
        confidence = top_citation.get("confidence", 0)

        print(f"\nTop citation:")
        print(f"  doc_id: {doc_id}")
        print(f"  page: {actual_page}")
        print(f"  confidence: {confidence:.4f}")

        # Check if page matches
        if actual_page == test["expected_page"]:
            print(
                f"\n✅ PASSED: Page matches expected ({actual_page} == {test['expected_page']})"
            )
            results["passed"] += 1
            results["details"].append(
                {
                    "test": test["name"],
                    "status": "PASSED",
                    "expected_page": test["expected_page"],
                    "actual_page": actual_page,
                    "confidence": confidence,
                }
            )
        else:
            print(
                f"\n❌ FAILED: Page mismatch (expected: {test['expected_page']}, got: {actual_page})"
            )
            results["failed"] += 1
            results["details"].append(
                {
                    "test": test["name"],
                    "status": "FAILED",
                    "reason": "Page mismatch",
                    "expected_page": test["expected_page"],
                    "actual_page": actual_page,
                    "confidence": confidence,
                }
            )

        # Show all citations for debugging
        print(f"\nAll citations (up to 5):")
        for j, citation in enumerate(citations[:5], 1):
            print(
                f"  {j}. page={citation.get('page')}, confidence={citation.get('confidence', 0):.4f}, doc_id={citation.get('doc_id', 'unknown')[:60]}..."
            )

    except requests.exceptions.RequestException as e:
        print(f"❌ FAILED: API request error - {e}")
        results["failed"] += 1
        results["details"].append(
            {
                "test": test["name"],
                "status": "FAILED",
                "reason": f"API error: {str(e)}",
                "expected_page": test["expected_page"],
                "actual_page": None,
            }
        )

    except Exception as e:
        print(f"❌ FAILED: Unexpected error - {e}")
        results["failed"] += 1
        results["details"].append(
            {
                "test": test["name"],
                "status": "FAILED",
                "reason": f"Unexpected error: {str(e)}",
                "expected_page": test["expected_page"],
                "actual_page": None,
            }
        )

    print()

# Summary
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"Total tests: {results['total']}")
print(f"Passed: {results['passed']} ✅")
print(f"Failed: {results['failed']} ❌")
print(f"Success rate: {100 * results['passed'] / results['total']:.1f}%")

# Detailed results
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

# Save results to file
output_file = "artifacts/pid_query_test_results.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"Results saved to: {output_file}")

# Exit code
if results["failed"] == 0:
    print("\n🎉 ALL TESTS PASSED!")
    exit(0)
else:
    print(f"\n⚠️  {results['failed']} TEST(S) FAILED!")
    exit(1)
