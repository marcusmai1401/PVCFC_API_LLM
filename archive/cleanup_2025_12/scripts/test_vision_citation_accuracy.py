#!/usr/bin/env python
"""
End-to-End Citation Accuracy Test

Tests citation accuracy with watermarked vision images.
Compares against expected results.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import time
from typing import Dict, List

import requests

# Test cases from VISION_CITATION_ACCURACY.md
TEST_CASES = [
    {
        "id": "TC1",
        "query": "MYLP 04504 là gì?",
        "expected_answer_contains": "STATUS",
        "expected_pages": [71],
        "description": "Single tag query - exact page citation",
    },
    {
        "id": "TC2",
        "query": "Tag name MYLP 04504 là STATUS hay ALARM hay STOP?",
        "expected_answer_contains": "STATUS",
        "expected_pages": [71],
        "description": "Multiple choice tag type query",
    },
    {
        "id": "TC3",
        "query": "Tìm tag MYLP 04501A",
        "expected_answer_contains": "STATUS",
        "expected_pages": [61],
        "description": "Different tag on different page",
    },
    {
        "id": "TC4",
        "query": "MYLP 04501A là gì?",
        "expected_answer_contains": "STATUS",
        "expected_pages": [61],
        "description": "Another tag - page 61",
    },
    {
        "id": "TC5",
        "query": "Tìm tag name có tên chính xác là MYLP 04504",
        "expected_answer_contains": ["MYLP 04504", "STATUS"],
        "expected_pages": [71],
        "description": "Explicit exact match query",
    },
]


def run_citation_test(api_url: str = "http://localhost:8000") -> Dict:
    """
    Run end-to-end citation accuracy test

    Returns:
        Dict with test results and metrics
    """

    print("=" * 70)
    print("CITATION ACCURACY TEST (with Watermark)")
    print("=" * 70)
    print(f"API URL: {api_url}")
    print(f"Test cases: {len(TEST_CASES)}\n")

    # Check API health
    try:
        resp = requests.get(f"{api_url}/healthz", timeout=5)
        if resp.status_code != 200:
            print(f"[ERROR] API not healthy: {resp.status_code}")
            return {"status": "error", "message": "API not healthy"}
    except Exception as e:
        print(f"[ERROR] Cannot reach API: {e}")
        return {"status": "error", "message": str(e)}

    print("[OK] API is healthy\n")

    # Run test cases
    results = []

    for test in TEST_CASES:
        print(f"\n{'─'*70}")
        print(f"Test {test['id']}: {test['description']}")
        print(f"Query: \"{test['query']}\"")
        print(f"{'─'*70}")

        try:
            # Send request
            start_time = time.time()
            response = requests.post(
                f"{api_url}/ask",
                json={
                    "query": test["query"],
                    "language": "vi",
                    "include_debug": True,  # Get reranking details
                },
                timeout=60,
            )
            latency = (time.time() - start_time) * 1000  # ms

            if response.status_code != 200:
                print(f"[FAIL] API error: {response.status_code}")
                results.append(
                    {
                        "test_id": test["id"],
                        "status": "API_ERROR",
                        "answer_correct": False,
                        "citation_correct": False,
                        "latency_ms": latency,
                    }
                )
                continue

            data = response.json()
            answer = data.get("answer", "")
            citations = data.get("citations", [])
            cited_pages = [c.get("page") for c in citations if c.get("page")]

            # Check answer correctness
            expected_answer = test["expected_answer_contains"]
            if isinstance(expected_answer, list):
                answer_correct = all(phrase in answer for phrase in expected_answer)
            else:
                answer_correct = expected_answer in answer

            # Check citation correctness
            expected_pages = test["expected_pages"]
            citation_correct = any(page in cited_pages for page in expected_pages)

            # Extract vision pages used (if available)
            vision_pages_used = []
            if "debug" in data and "vision_generation" in data["debug"]:
                vision_pages_used = data["debug"]["vision_generation"].get(
                    "pages_used", []
                )

            # Print results
            print(f"\nAnswer: {answer[:100]}...")
            print(f"  Expected contains: {expected_answer}")
            print(
                f"  Answer correct: {'✓' if answer_correct else '✗'} {answer_correct}"
            )

            print(f"\nCitations:")
            print(f"  Expected pages: {expected_pages}")
            print(f"  Cited pages: {cited_pages}")
            print(
                f"  Citation correct: {'✓' if citation_correct else '✗'} {citation_correct}"
            )

            if vision_pages_used:
                print(f"  Vision pages used: {vision_pages_used[:10]}...")
                expected_in_vision = any(
                    page in vision_pages_used for page in expected_pages
                )
                print(
                    f"  Expected page in vision: {'✓' if expected_in_vision else '✗'} {expected_in_vision}"
                )

            print(f"\nLatency: {latency:.0f}ms")

            # Overall test result
            passed = answer_correct and citation_correct
            print(f"\nResult: {'✓ PASS' if passed else '✗ FAIL'}")

            results.append(
                {
                    "test_id": test["id"],
                    "query": test["query"],
                    "status": "PASS" if passed else "FAIL",
                    "answer_correct": answer_correct,
                    "citation_correct": citation_correct,
                    "expected_pages": expected_pages,
                    "cited_pages": cited_pages,
                    "vision_pages_used": vision_pages_used[:10]
                    if vision_pages_used
                    else [],
                    "latency_ms": latency,
                }
            )

        except Exception as e:
            print(f"\n[ERROR] Test failed with exception: {e}")
            results.append(
                {
                    "test_id": test["id"],
                    "status": "EXCEPTION",
                    "error": str(e),
                    "answer_correct": False,
                    "citation_correct": False,
                }
            )

    # Summary
    print("\n\n" + "=" * 70)
    print("CITATION ACCURACY TEST SUMMARY")
    print("=" * 70)

    total = len(results)
    passed = sum(1 for r in results if r.get("status") == "PASS")
    answer_correct_count = sum(1 for r in results if r.get("answer_correct", False))
    citation_correct_count = sum(1 for r in results if r.get("citation_correct", False))

    answer_accuracy = (answer_correct_count / total * 100) if total > 0 else 0
    citation_accuracy = (citation_correct_count / total * 100) if total > 0 else 0
    overall_accuracy = (passed / total * 100) if total > 0 else 0

    print(f"\nOverall: {passed}/{total} tests passed ({overall_accuracy:.0f}%)")
    print(f"  Answer accuracy: {answer_correct_count}/{total} ({answer_accuracy:.0f}%)")
    print(
        f"  Citation accuracy: {citation_correct_count}/{total} ({citation_accuracy:.0f}%)"
    )

    # Average latency
    avg_latency = (
        sum(r.get("latency_ms", 0) for r in results) / total if total > 0 else 0
    )
    print(f"  Average latency: {avg_latency:.0f}ms")

    # Failed tests
    failed = [r for r in results if r.get("status") != "PASS"]
    if failed:
        print(f"\nFailed tests:")
        for r in failed:
            print(f"  - {r['test_id']}: {r.get('query', 'N/A')[:50]}...")
            if not r.get("answer_correct"):
                print(f"    → Answer incorrect")
            if not r.get("citation_correct"):
                print(
                    f"    → Citation incorrect (expected {r.get('expected_pages')}, got {r.get('cited_pages')})"
                )

    # Success criteria
    print("\n" + "-" * 70)
    print("SUCCESS CRITERIA")
    print("-" * 70)

    criteria = {
        "Citation accuracy ≥ 90%": citation_accuracy >= 90,
        "Answer accuracy ≥ 95%": answer_accuracy >= 95,
        "Overall pass rate ≥ 80%": overall_accuracy >= 80,
    }

    for criterion, met in criteria.items():
        status = "✓ PASS" if met else "✗ FAIL"
        print(f"  {status}  {criterion}")

    all_criteria_met = all(criteria.values())

    print("\n" + "=" * 70)
    if all_criteria_met:
        print("✓ ALL CRITERIA MET - WATERMARK IMPLEMENTATION SUCCESSFUL")
    else:
        print("✗ SOME CRITERIA NOT MET - REVIEW REQUIRED")
    print("=" * 70)

    return {
        "status": "success" if all_criteria_met else "partial",
        "total_tests": total,
        "passed": passed,
        "answer_accuracy": answer_accuracy,
        "citation_accuracy": citation_accuracy,
        "overall_accuracy": overall_accuracy,
        "avg_latency_ms": avg_latency,
        "results": results,
    }


if __name__ == "__main__":
    result = run_citation_test()

    # Exit code based on success criteria
    if result.get("status") == "success":
        sys.exit(0)
    else:
        sys.exit(1)
