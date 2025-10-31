# Kế Hoạch Triển Khai: Sửa Lỗi 69% Duplicate Chunks

**Trạng Thái**: DRAFT - Chờ Phê Duyệt
**Mức Độ Ưu Tiên**: URGENT
**Thời Gian Ước Tính**: 2-4 giờ (bao gồm testing)
**Ngày**: 2025-10-31

---

## 1. Mô Tả Vấn Đề

### Hiện Trạng

Ingestion pipeline hiện tại có **69% duplicate chunks** (23,087 duplicates trong tổng số 33,445 chunks) trong file `artifacts/ingestion_production/chunks/chunks.jsonl`.

**Hậu quả**:
1. **Lãng phí Storage**: 69% dung lượng đĩa (~60MB trong tổng 89MB file)
2. **Index Không Nhất Quán**: OpenSearch/FAISS indices có thể chứa duplicate hoặc conflicting versions
3. **Parent-Child Relationships Bị Hỏng**: Stats cho thấy 290% chunks không có parent (không thể xảy ra nếu không có duplicates)
4. **Retrieval Noise**: Cùng một chunk được trả về nhiều lần trong kết quả search
5. **Data Integrity Issues**: Các lần chạy ingestion khác nhau có thể có nội dung khác nhau cho cùng chunk_id

### Nguyên Nhân Gốc Rễ

**Root Cause**: Cả `chunks.jsonl` và `tags.jsonl` đều sử dụng **append-only mode** mà không có cơ chế cleanup giữa các lần chạy ingestion.

**Verified Facts**:
- Total chunks: 33,445
- Unique chunk IDs: 10,358
- Duplicates: 23,087 (69.0%)
- File `tags.jsonl` cũng có vấn đề tương tự (2,185 tags)

---

## 2. Phân Tích Code Hiện Tại

### File: `tools/ingest.py`

**Chunk Saving Logic** (lines 919-938):
```python
def _save_chunks(self, chunks: List[Dict], doc_id: str):
    """Save chunks in both JSON and JSONL formats"""
    # Save as JSON (backward compatibility)
    json_file = self.output_dir / "chunks" / f"{doc_id}_chunks.json"
    temp_file = json_file.with_suffix(".tmp")

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    temp_file.replace(json_file)

    # Save as JSONL if enabled
    if self.emit_jsonl:
        jsonl_file = self.output_dir / "chunks" / "chunks.jsonl"

        # Append to JSONL with lock to avoid interleaving lines
        with self._jsonl_lock:
            with open(jsonl_file, "a", encoding="utf-8") as f:  # ❌ APPEND MODE
                for chunk in chunks:
                    f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
```

**Vấn Đề**: Dòng 936 mở file ở chế độ `"a"` (append), không bao giờ xóa nội dung cũ.

**Setup Output Dirs** (lines 177-188):
```python
def _setup_output_dirs(self):
    """Create necessary output directories"""
    dirs = [
        self.output_dir,
        self.output_dir / "documents",
        self.output_dir / "markdown",
        self.output_dir / "chunks",
        self.output_dir / "manifests",
    ]

    for dir_path in dirs:
        dir_path.mkdir(parents=True, exist_ok=True)
```

**Vấn Đề**: Không có cleanup JSONL files, chỉ đảm bảo directories tồn tại.

### File: `app/ingestion/tags/tag_extractor.py`

**Tag Saving Logic** (lines 1043-1058):
```python
def save_tags(self, tags: List[TagEntity], output_file: Path):
    """
    Save extracted tags to JSONL file

    Args:
        tags: List of TagEntity objects
        output_file: Output file path (typically entities/tags.jsonl)
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "a", encoding="utf-8") as f:  # ❌ APPEND MODE
        for tag in tags:
            json_line = tag.model_dump_json()
            f.write(json_line + "\n")

    logger.debug(f"Saved {len(tags)} tags to {output_file.name}")
```

**Vấn Đề**: Dòng 1053 cũng sử dụng append mode không cleanup.

---

## 3. Giải Pháp Đề Xuất

### Approach: Add Cleanup at Pipeline Start (RECOMMENDED)

**Lý do**:
- Đơn giản và an toàn nhất
- Xóa JSONL files ở ĐẦU mỗi lần chạy ingestion
- Giữ nguyên per-document JSON files cho debugging
- Không breaking changes cho code hiện tại

**Implementation**:

#### Bước 1: Thêm method `_cleanup_jsonl_files()` vào `tools/ingest.py`

```python
def _cleanup_jsonl_files(self):
    """
    Clean up JSONL files from previous runs to prevent duplicates.
    Called at the start of each ingestion run.
    """
    jsonl_files_to_clean = [
        self.output_dir / "chunks" / "chunks.jsonl",
        self.output_dir / "entities" / "tags.jsonl",
    ]

    for jsonl_file in jsonl_files_to_clean:
        if jsonl_file.exists():
            # Create backup before deletion
            backup_file = jsonl_file.with_suffix(".jsonl.backup")
            if backup_file.exists():
                backup_file.unlink()  # Remove old backup

            shutil.copy2(jsonl_file, backup_file)
            logger.info(f"✅ Backed up {jsonl_file.name} to {backup_file.name}")

            # Clear the file
            jsonl_file.unlink()
            logger.info(f"🧹 Cleaned up {jsonl_file.name} from previous run")
```

#### Bước 2: Gọi method trong `run()`

```python
def run(self) -> Dict[str, Any]:
    """
    Run the ingestion pipeline

    Returns:
        Processing statistics
    """
    logger.info("=" * 80)
    logger.info("Starting Ingestion Pipeline V1")
    # ... existing logging ...

    self.stats["start_time"] = datetime.now()

    # Ensure output directories exist
    self._setup_output_dirs()

    # NEW: Clean up JSONL files from previous runs
    self._cleanup_jsonl_files()

    # ... rest of existing code ...
```

#### Bước 3: Cập nhật `_setup_output_dirs()`

```python
def _setup_output_dirs(self):
    """Create necessary output directories"""
    dirs = [
        self.output_dir,
        self.output_dir / "documents",
        self.output_dir / "markdown",
        self.output_dir / "chunks",
        self.output_dir / "manifests",
        self.output_dir / "entities",  # NEW: For tags.jsonl
    ]

    for dir_path in dirs:
        dir_path.mkdir(parents=True, exist_ok=True)
```

---

## 4. Các Bước Triển Khai Chi Tiết

### Step 1: Manual Cleanup (Trước khi đổi code)

**Backup dữ liệu hiện tại**:
```powershell
# Navigate to project root
cd "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC"

# Backup artifacts directory
cp -r artifacts/ingestion_production artifacts/ingestion_production_backup_$(Get-Date -Format "yyyyMMdd_HHmmss")
```

**Deduplicate chunks.jsonl** (giữ occurrence cuối cùng):
```python
# Tạo file scripts/dedupe_chunks.py
import json
from collections import OrderedDict
from pathlib import Path

# Read all chunks, keeping last occurrence
chunks = OrderedDict()
chunks_file = Path("artifacts/ingestion_production/chunks/chunks.jsonl")

with open(chunks_file, "r", encoding="utf-8") as f:
    for line in f:
        chunk = json.loads(line)
        chunk_id = chunk["chunk_id"]
        chunks[chunk_id] = chunk  # Overwrites duplicates, keeps last

# Write deduplicated chunks
output_file = chunks_file.with_suffix(".clean.jsonl")
with open(output_file, "w", encoding="utf-8") as f:
    for chunk in chunks.values():
        f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

print(f"Original: {sum(1 for _ in open(chunks_file))} chunks")
print(f"Deduplicated: {len(chunks)} chunks")
print(f"Removed: {sum(1 for _ in open(chunks_file)) - len(chunks)} duplicates")

# Verify
chunk_ids_clean = [json.loads(line)["chunk_id"] for line in open(output_file)]
print(f"\nVerification:")
print(f"Total in clean file: {len(chunk_ids_clean)}")
print(f"Unique in clean file: {len(set(chunk_ids_clean))}")
print(f"Duplicates in clean file: {len(chunk_ids_clean) - len(set(chunk_ids_clean))}")
```

**Chạy deduplication**:
```bash
python scripts/dedupe_chunks.py

# Verify kết quả
python -c "import json; ids = [json.loads(l)['chunk_id'] for l in open('artifacts/ingestion_production/chunks/chunks.clean.jsonl')]; print(f'Dup rate: {(len(ids) - len(set(ids))) / len(ids) * 100:.1f}%')"

# Nếu OK, replace file gốc
mv artifacts/ingestion_production/chunks/chunks.clean.jsonl artifacts/ingestion_production/chunks/chunks.jsonl
```

**Deduplicate tags.jsonl**:
```python
# Tạo file scripts/dedupe_tags.py
import json
from collections import OrderedDict
from pathlib import Path

# Read all tags, using composite key
tags = OrderedDict()
tags_file = Path("artifacts/ingestion_production/entities/tags.jsonl")

with open(tags_file, "r", encoding="utf-8") as f:
    for line in f:
        tag = json.loads(line)
        # Use composite key to identify unique tags
        key = (tag["doc_id"], tag["page"], tag["tag"])
        tags[key] = tag

# Write deduplicated tags
output_file = tags_file.with_suffix(".clean.jsonl")
with open(output_file, "w", encoding="utf-8") as f:
    for tag in tags.values():
        f.write(json.dumps(tag, ensure_ascii=False) + "\n")

print(f"Original: {sum(1 for _ in open(tags_file))} tags")
print(f"Deduplicated: {len(tags)} tags")
print(f"Removed: {sum(1 for _ in open(tags_file)) - len(tags)} duplicates")
```

```bash
python scripts/dedupe_tags.py
mv artifacts/ingestion_production/entities/tags.clean.jsonl artifacts/ingestion_production/entities/tags.jsonl
```

### Step 2: Sửa Code

**File cần sửa**: `tools/ingest.py`

1. Import đã có sẵn: `import shutil`
2. Thêm method `_cleanup_jsonl_files()` sau `_setup_output_dirs()` (line ~189)
3. Gọi `self._cleanup_jsonl_files()` trong `run()` sau `_setup_output_dirs()` (line ~214)
4. Thêm `self.output_dir / "entities"` vào list trong `_setup_output_dirs()`

**Không cần sửa**:
- `app/ingestion/tags/tag_extractor.py` (cleanup ở pipeline level xử lý tất cả)
- `app/ingestion/tags/orchestrator.py`

### Step 3: Testing

**Test 1: Small dataset run**
```bash
# Tạo test directory với vài PDFs
mkdir -p data/test_pdfs
cp data/raw_pdfs/*.pdf data/test_pdfs/ | Select-Object -First 5

# Run ingestion
python tools/ingest.py `
  --source-dir "data/test_pdfs" `
  --output-dir "artifacts/test_ingestion" `
  --workers 2

# Verify no duplicates
python -c "import json; ids = [json.loads(l)['chunk_id'] for l in open('artifacts/test_ingestion/chunks/chunks.jsonl')]; print(f'Total: {len(ids)}, Unique: {len(set(ids))}, Dup rate: {(len(ids) - len(set(ids))) / len(ids) * 100:.1f}%')"
```

**Test 2: Run twice (verify cleanup works)**
```bash
# First run
python tools/ingest.py --source-dir "data/test_pdfs" --output-dir "artifacts/test_ingestion" --workers 2

# Check results
$count1 = (Get-Content "artifacts/test_ingestion/chunks/chunks.jsonl" | Measure-Object -Line).Lines
Write-Host "First run: $count1 chunks"

# Second run (should cleanup and regenerate same number)
python tools/ingest.py --source-dir "data/test_pdfs" --output-dir "artifacts/test_ingestion" --workers 2

# Check results
$count2 = (Get-Content "artifacts/test_ingestion/chunks/chunks.jsonl" | Measure-Object -Line).Lines
Write-Host "Second run: $count2 chunks"

# Verify backup exists
Get-ChildItem "artifacts/test_ingestion/chunks/" -Filter "*.backup"

# Counts should be equal
if ($count1 -eq $count2) {
    Write-Host "✅ PASS: Both runs produced same number of chunks"
} else {
    Write-Host "❌ FAIL: Chunk counts differ: $count1 vs $count2"
}
```

**Test 3: Verify 0% duplicates after multiple runs**
```python
# Create file: tests/verify_no_duplicates.py
import json
from pathlib import Path

def check_duplicates(file_path, id_field="chunk_id"):
    """Check for duplicates in JSONL file"""
    ids = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            ids.append(obj[id_field])

    total = len(ids)
    unique = len(set(ids))
    duplicates = total - unique
    dup_rate = (duplicates / total * 100) if total > 0 else 0

    print(f"\n{file_path.name}:")
    print(f"  Total: {total}")
    print(f"  Unique: {unique}")
    print(f"  Duplicates: {duplicates}")
    print(f"  Duplicate rate: {dup_rate:.1f}%")

    return dup_rate == 0

# Check chunks
chunks_ok = check_duplicates(
    Path("artifacts/test_ingestion/chunks/chunks.jsonl"),
    id_field="chunk_id"
)

# Check tags
tags_ok = check_duplicates(
    Path("artifacts/test_ingestion/entities/tags.jsonl"),
    id_field="tag"  # Or use composite key if needed
)

if chunks_ok and tags_ok:
    print("\n✅ PASS: No duplicates found")
    exit(0)
else:
    print("\n❌ FAIL: Duplicates detected")
    exit(1)
```

```bash
python tests/verify_no_duplicates.py
```

### Step 4: Production Deployment

1. **Backup production artifacts**:
```bash
cp -r artifacts/ingestion_production artifacts/ingestion_production_backup_20251031
```

2. **Apply manual cleanup** (Step 1 scripts đã chạy ở trên)

3. **Commit code changes**:
```bash
git add tools/ingest.py scripts/dedupe_chunks.py scripts/dedupe_tags.py tests/verify_no_duplicates.py
git commit -m "fix: Clean JSONL files at pipeline start to prevent duplicates

Fixes issue where append-only mode caused 69% duplicate chunks.
Adds _cleanup_jsonl_files() method that backs up and clears
chunks.jsonl and tags.jsonl at the start of each ingestion run.

- Backup files with .backup extension before cleanup
- Add entities directory to _setup_output_dirs()
- Call cleanup after directory setup in run()

Resolves INGESTION_AUDIT_REPORT.md Finding #6.

Testing:
- Verified deduplication reduces 33,445 -> 10,358 chunks
- Verified running twice produces identical results
- Verified backup files are created

Breaking Changes: None
"
```

4. **Run production ingestion**:
```bash
python tools/ingest.py `
  --source-dir "data/raw_pdfs" `
  --output-dir "artifacts/ingestion_production" `
  --workers 4 `
  --enable-pid-tags
```

5. **Verify results**:
```bash
python tests/verify_no_duplicates.py

# Check backup was created
Get-ChildItem "artifacts/ingestion_production/chunks/" -Filter "*.backup"
Get-ChildItem "artifacts/ingestion_production/entities/" -Filter "*.backup"
```

---

## 5. Chiến Lược Testing

### Unit Tests

**File**: `tests/test_ingestion_cleanup.py`

```python
import json
import tempfile
from pathlib import Path
import pytest
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.ingest import IngestionPipeline

def test_cleanup_creates_backup(tmp_path):
    """Test that cleanup creates backup before deleting"""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Create dummy chunks file
    chunks_dir = output_dir / "chunks"
    chunks_dir.mkdir()
    chunks_file = chunks_dir / "chunks.jsonl"

    # Write some test data
    with open(chunks_file, "w") as f:
        f.write(json.dumps({"chunk_id": "test_1", "text": "data"}) + "\n")
        f.write(json.dumps({"chunk_id": "test_2", "text": "data"}) + "\n")

    assert chunks_file.exists()
    assert sum(1 for _ in open(chunks_file)) == 2

    # Create pipeline and call cleanup
    pipeline = IngestionPipeline(
        source_dir=tmp_path,
        output_dir=output_dir,
        emit_jsonl=True
    )
    pipeline._cleanup_jsonl_files()

    # Verify file was cleaned
    assert not chunks_file.exists(), "chunks.jsonl should be deleted"

    # Verify backup exists
    backup_file = chunks_file.with_suffix(".jsonl.backup")
    assert backup_file.exists(), "Backup should be created"
    assert sum(1 for _ in open(backup_file)) == 2, "Backup should have original data"

def test_cleanup_no_error_if_file_missing(tmp_path):
    """Test cleanup handles missing files gracefully"""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    pipeline = IngestionPipeline(
        source_dir=tmp_path,
        output_dir=output_dir,
        emit_jsonl=True
    )

    # Should not raise error
    pipeline._cleanup_jsonl_files()

def test_setup_creates_entities_dir(tmp_path):
    """Test that _setup_output_dirs creates entities directory"""
    output_dir = tmp_path / "output"

    pipeline = IngestionPipeline(
        source_dir=tmp_path,
        output_dir=output_dir
    )
    pipeline._setup_output_dirs()

    assert (output_dir / "entities").exists()
```

**Chạy tests**:
```bash
pytest tests/test_ingestion_cleanup.py -v
```

### Integration Tests

**Test duplicate prevention across runs**:
```python
# File: tests/integration/test_no_duplicates_across_runs.py
import json
import tempfile
from pathlib import Path
import shutil
import sys

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.ingest import IngestionPipeline

def test_multiple_runs_no_duplicates(tmp_path):
    """Test that running ingestion twice doesn't create duplicates"""
    # Copy some test PDFs
    test_pdfs = Path("data/test_pdfs")
    if not test_pdfs.exists():
        pytest.skip("Test PDFs not available")

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    for pdf in test_pdfs.glob("*.pdf"):
        shutil.copy(pdf, source_dir)

    output_dir = tmp_path / "output"

    # First run
    pipeline1 = IngestionPipeline(
        source_dir=source_dir,
        output_dir=output_dir,
        workers=2
    )
    stats1 = pipeline1.run()

    # Count chunks
    chunks_file = output_dir / "chunks" / "chunks.jsonl"
    count1 = sum(1 for _ in open(chunks_file))

    # Second run
    pipeline2 = IngestionPipeline(
        source_dir=source_dir,
        output_dir=output_dir,
        workers=2
    )
    stats2 = pipeline2.run()

    # Count chunks again
    count2 = sum(1 for _ in open(chunks_file))

    # Verify counts are equal
    assert count1 == count2, f"Chunk counts differ: {count1} vs {count2}"

    # Verify no duplicates
    chunk_ids = [json.loads(line)["chunk_id"] for line in open(chunks_file)]
    assert len(chunk_ids) == len(set(chunk_ids)), "Duplicates found after second run"
```

---

## 6. Rollback Plan

### Nếu có vấn đề sau deployment:

**Option 1: Restore từ backup**
```bash
# Restore production artifacts
rm -rf artifacts/ingestion_production
mv artifacts/ingestion_production_backup_20251031 artifacts/ingestion_production
```

**Option 2: Sử dụng .backup files** (nếu tạo bởi code mới)
```bash
mv artifacts/ingestion_production/chunks/chunks.jsonl.backup artifacts/ingestion_production/chunks/chunks.jsonl
mv artifacts/ingestion_production/entities/tags.jsonl.backup artifacts/ingestion_production/entities/tags.jsonl
```

**Option 3: Revert code changes**
```bash
git revert HEAD
git push
```

---

## 7. Success Criteria

- ✅ Duplicate rate trong `chunks.jsonl` giảm từ 69% xuống 0%
- ✅ Tất cả tags trong `tags.jsonl` là unique (không có duplicate doc_id+page+tag)
- ✅ Chạy ingestion 2 lần liên tiếp tạo ra kết quả giống hệt nhau (same số chunks/tags)
- ✅ Backup files (`.backup`) được tạo trước khi cleanup
- ✅ Không có lỗi trong ingestion pipeline
- ✅ Per-document JSON files (`{doc_id}_chunks.json`) vẫn còn nguyên

---

## 8. Risks và Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Data loss khi cleanup | HIGH | LOW | Tạo `.backup` files trước khi xóa |
| Concurrent ingestion runs | MEDIUM | LOW | Sử dụng file locks (đã implement) |
| Partial cleanup failure | MEDIUM | LOW | Sử dụng try-except với rollback |
| Breaking existing workflows | MEDIUM | LOW | Giữ nguyên per-document JSON files |
| Performance impact | LOW | VERY LOW | Cleanup rất nhanh (file deletion) |

---

## 9. Future Enhancements

1. **Incremental Ingestion Mode**: Thêm `--incremental` flag để hỗ trợ thêm documents mới mà không xóa existing ones (cần chunk-level deduplication logic)

2. **Versioned Ingestion**: Sử dụng timestamp-based directories cho mỗi run:
   ```
   artifacts/ingestion_production/
     20251031_143025/chunks/chunks.jsonl
     20251031_150812/chunks/chunks.jsonl
     latest -> 20251031_150812/
   ```

3. **Atomic JSONL Writes**: Write to temp file, sau đó atomic replace (giống manifests)

4. **Retention Policy cho Backups**: Auto-cleanup backups cũ hơn N days

---

## 10. Questions for Review

1. **Backup Strategy**: Có nên giữ multiple backup generations (`.backup`, `.backup.1`, `.backup.2`) hay chỉ một?

2. **Incremental Mode**: Có cần `--incremental` flag ngay bây giờ hay defer sang future?

3. **Logging Level**: Cleanup nên là INFO hay DEBUG level?

4. **entities Directory**: Nên thêm vào tất cả output directories hay chỉ khi P&ID tags enabled?

---

## 11. Checklist Trước Khi Triển Khai

- [ ] Đọc và hiểu toàn bộ plan
- [ ] Backup production artifacts
- [ ] Chạy manual deduplication scripts
- [ ] Verify deduplicated data (0% duplicates)
- [ ] Review code changes
- [ ] Run unit tests
- [ ] Run integration tests trên test dataset
- [ ] Test chạy 2 lần liên tiếp
- [ ] Verify backup creation
- [ ] Commit changes với descriptive message
- [ ] Deploy to staging first
- [ ] Monitor logs và metrics
- [ ] Deploy to production
- [ ] Verify production results
- [ ] Update documentation

---

**READY FOR APPROVAL** ✅

Vui lòng review và approve trước khi bắt đầu implementation.
