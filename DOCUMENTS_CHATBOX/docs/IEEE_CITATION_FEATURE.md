# IEEE-Style Citation Feature

## Overview

This feature adds IEEE-style citation formatting to the RAG system, converting inline document references like `[Doc 1, p.5]` into numbered citations `[1]` with a corresponding References section that includes clickable links to open PDFs directly at the referenced pages.

## Features

### 1. **Automatic Citation Conversion**
- Converts `[Doc X, p.Y]` format → `[n]` IEEE-style format
- Maintains citation order based on first appearance in answer
- Handles multiple citations in single brackets: `[Doc 1, p.5; Doc 2, p.10]` → `[1][2]`
- Deduplicates repeated document citations across answer

### 2. **Interactive References Section**
- Displays numbered bibliography below answer
- Format: `[1] filename.pdf` with clickable page links
- Each page link opens PDF in browser at exact page
- Fallback to image rendering if PDF file not found (with ⚠️ icon)

### 3. **Configurable Toggle**
- Enable/disable IEEE citations via UI checkbox
- Defaults to enabled
- Gracefully falls back to traditional citation format when disabled

### 4. **Backend Integration**
- Generator exports `doc_number_map` metadata with PDF paths
- New `/api/pdf/open` endpoint streams PDFs with page anchors
- Citation validator ensures accurate page references

## Usage

### For End Users

#### Enabling IEEE Citations
1. Open Query Lab in Streamlit app
2. Expand **"Citation Settings"** section
3. Check **"Use IEEE-style Citations"** (enabled by default)
4. Run your query

#### Reading Citations
- **In Answer**: Look for numbered references like `[1]`, `[2]`
- **In References Section**:
  - Find document titles: `[1] technical_manual.pdf`
  - Click page links: `p.5 p.10` to open PDF at that page
  - ⚠️ icon indicates image fallback (PDF not available)

#### Example Output
```
Answer: CO2 compressor specifications are detailed in [1]. Operating
procedures are found in [2].

References:
[1] compressor_manual_v2.pdf
    p.15 p.23 p.45
[2] operating_procedures.pdf
    p.8 p.12
```

### For Developers

#### Backend: Adding doc_number_map

In `app/rag/generator.py`, the `generate()` method now exports:

```python
# In metadata
"doc_number_map": {
    "1": {
        "doc_id": "DOCID_manual_abc123",
        "pdf_path": "/path/to/manual.pdf",
        "file_name": "manual.pdf"
    },
    "2": {...}
}
```

#### Frontend: Using convert_to_ieee_style()

```python
from components.query_lab_improved import convert_to_ieee_style

# Convert citations
converted_answer, citation_list = convert_to_ieee_style(
    answer_text=results["answer"],
    citations=results["citations"],
    doc_number_map=results["meta"]["doc_number_map"]
)

# citation_list format:
# [
#   {
#     "doc_id": "DOCID_...",
#     "file_name": "manual.pdf",
#     "pages": [5, 10, 15],
#     "pdf_path": "/full/path/to/manual.pdf"
#   }
# ]
```

#### API: PDF Open Endpoint

**Endpoint**: `GET /api/pdf/open`

**Parameters**:
- `pdf_path`: Full path to PDF file
- `page`: Page number to jump to

**Response**: Streams PDF with headers:
```
Content-Type: application/pdf
Content-Disposition: inline; filename="manual.pdf"
X-Page-Number: 15
```

**URL Example**:
```
http://localhost:8000/api/pdf/open?pdf_path=/data/manual.pdf&page=15#page=15
```

The `#page=15` fragment tells browser to jump to that page.

## Architecture

### Component Flow

```
┌─────────────────────────────────────────────────────────┐
│  1. Query Processing (Backend)                          │
│     - RAG Generator creates answer with [Doc X] format  │
│     - Exports doc_number_map in metadata                │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  2. Citation Conversion (Frontend)                      │
│     - convert_to_ieee_style() parses [Doc X, p.Y]      │
│     - Replaces with [1], [2], etc.                      │
│     - Builds ordered citation_list                      │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  3. References Rendering (UI)                           │
│     - Display converted answer                          │
│     - Render References section                         │
│     - Generate PDF links with /api/pdf/open            │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  4. PDF Viewing (Browser)                               │
│     - User clicks page link                             │
│     - Browser opens PDF at specified page               │
│     - Fallback to image if PDF unavailable              │
└─────────────────────────────────────────────────────────┘
```

### Key Files

| File | Purpose |
|------|---------|
| `app/rag/generator.py` | Exports doc_number_map metadata |
| `app/api/endpoints/pdf_renderer.py` | PDF streaming endpoint |
| `streamlit_app/components/query_lab_improved.py` | Citation conversion & UI |
| `tests/unit/test_ieee_citation_formatter.py` | Unit tests |

## Configuration

### Environment Variables

```bash
# API base URL (for PDF links)
PVCFC_API_BASE_URL=http://localhost:8000
```

### Streamlit Session State

```python
# Toggle IEEE citations
st.session_state["use_ieee_citations"] = True  # or False
```

## Testing

### Run Unit Tests
```bash
python tests/unit/test_ieee_citation_formatter.py
```

### Test Coverage
- ✅ Single citation conversion
- ✅ Multiple citations in one bracket
- ✅ Duplicate document handling
- ✅ Page range citations
- ✅ Missing doc_number_map fallback
- ✅ Empty answer edge case
- ✅ No citations in answer
- ✅ File name extraction
- ✅ Citation order preservation

### Manual Testing Checklist

1. **Basic Conversion**
   - [ ] Run query with citations
   - [ ] Verify answer shows `[1][2]` instead of `[Doc X]`
   - [ ] Check References section appears

2. **PDF Links**
   - [ ] Click page link in References
   - [ ] Verify browser opens PDF
   - [ ] Confirm page jumps to correct number

3. **Fallback Handling**
   - [ ] Test with missing PDF file
   - [ ] Verify ⚠️ icon appears
   - [ ] Confirm image fallback works

4. **Toggle Functionality**
   - [ ] Disable IEEE citations checkbox
   - [ ] Verify old format `[Doc X, p.Y]` appears
   - [ ] Re-enable and confirm IEEE format returns

## Troubleshooting

### Issue: Citations Not Converting

**Symptoms**: Still seeing `[Doc X, p.Y]` format in answer

**Solutions**:
1. Check IEEE citations toggle is enabled
2. Verify `doc_number_map` exists in API response:
   ```python
   print(results["meta"].get("doc_number_map"))
   ```
3. Check citation pattern matches expected format

### Issue: PDF Links Not Working

**Symptoms**: Clicking page link shows error

**Solutions**:
1. Verify API endpoint is accessible:
   ```bash
   curl http://localhost:8000/api/pdf/open?pdf_path=/path/to/file.pdf&page=1
   ```
2. Check PDF file path is absolute and exists
3. Verify PDF permissions (readable by API process)

### Issue: Wrong Page Numbers

**Symptoms**: PDF opens but wrong page displayed

**Solutions**:
1. Check citation validator is enabled
2. Verify page numbers in metadata match PDF actual pages
3. Some PDF viewers may have 0-based vs 1-based indexing issues

### Issue: Performance Degradation

**Symptoms**: Slow answer rendering

**Solutions**:
1. Citation conversion is O(n) - should be fast
2. Check if many citations (>50) causing slowdown
3. Consider caching converted answers if needed

## Future Enhancements

### Planned Features
- [ ] Hover tooltips on inline citations showing full reference
- [ ] Export references to BibTeX format
- [ ] Support for cross-referencing between documents
- [ ] Citation confidence scores in References section
- [ ] Batch PDF download of all cited documents

### API Improvements
- [ ] PDF page thumbnail preview
- [ ] Highlighted text snippets in PDF viewer
- [ ] Citation context extraction
- [ ] Multi-page PDF range viewing

## Migration Guide

### From Old Citation Format

If you have existing code using the old citation format:

**Before**:
```python
# Answer displayed as-is
st.markdown(results["answer"])

# Citations shown in separate tab
render_citations_table(results["citations"])
```

**After**:
```python
# Convert citations if enabled
if st.session_state.get("use_ieee_citations", True):
    converted_answer, citation_list = convert_to_ieee_style(
        results["answer"],
        results["citations"],
        results["meta"].get("doc_number_map")
    )
    st.markdown(converted_answer)
    render_references_section(citation_list)
else:
    # Keep old format
    st.markdown(results["answer"])
```

### Backward Compatibility

The feature is **fully backward compatible**:
- Old citation format still works
- Toggle allows switching between formats
- APIs maintain existing response structure
- Citations tab still available (optional)

## Version History

### v1.0.0 (2025-10-09)
- ✨ Initial IEEE citation feature release
- 📚 Automatic `[Doc X]` → `[1]` conversion
- 🔗 Clickable PDF page links
- ⚙️ Configurable toggle
- 🧪 Full unit test coverage
- 📖 Comprehensive documentation

## Support

For issues or questions:
- Create GitHub issue with `[IEEE Citations]` tag
- Check troubleshooting section above
- Review unit tests for usage examples
- Contact: [Your contact info]

## License

Same as parent project.
