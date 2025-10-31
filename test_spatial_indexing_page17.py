"""
Test: Extract and index spatial components from page 17
Verify that 04, TXI, 2077 are indexed correctly
"""
import sys

sys.path.insert(0, "C:\\Users\\Admin\\Desktop\\Code - API_LLM_PVCFC")

from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.rag.spatial import SpatialComponentExtractor, SpatialComponentIndexer

pdf_path = r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf"
doc_id = "Ammonia"
page_num = 17

print("=" * 80)
print(f"TEST: Index Spatial Components - Page {page_num}")
print("=" * 80)

# Step 1: Build page layout
print("\n[1] Building page layout...")
builder = PageLayoutBuilder()
layout = builder.build_layout(pdf_path, page_num, doc_id)
print(f"✓ Page layout built: {len(layout.spans)} spans")

# Step 2: Extract components
print("\n[2] Extracting components...")
extractor = SpatialComponentExtractor()
components = extractor.extract_components(layout)

print(f"✓ Extracted {len(components)} components:")
print(f"  - Units: {sum(1 for c in components if c.component_type == 'unit')}")
print(f"  - Prefixes: {sum(1 for c in components if c.component_type == 'prefix')}")
print(f"  - Suffixes: {sum(1 for c in components if c.component_type == 'suffix')}")

# Show target components
target_components = ["04", "TXI", "2077"]
found = {t: False for t in target_components}

print(f"\nLooking for target components: {target_components}")
for comp in components:
    if comp.text in target_components:
        found[comp.text] = True
        print(f"  ✓ Found '{comp.text}' ({comp.component_type}) at {comp.bbox}")

for text, is_found in found.items():
    if not is_found:
        print(f"  ✗ Missing '{text}'")

# Step 3: Create index
print("\n[3] Creating OpenSearch index...")
indexer = SpatialComponentIndexer()
indexer.create_index(recreate=False)

# Step 4: Delete existing page 17 components
print(f"\n[4] Deleting existing page {page_num} components...")
indexer.delete_page_components(doc_id, page_num)

# Step 5: Index new components
print(f"\n[5] Indexing {len(components)} components...")
success = indexer.index_components(components)
print(f"✓ Indexed {success} components")

# Step 6: Verify indexing
print("\n[6] Verifying indexed components...")

for target in target_components:
    results = indexer.search_components(
        component_text=target, doc_id=doc_id, page=page_num
    )

    if results:
        print(f"  ✓ '{target}' indexed: {len(results)} occurrences")
        for r in results:
            print(f"      Type: {r['component_type']}, BBox: {r['bbox']}")
    else:
        print(f"  ✗ '{target}' NOT found in index!")

# Step 7: Count total
print("\n[7] Final statistics:")
total = indexer.get_component_count(doc_id=doc_id, page=page_num)
print(f"  Total components on page {page_num}: {total}")

print("\n" + "=" * 80)
print("TEST COMPLETE!")
print("=" * 80)

# Success criteria
all_found = all(found.values())
if all_found and success == len(components):
    print("✓ SUCCESS: All target components found and indexed")
else:
    print("✗ FAILED: Some components missing")
    sys.exit(1)
