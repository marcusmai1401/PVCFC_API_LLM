"""Debug why spatial search doesn't find page intersections"""
import sys

sys.path.insert(0, "C:/Users/Admin/Desktop/Code - API_LLM_PVCFC")

from app.rag.spatial.component_indexer import SpatialComponentIndexer

indexer = SpatialComponentIndexer()
doc_id = "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b"

failed_tags = [
    {
        "tag": "04-TT-2097",
        "unit": "04",
        "prefix": "TT",
        "suffix": "2097",
        "expected_page": 21,
    },
    {
        "tag": "04-FIC-5041",
        "unit": "04",
        "prefix": "FIC",
        "suffix": "5041",
        "expected_page": 65,
    },
    {
        "tag": "04-HV-5501",
        "unit": "04",
        "prefix": "HV",
        "suffix": "5501",
        "expected_page": 55,
    },
]

print("=" * 70)
print("DEBUGGING PAGE INTERSECTIONS")
print("=" * 70)

for tag_info in failed_tags:
    print(f"\n{'=' * 70}")
    print(f"{tag_info['tag']} - Expected page: {tag_info['expected_page']}")
    print("=" * 70)

    # Get all pages for each component
    units = indexer.search_components(
        doc_id=doc_id, component_text=tag_info["unit"], component_type="unit", size=1000
    )
    prefixes = indexer.search_components(
        doc_id=doc_id,
        component_text=tag_info["prefix"],
        component_type="prefix",
        size=1000,
    )
    suffixes = indexer.search_components(
        doc_id=doc_id,
        component_text=tag_info["suffix"],
        component_type="suffix",
        size=1000,
    )

    unit_pages = set(c["page"] for c in units)
    prefix_pages = set(c["page"] for c in prefixes)
    suffix_pages = set(c["page"] for c in suffixes)

    print(f"\nPages containing each component:")
    print(
        f"  Unit '{tag_info['unit']}': {sorted(unit_pages)[:20]}... (total: {len(unit_pages)} pages)"
    )
    print(f"  Prefix '{tag_info['prefix']}': {sorted(prefix_pages)}")
    print(f"  Suffix '{tag_info['suffix']}': {sorted(suffix_pages)}")

    # Check intersection
    intersection = unit_pages & prefix_pages & suffix_pages

    print(
        f"\nPage intersection (all 3 components): {sorted(intersection) if intersection else 'EMPTY'}"
    )

    # Check if expected page in each set
    print(f"\nExpected page {tag_info['expected_page']} in:")
    print(f"  Unit pages: {'✅' if tag_info['expected_page'] in unit_pages else '❌'}")
    print(
        f"  Prefix pages: {'✅' if tag_info['expected_page'] in prefix_pages else '❌'}"
    )
    print(
        f"  Suffix pages: {'✅' if tag_info['expected_page'] in suffix_pages else '❌'}"
    )
