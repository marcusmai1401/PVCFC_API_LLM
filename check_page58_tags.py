import requests

# Search for all TI tags on page 58
response = requests.post(
    "http://localhost:9200/pvcfc_pid_tags/_search",
    json={
        "query": {
            "bool": {
                "must": [{"term": {"page": 58}}, {"term": {"prefix.keyword": "TI"}}]
            }
        },
        "size": 50,
        "sort": [{"suffix": "asc"}],
    },
)

data = response.json()

if "error" in data:
    print(f"Error: {data['error']}")
    exit(1)

hits = data["hits"]["hits"]

print(f"Found {len(hits)} TI tags on page 58:")
for hit in hits:
    src = hit["_source"]
    variant = f" {src['variant']}" if src.get("variant") else ""
    print(f"  {src['unit']} {src['prefix']} {src['suffix']}{variant}")

# Also search for tag with suffix 5058 on any page
print("\n--- Searching for suffix 5058 anywhere ---")
response2 = requests.post(
    "http://localhost:9200/pvcfc_pid_tags/_search",
    json={"query": {"bool": {"must": [{"term": {"suffix": "5058"}}]}}, "size": 10},
)

data2 = response2.json()
hits2 = data2.get("hits", {}).get("hits", [])

print(f"Found {len(hits2)} tags with suffix 5058:")
for hit in hits2:
    src = hit["_source"]
    variant = f" {src['variant']}" if src.get("variant") else ""
    print(
        f"  Page {src['page']:3d}: {src['unit']} {src['prefix']} {src['suffix']}{variant}"
    )
