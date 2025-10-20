import json
import time

import requests

print("Waiting for server restart (wait 10 seconds)...")
time.sleep(10)

# Test query
response = requests.post(
    "http://localhost:8000/ask",
    json={
        "query": "Tìm cho tôi thiết bị 04 PU 2049 nằm ở đâu trong bản vẽ P&ID",
        "lang": "vi",
    },
    timeout=120,
)

print("Status:", response.status_code)
print("\n=== ANSWER ===")
data = response.json()
print(data.get("answer", ""))

print("\n=== CITATIONS ===")
for i, cit in enumerate(data.get("citations", []), 1):
    page = cit.get("page")
    snippet = cit.get("text_snippet")
    score = cit.get("relevance_score")
    print(f"\n[{i}] Page {page}")
    print(f"    Snippet: {snippet}")
    print(f"    Score: {score}")

print("\n=== METADATA ===")
metadata = data.get("metadata", {})
vision_gen = metadata.get("vision_generation")
if vision_gen:
    print("Vision generation: ENABLED")
    print(f"  Pages used: {vision_gen.get('pages_used', [])}")
    print(f"  Pages failed: {vision_gen.get('pages_failed', [])}")
else:
    print("Vision generation: FAILED/DISABLED")

print(f"\nConfidence: {data.get('confidence_score')}")
print(f"Latency: {data.get('latency_ms')}ms")
