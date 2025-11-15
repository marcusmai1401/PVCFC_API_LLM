"""Check spatial index mapping and sample full documents"""
import json

import requests

print("=" * 70)
print("SPATIAL INDEX MAPPING")
print("=" * 70)

# Get mapping
response = requests.get("http://localhost:9200/pvcfc_pid_spatial_components/_mapping")
mapping = response.json()

properties = (
    mapping.get("pvcfc_pid_spatial_components", {})
    .get("mappings", {})
    .get("properties", {})
)

print("\nFields in mapping:")
for field, config in sorted(properties.items()):
    field_type = config.get("type", "object")
    print(f"  {field}: {field_type}")

# Check if tag field exists
if "tag" in properties:
    print(f"\n✅ 'tag' field exists: {properties['tag']}")
else:
    print("\n❌ 'tag' field NOT in mapping!")

print("\n" + "=" * 70)
print("SAMPLE FULL DOCUMENTS")
print("=" * 70)

# Get full documents (not just _source)
query = {"size": 3, "query": {"match_all": {}}}

response = requests.post(
    "http://localhost:9200/pvcfc_pid_spatial_components/_search", json=query
)

data = response.json()
hits = data.get("hits", {}).get("hits", [])

print(f"\nRetrieved {len(hits)} documents\n")

for i, hit in enumerate(hits, 1):
    print(f"Document {i}:")
    print(f"  _id: {hit.get('_id')}")
    print(f"  _source keys: {list(hit.get('_source', {}).keys())}")

    source = hit.get("_source", {})
    print(f"\n  _source content:")
    for key, value in source.items():
        if isinstance(value, (list, dict)):
            print(
                f"    {key}: {type(value).__name__} (length={len(value) if isinstance(value, list) else 'N/A'})"
            )
        else:
            val_str = str(value)[:100]
            print(f"    {key}: {val_str}")
    print()
