import json
import os
from pathlib import Path

print("=" * 80)
print("VALIDATING RE-INGESTION RESULTS")
print("=" * 80)

# 1. Check chunks.jsonl exists and count chunks
chunks_file = Path("artifacts/ingestion_production/chunks/chunks.jsonl")
if chunks_file.exists():
    with open(chunks_file, "r", encoding="utf-8") as f:
        chunks = [json.loads(line) for line in f]
    print(f"\n✓ Chunks file found: {len(chunks)} chunks")

    # Sample first chunk to check metadata
    if chunks:
        sample = chunks[0]
        print(f"\nSample chunk metadata:")
        print(f"  - doc_id: {sample.get('doc_id', 'N/A')[:60]}...")
        print(f"  - file_name: {sample.get('file_name', 'N/A')}")
        print(f"  - page_num: {sample.get('page_num', 'N/A')}")
        print(f"  - chunk_index: {sample.get('chunk_index', 'N/A')}")
else:
    print("\n✗ Chunks file not found!")

# 2. Check doc_id_map
doc_map_file = Path("artifacts/ingestion_production/doc_id_map.json")
if doc_map_file.exists():
    with open(doc_map_file, "r", encoding="utf-8") as f:
        doc_map = json.load(f)
    print(f"\n✓ Doc ID map found: {len(doc_map)} documents")
else:
    print("\n✗ Doc ID map not found!")

# 3. Check for previously identified problem documents
print("\n" + "=" * 80)
print("CHECKING PREVIOUSLY PROBLEMATIC DOCUMENTS")
print("=" * 80)

problem_docs = [
    ("MANUAL(COMPRESSOR)l.pdf", "Expected: 1437 pages"),
    ("K03-K04  O&M.pdf", "Expected: 1437 pages"),
    ("Operating Manual KT06101_0-2520-8043-00-en.pdf", "Expected: 281 pages"),
]

for filename, expected in problem_docs:
    # Find doc_id for this file
    matching_docs = [doc_id for doc_id, path in doc_map.items() if filename in path]

    if matching_docs:
        doc_id = matching_docs[0]
        # Count chunks for this document
        doc_chunks = [c for c in chunks if c.get("doc_id") == doc_id]
        if doc_chunks:
            max_page = max(c.get("page_num", 0) for c in doc_chunks)
            print(f"\n✓ {filename}")
            print(f"  Doc ID: {doc_id[:50]}...")
            print(f"  Chunks: {len(doc_chunks)}")
            print(f"  Max page num in chunks: {max_page}")
            print(f"  {expected}")
        else:
            print(f"\n⚠ {filename}: No chunks found!")
    else:
        print(f"\n⚠ {filename}: Not found in doc_id_map")

# 4. Check overall statistics
print("\n" + "=" * 80)
print("OVERALL STATISTICS")
print("=" * 80)

total_pages_referenced = set()
for chunk in chunks:
    doc_id = chunk.get("doc_id")
    page_num = chunk.get("page_num")
    if doc_id and page_num is not None:
        total_pages_referenced.add((doc_id, page_num))

print(f"\nTotal unique (doc_id, page_num) pairs: {len(total_pages_referenced)}")
print(f"Average chunks per document: {len(chunks) / len(doc_map):.1f}")

# Group by document
chunks_per_doc = {}
for chunk in chunks:
    doc_id = chunk.get("doc_id")
    if doc_id:
        chunks_per_doc[doc_id] = chunks_per_doc.get(doc_id, 0) + 1

if chunks_per_doc:
    max_chunks = max(chunks_per_doc.values())
    max_doc = [k for k, v in chunks_per_doc.items() if v == max_chunks][0]
    print(f"\nDocument with most chunks: {max_chunks} chunks")
    print(f"  Doc ID: {max_doc[:60]}...")

print("\n" + "=" * 80)
print("✓ VALIDATION COMPLETE")
print("=" * 80)
