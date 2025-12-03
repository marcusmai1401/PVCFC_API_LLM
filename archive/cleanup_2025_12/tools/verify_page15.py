import json

docs = json.load(open("artifacts/index/bm25/documents.json", encoding="utf-8"))
metas = json.load(open("artifacts/index/bm25/metadata.json", encoding="utf-8"))

page15_chunks = [
    (i, m, docs[i])
    for i, m in enumerate(metas)
    if m.get("page") == 15 and "installation" in m.get("doc_id", "").lower()
]

print(f"✓ Found {len(page15_chunks)} chunks on PAGE 15")
print("=" * 70)

for i, meta, text in page15_chunks[:5]:
    print(f"\nChunk index: {i}")
    print(f"Chunk ID: {meta.get('chunk_id', 'N/A')}")
    print(f"Page: {meta['page']}")
    print(f"Doc ID: {meta['doc_id'][:70]}...")
    print(f"Text preview: {text[:200]}...")
    print("-" * 70)

# Check for table content
table_chunks = [
    (i, m, text)
    for i, m, text in page15_chunks
    if "torque" in text.lower() or "anchor bolt" in text.lower()
]

print(f"\n✓ Found {len(table_chunks)} table-related chunks on page 15")
