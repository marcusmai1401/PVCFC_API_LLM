"""Direct OpenSearch query to check unit 04 on specific pages"""
import json

import requests

doc_id = "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b"
target_pages = [21, 55, 65]

print("=" * 70)
print("DIRECT OPENSEARCH CHECK FOR UNIT '04'")
print("=" * 70)

for page in target_pages:
    print(f"\n{'=' * 70}")
    print(f"Page {page}")
    print("=" * 70)

    # Query for unit=04 on this page
    query = {
        "size": 100,
        "_source": ["component", "component_type", "page", "center_x", "center_y"],
        "query": {
            "bool": {
                "must": [
                    {"term": {"doc_id": doc_id}},
                    {"term": {"page": page}},
                    {"term": {"component_type": "unit"}},
                ]
            }
        },
    }

    response = requests.post(
        "http://localhost:9200/pvcfc_pid_spatial_components/_search", json=query
    )

    data = response.json()
    hits = data.get("hits", {}).get("hits", [])

    if hits:
        unique_units = {}
        for hit in hits:
            comp = hit["_source"]["component"]
            if comp not in unique_units:
                unique_units[comp] = []
            unique_units[comp].append(hit["_source"])

        print(f"Found {len(hits)} unit components:")
        for unit, instances in sorted(unique_units.items()):
            print(f"  '{unit}': {len(instances)} instance(s)")
            for inst in instances[:3]:
                print(f"    - center=({inst['center_x']:.1f}, {inst['center_y']:.1f})")

        if "04" in unique_units:
            print(f"\n✅ Unit '04' FOUND on page {page}")
        else:
            print(f"\n⚠️  Unit '04' NOT found on page {page}")
            print(f"   Available units: {list(unique_units.keys())}")
    else:
        print(f"❌ NO unit components found on page {page}")

    # Also check ALL components on this page (not just units)
    query_all = {
        "size": 0,
        "query": {
            "bool": {"must": [{"term": {"doc_id": doc_id}}, {"term": {"page": page}}]}
        },
        "aggs": {"by_type": {"terms": {"field": "component_type", "size": 10}}},
    }

    response = requests.post(
        "http://localhost:9200/pvcfc_pid_spatial_components/_search", json=query_all
    )

    data = response.json()
    aggs = data.get("aggregations", {}).get("by_type", {}).get("buckets", [])

    if aggs:
        print(f"\nComponent type distribution on page {page}:")
        for bucket in aggs:
            print(f"  {bucket['key']}: {bucket['doc_count']} components")

print("\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)
print("If unit '04' is not found on these pages, it means:")
print("  A) Tags on these pages don't have explicit unit component in PDF")
print("  B) Ingestion skipped unit detection on these pages")
print("  C) Page numbering mismatch (PDF page != indexed page)")
