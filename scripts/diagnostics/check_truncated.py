import json

print("Searching for S427434 (truncated version of S4274343)...")

with open(
    "data/indexes/faiss_index/metadatas.json", "r", encoding="utf-8", errors="ignore"
) as f:
    meta = json.load(f)

# Search with truncated ID
matches = [
    m
    for m in meta
    if "S427434" in m.get("doc_id", "") and "COMPRESSOR" in m.get("doc_id", "")
]
print(f"\nFound {len(matches)} chunks with S427434 (truncated):")

# Group by page
by_page = {}
for m in matches:
    page = m.get("page", "N/A")
    if page not in by_page:
        by_page[page] = []
    by_page[page].append(m)

print(f"\nPages with data from this file:")
for page in sorted(by_page.keys(), key=lambda x: x if isinstance(x, int) else 999):
    count = len(by_page[page])
    print(f"  Page {page}: {count} chunks")

# Show details of page 3
if 3 in by_page:
    print(f"\n⭐ PAGE 3 DATA (THE CORRECT PAGE):")
    print(f"   Found {len(by_page[3])} chunks on page 3")
    for i, m in enumerate(by_page[3][:3], 1):
        chunk_id = m.get("chunk_id", "N/A")
        doc_id = m.get("doc_id", "N/A")
        print(f"   Chunk {i}:")
        print(f"     chunk_id: {chunk_id[:80]}")
        print(f"     doc_id: {doc_id[:100]}...")
else:
    print("\n❌ NO DATA FROM PAGE 3 FOUND!")
    print("   This explains why retrieval cannot find the correct answer.")
