# CRITICAL FIX: Implement File Hash Deduplication

**Priority**: 🔴 **CRITICAL**  
**File**: `tools/ingest.py`  
**Time**: ~10 minutes  
**Impact**: Prevent processing exact duplicate files

---

## Problem

Hiện tại, `file_hash` được tính nhưng **KHÔNG** được dùng để skip exact duplicates.

**Test Proof**:
```
original.pdf + original_copy.pdf (trùng 100%)
→ CẢ 2 đều được xử lý ❌
```

**Should Be**:
```
original.pdf → Xử lý ✅
original_copy.pdf → BỎ QUA ✅ (file_hash trùng)
```

---

## Solution

Thêm 2 đoạn code vào `tools/ingest.py`:

### CHANGE 1: Initialize file_hash_seen set

**Location**: In `__init__` method, around line **120-140**

**ADD THIS**:
```python
# Initialize file_hash tracking for exact duplicate detection
self.file_hash_seen = set()
```

**Full Context**:
```python
def __init__(
    self,
    source_dir: Path,
    output_dir: Path,
    ...
):
    ...
    # Existing init code
    self.content_hash_map = {}
    self.duplicate_groups = {}
    
    # ADD THIS LINE:
    self.file_hash_seen = set()  # Track file hashes to skip exact duplicates
    
    # Locks
    self._dedup_lock = threading.Lock()
    self._quarantine_lock = threading.Lock()
    ...
```

---

### CHANGE 2: Add file_hash dedup check

**Location**: In `_process_single_pdf` method, around line **394-395**

**FIND THIS**:
```python
        # Calculate file hash
        file_hash = self._calculate_file_hash(pdf_path)
        file_size = pdf_path.stat().st_size
        mtime = pdf_path.stat().st_mtime

        # Try to extract text first
        pdf_doc = None
        used_ocr = False
```

**CHANGE TO**:
```python
        # Calculate file hash
        file_hash = self._calculate_file_hash(pdf_path)
        file_size = pdf_path.stat().st_size
        mtime = pdf_path.stat().st_mtime

        # ===== FILE HASH DEDUPLICATION =====
        # Skip exact file duplicates (100% identical)
        with self._dedup_lock:
            if file_hash in self.file_hash_seen:
                # This is an exact duplicate file
                self.stats["duplicates_skipped"] += 1
                logger.info(f"Skipping exact duplicate (file_hash): {pdf_path.name}")
                return {"status": "skipped", "reason": "exact_file_duplicate"}
            
            # Mark this file_hash as seen
            self.file_hash_seen.add(file_hash)
        # ===== END FILE HASH DEDUPLICATION =====

        # Try to extract text first
        pdf_doc = None
        used_ocr = False
```

---

### CHANGE 3: Add duplicates_skipped to stats

**Location**: In `__init__` method, stats initialization, around line **95-110**

**FIND THIS**:
```python
self.stats = {
    "total_pdfs": 0,
    "processed": 0,
    "failed": 0,
    "duplicates_collapsed": 0,
    "quarantine_count": 0,
    ...
}
```

**ADD THIS LINE**:
```python
self.stats = {
    "total_pdfs": 0,
    "processed": 0,
    "failed": 0,
    "duplicates_skipped": 0,  # ADD THIS
    "duplicates_collapsed": 0,
    "quarantine_count": 0,
    ...
}
```

---

### CHANGE 4: Report duplicates_skipped in summary

**Location**: At the end of `run()` method, around line **280-290**

**FIND THIS**:
```python
logger.info(f"Processed: {self.stats['processed']}")
logger.info(f"Failed: {self.stats['failed']}")
logger.info(f"Duplicates collapsed: {self.stats['duplicates_collapsed']}")
logger.info(f"Quarantined: {self.stats['quarantine_count']}")
```

**ADD AFTER "Failed"**:
```python
logger.info(f"Processed: {self.stats['processed']}")
logger.info(f"Failed: {self.stats['failed']}")
logger.info(f"Duplicates skipped (exact files): {self.stats['duplicates_skipped']}")  # ADD THIS
logger.info(f"Duplicates collapsed: {self.stats['duplicates_collapsed']}")
logger.info(f"Quarantined: {self.stats['quarantine_count']}")
```

---

## Testing After Fix

### Test 1: Run Dedup Test

```bash
python scripts/test_scripts/test_deduplication_behavior.py
```

**Expected Output**:
```
✅ PASS: File hash deduplication is working
   Exact duplicates are correctly skipped
   Processed files: 1
```

### Test 2: Manual Verification

```bash
# Create 3 test files
cp test_docs/Equipment_Datasheet_KT06101.pdf data/test/dup1.pdf
cp data/test/dup1.pdf data/test/dup1_copy.pdf  # Exact copy
# Manually edit dup1.pdf slightly and save as dup1_v2.pdf

# Run ingestion
python tools/ingest.py \
  --source-dir data/test \
  --output-dir artifacts/test_fix

# Check results
cat artifacts/test_fix/doc_id_map.json
# Should show:
# - dup1.pdf → processed ✅
# - dup1_copy.pdf → skipped ✅ (exact duplicate)
# - dup1_v2.pdf → processed ✅ (95% similar but different file)
```

### Test 3: Check Logs

```bash
# Look for log message
grep "Skipping exact duplicate" logs/ingestion_*.log

# Should see:
# Skipping exact duplicate (file_hash): dup1_copy.pdf
```

---

## Rollback (If Issues)

If fix causes problems, rollback by:

1. Remove `file_hash_seen` initialization
2. Remove file_hash dedup block
3. Remove `duplicates_skipped` from stats

---

## Impact Analysis

### Before Fix (Current):

```
1000 PDFs including:
- 950 unique files
- 50 exact duplicates (copies)

Result: 1000 files processed
Time: 10 minutes
Disk: 500MB artifacts
```

### After Fix:

```
1000 PDFs including:
- 950 unique files
- 50 exact duplicates (copies)

Result: 950 files processed ✅
Time: 9.5 minutes ✅ (5% faster)
Disk: 475MB artifacts ✅ (5% smaller)
```

**Benefit**: ~5% time & space savings (more with higher dup rate)

---

## Related Documents

- `reports/test_results/OFFLINE_BUILD_AUDIT_REPORT_20251007.md` - Full audit report
- `reports/OFFLINE_BUILD_AUDIT_FINAL_REPORT.md` - Executive summary
- `scripts/test_scripts/test_deduplication_behavior.py` - Test script

---

**Created**: 2025-10-07  
**Status**: Ready to Apply  
**Reviewed By**: AI Assistant

