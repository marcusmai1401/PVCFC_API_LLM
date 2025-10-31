"""
Extract tags from page 58 with new loosened config
"""
import sys
from pathlib import Path

import fitz

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.ingestion.tags.tag_extractor import TagExtractor

# PDF path
pdf_path = Path("D:/Data_Raw/01. P&ID Ammonia Unit Rev12 (04000).pdf")

print(f"Opening PDF: {pdf_path}")

page_num = 58

print(f"\nExtracting tags from page {page_num}...")

# Build layout
builder = PageLayoutBuilder()
layout = builder.build_layout(
    pdf_path=pdf_path, page_num=page_num, doc_id="TEST_AMMONIA"
)

print(f"  Page layout: {len(layout.spans)} spans")

# Extract tags
extractor = TagExtractor()
tags = extractor.extract_tags(layout)

print(f"\nExtracted {len(tags)} tags from page {page_num}:")
print()

# Look for suffix 5058
tags_5058 = [t for t in tags if t.parts.suffix == "5058"]

if tags_5058:
    print(f"✅ Found {len(tags_5058)} tags with suffix 5058:")
    for tag in tags_5058:
        variant_str = f" {tag.parts.variant}" if tag.parts.variant else ""
        print(f"   {tag.parts.unit} {tag.parts.prefix} {tag.parts.suffix}{variant_str}")
        print(f"      Confidence: {tag.confidence:.2f}, Bbox: {tag.bbox}")
else:
    print("❌ No tags with suffix 5058 found")

# Show all TI and TT tags
print(f"\nAll TI tags on page {page_num}:")
ti_tags = [t for t in tags if t.parts.prefix == "TI"]
if ti_tags:
    for t in ti_tags:
        variant_str = f" {t.parts.variant}" if t.parts.variant else ""
        print(
            f"   {t.parts.unit} {t.parts.prefix} {t.parts.suffix}{variant_str} (conf={t.confidence:.2f})"
        )
else:
    print("   (none)")

print(f"\nAll TT tags on page {page_num}:")
tt_tags = [t for t in tags if t.parts.prefix == "TT"]
if tt_tags:
    for t in tt_tags[:10]:
        variant_str = f" {t.parts.variant}" if t.parts.variant else ""
        print(
            f"   {t.parts.unit} {t.parts.prefix} {t.parts.suffix}{variant_str} (conf={t.confidence:.2f})"
        )
    if len(tt_tags) > 10:
        print(f"   ... and {len(tt_tags) - 10} more")
else:
    print("   (none)")
