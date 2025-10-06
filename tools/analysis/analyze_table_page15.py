"""
Analyze table extraction from Installation Instruction PDF page 15
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import fitz  # PyMuPDF

# Find the PDF
pdf_path = Path(
    "D:/Data_Raw/KT06101_TURBINE_HTC/KT06101_TURBINE_HTC/Manual/KT06101_Installation instruction.pdf"
)

if not pdf_path.exists():
    print(f"PDF not found: {pdf_path}")
    print("Searching for alternative paths...")
    # Try to find it
    import json

    doc_id_map = json.load(open("artifacts/ingestion/doc_id_map.json"))
    for doc_id, path in doc_id_map.items():
        if "installation_instruction" in doc_id.lower():
            pdf_path = Path(path)
            print(f"Found: {pdf_path}")
            break

if not pdf_path.exists():
    print(f"Cannot find PDF")
    sys.exit(1)

print("=" * 70)
print("ANALYZING TABLE ON PAGE 15")
print("=" * 70)
print(f"PDF: {pdf_path.name}")

# Open PDF
doc = fitz.open(str(pdf_path))
page = doc[14]  # Page 15 (0-indexed)

print(f"\nPage: 15 (index 14)")
print(f"Size: {page.rect.width:.1f} x {page.rect.height:.1f}")

# Extract text
text = page.get_text()
print(f"\n{'='*70}")
print("RAW TEXT EXTRACTION (first 1000 chars)")
print("=" * 70)
print(text[:1000])

# Try to extract tables (PyMuPDF 1.23.0+)
print(f"\n{'='*70}")
print("TRYING PyMuPDF TABLE EXTRACTION")
print("=" * 70)

try:
    # PyMuPDF tables feature
    tabs = page.find_tables()

    if tabs.tables:
        print(f"✓ Found {len(tabs.tables)} table(s)\n")

        for i, table in enumerate(tabs.tables, 1):
            print(f"Table {i}:")
            print(f"  Rows: {table.row_count}")
            print(f"  Cols: {table.col_count}")
            print(f"  BBox: {table.bbox}")

            # Extract table data
            tab_data = table.extract()

            print(f"\n  Table content:")
            for row_idx, row in enumerate(tab_data):
                print(f"    Row {row_idx}: {row}")
                if row_idx >= 5:  # Show first 5 rows
                    print(f"    ... ({len(tab_data) - 5} more rows)")
                    break

            print()
    else:
        print("✗ No tables detected by PyMuPDF")

except AttributeError:
    print("✗ PyMuPDF version does not support find_tables()")
    print("   (Requires PyMuPDF >= 1.23.0)")
except Exception as e:
    print(f"✗ Error: {e}")

# Check for table-like text patterns
print(f"\n{'='*70}")
print("SEARCHING FOR TABLE PATTERNS IN TEXT")
print("=" * 70)

lines = text.split("\n")
table_keywords = ["M30", "M36", "M42", "M45", "M48", "M52", "M56", "M64"]
torque_values = ["510", "890", "1420", "1770", "2150", "2750", "3430", "5110"]

found_keywords = []
found_values = []

for line in lines:
    for kw in table_keywords:
        if kw in line:
            found_keywords.append((kw, line.strip()))
    for val in torque_values:
        if val in line:
            found_values.append((val, line.strip()))

print(f"\nTable column headers found: {len(found_keywords)}")
for kw, line in found_keywords[:5]:
    print(f"  {kw}: {line[:80]}")

print(f"\nTable values found: {len(found_values)}")
for val, line in found_values[:5]:
    print(f"  {val}: {line[:80]}")

# Try text extraction with different modes
print(f"\n{'='*70}")
print("TEXT EXTRACTION WITH LAYOUT PRESERVATION")
print("=" * 70)

text_blocks = page.get_text("blocks")
print(f"Found {len(text_blocks)} text blocks\n")

# Find blocks containing table keywords
table_blocks = []
for block in text_blocks:
    block_text = block[4] if len(block) > 4 else ""
    if any(kw in block_text for kw in table_keywords + ["torque", "anchor bolt"]):
        table_blocks.append(block)

print(f"Blocks with table content: {len(table_blocks)}")
for i, block in enumerate(table_blocks[:3], 1):
    x0, y0, x1, y1 = block[:4]
    block_text = block[4] if len(block) > 4 else ""
    print(f"\nBlock {i}:")
    print(f"  Position: ({x0:.1f}, {y0:.1f}, {x1:.1f}, {y1:.1f})")
    print(f"  Text: {block_text[:200]}")

doc.close()

print(f"\n{'='*70}")
print("SUMMARY")
print("=" * 70)
print("\nThe table exists on page 15 but needs proper extraction.")
print("Next step: Choose extraction method (PyMuPDF tables, Camelot, or pattern-based)")
