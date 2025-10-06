"""
Find all chunks containing "1420" in the production index
"""
import json
from pathlib import Path

# Load BM25 documents
docs_path = Path("artifacts/index_production/bm25/documents.json")
if not docs_path.exists():
    print(f"File không tồn tại: {docs_path}")
    exit(1)

with open(docs_path, "r", encoding="utf-8") as f:
    raw_documents = json.load(f)

print(f"Tổng số chunks: {len(raw_documents)}")
print(f'Format: {type(raw_documents[0]) if raw_documents else "empty"}')
print()

# Parse documents if they're stored as JSON strings
documents = []
for doc in raw_documents:
    if isinstance(doc, str):
        try:
            parsed = json.loads(doc)
            if isinstance(parsed, dict):
                documents.append(parsed)
            else:
                documents.append({"text": str(parsed), "metadata": {}})
        except Exception as e:
            documents.append({"text": doc, "metadata": {}})
    elif isinstance(doc, dict):
        documents.append(doc)
    else:
        documents.append({"text": str(doc), "metadata": {}})

# Tìm chunks chứa '1420'
matching = []
for doc in documents:
    text = doc.get("text", "")
    if "1420" in text:
        matching.append(doc)

print(f'Tìm thấy {len(matching)} chunks chứa "1420"')
print("=" * 80)

# In ra tất cả chunks tìm thấy
for i, doc in enumerate(matching, 1):
    meta = doc.get("metadata", {})
    print(f"\n[{i}] CHUNK CHỨA 1420:")
    print(f'Chunk ID: {doc.get("chunk_id", "N/A")}')
    print(f'Doc ID: {meta.get("doc_id", "N/A")}')
    print(f'Page: {meta.get("page", "N/A")}')
    print(f'Page Start: {meta.get("page_start", "N/A")}')
    print(f'Page End: {meta.get("page_end", "N/A")}')
    print(f"\nText (first 600 chars):")
    print(doc.get("text", "")[:600])
    print("\n" + "-" * 80)

# Load doc_id_map để xem tên file thật
doc_id_map_path = Path("artifacts/ingestion/doc_id_map.json")
if doc_id_map_path.exists():
    with open(doc_id_map_path, "r", encoding="utf-8") as f:
        doc_id_map = json.load(f)

    print("\n\n" + "=" * 80)
    print("ÁNH XẠ DOC_ID -> PDF FILE")
    print("=" * 80)

    # Lấy danh sách doc_id từ các chunks matching
    doc_ids = set(doc.get("metadata", {}).get("doc_id", "") for doc in matching)

    for doc_id in doc_ids:
        if doc_id and doc_id in doc_id_map:
            pdf_path = doc_id_map[doc_id]
            filename = Path(pdf_path).name
            print(f"\nDoc ID: {doc_id}")
            print(f"File: {filename}")
            print(f"Full path: {pdf_path}")
