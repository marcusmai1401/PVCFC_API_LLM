"""
Analyze chunks to understand page metadata and content issues
"""
import json
from pathlib import Path

# Load BM25 documents
bm25_docs_path = Path("artifacts/index/bm25/documents.json")
with open(bm25_docs_path, encoding="utf-8") as f:
    raw_data = json.load(f)

# Check format - it might be a list of strings or list of dicts
if isinstance(raw_data, list) and len(raw_data) > 0:
    print(f"Loaded {len(raw_data)} documents")
    print(f"First doc type: {type(raw_data[0])}")
    if isinstance(raw_data[0], str):
        print("Documents stored as strings - need to parse differently")
        print(f"First doc preview: {raw_data[0][:200]}")
    elif isinstance(raw_data[0], dict):
        print(f"Documents stored as dicts with keys: {list(raw_data[0].keys())}")
        documents = raw_data
    else:
        print(f"Unknown doc format: {type(raw_data[0])}")
else:
    print("Unexpected data format")
    documents = []

# Find chunks related to condensing turbine installation
matching_chunks = []
for doc in documents:
    if isinstance(doc, dict):
        text = doc.get("text", "").lower()
        if "installation of condensing turbine" in text and "back grouting" in text:
            matching_chunks.append(doc)

print(f"Found {len(matching_chunks)} matching chunks\n")
print("=" * 100)

for i, chunk in enumerate(matching_chunks[:10], 1):
    metadata = chunk.get("metadata", {})
    print(f"\n[{i}] CHUNK ANALYSIS")
    print(f"Chunk ID: {chunk.get('chunk_id', 'N/A')}")
    print(f"Doc ID: {metadata.get('doc_id', 'N/A')}")
    print(f"Page: {metadata.get('page', 'N/A')}")
    print(f"Page Start: {metadata.get('page_start', 'N/A')}")
    print(f"Page End: {metadata.get('page_end', 'N/A')}")
    print(f"\nText preview (first 400 chars):")
    print(chunk.get("text", "")[:400])
    print("\n" + "=" * 100)

# Also check for table/torque related chunks
print("\n\n" + "=" * 100)
print("SEARCHING FOR TABLE/TORQUE CHUNKS")
print("=" * 100)

torque_chunks = []
for doc in documents:
    text = doc.get("text", "").lower()
    metadata = doc.get("metadata", {})
    doc_id = metadata.get("doc_id", "")

    # Look for torque table content
    if "installation_instruction" in doc_id and (
        "torque" in text or "anchor bolt" in text
    ):
        torque_chunks.append(doc)

print(f"\nFound {len(torque_chunks)} torque-related chunks")

for i, chunk in enumerate(torque_chunks[:10], 1):
    metadata = chunk.get("metadata", {})
    print(f"\n[{i}] TORQUE CHUNK")
    print(f"Chunk ID: {chunk.get('chunk_id', 'N/A')}")
    print(f"Page: {metadata.get('page', 'N/A')}")
    print(f"\nText preview (first 500 chars):")
    print(chunk.get("text", "")[:500])
    print("\n" + "-" * 80)

# Check doc_id_map to understand doc-to-file mapping
doc_id_map_path = Path("artifacts/ingestion/doc_id_map.json")
if doc_id_map_path.exists():
    with open(doc_id_map_path, encoding="utf-8") as f:
        doc_id_map = json.load(f)

    print("\n\n" + "=" * 100)
    print("DOC_ID_MAP ENTRIES (Installation instruction)")
    print("=" * 100)

    for doc_id, pdf_path in doc_id_map.items():
        if "installation" in doc_id.lower():
            print(f"\nDoc ID: {doc_id}")
            print(f"PDF Path: {pdf_path}")
