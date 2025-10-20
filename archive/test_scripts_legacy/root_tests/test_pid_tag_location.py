#!/usr/bin/env python
"""
Test P&ID Tag Location Queries

Tests if the RAG system correctly identifies the page numbers where
specific P&ID tags are located in documents.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

# API Configuration
API_BASE_URL = "http://localhost:8000"
API_ENDPOINT = f"{API_BASE_URL}/ask/"

# Test cases: (tag_name, expected_page, total_pages)
TEST_CASES = [
    {
        "tag": "04 ZLH 2038A",
        "expected_page": 13,
        "total_pages": 117,
        "query": "Tag 04 ZLH 2038A nằm ở trang nào của file P&ID?",
    },
    {
        "tag": "04 LAHH 2091",
        "expected_page": 23,
        "total_pages": 117,
        "query": "Cho tôi biết tag 04 LAHH 2091 xuất hiện ở trang nào?",
    },
    {
        "tag": "04 TI 5027",
        "expected_page": None,  # Unknown
        "total_pages": 117,
        "query": "Tag 04 TI 5027 có trong file P&ID không? Nếu có thì ở trang bao nhiêu?",
    },
]


def print_separator(title: str = "", char: str = "="):
    """Print a separator line"""
    if title:
        print(f"\n{char*80}")
        print(f"{title}")
        print(f"{char*80}\n")
    else:
        print(f"{char*80}\n")


def extract_pages_from_response(response_data: Dict[str, Any]) -> List[int]:
    """Extract page numbers from API response"""
    pages = []

    # Check citations
    if "citations" in response_data:
        for citation in response_data["citations"]:
            page = citation.get("page")
            if page is not None and page > 0:
                pages.append(page)

    # Check contexts (alternative structure)
    if "contexts" in response_data:
        for context in response_data["contexts"]:
            page = context.get("page")
            if page is not None and page > 0:
                pages.append(page)

    # Check chunks (alternative structure)
    if "chunks" in response_data:
        for chunk in response_data["chunks"]:
            if isinstance(chunk, dict):
                page = chunk.get("page") or chunk.get("metadata", {}).get("page")
                if page is not None and page > 0:
                    pages.append(page)

    return sorted(list(set(pages)))  # Remove duplicates and sort


def test_tag_query(test_case: Dict[str, Any], test_num: int) -> Dict[str, Any]:
    """
    Test a single tag location query

    Returns:
        Dictionary with test results
    """
    tag = test_case["tag"]
    expected_page = test_case["expected_page"]
    query = test_case["query"]

    print_separator(f"TEST {test_num}: {tag}")

    print(f"📋 Tag:           {tag}")
    print(f"❓ Query:         {query}")
    if expected_page:
        print(f"✅ Expected Page: {expected_page}/{test_case['total_pages']}")
    else:
        print(f"❓ Expected Page: Unknown")
    print()

    # Prepare request
    payload = {
        "query": query,
        "hyde": True,
        "max_context": 8,
        "language": "vi",
        "filters": {"doc_category": ["pid"]},  # Filter for P&ID documents
    }

    print("📤 Sending request to API...")
    print(f"   URL: {API_ENDPOINT}")
    print(f"   Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    print()

    try:
        # Make API request
        response = requests.post(
            API_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        print(f"📥 Response Status: {response.status_code}")

        if response.status_code != 200:
            print(f"❌ API Error: {response.text}")
            return {
                "tag": tag,
                "success": False,
                "error": f"HTTP {response.status_code}",
                "expected_page": expected_page,
                "found_pages": [],
            }

        response_data = response.json()

        # Debug: Print full response structure
        print("\n🔍 DEBUG: Response structure:")
        print(f"   Keys: {list(response_data.keys())}")
        print()

        # Extract answer
        answer = response_data.get("answer", "")
        print(f"💬 LLM Answer:\n{answer}\n")

        # Extract pages from citations/contexts
        found_pages = extract_pages_from_response(response_data)

        print(f"📄 Pages found in response: {found_pages}")

        # Debug: Print citations detail
        if "citations" in response_data:
            print("\n🔍 DEBUG: Citations detail:")
            for i, citation in enumerate(response_data["citations"], 1):
                print(
                    f"   {i}. Page: {citation.get('page')}, "
                    f"Doc: {citation.get('doc_id', 'N/A')[:50]}, "
                    f"Confidence: {citation.get('confidence', 'N/A')}"
                )
                print(f"       Full citation: {citation}")

        if "contexts" in response_data:
            print("\n🔍 DEBUG: Contexts detail:")
            for i, ctx in enumerate(response_data["contexts"], 1):
                print(
                    f"   {i}. Page: {ctx.get('page')}, "
                    f"Text: {ctx.get('text', '')[:80]}..."
                )

        print()

        # Validate result
        result = {
            "tag": tag,
            "query": query,
            "success": True,
            "expected_page": expected_page,
            "found_pages": found_pages,
            "answer": answer,
            "response_time_ms": response.elapsed.total_seconds() * 1000,
        }

        # Check correctness
        if expected_page:
            if expected_page in found_pages:
                result["verdict"] = "✅ CORRECT"
                print(f"✅ SUCCESS: Expected page {expected_page} found in results!")
            else:
                result["verdict"] = "❌ INCORRECT"
                print(
                    f"❌ FAILED: Expected page {expected_page} NOT in results {found_pages}"
                )

                # Check if it's close (within ±2 pages)
                close_pages = [p for p in found_pages if abs(p - expected_page) <= 2]
                if close_pages:
                    result["verdict"] = "⚠️  CLOSE"
                    print(f"⚠️  But found close pages: {close_pages}")
        else:
            if found_pages:
                result["verdict"] = "ℹ️  FOUND"
                print(f"ℹ️  Found pages: {found_pages} (expected unknown)")
            else:
                result["verdict"] = "⚠️  NOT FOUND"
                print(f"⚠️  No pages found")

        return result

    except requests.exceptions.Timeout:
        print("❌ Request timeout!")
        return {
            "tag": tag,
            "success": False,
            "error": "Timeout",
            "expected_page": expected_page,
            "found_pages": [],
        }
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return {
            "tag": tag,
            "success": False,
            "error": str(e),
            "expected_page": expected_page,
            "found_pages": [],
        }


def main():
    """Run all tests"""
    print_separator("P&ID TAG LOCATION TEST SUITE", "=")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API Endpoint: {API_ENDPOINT}")
    print(f"Total test cases: {len(TEST_CASES)}")

    # Check API health
    print("\n🔍 Checking API health...")
    try:
        health_response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if health_response.status_code == 200:
            print("✅ API is healthy")
        else:
            print(f"⚠️  API health check returned: {health_response.status_code}")
    except Exception as e:
        print(f"❌ API health check failed: {e}")
        print("   Continuing anyway...")

    # Run tests
    results = []
    for i, test_case in enumerate(TEST_CASES, 1):
        result = test_tag_query(test_case, i)
        results.append(result)

        if i < len(TEST_CASES):
            print("\n" + "=" * 80)
            print("Waiting 2 seconds before next test...")
            print("=" * 80)
            import time

            time.sleep(2)

    # Summary
    print_separator("TEST SUMMARY", "=")

    total = len(results)
    successful_api = sum(1 for r in results if r["success"])
    correct = sum(1 for r in results if r.get("verdict") == "✅ CORRECT")
    close = sum(1 for r in results if r.get("verdict") == "⚠️  CLOSE")
    incorrect = sum(1 for r in results if r.get("verdict") == "❌ INCORRECT")

    print(f"Total tests:           {total}")
    print(f"API successful:        {successful_api}/{total}")
    print(f"Correct page results:  {correct}/{total}")
    print(f"Close page results:    {close}/{total}")
    print(f"Incorrect results:     {incorrect}/{total}")
    print()

    # Detailed results table
    print("DETAILED RESULTS:")
    print("-" * 80)
    print(f"{'Tag':<20} {'Expected':<10} {'Found':<20} {'Verdict':<15}")
    print("-" * 80)

    for r in results:
        expected = str(r["expected_page"]) if r["expected_page"] else "Unknown"
        found = str(r["found_pages"]) if r["found_pages"] else "[]"
        verdict = r.get("verdict", "❌ ERROR")
        print(f"{r['tag']:<20} {expected:<10} {found:<20} {verdict:<15}")

    print("-" * 80)

    # Performance
    if any("response_time_ms" in r for r in results):
        avg_time = sum(r.get("response_time_ms", 0) for r in results) / total
        print(f"\nAverage response time: {avg_time:.0f}ms")

    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print_separator()

    # Return exit code
    if correct == sum(1 for tc in TEST_CASES if tc["expected_page"] is not None):
        print("🎉 ALL TESTS WITH EXPECTED PAGES PASSED!")
        return 0
    else:
        print("⚠️  SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    import sys

    exit_code = main()
    sys.exit(exit_code)
