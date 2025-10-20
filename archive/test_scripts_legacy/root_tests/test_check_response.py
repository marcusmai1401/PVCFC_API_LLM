import json

import requests

response = requests.post(
    "http://localhost:8000/ask",
    json={
        "query": "Tìm cho tôi thiết bị 04 PU 2049 nằm ở đâu trong bản vẽ P&ID",
        "lang": "vi",
    },
)

print("Status:", response.status_code)
print("\n=== RESPONSE ===")
data = response.json()
print(json.dumps(data, indent=2, ensure_ascii=False))

print("\n=== ANSWER ===")
print(data.get("answer", ""))

print("\n=== CITATIONS ===")
for i, cit in enumerate(data.get("citations", []), 1):
    print(f"\n[{i}] Page {cit.get('page')}: {cit.get('text_snippet')}")
    print(f"    Score: {cit.get('relevance_score')}")
