# 🚀 START HERE - CAD Tag Extraction

**Welcome!** This feature is now implemented and ready for testing.

---

## ⚡ Quick Start (3 Commands)

```powershell
# 1. Enable feature
echo "`nENABLE_PID_TAGS=true" >> .env

# 2. Create index
python scripts\opensearch\create_tags_index.py

# 3. Test (replace with your P&ID file)
python tools\test_tag_extraction.py --pdf "D:\Data_Raw\your_pid.pdf" --doc-id "test_001"
```

**That's it!** Check the output and telemetry logs.

---

## 📖 Read Next

1. **Quick Reference** (1 page): `CAD_TAG_EXTRACTION_QUICK_REFERENCE.md`
2. **Quick Start Guide**: `CAD_TAG_EXTRACTION_QUICKSTART.md`
3. **Full Summary**: `CAD_TAG_EXTRACTION_IMPLEMENTATION_SUMMARY.md`

---

## ✅ Verification

Run this to verify everything works:
```powershell
python test_imports_cad_tags.py
```

Expected: `[SUCCESS] ALL IMPORTS OK`

---

## 🎯 What This Does

- **Auto-detects** CAD-like PDFs (P&ID, PFD, ISO drawings)
- **Extracts** instrument tags (e.g., "04 PSAL 2207", "PAL 2208 A/B/C")
- **Captures** bbox coordinates for each tag
- **Generates** PNG crops for vision citations
- **Indexes** to sidecar OpenSearch index
- **Integrates** with query processing (parallel search)
- **Logs** telemetry with auto-warnings

---

## ⚠️ Important

- Feature is **DISABLED** by default (`ENABLE_PID_TAGS=false`)
- **Non-invasive** - doesn't affect existing system
- **Easy rollback** - just set `ENABLE_PID_TAGS=false`
- Storage on **D: drive** (476 GB free) ✓

---

**Need help?** Check the documentation files above!
**Questions?** Review telemetry logs for insights.
**Ready?** Enable → Test → Deploy!
