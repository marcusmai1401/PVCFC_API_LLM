import requests

# Search for tag 04 TI 5058
response = requests.post(
    "http://localhost:9200/pvcfc_pid_tags/_search",
    json={
        "query": {
            "bool": {
                "must": [
                    {"term": {"unit": "04"}},
                    {"term": {"prefix.keyword": "TI"}},
                    {"term": {"suffix": "5058"}},
                ]
            }
        },
        "size": 10,
    },
)

data = response.json()

if "error" in data:
    print(f"OpenSearch error: {data['error']}")
    exit(1)

if "hits" not in data:
    print(f"Unexpected response: {data}")
    exit(1)

hits = data["hits"]["hits"]

print(f"Found {len(hits)} tags matching '04 TI 5058':")
if len(hits) == 0:
    print("  (No tags found - tag may not be extracted or different format)")
else:
    for hit in hits:
        src = hit["_source"]
        variant = f" {src['variant']}" if src.get("variant") else ""
        print(
            f"  Page {src['page']:3d}: {src['unit']} {src['prefix']} {src['suffix']}{variant}"
        )
