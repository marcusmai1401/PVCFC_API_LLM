"""
Debug tag extraction for page 58 of Ammonia PDF
Expected: 04 TI 5058
"""
import sys

sys.path.insert(0, "C:/Users/Admin/Desktop/Code - API_LLM_PVCFC")

from pathlib import Path

import fitz

# PDF path
pdf_path = Path("D:/Data_Raw/01. P&ID Ammonia Unit Rev12 (04000).pdf")

if not pdf_path.exists():
    print(f"ERROR: PDF not found at {pdf_path}")
    sys.exit(1)

print(f"Opening PDF: {pdf_path}")
doc = fitz.open(pdf_path)

page_num = 58
print(f"\n{'='*80}")
print(f"PAGE {page_num} ANALYSIS")
print(f"{'='*80}")

page = doc[page_num - 1]  # 0-indexed

# Get page info
print(f"\nPage dimensions: {page.rect.width} x {page.rect.height}")

# Extract text spans
text_dict = page.get_text("dict")
blocks = text_dict.get("blocks", [])

# Count text spans
total_spans = 0
for block in blocks:
    if block.get("type") == 0:  # text block
        for line in block.get("lines", []):
            total_spans += len(line.get("spans", []))

print(f"Total text blocks: {len([b for b in blocks if b.get('type') == 0])}")
print(f"Total text spans: {total_spans}")

# Check if page is considered "raster" (low text content)
if total_spans < 50:
    print(
        f"\n⚠️  WARNING: Page has very few text spans ({total_spans}) - might be raster/image-based"
    )
    print("    OCR may be needed for this page")

# Search for component parts in raw text
print(f"\n{'='*80}")
print("SEARCHING FOR TAG COMPONENTS: 04, TI, 5058")
print(f"{'='*80}")

raw_text = page.get_text()

has_04 = "04" in raw_text
has_ti = "TI" in raw_text
has_5058 = "5058" in raw_text

print(f"\n  '04'   found: {has_04}")
print(f"  'TI'   found: {has_ti}")
print(f"  '5058' found: {has_5058}")

if has_5058:
    # Show all occurrences of 5058
    idx = 0
    occurrences = []
    while True:
        idx = raw_text.find("5058", idx)
        if idx == -1:
            break
        start = max(0, idx - 40)
        end = min(len(raw_text), idx + 44)
        context = raw_text[start:end].replace("\n", " ").replace("\r", " ")
        occurrences.append(context)
        idx += 1

    print(f"\n  Found {len(occurrences)} occurrence(s) of '5058':")
    for i, ctx in enumerate(occurrences, 1):
        print(f"    [{i}] ...{ctx}...")

if has_ti:
    # Count TI occurrences
    ti_count = raw_text.count("TI")
    print(f"\n  'TI' appears {ti_count} times in page text")

# Check if components appear near each other
print(f"\n{'='*80}")
print("CHECKING TAG FORMATION POTENTIAL")
print(f"{'='*80}")

if has_04 and has_ti and has_5058:
    print("\n✓ All three components (04, TI, 5058) present on page")
    print("  → Tag extraction should have found this tag")
    print("  → Likely issue: Spatial arrangement or filtering")
else:
    missing = []
    if not has_04:
        missing.append("04")
    if not has_ti:
        missing.append("TI")
    if not has_5058:
        missing.append("5058")
    print(f"\n✗ Missing components: {', '.join(missing)}")
    print("  → Cannot form tag from available text")

# Search for text "5058" in raw page text
print(f"\n{'='*80}")
print("SEARCHING RAW TEXT FOR '5058'")
print(f"{'='*80}")

raw_text = page.get_text()
if "5058" in raw_text:
    print("✓ Text '5058' found in raw page text")
    # Show context
    idx = raw_text.find("5058")
    start = max(0, idx - 30)
    end = min(len(raw_text), idx + 34)
    context = raw_text[start:end].replace("\n", " ")
    print(f"  Context: ...{context}...")
else:
    print("✗ Text '5058' NOT found in raw page text")
    print("  → Page might be image-based or text is not extractable")

doc.close()
