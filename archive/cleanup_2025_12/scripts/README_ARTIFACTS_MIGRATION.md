# Artifacts Storage Migration - D Drive Setup

## 📋 Overview

Scripts để migrate artifacts storage từ default location (project folder) sang D drive cho better disk space management, đặc biệt quan trọng cho **CAD-like Tag Extraction** feature.

## 🎯 Why Migrate to D Drive?

### **Disk Space Requirements:**

| Component | Size Estimate | Note |
|-----------|--------------|------|
| **Existing artifacts** | ~100-500MB | chunks.jsonl, indices |
| **CAD crops** (new) | **2-5GB** | PNG crops của mỗi tag (~50KB × 50K tags) |
| **Page layouts** (new) | 500MB-1GB | JSON layouts với vector drawings |
| **Tag entities** (new) | 100-200MB | tags.jsonl, relations.jsonl |
| **Logs & telemetry** | 100-500MB | Runtime logs, metrics |
| **Total** | **~4-8GB** | Có thể lớn hơn với large corpus |

### **Benefits:**

- ✅ D drive có nhiều space hơn (giả sử D: có hàng trăm GB)
- ✅ Không ảnh hưởng project folder size (dễ backup code)
- ✅ Dễ manage: artifacts cùng chỗ với raw data (D:\Data_Raw)
- ✅ Safe rollback: chỉ cần update .env

## 🚀 Quick Start

### **Option 1: Full Migration (Recommended)**

```powershell
# Run migration script
.\scripts\utilities\migrate_artifacts_to_d_drive.ps1

# Follow prompts and verify
.\scripts\utilities\verify_artifacts_location.ps1
```

### **Option 2: Test First**

```powershell
# Dry run - test only, no changes
.\scripts\utilities\migrate_artifacts_to_d_drive.ps1 -TestOnly

# If test passes, run actual migration
.\scripts\utilities\migrate_artifacts_to_d_drive.ps1
```

### **Option 3: Manual Setup**

```powershell
# 1. Create directory
New-Item -ItemType Directory -Path "D:\PVCFC_Artifacts" -Force

# 2. Add to .env
Add-Content -Path ".env" -Value "`nARTIFACTS_DIR=D:\PVCFC_Artifacts"

# 3. Verify
.\scripts\utilities\verify_artifacts_location.ps1
```

## 📖 Detailed Usage

### **migrate_artifacts_to_d_drive.ps1**

**Purpose**: Safe migration với validation và backup.

**Parameters:**
```powershell
-TargetDir <string>   # Target directory (default: D:\PVCFC_Artifacts)
-TestOnly             # Dry run mode - test without changes
-Force                # Skip confirmations
```

**Examples:**

```powershell
# Standard migration
.\scripts\utilities\migrate_artifacts_to_d_drive.ps1

# Custom target directory
.\scripts\utilities\migrate_artifacts_to_d_drive.ps1 -TargetDir "D:\MyCustomPath"

# Test mode (safe to run multiple times)
.\scripts\utilities\migrate_artifacts_to_d_drive.ps1 -TestOnly

# Force migration without prompts
.\scripts\utilities\migrate_artifacts_to_d_drive.ps1 -Force
```

**What it does:**

1. ✅ **Pre-flight checks**: D: drive accessibility, free space
2. ✅ **Performance test**: Write speed test (100 small files)
3. ✅ **Backup .env**: Creates timestamped backup
4. ✅ **Create structure**: Sets up required directories
5. ✅ **Migrate data**: Uses robocopy for efficient copy (if existing data)
6. ✅ **Update .env**: Adds/updates `ARTIFACTS_DIR` configuration
7. ✅ **Verification**: Checks critical files integrity

**Output:**
```
================================================================================
MIGRATION COMPLETED SUCCESSFULLY!
================================================================================

📊 Summary:
  ✓ Target directory: D:\PVCFC_Artifacts
  ✓ Configuration: Updated in .env
  ✓ D: free space: 245.67 GB
  ✓ Migrated data: 123.45 MB

🔧 Next Steps:
  1. Test with a small ingestion
  2. Verify artifacts are created in D: drive
  3. If successful, delete old artifacts (keep 1 week)
```

### **verify_artifacts_location.ps1**

**Purpose**: Post-migration verification.

**Usage:**
```powershell
.\scripts\utilities\verify_artifacts_location.ps1
```

**Checks:**

1. ✅ .env configuration
2. ✅ Directory accessibility & write permission
3. ✅ Disk space availability
4. ✅ Existing artifacts detection
5. ✅ Critical files integrity

**Output:**
```
================================================================================
VERIFICATION SUMMARY
================================================================================

Configuration: D:\PVCFC_Artifacts
Status: ✓ READY

💡 Tips for D: Drive Storage:
  • Keep at least 100GB free for CAD-like tag extraction
  • Monitor disk usage during ingestion
  • Old artifacts in C:\...\artifacts\ can be deleted after verification
```

## ⚠️ Risk Assessment

### **LOW Risk:**
- ✅ Core modules use centralized config (`PipelineConfig`)
- ✅ Auto-create directories
- ✅ Easy rollback (remove env var)

### **MEDIUM Risk:**
- ⚠️ Some hardcoded paths (embedding cache) - minor, ~100MB
- ⚠️ Cross-drive performance ~10-20% slower (acceptable)
- ⚠️ Need to migrate existing data

### **Mitigation:**
- ✅ Test mode available (`-TestOnly`)
- ✅ Automatic backup of .env
- ✅ Verification script
- ✅ Clear rollback instructions

## 🔄 Rollback

If you need to revert:

```powershell
# Option 1: Remove from .env
# Open .env and delete or comment out:
# ARTIFACTS_DIR=D:\PVCFC_Artifacts

# Option 2: Restore backup
Copy-Item ".env.backup_YYYYMMDD_HHMMSS" ".env" -Force

# Verify
.\scripts\utilities\verify_artifacts_location.ps1
```

System will automatically use default location: `artifacts/` in project folder.

## 📊 Post-Migration Testing

After migration, test with small ingestion:

```powershell
# 1. Test ingestion with 5-10 PDFs
python tools/ingest.py `
  --source-dir "D:\Data_Raw\test_folder" `
  --output-dir "$(Get-Content .env | Select-String 'ARTIFACTS_DIR' | % { $_ -replace '.*=', '' })\ingestion_test" `
  --workers 1

# 2. Verify files created in D:
Get-ChildItem "D:\PVCFC_Artifacts" -Recurse |
  Where-Object {-not $_.PSIsContainer} |
  Measure-Object -Property Length -Sum |
  Select-Object Count, @{Name="SizeMB";Expression={[math]::Round($_.Sum/1MB, 2)}}

# 3. Test query processing
python -c "from app.config import get_config; print(f'ARTIFACTS_DIR: {get_config().ARTIFACTS_DIR}')"
```

## 🛠️ Troubleshooting

### **Issue: "D: drive not accessible"**
```powershell
# Check drive
Get-PSDrive D

# Check permissions
Test-Path "D:\" -PathType Container
```

### **Issue: "Write permission denied"**
```powershell
# Run PowerShell as Administrator
# Or check folder permissions:
icacls "D:\PVCFC_Artifacts"
```

### **Issue: "Robocopy failed"**
```powershell
# Manual copy alternative
Copy-Item "artifacts\*" "D:\PVCFC_Artifacts" -Recurse -Force
```

### **Issue: "Performance very slow"**
```powershell
# Check if D: is external/network drive
Get-PhysicalDisk | Format-Table -AutoSize

# If slow, consider keeping on C: but monitor space
```

## 📝 Notes

- **Embedding cache** (~100MB) vẫn lưu ở `artifacts/ingestion/cache` (hardcoded) - not critical
- **Backup old artifacts** trước khi xóa (recommend keep 1 week)
- **Monitor disk usage** sau migration, especially khi run CAD tag extraction
- **.env.backup_*** files được tạo automatically - keep for rollback

## 🔗 Related Documentation

- `PVCFC_CADlike_Tag_Extraction_Handoff.md` - CAD tag extraction spec
- `Review_AI.md` - Implementation review & recommendations
- `app/config/pipeline_config.py` - Configuration source code

---

**Created**: 2025-10-16
**Author**: AI Agent (Claude Sonnet 4.5)
**Version**: 1.0
