"""Sample tags from spatial index to see what's actually there"""
import requests

print("Sampling 50 tags from spatial index...")

query = {
    "size": 50,
    "_source": ["doc_id", "page", "tag", "normalized_tag"],
    "query": {"match_all": {}},
}

response = requests.post(
    "http://localhost:9200/pvcfc_pid_spatial_components/_search", json=query
)

data = response.json()
hits = data.get("hits", {}).get("hits", [])

print(f"\nTotal components: {data.get('hits', {}).get('total', {}).get('value', 0):,}")
print(f"\nSample of {len(hits)} tags:\n")

# Group by doc_id to see distribution
doc_tags = {}
for hit in hits:
    source = hit["_source"]
    doc_id = source.get("doc_id", "unknown")
    page = source.get("page")
    tag = source.get("tag")

    if doc_id not in doc_tags:
        doc_tags[doc_id] = []
    doc_tags[doc_id].append({"page": page, "tag": tag})

# Show sample from each doc
for doc_id, tags in list(doc_tags.items())[:3]:
    print(f"\nDoc: ...{doc_id[-50:]}")
    for t in tags[:10]:
        print(f"  Page {t['page']}: {t['tag']}")
    if len(tags) > 10:
        print(f"  ... and {len(tags) - 10} more tags")

# Check for patterns matching our test tags
print("\n" + "=" * 70)
print("Searching for patterns similar to test tags...")
print("=" * 70)

patterns = ["FIC", "PIC", "TIC", "LIC", "310", "560", "460", "520"]
for pattern in patterns:
    query = {
        "size": 5,
        "_source": ["page", "tag", "doc_id"],
        "query": {"wildcard": {"tag": f"*{pattern}*"}},
    }

    response = requests.post(
        "http://localhost:9200/pvcfc_pid_spatial_components/_search", json=query
    )

    data = response.json()
    hits = data.get("hits", {}).get("hits", [])
    count = data.get("hits", {}).get("total", {}).get("value", 0)

    if hits:
        print(f"\nPattern '*{pattern}*': {count} matches")
        for hit in hits[:5]:
            source = hit["_source"]
            print(f"  Page {source.get('page')}: {source.get('tag')}")
