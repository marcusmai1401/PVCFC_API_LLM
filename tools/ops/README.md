# 🔧 Operations Tools

Production operations scripts for data ingestion and indexing.

## Scripts

- **run_production_ingest.py** - Chạy data ingestion cho production
- **build_production_indices.py** - Build BM25 và FAISS indices
- **reindex_phase1.py** - Re-index data cho Phase 1

## Cách sử dụng

### Re-ingest toàn bộ dữ liệu
```bash
python tools/ops/run_production_ingest.py
```

### Rebuild indices
```bash
python tools/ops/build_production_indices.py
```

### Re-index Phase 1 data
```bash
python tools/ops/reindex_phase1.py
```

## ⚠️ Lưu ý

- Các scripts này thay đổi production data
- Backup artifacts trước khi chạy
- Có thể mất nhiều thời gian (10-60 phút tùy dataset size)
- Cần đủ disk space cho artifacts

## Workflow thông thường

1. Ingest PDFs → `run_production_ingest.py`
2. Build indices → `build_production_indices.py`
3. Verify system → `scripts/test_scripts/test_production_ready.py`
4. Start services → `start.ps1`
