"""
Test API with Gemini 768-dim embeddings
"""
import json

import requests

API_URL = "http://localhost:8000/ask"

# Test query about NDH 2022 tags
payload = {
    "query": "NDH 2022 ở trang nào?",
    "max_context": 3,
    "language": "vi",
    "hyde": False,
    "execution_mode": "light_only",
}

print("=" * 80)
print("API TEST - Gemini 768-dim Embeddings")
print("=" * 80)
print(f"\nQuery: {payload['query']}")
print(f"Execution mode: {payload['execution_mode']}")
print(f"Timeout: 120 seconds")
print("\n🔬 Testing with Gemini 768-dimensional embeddings...")
print("\nSending request...")

try:
    response = requests.post(API_URL, json=payload, timeout=120)
    response.raise_for_status()

    result = response.json()

    print(f"\n✅ SUCCESS! Status: {response.status_code}")
    print(f"\n📝 Answer Preview:")
    print(result.get("answer", "")[:300])

    print(f"\n📚 Citations ({len(result.get('citations', []))}):")
    for i, citation in enumerate(result.get("citations", [])[:3], 1):
        print(f"\n  {i}. Page: {citation.get('page_number')}")
        print(f"     Doc: {citation.get('doc_id', '')[:60]}")
        print(f"     Score: {citation.get('score', 0):.4f}")

        # Show tags if available
        metadata = citation.get("metadata", {})
        tags = metadata.get("tags", [])
        if tags:
            print(f"     Tags (first 8): {tags[:8]}")
            # Check if NDH 2022 is in tags
            if any("NDH 2022" in str(tag) for tag in tags):
                print(f"     ✅ Contains 'NDH 2022' tag!")
        else:
            print(f"     Tags: (none in metadata)")

    print(f"\n⏱️ Timing:")
    metadata_timing = result.get("metadata", {})
    print(f"  Retrieval: {metadata_timing.get('retrieval_time_ms', 0):.0f}ms")
    print(f"  Rerank: {metadata_timing.get('rerank_time_ms', 0):.0f}ms")
    print(f"  Generation: {metadata_timing.get('generation_time_ms', 0):.0f}ms")
    print(f"  Total: {metadata_timing.get('total_time_ms', 0):.0f}ms")

    print("\n" + "=" * 80)
    print("🎉 API TEST WITH GEMINI EMBEDDINGS PASSED!")
    print("=" * 80)

except requests.exceptions.Timeout:
    print("\n❌ Request timeout after 120s")
    print("   Check API logs for details")

except requests.exceptions.RequestException as e:
    print(f"\n❌ Request failed: {e}")
    if hasattr(e, "response") and e.response:
        print(f"Response text: {e.response.text[:500]}")

except json.JSONDecodeError as e:
    print(f"\n❌ JSON decode failed: {e}")
    print(f"Response: {response.text[:500]}")

except Exception as e:
    print(f"\n❌ Unexpected error: {e}")
    import traceback

    traceback.print_exc()
