"""
Debug script for Query 3: 04 TXI 2077 on page 17
Check if tag exists in OpenSearch index
"""
import json

from opensearchpy import OpenSearch

# OpenSearch connection
client = OpenSearch(
    hosts=[{"host": "localhost", "port": 9200}],
    http_compress=True,
    use_ssl=False,
    verify_certs=False,
    ssl_assert_hostname=False,
    ssl_show_warn=False,
)

index_name = "pvcfc_pid_tags"

# Search for exact tag
print("=" * 80)
print("QUERY 3 DEBUG: Searching for '04 TXI 2077'")
print("=" * 80)
print()

# 1. Search by exact full tag text
print("[1] Exact tag text search:")
response = client.search(
    index=index_name, body={"query": {"match": {"tag_text": "04 TXI 2077"}}, "size": 20}
)

print(f"Total hits: {response['hits']['total']['value']}")
for hit in response["hits"]["hits"][:10]:
    src = hit["_source"]
    print(
        f"  Tag: {src['tag_text']}, Page: {src['page']}, Doc: {src['doc_id']}, Score: {hit['_score']:.2f}"
    )
print()

# 2. Search by components
print("[2] Component search (unit=04, prefix=TXI, suffix=2077):")
response = client.search(
    index=index_name,
    body={
        "query": {
            "bool": {
                "must": [
                    {"term": {"tag_parts.unit": "04"}},
                    {"term": {"tag_parts.prefix": "TXI"}},
                    {"term": {"tag_parts.suffix": "2077"}},
                ]
            }
        },
        "size": 20,
    },
)

print(f"Total hits: {response['hits']['total']['value']}")
for hit in response["hits"]["hits"][:10]:
    src = hit["_source"]
    parts = src.get("tag_parts", {})
    print(
        f"  Tag: {src['tag_text']}, Page: {src['page']}, Parts: {parts}, Score: {hit['_score']:.2f}"
    )
print()

# 3. Search all tags on page 17
print("[3] All tags on page 17:")
response = client.search(
    index=index_name,
    body={
        "query": {
            "bool": {"must": [{"term": {"page": 17}}, {"match": {"doc_id": "Ammonia"}}]}
        },
        "size": 100,
    },
)

print(f"Total tags on page 17: {response['hits']['total']['value']}")
tags_on_17 = []
for hit in response["hits"]["hits"]:
    src = hit["_source"]
    tags_on_17.append(src["tag_text"])

# Look for TXI tags
txi_tags = [t for t in tags_on_17 if "TXI" in t]
print(f"TXI tags on page 17: {txi_tags}")

# Look for 2077 suffix tags
suffix_2077_tags = [t for t in tags_on_17 if "2077" in t]
print(f"Tags with suffix 2077 on page 17: {suffix_2077_tags}")
print()

# 4. Search all TXI 2077 tags across all pages
print("[4] All TXI 2077 tags (any page):")
response = client.search(
    index=index_name,
    body={
        "query": {
            "bool": {
                "must": [
                    {"term": {"tag_parts.prefix": "TXI"}},
                    {"term": {"tag_parts.suffix": "2077"}},
                ]
            }
        },
        "size": 20,
        "sort": [{"page": "asc"}],
    },
)

print(f"Total TXI 2077 tags: {response['hits']['total']['value']}")
for hit in response["hits"]["hits"]:
    src = hit["_source"]
    parts = src.get("tag_parts", {})
    print(
        f"  Tag: {src['tag_text']}, Page: {src['page']}, Unit: {parts.get('unit')}, Doc: {src['doc_id']}"
    )
print()

print("=" * 80)
print("CONCLUSION:")
print("=" * 80)
if "04 TXI 2077" in suffix_2077_tags:
    print("✓ Tag '04 TXI 2077' EXISTS on page 17")
else:
    print("✗ Tag '04 TXI 2077' NOT FOUND on page 17")
    print("  Possible issues:")
    print("  1. Ground truth is incorrect")
    print("  2. Tag was not extracted from page 17")
    print("  3. Tag format mismatch in extraction")
