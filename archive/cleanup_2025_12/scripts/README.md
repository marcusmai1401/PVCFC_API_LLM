# 🛠️ Utility Scripts

Các script tiện ích để bảo trì và fix issues trong project.

---

## 📁 FILES

### **`fix_hosts.py`**

**Mô tả**: Fix host placeholders trong project files

**Vấn đề**:
- Một số files có placeholder `*********` thay vì IP addresses thực
- Cần replace với `127.0.0.1` hoặc `0.0.0.0`

**Files được fix**:
- `app/main.py`
- `scripts/run.ps1`
- `start_api.ps1`
- `QUICKSTART.md`

**Sử dụng**:
```bash
python scripts/utilities/fix_hosts.py
```

**Output mẫu**:
```
Fixing host placeholders in project files...
--------------------------------------------------
✓ Fixed: app/main.py
  No changes needed: scripts/run.ps1
✓ Fixed: start_api.ps1
  File not found: QUICKSTART.md
--------------------------------------------------
Fixed 2 files

Checking for 0.0.0.0 references...
⚠ Found 0.0.0.0 in app/main.py - consider changing to 127.0.0.1 for local dev
```

**Status**: ⚠️ LEGACY (vấn đề đã được fix, giữ lại cho reference)

---

## 🎯 Khi nào nên dùng

### `fix_hosts.py`
- Khi clone project mới và thấy host placeholders
- Sau khi merge code có conflicts về host configs
- Khi cần standardize host configuration

---

## 💡 Thêm utilities mới

Nếu bạn tạo utility scripts mới, đặt chúng trong folder này:

```bash
scripts/utilities/
├── README.md                    ← File này
├── fix_hosts.py                 ← Fix host placeholders
├── cleanup_artifacts.py         ← (Future) Clean temp files
├── backup_indices.py            ← (Future) Backup FAISS/BM25
└── check_dependencies.py        ← (Future) Verify installations
```

### Format cho utilities mới
```python
#!/usr/bin/env python3
\"\"\"
Brief description of what this utility does
\"\"\"
import os
from pathlib import Path

def main():
    \"\"\"Main utility function\"\"\"
    print("=" * 60)
    print("UTILITY NAME")
    print("=" * 60)

    # Your utility logic here

    print("\\n✓ Done!")

if __name__ == "__main__":
    main()
```

---

## 📚 Utility Ideas (Future)

### Cleanup Artifacts
```python
# cleanup_artifacts.py
- Clean temp files in artifacts/
- Remove old logs
- Clear cache folders
```

### Backup Indices
```python
# backup_indices.py
- Backup FAISS index
- Backup BM25 index
- Timestamp backups
```

### Check Dependencies
```python
# check_dependencies.py
- Verify Python packages
- Check Tesseract installation
- Verify API keys
```

### Database Migration
```python
# migrate_indices.py
- Migrate old index format to new
- Update metadata schemas
- Preserve data integrity
```

---

**Status**: ✅ Ready for expansion
**Last updated**: 2025-10-01
