"""
Index all pages from Ammonia PDF to spatial components index
For testing purposes - index pages needed for 7 ground truth queries
"""
import sys

sys.path.insert(0, "C:\\Users\\Admin\\Desktop\\Code - API_LLM_PVCFC")

from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.rag.spatial import SpatialComponentExtractor, SpatialComponentIndexer

pdf_path = r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf"
doc_id = "Ammonia"

# Pages needed for 7 queries: 41, 58, 17, 100, 9, 14, 20
PAGES_TO_INDEX = [9, 14, 17, 20, 41, 58, 100]

print("=" * 80)
print(f"BULK INDEXING: {len(PAGES_TO_INDEX)} pages for spatial search")
print("=" * 80)

# Initialize
builder = PageLayoutBuilder()
extractor = SpatialComponentExtractor()
indexer = SpatialComponentIndexer()

# Create index
print("\n[1] Creating index...")
indexer.create_index(recreate=False)

total_components = 0

for page_num in PAGES_TO_INDEX:
    print(f"\n[Page {page_num}]")

    try:
        # Build layout
        layout = builder.build_layout(pdf_path, page_num, doc_id)
        print(f"  Layout: {len(layout.spans)} spans")

        # Extract components
        components = extractor.extract_components(layout)
        print(f"  Extracted: {len(components)} components")

        # Delete existing
        indexer.delete_page_components(doc_id, page_num)

        # Index
        success = indexer.index_components(components)
        total_components += success
        print(f"  ✓ Indexed: {success} components")

    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        import traceback

        traceback.print_exc()

# Summary
print("\n" + "=" * 80)
print("INDEXING COMPLETE")
print("=" * 80)
print(f"Pages indexed: {len(PAGES_TO_INDEX)}")
print(f"Total components: {total_components}")

# Verify
print("\nVerifying index...")
for page_num in PAGES_TO_INDEX:
    count = indexer.get_component_count(doc_id=doc_id, page=page_num)
    print(f"  Page {page_num}: {count} components")

print("\n✓ Ready for testing!")
