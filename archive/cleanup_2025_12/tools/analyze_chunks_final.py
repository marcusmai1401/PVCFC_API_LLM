"""
Final analysis script - use documents.json correctly
"""
import json
from pathlib import Path

# Load documents and metadata
docs_path = Path("artifacts/index/bm25/documents.json")
metadata_path = Path("artifacts/index/bm25/metadata.json")

with open(docs_path, encoding="utf-8") as f:
    documents_text = json.load(f)

with open(metadata_path, encoding="utf-8") as f:
    metadata_list = json.load(f)

print(
    f"Loaded {len(documents_text)} document texts and {len(metadata_list)} metadata entries\n"
)

# Combine
documents = []
for text, meta in zip(documents_text, metadata_list):
    documents.append({"text": text, "metadata": meta})

# 1) Find "Installation of Condensing Turbine" + "back grouting"
print("=" * 100)
print("SEARCH 1: Installation of Condensing Turbine + Back Grouting")
print("=" * 100)

matches = []
for doc in documents:
    txt_lower = doc["text"].lower()
    if (
        "installation of condensing turbine" in txt_lower
        and "back grouting" in txt_lower
    ):
        matches.append(doc)

print(f"\nFound {len(matches)} matching chunks\n")

for i, chunk in enumerate(matches[:5], 1):
    meta = chunk["metadata"]
    print(f"\n[{i}] CHUNK")
    print(f"Chunk ID: {meta.get('chunk_id', 'N/A')}")
    print(f"Doc ID: {meta.get('doc_id', 'N/A')}")
    print(f"Page: {meta.get('page', 'N/A')}")
    print(f"\nText (first 500 chars):")
    print(chunk["text"][:500])
    print("\n" + "-" * 100)

# 2) Find torque/anchor bolt chunks in Installation Instruction
print("\n\n" + "=" * 100)
print("SEARCH 2: Torque + Anchor Bolt (Installation Instruction doc)")
print("=" * 100)

torque_chunks = []
for doc in documents:
    meta = doc["metadata"]
    doc_id = meta.get("doc_id", "")
    txt_lower = doc["text"].lower()

    if "installation_instruction" in doc_id.lower():
        if "torque" in txt_lower or "anchor bolt" in txt_lower:
            torque_chunks.append(doc)

print(f"\nFound {len(torque_chunks)} torque-related chunks\n")

high_page = [c for c in torque_chunks if c["metadata"].get("page", 0) >= 10]
print(f"Chunks on page >= 10: {len(high_page)}\n")

for i, chunk in enumerate(torque_chunks[:20], 1):
    meta = chunk["metadata"]
    page = meta.get("page", "N/A")
    print(f"\n[{i}] Page {page}")
    print(f"Chunk ID: {meta.get('chunk_id', 'N/A')}")
    print(f"\nText (first 300 chars):")
    print(chunk["text"][:300])
    print("\n" + "-" * 80)

# 3) Check for table content with specific values
print("\n\n" + "=" * 100)
print("SEARCH 3: Table values (M30, M36, 510, 890, 1420, 1770, etc.)")
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
    "2150",
    "2750",
]
table_chunks = []

for doc in documents:
    meta = doc["metadata"]
    doc_id = meta.get("doc_id", "")
    txt_lower = doc["text"].lower()

    if "installation_instruction" in doc_id.lower():
        match_count = sum(1 for kw in table_keywords if kw in txt_lower)
        if match_count >= 4:  # At least 4 keywords (indicates table row)
            table_chunks.append((doc, match_count))

table_chunks.sort(key=lambda x: x[1], reverse=True)
print(f"\nFound {len(table_chunks)} chunks with table-like content\n")

for i, (chunk, match_count) in enumerate(table_chunks[:8], 1):
    meta = chunk["metadata"]
    print(f"\n[{i}] TABLE CHUNK (keyword matches: {match_count})")
    print(f"Page: {meta.get('page', 'N/A')}")
    print(f"Chunk ID: {meta.get('chunk_id', 'N/A')}")
    print(f"\nFull text:")
    print(chunk["text"])
    print("\n" + "=" * 100)

# 4) Specifically check for page 15 (where the table should be)
print("\n\n" + "=" * 100)
print("SEARCH 4: All chunks from page 15 (Installation Instruction)")
print("=" * 100)

page15_chunks = []
for doc in documents:
    meta = doc["metadata"]
    doc_id = meta.get("doc_id", "")
    page = meta.get("page", None)

    if "installation_instruction" in doc_id.lower() and page == 15:
        page15_chunks.append(doc)

print(f"\nFound {len(page15_chunks)} chunks on page 15\n")

for i, chunk in enumerate(page15_chunks, 1):
    meta = chunk["metadata"]
    print(f"\n[{i}] PAGE 15 CHUNK")
    print(f"Chunk ID: {meta.get('chunk_id', 'N/A')}")
    print(f"\nFull text:")
    print(chunk["text"])
    print("\n" + "=" * 100)
