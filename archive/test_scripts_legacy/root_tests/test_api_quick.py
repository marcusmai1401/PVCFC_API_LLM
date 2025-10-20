"""Quick API test with longer timeout and light execution mode"""
import json

import requests

API_URL = "http://localhost:8000/ask"

# Simple test query
payload = {
    "query": "NDH 2022 ở trang nào?",
    "max_context": 3,
    "language": "vi",
    "hyde": False,
    "execution_mode": "light_only",  # Use light model to avoid heavy model cold start
}

print("=" * 80)
print("QUICK API TEST - Light Mode with 120s timeout")
print("=" * 80)
print(f"\nQuery: {payload['query']}")
print(f"Execution mode: {payload['execution_mode']}")
print(f"Timeout: 120 seconds")
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
        tags = citation.get("metadata", {}).get("tags", [])
        if tags:
            print(f"     Tags (first 8): {tags[:8]}")
            # Check if NDH 2022 is in tags
            if any("NDH 2022" in tag for tag in tags):
                print(f"     ✅ Contains 'NDH 2022' tag!")

    print(f"\n⏱️ Timing:")
    metadata = result.get("metadata", {})
    print(f"  Retrieval: {metadata.get('retrieval_time_ms', 0):.0f}ms")
    print(f"  Rerank: {metadata.get('rerank_time_ms', 0):.0f}ms")
    print(f"  Generation: {metadata.get('generation_time_ms', 0):.0f}ms")
    print(f"  Total: {metadata.get('total_time_ms', 0):.0f}ms")

    print("\n" + "=" * 80)
    print("🎉 API TEST PASSED!")
    print("=" * 80)

except requests.exceptions.Timeout:
    print("\n❌ Request timeout after 120s")
    print("   Possible causes:")
    print("   - LLM model still loading")
    print("   - Heavy processing in pipeline")
    print("   - Check API logs for details")

except requests.exceptions.RequestException as e:
    print(f"\n❌ Request failed: {e}")

except json.JSONDecodeError as e:
    print(f"\n❌ JSON decode failed: {e}")
    print(f"Response: {response.text[:500]}")

except Exception as e:
    print(f"\n❌ Unexpected error: {e}")
    import traceback

    traceback.print_exc()
