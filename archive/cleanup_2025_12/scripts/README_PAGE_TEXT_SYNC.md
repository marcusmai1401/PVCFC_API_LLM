# text_by_page.jsonl Location Fix

## Problem

`PageReranker` and `CitationValidator` expect `text_by_page.jsonl` at:
```
D:\PVCFC_Artifacts\text_by_page.jsonl
```

But after building the index, the file is created at:
```
D:\PVCFC_Artifacts\index_production\text_by_page.jsonl
```

This mismatch causes errors during citation validation:
```
ERROR | Failed to get page text: [Errno 2] No such file or directory: 'D:\PVCFC_Artifacts\text_by_page.jsonl'
```

## Solution

### One-time Fix (Already Done)
```powershell
Copy-Item -Path "D:\PVCFC_Artifacts\index_production\text_by_page.jsonl" `
          -Destination "D:\PVCFC_Artifacts\text_by_page.jsonl" -Force
```

### After Rebuilding Index
Every time you rebuild the index, run the sync script:
```powershell
.\scripts\sync_page_text.ps1
```

This ensures the file is always in the correct location.

## Alternative: Symlink (Requires Admin)

If you have admin privileges or Windows Developer Mode enabled, you can create a symlink instead:

```powershell
# PowerShell (Run as Administrator)
New-Item -ItemType SymbolicLink `
  -Path "D:\PVCFC_Artifacts\text_by_page.jsonl" `
  -Target "D:\PVCFC_Artifacts\index_production\text_by_page.jsonl"
```

Or using CMD:
```cmd
mklink "D:\PVCFC_Artifacts\text_by_page.jsonl" "D:\PVCFC_Artifacts\index_production\text_by_page.jsonl"
```

**Advantage**: File automatically updates when you rebuild the index.

## Verification

Check the file exists:
```powershell
Test-Path "D:\PVCFC_Artifacts\text_by_page.jsonl"
# Should return: True

Get-Item "D:\PVCFC_Artifacts\text_by_page.jsonl" | Format-List
# Should show file metadata
```

## Root Cause

The `PipelineConfig` class uses `ARTIFACTS_DIR / "text_by_page.jsonl"` but the indexing pipeline creates it in the `index_production` subdirectory.

## Future Improvement

Consider updating `PipelineConfig.text_by_page_path` to point to the actual location:
```python
@property
def text_by_page_path(self) -> Path:
    """Path to text_by_page.jsonl file"""
    return self.ARTIFACTS_DIR / "index_production" / "text_by_page.jsonl"
```

---

**Status**: ✅ Fixed on 2025-10-17
**File Size**: ~7.8 MB
**Last Modified**: 2025-10-04 03:30:01
