"""
Comprehensive test after metadata and timing fixes
"""
import json

import requests

API_URL = "http://localhost:8000/ask"

payload = {
    "query": "NDH 2022 ở trang nào?",
    "max_context": 3,
    "language": "vi",
    "hyde": False,
    "execution_mode": "light_only",
}

print("=" * 80)
print("COMPREHENSIVE API TEST - After Metadata & Timing Fixes")
print("=" * 80)
print(f"\nQuery: {payload['query']}\n")

try:
    response = requests.post(API_URL, json=payload, timeout=120)
    response.raise_for_status()

    result = response.json()

    print(f"✅ API Response Status: {response.status_code}\n")

    # Test 1: Check citations have all required fields
    print("=" * 80)
    print("TEST 1: CITATION FIELDS")
    print("=" * 80)

    if result.get("citations"):
        first_citation = result["citations"][0]
        print("\n📚 First Citation:")
        print(json.dumps(first_citation, indent=2, ensure_ascii=False))

        # Verify required fields
        checks = {
            "doc_id": first_citation.get("doc_id") is not None,
            "page": first_citation.get("page") is not None,
            "confidence": first_citation.get("confidence") is not None,
            "pdf_path": first_citation.get("pdf_path") is not None,
            "metadata": first_citation.get("metadata") is not None,
        }

        print("\n✅ Field Checks:")
        for field, present in checks.items():
            status = "✅" if present else "❌"
            print(f"   {status} {field}: {present}")

        # Test 2: Check metadata has tags
        print("\n" + "=" * 80)
        print("TEST 2: METADATA TAGS")
        print("=" * 80)

        if first_citation.get("metadata"):
            tags = first_citation["metadata"].get("tags", [])
            print(f"\n✅ Tags found: {len(tags)} tags")
            if tags:
                print(f"   Tags (first 10): {tags[:10]}")

                # Check for NDH 2022
                has_ndh_2022 = any("NDH 2022" in str(tag) for tag in tags)
                if has_ndh_2022:
                    print(f"\n   ✅ Contains 'NDH 2022' tag!")
                else:
                    print(f"\n   ⚠️  'NDH 2022' not found in tags")
            else:
                print(f"   ⚠️  Tags array is empty")
        else:
            print(f"\n❌ Metadata is None")
    else:
        print("\n❌ No citations in response")

    # Test 3: Check timing breakdown
    print("\n" + "=" * 80)
    print("TEST 3: TIMING BREAKDOWN")
    print("=" * 80)

    meta = result.get("meta", {})
    breakdown = meta.get("breakdown", {})

    timing_checks = {
        "transform_ms": breakdown.get("transform_ms", 0),
        "retrieve_ms": breakdown.get("retrieve_ms", 0),
        "rerank_ms": breakdown.get("rerank_ms", 0),
        "generate_ms": breakdown.get("generate_ms", 0),
        "total_ms": meta.get("latency_ms", 0),
    }

    print(f"\n📊 Timing:")
    for metric, value in timing_checks.items():
        status = "✅" if value > 0 or metric == "rerank_ms" else "⚠️"
        print(f"   {status} {metric}: {value}ms")

    # Test 4: Check answer quality
    print("\n" + "=" * 80)
    print("TEST 4: ANSWER QUALITY")
    print("=" * 80)

    answer = result.get("answer", "")
    print(f"\n📝 Answer length: {len(answer)} chars")
    print(f"   Preview: {answer[:200]}...")

    # Check if answer mentions pages
    has_page_refs = any(
        word in answer.lower() for word in ["trang", "page", "110", "113", "116"]
    )
    print(
        f"\n   {'✅' if has_page_refs else '⚠️'} Answer mentions page numbers: {has_page_refs}"
    )

    # Final summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    all_passed = (
        checks.get("metadata", False)
        and timing_checks.get("transform_ms", 0) > 0
        and timing_checks.get("generate_ms", 0) > 0
        and len(answer) > 50
    )

    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
    else:
        print("\n⚠️  Some tests failed - check details above")

    print("=" * 80)

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback

    traceback.print_exc()
