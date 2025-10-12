# Task 1.2: Sync Metadata "Page" Field - Detailed Plan

## 🎯 Objective
Ensure all chunks in BM25 and FAISS indices have consistent `page` field (1-based) for accurate page-level citations and page jump functionality.

## 📊 Current Situation Analysis

### BM25 Index
- **Current fields**: `page_start`, `page_end` (lines 57-58 in bm25_indexer.py)
- **Missing**: Direct `page` field
- **Retriever usage**: Tries to get `page` from metadata (line 236), will be None if not present

### FAISS Index
- **Current**: Stores metadata in VectorDoc, accesses via `doc.metadata.get("page")` (line 332 in retriever.py)
- **Status**: Depends on how chunks were created during ingestion

### Text Chunker
- **Current**: Stores `page` in metadata when chunking documents (line 370 in text_chunker.py)
- **Also has**: `page_nums` list in TextChunk dataclass (line 27)
- **Good news**: When processing documents with pages, it already sets `metadata["page"]`

## 📝 Detailed Task List

### Sub-task 1.2.1: Update BM25 Indexer
- [ ] Add `page` field to metadata extraction in `build_index()`
- [ ] Implement fallback logic: `page = chunk.get("page") or chunk.get("page_start") or chunk.get("page_nums")[0] if page_nums else 1`
- [ ] Ensure backward compatibility with existing indices

### Sub-task 1.2.2: Create Page Sync Utility
- [ ] Create `app/utils/page_utils.py` with:
  - `extract_page_number(chunk_metadata)`: Smart extraction with fallbacks
  - `normalize_page_metadata(metadata)`: Ensure page field exists
  - `validate_page_number(page)`: Ensure 1-based integer

### Sub-task 1.2.3: Update Retriever
- [ ] Modify `_search_bm25()` to use page utility for consistent page extraction
- [ ] Update `_search_faiss()` similarly
- [ ] Add logging when page is missing/defaulted

### Sub-task 1.2.4: Create Migration Script
- [ ] Create `tools/migrate_page_metadata.py` to update existing indices
- [ ] Load existing BM25/FAISS indices
- [ ] Add `page` field to all chunks using fallback logic
- [ ] Save updated indices
- [ ] Create backup before migration

### Sub-task 1.2.5: Update TextChunk Export
- [ ] Ensure `to_dict()` includes `page` in metadata
- [ ] Update chunk creation to always set `page` field

### Sub-task 1.2.6: Testing
- [ ] Create test file `tests/test_page_metadata.py`
- [ ] Test page extraction with various metadata formats
- [ ] Test migration script on sample data
- [ ] Test retriever with updated indices

## 🔧 Implementation Order
1. Create page utilities (1.2.2)
2. Update BM25 Indexer (1.2.1)
3. Update Retriever (1.2.3)
4. Create migration script (1.2.4)
5. Update TextChunk if needed (1.2.5)
6. Testing (1.2.6)

## ✅ Success Criteria
- All chunks have `page` field (integer, 1-based)
- Page extraction works with legacy data (page_start/page_end)
- Citations show correct page numbers
- No breaking changes to existing functionality
- Migration script safely updates existing indices

## 🚀 Let's Start!
Beginning with Sub-task 1.2.2: Create Page Sync Utility
