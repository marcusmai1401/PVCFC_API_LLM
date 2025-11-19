"""Debug spatial search step by step for multiple tags"""
import sys

sys.path.insert(0, "C:/Users/Admin/Desktop/Code - API_LLM_PVCFC")

from app.rag.spatial.component_indexer import SpatialComponentIndexer

indexer = SpatialComponentIndexer()
doc_id = "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b"

# Test cases (including failing ones from spatial_search_direct)
TESTS = [
    {
        "name": "REF: 04-TT-2097 (baseline)",
        "unit": "04",
        "prefix": "TT",
        "suffix": "2097",
        "expected_page": 21,
    },
    {
        "name": "DBG: 04-I-3201",
        "unit": "04",
        "prefix": "I",
        "suffix": "3201",
        "expected_page": 26,
    },
    {
        "name": "DBG: 04-I-1303",
        "unit": "04",
        "prefix": "I",
        "suffix": "1303",
        "expected_page": 40,
    },
    {
        "name": "DBG: 29-TI-2202A",
        "unit": "29",
        "prefix": "TI",
        "suffix": "2202A",
        "expected_page": 113,
    },
    {
        "name": "DBG: 29-VE-2003AX",
        "unit": "29",
        "prefix": "VE",
        "suffix": "2003AX",
        "expected_page": 113,
    },
    {
        "name": "DBG: 29-VE-2003BY",
        "unit": "29",
        "prefix": "VE",
        "suffix": "2003BY",
        "expected_page": 113,
    },
]

for test in TESTS:
    unit = test["unit"]
    prefix = test["prefix"]
    suffix = test["suffix"]
    expected_page = test["expected_page"]

    print("=" * 80)
    print(f"{test['name']}: {unit} {prefix} {suffix} (expected page {expected_page})")
    print("=" * 80)

    # Step 1: Get pages with each component
    print("\nStep 1: Get pages with each component type\n")

    print(
        f"Searching for unit='{unit}', component_type='unit', doc_id='{doc_id[:50]}...'"
    )
    units = indexer.search_components(
        component_text=unit, component_type="unit", doc_id=doc_id, size=1000
    )
    print(f"  Found {len(units)} unit components")
    unit_pages = set(c["page"] for c in units)
    print(f"  Unit pages: {sorted(unit_pages)}")

    print(
        f"\nSearching for prefix='{prefix}', component_type='prefix', doc_id='{doc_id[:50]}...'"
    )
    prefixes = indexer.search_components(
        component_text=prefix, component_type="prefix", doc_id=doc_id, size=1000
    )
    print(f"  Found {len(prefixes)} prefix components")
    prefix_pages = set(c["page"] for c in prefixes)
    print(f"  Prefix pages: {sorted(prefix_pages)}")

    print(
        f"\nSearching for suffix='{suffix}', component_type='suffix', doc_id='{doc_id[:50]}...'"
    )
    suffixes = indexer.search_components(
        component_text=suffix, component_type="suffix", doc_id=doc_id, size=1000
    )
    print(f"  Found {len(suffixes)} suffix components")
    suffix_pages = set(c["page"] for c in suffixes)
    print(f"  Suffix pages: {sorted(suffix_pages)}")

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

        print(f"\n  Expected page {expected_page}:")
        print(f"    In unit pages: {expected_page in unit_pages}")
        print(f"    In prefix pages: {expected_page in prefix_pages}")
        print(f"    In suffix pages: {expected_page in suffix_pages}")

    print("\n")
