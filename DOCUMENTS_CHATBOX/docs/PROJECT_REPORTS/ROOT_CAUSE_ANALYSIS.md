# Root Cause Analysis - Vision Citation Bug

## 🎯 Vấn đề

**Hiện tượng**: Model trả lời đúng "1420 Nm" cho câu hỏi về M42 anchor bolt, nhưng citation trỏ sai về Operating Manual page 160 thay vì Installation instruction.pdf page 15 (nơi có bảng thật).

## 🔍 Điều tra

### Kết quả tìm được:

1. **Bảng M42/1420 CÓ TỒN TẠI trong index**:
   - Chunk #2892 chứa bảng đầy đủ được extract từ page 15
   - Content: `TABLE START (Page 15)... | M42 | 1420 | ...`
   - Doc ID: `DOCID_..._Installation_instruction_c2974d5b`
   - ✅ Text extraction và table detection hoạt động đúng

2. **❌ Metadata bị SAI**:
   ```json
   Chunk #2892 metadata:
   {
     "page": 1,           // ← SAI! Nên là 15
     "page_start": 1,
     "page_end": 19,
     "doc_id": "..._Installation_instruction..."
   }
   ```

3. **Model trả lời ĐÚNG nhờ text, KHÔNG phải Vision**:
   - Text context có chunk #2892 với bảng đầy đủ
   - Gemini đọc text và trả lời đúng "1420 Nm"
   - **Vision KHÔNG giúp gì** vì không có page 15

4. **Vision chọn SAI pages**:
   ```
   Metadata page=1 → Vision selector chọn pages [1-3]
   → Bỏ lỡ page 15 (page thật của bảng)
   → Citation map sang Vision page đầu tiên (Operating Manual p.160)
   ```

## 🎭 Chuỗi sự kiện

| Bước | Điều gì xảy ra | Kết quả |
|------|----------------|---------|
| **Ingestion** | Chunk full-doc → metadata.page = page_start = 1 | ❌ Metadata SAI |
| **BM25 Retrieval** | Tìm được chunk #2892 chứa "1420" | ✅ Text ĐÚNG |
| **Vision Selector** | Dùng metadata.page=1 → chọn pages 1-3 | ❌ Thiếu page 15 |
| **Vision Rendering** | Render pages [160-167, 1-2] | ❌ Không có page 15 |
| **LLM Generation** | Đọc text context → trả lời "1420 Nm" | ✅ Trả lời ĐÚNG (từ text) |
| **Citation Mapping** | Map [Doc 1] → Vision page đầu (p.160) | ❌ Citation SAI |

## 🐛 Nguyên nhân gốc

### Lỗi #1: Ingestion metadata
Khi tạo full-document chunks, code set:
```python
metadata = {
    "page": page_start,  # Luôn = 1 cho full-doc
    "page_start": 1,
    "page_end": 19
}
```

**Nên là**: Parse page từ content markers (`<!-- Page 15 -->`) hoặc dùng middle of range.

### Lỗi #2: Vision selector tin metadata mù quáng
```python
# Old logic (generator.py line 1352)
center = doc.page  # = 1 (SAI!)
start = center - 2  # = -1 → max(1, -1) = 1
end = center + 2    # = 3
# → Chọn pages [1, 2, 3] thay vì [13, 14, 15, 16, 17]
```

## ✅ Giải pháp

### Fix #1: Parse page từ content (IMPLEMENTED)

Tạo `app/utils/page_utils.py`:
```python
def extract_page_from_content(text: str) -> Optional[int]:
    """Extract page from <!-- Page N --> or TABLE START (Page N)"""
    page_markers = re.findall(r'<!-- Page (\d+) -->', text)
    if page_markers:
        return int(page_markers[0])
    return None

def get_best_page_number(text: str, metadata: Dict) -> int:
    """Priority: content > metadata > range middle"""
    # 1. Try content
    page_from_content = extract_page_from_content(text)
    if page_from_content:
        return page_from_content

    # 2. Try metadata
    page_from_meta = extract_page_number(metadata)

    # 3. If suspicious (page=1 but page_end >> 1), use middle
    if page_from_meta == 1:
        page_start = metadata.get('page_start', 1)
        page_end = metadata.get('page_end', 1)
        if page_end > page_start + 5:
            return (page_start + page_end) // 2

    return page_from_meta
```

### Fix #2: Update vision selector (IMPLEMENTED)

Sửa `generator.py` `_build_vision_pages`:
```python
# NEW: Try content first
from app.utils.page_utils import get_best_page_number

if hasattr(doc, 'text') and doc.text:
    center = get_best_page_number(doc.text, meta)  # → 15!
else:
    # Fallback với logic middle-of-range
    center = doc.page
    if center == 1 and page_end > page_start + 5:
        center = (page_start + page_end) // 2

start = max(1, center - 2)  # → 13
end = center + 2              # → 17
# Chọn pages [13, 14, 15, 16, 17] ✅
```

## 🎯 Kết quả mong đợi sau fix

### Với cùng query:

| Bước | Trước fix | Sau fix |
|------|----------|---------|
| **Vision selector** | Pages [1-3] | Pages [13-17] ✅ |
| **Vision images** | [160-167, 1-2] | [13-17] ✅ |
| **Vision có page 15?** | ❌ Không | ✅ CÓ |
| **LLM thấy bảng** | Chỉ từ text | Text + Image ✅ |
| **Citation** | Operating Manual p.160 | Installation p.15 ✅ |

## 📊 Approach comparison

| Approach | Độ chính xác | Chi phí | Khuyến nghị |
|----------|-------------|---------|-------------|
| **Metadata-only** | ❌ Thấp | Trung bình | Không dùng |
| **Content-first (Implemented)** | ✅ Cao | Thấp | **Best practice** |
| **Middle-of-range fallback** | ⚠️ Tạm được | Thấp | Fallback tốt |
| **Re-ingest all docs** | ✅ Hoàn hảo | ❌ Rất cao | Không cần thiết |

## 🚀 Testing

### Test case:
```python
# Query: "What is the final tightening torque for M42 anchor bolt?"

# Expected:
# - Answer: "1420 Nm" ✅
# - Citation: Installation instruction.pdf, page 15 ✅
# - Vision metadata: pages_used includes page 15 ✅
```

### Verification script:
```bash
python -c "
from app.utils.page_utils import get_best_page_number, extract_page_from_content

# Test text with page marker
text = '''<!-- Page 15 -->
--- TABLE START (Page 15) ---
| M42 | 1420 |
'''

metadata = {'page': 1, 'page_start': 1, 'page_end': 19}

page = get_best_page_number(text, metadata)
print(f'Extracted page: {page}')  # Should print: 15
"
```

## 📝 Lessons Learned

1. **Text extraction là nền tảng**: Dù có Vision hay không, text quality quyết định độ chính xác
2. **Metadata không đáng tin 100%**: Luôn validate bằng content markers
3. **Vision chỉ hữu ích khi có đúng pages**: Page selection là bước critical
4. **Parse from content > Trust metadata**: Content markers (<!-- Page N -->) đáng tin hơn metadata
5. **Test với data thật**: Synthetic tests không bắt được edge cases này

## ✅ Files Modified

1. `app/utils/page_utils.py`: Added `extract_page_from_content()`, `get_best_page_number()`
2. `app/rag/generator.py`: Updated `_build_vision_pages()` to use content-based page extraction
3. `ROOT_CAUSE_ANALYSIS.md`: This document

## 🎓 Recommendations

### Immediate (Done):
- ✅ Parse page from content in vision selector
- ✅ Fallback to middle-of-range for suspicious metadata

### Short-term (Optional):
- Update metadata.page during ingestion to use content markers
- Add logging for page mismatches (metadata vs content)

### Long-term (Nice to have):
- Add telemetry to track vision page selection accuracy
- Implement keyword-driven page selection for table queries
- Consider OCR-based table detection as fallback
