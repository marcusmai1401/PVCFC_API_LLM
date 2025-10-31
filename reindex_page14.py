"""Re-index page 14 after fixing single-letter prefix support"""
import sys

sys.path.insert(0, "C:\\Users\\Admin\\Desktop\\Code - API_LLM_PVCFC")

from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.rag.spatial import SpatialComponentExtractor, SpatialComponentIndexer

pdf_path = r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf"
page_num = 14
doc_id = "Ammonia"

print("Re-indexing page 14 with updated extractor...")

builder = PageLayoutBuilder()
extractor = SpatialComponentExtractor()
indexer = SpatialComponentIndexer()

# Extract
layout = builder.build_layout(pdf_path, page_num, doc_id)
components = extractor.extract_components(layout)

# Count single-letter prefixes
single_letter_prefixes = [
    c for c in components if c.component_type == "prefix" and len(c.text) == 1
]
i_prefixes = [c for c in components if c.text == "I" and c.component_type == "prefix"]

print(f"Total components: {len(components)}")
print(f"Single-letter prefixes: {len(single_letter_prefixes)}")
print(f"'I' prefixes found: {len(i_prefixes)}")

if i_prefixes:
    print("\n'I' prefix locations:")
    for comp in i_prefixes:
        print(f"  {comp.text} at {comp.bbox}")

# Re-index
indexer.delete_page_components(doc_id, page_num)
success = indexer.index_components(components)

print(f"\n✓ Re-indexed page {page_num}: {success} components")
