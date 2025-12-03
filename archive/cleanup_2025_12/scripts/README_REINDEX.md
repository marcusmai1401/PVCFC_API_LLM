# Weaviate Re-index Script - Page Number Validation

## Mục Đích

Script này fix vấn đề `page=0` và `page=None` trong Weaviate bằng cách:
1. **Backup** toàn bộ data hiện tại
2. **Validate** tất cả page numbers
3. **Sanitize** các page invalid với 3 strategies:
   - Từ content markers (`<!-- Page N -->`)
   - Từ chunk_id patterns (`_p13_`, `p13`)
   - Fallback to `1` nếu không tìm được
4. **Re-index** với data đã clean
5. **Verify** kết quả

## Cách Sử Dụng

### 1. Dry-Run (Khuyến nghị chạy trước)

Kiểm tra xem có bao nhiêu objects cần fix mà không thay đổi gì:

```bash
python scripts/maintenance/reindex_weaviate_fix_pages.py --dry-run
```

**Output:**
- Số objects với page=0, page=None
- Số objects sẽ được fix
- Statistics về fix strategies
- **KHÔNG** thay đổi data

### 2. Backup Only

Chỉ backup data để an toàn:

```bash
python scripts/maintenance/reindex_weaviate_fix_pages.py --backup-only
```

**Output:**
- File backup tại: `artifacts/backups/weaviate/weaviate_backup_YYYYMMDD_HHMMSS.json`

### 3. Execute Re-index (Production)

Thực sự update data:

```bash
python scripts/maintenance/reindex_weaviate_fix_pages.py --execute
```

**Lưu ý:**
- **Tự động backup** trước khi update
- Update theo batch (100 objects/batch)
- Verify kết quả sau khi done
- **Rollback:** Nếu có lỗi, restore từ backup file

### 4. Skip Backup (Không khuyến nghị)

Nếu đã backup trước đó:

```bash
python scripts/maintenance/reindex_weaviate_fix_pages.py --execute --no-backup
```

## Output Mẫu

### Dry-Run Output

```
================================================================================
WEAVIATE PAGE NUMBER RE-INDEX
================================================================================
Mode: DRY RUN
Collection: Chunk

================================================================================
BACKUP: Exporting Weaviate data...
================================================================================
Fetching all objects from collection: Chunk
  Fetched 100 objects...
  Fetched 200 objects...
  ...
✅ Backup complete: 1523 objects saved
   File: artifacts/backups/weaviate/weaviate_backup_20250117_160000.json

================================================================================
ANALYSIS: Page number distribution
================================================================================
Total objects: 1523
  Page = None: 0 (0.0%)
  Page = 0: 3 (0.2%)
  Page > 0: 1520 (99.8%)
⚠️  Found 3 objects with invalid pages

================================================================================
VALIDATION: DRY RUN page numbers
================================================================================
  Processing 100/1523...
  Processing 200/1523...
  ...

================================================================================
VALIDATION STATISTICS
================================================================================
Total chunks: 1523
  Page = None: 0
  Page = 0: 3
  Page > 0 (valid): 1520

Fixes applied:
  From metadata: 0
  From content markers: 2
  From chunk_id: 1
  Fallback to 1: 0

✅ 3 objects will be updated

================================================================================
🔍 DRY RUN MODE - No changes will be made
================================================================================
✅ Script complete!
```

### Execute Output

```
================================================================================
RE-INDEX: EXECUTING
================================================================================
Starting batch update...
  Batch 1: 3 objects updated

================================================================================
✅ Re-index complete: 3 updated, 0 failed
================================================================================

================================================================================
VERIFICATION: Checking re-indexed data
================================================================================
  Page = 0: 0
✅ No page=0 found!

================================================================================
✅ Script complete!
================================================================================
```

## Rollback (Nếu Cần)

Nếu re-index bị lỗi, restore từ backup:

```bash
# Tìm backup file mới nhất
ls -la artifacts/backups/weaviate/

# Restore từ backup (script riêng - cần implement nếu cần)
# hoặc re-index lại từ raw data sources
```

## Kiểm Tra Kết Quả

Sau khi re-index, kiểm tra:

```python
# Test query
python test_page_comprehensive.py

# Hoặc check trực tiếp trong code
from app.rag.hybrid_weaviate_opensearch_retriever import HybridWeaviateOpenSearchRetriever

retriever = HybridWeaviateOpenSearchRetriever()
results = retriever.retrieve_enhanced("operating pressure", top_k=10)

# Check page numbers
for r in results:
    print(f"Chunk: {r.chunk_id[:50]}, Page: {r.page}")
```

## Troubleshooting

### Issue: "Connection refused"
```
Error: Failed to connect to Weaviate
```

**Fix:**
```bash
# Check if Weaviate is running
curl http://localhost:8080/v1/.well-known/ready

# Start Weaviate if not running
docker-compose up -d weaviate
```

### Issue: "Batch update failed"

**Fix:**
- Check backup file còn intact
- Re-run với `--dry-run` để analyze
- Kiểm tra Weaviate logs: `docker logs weaviate`

### Issue: "Still have page=0 after re-index"

**Nguyên nhân:** Có objects được tạo mới sau khi re-index

**Fix:**
- Re-run script lại
- Hoặc check indexing pipeline để prevent page=0 ở source

## Safety Checklist

Trước khi execute production:

- [ ] Đã chạy `--dry-run` và review output
- [ ] Đã có backup gần đây (hoặc script sẽ tự động backup)
- [ ] Weaviate connection ổn định
- [ ] Không có indexing jobs đang chạy parallel
- [ ] Đã notify team về downtime (nếu có)
- [ ] Có plan rollback nếu cần

## Performance

- **Backup:** ~30 giây cho 1500 objects
- **Validation:** ~1 phút cho 1500 objects
- **Re-index:** ~2 phút cho 1500 objects (batch 100)
- **Total:** ~3-4 phút cho 1500 objects

Với 10K objects: ~20-30 phút

## Notes

- Script này **không** xóa data, chỉ update page numbers
- Backup được lưu permanent (phải xóa manual nếu cần)
- Re-index có thể chạy multiple times (idempotent)
- Không ảnh hưởng đến vectors/embeddings
