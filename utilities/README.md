# Utility Scripts

Các script tiện ích để quản lý và kiểm tra hệ thống.

## Scripts

- `check_embeddings.py` - Kiểm tra page embeddings và FAISS index
- `generate_doc_id_map.py` - Tạo doc_id_map.json từ FAISS metadata
- `generate_doc_id_map_full_paths.py` - Tạo doc_id_map với full paths
- `rag_cli.py` - Command-line interface cho RAG queries
- `run_all_tests.py` - Chạy tất cả tests trong project

## Usage

```bash
# Kiểm tra embeddings
python utilities/check_embeddings.py

# Tạo doc_id_map
python utilities/generate_doc_id_map.py

# CLI query
python utilities/rag_cli.py query "What is the operating pressure?"

# Chạy all tests
python utilities/run_all_tests.py
```
