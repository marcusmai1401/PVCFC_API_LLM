"""
Find the specific chunk containing the M42/1420 torque table
"""
import json
from pathlib import Path

# Load and parse
docs_path = Path("artifacts/index_production/bm25/documents.json")
with open(docs_path, "r", encoding="utf-8") as f:
    raw_documents = json.load(f)

documents = []
for doc in raw_documents:
    if isinstance(doc, str):
        try:
            parsed = json.loads(doc)
            if isinstance(parsed, dict):
                documents.append(parsed)
        except:
            pass

print(f"Parsed {len(documents)} valid chunks\n")

# Find the table chunk specifically
found_table = False
for doc in documents:
    text = doc.get("text", "")
    if "1420" in text and "TABLE START" in text and "M42" in text:
        meta = doc.get("metadata", {})
        print("=" * 80)
        print("CHUNK CHỨA BẢNG M42/1420 NM")
        print("=" * 80)
        print(f'Chunk ID: {doc.get("chunk_id", "N/A")}')
        print(f'Doc ID: {meta.get("doc_id", "N/A")}')
        print(f'Source: {meta.get("source", "N/A")}')
        print(f'Page: {meta.get("page", "N/A")}')
        print(f'Page Start: {meta.get("page_start", "N/A")}')
        print(f'Page End: {meta.get("page_end", "N/A")}')
        print()
        print("Full metadata keys:", list(meta.keys()))
        print()
        print("Full text:")
        print(text)
        print()
        found_table = True
        break

if not found_table:
    print("KHÔNG TÌM THẤY chunk chứa bảng!")
    print("Tìm thấy các chunk có 1420:")
    for i, doc in enumerate(documents, 1):
        if "1420" in doc.get("text", ""):
            meta = doc.get("metadata", {})
            print(
                f'\n{i}. Page {meta.get("page", "?")} - Doc ID: {meta.get("doc_id", "?")}'
            )
            print(f'   Text preview: {doc.get("text", "")[:100]}...')

# Load doc_id_map
print("\n" + "=" * 80)
print("ÁNH XẠ DOC_ID -> PDF FILE")
print("=" * 80)

doc_id_map_path = Path("artifacts/ingestion/doc_id_map.json")
if doc_id_map_path.exists():
    with open(doc_id_map_path, "r", encoding="utf-8") as f:
        doc_id_map = json.load(f)

    # Look for Installation instruction doc_id
    for doc_id, pdf_path in doc_id_map.items():
        if "Installation" in pdf_path and "instruction" in pdf_path:
            filename = Path(pdf_path).name
            print(f"\nDoc ID: {doc_id}")
            print(f"File: {filename}")
            print(f"Full path: {pdf_path}")
