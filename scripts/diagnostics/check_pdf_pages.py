import json
import os
from pathlib import Path

import PyPDF2

# Đọc doc_id_map
with open(
    "C:\\Users\\Admin\\Desktop\\Code - API_LLM_PVCFC\\artifacts\\ingestion\\doc_id_map.json",
    "r",
    encoding="utf-8",
) as f:
    doc_id_map = json.load(f)

# Kiểm tra 10 entries đầu tiên
results = []
count = 0
for doc_id, file_path in doc_id_map.items():
    if count >= 10:
        break

    # Kiểm tra file có tồn tại không
    if os.path.exists(file_path):
        try:
            with open(file_path, "rb") as pdf_file:
                reader = PyPDF2.PdfReader(pdf_file)
                page_count = len(reader.pages)
                file_name = os.path.basename(file_path)
                results.append(
                    {"doc_id": doc_id, "file_name": file_name, "page_count": page_count}
                )
        except Exception as e:
            results.append(
                {
                    "doc_id": doc_id,
                    "file_name": os.path.basename(file_path),
                    "error": str(e),
                }
            )
    else:
        results.append(
            {
                "doc_id": doc_id,
                "file_name": os.path.basename(file_path),
                "error": "File not found",
            }
        )

    count += 1

# In kết quả
for r in results:
    print(f"Doc ID: {r['doc_id'][:60]}...")
    print(f"  File: {r['file_name']}")
    if "page_count" in r:
        print(f"  Pages: {r['page_count']}")
    else:
        print(f"  Error: {r['error']}")
    print()
