# IEEE Citation Feature - Quick Reference

## 🚀 Quick Start

### Enable Feature (Default: ON)
1. Open Query Lab in Streamlit
2. Expand "Citation Settings"
3. Check "Use IEEE-style Citations"

### Citation Format
- **Before**: `[Doc 1, p.5]`
- **After**: `[1]`

### References Section
```
📚 References
[1] manual.pdf
    p.5 p.10 p.15
```
👆 Click page numbers to open PDF

---

## 🎯 For Users

### Reading Citations
- Numbers like `[1][2]` in answer = citations
- Scroll to "References" below answer
- Click page numbers to view source

### Troubleshooting
- ⚠️ icon = PDF not available (viewing image instead)
- Toggle off if you prefer old format `[Doc X]`
- Check API is running if links don't work

---

## 💻 For Developers

### API Endpoint
```bash
GET /api/pdf/open?pdf_path=/path/to/file.pdf&page=5#page=5
```

### Function Usage
```python
from components.query_lab_improved import convert_to_ieee_style

converted_text, citations = convert_to_ieee_style(
    answer_text,
    citations_list,
    doc_number_map
)
```

### Run Tests
```bash
python tests/unit/test_ieee_citation_formatter.py
```

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `app/rag/generator.py` | Exports doc_number_map |
| `app/api/endpoints/pdf_renderer.py` | PDF streaming |
| `streamlit_app/components/query_lab_improved.py` | UI & conversion |
| `tests/unit/test_ieee_citation_formatter.py` | Tests |
| `docs/IEEE_CITATION_FEATURE.md` | Full docs |

---

## 🐛 Common Issues

### Citations not converting?
- ✅ Check toggle is enabled
- ✅ Verify doc_number_map in API response

### PDF links not working?
- ✅ Check API is running
- ✅ Verify PDF file exists
- ✅ Check file permissions

### Performance slow?
- ✅ Should be fast (<10ms)
- ✅ Check citation count (>50 may slow)

---

## 📖 Full Documentation
See: `docs/IEEE_CITATION_FEATURE.md`

---

**Version**: 1.0.0
**Date**: 2025-10-09
**Status**: Production Ready ✅
