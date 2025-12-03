"""Check component positions for tags that failed clustering"""
import sys

sys.path.insert(0, "C:/Users/Admin/Desktop/Code - API_LLM_PVCFC")

from app.rag.spatial.component_indexer import SpatialComponentIndexer

indexer = SpatialComponentIndexer()
doc_id = "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b"

# Failed tags
failed_tags = [
    {"tag": "04-TT-2097", "unit": "04", "prefix": "TT", "suffix": "2097", "page": 21},
    {"tag": "04-FIC-5041", "unit": "04", "prefix": "FIC", "suffix": "5041", "page": 65},
    {"tag": "04-HV-5501", "unit": "04", "prefix": "HV", "suffix": "5501", "page": 55},
]

print("=" * 70)
print("CHECKING COMPONENT POSITIONS FOR FAILED TAGS")
print("=" * 70)

for tag_info in failed_tags:
    print(f"\n{'=' * 70}")
    print(f"{tag_info['tag']} on page {tag_info['page']}")
    print("=" * 70)

    page = tag_info["page"]

    # Get components on this page
    units = indexer.search_components(
        doc_id=doc_id,
        component_text=tag_info["unit"],
        component_type="unit",
        page=page,
        size=100,
    )
    prefixes = indexer.search_components(
        doc_id=doc_id,
        component_text=tag_info["prefix"],
        component_type="prefix",
        page=page,
        size=100,
    )
    suffixes = indexer.search_components(
        doc_id=doc_id,
        component_text=tag_info["suffix"],
        component_type="suffix",
        page=page,
        size=100,
    )

    print(f"\nComponents on page {page}:")
    print(f"  Units '{tag_info['unit']}': {len(units)}")
    print(f"  Prefixes '{tag_info['prefix']}': {len(prefixes)}")
    print(f"  Suffixes '{tag_info['suffix']}': {len(suffixes)}")

    if units and prefixes and suffixes:
        print("\n✅ All components exist on this page!")
        print("\nPositions:")
        for u in units[:3]:
            print(
                f"  Unit {u['component']}: center=({u['center_x']:.1f}, {u['center_y']:.1f})"
            )
        for p in prefixes[:3]:
            print(
                f"  Prefix {p['component']}: center=({p['center_x']:.1f}, {p['center_y']:.1f})"
            )
        for s in suffixes[:3]:
            print(
                f"  Suffix {s['component']}: center=({s['center_x']:.1f}, {s['center_y']:.1f})"
            )

        # Calculate distances
        if units and prefixes and suffixes:
            u = units[0]
            p = prefixes[0]
            s = suffixes[0]

            dist_up = (
                (u["center_x"] - p["center_x"]) ** 2
                + (u["center_y"] - p["center_y"]) ** 2
            ) ** 0.5
            dist_ps = (
                (p["center_x"] - s["center_x"]) ** 2
                + (p["center_y"] - s["center_y"]) ** 2
            ) ** 0.5
            dist_us = (
                (u["center_x"] - s["center_x"]) ** 2
                + (u["center_y"] - s["center_y"]) ** 2
            ) ** 0.5

            print(f"\nDistances (in PDF points, ~72 points/inch):")
            print(f"  Unit ↔ Prefix: {dist_up:.1f} points ({dist_up/72*25.4:.1f} mm)")
            print(f"  Prefix ↔ Suffix: {dist_ps:.1f} points ({dist_ps/72*25.4:.1f} mm)")
            print(f"  Unit ↔ Suffix: {dist_us:.1f} points ({dist_us/72*25.4:.1f} mm)")
            print(f"\n  Clustering threshold: 25.0 mm (~71 points)")

            if dist_up / 72 * 25.4 > 25 or dist_ps / 72 * 25.4 > 25:
                print(f"  ⚠️  DISTANCE EXCEEDS THRESHOLD - Cannot cluster!")
    else:
        print("\n❌ Missing components:")
        if not units:
            print(f"  - No unit '{tag_info['unit']}' on page {page}")
        if not prefixes:
            print(f"  - No prefix '{tag_info['prefix']}' on page {page}")
        if not suffixes:
            print(f"  - No suffix '{tag_info['suffix']}' on page {page}")
