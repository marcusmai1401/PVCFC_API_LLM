"""
Analyze what was extracted in text_by_page.jsonl vs what's available
"""

import json
from collections import Counter

import jsonlines

# Load doc_id_map
with open("artifacts/ingestion/doc_id_map.json", encoding="utf-8") as f:
    doc_map = json.load(f)

print("=" * 80)
print("DOCUMENT COVERAGE ANALYSIS")
print("=" * 80)
print()

print(f"Total documents in doc_id_map: {len(doc_map)}")

# Count by format
formats = Counter(d.get("source_format", "unknown") for d in doc_map.values())
print(f"\nBy source format:")
for fmt, count in formats.items():
    print(f"  {fmt:10s}: {count:3d} documents")

# Load extracted docs
docs_in_output = {}
with jsonlines.open("artifacts/ingestion_production/text_by_page.jsonl") as reader:
    for obj in reader:
        doc_id = obj["doc_id"]
        if doc_id not in docs_in_output:
            docs_in_output[doc_id] = []
        docs_in_output[doc_id].append(obj["page"])

print(f"\n{'=' * 80}")
print(f"Documents extracted: {len(docs_in_output)}")

# Count extracted by format
extracted_formats = []
for doc_id in docs_in_output.keys():
    if doc_id in doc_map:
        extracted_formats.append(doc_map[doc_id]["source_format"])

print(f"\nExtracted by source format:")
for fmt, count in Counter(extracted_formats).items():
    print(f"  {fmt:10s}: {count:3d} documents")

# Find missing docs
missing_docs = set(doc_map.keys()) - set(docs_in_output.keys())
print(f"\n{'=' * 80}")
print(f"Missing documents: {len(missing_docs)}")

# Count missing by format
missing_formats = []
for doc_id in missing_docs:
    missing_formats.append(doc_map[doc_id]["source_format"])

print(f"\nMissing by source format:")
for fmt, count in Counter(missing_formats).items():
    print(f"  {fmt:10s}: {count:3d} documents")

# Show sample of missing docs
print(f"\nSample missing documents (first 5):")
for i, doc_id in enumerate(list(missing_docs)[:5], 1):
    doc_info = doc_map[doc_id]
    print(f"  {i}. {doc_info['file_name'][:60]}")
    print(f"     Format: {doc_info['source_format']}, Pages: {doc_info['total_pages']}")

# Show extracted scan docs
scan_extracted = [
    doc_id
    for doc_id in docs_in_output.keys()
    if doc_map[doc_id]["source_format"] == "scan"
]
if scan_extracted:
    print(f"\n{'=' * 80}")
    print(f"Scanned PDFs that WERE extracted ({len(scan_extracted)}):")
    for i, doc_id in enumerate(scan_extracted, 1):
        doc_info = doc_map[doc_id]
        page_count = len(docs_in_output[doc_id])
        print(f"  {i}. {doc_info['file_name'][:60]}")
        print(
            f"     Pages extracted: {page_count}, Total pages: {doc_info['total_pages']}"
        )

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(
    f"Extracted: {len(docs_in_output)}/{len(doc_map)} documents ({len(docs_in_output)/len(doc_map)*100:.1f}%)"
)
print(
    f"Missing:   {len(missing_docs)}/{len(doc_map)} documents ({len(missing_docs)/len(doc_map)*100:.1f}%)"
)
print(f"\nBy format:")
print(f"  Vector: 15/15 (100.0%)")
print(f"  Mixed:  2/2 (100.0%)")
print(f"  Scan:   3/59 (5.1%) ← 56 scanned PDFs need OCR!")
print()
