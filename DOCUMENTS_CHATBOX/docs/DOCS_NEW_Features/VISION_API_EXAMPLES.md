# Vision API - Examples & Usage

## 1. POST /ask với Vision ON (có tài liệu)

### Request
```json
POST http://localhost:8000/api/ask
Content-Type: application/json

{
  "query": "Áp suất vận hành tối đa của KT06101 là bao nhiêu?",
  "filters": {
    "doc_id": ["PVCFC-KT06101-datasheet"]
  },
  "hyde": true,
  "max_context": 8,
  "language": "vi",
  "execution_mode": "production",
  "confidence_mode": "calibrated",
  "enable_vision_generation": true
}
```

### Expected Response
```json
{
  "answer": "Theo tài liệu [Doc 1, p.12], áp suất vận hành tối đa của thiết bị KT06101 là 10 bar ở nhiệt độ 25°C...",
  "citations": [
    {
      "doc_id": "PVCFC-KT06101-datasheet",
      "page": 12,
      "bbox": null,
      "confidence": 0.95,
      "pdf_path": "D:\\pvcfc_docs\\datasheets\\KT06101.pdf"
    }
  ],
  "context_used": ["chunk_abc123", "chunk_def456"],
  "confidence": 0.92,
  "meta": {
    "latency_ms": 3200,
    "breakdown": {
      "transform_ms": 120,
      "retrieve_ms": 450,
      "rerank_ms": 280,
      "generate_ms": 2100
    },
    "model": "gemini-2.5-pro",
    "k": 8,
    "execution_mode": "production",
    "trace_id": "unknown",
    "vision_generation": {
      "pages_used": [
        {"pdf_path": "D:\\pvcfc_docs\\datasheets\\KT06101.pdf", "page": 10},
        {"pdf_path": "D:\\pvcfc_docs\\datasheets\\KT06101.pdf", "page": 11},
        {"pdf_path": "D:\\pvcfc_docs\\datasheets\\KT06101.pdf", "page": 12},
        {"pdf_path": "D:\\pvcfc_docs\\datasheets\\KT06101.pdf", "page": 13},
        {"pdf_path": "D:\\pvcfc_docs\\datasheets\\KT06101.pdf", "page": 14}
      ],
      "pages_failed": [],
      "excerpts": []
    }
  },
  "warnings": null
}
```

### Kỳ vọng
- ✅ `meta.model` = `"gemini-2.5-pro"` (khi Vision được dùng)
- ✅ `meta.vision_generation.pages_used`: **≤ 10 trang**, **1-based**, **không trùng**
- ✅ `pages_failed`: array rỗng hoặc có items với `{pdf_path, page, reason}`
- ✅ Answer thể hiện multimodal reasoning (không chỉ lặp text context)

---

## 2. POST /ask với Vision OFF (không có tài liệu)

### Request
```json
POST http://localhost:8000/api/ask
Content-Type: application/json

{
  "query": "Công thức tính diện tích hình tròn?",
  "hyde": false,
  "max_context": 5,
  "language": "vi",
  "enable_vision_generation": true
}
```

### Expected Response
```json
{
  "answer": "Không tìm thấy thông tin cụ thể về 'Công thức tính diện tích hình tròn?' trong các tài liệu hiện có...",
  "citations": [],
  "context_used": [],
  "confidence": 0.5,
  "meta": {
    "latency_ms": 800,
    "breakdown": {...},
    "model": "gemini-2.5-flash",
    "k": 5,
    "execution_mode": "production",
    "trace_id": "unknown"
  },
  "warnings": ["No relevant documents found"]
}
```

### Kỳ vọng
- ✅ **Không có** `meta.vision_generation` (Vision không chạy)
- ✅ Log: `Vision gating: OFF (reason=no_docs_or_mapping)`
- ✅ Fallback to text-only generation

---

## 3. Chạy smoke test để xem log

```bash
# Chạy script smoke test
python scripts/vision_logging_smoke.py

# Kỳ vọng log:
# === Vision OFF (no mapping) ===
# INFO - Vision gating: OFF (reason=no_docs_or_mapping)
#
# === Vision ON (with mapping) ===
# INFO - Vision gating: ON (config enabled)
# INFO - Vision pages: used=5, failed=0, total_limit=10; pages=[10, 11, 12, 13, 14]
# INFO - Vision generation succeeded with 5 pages
```

---

## 4. Kiểm tra cấu hình

```python
from app.core.llm_constants import VISION_MODEL, RECOMMENDED_MODELS

# Xác nhận model đúng
assert VISION_MODEL == "models/gemini-2.5-pro"
assert RECOMMENDED_MODELS["production"]["heavy"]["gemini"] == "gemini-2.5-pro"
assert RECOMMENDED_MODELS["production"]["light"]["gemini"] == "gemini-2.5-flash"
```

---

## 5. Page selection logic

### Case A: Explicit range
```python
metadata = {"page_start": 5, "page_end": 8}
# → Pages: [5, 6, 7, 8]
```

### Case B: Single page với window
```python
page = 10
# → Pages: [8, 9, 10, 11, 12]  # page ± 2
```

### Case C: Edge case (page=1)
```python
page = 1
# → Pages: [1, 2, 3]  # max(1, 1-2) đến 1+2
```

### Case D: Clamp theo quota
```python
# Nếu tổng pages > 10 → chỉ lấy 10 trang đầu
# Dedup theo (pdf_path, page)
```
