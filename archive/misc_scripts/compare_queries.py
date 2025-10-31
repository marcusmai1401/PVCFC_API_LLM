import json

import requests

queries = [
    {
        "name": "Simple (tag only)",
        "payload": {"query": "04 TI 5058", "query_type": "pid"},
    },
    {
        "name": "Vietnamese context",
        "payload": {
            "query": "Tìm cho tôi tag name 04 TI 5058 trong bản vẽ P&ID",
            "query_type": "pid",
            "language": "vi",
            "max_context": 8,
            "hyde": False,
            "execution_mode": "production",
            "confidence_mode": "legacy",
        },
    },
]

print("=" * 80)
print("QUERY COMPARISON")
print("=" * 80)
print()

for test in queries:
    print(f"{test['name']}:")
    print(f"  Query: {test['payload']['query']}")

    try:
        response = requests.post(
            "http://localhost:8000/ask", json=test["payload"], timeout=60
        )

        if response.ok:
            data = response.json()
            citations = data.get("citations", [])
            pages = [c.get("page") for c in citations if c.get("page")]

            print(f"  Pages: {pages[:5]}")
            print(f"  Has page 58: {58 in pages[:5]}")
            print(f"  Confidence: {data.get('confidence', 0):.2f}")
        else:
            print(f"  ERROR: {response.status_code}")

    except Exception as e:
        print(f"  EXCEPTION: {e}")

    print()

print("=" * 80)
print("If 'Simple' works but 'Vietnamese context' fails,")
print("the issue is in query processing/transformation.")
