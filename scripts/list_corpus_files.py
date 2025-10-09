import json
from collections import Counter

# Load FAISS metadata
with open("artifacts/index/faiss/metadatas.json", encoding="utf-8") as f:
    meta = json.load(f)

# Extract doc_ids
doc_ids = [m.get("doc_id", "") for m in meta if m.get("doc_id")]
unique_docs = sorted(set(doc_ids))

print(f"Total unique docs in FAISS: {len(unique_docs)}")
print("\nAll doc_ids:")
for i, d in enumerate(unique_docs, 1):
    print(f"{i:3}. {d}")

# Count pages per doc
doc_pages = Counter()
for m in meta:
    doc_id = m.get("doc_id")
    if doc_id:
        page = m.get("page", 1)
        doc_pages[doc_id] = max(doc_pages[doc_id], page)

print(f"\n\nDocs with page coverage:")
for doc_id in unique_docs[:10]:
    max_page = doc_pages.get(doc_id, 0)
    print(f"  {doc_id[:80]}: {max_page} pages")
