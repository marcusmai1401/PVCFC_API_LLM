# 📘 HƯỚNG DẪN INGESTION & INDEXING TÀI LIỆU

> **Tài liệu hướng dẫn đầy đủ về quy trình xử lý và lập chỉ mục tài liệu PDF cho hệ thống RAG**
>
> **Cập nhật:** 2025-11-19 (Binary Classification + 100% Spatial Coverage + OCR Default On + Single-Letter Prefix + Protobuf Fix + Parent-Child Chunking)
> **Hệ điều hành:** Windows
> **Shell:** PowerShell 5.1+

---

## 📋 MỤC LỤC

1. [Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
2. [Chuẩn bị môi trường](#2-chuẩn-bị-môi-trường)
3. [Quy trình 3 bước đơn giản](#3-quy-trình-3-bước-đơn-giản)
4. [Chi tiết từng bước](#4-chi-tiết-từng-bước)
5. [Kiểm tra kết quả](#5-kiểm-tra-kết-quả)
6. [Xử lý lỗi](#6-xử-lý-lỗi)
7. [Tham số nâng cao](#7-tham-số-nâng-cao)

---

## 1. TỔNG QUAN HỆ THỐNG

### 1.1 Dual Pipeline Architecture

Hệ thống tự động phân loại tài liệu thành **2 loại** và xử lý khác nhau:

```
PDF INPUT
    │
    ↓
CAD-like Gate (Binary Classification)
    │
    ├─ score ≥ 0.55 → CAD-like Pipeline (Extended)
    │                   ├─ Layout + Tags
    │                   ├─ Spatial Components (ALL 100% pages)
    │                   └─ 2 Indexes
    │
    └─ score < 0.55 → Non-CAD-like Pipeline (Standard)
                        ├─ Text + Chunks
                        └─ 1 Index
```

**CAD-like Pipeline (when `--enable-pid-tags`):**
- ✅ Binary classification: CAD-like vs non-CAD-like (threshold=0.55)
- ✅ Extract spatial layout (bbox, font, drawings)
- ✅ Extract instrument tags (Geometric Assembly)
- ✅ Extract spatial components for **ALL 100% pages** (complete coverage)
- ✅ Index vào 2 hệ thống: `rag_chunks` + `pvcfc_pid_spatial_components`
- ✅ OCR với Real-ESRGAN khi text < 1700 chars/page

**Non-CAD-like Pipeline (Standard):**
- ✅ Standard text extraction và chunking
- ✅ Index vào 1 hệ thống: `rag_chunks`
- ✅ OCR (no Real-ESRGAN) khi text < 40 chars/page

> **Lưu ý quan trọng:**
> - OCR **LUÔN ENABLED** by default, không cần `--enable-ocr` flag
> - CAD-like documents vẫn có standard chunks → có thể fallback sang semantic search

### 1.2 Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **OCR** | Google Cloud Vision API + Real-ESRGAN (2x upscaling) | Text detection từ scanned PDFs |
| **Vector DB** | Weaviate (gRPC) | Semantic search |
| **Keyword Search** | OpenSearch (BM25) | Keyword search |
| **P&ID Search** | Level 2 Spatial Search (component-based clustering) | Absolute accuracy cho P&ID tags |

---

## 2. CHUẨN BỊ MÔI TRƯỜNG

### 2.1 Single Environment (Không cần 2 môi trường nữa!)

**✅ CẬP NHẬT 2025-11-02:** Hệ thống chỉ cần **1 môi trường duy nhất** (`.venv`)

**Tại sao không cần 2 môi trường nữa?**
- **Trước đây (deprecated):** PaddleOCR cần protobuf 3.20.x, Weaviate cần protobuf ≥4.21 → xung đột → cần 2 môi trường
- **Bây giờ:** Google Cloud Vision API không xung đột protobuf → cài chung 1 môi trường được!

### 2.2 Setup Environment

```powershell
# 1. Di chuyển về thư mục project
cd "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC"

# 2. Tạo virtual environment (nếu chưa có)
py -3.11 -m venv .venv

# 3. Kích hoạt environment
.venv\Scripts\Activate.ps1

# 4. Cài đặt dependencies
pip install -r requirements.txt

# 5. Cấu hình Google Cloud Vision API
# Đặt biến môi trường GOOGLE_APPLICATION_CREDENTIALS
$env:GOOGLE_APPLICATION_CREDENTIALS = "path\to\your\service-account-key.json"

# 6. Kiểm tra các service đã sẵn sàng
# - Weaviate (Docker)
docker ps | Select-String weaviate

# - OpenSearch (Docker hoặc standalone)
# Kiểm tra: http://localhost:9200
```

### 2.3 Verify Installation

```powershell
# Kiểm tra Google Cloud Vision
python -c "from google.cloud import vision; print('✓ Vision API OK')"

# Kiểm tra Weaviate
python -c "import weaviate; print('✓ Weaviate OK')"

# Kiểm tra Real-ESRGAN
python -c "from realesrgan import RealESRGANer; print('✓ Real-ESRGAN OK')"
```

---

## 3. QUY TRÌNH 3 BƯỚC ĐƠN GIẢN

### ✅ Checklist nhanh (45 phút)

```
□ Bước 0: Activate .venv (1 lần duy nhất)
□ Bước 1: Process PDFs (2-3 phút)
□ Bước 2: Index vào databases (35-40 phút)
□ Bước 3: Start API (30 giây)

✓ XONG! Có thể query ngay!
```

### 3.0 Bước 0: Kích hoạt môi trường (5 giây)

```powershell
.venv\Scripts\Activate.ps1
```

**Kiểm tra:** Prompt có `(.venv)` → Đúng!

### 3.1 Bước 1: Ingestion - Xử lý PDF (5-10 phút)

```powershell
# Sử dụng production script (khuyến nghị)
python scripts\ingest_production.py

# Hoặc thủ công với parameters:
python tools/ingest.py `
  --source-dir "D:\Data_Raw" `
  --output-dir "D:\PVCFC_Artifacts\ingestion_production" `
  --workers 2 `
  --enable-pid-tags
```

**Lưu ý:**
- OCR **LUÔN ENABLED** by default, không cần `--enable-ocr` flag
- Nếu muốn tắt OCR: thêm `--no-ocr` flag
- **Phase 3**: Sử dụng Parent-Child Chunking (parent ~1800 chars, child ~400 chars)
- **Storage**: Tự động sử dụng `D:\PVCFC_Artifacts` từ `.env` (ARTIFACTS_DIR)

**Kết quả:**
- `chunks.jsonl` (~5,000 child chunks với parent_text embedded)
- `entities/tags.jsonl` (~200 tags từ Geometric Assembly)
- `page_layout/*.json` (spatial layout data)
- **Spatial components tự động được extract và index** vào `pvcfc_pid_spatial_components`
- **Xử lý ALL 100% pages** của CAD-like docs (complete coverage)

### 3.2 Bước 2: Build Indices (35-40 phút)

```powershell
# 1. Tạo OpenSearch indexes
python scripts\opensearch\create_rag_chunks_index.py --delete-if-exists
python scripts\opensearch\create_spatial_components_index.py --delete-if-exists

# 2. Index chunks vào OpenSearch + Weaviate
python scripts\utilities\index_production_chunks.py
```

**Kết quả:**
- OpenSearch `rag_chunks`: ~10,000 documents
- Weaviate `Chunk`: ~10,000 objects
- OpenSearch `pvcfc_pid_spatial_components`: ~thousands of components (đã tự động index trong ingestion)

> **Lưu ý:** Spatial components đã được tự động index trong ingestion, không cần script riêng!

### 3.3 Bước 3: Khởi động API (30 giây)

```powershell
.\launchers\start_api.ps1
```

**Kết quả:** API ready tại http://localhost:8000

---

## 4. CHI TIẾT TỪNG BƯỚC

### 4.1 Bước 1: Ingestion - Chi tiết

#### 4.1.1 Auto-Detection Process

Khi ingestion chạy, mỗi PDF được đánh giá qua CAD-like Gate:

```
PDF File
    ↓
CAD-like Gate - HYBRID DETECTION (v1.4.0)
    │
    ├─ PHASE 1: Vector Features (8 features - ALWAYS)
    │   ├─ Producer keywords (AutoCAD, Bentley, etc.) - 0.20
    │   ├─ Geometry density (vector paths/lines) - 0.15
    │   ├─ Short CAPS rate (2-4 letters) - 0.15
    │   ├─ 3-piece tag regex (dd CC-CC ddddd) - 0.20
    │   ├─ Technical suffixes (A/B/C, 2oo3) - 0.10
    │   ├─ Large page (A1/A0) - 0.05
    │   ├─ Rotated text - 0.05
    │   └─ Leader patterns - 0.10
    │   → vector_score = Σ(weight × feature)
    │
    ├─ PHASE 2: Image Features (3 features - CONDITIONAL)
    │   Trigger: IF vector_score < 0.55
    │   ├─ Shape detection (circles + rectangles) - 0.40
    │   ├─ Line detection (long lines >100px) - 0.30
    │   └─ Edge density (Canny edges) - 0.30
    │   → image_score = weighted sum @ 300 DPI
    │
    ├─ PHASE 3: Hybrid Classification (4 paths)
    │   Path 1 (VECTOR): vector_score ≥ 0.55 → CAD-like (HIGH)
    │   Path 2 (FALLBACK): No image → Use vector only
    │   Path 3 (IMAGE): vector < 0.20 → Use image score
    │   Path 4 (HYBRID): 0.20 ≤ vector < 0.55 → Combined
    │
    └─ Result: is_cadlike + confidence (HIGH/MEDIUM) + method (VECTOR/IMAGE/HYBRID)
    ├─ Short CAPS rate (2-4 letter tokens)
    ├─ 3-piece tag regex (dd CC-CC ddddd)
    ├─ Technical suffixes (A/B/C, 2oo3)
    ├─ Large page size (A1/A0)
    ├─ Rotated text spans
    └─ Leader patterns
    ↓
Score = Σ(weight × feature)
    ↓
    ├─ Score ≥ 0.55 → P&ID Pipeline
    └─ Score < 0.55 → Technical Doc Pipeline
```

#### 4.1.2 Technical Doc Processing (V1 - tools/ingest.py)

**Input:** PDF file
**Output:** `chunks.jsonl`, `doc_id_map.json`

**Quy trình (ingest V1 - legacy, semantic chunking):
1. Parse PDF (PyMuPDF)
2. Extract text (vector hoặc OCR nếu cần)
3. OCR với Google Cloud Vision + Real-ESRGAN (nếu text < threshold)
4. Semantic chunking (1000 chars, 200 overlap) bằng `TextChunker`
5. Save chunks

**Tham số mặc định (ingest V1):**
- OCR threshold: 40 chars (technical docs)
- Chunk size: 1000 chars
- Chunk overlap: 200 chars

> **Lưu ý (Phase 3 - Production):** Pipeline production dùng `scripts/ingest_production.py` với **Parent-Child Chunking** (parent ~1800 / child ~400). Mục 4.1.2 mô tả pipeline V1 (tools/ingest.py) cho mục đích tham khảo/legacy.

#### 4.1.3 CAD-like Processing (Extended)

**Input:** PDF file (đã được detect là CAD-like, score ≥ 0.55)
**Output:** `chunks.jsonl` + `tags.jsonl` + `page_layout/*.json` + **spatial components indexed**

**Quy trình mở rộng:**
1. Parse PDF (giống Non-CAD-like)
2. Extract text + OCR (nếu cần)
3. **CAD-like Gate:** Binary classification (CAD-like vs non-CAD-like, threshold=0.55)
4. **Page Layout Extraction:**
   - Vector-first: PyMuPDF text spans (bbox, font, rotation)
   - OCR fallback: Google Cloud Vision nếu vector text < 100 chars
   - Vector drawings: lines, circles, rectangles
   - Save: `page_layout/{doc_id}_p{page}_layout.json`
5. **Tag Extraction:**
   - Token classification (unit/prefix/suffix/variant)
   - PREFIX-anchored triplet assembly
   - Geometric Assembly algorithm
   - Save: `entities/tags.jsonl`
6. **Spatial Component Extraction (100% Coverage):**
   - Extract từ **TẤT CẢ 100% pages** (không chỉ taggy pages)
   - Smart layout reuse: Tái sử dụng layout từ Tag Extraction, chỉ build mới khi cần
   - Classify: unit (e.g., "04"), prefix (e.g., "PSAL"), suffix (e.g., "2207")
   - **Tự động index** vào `pvcfc_pid_spatial_components` trong ingestion
7. **Crop Generation (Optional):**
   - Render tag bboxes to PNG (DPI=200)
   - Lazy mode: Generate on-demand (default)
   - Save: `crops/{doc_id}_p{page}_{tag_hash}.png`
8. **Standard Chunking:** Vẫn tạo chunks như Non-CAD-like

**Tham số CAD-like:**
- OCR threshold: 1700 chars/page (per-page check)
- OCR enhancement: Real-ESRGAN 2x khi cần OCR
- Spatial coverage: ALL 100% pages (complete coverage)
- Crop generation: Lazy (on-demand) hoặc immediate

#### 4.1.4 OCR với Google Cloud Vision + Real-ESRGAN

**OCR LUÔN ENABLED by default!**
- Flag `--enable-ocr` DEPRECATED (luôn bật)
- Muốn tắt: dùng `--no-ocr` flag

**Quy trình OCR (per-page):**
```
PDF Page
    ↓
Check text count
    ├─ CAD-like: text < 1700 chars? → OCR + Real-ESRGAN
    └─ Non-CAD-like: text < 40 chars? → OCR only
    ↓
(Nếu cần OCR)
Render to image (Adaptive DPI: 144-216)
    ↓
Real-ESRGAN 2x upscaling (chỉ CAD-like + GPU nếu có)
    ↓
Google Cloud Vision API
    ├─ Language hints: ["en", "vi"]
    └─ Text detection
    ↓
Extract text với bounding boxes
```

**Performance (per page):**
- Baseline (no enhancement): ~4.38s/page
- With Real-ESRGAN 2x: ~21.59s/page (5x slower)
- Text improvement: +46% more text extracted
- Tag improvement: +150% more tags found

**Per-page Thresholds:**
- CAD-like: < 1700 chars/page → OCR + Real-ESRGAN
- Non-CAD-like: < 40 chars/page → OCR only
- effective_dpi < 120 → Real-ESRGAN (both types)

### 4.2 Bước 2: Indexing - Chi tiết

#### 4.2.1 Tạo OpenSearch Indexes

```powershell
# 1. Tạo rag_chunks index (cho keyword search)
python scripts\opensearch\create_rag_chunks_index.py --delete-if-exists

# 2. Tạo spatial components index (cho Level 2 P&ID search)
python scripts\opensearch\create_spatial_components_index.py --delete-if-exists
```

**Index Schemas:**
- `rag_chunks`: Text chunks với BM25 fields
- `pvcfc_pid_spatial_components`: Components với bbox, center coordinates

#### 4.2.2 Index Chunks (OpenSearch + Weaviate)

```powershell
python scripts\utilities\index_production_chunks.py
```

**Quy trình:**
1. Đọc `chunks.jsonl`
2. Batch embed texts (Gemini Embedding 001, 768D)
3. Index vào OpenSearch `rag_chunks` (BM25)
4. Index vào Weaviate `Chunk` collection (vector search)

**Thời gian:** ~35-40 phút cho 10,000 chunks

#### 4.2.3 Spatial Components Indexing

> **⚠️ QUAN TRỌNG:** Spatial components **TỰ ĐỘNG** được extract và index trong ingestion!

**Không cần script riêng** vì `tools/ingest.py` đã integrate:
- Component extraction từ PageLayout
- Bulk indexing vào `pvcfc_pid_spatial_components`
- Hành vi tự động khi `--enable-pid-tags` được set

**Kiểm tra:**
```powershell
curl -X GET "localhost:9200/pvcfc_pid_spatial_components/_count"
```

### 4.3 Bước 3: Start API

```powershell
.\launchers\start_api.ps1
```

**Verify API:**
```powershell
# Health check
Invoke-RestMethod -Uri "http://localhost:8000/healthz"

# Test query
$body = @{
    query = "What is the operating pressure of K06101?"
    language = "vi"
    query_type = "technical_doc"
    max_context = 8
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://localhost:8000/ask" `
    -Headers @{ "Content-Type" = "application/json" } `
    -Body $body
```

---

## 5. KIỂM TRA KẾT QUẢ

### 5.1 Kiểm tra Ingestion Outputs

#### Technical Doc Outputs:
```powershell
# Chunks
$chunkCount = (Get-Content "D:\\PVCFC_Artifacts\\ingestion_production\\chunks.jsonl").Count
Write-Host "✓ Created $chunkCount chunks" -ForegroundColor Green

# Doc ID map
Get-Content "D:\\PVCFC_Artifacts\\ingestion_production\\doc_id_map.json" | ConvertFrom-Json | Select-Object -First 5
```

#### P&ID Outputs:
```powershell
# Tags (Geometric Assembly)
if (Test-Path "D:\\PVCFC_Artifacts\\ingestion_production\\entities\\tags.jsonl") {
    $tagCount = (Get-Content "D:\\PVCFC_Artifacts\\ingestion_production\\entities\\tags.jsonl").Count
    Write-Host "✓ Extracted $tagCount tags" -ForegroundColor Green
}

# Page layouts
$layoutCount = (Get-ChildItem "D:\\PVCFC_Artifacts\\ingestion_production\\page_layout" -Filter "*.json").Count
Write-Host "✓ Extracted $layoutCount page layouts" -ForegroundColor Green

# Spatial components (Level 2)
$componentCount = (Invoke-RestMethod -Uri "http://localhost:9200/pvcfc_pid_spatial_components/_count").count
Write-Host "✓ Indexed $componentCount spatial components" -ForegroundColor Green
```

### 5.2 Kiểm tra Indexes

#### Weaviate:
```powershell
$body = '{ "query": "{ Aggregate { Chunk { meta { count } } } }" }'
$result = Invoke-RestMethod -Method Post -Uri "http://localhost:8080/v1/graphql" `
    -Headers @{ "Content-Type" = "application/json" } `
    -Body $body
$count = $result.data.Aggregate.Chunk[0].meta.count
Write-Host "✓ Weaviate: $count chunks" -ForegroundColor Green
```

#### OpenSearch:
```powershell
# Chunks
$chunkCount = (Invoke-RestMethod -Uri "http://localhost:9200/rag_chunks/_count").count
Write-Host "✓ OpenSearch rag_chunks: $chunkCount documents" -ForegroundColor Green

# Spatial components
$componentCount = (Invoke-RestMethod -Uri "http://localhost:9200/pvcfc_pid_spatial_components/_count").count
Write-Host "✓ OpenSearch spatial_components: $componentCount components" -ForegroundColor Green
```

### 5.3 Test Queries

#### Technical Doc Query:
```powershell
$body = @{
    query = "What are the setpoints for HCD025 gear unit?"
    language = "en"
    query_type = "technical_doc"
    max_context = 8
} | ConvertTo-Json

$response = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/ask" `
    -Headers @{ "Content-Type" = "application/json" } `
    -Body $body

Write-Host "Answer: $($response.answer)"
Write-Host "Citations: $($response.citations.Count)"
```

#### P&ID Query (Level 2 Spatial Search):
```powershell
$body = @{
    query = "What is 04 PSAL 2207 pressure alarm?"
    language = "en"
    query_type = "pid"
    max_context = 8
} | ConvertTo-Json

$response = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/ask" `
    -Headers @{ "Content-Type" = "application/json" } `
    -Body $body

Write-Host "Answer: $($response.answer)"
Write-Host "Search method: Level 2 Spatial Search" -ForegroundColor Cyan
```

---

## 6. XỬ LÝ LỖI

### 6.1 Google Cloud Vision API Errors

**Lỗi:** `google.auth.exceptions.DefaultCredentialsError`

**Nguyên nhân:** Chưa set `GOOGLE_APPLICATION_CREDENTIALS`

**Giải pháp:**
```powershell
# Set environment variable
$env:GOOGLE_APPLICATION_CREDENTIALS = "path\to\service-account-key.json"

# Verify
Test-Path $env:GOOGLE_APPLICATION_CREDENTIALS
```

**Lỗi 2:** `Descriptors cannot be created directly` (Protobuf error)

**✅ FIXED (2025-11-11):**
- Removed PaddlePaddle dependency (conflicted with protobuf)
- Upgraded protobuf to 5.29.5 (compatible with Weaviate, Google Vision, gRPC)
- Added pure-Python implementation flag in `tools/reindex_pid_tags.py`
- OCR now works without errors

### 6.2 Weaviate Connection Refused

**Lỗi:** `Connection refused` khi connect Weaviate

**Giải pháp:**
```powershell
# Kiểm tra container
docker ps | Select-String weaviate

# Nếu stopped, khởi động
docker start weaviate

# Chờ sẵn sàng
Start-Sleep -Seconds 10
Invoke-RestMethod -Uri http://localhost:8080/v1/.well-known/ready
```

### 6.3 OpenSearch Connection Errors

**Lỗi:** `Connection refused` khi connect OpenSearch

**Giải pháp:**
```powershell
# Kiểm tra OpenSearch đang chạy
Invoke-RestMethod -Uri "http://localhost:9200"

# Nếu không có, start Docker container
docker-compose up -d opensearch
```

### 6.4 Real-ESRGAN GPU Issues

**Lỗi:** CUDA out of memory hoặc GPU not found

**Giải pháp:**
- Hệ thống tự động fallback về CPU nếu GPU không khả dụng
- Có thể force CPU: `CUDA_VISIBLE_DEVICES=-1 python tools/ingest.py ...`

### 6.5 P&ID Tags Không Extract

**Triệu chứng:** File P&ID nhưng không có tags

**Nguyên nhân có thể:**
- `ENABLE_PID_TAGS=false` hoặc không set
- CAD-like score < 0.55 (threshold)
- Không có taggy pages (regex_hits < 3)
- **Single-letter prefix issue (FIXED Nov 11):** Tags với prefix 1 ký tự ("I", "P", "T") giờ đã được support

**Giải pháp:**
```powershell
# Set environment variable
$env:ENABLE_PID_TAGS = "true"

# Kiểm tra telemetry
Get-Content "D:\\PVCFC_Artifacts\\logs\\tag_extraction_telemetry.jsonl" |
    ConvertFrom-Json |
    Where-Object { $_.doc_id -eq "your_file.pdf" } |
    Select-Object cadlike_score, is_cadlike, tags_found_total
```

---

## 7. THAM SỐ NÂNG CAO

### 7.1 Ingestion Parameters

```powershell
python tools/ingest.py --help
```

**Tham số chính:**

| Tham số | Mô tả | Mặc định | Ví dụ |
|---------|-------|----------|-------|
| `--source-dir` | Thư mục PDF nguồn | (bắt buộc) | `--source-dir "D:\Data_Raw"` |
| `--output-dir` | Thư mục output | `artifacts/ingestion` | `--output-dir artifacts/ingestion_production` |
| `--no-ocr` | Tắt OCR | OCR enabled by default | `--no-ocr` |
| `--enable-pid-tags` | Bật CAD-like pipeline | `False` | `--enable-pid-tags` |
| `--workers` | Số worker threads | auto (max 4) | `--workers 2` |
| `--chunk-size` | Kích thước chunk (chars) | `1000` | `--chunk-size 1500` |
| `--chunk-overlap` | Độ overlap (chars) | `200` | `--chunk-overlap 300` |

**Thời gian xử lý (dự đoán):**
- CAD-like doc: ~5 phút/doc (với Real-ESRGAN + 100% spatial coverage)
- Non-CAD-like doc: ~1 phút/doc (không có Real-ESRGAN + spatial)

**Ví dụ nâng cao:**
```powershell
# Với OCR (default)
python tools/ingest.py `
  --source-dir "D:\Data_Raw" `
  --output-dir "D:\PVCFC_Artifacts\ingestion_production" `
  --enable-pid-tags `
  --workers 4 `
  --chunk-size 2000 `
  --chunk-overlap 400

# Không OCR (fast mode)
python tools/ingest.py `
  --source-dir "D:\Data_Raw" `
  --output-dir "D:\PVCFC_Artifacts\ingestion_production" `
  --no-ocr `
  --enable-pid-tags `
  --workers 4
```

### 7.2 Indexing Parameters

#### Index Production Chunks:
```powershell
python scripts\utilities\index_production_chunks.py --help
```

**Tham số:**
- `--chunks-file`: Path đến chunks.jsonl
- `--batch-size`: Số chunks per batch (default: 100)
- `--embedding-batch-size`: Embedding batch size (default: 256)

---

## 8. QUY TRÌNH ĐẦY ĐỦ - SUMMARY

### ✅ Complete Checklist

**Chuẩn bị:**
- [ ] `.venv` đã activate
- [ ] `GOOGLE_APPLICATION_CREDENTIALS` đã set
- [ ] Weaviate container đang chạy
- [ ] OpenSearch đang chạy

**Bước 1: Ingestion**
- [ ] Chạy `python tools/ingest.py ... --enable-ocr --enable-pid-tags`
- [ ] Kiểm tra `chunks.jsonl` được tạo
- [ ] Kiểm tra `tags.jsonl` được tạo (nếu có P&ID)
- [ ] Kiểm tra spatial components đã được index

**Bước 2: Indexing**
- [ ] Tạo OpenSearch indexes
- [ ] Index chunks vào OpenSearch + Weaviate
- [ ] Verify số lượng documents

**Bước 3: API**
- [ ] Start API server
- [ ] Test health check
- [ ] Test query

---

## 9. TÀI LIỆU THAM KHẢO

### Links hữu ích:
- **Google Cloud Vision API:** https://cloud.google.com/vision/docs
- **Weaviate Documentation:** https://weaviate.io/developers/weaviate
- **Real-ESRGAN:** https://github.com/xinntao/Real-ESRGAN

### File cấu hình:
- `config/cadlike_gate.yaml` - CAD-like Gate thresholds
- `config/tag_grammar.yaml` - Tag patterns
- `.env` - Environment variables

### Cấu trúc thư mục:
```
Code - API_LLM_PVCFC/
├── tools/
│   └── ingest.py                    # Main ingestion script
├── scripts/
│   ├── opensearch/
│   │   ├── create_rag_chunks_index.py
│   │   └── create_spatial_components_index.py
│   └── utilities/
│       └── index_production_chunks.py
├── D:\PVCFC_Artifacts\
│   └── ingestion_production\
│       ├── chunks.jsonl
│       ├── entities/tags.jsonl
│       ├── page_layout/*.json
│       └── doc_id_map.json
└── .venv/                           # Single environment (all-in-one)
```

---

**Cập nhật lần cuối:** 2025-11-02
**Version:** 3.0 (Level 2 + Google Vision OCR)
