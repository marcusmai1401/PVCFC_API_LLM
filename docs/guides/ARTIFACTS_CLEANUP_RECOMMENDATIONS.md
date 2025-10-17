# 🧹 Artifacts Cleanup Recommendations

**Date**: 2025-10-17
**Current Total Size**: ~862MB
**D: Drive Free Space**: 476.16 GB

---

## ✅ Test Migration Results

```
[OK] D: drive accessible with 476.16 GB free
[OK] Write performance: 0.24 seconds (100 files) - EXCELLENT!
[OK] Existing data: 862.54 MB to migrate
[OK] .env backup created: .env.backup_20251017_070334
```

**Verdict**: Migration is **SAFE TO PROCEED** 🚀

---

## 📊 Current Artifacts Analysis

### **Critical (KEEP - Will be migrated):**

| Directory | Size | Files | Purpose |
|-----------|------|-------|---------|
| **ingestion_production** | 106MB | 320 | Production chunks & metadata |
| **index_production** | 62MB | 11 | Production BM25 & FAISS indices |
| **cache** | 122MB | 602 | Embedding cache (performance) |

**Total Critical**: ~290MB

---

### **Backups (Review & Clean):**

| Directory | Size | Files | Date | Action |
|-----------|------|-------|------|--------|
| **ingestion_backup_20251015_063804** | 282MB | 360 | 2025-10-15 | ⚠️ Delete if > 1 week old |
| **ingestion_production_backup_20251009_181153** | 70MB | 95 | 2025-10-09 | ⚠️ OLD - Can delete |
| **index_backup_before_phase1_fix_20251001_161503** | 152MB | 44 | 2025-10-01 | ⚠️ OLD - Can delete |
| **index_production_backup_20251009_181821** | 54MB | 11 | 2025-10-09 | ⚠️ OLD - Can delete |

**Total Backups**: ~558MB
**Recommendation**: ⚠️ **CLEANUP - Save ~558MB**

---

### **Test/Development Folders (DELETE):**

| Directory | Size | Files | Purpose |
|-----------|------|-------|---------|
| ingestion | 64MB | 315 | Test |
| perf_test | 9MB | 46 | Performance test |
| test_classify_enhanced | 10MB | 20 | Test |
| test_ingestion_tables | 8MB | 13 | Test |
| test_small_to_big | 7MB | 19 | Test |
| test_parent_child | 7MB | 19 | Test |
| bench_hier | 7MB | 19 | Benchmark |
| perf_w1 | 7MB | 19 | Performance test |
| test_classify | 7MB | 19 | Test |
| perf_w4 | 7MB | 19 | Performance test |
| bench_stb | 6MB | 19 | Benchmark |
| bench_sw | 6MB | 19 | Benchmark |
| test_ingest_* (6 folders) | ~18MB | ~100 | Various tests |
| chunks | 1.3MB | 5 | Test |
| + 13 other small test folders | ~2MB | ~50 | Various |

**Total Test Folders**: ~165MB
**Recommendation**: ✅ **DELETE ALL - Save ~165MB**

---

### **Questionable Files:**

| File/Folder | Size | Action |
|-------------|------|--------|
| **gemini_models.json** | 0 GB (empty file) | ✅ DELETE (rỗng, không dùng) |
| **ocr/** | 110MB | ⚠️ Keep if có scanned PDFs cần re-process |
| **chroma_db/** | 0.16MB | ❌ DELETE (không dùng Chroma nữa) |
| **faiss/** | Empty | ✅ DELETE (empty) |
| **bm25/** | Empty | ✅ DELETE (empty) |

---

## 🎯 Cleanup Plan

### **Phase 1: Safe Cleanup (Before Migration)**

```powershell
# Navigate to artifacts
cd artifacts

# 1. Delete old backups (> 1 week)
Remove-Item "ingestion_production_backup_20251009_181153" -Recurse -Force
Remove-Item "index_backup_before_phase1_fix_20251001_161503" -Recurse -Force
Remove-Item "index_production_backup_20251009_181821" -Recurse -Force

# 2. Delete obsolete folders
Remove-Item "chroma_db" -Recurse -Force
Remove-Item "faiss" -Recurse -Force
Remove-Item "bm25" -Recurse -Force

# 3. Delete gemini_models.json (empty file)
Remove-Item "gemini_models.json" -Force

# Savings: ~280MB
```

### **Phase 2: Aggressive Cleanup (Optional)**

```powershell
# Delete ALL test/benchmark folders
$testFolders = @(
    "ingestion",
    "perf_test", "perf_w1", "perf_w4",
    "test_*",
    "bench_*",
    "chunks",
    "eval",
    "qa",
    "tmp",
    "p2_test",
    "version_test",
    "evaluation_results"
)

foreach ($folder in $testFolders) {
    Get-ChildItem -Path "." -Directory -Filter $folder | Remove-Item -Recurse -Force
}

# Savings: ~165MB additional
```

### **Phase 3: Review Recent Backup**

```powershell
# Check if ingestion_backup_20251015_063804 is still needed
# If production is stable, delete it:
# Remove-Item "ingestion_backup_20251015_063804" -Recurse -Force
# Savings: 282MB additional
```

---

## 📋 Recommended Workflow

### **Conservative Approach (Recommended):**

```powershell
# 1. Cleanup old files BEFORE migration
cd artifacts
Remove-Item "ingestion_production_backup_20251009_181153" -Recurse -Force
Remove-Item "index_backup_before_phase1_fix_20251001_161503" -Recurse -Force
Remove-Item "index_production_backup_20251009_181821" -Recurse -Force
Remove-Item "chroma_db","faiss","bm25","gemini_models.json" -Recurse -Force

# 2. Run migration
cd ..
.\scripts\utilities\migrate_artifacts_to_d_drive.ps1

# 3. Verify
.\scripts\utilities\verify_artifacts_location.ps1

# 4. Delete test folders AFTER successful migration
cd artifacts
Get-ChildItem -Directory -Filter "test_*" | Remove-Item -Recurse -Force
Get-ChildItem -Directory -Filter "bench_*" | Remove-Item -Recurse -Force
Get-ChildItem -Directory -Filter "perf_*" | Remove-Item -Recurse -Force

# 5. Final: Delete recent backup after 1 week if production is stable
# Remove-Item "ingestion_backup_20251015_063804" -Recurse -Force
```

### **After Migration:**

```powershell
# You can delete the old C:\...\artifacts\ folder entirely
# BUT keep for 1 week to be safe:

# After 1 week:
Remove-Item "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\artifacts" -Recurse -Force
```

---

## 💾 Space Savings Summary

| Phase | Action | Space Saved | Risk |
|-------|--------|-------------|------|
| **Phase 1** | Delete old backups + obsolete | ~280MB | LOW |
| **Phase 2** | Delete test folders | ~165MB | LOW |
| **Phase 3** | Delete recent backup | ~282MB | MEDIUM (wait 1 week) |
| **Total** | | **~727MB** | |

**After cleanup**: ~135MB critical data to migrate
**After migration to D:**: Can delete old C:\artifacts\ (save another ~135MB on C:)

---

## ⚠️ Important Notes

1. **Backup Policy**:
   - Keep production backups < 1 week old
   - Delete backups > 1 month old
   - Always verify production is working before deleting recent backups

2. **Test Folders**:
   - Safe to delete ALL test_*/bench_*/perf_* folders
   - They can be regenerated if needed

3. **OCR Folder** (110MB):
   - Contains cached OCR results
   - Keep if you have scanned PDFs that need re-processing
   - Delete if all PDFs are vector-based

4. **Cache Folder** (122MB):
   - Embedding cache - improves performance
   - **KEEP** - will significantly speed up ingestion

---

## 🚀 Ready to Migrate?

After cleanup, run:

```powershell
# Final migration (after cleanup)
.\scripts\utilities\migrate_artifacts_to_d_drive.ps1
```

Expected migration:
- **Before cleanup**: 862MB
- **After Phase 1+2 cleanup**: ~297MB (production + cache only)
- **Migration time**: ~30-60 seconds

---

**Status**: ✅ Safe to proceed
**Recommendation**: Do Phase 1 cleanup → Migrate → Do Phase 2 cleanup → Wait 1 week → Phase 3
