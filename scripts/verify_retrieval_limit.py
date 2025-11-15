"""Verify that retrieval limit has been increased"""
import sys

sys.path.insert(0, "C:/Users/Admin/Desktop/Code - API_LLM_PVCFC")

import requests

from app.rag.spatial.component_indexer import SpatialComponentIndexer

indexer = SpatialComponentIndexer()
doc_id = "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b"

print("=" * 70)
print("VERIFYING RETRIEVAL LIMIT")
print("=" * 70)

# Test 1: Using indexer.search_components()
print("\n1. Using indexer.search_components():")
units = indexer.search_components(
    component_text="04",
    component_type="unit",
    doc_id=doc_id,
    size=10000,  # Explicit size
)
print(f"   Retrieved: {len(units)} unit '04' components")
unit_pages = sorted(set(c["page"] for c in units))
print(f"   Unique pages: {len(unit_pages)}")
print(f"   Pages: {unit_pages}")

# Test 2: Direct OpenSearch query to get TOTAL count
print("\n2. Direct OpenSearch count (actual total in index):")
response = requests.post(
    "http://localhost:9200/pvcfc_pid_spatial_components/_count",
    json={
        "query": {
            "bool": {
                "must": [
                    {"term": {"doc_id": doc_id}},
                    {"term": {"component_type": "unit"}},
                    {"term": {"component": "04"}},
                ]
            }
        }
    },
)
data = response.json()
total_count = data.get("count", 0)
print(f"   Total in index: {total_count} unit '04' components")

# Test 3: Check if we got all of them
print("\n3. Comparison:")
if len(units) == total_count:
    print(f"   ✅ SUCCESS: Retrieved ALL {total_count} components")
elif len(units) < total_count:
    missing = total_count - len(units)
    print(f"   ⚠️  PARTIAL: Retrieved {len(units)}/{total_count} ({missing} missing)")
    print(f"   Reason: Likely hit OpenSearch default max_result_window (10000)")
else:
    print(f"   ❓ UNEXPECTED: Retrieved more than total count")

# Test 4: Check specific pages we need
print("\n4. Critical pages check:")
critical_pages = [21, 55, 65]
for page in critical_pages:
    if page in unit_pages:
        print(f"   ✅ Page {page}: FOUND")
    else:
        print(f"   ❌ Page {page}: MISSING")

print("\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)
if len(units) >= total_count * 0.95:  # Allow 5% tolerance
    print("✅ Retrieval limit is working correctly")
    print(f"   Retrieved {len(units)}/{total_count} components")
else:
    print("⚠️  Retrieval limit may need adjustment")
    print(f"   Only retrieved {len(units)}/{total_count} components")
    print("\nOptions:")
    print("  1. Use scroll API for >10000 results")
    print("  2. Use aggregations to get unique pages")
    print("  3. Increase index.max_result_window setting")
