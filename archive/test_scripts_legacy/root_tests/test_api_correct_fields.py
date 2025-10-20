"""
Test API với correct field names theo schema
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
print("API TEST - Checking Actual Response Structure")
print("=" * 80)
print(f"\nQuery: {payload['query']}\n")

try:
    response = requests.post(API_URL, json=payload, timeout=120)
    response.raise_for_status()

    result = response.json()

    print(f"✅ SUCCESS! Status: {response.status_code}\n")

    print("📚 RAW CITATIONS (first citation):")
    if result.get("citations"):
        first_citation = result["citations"][0]
        print(json.dumps(first_citation, indent=2, ensure_ascii=False))

        print("\n" + "=" * 80)
        print("FIELD ANALYSIS:")
        print("=" * 80)

        # Check what fields actually exist
        print(f"\n✅ Fields present in citation:")
        for key in first_citation.keys():
            print(f"   - {key}: {first_citation[key]}")

        print(f"\n❌ Fields NOT present:")
        missing = []
        if "page_number" not in first_citation:
            missing.append("page_number")
        if "score" not in first_citation:
            missing.append("score")
        if "metadata" not in first_citation:
            missing.append("metadata")
        if "tags" not in first_citation:
            missing.append("tags")

        for field in missing:
            print(f"   - {field}")

        print(f"\n" + "=" * 80)
        print("CORRECT FIELD NAMES:")
        print("=" * 80)
        print(f"Page: {first_citation.get('page', 'N/A')}")
        print(f"Confidence: {first_citation.get('confidence', 'N/A')}")
        print(
            f"PDF Path: {first_citation.get('pdf_path', 'N/A')[:80] if first_citation.get('pdf_path') else 'N/A'}..."
        )
        print(f"Bbox: {first_citation.get('bbox', 'N/A')}")

    print(f"\n" + "=" * 80)
    print("META TIMING:")
    print("=" * 80)
    meta = result.get("meta", {})
    breakdown = meta.get("breakdown", {})
    print(f"Transform: {breakdown.get('transform_ms', 0)}ms")
    print(f"Retrieve: {breakdown.get('retrieve_ms', 0)}ms")
    print(f"Rerank: {breakdown.get('rerank_ms', 0)}ms")
    print(f"Generate: {breakdown.get('generate_ms', 0)}ms")
    print(f"Total: {meta.get('latency_ms', 0)}ms")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback

    traceback.print_exc()
