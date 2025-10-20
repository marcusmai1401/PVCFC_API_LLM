#!/usr/bin/env python
from opensearchpy import OpenSearch

client = OpenSearch([{"host": "localhost", "port": 9200}], use_ssl=False)

# Search for "04 PU 2049"
result = client.search(
    index="rag_chunks",
    body={
        "query": {"match": {"metadata.tags": "04 PU 2049"}},
        "size": 3,
    },
)

total = result["hits"]["total"]["value"]
print(f"\nFound {total} chunks with '04 PU 2049'")

if total > 0:
    for hit in result["hits"]["hits"]:
        print(f"\n  Tag: {hit['_source']['metadata']['tags']}")
        print(f"  Page: {hit['_source'].get('page', 'N/A')}")
        print(f"  Doc: {hit['_source']['doc_id'][:60]}...")
else:
    print("  Tag not found in index")

# Check total tag entities
result = client.search(
    index="rag_chunks",
    body={
        "query": {"term": {"metadata.is_tag_entity": True}},
        "size": 0,
    },
)

print(f"\nTotal tag entities in index: {result['hits']['total']['value']}")
