"""Check if test tag components exist in spatial index"""
import sys

sys.path.insert(0, "C:/Users/Admin/Desktop/Code - API_LLM_PVCFC")

from app.rag.spatial.component_indexer import SpatialComponentIndexer

indexer = SpatialComponentIndexer()

doc_id = "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b"

# Test components
test_components = {
    "prefixes": ["FIC", "PIC", "TIC", "LIC"],
    "suffixes": ["310", "560", "460", "520"],
}

print("=" * 70)
print("CHECKING TEST TAG COMPONENTS")
print("=" * 70)
print(f"\nDoc: {doc_id}")

for comp_type, values in test_components.items():
    print(f"\n{comp_type.upper()}:")
    for value in values:
        results = indexer.search_components(
            doc_id=doc_id,
            component_text=value,
            component_type=comp_type.rstrip("es"),  # prefix/suffix
            size=100,
        )

        if results:
            pages = set(r["page"] for r in results)
            print(f"  ✅ {value}: {len(results)} occurrences on pages {sorted(pages)}")
        else:
            print(f"  ❌ {value}: NOT FOUND")

# Try wildcard search for partial matches
print("\n" + "=" * 70)
print("SEARCHING FOR SIMILAR PREFIXES")
print("=" * 70)

import requests

query = {
    "size": 100,
    "_source": ["component", "page"],
    "query": {
        "bool": {
            "must": [
                {"term": {"doc_id": doc_id}},
                {"term": {"component_type": "prefix"}},
                {"regexp": {"component": ".*IC.*"}},  # Any prefix containing IC
            ]
        }
    },
}

response = requests.post(
    "http://localhost:9200/pvcfc_pid_spatial_components/_search", json=query
)

if response.status_code == 200:
    data = response.json()
    hits = data.get("hits", {}).get("hits", [])

    if hits:
        unique_prefixes = set()
        for hit in hits:
            unique_prefixes.add(hit["_source"]["component"])

        print(f"\nFound {len(unique_prefixes)} prefixes containing 'IC':")
        for prefix in sorted(unique_prefixes)[:20]:
            print(f"  {prefix}")
