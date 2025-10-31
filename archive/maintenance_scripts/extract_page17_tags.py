"""
Extract tags from page 17 to verify if 04 TXI 2077 exists
"""
import sys

sys.path.insert(0, "C:\\Users\\Admin\\Desktop\\Code - API_LLM_PVCFC")

from app.config import get_config
from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.ingestion.tags.tag_extractor import TagExtractor

config = get_config()
pdf_path = "C:\\Users\\Admin\\Desktop\\Code - API_LLM_PVCFC\\assets\\pdfs\\Ammonia_Unit_P&ID.pdf"
page_num = 17
doc_id = "Ammonia"

print("=" * 80)
print(f"Extracting tags from {doc_id} page {page_num}")
print("=" * 80)

# Build page layout
print("\n[1] Building page layout...")
builder = PageLayoutBuilder()
page_layout = builder.build_layout(pdf_path, page_num, doc_id)
print(f"✓ Page layout built - found {len(page_layout.text_elements)} text elements")

# Extract tags
print("\n[2] Extracting tags...")
extractor = TagExtractor()
tags = extractor.extract_tags(page_layout)
print(f"✓ Extracted {len(tags)} tags\n")

# Display all tags
print(f"All {len(tags)} tags on page {page_num}:")
print("-" * 80)

tag_texts = []
for i, tag in enumerate(tags, 1):
    tag_text = f"{tag.parts.unit} {tag.parts.prefix} {tag.parts.suffix}"
    if tag.parts.variant:
        tag_text += tag.parts.variant
    tag_texts.append(tag_text.strip())
    print(f"{i:3}. {tag_text.strip():<20} (confidence: {tag.confidence:.2f})")

# Search for target
print("\n" + "=" * 80)
print("SEARCH RESULTS:")
print("=" * 80)

target = "04 TXI 2077"
if target in tag_texts:
    print(f"✓ Found '{target}' on page {page_num}")
else:
    print(f"✗ Tag '{target}' NOT FOUND on page {page_num}")

    # Look for similar tags
    txi_tags = [t for t in tag_texts if "TXI" in t]
    if txi_tags:
        print(f"\nTXI tags found on this page: {txi_tags}")

    suffix_2077_tags = [t for t in tag_texts if "2077" in t]
    if suffix_2077_tags:
        print(f"\nTags with suffix 2077 on this page: {suffix_2077_tags}")

    # Look for unit 04 tags
    unit_04_tags = [t for t in tag_texts if t.startswith("04 ")]
    print(f"\nAll Unit 04 tags on this page ({len(unit_04_tags)} total):")
    for tag in sorted(unit_04_tags)[:20]:  # Show first 20
        print(f"  - {tag}")
