import json

import requests

# Test query 2
payload = {
    "query": "Tìm cho tôi tag name 04 TI 5058 trong bản vẽ P&ID",
    "query_type": "pid",
    "language": "vi",
    "max_context": 8,
    "hyde": False,
    "execution_mode": "production",
    "confidence_mode": "legacy",
}

print("Testing Query 2: 04 TI 5058")
print(f"Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
print()

response = requests.post("http://localhost:8000/ask", json=payload, timeout=120)

if response.ok:
    data = response.json()

    citations = data.get("citations", [])
    pages = [c.get("page") for c in citations if c.get("page")]

    print(f"✅ API Response OK")
    print(f"   Citations: {len(citations)}")
    print(f"   Pages: {pages[:10]}")
    print(f"   Confidence: {data.get('confidence', 0):.2f}")
    print()

    if 58 in pages[:5]:
        print(f"✅ PASS: Page 58 found in top-5 (position {pages.index(58) + 1})")
    else:
        print(f"❌ FAIL: Page 58 NOT in top-5")
        print(f"   Expected: 58")
        print(f"   Got: {pages[:5]}")
else:
    print(f"❌ API Error: {response.status_code}")
    print(response.text[:500])
