"""Detailed API test to inspect full response structure"""
import json

import requests

API_URL = "http://localhost:8000/ask"

payload = {
    "query": "Tìm thông tin về NDH 2022",
    "max_context": 5,
    "language": "vi",
    "hyde": False,
    "execution_mode": "light_only",
}

print("=" * 100)
print("DETAILED API TEST - Inspecting Full Response")
print("=" * 100)

try:
    response = requests.post(API_URL, json=payload, timeout=120)
    response.raise_for_status()

    result = response.json()

    print(f"\n✅ Status: {response.status_code}\n")

    # Save full response for inspection
    with open("api_response_full.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("📁 Full response saved to: api_response_full.json\n")

    # Check response structure
    print("📊 Response Structure:")
    print(f"  - answer: {len(result.get('answer', ''))} chars")
    print(f"  - citations: {len(result.get('citations', []))} items")
    print(f"  - metadata: {list(result.get('metadata', {}).keys())}")
    print(f"  - trace_id: {result.get('trace_id', 'N/A')}")

    # Inspect citations in detail
    citations = result.get("citations", [])
    if citations:
        print(f"\n📚 Citations Detail:\n")
        for i, cit in enumerate(citations, 1):
            print(f"  Citation {i}:")
            print(f"    Keys: {list(cit.keys())}")
            print(f"    page_number: {cit.get('page_number')}")
            print(f"    doc_id: {cit.get('doc_id', 'N/A')[:60]}")
            print(f"    score: {cit.get('score')}")
            print(f"    text length: {len(cit.get('text', ''))}")

            # Check metadata
            meta = cit.get("metadata", {})
            if meta:
                print(f"    metadata keys: {list(meta.keys())}")
                print(f"    metadata.page: {meta.get('page')}")
                print(f"    metadata.tags: {meta.get('tags', [])[:5]}")
            else:
                print(f"    ⚠️ No metadata!")
            print()

    # Check if any citation has tags
    has_tags = any(cit.get("metadata", {}).get("tags") for cit in citations)

    if has_tags:
        print("✅ Some citations have tags!")
        # Find citations with NDH 2022
        matching_cits = [
            cit
            for cit in citations
            if any(
                "NDH 2022" in str(tag).upper()
                for tag in cit.get("metadata", {}).get("tags", [])
            )
        ]
        if matching_cits:
            print(f"✅ Found {len(matching_cits)} citation(s) with 'NDH 2022' tag!")
    else:
        print("⚠️ No citations have tags in metadata!")

    # Check timing metadata
    print(f"\n⏱️ Timing Information:")
    meta = result.get("metadata", {})
    for key in [
        "retrieval_time_ms",
        "rerank_time_ms",
        "generation_time_ms",
        "total_time_ms",
    ]:
        print(f"  {key}: {meta.get(key, 'N/A')}")

    print("\n" + "=" * 100)
    print("✅ TEST COMPLETE - Check api_response_full.json for details")
    print("=" * 100)

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback

    traceback.print_exc()
