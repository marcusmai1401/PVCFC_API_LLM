"""
Analyze BM25 chunks to understand page metadata issues
"""
import json
from pathlib import Path

# Load texts and metadata separately
texts_path = Path("artifacts/index/bm25/texts.json")
metadata_path = Path("artifacts/index/bm25/metadata.json")

with open(texts_path, encoding="utf-8") as f:
    texts = json.load(f)

with open(metadata_path, encoding="utf-8") as f:
    metadata_list = json.load(f)

print(f"Loaded {len(texts)} texts and {len(metadata_list)} metadata entries\n")

# Reconstruct documents
documents = []
for i, (text, meta) in enumerate(zip(texts, metadata_list)):
    documents.append({"text": text, "metadata": meta})

# Find chunks related to "installation of condensing turbine" + "back grouting"
print("=" * 100)
print("SEARCHING: Installation of Condensing Turbine + Back Grouting")
print("=" * 100)

matching_chunks = []
for doc in documents:
    text_lower = doc["text"].lower()
    if (
        "installation of condensing turbine" in text_lower
        and "back grouting" in text_lower
    ):
        matching_chunks.append(doc)

print(f"\nFound {len(matching_chunks)} matching chunks\n")

for i, chunk in enumerate(matching_chunks[:5], 1):
    meta = chunk["metadata"]
    print(f"\n[{i}] CHUNK")
    print(f"Chunk ID: {meta.get('chunk_id', 'N/A')}")
    print(f"Doc ID: {meta.get('doc_id', 'N/A')}")
    print(f"Page: {meta.get('page', 'N/A')}")
    print(f"Heading: {meta.get('heading', 'N/A')}")
    print(f"\nText (first 500 chars):")
    print(chunk["text"][:500])
    print("\n" + "-" * 100)

# Search for torque/anchor bolt related chunks
print("\n\n" + "=" * 100)
print("SEARCHING: Torque + Anchor Bolt (in Installation Instruction doc)")
print("=" * 100)

torque_chunks = []
for doc in documents:
    meta = doc["metadata"]
    text_lower = doc["text"].lower()
    doc_id = meta.get("doc_id", "")

    if "installation_instruction" in doc_id.lower():
        if "torque" in text_lower or "anchor bolt" in text_lower:
            torque_chunks.append(doc)

print(f"\nFound {len(torque_chunks)} torque-related chunks\n")

# Show all chunks with  pages >= 10
high_page_torque = [c for c in torque_chunks if c["metadata"].get("page", 0) >= 10]
print(f"Chunks on page >= 10: {len(high_page_torque)}\n")

for i, chunk in enumerate(torque_chunks[:15], 1):
    meta = chunk["metadata"]
    page = meta.get("page", "N/A")
    print(f"\n[{i}] Page {page}")
    print(f"Chunk ID: {meta.get('chunk_id', 'N/A')}")
    print(f"Heading: {meta.get('heading', 'N/A')}")
    print(f"\nText (first 400 chars):")
    print(chunk["text"][:400])
    print("\n" + "-" * 80)

# Check if table values are in the chunks
print("\n\n" + "=" * 100)
print("CHECKING: Are table values (M30, M36, 510, 890, etc.) in any chunk?")
print("=" * 100)

table_keywords = [
    "m30",
    "m36",
    "m42",
    "m45",
    "m48",
    "m52",
    "m56",
    "m64",
    "510",
    "890",
    "1420",
    "1770",
]
table_chunks = []

for doc in documents:
    meta = doc["metadata"]
    text_lower = doc["text"].lower()
    doc_id = meta.get("doc_id", "")

    if "installation_instruction" in doc_id.lower():
        # Check if chunk contains multiple table keywords (likely a table)
        matches = sum(1 for kw in table_keywords if kw in text_lower)
        if matches >= 3:  # At least 3 keywords
            table_chunks.append((doc, matches))

table_chunks.sort(key=lambda x: x[1], reverse=True)  # Sort by match count
print(f"\nFound {len(table_chunks)} chunks with table-like content\n")

for i, (chunk, match_count) in enumerate(table_chunks[:5], 1):
    meta = chunk["metadata"]
    print(f"\n[{i}] POTENTIAL TABLE CHUNK (matches: {match_count})")
    print(f"Page: {meta.get('page', 'N/A')}")
    print(f"Chunk ID: {meta.get('chunk_id', 'N/A')}")
    print(f"Heading: {meta.get('heading', 'N/A')}")
    print(f"\nFull text:")
    print(chunk["text"])
    print("\n" + "=" * 100)
