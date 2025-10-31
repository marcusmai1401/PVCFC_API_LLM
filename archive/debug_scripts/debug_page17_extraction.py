"""
Debug page 17 extraction for missing tag 04 TXI 2077
Check raw text, elements, and tag grammar matching
"""
import sys

sys.path.insert(0, "C:\\Users\\Admin\\Desktop\\Code - API_LLM_PVCFC")

import fitz  # PyMuPDF

from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.ingestion.tags.tag_extractor import TagExtractor

pdf_path = r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf"
page_num = 17
doc_id = "Ammonia"

print("=" * 80)
print(f"DEBUG: Page {page_num} - Looking for '04 TXI 2077'")
print("=" * 80)

# Step 1: Raw text extraction
print("\n[STEP 1] Raw PDF text on page 17:")
print("-" * 80)
doc = fitz.open(pdf_path)
page = doc[page_num - 1]  # 0-indexed
raw_text = page.get_text()
print(raw_text[:2000])  # First 2000 chars
print("\nSearching for components:")
print(f"  '04' found: {'04' in raw_text}")
print(f"  'TXI' found: {'TXI' in raw_text}")
print(f"  '2077' found: {'2077' in raw_text}")
print(f"  '04 TXI 2077' found: {'04 TXI 2077' in raw_text}")

# Step 2: Check text blocks
print("\n[STEP 2] Text blocks on page 17:")
print("-" * 80)
blocks = page.get_text("blocks")
txi_blocks = []
for block in blocks:
    text = block[4] if len(block) > 4 else ""
    if "TXI" in text or "2077" in text or "04" in text:
        txi_blocks.append({"bbox": block[:4], "text": text.strip()})

print(f"Found {len(txi_blocks)} blocks containing '04', 'TXI', or '2077':")
for i, block in enumerate(txi_blocks[:20], 1):
    print(f"{i}. [{block['bbox']}] {repr(block['text'][:100])}")

# Step 3: Page layout builder
print("\n[STEP 3] Page layout elements:")
print("-" * 80)
builder = PageLayoutBuilder()
page_layout = builder.build_layout(pdf_path, page_num, doc_id)
print(f"Total text elements: {len(page_layout.elements)}")

# Find elements with target components
target_elements = []
for elem in page_layout.elements:
    text = elem.text.upper()
    if any(keyword in text for keyword in ["04", "TXI", "TSAH", "2077"]):
        target_elements.append(elem)

print(f"\nElements containing '04', 'TXI', 'TSAH', or '2077': {len(target_elements)}")
for i, elem in enumerate(target_elements[:30], 1):
    print(f"{i}. {elem.text:<30} bbox:{elem.bbox}")

# Step 4: Tag extraction
print("\n[STEP 4] Extracted tags:")
print("-" * 80)
extractor = TagExtractor()
tags = extractor.extract_tags(page_layout)
print(f"Total extracted tags: {len(tags)}")

# Search for target
target_found = False
tsah_found = False
for tag in tags:
    tag_text = f"{tag.parts.unit} {tag.parts.prefix} {tag.parts.suffix}".strip()
    if "TXI" in tag_text or "TSAH" in tag_text or "2077" in tag_text:
        print(f"  → {tag_text} (confidence: {tag.confidence:.2f})")
        if tag_text == "04 TXI 2077":
            target_found = True
            print(f"    ✓ TARGET 'TXI' FOUND!")
        if tag_text == "04 TSAH 2077":
            tsah_found = True
            print(f"    ✓ FOUND 'TSAH 2077' (not TXI!)")

# Step 5: Manual pattern search in elements
print("\n[STEP 5] Manual pattern matching:")
print("-" * 80)
print("Looking for pattern: 04 + TXI + 2077 within proximity")

# Group elements by Y coordinate (same line)
from collections import defaultdict

lines = defaultdict(list)
for elem in page_layout.elements:
    y_pos = int(elem.bbox[1] / 5) * 5  # Group by 5pt buckets
    lines[y_pos].append(elem)

# Check each line for the pattern
for y_pos in sorted(lines.keys()):
    line_elems = sorted(lines[y_pos], key=lambda e: e.bbox[0])
    line_text = " ".join([e.text for e in line_elems])

    if any(x in line_text.upper() for x in ["TXI", "TSAH", "2077"]):
        print(f"\nLine at Y={y_pos}: {line_text[:150]}")

        # Check if 04, TXI/TSAH, 2077 are in this line
        has_04 = "04" in line_text
        has_txi = "TXI" in line_text.upper()
        has_tsah = "TSAH" in line_text.upper()
        has_2077 = "2077" in line_text

        if has_04 and (has_txi or has_tsah) and has_2077:
            prefix_type = "TXI" if has_txi else "TSAH"
            print(f"  ★★★ POTENTIAL MATCH: Line contains 04 + {prefix_type} + 2077!")
            print(f"      Elements on this line:")
            for elem in line_elems:
                print(f"        - '{elem.text}' at x={elem.bbox[0]:.1f}")

# Step 6: Check annotations/drawings
print("\n[STEP 6] Check for annotations/symbols:")
print("-" * 80)
annots = page.annots()
if annots:
    for annot in annots:
        print(f"  Annotation: {annot.type} - {annot.info}")
else:
    print("  No annotations found")

# Check for drawing objects
drawings = page.get_drawings()
print(f"\nDrawing objects: {len(drawings)}")

print("\n" + "=" * 80)
print("CONCLUSION:")
print("=" * 80)
if target_found:
    print("✓ Tag '04 TXI 2077' was successfully extracted")
elif tsah_found:
    print("⚠ Found '04 TSAH 2077' instead of '04 TXI 2077'")
    print("\nThis means:")
    print("  - The tag in the PDF is actually 'TSAH 2077' not 'TXI 2077'")
    print("  - Ground truth may have incorrect prefix")
    print("  - Or OCR/visual similarity: I vs H, X vs S")
else:
    print("✗ Tag '04 TXI 2077' NOT extracted (neither TXI nor TSAH found)")
    print("\nPossible reasons:")
    print("  1. Components are too far apart spatially")
    print("  2. Text is in symbol/annotation layer (not regular text)")
    print("  3. Tag grammar confidence threshold too high")
    print("  4. Font/styling causes text extraction issues")
    print("\nCheck the manual pattern search above for clues.")

doc.close()
