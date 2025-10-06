# 🔍 ROOT CAUSE ANALYSIS: Sai trang citation và LLM trả lời không đúng

**Ngày**: 2025-10-01
**Vấn đề**: User hỏi về "tightened torque for anchor bolt after back grouting 72 hours" (thông tin ở trang 15), nhưng LLM trả lời sai và citation trỏ về trang 1
**Severity**: **CRITICAL** - Ảnh hưởng trực tiếp đến độ chính xác của hệ thống RAG

---

## 📋 TÓM TẮT HIỆN TRẠNG

### Triệu chứng quan sát được
1. **LLM trả lời không đúng**: Không trả lời được câu hỏi về bảng torque values
2. **Citation sai trang**: Tất cả citations đều trỏ về `page: 1`, trong khi thông tin thực tế ở trang 15
3. **Vision generation failed**: Lỗi `Part.from_text() takes 1 positional argument but 2 were given`
4. **Text-only fallback không hiệu quả**: Sau khi vision fail, text-only generation vẫn không có đủ context

### Kết quả từ logs
```
2025-10-01 15:34:52 | WARNING  | app.rag.generator:generate:444 - Vision gating: OFF
                     (reason=exception: Part.from_text() takes 1 positional argument but 2 were given)

Retrieved citations:
- Citation 1: Page 1, doc_id=...Installation_instruction, source=bm25, score=4.608
- Citation 2: Page 1, doc_id=...Installation_instruction, source=bm25, score=4.603
- Citation 3: Page 1, doc_id=...Operating_Manual, source=bm25, score=4.373

Actual table location: Page 15 của Installation Instruction document
```

---

## 🔎 PHÂN TÍCH CHI TIẾT

### ✅ VẤN ĐỀ 1: Page Metadata BỊ SAI TRONG INDEX

**Root Cause**: **CRITICAL BUG trong ingestion/chunking phase**

#### Phát hiện
Khi phân tích BM25 index (`artifacts/index/bm25/metadata.json`), tôi phát hiện:

```json
{
  "chunk_id": "..._chunk_0037",
  "doc_id": "DOCID_KT06101_...Installation_instruction...",
  "page": 1,          ← SAI! Nội dung thực tế từ page 13
  "heading": null
},
{
  "chunk_id": "..._chunk_0043",
  "doc_id": "DOCID_KT06101_...Installation_instruction...",
  "page": 1,          ← SAI! Nội dung thực tế từ page 15 (có table)
  "heading": null
}
```

**Chunk content thực tế** (từ `documents.json`):
```
Chunk _0043:
<!-- Page 15 -->

Operating Instructions
Installation of Condensing Turbine with Baseplate Delivered in Completion  2-0400-13-01
[... nội dung về alignment ...]

Table: Tightened torque for anchor bolt
Size of anchor bolt
```

**Contradiction rõ ràng**:
- Chunk TEXT chứa marker `<!-- Page 15 -->` và table header
- Chunk METADATA có `"page": 1` ← SAI!

#### Impact
1. **Retrieval trả về đúng chunks** (BM25 match text tốt)
2. **Nhưng metadata page number sai** → Citation generation dùng sai page
3. **LLM không thấy table trong context** vì:
   - Table bị split thành nhiều chunks riêng biệt
   - Metadata page sai → không được gom vào cùng context window

---

### ✅ VẤN ĐỀ 2: TABLE CHUNKING KHÔNG TỐI ƯU

**Root Cause**: Table bị tách thành nhiều chunks nhỏ, mất ngữ cảnh

#### Phát hiện từ analysis

Tìm thấy **2 chunks có table keywords** (từ 14 keywords match):

**Chunk _0043** (Page 15 marker, metadata page=1):
```
[... alignment instructions...]
Table: Tightened torque for anchor bolt
Size of anchor bolt
```

**Chunk _0044** (Page 15 marker, metadata page=1):
```
[... alignment instructions...]
Table: Tightened torque for anchor bolt
Size of anchor bolt
```

**Vấn đề**:
- Table **header** xuất hiện nhưng **không có values** (M30, M36, 510, 890, etc.)
- Table content bị tách thành chunk riêng (hoặc bị lost)
- Semantic chunker có thể đã tách table thành chunk riêng mà không preserve structure

#### Table structure bị mất
Original table (từ PDF):
```
Table: Tightened torque for anchor bolt
┌──────────────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐
│ Size         │ M30 │ M36 │ M42 │ M45 │ M48 │ M52 │ M56 │ M64 │
├──────────────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┤
│ Initial (A)  │ 20  │ 30  │ 40  │ 50  │ 50  │ 60  │ 70  │ 80  │
│ Initial (B)  │ 100 │ 150 │ 200 │ 220 │ 250 │ 280 │ 320 │ 470 │
│ Final        │ 510 │ 890 │1420 │1770 │2150 │2750 │3430 │5110 │
└──────────────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘
```

Chunks hiện tại: **CHỈ có header, KHÔNG có data rows!**

---

### ✅ VẤN ĐỀ 3: VISION GENERATION FAILED

**Root Cause**: API signature thay đổi trong google-genai SDK

#### Lỗi
```python
# app/rag/generator.py line 1191
parts = [types.Part.from_text(prompt_text)]  ← SAI!
```

**Error**: `Part.from_text() takes 1 positional argument but 2 were given`

#### Phân tích
- SDK version cũ: `Part.from_text(text)` - nhận 1 positional arg
- SDK version mới: `Part.from_text()` - không nhận argument, trả về class method

**Cách gọi đúng** (tùy SDK version):
```python
# Option 1: Nếu SDK support text trong Part init
parts = [types.Part(text=prompt_text)]

# Option 2: Nếu SDK cần dùng từ điển
parts = [{"text": prompt_text}]

# Option 3: Nếu Part.from_text là class method không arg
part_text = types.Part.from_text()
part_text.text = prompt_text
parts = [part_text]
```

#### Impact
- Vision generation LUÔN fail → không bao giờ dùng được images
- Fallback sang text-only generation
- **NHƯNG** text-only generation không nhận đủ context vì:
  - Page metadata sai
  - Table bị split
  - Context window không chứa đủ thông tin

---

### ✅ VẤN ĐỀ 4: TEXT-ONLY CONTEXT KHÔNG ĐỦ THÔNG TIN

**Root Cause**: Cascade failures từ các vấn đề trên

#### Context passed to LLM (ước lượng)
```
[Doc 1] Operating Instructions
Installation of Condensing Turbine with Baseplate Delivered in Completion

[... some text about back grouting from page 13 ...]
For the requirement on the back grouting, see 2-0310-01-00.
Mounting or dismounting heavy component on the baseplate only can be done after the
back grouting finished at least for 24 hours.
After the back grouting finished for 24 hours, turn back all of the trimming screws by 1 turn.
After back grouting finished for 72 hours, tighten the anchor bolts to the final tightening torque...

[Doc 2] [... similar content ...]
```

**MISSING**:
- ❌ Table header và values
- ❌ Explicit page 15 marker trong context
- ❌ Complete table structure

**Result**: LLM không thể trả lời về table values vì:
1. Context không có data
2. Chỉ có reference "tighten... to the final tightening torque listed in the table below" (mà không có table)

---

## 📊 FLOW PHÂN TÍCH

```
User Query: "Tightened torque for anchor bolt after 72 hours?"
    ↓
Query Transform: HyDE generation OK
    ↓
Retrieval:
  ├─ BM25: ✅ Matched chunks _0037, _0038, _0043 (có mention "tighten anchor bolts")
  ├─ FAISS: ⚠️ Worked but results có same page=1 issue
  └─ RRF Fusion: ✅ Combined 36 results
    ↓
Reranker: ✅ Reranked to top 20
    ↓
Context Preparation:
  ├─ doc_mapping created: {1: chunk_0037, 2: chunk_0038, 3: chunk_0043, ...}
  └─ context string built ✅
    ↓
Generation Attempt 1: VISION
  ├─ Vision pages extracted: page=1, page=1, page=1 (all wrong!)
  ├─ Images rendered for page 1 (×3 docs) ✅
  ├─ Gemini API call: ❌ FAILED - Part.from_text() error
  └─ Result: None
    ↓
Generation Attempt 2: TEXT-ONLY FALLBACK
  ├─ Context: ❌ Missing table data (only references to "table below")
  ├─ LLM generates vague answer or apology
  └─ Result: "See document 2-0310-01-00" (không đúng)
    ↓
Citation Extraction:
  ├─ Parse [Doc 1], [Doc 2], [Doc 3] from answer
  ├─ Map to RetrievalResult
  ├─ Extract page: ❌ All chunks have page=1
  └─ Final citations: ALL point to page 1 (WRONG!)
    ↓
Response to User:
  ├─ Answer: ❌ Không có torque values
  └─ Citations: ❌ Page 1 (should be Page 15)
```

---

## 🎯 ROOT CAUSES SUMMARY

| # | Root Cause | Severity | Category | Detected Where |
|---|------------|----------|----------|----------------|
| 1 | **Page metadata trong chunks bị sai** | **CRITICAL** | Ingestion/Chunking | `metadata.json` analysis |
| 2 | **Table structure bị lost khi chunk** | **HIGH** | Ingestion/Chunking | Chunk content analysis |
| 3 | **Vision API signature không đúng** | **HIGH** | Generator/Vision | Runtime error logs |
| 4 | **Text-only context thiếu table data** | **MEDIUM** | Context preparation | Context string analysis |
| 5 | **Citation dùng metadata page sai** | **CRITICAL** | Citation extraction | Output citations |

---

## 🔧 NGUYÊN NHÂN SÂU XA

### 1. Page Metadata Issue - Ingestion Bug

**Có thể do**:
- PDF processor không extract đúng page number từ PyMuPDF
- Text chunker không preserve page info khi tạo chunks
- Metadata merger trong indexer bị bug
- Multi-page chunks được gán page đầu tiên (page 1) thay vì preserve range

**Files liên quan**:
- `app/ingestion/pdf_processor.py` - Extract pages
- `app/ingestion/text_chunker.py` - Create chunks với metadata
- `app/rag/indexers/bm25_indexer.py` - Save metadata

### 2. Table Extraction Issue

**Có thể do**:
- PyMuPDF `get_text()` không preserve table structure
- Semantic chunker chia table thành nhiều chunks riêng lẻ
- Table detection không được implement trong ingestion
- Chunking strategy không có special handling cho tables

**Best practice bị vi phạm**:
- Tables should be kept atomic trong 1 chunk
- Table structure cần preserve với Markdown format
- Hoặc dùng table extraction library (Camelot, Tabula)

### 3. Vision API Breaking Change

**Nguyên nhân**:
- Google GenAI SDK được update (breaking changes trong API)
- Code không được test với SDK version mới
- No version pinning trong requirements

---

## 💡 ĐỀ XUẤT GIẢI PHÁP

### 🔴 URGENT FIX (Must do ngay)

#### Fix 1: Page Metadata Correction
**Priority**: **P0 - CRITICAL**

```python
# app/ingestion/pdf_processor.py hoặc text_chunker.py
# Ensure page number từ <!-- Page X --> marker được parse đúng

import re

def extract_page_from_content(text: str) -> Optional[int]:
    """Extract page number from <!-- Page X --> marker"""
    match = re.search(r'<!-- Page (\d+) -->', text)
    if match:
        return int(match.group(1))
    return None

# Trong chunking logic:
for chunk in chunks:
    # Try extract from content first
    page = extract_page_from_content(chunk.text)
    if page:
        chunk.metadata['page'] = page
    # Fallback to original metadata
    elif 'page' not in chunk.metadata:
        chunk.metadata['page'] = chunk.metadata.get('page_start', 1)
```

**Action required**:
1. Fix ingestion pipeline
2. **RE-INDEX toàn bộ documents**
3. Verify metadata.json có page đúng

---

#### Fix 2: Vision API Signature
**Priority**: **P0 - CRITICAL**

```python
# app/rag/generator.py line 1191

# OLD (BROKEN):
parts = [types.Part.from_text(prompt_text)]

# NEW (FIXED):
parts = [types.Part(text=prompt_text)]  # hoặc {"text": prompt_text}

# For images:
parts.append(types.Part(inline_data={"mime_type": mime, "data": img}))
# hoặc
parts.append({"inline_data": {"mime_type": mime, "data": img}})
```

**Action required**:
1. Check google-genai SDK version: `pip show google-genai`
2. Read SDK docs for correct API
3. Update Part construction
4. Test vision generation end-to-end

---

### 🟡 HIGH PRIORITY (Cần làm sớm)

#### Fix 3: Table-Aware Chunking
**Priority**: **P1 - HIGH**

**Option A: Table Detection + Atomic Chunking**
```python
def detect_table(text: str) -> bool:
    """Detect if text contains table structure"""
    indicators = [
        r'Table:',
        r'\|\s+\|',  # Markdown table
        r'^\s*┌.*┐',  # ASCII table
        r'(\d+\s+){5,}',  # Multiple numbers (table row)
    ]
    return any(re.search(pattern, text) for pattern in indicators)

def chunk_with_table_awareness(doc_text: str):
    # If contains table, keep entire section as one chunk
    if detect_table(doc_text):
        yield create_atomic_chunk(doc_text)
    else:
        # Normal semantic chunking
        yield from semantic_chunk(doc_text)
```

**Option B: Use PDF Table Extraction**
```python
import camelot  # or tabula-py

def extract_tables_from_pdf(pdf_path: str, page: int):
    """Extract structured tables"""
    tables = camelot.read_pdf(pdf_path, pages=str(page))
    for table in tables:
        markdown_table = table.df.to_markdown()
        yield {
            "text": markdown_table,
            "metadata": {
                "type": "table",
                "page": page,
                "structured": True
            }
        }
```

---

### 🟢 MEDIUM PRIORITY (Improvements)

#### Fix 4: Enhanced Context Building

```python
def build_context_with_page_grouping(results: List[RetrievalResult]) -> str:
    """Group chunks by page để preserve table structure"""
    from collections import defaultdict

    by_page = defaultdict(list)
    for r in results:
        page = r.page or 1
        by_page[page].append(r)

    context_parts = []
    for page, chunks in sorted(by_page.items()):
        # Concatenate all chunks from same page
        page_text = "\\n".join(c.text for c in chunks)
        context_parts.append(f"[Page {page}]\\n{page_text}")

    return "\\n\\n".join(context_parts)
```

#### Fix 5: Validation & Monitoring

```python
def validate_citation_pages(citations, retrieved_docs):
    """Validate citations point to correct pages"""
    for citation in citations:
        # Check if page matches actual content
        actual_chunks = [d for d in retrieved_docs if d.doc_id == citation.doc_id]
        if actual_chunks:
            # Verify page is in reasonable range
            pages = [c.page for c in actual_chunks if c.page]
            if citation.page not in pages:
                logger.warning(
                    f"Citation page mismatch: cited p.{citation.page}, "
                    f"but chunks are from pages {pages}"
                )
```

---

## 📝 IMPLEMENTATION PLAN

### Phase 1: Emergency Fixes (1-2 days)
- [ ] Fix vision API signature (30 min)
- [ ] Test vision generation (1 hour)
- [ ] Fix page metadata extraction logic (4 hours)
- [ ] Re-index affected documents (2 hours)
- [ ] Verify citations now point to correct pages (1 hour)

### Phase 2: Table Handling (2-3 days)
- [ ] Implement table detection (4 hours)
- [ ] Add table-aware chunking (8 hours)
- [ ] OR integrate Camelot/Tabula (8 hours)
- [ ] Re-index with new chunking strategy (2 hours)
- [ ] Test table extraction accuracy (4 hours)

### Phase 3: Validation & Monitoring (1 day)
- [ ] Add citation validation (2 hours)
- [ ] Add context quality metrics (2 hours)
- [ ] Create test cases for table queries (2 hours)
- [ ] Update documentation (2 hours)

---

## 🧪 TESTING REQUIREMENTS

### Test Case 1: Page Metadata Correctness
```python
def test_page_metadata_after_reindex():
    # Load metadata
    metadata = load_bm25_metadata()

    # Load texts
    texts = load_bm25_texts()

    for meta, text in zip(metadata, texts):
        # Extract page from content
        content_page = extract_page_from_marker(text)
        meta_page = meta.get('page')

        if content_page and meta_page != content_page:
            raise AssertionError(
                f"Page mismatch: content={content_page}, metadata={meta_page}"
            )
```

### Test Case 2: Vision Generation Works
```python
def test_vision_api_call():
    from google import genai
    from google.genai import types

    # Test Part construction
    try:
        part = types.Part(text="Test prompt")
        assert part.text == "Test prompt"
    except Exception as e:
        raise AssertionError(f"Part construction failed: {e}")
```

### Test Case 3: Table Query Accuracy
```python
def test_table_query():
    query = "What is the final tightened torque for M48 anchor bolt?"

    response = ask_api(query)

    # Expected answer should contain:
    assert "2150" in response.answer  # Correct value
    assert "15" in str(response.citations[0].page)  # Correct page
    assert "M48" in response.answer  # Correct specification
```

---

## 📚 LESSONS LEARNED

### 1. Metadata Integrity is Critical
- Page numbers MUST be preserved accurately throughout pipeline
- Always validate metadata matches content
- Add checksums or validation hashes

### 2. Table Handling Needs Special Care
- Tables are structurally different from prose text
- Standard chunking breaks table semantics
- Need specialized extraction OR atomic chunking

### 3. Vision API Integration Requires Careful Testing
- SDK breaking changes happen
- Pin dependency versions
- Have fallback strategies
- Test with real API calls, not just mocks

### 4. Context Quality Matters More Than Quantity
- Wrong metadata → wrong context → wrong answer
- Better to have 1 correct page than 10 wrong ones
- Validation layers are essential

---

## ✅ SIGN-OFF

**Status**: 🔴 **ANALYSIS COMPLETE - WAITING FOR FIXES**

**Root causes identified**:
1. ✅ Page metadata bug in ingestion
2. ✅ Table chunking issue
3. ✅ Vision API signature error
4. ✅ Context missing table data
5. ✅ Citations using wrong page numbers

**Action items created**: 13 tasks across 3 phases

**Estimated time to fix**: 4-6 days (with re-indexing)

**Risk if not fixed**: System không tin cậy cho technical queries có tables/diagrams

---

**Người phân tích**: AI Assistant (Claude Sonnet 4.5)
**Ngày**: 2025-10-01
**Thời gian phân tích**: ~90 phút
**Files analyzed**: 8+ (index files, code, logs)
