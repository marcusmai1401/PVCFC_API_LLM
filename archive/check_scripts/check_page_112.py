"""Check tags on page 112 (what was returned for 04 TXI 2077)"""
from opensearchpy import OpenSearch

client = OpenSearch(
    hosts=[{"host": "localhost", "port": 9200}],
    http_compress=True,
    use_ssl=False,
    verify_certs=False,
    ssl_assert_hostname=False,
    ssl_show_warn=False,
)

index_name = "pvcfc_pid_tags"

print("=" * 80)
print("Tags on Page 112 (returned for query '04 TXI 2077')")
print("=" * 80)

response = client.search(
    index=index_name,
    body={
        "query": {
            "bool": {
                "must": [{"term": {"page": 112}}, {"match": {"doc_id": "Ammonia"}}]
            }
        },
        "size": 100,
    },
)

print(f"Total tags on page 112: {response['hits']['total']['value']}\n")

tags = []
for hit in response["hits"]["hits"]:
    src = hit["_source"]
    parts = src.get("tag_parts", {})
    tag_text = src.get("tag_text", "")
    tags.append(tag_text)
    if "TXI" in tag_text or "2077" in tag_text:
        print(f"  {tag_text} - Parts: {parts}")

# Sort and display all
tags.sort()
print(f"\nAll {len(tags)} tags on page 112:")
for i, tag in enumerate(tags, 1):
    if i % 5 == 0:
        print(tag)
    else:
        print(tag, end=", ")
    if i % 5 == 0 and i < len(tags):
        print()
