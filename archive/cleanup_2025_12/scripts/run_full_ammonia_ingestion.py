"""
Full ingestion for Ammonia PDF with new config (threshold=4, loosened tolerances)
"""
import json
import sys
from pathlib import Path

from tqdm import tqdm

# Add project root to path (handle both root and scripts/ingestion execution)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import fitz

from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.ingestion.tags.tag_extractor import TagExtractor

# Setup
pdf_path = Path("D:/Data_Raw/01. P&ID Ammonia Unit Rev12 (04000).pdf")
output_dir = Path("output/pid_ingestion")
output_dir.mkdir(parents=True, exist_ok=True)

tags_output = output_dir / "tags.jsonl"

print(f"Ingesting: {pdf_path.name}")
print(f"Output: {tags_output}")
print()

# Open PDF
doc = fitz.open(pdf_path)
total_pages = len(doc)

print(f"Total pages: {total_pages}")
print("Starting extraction...")
print()

# Initialize
builder = PageLayoutBuilder(enable_ocr=True)
extractor = TagExtractor()

all_tags = []

# Process each page
for page_num in tqdm(range(1, total_pages + 1), desc="Extracting"):
    try:
        # Build layout
        layout = builder.build_layout(
            pdf_path=pdf_path, page_num=page_num, doc_id="AMMONIA"
        )

        # Extract tags
        tags = extractor.extract_tags(layout)

        # Convert to dict and add to list
        for tag in tags:
            tag_dict = {
                "doc_id": tag.doc_id,
                "page": tag.page,
                "tag": tag.tag,
                "unit": tag.parts.unit,
                "prefix": tag.parts.prefix,
                "suffix": tag.parts.suffix,
                "variant": tag.parts.variant,
                "annotation": tag.parts.annotation,
                "bbox": tag.bbox,
                "confidence": tag.confidence,
                "has_variant": tag.has_variant,
                "has_annotation": tag.has_annotation,
            }
            all_tags.append(tag_dict)

    except Exception as e:
        print(f"\nError on page {page_num}: {e}")
        continue

doc.close()

# Save tags
print(f"\nWriting {len(all_tags)} tags to {tags_output}")
with open(tags_output, "w", encoding="utf-8") as f:
    for tag in all_tags:
        f.write(json.dumps(tag, ensure_ascii=False) + "\n")

print("\n✅ Ingestion complete!")
print(f"   Total tags: {len(all_tags)}")

# Show stats
pages_with_tags = len(set(t["page"] for t in all_tags))
print(f"   Pages with tags: {pages_with_tags}/{total_pages}")

# Check for target tag
target_tags = [
    t
    for t in all_tags
    if t["unit"] == "04" and t["prefix"] == "TI" and t["suffix"] == "5058"
]
if target_tags:
    print(f"\n✅ Target tag '04 TI 5058' found on page {target_tags[0]['page']}")
else:
    print(f"\n❌ Target tag '04 TI 5058' NOT found")
