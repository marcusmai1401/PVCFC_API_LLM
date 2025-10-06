"""
Quick diagnostic test script for 3 original queries
Runs queries and displays diagnostic log output
"""
import json
import sys

import requests

API_URL = "http://127.0.0.1:8000/ask"

# 3 original test queries
QUERIES = [
    {
        "name": "Query 1 - P&ID Vietnamese",
        "payload": {
            "query": 'Theo P&ID "AMMONIA UNIT – Rev12 (04000)" của PVCFC, tại khu vực Natural Gas Preheat / Primary Reformer, tag 04-FIC-2035 nằm ở trang nào?',
            "max_context": 20,
            "language": "vi",
            "hyde": True,
            "execution_mode": "production",
            "confidence_mode": "calibrated",
            "enable_vision_generation": True,
        },
        "expected_page": 5,
    },
    {
        "name": "Query 2 - P&ID English (translated)",
        "payload": {
            "query": 'According to the P&ID "AMMONIA UNIT – Rev12 (04000)" of PVCFC, in the Natural Gas Preheat / Primary Reformer section, on which page is the tag 04-FIC-2035 located?',
            "max_context": 20,
            "language": "en",
            "hyde": True,
            "execution_mode": "production",
            "confidence_mode": "calibrated",
            "enable_vision_generation": True,
        },
        "expected_page": 5,
    },
    {
        "name": "Query 3 - Gear Unit Temperature",
        "payload": {
            "query": "According to the maintenance and inspection guidelines for the HCD025 Gear Unit, what is the maximum allowable temperature for the embedded temperature sensor (TE)?",
            "max_context": 20,
            "language": "en",
            "hyde": True,
            "execution_mode": "production",
            "confidence_mode": "calibrated",
            "enable_vision_generation": True,
        },
        "expected_page": None,  # Should have citations but page unknown
    },
]


def run_query(query_info):
    """Run a single query and display results"""
    print("\n" + "=" * 80)
    print(f"TEST: {query_info['name']}")
    print("=" * 80)
    print(f"Query: {query_info['payload']['query'][:100]}...")
    print(f"Expected page: {query_info['expected_page']}")

    try:
        response = requests.post(API_URL, json=query_info["payload"], timeout=60)

        if response.status_code != 200:
            print(f"❌ API Error: {response.status_code}")
            print(response.text[:500])
            return False

        data = response.json()

        # Extract key info
        answer = data.get("answer", "")
        citations = data.get("citations", [])
        confidence = data.get("confidence", 0)
        meta = data.get("meta", {})
        vision_meta = meta.get("vision_generation", {})

        print(f"\n✓ Response received (confidence: {confidence:.2f})")
        print(f"Answer length: {len(answer)} chars")
        print(f"Citations count: {len(citations)}")

        if vision_meta:
            pages_used = vision_meta.get("pages_used", [])
            print(f"Vision pages used: {len(pages_used)}")
            if pages_used:
                page_nums = [p.get("page") for p in pages_used[:5]]
                print(f"  Pages: {page_nums}")

        if citations:
            print("\nCitations:")
            for i, cit in enumerate(citations[:3], 1):
                print(
                    f"  [{i}] Page {cit.get('page')}, Doc: {cit.get('doc_id', '')[:50]}"
                )
        else:
            print("⚠ No citations returned!")

        # Check expectation
        if query_info["expected_page"]:
            found_expected = any(
                cit.get("page") == query_info["expected_page"] for cit in citations
            )
            if found_expected:
                print(
                    f"✓ Expected page {query_info['expected_page']} found in citations"
                )
            else:
                print(f"✗ Expected page {query_info['expected_page']} NOT in citations")

        return True

    except requests.exceptions.Timeout:
        print("❌ Request timeout (60s)")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all queries"""
    print("DIAGNOSTIC TEST - 3 Original Queries")
    print("NOTE: Check server logs for [DIAGNOSTIC] messages")
    print("\nWaiting for server...")

    # Check server health
    try:
        health = requests.get("http://127.0.0.1:8000/healthz", timeout=5)
        if health.status_code != 200:
            print("❌ Server not healthy")
            sys.exit(1)
        print("✓ Server is ready\n")
    except:
        print("❌ Server not responding")
        sys.exit(1)

    # Run all queries
    results = []
    for query_info in QUERIES:
        success = run_query(query_info)
        results.append((query_info["name"], success))
        print("\n" + "-" * 80)

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    for name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {name}")

    print("\n⚠ IMPORTANT: Review server logs for [DIAGNOSTIC] messages!")
    print("   Look for:")
    print("   - Retrieved docs metadata (pdf_path, page, page_start, page_end)")
    print("   - Page center calculation logic")
    print("   - Vision reorder scoring")
    print("   - Rerank input/output counts")


if __name__ == "__main__":
    main()
