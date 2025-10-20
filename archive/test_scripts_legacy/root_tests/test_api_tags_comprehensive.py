"""
Comprehensive API Test for Tag-based Retrieval
Tests P&ID tag queries with spaces to verify:
1. Tags with spaces are preserved and searchable
2. Correct pages are returned in citations
3. Multiple tag formats work correctly
"""
import json
from typing import Dict, List

import requests

API_URL = "http://localhost:8000/ask"


def test_tag_query(query: str, expected_tags: List[str] = None, test_name: str = ""):
    """Test a single tag query and analyze results"""
    print("=" * 100)
    print(f"TEST: {test_name if test_name else query}")
    print("=" * 100)
    print(f"Query: {query}")
    if expected_tags:
        print(f"Expected tags: {expected_tags}")
    print()

    # Make API request
    payload = {
        "query": query,
        "max_context": 5,
        "language": "vi",
        "hyde": False,
        "execution_mode": "production",
    }

    try:
        response = requests.post(API_URL, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()

        # Analyze response
        print(f"✅ Status: {response.status_code}")
        print(f"Answer preview: {result.get('answer', '')[:200]}...")
        print()

        # Check citations
        citations = result.get("citations", [])
        print(f"📚 Citations: {len(citations)} results")

        for i, citation in enumerate(citations[:5], 1):
            print(f"\n  Citation {i}:")
            print(f"    - Doc: {citation.get('doc_id', 'N/A')[:60]}")
            print(f"    - Page: {citation.get('page_number', 'N/A')}")
            print(f"    - Score: {citation.get('score', 0):.4f}")

            # Check metadata for tags
            metadata = citation.get("metadata", {})
            tags = metadata.get("tags", [])
            if tags:
                print(f"    - Tags (first 10): {tags[:10]}")

                # Verify expected tags if provided
                if expected_tags:
                    found_tags = [tag for tag in expected_tags if tag in tags]
                    if found_tags:
                        print(f"    ✅ Found expected tags: {found_tags}")
                    else:
                        print(f"    ⚠️  Expected tags not found in this result")
            else:
                print(f"    - Tags: None")

            # Show text preview
            text = citation.get("text", "")
            if len(text) > 150:
                text = text[:150] + "..."
            print(f"    - Text preview: {text[:100]}")

        # Check metadata
        print(f"\n📊 Metadata:")
        print(
            f"  - Execution mode: {result.get('metadata', {}).get('execution_mode', 'N/A')}"
        )
        print(
            f"  - Retrieval time: {result.get('metadata', {}).get('retrieval_time_ms', 0):.0f}ms"
        )
        print(
            f"  - Total time: {result.get('metadata', {}).get('total_time_ms', 0):.0f}ms"
        )

        return result

    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode failed: {e}")
        print(f"Response text: {response.text[:500]}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None


def main():
    print("\n" + "🎯" * 50)
    print("COMPREHENSIVE TAG RETRIEVAL API TEST")
    print("🎯" * 50 + "\n")

    # Test cases with various tag formats
    test_cases = [
        {
            "query": "Tìm thông tin về thiết bị NDH 2022",
            "expected_tags": ["NDH 2022", "H 2022"],
            "test_name": "Tag with spaces: NDH 2022",
        },
        {
            "query": "Valve 04 ZLH 2055A ở trang nào?",
            "expected_tags": ["04 ZLH 2055A", "ZLH 2055A"],
            "test_name": "Full tag with spaces: 04 ZLH 2055A",
        },
        {
            "query": "NG 04109 thông tin gì?",
            "expected_tags": ["NG 04109"],
            "test_name": "Tag with space: NG 04109",
        },
        {
            "query": "Tìm H 2024 và H 2025",
            "expected_tags": ["H 2024", "H 2025"],
            "test_name": "Multiple tags with spaces",
        },
        {
            "query": "Equipment tag NDH 2024 location",
            "expected_tags": ["NDH 2024"],
            "test_name": "English query with tag spaces",
        },
    ]

    results = []
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*100}")
        print(f"TEST CASE {i}/{len(test_cases)}")
        result = test_tag_query(
            query=test_case["query"],
            expected_tags=test_case.get("expected_tags"),
            test_name=test_case.get("test_name"),
        )
        results.append(
            {
                "test_name": test_case.get("test_name"),
                "success": result is not None,
                "num_citations": len(result.get("citations", [])) if result else 0,
            }
        )
        print()

    # Summary
    print("\n" + "📊" * 50)
    print("TEST SUMMARY")
    print("📊" * 50 + "\n")

    successful_tests = sum(1 for r in results if r["success"])
    total_tests = len(results)

    print(f"Total tests: {total_tests}")
    print(f"Successful: {successful_tests}")
    print(f"Failed: {total_tests - successful_tests}")
    print()

    for i, result in enumerate(results, 1):
        status = "✅" if result["success"] else "❌"
        print(f"{status} Test {i}: {result['test_name']}")
        if result["success"]:
            print(f"   Citations: {result['num_citations']}")

    print("\n" + "=" * 100)
    if successful_tests == total_tests:
        print("🎉 ALL TESTS PASSED! Tags with spaces are working correctly!")
    else:
        print(f"⚠️  {total_tests - successful_tests} test(s) failed")
    print("=" * 100 + "\n")


if __name__ == "__main__":
    main()
