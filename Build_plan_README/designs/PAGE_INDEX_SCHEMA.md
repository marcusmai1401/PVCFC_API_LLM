# PAGE INDEX SCHEMA DESIGN
## Phase 1: Page-Level Indexing for Citation Accuracy

**Version**: 1.0
**Date**: 2025-10-03

---

## OVERVIEW

Page-level indexing enables:
1. **Intra-document page reranking**: Find the exact page containing answer
2. **Citation validation (CiteFix)**: Verify citations point to correct pages
3. **Confidence calibration**: Score citations based on page-level evidence

---

## SCHEMA DEFINITIONS

### 1. text_by_page.jsonl

**Purpose**: Store extracted text for each page of each document

**Format**: JSONL (one JSON object per line)

**Schema**:
```json
{
  "doc_id": "string",           // Document identifier
  "page": 1,                    // Page number (1-indexed)
  "text": "string",              // Extracted page text
  "char_count": 1234,           // Character count
  "word_count": 234,            // Word count
  "has_tables": false,          // Boolean: contains tables
  "has_figures": false,         // Boolean: contains figures
  "metadata": {
    "source_path": "string",    // PDF path
    "extraction_method": "pymupdf|pdfplumber",
    "extraction_date": "ISO8601",
    "page_width": 595.0,        // Page dimensions
    "page_height": 842.0
  }
}
```

**Example**:
```json
{
  "doc_id": "DOCID_KT06101_datasheet_abc123",
  "page": 15,
  "text": "Maximum operating pressure: 150 psi\\nTemperature range: 5-40°C\\n...",
  "char_count": 1850,
  "word_count": 285,
  "has_tables": true,
  "has_figures": false,
  "metadata": {
    "source_path": "D:\\Data_Raw\\KT06101_datasheet.pdf",
    "extraction_method": "pymupdf",
    "extraction_date": "2025-10-03T14:00:00Z",
    "page_width": 595.0,
    "page_height": 842.0
  }
}
```

**Storage Location**: `artifacts/ingestion_production/text_by_page.jsonl`

**Estimated Size**: ~50-100 MB for 1000 pages

---

### 2. Page BM25 Index

**Purpose**: Fast lexical search at page level

**Implementation**: Use rank_bm25 library

**Structure**:
```python
{
  "corpus": List[str],          # List of page texts
  "doc_ids": List[str],         # Corresponding doc_ids
  "pages": List[int],           # Corresponding page numbers
  "bm25": BM25Okapi             # BM25 index object
}
```

**Storage**: Pickle format at `artifacts/ingestion_production/page_bm25_index.pkl`

**Index Key**: `(doc_id, page)` -> corpus_index

---

### 3. Page Metadata Index

**Purpose**: Quick lookup of page metadata

**Format**: JSON

**Schema**:
```json
{
  "doc_id": {
    "total_pages": 50,
    "pages": {
      "1": {
        "char_count": 1200,
        "word_count": 180,
        "has_tables": false,
        "has_figures": true
      },
      "2": {...}
    }
  }
}
```

**Storage**: `artifacts/ingestion_production/page_metadata.json`

---

## DATA FLOW

```
PDF Files
    ↓
[Extract per-page text via PyMuPDF]
    ↓
text_by_page.jsonl
    ↓
[Build BM25 Index] ────→ page_bm25_index.pkl
    ↓
[Extract Metadata] ────→ page_metadata.json
```

---

## INDEXING STRATEGY

### Page Extraction Rules:
1. **Skip empty pages**: Pages with < 50 characters
2. **Merge short pages**: If page < 100 chars, consider merging with next
3. **Table detection**: Use PyMuPDF layout analysis
4. **Figure detection**: Check for embedded images

### Text Preprocessing for BM25:
1. Lowercase conversion
2. Remove special characters (keep numbers, units)
3. Tokenize on whitespace
4. Keep technical terms intact (e.g., "KT-06101", "150psi")

---

## USAGE EXAMPLES

### Example 1: Page Reranking
```python
from app.rag.page_reranker import PageReranker

reranker = PageReranker()

# Find best pages in a document for a query
pages = reranker.rank_pages_for_doc(
    query="maximum operating pressure",
    doc_id="DOCID_KT06101_datasheet_abc123",
    top_k=5
)

# Returns: [(page_num, score), ...]
# e.g., [(15, 0.95), (16, 0.82), ...]
```

### Example 2: Citation Validation
```python
from app.rag.citefix import validate_citation

result = validate_citation(
    claim="Maximum pressure is 150 psi",
    doc_id="DOCID_KT06101_datasheet_abc123",
    page=15
)

# Returns validation scores:
# {
#   "lexical_score": 0.85,
#   "semantic_score": 0.92,
#   "is_valid": True,
#   "confidence": 0.88
# }
```

---

## PERFORMANCE CONSIDERATIONS

### Build Time:
- ~1-2 seconds per page for extraction
- ~0.1 second per page for BM25 indexing
- **Total for 1000 pages**: ~20-30 minutes

### Query Time:
- Page rerank (per doc): ~50-100ms for 50 pages
- BM25 search: ~10-20ms
- Semantic rerank: ~30-50ms

### Storage:
- text_by_page.jsonl: ~50KB per page average
- BM25 index: ~10-20MB for 1000 pages
- Metadata: ~1-2MB for 1000 pages

**Total storage for 1000 pages**: ~60-80MB

---

## MAINTENANCE

### Incremental Updates:
- Append new pages to text_by_page.jsonl
- Rebuild BM25 index (fast: ~seconds)
- Update metadata index

### Consistency Checks:
- Verify all doc_ids in text_by_page match doc_id_map
- Check page counts against PDF page counts
- Validate no duplicate (doc_id, page) entries

---

## IMPLEMENTATION NOTES

### Libraries Required:
```python
# Already in requirements.txt:
- pymupdf (fitz)  # PDF text extraction
- rank-bm25       # BM25 indexing
- sentence-transformers  # Semantic similarity

# For validation:
- rapidfuzz       # Fuzzy string matching
```

### Error Handling:
- **PDF read errors**: Log and skip problematic pages
- **Empty pages**: Mark in metadata, don't index
- **Encoding issues**: Use UTF-8, fallback to latin-1

---

## FUTURE ENHANCEMENTS (Post-Phase 1)

1. **Semantic embeddings per page**: For better reranking
2. **Table structure preservation**: Store table data separately
3. **Figure OCR**: Extract text from images
4. **Cross-document page linking**: Related pages across docs

---

## MIGRATION PATH

### From Current State:
1. Existing chunks.jsonl has page_start/page_end
2. Use doc_id_map to find PDF paths
3. Extract per-page text from PDFs
4. Build new page-level indices
5. **No breaking changes** to existing chunk-based retrieval

### Backward Compatibility:
- Chunk-level retrieval continues to work
- Page-level is **additional** capability
- Fallback to document-level if page index missing

---

**Schema approved for implementation** ✓
