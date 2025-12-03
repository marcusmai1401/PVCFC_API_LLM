"""Test query for 04 TXI 2077 after re-indexing"""
import requests

response = requests.post(
    "http://localhost:8000/ask",
    json={
        "query": "04 TXI 2077",
        "query_type": "pid",
        "language": "vi",
        "max_context": 5,
    },
    timeout=60,
)

if response.ok:
    data = response.json()
    citations = data.get("citations", [])

    print(f"Query: 04 TXI 2077")
    print(f"Citations: {len(citations)}")
    print(f"Confidence: {data.get('confidence', 0):.2f}")

    if citations:
        print(f"\nTop 5 pages:")
        for i, cit in enumerate(citations[:5], 1):
            print(f"  {i}. Page {cit.get('page')} - {cit.get('doc_id')}")

        if citations[0].get("page") == 17:
            print("\n✓ SUCCESS: Query returns page 17!")
        else:
            print(f"\n✗ WRONG PAGE: Expected 17, got {citations[0].get('page')}")
    else:
        print("\n✗ NO CITATIONS returned")
else:
    print(f"Error: {response.status_code}")
    print(response.text)
