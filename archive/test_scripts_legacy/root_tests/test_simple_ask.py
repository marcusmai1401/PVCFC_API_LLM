#!/usr/bin/env python
"""Simple test of ask endpoint to see detailed error"""

import json

import requests

url = "http://localhost:8000/ask"

payload = {
    "query": "Tag 04 ZLH 2038A nằm ở trang nào của file P&ID?",
    "hyde": True,
    "max_context": 8,
    "language": "vi",
    "filters": {"doc_category": ["pid"]},
}

print("\nSending request...")
print(f"URL: {url}")
print(f"Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}\n")

try:
    response = requests.post(url, json=payload, timeout=30)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"\nAnswer: {data.get('answer')}")
        print(f"\nCitations ({len(data.get('citations', []))}):")
        for i, cit in enumerate(data.get("citations", [])[:3], 1):
            print(f"  {i}. Page {cit.get('page')}: {cit.get('doc_id', 'N/A')[:50]}")
    else:
        print(f"\nError: {response.text}")

except Exception as e:
    print(f"\nException: {e}")
    import traceback

    traceback.print_exc()
