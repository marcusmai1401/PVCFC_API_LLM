#!/usr/bin/env python
import json

import requests

url = "http://localhost:8000/ask"
payload = {
    "query": "Tell me about equipment tag 04 PU 2049 in the P&ID diagram",
    "session_id": "test_tags_final",
}

print("\nSending query to API...")
print(f"Query: {payload['query']}")

r = requests.post(url, json=payload, timeout=120)

print(f"\nStatus: {r.status_code}")

if r.status_code == 200:
    resp = r.json()

    print(f"\nAnswer ({len(resp['answer'])} chars):")
    print(resp["answer"][:500])

    if resp.get("citations"):
        print(f"\nCitations ({len(resp['citations'])} total):")
        for i, cit in enumerate(resp["citations"][:3], 1):
            print(f"\n  {i}. Page {cit['page']}")
            print(f"     Doc: {cit['doc_id'][:60]}...")
            print(f"     Source: {cit.get('source', 'N/A')}")
    else:
        print("\nNo citations")
else:
    print(f"Error: {r.text}")
