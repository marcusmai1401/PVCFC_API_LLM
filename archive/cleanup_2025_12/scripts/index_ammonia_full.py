"""
Production Indexing Script
Index all 117 pages of Ammonia PDF for spatial search
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.rag.spatial import SpatialComponentExtractor, SpatialComponentIndexer

# Configuration
PDF_PATH = r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf"
DOC_ID = "Ammonia"
TOTAL_PAGES = 117  # Total pages in Ammonia PDF

# Option to index subset for testing
START_PAGE = 1
END_PAGE = TOTAL_PAGES  # Change to smaller number for testing

print("=" * 80)
print("PRODUCTION INDEXING: Ammonia Unit P&ID")
print("=" * 80)
print(f"PDF: {PDF_PATH}")
print(f"Pages: {START_PAGE} to {END_PAGE}")
print("=" * 80)

# Initialize
builder = PageLayoutBuilder()
extractor = SpatialComponentExtractor()
indexer = SpatialComponentIndexer()

# Create/verify index
print("\n[SETUP] Creating index...")
indexer.create_index(recreate=False)
print("✓ Index ready")

# Statistics
total_components = 0
total_time = 0
errors = []
success_pages = []

print(f"\n[INDEXING] Processing {END_PAGE - START_PAGE + 1} pages...\n")

for page_num in range(START_PAGE, END_PAGE + 1):
    start_time = time.time()

    try:
        # Build layout
        layout = builder.build_layout(PDF_PATH, page_num, DOC_ID)

        # Extract components
        components = extractor.extract_components(layout)

        # Delete existing (for re-indexing)
        indexer.delete_page_components(DOC_ID, page_num)

        # Index
        success = indexer.index_components(components)

        elapsed = time.time() - start_time
        total_time += elapsed
        total_components += success
        success_pages.append(page_num)

        # Progress indicator
        if page_num % 10 == 0 or page_num == END_PAGE:
            print(
                f"  Page {page_num:3d}/{END_PAGE}: {success:3d} components ({elapsed:.1f}s)"
            )

    except Exception as e:
        elapsed = time.time() - start_time
        total_time += elapsed
        errors.append({"page": page_num, "error": str(e)})
        print(f"  Page {page_num:3d}/{END_PAGE}: ERROR - {e}")

# Summary
print("\n" + "=" * 80)
print("INDEXING COMPLETE")
print("=" * 80)
print(
    f"Pages processed: {len(success_pages) + len(errors)}/{END_PAGE - START_PAGE + 1}"
)
print(f"Success: {len(success_pages)}")
print(f"Errors: {len(errors)}")
print(f"Total components: {total_components:,}")
print(f"Total time: {total_time:.1f}s")
print(f"Avg time/page: {total_time/(END_PAGE - START_PAGE + 1):.2f}s")

if errors:
    print(f"\nErrors on {len(errors)} pages:")
    for err in errors[:10]:  # Show first 10
        print(f"  Page {err['page']}: {err['error']}")
    if len(errors) > 10:
        print(f"  ... and {len(errors) - 10} more")

# Verify total
print("\n[VERIFICATION] Checking index...")
total_indexed = indexer.get_component_count(doc_id=DOC_ID)
print(f"Total components in index: {total_indexed:,}")

print("\n✓ PRODUCTION INDEXING COMPLETE!")
print(f"\nTo test, run: python test_7_queries_spatial.py")
