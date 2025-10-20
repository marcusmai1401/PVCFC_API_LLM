#!/usr/bin/env python3
"""Test OpenSearch with tag boosting"""

from opensearchpy import OpenSearch

client = OpenSearch(
    hosts=[{"host": "localhost", "port": 9200}],
    http_auth=("admin", "PhuVinhChemical@2024"),
    use_ssl=False,
    verify_certs=False,
    ssl_show_warn=False,
)

query_text = "04 PU 2049"

# Query WITH tag boosting
query_boosted = {
    "query": {
        "bool": {
            "should": [
                {"match": {"text": {"query": query_text, "boost": 1.0}}},
                {
                    "bool": {
                        "must": [
                            {"match": {"text": query_text}},
                            {"term": {"is_tag_entity": True}},
                        ],
                        "boost": 10.0,  # 10x boost for tags!
                    }
                },
            ]
        }
    },
    "size": 20,
    "_source": ["doc_id", "page", "text", "is_tag_entity"],
}

print("\n" + "=" * 80)
print("OPENSEARCH WITH TAG BOOSTING (10x)")
print("=" * 80)

response = client.search(index="rag_chunks", body=query_boosted)
hits = response["hits"]["hits"]

print(f"\nFound {len(hits)} results:\n")

tag_count = 0
for i, hit in enumerate(hits, 1):
    source = hit["_source"]
    is_tag = source.get("is_tag_entity", False)
    score = hit["_score"]

    if is_tag:
        tag_count += 1
        print(f"[{i}] TAG ⭐ | Page {source.get('page')} | Score {score:.4f}")
    else:
        print(f"[{i}] TEXT   | Page {source.get('page')} | Score {score:.4f}")

    print(f"    {source.get('text', '')[:80]}")
    print()

print("=" * 80)
print(f"\nSUMMARY:")
print(f"  Tags in top 20: {tag_count}")
print(f"  Tag boost: ENABLED (10x)")

# Check if PU 2049 tag is in top 5
pu_found_in_top5 = False
for i, hit in enumerate(hits[:5], 1):
    text = hit["_source"].get("text", "")
    is_tag = hit["_source"].get("is_tag_entity", False)
    if "04 PU 2049" in text and is_tag:
        pu_found_in_top5 = True
        print(f"\n✅ '04 PU 2049' tag found in TOP {i}!")
        break

if not pu_found_in_top5:
    print(f"\n❌ '04 PU 2049' tag NOT in top 5")
