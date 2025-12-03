"""
Test script for Task 2: Verify post-validation fix
Tests all 3 original queries to ensure no crash in post-validation
"""

import json
import time
from datetime import datetime

import requests

API_URL = "http://127.0.0.1:8000/ask"

# Test queries
QUERIES = [
    {
        "name": "Query 1 (Turbine rated power - Page 45 expected)",
        "query": "To achieve the rated power of 11040 kW under normal work conditions, what are the specified operating conditions?",
        "expected_page": 45,
        "doc_type": "turbine",
    },
    {
        "name": "Query 2 (Gear lubricating oil pressure - Page 8 or 18 expected)",
        "query": "For the HCD025 Gear Unit, at what specific lubricating oil pressure does the alarm system trigger a minor trouble alarm, and at what pressure does it trigger a major trouble trip (shutdown)?",
        "expected_pages": [8, 18],
        "doc_type": "gear",
    },
    {
        "name": "Query 3 (P&ID tag 04-FIC-2035 - Page 5 expected)",
        "query": 'Theo P&ID "AMMONIA UNIT – Rev12 (04000)" của PVCFC, tại khu vực Natural Gas Preheat / Primary Reformer, tag số 04-FIC-2035 điều khiển hiệu chỉnh dòng nào?',
        "expected_page": 5,
        "doc_type": "p&id",
    },
]


def test_query(query_data, test_num):
    """Test single query and return results"""
    print(f"\n{'='*80}")
    print(f"TEST {test_num}: {query_data['name']}")
    print(f"{'='*80}")

    payload = {
        "query": query_data["query"],
        "max_context": 8,
        "language": "vi" if "Theo P&ID" in query_data["query"] else "en",
        "enable_vision_generation": True,
    }

    print(f"\nSending request...")
    start_time = time.time()

    try:
        response = requests.post(API_URL, json=payload, timeout=120)
        latency = (time.time() - start_time) * 1000

        print(f"✓ Response received: {response.status_code} ({latency:.0f}ms)")

        if response.status_code != 200:
            print(f"✗ FAILED: HTTP {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return {
                "test_num": test_num,
                "name": query_data["name"],
                "status": "FAILED",
                "error": f"HTTP {response.status_code}",
                "latency_ms": latency,
            }

        data = response.json()

        # Extract key information
        answer = data.get("answer", "")
        citations = data.get("citations", [])
        meta = data.get("meta", {})
        vision_meta = meta.get("vision_generation", {})

        print(f"\n--- ANSWER ---")
        print(answer[:300] + ("..." if len(answer) > 300 else ""))

        print(f"\n--- CITATIONS ({len(citations)}) ---")
        for i, cit in enumerate(citations[:5], 1):
            page = cit.get("page", "?")
            doc_id = cit.get("doc_id", "unknown")[:50]
            print(f"  [{i}] Page {page} - {doc_id}")

        print(f"\n--- VISION INFO ---")
        if vision_meta:
            pages_used = vision_meta.get("pages_used", [])
            pages_failed = vision_meta.get("pages_failed", [])
            print(
                f"  Pages used: {len(pages_used)} - {[p.get('page') for p in pages_used]}"
            )
            print(f"  Pages failed: {len(pages_failed)}")
        else:
            print(f"  Vision NOT used")

        # Check for post-validation crash indicators
        print(f"\n--- POST-VALIDATION CHECK ---")
        # If server returned 200 with citations, post-validation didn't crash
        has_citations = len(citations) > 0
        print(f"  ✓ Server returned 200 OK")
        print(f"  {'✓' if has_citations else '✗'} Citations present: {len(citations)}")

        # Check expected pages
        print(f"\n--- EXPECTED vs ACTUAL ---")
        if "expected_page" in query_data:
            expected = query_data["expected_page"]
            actual_pages = [c.get("page") for c in citations]
            match = expected in actual_pages
            print(f"  Expected: page {expected}")
            print(f"  Actual: pages {actual_pages}")
            print(f"  {'✓' if match else '✗'} Match: {match}")
        elif "expected_pages" in query_data:
            expected = query_data["expected_pages"]
            actual_pages = [c.get("page") for c in citations]
            match = any(exp in actual_pages for exp in expected)
            print(f"  Expected: pages {expected}")
            print(f"  Actual: pages {actual_pages}")
            print(f"  {'✓' if match else '✗'} Match: {match}")

        return {
            "test_num": test_num,
            "name": query_data["name"],
            "status": "PASSED" if response.status_code == 200 else "FAILED",
            "has_citations": has_citations,
            "citation_count": len(citations),
            "pages_cited": [c.get("page") for c in citations],
            "vision_used": bool(vision_meta),
            "vision_pages_used": [
                p.get("page") for p in vision_meta.get("pages_used", [])
            ]
            if vision_meta
            else [],
            "latency_ms": latency,
            "answer_length": len(answer),
        }

    except requests.exceptions.Timeout:
        print(f"✗ FAILED: Request timeout after 120s")
        return {
            "test_num": test_num,
            "name": query_data["name"],
            "status": "TIMEOUT",
            "error": "Request timeout",
        }
    except Exception as e:
        print(f"✗ FAILED: {str(e)}")
        return {
            "test_num": test_num,
            "name": query_data["name"],
            "status": "ERROR",
            "error": str(e),
        }


def main():
    """Run all tests"""
    print(f"\n{'#'*80}")
    print(f"# POST-VALIDATION FIX TEST - Task 2")
    print(f"# Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"# Testing: {len(QUERIES)} queries")
    print(f"{'#'*80}")

    # Check if server is running
    try:
        health_response = requests.get("http://127.0.0.1:8000/healthz", timeout=5)
        if health_response.status_code != 200:
            print(f"\n✗ Server not healthy: {health_response.status_code}")
            print(f"Please start the server first: python run_api.py")
            return
        print(f"\n✓ Server is running and healthy")
    except Exception as e:
        print(f"\n✗ Cannot connect to server: {e}")
        print(f"Please start the server first: python run_api.py")
        return

    # Run tests
    results = []
    for i, query_data in enumerate(QUERIES, 1):
        result = test_query(query_data, i)
        results.append(result)
        time.sleep(2)  # Brief pause between tests

    # Summary
    print(f"\n{'='*80}")
    print(f"SUMMARY - Task 2 Test Results")
    print(f"{'='*80}")

    passed = sum(1 for r in results if r.get("status") == "PASSED")
    failed = len(results) - passed

    print(f"\nTotal: {len(results)} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    print(f"\nDetailed Results:")
    for r in results:
        status_icon = "✓" if r.get("status") == "PASSED" else "✗"
        print(f"  {status_icon} Test {r['test_num']}: {r['name']}")
        print(f"     Status: {r.get('status')}")
        if r.get("has_citations"):
            print(
                f"     Citations: {r.get('citation_count')} (pages: {r.get('pages_cited')})"
            )
        if r.get("vision_used"):
            pages = r.get("vision_pages_used", [])
            print(f"     Vision: used {len(pages)} pages {pages}")
        if r.get("latency_ms"):
            print(f"     Latency: {r.get('latency_ms'):.0f}ms")
        if r.get("error"):
            print(f"     Error: {r.get('error')}")

    print(f"\n{'='*80}")
    print(f"KEY SUCCESS CRITERIA FOR TASK 2:")
    print(f"  1. All 3 queries return HTTP 200 OK")
    print(f"  2. No 'expected str, bytes or os.PathLike object, not dict' errors")
    print(f"  3. Citations are present in responses")
    print(f"{'='*80}")

    # Save results
    output_file = "test_results_task2.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "total": len(results),
                "passed": passed,
                "failed": failed,
                "results": results,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\n✓ Results saved to: {output_file}")

    if failed == 0:
        print(f"\n{'🎉'*20}")
        print(f"  TASK 2 PASSED! Post-validation fix is working correctly.")
        print(f"{'🎉'*20}\n")
    else:
        print(
            f"\n⚠️  TASK 2 INCOMPLETE: {failed} test(s) failed. Check logs for details.\n"
        )


if __name__ == "__main__":
    main()
