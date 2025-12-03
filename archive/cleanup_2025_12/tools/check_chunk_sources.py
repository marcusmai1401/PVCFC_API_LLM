"""
Check the source files for chunks containing 1420
"""
import json
import re
from pathlib import Path

docs_path = Path("artifacts/index_production/bm25/documents.json")
with open(docs_path, "r", encoding="utf-8") as f:
    documents = json.load(f)

# Check surrounding chunks for the table
print("=" * 80)
print("KIỂM TRA SOURCE FILE CỦA CÁC CHUNKS CHỨA BẢNG")
print("=" * 80)

for chunk_idx in [2890, 2891, 2892, 2893]:
    chunk = documents[chunk_idx]

    print(f"\nCHUNK #{chunk_idx}:")
    print("-" * 80)

    # Try to find source in frontmatter (first few lines)
    lines = chunk.split("\n")
    for i, line in enumerate(lines[:10]):
        if "source:" in line.lower():
            source = line.split("source:")[1].strip()
            print(f"Source: {Path(source).name}")
            print(f"Full path: {source}")
            break
    else:
        print("No source frontmatter found")

    # Find page marker
    page_match = re.search(r"<!-- Page (\d+) -->", chunk)
    if page_match:
        print(f"Page marker: {page_match.group(1)}")

    # Check if it has the table
    if "TABLE START" in chunk and "M42" in chunk and "1420" in chunk:
        print("*** ĐÚNG CHUNK CÓ BẢNG M42/1420 ***")

    # Show first 300 chars
    print(f"\nFirst 300 chars:")
    print(chunk[:300])
    print()
