"""Test aggregation-based page retrieval for 100% coverage"""
import sys

sys.path.insert(0, "C:/Users/Admin/Desktop/Code - API_LLM_PVCFC")

import requests

from app.rag.spatial.spatial_searcher import SpatialTagSearcher

# Initialize searcher (will use new aggregation method)
searcher = SpatialTagSearcher()

doc_id = "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b"

print("=" * 70)
print("TESTING AGGREGATION-BASED PAGE RETRIEVAL")
print("=" * 70)

# Test: Get pages with unit "04"
print("\n1. Getting pages with unit '04' using NEW aggregation method:")
unit_pages = searcher._get_pages_with_component("04", "unit", doc_id)
print(f"   Found: {len(unit_pages)} unique pages")
print(f"   Pages: {sorted(unit_pages)}")

# Compare with actual total
print("\n2. Direct count from OpenSearch:")
response = requests.post(
    "http://localhost:9200/pvcfc_pid_spatial_components/_search",
    json={
        "size": 0,
        "query": {
            "bool": {
                "must": [
                    {"term": {"doc_id": doc_id}},
                    {"term": {"component_type": "unit"}},
                    {"term": {"component": "04"}},
                ]
            }
        },
        "aggs": {"unique_pages": {"terms": {"field": "page", "size": 10000}}},
    },
)

data = response.json()
total_count = data.get("hits", {}).get("total", {}).get("value", 0)
agg_buckets = data.get("aggregations", {}).get("unique_pages", {}).get("buckets", [])
actual_unique_pages = len(agg_buckets)

print(f"   Total components: {total_count}")
print(f"   Unique pages: {actual_unique_pages}")

# Comparison
print("\n3. Comparison:")
if len(unit_pages) == actual_unique_pages:
    print(f"   ✅ PERFECT: Retrieved ALL {actual_unique_pages} unique pages")
else:
    print(f"   ❌ MISMATCH: Retrieved {len(unit_pages)}, expected {actual_unique_pages}")

# Check all P&ID pages (should be 117)
print("\n4. Coverage check:")
print(f"   Total P&ID pages: 117")
print(f"   Pages with unit '04': {len(unit_pages)}")
print(f"   Coverage: {100 * len(unit_pages) / 117:.1f}%")

# Check critical pages
critical_pages = [21, 55, 65]
print("\n5. Critical pages:")
for page in critical_pages:
    status = "✅" if page in unit_pages else "❌"
    print(f"   {status} Page {page}")

print("\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)
if len(unit_pages) == actual_unique_pages:
    print("✅ Aggregation-based retrieval is working perfectly!")
    print(f"   No components missed, all {actual_unique_pages} unique pages retrieved")
else:
    print("⚠️  Issue with aggregation retrieval")
