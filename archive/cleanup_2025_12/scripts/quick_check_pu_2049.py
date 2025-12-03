#!/usr/bin/env python3
"""Quick check for PU 2049 tag"""

import os

from opensearchpy import OpenSearch

# Load credentials from environment variables (optional for no-security mode)
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD")

# Connect with or without authentication based on security mode
if OPENSEARCH_PASSWORD:
    client = OpenSearch(
        hosts=[{"host": "localhost", "port": 9200}],
        http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
        use_ssl=False,
        verify_certs=False,
        ssl_show_warn=False,
    )
else:
    client = OpenSearch(
        hosts=[{"host": "localhost", "port": 9200}],
        use_ssl=False,
        verify_certs=False,
        ssl_show_warn=False,
    )

# Search for "04 PU 2049" with is_tag_entity filter
query = {
    "query": {
        "bool": {
            "must": [
                {"match": {"text": "04 PU 2049"}},
                {"term": {"is_tag_entity": True}},
            ]
        }
    },
    "size": 5,
    "_source": ["doc_id", "page", "text", "is_tag_entity"],
}

print("\n" + "=" * 60)
print("SEARCHING FOR: 04 PU 2049 (with is_tag_entity=True)")
print("=" * 60)

response = client.search(index="rag_chunks", body=query)
hits = response["hits"]["hits"]

if hits:
    print(f"\nFound {len(hits)} matches:\n")
    for i, hit in enumerate(hits, 1):
        source = hit["_source"]
        print(f"[{i}] {source.get('text', '')}")
        print(f"    Page: {source.get('page')}")
        print(f"    is_tag_entity: {source.get('is_tag_entity')}")
        print(f"    Doc: {source.get('doc_id', '')[:50]}...")
        print()
else:
    print("\nNO MATCHES FOUND!")

    # Try without filter
    print("\nRetrying WITHOUT is_tag_entity filter...")
    query_no_filter = {
        "query": {"match": {"text": "04 PU 2049"}},
        "size": 5,
        "_source": ["doc_id", "page", "text", "is_tag_entity"],
    }

    response2 = client.search(index="rag_chunks", body=query_no_filter)
    hits2 = response2["hits"]["hits"]

    if hits2:
        print(f"\nFound {len(hits2)} matches WITHOUT filter:\n")
        for i, hit in enumerate(hits2, 1):
            source = hit["_source"]
            is_tag = source.get("is_tag_entity", "MISSING")
            print(f"[{i}] Page {source.get('page')}: is_tag_entity = {is_tag}")
    else:
        print("\nStill no matches!")

print("\n" + "=" * 60)
