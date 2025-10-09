import json
import os
from pathlib import Path

import PyPDF2

# Đọc doc_id_map
print("Loading doc_id_map...")
with open(
    "C:\\Users\\Admin\\Desktop\\Code - API_LLM_PVCFC\\artifacts\\ingestion\\doc_id_map.json",
    "r",
    encoding="utf-8",
) as f:
    doc_id_map = json.load(f)

print(f"Found {len(doc_id_map)} documents in doc_id_map")

# Tạo mapping: doc_id -> page_count
page_counts = {}
errors = []

for idx, (doc_id, file_path) in enumerate(doc_id_map.items(), 1):
    if idx % 10 == 0:
        print(f"Processing {idx}/{len(doc_id_map)}...")

    # Kiểm tra file có tồn tại không
    if os.path.exists(file_path):
        try:
            with open(file_path, "rb") as pdf_file:
                reader = PyPDF2.PdfReader(pdf_file)
                page_count = len(reader.pages)
                page_counts[doc_id] = page_count
        except Exception as e:
            errors.append({"doc_id": doc_id, "file_path": file_path, "error": str(e)})
    else:
        errors.append(
            {"doc_id": doc_id, "file_path": file_path, "error": "File not found"}
        )

# Lưu kết quả
output_file = "C:\\Users\\Admin\\Desktop\\Code - API_LLM_PVCFC\\artifacts\\ingestion\\pdf_page_counts.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(page_counts, f, indent=2, ensure_ascii=False)

print(f"\n✓ Successfully processed {len(page_counts)} PDFs")
print(f"✓ Results saved to: {output_file}")

if errors:
    print(f"\n⚠ {len(errors)} errors encountered:")
    for err in errors[:5]:  # Show first 5 errors
        print(f"  - {err['doc_id'][:50]}...")
        print(f"    Error: {err['error']}")
else:
    print("\n✓ No errors encountered")

# Summary statistics
print("\n--- Summary ---")
print(f"Total documents: {len(doc_id_map)}")
print(f"Successfully processed: {len(page_counts)}")
print(f"Errors: {len(errors)}")

if page_counts:
    total_pages = sum(page_counts.values())
    avg_pages = total_pages / len(page_counts)
    max_pages = max(page_counts.values())
    min_pages = min(page_counts.values())

    print(f"Total pages: {total_pages}")
    print(f"Average pages per document: {avg_pages:.1f}")
    print(f"Max pages in a document: {max_pages}")
    print(f"Min pages in a document: {min_pages}")
