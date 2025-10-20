#!/usr/bin/env python3
"""Investigate OpenSearch indexed data directly"""

import json
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

client = OpenSearch(
    hosts=[{"host": "localhost", "port": 9200}],
    http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
    use_ssl=False,
    verify_certs=False,
    ssl_show_warn=False,
)

print("\n" + "=" * 80)
print("INVESTIGATION: Check actual OpenSearch data")
print("=" * 80)

# 1. Get specific tag by ID
tag_id = "TAG_DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b_p13_04_PU_2049"
print(f"\n1. FETCHING DOCUMENT BY ID: {tag_id}")
print("-" * 40)

try:
    doc = client.get(index="rag_chunks", id=tag_id)
    source = doc["_source"]
    print(f"Found: YES")
    print(f"  page field: {source.get('page')}")
    print(f"  is_tag_entity: {source.get('is_tag_entity')}")
    print(f"  text: {source.get('text')}")
    print(f"  chunk_id: {source.get('chunk_id')}")
    if "metadata" in source:
        print(f"  metadata.page: {source['metadata'].get('page')}")
        print(f"  metadata.is_tag_entity: {source['metadata'].get('is_tag_entity')}")
except Exception as e:
    print(f"ERROR: {e}")

# 2. Search for all PU 2049 tags
print(f"\n2. SEARCH FOR ALL '04 PU 2049' DOCUMENTS")
print("-" * 40)

query = {
    "query": {"bool": {"must": [{"match_phrase": {"text": "04 PU 2049"}}]}},
    "size": 10,
    "_source": ["chunk_id", "page", "text", "is_tag_entity", "metadata.page"],
}

response = client.search(index="rag_chunks", body=query)
hits = response["hits"]["hits"]

print(f"Found {len(hits)} documents with '04 PU 2049':\n")
for i, hit in enumerate(hits, 1):
    source = hit["_source"]
    print(f"[{i}] ID: {hit['_id']}")
    print(f"    chunk_id: {source.get('chunk_id')}")
    print(f"    page (top-level): {source.get('page')}")
    print(
        f"    metadata.page: {source.get('metadata', {}).get('page') if 'metadata' in source else 'N/A'}"
    )
    print(f"    is_tag_entity: {source.get('is_tag_entity')}")
    print(f"    text: {source.get('text')[:50]}")
    print()

# 3. Count documents by page value
print(f"\n3. COUNT TAGS BY PAGE VALUE")
print("-" * 40)

agg_query = {
    "query": {"term": {"is_tag_entity": True}},
    "size": 0,
    "aggs": {"pages": {"terms": {"field": "page", "size": 50}}},
}

response = client.search(index="rag_chunks", body=agg_query)
buckets = response["aggregations"]["pages"]["buckets"]

print("Page distribution for tag entities:")
for bucket in buckets[:10]:
    page = bucket["key"]
    count = bucket["doc_count"]
    print(f"  Page {page}: {count} tags")

# 4. Check index mapping for page field
print(f"\n4. INDEX MAPPING FOR 'page' FIELD")
print("-" * 40)

mapping = client.indices.get_mapping(index="rag_chunks")
page_mapping = mapping["rag_chunks"]["mappings"]["properties"].get("page", {})
print(f"Page field type: {page_mapping}")
