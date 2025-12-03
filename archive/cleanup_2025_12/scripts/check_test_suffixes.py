"""Check if test suffixes exist in spatial index"""
import sys

sys.path.insert(0, "C:/Users/Admin/Desktop/Code - API_LLM_PVCFC")

from app.rag.spatial.component_indexer import SpatialComponentIndexer

indexer = SpatialComponentIndexer()
doc_id = "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b"

# Test suffixes from ground truth
suffixes = ["2097", "2095", "5041", "5501"]

print("=" * 70)
print("CHECKING TEST SUFFIXES IN SPATIAL INDEX")
print("=" * 70)

for suffix in suffixes:
    results = indexer.search_components(
        doc_id=doc_id, component_text=suffix, component_type="suffix", size=100
    )

    if results:
        pages = sorted(set(r["page"] for r in results))
        print(f"✅ {suffix}: Found on pages {pages}")
    else:
        print(f"❌ {suffix}: NOT FOUND")

# Also check the prefixes
print("\n" + "=" * 70)
print("CHECKING TEST PREFIXES")
print("=" * 70)

prefixes = ["TT", "FIC", "HV"]
for prefix in prefixes:
    results = indexer.search_components(
        doc_id=doc_id, component_text=prefix, component_type="prefix", size=100
    )

    if results:
        count = len(results)
        pages = sorted(set(r["page"] for r in results))[:10]
        print(f"✅ {prefix}: {count} occurrences, sample pages {pages}...")
    else:
        print(f"❌ {prefix}: NOT FOUND")
