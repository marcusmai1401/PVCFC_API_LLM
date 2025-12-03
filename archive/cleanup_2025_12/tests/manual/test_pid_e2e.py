"""
End-to-end test of P&ID query through full pipeline
"""
import sys

sys.path.insert(0, ".")

import json

import requests

API_URL = "http://localhost:8000"

print("=" * 80)
print("P&ID END-TO-END TEST")
print("=" * 80)

# Test 1: Check API health
print("\n[STEP 1] Checking API health...")
try:
    response = requests.get(f"{API_URL}/healthz", timeout=3)
    if response.ok:
        print("  Status: API is healthy")
    else:
        print("  ERROR: API not healthy")
        sys.exit(1)
except Exception as e:
    print(f"  ERROR: Cannot connect to API - {e}")
    print("  Please start the API server first:")
    print("    python -m uvicorn app.main:app --reload")
    sys.exit(1)

# Test 2: Query with PID tag
print("\n[STEP 2] Sending P&ID query: '04 PI 2504'")
print("-" * 80)

payload = {
    "query": "04 PI 2504",
    "query_type": "pid",
    "language": "vi",
    "max_context": 8,
    "hyde": False,
    "execution_mode": "light_only",  # Faster for testing
}

try:
    response = requests.post(f"{API_URL}/ask", json=payload, timeout=30)

    if response.ok:
        result = response.json()

        print(f"  Status: SUCCESS (HTTP {response.status_code})")
        print(f"  Answer length: {len(result.get('answer', ''))}")
        print(f"  Citations count: {len(result.get('citations', []))}")
        print(f"  Confidence: {result.get('confidence', 0):.2f}")

        # Check citations
        citations = result.get("citations", [])
        if citations:
            print(f"\n  Citations detail:")
            for i, cit in enumerate(citations[:5], 1):
                bbox = cit.get("bbox")
                bbox_str = f"bbox: YES" if bbox else "bbox: NO"
                metadata = cit.get("metadata", {})
                tags = metadata.get("tags", [])
                print(f"    {i}. Doc: {cit.get('doc_id', 'N/A')[:50]}")
                print(f"       Page: {cit.get('page')}, {bbox_str}")
                if tags:
                    print(f"       Tags in metadata: {tags[:3]}")
        else:
            print(f"\n  WARNING: No citations returned")

        # Check meta
        meta = result.get("meta", {})
        print(f"\n  Timing:")
        print(f"    Total: {meta.get('latency_ms')}ms")
        breakdown = meta.get("breakdown", {})
        if breakdown:
            print(f"    Retrieve: {breakdown.get('retrieve_ms')}ms")
            print(f"    Generate: {breakdown.get('generate_ms')}ms")

        print(f"\n  Retriever used: {meta.get('query_type', 'N/A')}")

        # Check retrieval details
        retrieval_details = result.get("retrieval_details")
        if retrieval_details:
            print(f"\n  Retrieval details available: YES")
            print(f"    Retriever type: {retrieval_details.get('retriever_type')}")
            print(f"    Total retrieved: {retrieval_details.get('total_retrieved')}")

    else:
        print(f"  Status: FAIL (HTTP {response.status_code})")
        print(f"  Error: {response.text[:500]}")

except Exception as e:
    print(f"  Status: FAIL")
    print(f"  ERROR: {e}")
    import traceback

    traceback.print_exc()

# Test 3: Query with location intent
print("\n[STEP 3] Sending location query: 'tag 04 PI 2504 o dau?'")
print("-" * 80)

payload2 = {
    "query": "tag 04 PI 2504 o dau?",
    "query_type": "pid",
    "language": "vi",
    "max_context": 8,
    "hyde": False,
    "execution_mode": "light_only",
}

try:
    response = requests.post(f"{API_URL}/ask", json=payload2, timeout=30)

    if response.ok:
        result = response.json()
        print(f"  Status: SUCCESS")
        print(f"  Answer preview: {result.get('answer', '')[:200]}...")
        print(f"  Citations: {len(result.get('citations', []))}")

        # Check if tag location was detected
        meta = result.get("meta", {})
        if meta.get("tag_location_query"):
            print(f"  Tag location query: DETECTED")
            print(f"  Tag name: {meta.get('tag_name')}")
    else:
        print(f"  Status: FAIL (HTTP {response.status_code})")

except Exception as e:
    print(f"  Status: FAIL - {e}")

print("\n" + "=" * 80)
print("E2E TEST COMPLETE")
print("=" * 80)
