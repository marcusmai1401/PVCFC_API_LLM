"""
Comprehensive check for 1420 in documents
"""
import json
import re
from pathlib import Path

docs_path = Path("artifacts/index_production/bm25/documents.json")
with open(docs_path, "r", encoding="utf-8") as f:
    documents = json.load(f)

print(f"Searching in {len(documents)} documents...\n")

# Find docs containing 1420
matches = []
for i, doc in enumerate(documents):
    if isinstance(doc, str) and "1420" in doc:
        matches.append((i, doc))

print(f'Found {len(matches)} documents containing "1420"\n')
print("=" * 80)
print("ALL CHUNKS WITH 1420:")
print("=" * 80)

for idx, doc in matches:
    print(f"\n[Chunk #{idx}]")

    # Extract page marker
    page_match = re.search(r"<!-- Page (\d+) -->", doc)
    page_num = page_match.group(1) if page_match else "Unknown"

    # Extract source
    source_match = re.search(r"source: (.+)", doc)
    if source_match:
        source = source_match.group(1).strip()
        filename = Path(source).name
        print(f"Source: {filename}")
        print(f"Page: {page_num}")

    # Check if it's the table
    if "TABLE START" in doc:
        print("*** THIS IS THE TABLE CHUNK! ***")

    # Show snippet
    print("Content preview (600 chars):")
    print(doc[:600])
    print("-" * 80)

# Now check doc_id_map
print("\n\n" + "=" * 80)
print("DOC_ID MAP - Installation Instruction")
print("=" * 80)

doc_id_map_path = Path("artifacts/ingestion/doc_id_map.json")
if doc_id_map_path.exists():
    with open(doc_id_map_path, "r", encoding="utf-8") as f:
        doc_id_map = json.load(f)

    for doc_id, pdf_path in doc_id_map.items():
        if "Installation" in pdf_path and "instruction" in pdf_path:
            print(f"\nDoc ID: {doc_id}")
            print(f"PDF: {pdf_path}")
