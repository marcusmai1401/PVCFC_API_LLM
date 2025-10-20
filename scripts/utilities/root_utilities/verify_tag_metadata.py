#!/usr/bin/env python3
"""Verify tag metadata in OpenSearch index"""

import os

from opensearchpy import OpenSearch

# Load credentials from environment variables
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD")

if not OPENSEARCH_PASSWORD:
    raise ValueError(
        "OPENSEARCH_PASSWORD environment variable is required. "
        "Please set it before running this script."
    )

# Connect to OpenSearch
client = OpenSearch(
    hosts=[{"host": "localhost", "port": 9200}],
    http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
    use_ssl=False,
    verify_certs=False,
    ssl_show_warn=False,
)

# Search for tags with "2049" - WITHOUT is_tag_entity filter first
query = {
    "query": {
        "bool": {
            "must": [
                {"match": {"text": "2049"}},
            ]
        }
    },
    "size": 50,
    "_source": ["doc_id", "page", "text", "metadata", "chunk_id", "is_tag_entity"],
}

response = client.search(index="rag_chunks", body=query)
hits = response["hits"]["hits"]

print(f"Found {len(hits)} tags with '2049'\n")
print("=" * 80)

for i, hit in enumerate(hits, 1):
    source = hit["_source"]
    tag_text = source.get("text", "")
    page = source.get("page")
    doc_id = source.get("doc_id", "")[:50]
    metadata = source.get("metadata", {})

    is_tag = source.get("is_tag_entity", False)

    print(f"\n[{i}] Tag: {tag_text}")
    print(f"    Page (field): {page}")
    print(f"    Page (metadata): {metadata.get('page')}")
    print(f"    Doc ID: {doc_id}")
    print(f"    Chunk ID: {source.get('chunk_id', '')[:60]}")
    print(f"    is_tag_entity: {is_tag}")

    # Check if it's the PU 2049 tag
    if "PU" in tag_text and "2049" in tag_text:
        print(f"    *** THIS IS 04 PU 2049 ***")

print("\n" + "=" * 80)
print("\nSUMMARY:")
print(f"Total tags found: {len(hits)}")

# Count by page
from collections import Counter

page_counts = Counter()
for hit in hits:
    page = hit["_source"].get("page")
    page_counts[page] += 1

print("\nTags by page:")
for page, count in sorted(page_counts.items()):
    print(f"  Page {page}: {count} tags")
