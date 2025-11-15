"""Debug spatial search step by step"""
import sys

sys.path.insert(0, "C:/Users/Admin/Desktop/Code - API_LLM_PVCFC")

from app.rag.spatial.component_indexer import SpatialComponentIndexer

indexer = SpatialComponentIndexer()
doc_id = "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b"

# Test case: 04-TT-2097 on page 21
unit = "04"
prefix = "TT"
suffix = "2097"

print("=" * 70)
print(f"DEBUGGING: {unit}-{prefix}-{suffix}")
print("=" * 70)

# Step 1: Get pages with each component
print("\nStep 1: Get pages with each component type\n")

print(f"Searching for unit='{unit}', component_type='unit', doc_id='{doc_id[:50]}...'")
units = indexer.search_components(
    component_text=unit, component_type="unit", doc_id=doc_id, size=1000
)
print(f"  Found {len(units)} unit components")
unit_pages = set(c["page"] for c in units)
print(f"  Pages: {sorted(unit_pages)}")

print(
    f"\nSearching for prefix='{prefix}', component_type='prefix', doc_id='{doc_id[:50]}...'"
)
prefixes = indexer.search_components(
    component_text=prefix, component_type="prefix", doc_id=doc_id, size=1000
)
print(f"  Found {len(prefixes)} prefix components")
prefix_pages = set(c["page"] for c in prefixes)
print(f"  Pages: {sorted(prefix_pages)}")

print(
    f"\nSearching for suffix='{suffix}', component_type='suffix', doc_id='{doc_id[:50]}...'"
)
suffixes = indexer.search_components(
    component_text=suffix, component_type="suffix", doc_id=doc_id, size=1000
)
print(f"  Found {len(suffixes)} suffix components")
suffix_pages = set(c["page"] for c in suffixes)
print(f"  Pages: {sorted(suffix_pages)}")

# Step 2: Intersection
print("\nStep 2: Page intersection\n")
intersection = unit_pages & prefix_pages & suffix_pages
print(
    f"Pages with ALL 3 components: {sorted(intersection) if intersection else 'EMPTY'}"
)

if not intersection:
    print("\n❌ NO INTERSECTION!")
    print("\nDebugging why:")
    print(f"  Unit pages ({len(unit_pages)}): {sorted(unit_pages)}")
    print(f"  Prefix pages ({len(prefix_pages)}): {sorted(prefix_pages)}")
    print(f"  Suffix pages ({len(suffix_pages)}): {sorted(suffix_pages)}")

    print("\n  Expected page 21:")
    print(f"    In unit pages: {21 in unit_pages}")
    print(f"    In prefix pages: {21 in prefix_pages}")
    print(f"    In suffix pages: {21 in suffix_pages}")
