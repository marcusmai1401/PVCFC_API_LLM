# Deep Discovery Search & Intelligent Classification

## Tổng quan

Tài liệu này mô tả chi tiết tính năng **Deep Discovery Search** và **Intelligent Auto-Classification** trong hệ thống PVCFC RAG v2.0. Đây là 2 tính năng chính phục vụ cho việc quản trị tri thức (Knowledge Management) và tìm kiếm toàn diện (Exhaustive Search).

### Mục tiêu

1. **Deep Discovery Search**: Tìm kiếm keyword toàn diện, trả về TẤT CẢ documents chứa keyword - không bị giới hạn bởi top_k của RAG
2. **Intelligent Auto-Classification**: Tự động phân loại tài liệu PDF vào taxonomy chuẩn hóa sử dụng Multimodal AI (Gemini 2.5 Flash)

---

## 1. Deep Discovery Search

### 1.1 Khái niệm

Deep Discovery Search là endpoint tìm kiếm keyword sử dụng OpenSearch Aggregation, khác với RAG search:

| Đặc điểm | RAG Search | Deep Discovery Search |
|----------|------------|----------------------|
| Phương pháp | Vector similarity + BM25 | Keyword match only |
| Giới hạn kết quả | top_k (thường 10-50) | Tất cả documents (max 10,000) |
| Sử dụng LLM | Có | Không |
| Mục đích | Trả lời câu hỏi | Tìm tất cả tài liệu chứa keyword |

### 1.2 API Endpoint

```
GET /api/search/documents
```

**Parameters:**
- `keyword` (required): Từ khóa tìm kiếm (1-200 ký tự)
- `category` (optional): Lọc theo category (ENGINEERING_DESIGN, VENDOR_EQUIPMENT, etc.)
- `doc_type` (optional): Lọc theo loại tài liệu (P&ID, Datasheet, etc.)
- `max_results` (optional): Số lượng tối đa documents trả về (default: 1000, max: 10000)

**Response:**
```json
{
  "query": "KT06101",
  "total_documents": 5,
  "results": [
    {
      "doc_id": "DOCID_KT06101_TURBINE_HTC_...",
      "filename": "KT06101-Packing list-Detail.pdf",
      "category": "VENDOR_EQUIPMENT",
      "doc_type": "Material Partlist",
      "occurrence_count": 15,
      "first_page": 2,
      "snippet": "...equipment tag KT06101 located in section A-1..."
    }
  ],
  "results_by_category": {
    "VENDOR_EQUIPMENT": [...],
    "ENGINEERING_DESIGN": [...]
  }
}
```

### 1.3 Cách hoạt động

1. **Query Building**: Sử dụng OpenSearch `match` query với operator `and`
2. **Aggregation**: Group kết quả theo `doc_id` để lấy unique documents
3. **Top Hits**: Lấy thông tin chi tiết từ document đầu tiên trong mỗi bucket
4. **Filtering**: Áp dụng category/doc_type filter nếu có

**OpenSearch Query Structure:**
```json
{
  "size": 0,
  "query": {
    "bool": {
      "must": [
        {
          "match": {
            "text": {
              "query": "KT06101",
              "operator": "and"
            }
          }
        }
      ],
      "filter": [
        {"term": {"category": "VENDOR_EQUIPMENT"}}
      ]
    }
  },
  "aggs": {
    "unique_documents": {
      "terms": {
        "field": "doc_id",
        "size": 10000
      },
      "aggs": {
        "doc_info": {
          "top_hits": {
            "size": 1,
            "_source": ["doc_id", "file_name", "category", "doc_type", "page", "text"]
          }
        },
        "occurrence_count": {
          "value_count": {"field": "_id"}
        }
      }
    }
  }
}
```

### 1.4 OpenSearch Index Structure

Documents được lưu trong index `rag_chunks` với các fields chính:

| Field | Type | Mô tả |
|-------|------|-------|
| `text` | text | Nội dung chunk |
| `doc_id` | keyword | ID unique của document |
| `file_name` | keyword | Tên file PDF gốc |
| `category` | keyword | Category phân loại |
| `doc_type` | keyword | Loại tài liệu |
| `page` | integer | Số trang |
| `chunk_id` | keyword | ID unique của chunk |
| `classification_status` | keyword | Trạng thái phân loại |
| `classification_confidence` | float | Độ tin cậy phân loại |
| `classification_method` | keyword | Phương pháp phân loại |

---

## 2. Intelligent Auto-Classification

### 2.1 Document Taxonomy (4-Category System)

```
├── ENGINEERING_DESIGN
│   ├── P&ID
│   ├── Drawing
│   └── Technical Data
│
├── VENDOR_EQUIPMENT
│   ├── Datasheet
│   ├── Material Partlist
│   └── Vendor Manual
│
├── OPERATIONS_MAINTENANCE
│   ├── Operation Instruction
│   ├── Maintenance Instruction
│   ├── Maintenance History
│   └── Inventory
│
├── SAFETY_MANAGEMENT
│   ├── MOC
│   ├── RCA
│   └── Pictures
│
└── UNCATEGORIZED
    └── Unknown
```

### 2.2 Classification Pipeline

```
PDF Upload
    │
    ▼
┌─────────────────────────┐
│  Adaptive Page Sampler  │  ← Lấy mẫu 10 trang (Head-Body-Tail)
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│    CADLikeGate Check    │  ← Guardrail cho P&ID
└─────────────────────────┘
    │
    ├── CAD_score >= 0.55 ──► Force P&ID Classification
    │
    └── CAD_score < 0.55
            │
            ▼
    ┌─────────────────────────┐
    │  Gemini 2.5 Flash AI    │  ← Multimodal classification
    └─────────────────────────┘
            │
            ├── confidence >= 0.5 ──► Store Classification
            │
            └── confidence < 0.5 ──► UNCATEGORIZED + NEEDS_REVIEW
```

### 2.3 Adaptive Page Sampling Strategy

**Mục đích**: Lấy mẫu trang thông minh để phân loại tài liệu dài hiệu quả

| Số trang PDF | Strategy | Pages sampled |
|--------------|----------|---------------|
| ≤ 10 pages | All | Tất cả trang |
| > 10 pages | Head-Body-Tail | 10 trang |

**Head-Body-Tail Strategy:**
- **Head (3 pages)**: Trang 1, 2, 3 - Cover, TOC
- **Body (5 pages)**: 5 trang phân bố đều ở giữa
- **Tail (2 pages)**: Trang N-1, N - Appendix, signatures

### 2.4 P&ID Safety Guardrail (CADLikeGate)

CADLikeGate là module phát hiện P&ID/CAD-like documents:

- **Threshold**: CAD_score >= 0.55
- **Khi trigger**: Force assign `category=ENGINEERING_DESIGN`, `doc_type=P&ID`
- **Mục đích**: Đảm bảo P&ID không bao giờ bị misclassify

### 2.5 Gemini AI Classification

Khi CADLikeGate không trigger, sử dụng Gemini 2.5 Flash:

1. **Input**: Page images (PNG) từ sampler
2. **Dominant Content Rule**: 
   - Nếu >50% pages là text → classify as text-based doc
   - Nếu >50% pages là drawing → classify as drawing-based doc
3. **Output**: category, doc_type, confidence score
4. **Fallback**: confidence < 0.5 → UNCATEGORIZED + NEEDS_REVIEW

---

## 3. Batch Re-classification

### 3.1 Script Location

```
scripts/utilities/batch_reclassify.py
```

### 3.2 Chức năng

Script để classify lại tất cả documents đã có trong hệ thống:

- Quét tất cả documents từ OpenSearch
- Chạy classification pipeline cho từng document
- Update metadata trong cả OpenSearch và Weaviate
- Hỗ trợ checkpoint/resume
- Rate limiting để tránh overload API

### 3.3 Cách sử dụng

```bash
# Activate virtual environment
.venv\Scripts\Activate.ps1

# Run batch reclassification
python scripts/utilities/batch_reclassify.py
```

**Output:**
```
Processing 77 documents...
[1/77] DOCID_xxx - P&ID (CADLikeGate, confidence: 0.98)
[2/77] DOCID_yyy - Vendor Manual (AI, confidence: 0.85)
...
Results saved to artifacts/reclassify_results.json
```

---

## 4. Cấu hình

### 4.1 Environment Variables

```env
# Gemini API Key (hỗ trợ cả 2 tên)
GOOGLE_API_KEY=your_api_key
# hoặc
GEMINI_API_KEY=your_api_key

# OpenSearch
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
OPENSEARCH_INDEX=rag_chunks

# Weaviate
WEAVIATE_HOST=localhost
WEAVIATE_PORT=8080
```

### 4.2 Classification Thresholds

| Parameter | Value | Mô tả |
|-----------|-------|-------|
| CAD_score threshold | 0.55 | Ngưỡng để force P&ID |
| Confidence threshold | 0.5 | Ngưỡng để accept AI classification |
| Max sample pages | 10 | Số trang tối đa để sample |
| DPI for rendering | 150 | Độ phân giải render page |

---

## 5. Streamlit UI

### 5.1 Deep Search Tab

Truy cập: `http://localhost:8501` → Deep Search

**Features:**
- Search bar cho keyword input
- Dropdown filters cho category và doc_type
- Results grouped by category
- View button để mở PDF tại trang chứa keyword

### 5.2 Document Explorer

Truy cập: `http://localhost:8501` → Document Explorer

**Features:**
- Tree view với 4 category chính
- Expand để xem doc_types và files
- Classification status badges
- Re-classify button cho từng document

---

## 6. Troubleshooting

### 6.1 Deep Search trả về 0 kết quả

**Nguyên nhân có thể:**
1. Keyword không tồn tại trong index
2. Field names không đúng (đã fix: fields ở root level, không phải trong `metadata`)

**Kiểm tra:**
```bash
# Test trực tiếp với OpenSearch
curl -X POST "http://localhost:9200/rag_chunks/_search" \
  -H "Content-Type: application/json" \
  -d '{"size": 1, "query": {"match": {"text": "KT06101"}}}'
```

### 6.2 Classification không hoạt động

**Kiểm tra:**
1. GOOGLE_API_KEY hoặc GEMINI_API_KEY đã set chưa
2. Gemini API có accessible không
3. PDF có readable không

### 6.3 API trả về 404

**Nguyên nhân:** Router prefix không đúng

**Fix đã áp dụng:**
```python
# app/api/routers/search.py
router = APIRouter(prefix="/api/search", tags=["search"])
```

---

## 7. Files quan trọng

| File | Mô tả |
|------|-------|
| `app/services/deep_search.py` | DeepSearchService implementation |
| `app/api/routers/search.py` | Deep Search API endpoint |
| `app/classification/pipeline.py` | Classification pipeline |
| `app/classification/classifier.py` | Gemini AI classifier |
| `app/classification/sampler.py` | Adaptive page sampler |
| `app/classification/taxonomy.py` | Document taxonomy |
| `scripts/utilities/batch_reclassify.py` | Batch re-classification script |
| `streamlit_app/pages/deep_search.py` | Deep Search UI |

---

## 8. Kết quả đã đạt được

### 8.1 Batch Re-classification Results

- **Total documents**: 77
- **P&ID (CADLikeGate)**: 39 documents
- **AI Classified**: 38 documents
- **Failures**: 0
- **Chunks updated**: 6,470

### 8.2 Test Coverage

- **Total tests**: 156
- **Passed**: 156
- **Coverage**: API, Classification, Deep Search modules

---

## 9. Changelog

### v2.0.0 (2024-12-03)

- ✅ Implemented Deep Discovery Search endpoint
- ✅ Implemented Intelligent Auto-Classification with Gemini 2.5 Flash
- ✅ Integrated CADLikeGate P&ID guardrail
- ✅ Added Adaptive Page Sampling (Head-Body-Tail)
- ✅ Updated OpenSearch/Weaviate metadata schema
- ✅ Created batch re-classification script
- ✅ Built Streamlit UI for Deep Search and Document Explorer
- ✅ Fixed API endpoint routing (`/api/search/documents`)
- ✅ Fixed OpenSearch field names (root level vs metadata)
- ✅ Fixed GOOGLE_API_KEY/GEMINI_API_KEY compatibility
