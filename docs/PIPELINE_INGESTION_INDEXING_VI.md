# PIPELINE INGESTION VÀ INDEXING - HỆ THỐNG PVCFC RAG

**Tài liệu kỹ thuật tiếng Việt**
**Phiên bản:** 1.0
**Ngày cập nhật:** 2025-01-07
**Mục đích:** Giải thích chi tiết luồng xử lý từ PDF gốc đến dữ liệu có thể truy vấn

---

## 📋 MỤC LỤC

1. [Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
2. [Kiến trúc Dual Pipeline](#2-kiến-trúc-dual-pipeline)
3. [Phase 1: Ingestion - Xử lý tài liệu](#3-phase-1-ingestion---xử-lý-tài-liệu)
4. [Phase 2: Indexing - Lập chỉ mục](#4-phase-2-indexing---lập-chỉ-mục)
5. [So sánh hai loại tài liệu](#5-so-sánh-hai-loại-tài-liệu)
6. [Cấu hình quan trọng](#6-cấu-hình-quan-trọng)
7. [Ví dụ thực tế](#7-ví-dụ-thực-tế)

---

## 1. TỔNG QUAN HỆ THỐNG

### 1.1 Mục tiêu chính

Hệ thống được thiết kế để:
- **Xử lý tự động** hàng nghìn tài liệu PDF (P&ID, Manual, Datasheet)
- **Phân loại thông minh** tài liệu theo loại và xử lý phù hợp
- **Trích xuất nội dung** chính xác từ cả PDF vector và scan
- **Lập chỉ mục** vào nhiều hệ thống để tối ưu tìm kiếm
- **Hỗ trợ truy vấn** cả ngữ nghĩa lẫn từ khóa chính xác

### 1.2 Luồng dữ liệu tổng quan

```
┌─────────────────────────────────────────────────────────────┐
│                    FILE PDF GỐC                             │
│          (từ thư mục D:\Data_Raw\)                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│              BƯỚC 1: PHÂN LOẠI TỰ ĐỘNG                      │
│  "Đây là bản vẽ kỹ thuật (P&ID) hay tài liệu văn bản?"      │
└────────────────────────┬────────────────────────────────────┘
                         │
                    ┌────┴────┐
                    │         │
         ┌──────────▼─┐    ┌─▼──────────┐
         │  P&ID      │    │  Technical │
         │  (CAD-like)│    │  Document  │
         └──────┬─────┘    └─────┬──────┘
                │                │
                ↓                ↓
    ┌───────────────────┐   ┌──────────────┐
    │ XỬ LÝ MỞ RỘNG     │   │ XỬ LÝ CHUẨN  │
    │ - Layout          │   │ - Text       │
    │ - Tags            │   │ - Chunks     │
    │ - Spatial         │   │              │
    └───────┬───────────┘   └──────┬───────┘
            │                      │
            └──────────┬───────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│              BƯỚC 2: LẬP CHỈ MỤC (3 HỆ THỐNG)               │
│  1. Weaviate (vector 768D) - tìm kiếm ngữ nghĩa             │
│  2. OpenSearch rag_chunks (BM25) - tìm kiếm từ khóa         │
│  3. OpenSearch spatial_components - tìm kiếm không gian     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│              DỮ LIỆU SẴN SÀNG TRẢ LỜI                       │
│           (User có thể query và nhận kết quả)               │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 Công nghệ sử dụng

| Thành phần | Công nghệ | Vai trò |
|------------|-----------|---------|
| **OCR** | Google Cloud Vision API + Real-ESRGAN | Đọc text từ ảnh scan, tăng chất lượng ảnh |
| **Vector DB** | Weaviate (768 chiều) | Tìm kiếm theo ngữ nghĩa |
| **Keyword Search** | OpenSearch BM25 | Tìm kiếm từ khóa chính xác |
| **Spatial Search** | OpenSearch spatial | Tìm tag P&ID theo vị trí |
| **Embedding** | Gemini embedding-001 | Chuyển text thành vector |

---

## 2. KIẾN TRÚC DUAL PIPELINE

### 2.1 Tại sao cần 2 pipeline?

Hệ thống xử lý 2 loại tài liệu rất khác nhau:

**Loại 1: P&ID (Bản vẽ kỹ thuật)**
- Nhiều ký hiệu, mã thiết bị (ví dụ: "04 PSAL 2207")
- Text nhỏ, rải rác trên bản vẽ
- Cần hiểu vị trí không gian (tag ở đâu trên bản vẽ?)
- Ưu tiên độ chính xác tuyệt đối

**Loại 2: Technical Document (Tài liệu văn bản)**
- Văn bản liên tục, có đoạn văn
- Ít ký hiệu kỹ thuật
- Cần hiểu ngữ nghĩa (nghĩa của câu, đoạn)
- Ưu tiên tìm kiếm theo ý nghĩa

### 2.2 Quyết định phân loại tự động

**Hệ thống tự động phân loại dựa trên 8 đặc điểm:**

```
BƯỚC PHÂN LOẠI TỰ ĐỘNG (CAD-like Gate)
│
├─ Đặc điểm 1: Kiểm tra metadata PDF
│  → Có từ khóa "AutoCAD", "Bentley"? (+20 điểm)
│
├─ Đặc điểm 2: Đếm đường vẽ vector
│  → Nhiều đường thẳng, đường cong? (+15 điểm)
│
├─ Đặc điểm 3: Tỷ lệ text viết hoa ngắn
│  → Nhiều chữ 2-4 ký tự viết hoa (VD, PT, FIC)? (+15 điểm)
│
├─ Đặc điểm 4: Pattern mã thiết bị
│  → Có pattern "số số chữ chữ số số số số"? (+20 điểm)
│
├─ Đặc điểm 5: Hậu tố kỹ thuật
│  → Có A/B/C, 2oo3, -201B? (+10 điểm)
│
├─ Đặc điểm 6: Kích thước trang
│  → Trang A1, A0 (lớn)? (+10 điểm)
│
├─ Đặc điểm 7: Text xoay
│  → Có text xoay 90°, 180°? (+5 điểm)
│
└─ Đặc điểm 8: Đường dẫn (leader lines)
   → Có đường dẫn từ text đến thiết bị? (+5 điểm)

TỔNG ĐIỂM = Tổng các điểm trên

► Nếu TỔNG ĐIỂM ≥ 0.55 → P&ID Pipeline
► Nếu TỔNG ĐIỂM < 0.55 → Technical Document Pipeline
```

**Ví dụ:**
- File "01. P&ID Ammonia Unit.pdf" → điểm 0.78 → **P&ID Pipeline**
- File "Compressor Manual.pdf" → điểm 0.12 → **Technical Document Pipeline**

---

## 3. PHASE 1: INGESTION - XỬ LÝ TÀI LIỆU

### 3.1 Bước 1: Phát hiện và loại trùng

```
QUÉT THƯ MỤC NGUỒN
│
├─ Tìm tất cả file .pdf trong D:\Data_Raw\ (recursive)
│  → Tìm thấy 150 file PDF
│
├─ Với mỗi file, tính hash (SHA256)
│  → File 1: hash_abc123
│  → File 2: hash_def456
│  → File 3: hash_abc123 (trùng với File 1!)
│
├─ Loại bỏ file trùng 100%
│  → File 3 bị bỏ qua (duplicate)
│  → Còn lại 148 file duy nhất
│
└─ Tạo danh sách xử lý
   → 148 file sẽ được xử lý tiếp
```

**Lý do:** Tránh xử lý lặp lại file giống hệt nhau (copy, backup)

### 3.2 Bước 2: Phân loại tài liệu (CAD-like Gate)

Đây là bước **QUAN TRỌNG NHẤT** quyết định cách xử lý tiếp theo.

```
ĐỌC THÔNG TIN CƠ BẢN PDF
│
├─ Lấy 5 trang mẫu: trang 1, 2, 3, giữa, cuối
│
├─ Phân tích từng trang mẫu:
│  │
│  ├─ Đếm số đường vẽ vector (lines, circles, rectangles)
│  ├─ Đếm text viết hoa ngắn (2-4 ký tự)
│  ├─ Tìm pattern mã thiết bị (regex)
│  ├─ Kiểm tra metadata (Creator, Producer)
│  └─ Đo kích thước trang
│
├─ Tính điểm CAD-like (0.0 → 1.0)
│  → Ví dụ: 0.78 cho P&ID, 0.12 cho Manual
│
└─ QUYẾT ĐỊNH:
   ├─ Điểm ≥ 0.55 → CAD-LIKE → Pipeline mở rộng
   └─ Điểm < 0.55 → NON-CAD-LIKE → Pipeline chuẩn
```

### 3.3 Bước 3A: Xử lý P&ID (Pipeline mở rộng)

Khi file được xác định là P&ID, hệ thống thực hiện **10 bước chi tiết:**

#### **Bước 3A.1: Trích xuất text ban đầu**

```
MỞ PDF
│
├─ Thử đọc text trực tiếp từ PDF (vector text)
│  → Trang 113: tìm được 1376 ký tự
│
├─ KIỂM TRA NGƯỠNG:
│  │
│  ├─ Với P&ID: ngưỡng = 1700 ký tự/trang
│  │  → 1376 < 1700 → CÁN OCR!
│  │
│  └─ Lý do ngưỡng cao: P&ID có nhiều text nhỏ,
│     text trong ảnh, text bị mất trong PDF vector
│
└─ Quyết định: Trang này CẦN OCR
```

#### **Bước 3A.2: Tăng cường chất lượng ảnh (Real-ESRGAN)**

```
CHUẨN BỊ TRANG CHO OCR
│
├─ Render trang PDF thành ảnh PNG
│  → DPI thích ứng: 144-216 DPI
│  → Trang 113: 3508 x 2480 pixels
│
├─ ÁP DỤNG Real-ESRGAN (AI upscaling 2x)
│  │
│  ├─ Mục đích: Làm rõ text nhỏ, mờ
│  ├─ Upscale 2x: 3508 → 7016 pixels
│  └─ Thời gian: ~21 giây/trang (chậm nhưng chính xác)
│
└─ Kết quả: Ảnh siêu rõ nét, text dễ đọc
```

**Giải thích Real-ESRGAN:**
- Là mô hình AI học cách "đoán" chi tiết bị mất
- Biến ảnh mờ thành ảnh rõ, như phép màu
- Đặc biệt tốt cho text nhỏ trên bản vẽ

#### **Bước 3A.3: OCR với Google Cloud Vision**

```
GỬI ẢNH ĐẾN GOOGLE CLOUD VISION
│
├─ Request: DOCUMENT_TEXT_DETECTION
│  → Ngôn ngữ: tiếng Việt + tiếng Anh
│
├─ Google trả về:
│  │
│  ├─ Toàn bộ text trên ảnh: "29 SG 2201A..."
│  │
│  └─ Vị trí từng text (bounding box):
│     ├─ "29" ở (x:1688, y:525) kích thước 10x12
│     ├─ "SG" ở (x:1690, y:545) kích thước 14x10
│     └─ "2201A" ở (x:1685, y:560) kích thước 30x12
│
└─ Kết quả: Text + Vị trí chính xác của mỗi chữ
```

#### **Bước 3A.4: Tổ hợp hình học (Geometric Assembly)**

Đây là bước **ĐỘC ĐÁO** của hệ thống - ghép các text riêng lẻ thành tag hoàn chỉnh.

```
TỔ HỢP CÁC TEXT THÀNH TAG
│
├─ Vấn đề: OCR trả về text rời rạc
│  "29", "SG", "2201A" → Làm sao biết chúng là 1 tag?
│
├─ CHIẾN LƯỢC PREFIX-ANCHORED:
│  │
│  ├─ Bước 1: Tìm PREFIX (chữ cái, VD: SG, PSAL, PT)
│  │  → Tìm thấy "SG" ở (1690, 545)
│  │
│  ├─ Bước 2: Tìm UNIT (số 1-2 chữ số) PHÍA TRÊN PREFIX
│  │  → Tìm "29" ở (1688, 525) - cách PREFIX 20px
│  │  → Kiểm tra: có cùng cột không? (x gần nhau)
│  │  → ✓ Hợp lệ!
│  │
│  ├─ Bước 3: Tìm SUFFIX (số 3-5 chữ số) PHÍA DƯỚI PREFIX
│  │  → Tìm "2201A" ở (1685, 560) - cách PREFIX 15px
│  │  → Kiểm tra: có cùng cột không?
│  │  → ✓ Hợp lệ!
│  │
│  └─ Bước 4: Ghép thành TAG HOÀN CHỈNH
│     → UNIT + PREFIX + SUFFIX = "29 SG 2201A"
│
└─ Kết quả: TAG hoàn chỉnh với độ tin cậy cao
```

**Quy tắc geometric assembly:**
- Text cùng cột (cách nhau < 20 pixels theo X)
- Khoảng cách hợp lý (< 30 pixels theo Y)
- Đúng thứ tự: UNIT trên, PREFIX giữa, SUFFIX dưới
- Font size tương đương

#### **Bước 3A.5: Trích xuất spatial components (Level 2)**

```
PHÂN TÍCH CẤU TRÚC KHÔNG GIAN
│
├─ Mục đích: Lưu TỪNG THÀNH PHẦN RIÊNG LẺ để tìm kiếm
│
├─ PHÂN LOẠI text theo regex:
│  │
│  ├─ Pattern ^\\d{1,2}$ → UNIT (1-2 chữ số)
│  │  Ví dụ: "04", "29", "8"
│  │
│  ├─ Pattern ^[A-Z]{1,6}$ → PREFIX (chữ cái)
│  │  Ví dụ: "PSAL", "SG", "PT", "FIC"
│  │
│  └─ Pattern ^\\d{3,5}[A-Z]?$ → SUFFIX (3-5 số + chữ)
│     Ví dụ: "2207", "2201A", "1234B"
│
├─ LƯU TỪNG COMPONENT VỚI METADATA:
│  {
│    "component": "29",
│    "type": "unit",
│    "bbox": {"x0": 1688, "y0": 525, "x1": 1698, "y1": 537},
│    "center_x": 1693,
│    "center_y": 531,
│    "page": 113
│  }
│
└─ Ví dụ trang 113:
   ├─ 15 units: "04", "29", "8"...
   ├─ 12 prefixes: "PSAL", "SG", "PT"...
   └─ 10 suffixes: "2207", "2201A"...
   TỔNG: 247 components
```

**Tại sao cần spatial components?**
- Tìm kiếm CHÍNH XÁC: User hỏi "04 PSAL 2207" → Tìm đúng vị trí trên bản vẽ
- Tìm thiết bị GẦN NHAU: "Tìm tất cả thiết bị gần PT 1234"
- Phân tích mật độ: "Khu vực nào có nhiều thiết bị nhất?"

#### **Bước 3A.6: Tạo crops (PNG của tag)**

```
TẠO ẢNH CẮT (CROP) CHO MỖI TAG
│
├─ Mục đích: Có ảnh minh họa cho mỗi tag
│
├─ Với mỗi tag "29 SG 2201A":
│  │
│  ├─ Lấy bounding box bao quanh tag
│  │  → bbox: (x0:1685, y0:520, x1:1715, y1:572)
│  │
│  ├─ Thêm margin 10px
│  │  → bbox_expanded: (1675, 510, 1725, 582)
│  │
│  ├─ Cắt ảnh PDF tại vùng này
│  │  → Render với DPI=200
│  │
│  └─ Lưu file PNG
│     → crops/Ammonia_p113_29_SG_2201A.png
│
├─ Chế độ lazy (mặc định):
│  → Tạo crop KHI CẦN, không phải lúc ingestion
│  → Tiết kiệm thời gian và dung lượng
│
└─ Kết quả: 347 crops cho 347 tags
```

#### **Bước 3A.7: Chunking (chia nhỏ text)**

```
CHIA NỘI DUNG THÀNH CHUNKS
│
├─ Text của trang 113:
│  "29 SG 2201A steam generator...
│   04 PSAL 2207 pressure alarm...
│   General Notes: All valves..."
│  (Tổng: ~3500 ký tự)
│
├─ CHIẾN LƯỢC: Hierarchical chunking
│  │
│  ├─ Tôn trọng cấu trúc: heading, section, paragraph
│  ├─ Kích thước mục tiêu: 1000 ký tự/chunk
│  ├─ Overlap: 200 ký tự (để giữ ngữ cảnh)
│  │
│  └─ Kết quả cho trang 113:
│     ├─ Chunk 0: "29 SG 2201A steam..." (998 chars)
│     ├─ Chunk 1: "...generator details..." (1024 chars)
│     └─ Chunk 2: "...General Notes..." (856 chars)
│
├─ METADATA được gắn vào mỗi chunk:
│  {
│    "chunk_id": "Ammonia_P&ID_chunk_0",
│    "doc_id": "Ammonia_P&ID_04000",
│    "page": 113,
│    "tags": ["29 SG 2201A", "04 PSAL 2207"],
│    "doc_type": "CAD-like",
│    "text": "29 SG 2201A steam generator..."
│  }
│
└─ Toàn bộ file: 25 trang → 67 chunks
```

**Tại sao chunk?**
- Vector embedding giới hạn độ dài input (thường 512 tokens)
- Chunk nhỏ → kết quả tìm kiếm chính xác hơn
- Overlap → tránh mất ngữ cảnh giữa các chunk

### 3.4 Bước 3B: Xử lý Technical Document (Pipeline chuẩn)

Với tài liệu văn bản thông thường, quy trình **ĐƠN GIẢN HƠN NHIỀU:**

```
XỬ LÝ TECHNICAL DOCUMENT
│
├─ Bước 1: Trích xuất text vector
│  → Đọc trực tiếp từ PDF
│  → Manual trang 5: 2340 ký tự
│
├─ Bước 2: Kiểm tra ngưỡng OCR
│  │
│  ├─ Ngưỡng cho Technical Doc: 40 ký tự/trang
│  │  → 2340 > 40 → KHÔNG CẦN OCR
│  │
│  └─ Chỉ OCR nếu: trang scan hoặc text < 40
│
├─ Bước 3: Chunking (giống P&ID)
│  → 1000 chars/chunk, 200 overlap
│  → Manual 150 trang → 456 chunks
│
├─ KHÔNG LÀM:
│  ✗ Không trích layout
│  ✗ Không tìm tags
│  ✗ Không spatial components
│  ✗ Không crops
│
└─ Kết quả: Chỉ có chunks với metadata cơ bản
```

**So sánh thời gian xử lý:**
- P&ID (25 trang): ~5 phút (có Real-ESRGAN + spatial)
- Manual (150 trang): ~3 phút (chỉ text + chunking)

### 3.5 Bước 4: Finalization (Hoàn tất)

```
TẠO CÁC FILE KẾT QUẢ
│
├─ File 1: chunks.jsonl
│  → Chứa TẤT CẢ chunks từ tất cả file
│  → Ví dụ: 6758 chunks từ 25 files
│  → Mỗi dòng = 1 chunk (JSON)
│
├─ File 2: doc_id_map.json
│  → Map doc_id → đường dẫn PDF gốc
│  → Dùng để hiển thị citation về sau
│
├─ File 3: entities/tags.jsonl (chỉ P&ID)
│  → Chứa TẤT CẢ tags đã trích xuất
│  → Ví dụ: 347 tags từ 5 P&ID files
│
├─ File 4: manifests/corpus.jsonl
│  → Thống kê metadata từng file
│  → pages, source_format, doc_type...
│
└─ THỐNG KÊ:
   ├─ Tổng files: 25
   ├─ Processed: 25
   ├─ Total chunks: 6758
   ├─ P&ID tags: 347
   ├─ Spatial components: 12,450
   └─ Thời gian: 4.5 giờ
```

**Vị trí lưu trữ:**
```
artifacts/ingestion_production/
├── chunks/
│   └── chunks.jsonl                   (6758 dòng)
├── entities/
│   └── tags.jsonl                     (347 dòng)
├── page_layout/
│   ├── page_Ammonia_113.json
│   └── ...
├── manifests/
│   ├── corpus.jsonl
│   └── doc_id_map.json
└── logs/
    └── tag_extraction_telemetry.jsonl
```

---

## 4. PHASE 2: INDEXING - LẬP CHỈ MỤC

Sau khi có chunks.jsonl, hệ thống lập chỉ mục vào **3 hệ thống độc lập** để phục vụ các kiểu truy vấn khác nhau.

### 4.1 Tại sao cần 3 hệ thống index?

```
3 KIỂU TRẢ LỜI CÂU HỎI KHÁC NHAU:

┌─────────────────────────────────────────────────────────┐
│ Câu hỏi 1: "Áp suất vận hành là bao nhiêu?"             │
│ → Cần: Tìm theo NGỮ NGHĨA                               │
│ → Dùng: WEAVIATE (vector search)                        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Câu hỏi 2: "Tìm tài liệu về K06101"                     │
│ → Cần: Tìm chính xác TỪ KHÓA "K06101"                   │
│ → Dùng: OPENSEARCH BM25                                 │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Câu hỏi 3: "Tag 04 PSAL 2207 ở đâu trên bản vẽ?"        │
│ → Cần: Tìm theo VỊ TRÍ KHÔNG GIAN                       │
│ → Dùng: OPENSEARCH SPATIAL                              │
└─────────────────────────────────────────────────────────┘
```

### 4.1.1 Cách 3 hệ thống hoạt động: ĐỘC LẬP + SONG SONG

**⚠️ QUAN TRỌNG:** 3 hệ thống này hoạt động **ĐỘC LẬP** với nhau nhưng được **SỬ DỤNG SONG SONG** khi truy vấn!

```
┌─────────────────────────────────────────────────────────────┐
│                   GIAI ĐOẠN 1: INDEXING                    │
│              (3 hệ thống hoạt động ĐỘC LẬP)                │
└─────────────────────────────────────────────────────────────┘

DỮ LIỆU CHUNG: chunks.jsonl (6,758 chunks)
       │
       ├───────────┬───────────┬────────────┐
       │           │           │            │
       ↓           ↓           ↓            ↓
  ┌────────┐  ┌────────┐  ┌────────┐
  │Weaviate│  │OpenSrch│  │OpenSrch│
  │        │  │ BM25   │  │Spatial │
  │768D vec│  │keyword │  │geo     │
  └────────┘  └────────┘  └────────┘
       ↓           ↓           ↓
   Index 1     Index 2     Index 3
  (riêng rẽ)  (riêng rẽ)  (riêng rẽ)

→ Mỗi hệ thống LƯU RIÊNG data của nó
→ KHÔNG phụ thuộc vào nhau
→ Có thể index TUẦN TỰ hoặc SONG SONG

┌─────────────────────────────────────────────────────────────┐
│                   GIAI ĐOẠN 2: QUERY                        │
│          (3 hệ thống được GỌI SONG SONG hoặc CHỌN LỌC)     │
└─────────────────────────────────────────────────────────────┘

USER QUERY: "Áp suất của K06101 là bao nhiêu?"
       │
       ↓
┌──────────────────────┐
│ QUERY ROUTER         │ ← Phân tích câu hỏi
│ - Loại: Semantic     │
│ - Có keyword: K06101 │
│ - Không phải P&ID    │
└──────────────────────┘
       │
       ├────────────┬─────────────┐
       ↓            ↓             ↓
  ┌────────┐   ┌────────┐   ┌────────┐
  │Weaviate│   │OpenSrch│   │SKIP    │
  │ CALL   │   │ CALL   │   │(không  │
  │        │   │        │   │ cần)   │
  └────┬───┘   └────┬───┘   └────────┘
       │            │
       ↓            ↓
   Kết quả 1    Kết quả 2
   (50 chunks)  (50 chunks)
       │            │
       └─────┬──────┘
             ↓
      ┌────────────┐
      │ RRF FUSION │ ← Kết hợp kết quả
      └─────┬──────┘
            ↓
      TOP 10 chunks
            ↓
      ANSWER GENERATION
```

#### **Chi tiết hoạt động:**

**1. LÚC INDEXING (Độc lập, song song):**
```
# Script chạy tuần tự nhưng các hệ thống KHÔNG phụ thuộc nhau

[Bước 1] Index vào Weaviate
├─ Đọc chunks.jsonl
├─ Tạo embedding (768D)
├─ Lưu vào Weaviate
└─ XONG → Weaviate có đầy đủ data

[Bước 2] Index vào OpenSearch BM25
├─ Đọc chunks.jsonl (CÙNG FILE)
├─ KHÔNG cần embedding
├─ Lưu vào OpenSearch index "rag_chunks"
└─ XONG → OpenSearch BM25 có đầy đủ data

[Bước 3] Index spatial (chỉ P&ID)
├─ Đọc spatial_components.jsonl
├─ Lưu vào OpenSearch index "pvcfc_pid_spatial_components"
└─ XONG → Spatial có đầy đủ data

→ Nếu 1 hệ thống lỗi, 2 hệ thống kia VẪN HOẠT ĐỘNG!
→ Có thể index lại 1 hệ thống mà KHÔNG ảnh hưởng hệ thống khác
```

**2. LÚC QUERY (Song song, chọn lọc):**
```
┌─────────────────────────────────────────────────────────┐
│ CASE 1: Technical Document Query                       │
│ "Áp suất vận hành của K06101?"                          │
└─────────────────────────────────────────────────────────┘

[Parallel Search]
├─ Thread 1: Weaviate semantic search
│  → "áp suất vận hành" → 50 chunks
│
└─ Thread 2: OpenSearch BM25
   → "K06101" → 50 chunks

→ Không gọi Spatial (không cần)
→ 2 threads chạy ĐỒNG THỜI
→ RRF Fusion kết hợp 2 kết quả
→ Thời gian = max(thread1, thread2) ≈ 100ms

┌─────────────────────────────────────────────────────────┐
│ CASE 2: P&ID Query                                      │
│ "Tag 04 PSAL 2207 ở đâu?"                               │
└─────────────────────────────────────────────────────────┘

[Parallel Search - 2 branches]
Branch A (Level 2 Spatial):
├─ OpenSearch Spatial search
│  → Tìm "04" + "PSAL" + "2207" theo vị trí
│  → Component-based clustering
│  → 10 matches
│
Branch B (Chunks):
├─ Thread 1: Weaviate semantic
│  → "04 PSAL 2207" → 30 chunks
│
└─ Thread 2: OpenSearch BM25
   → "04 PSAL 2207" → 30 chunks

→ GỌI CẢ 3 HỆ THỐNG!
→ Branch A và Branch B chạy SONG SONG
→ Trong Branch B, 2 threads chạy SONG SONG
→ Adaptive RRF Fusion kết hợp 3 nguồn kết quả
→ Thời gian = max(branchA, branchB) ≈ 150ms
```

#### **Tóm tắt:**

| Khía cạnh | Cách hoạt động |
|-----------|----------------|
| **Indexing** | ✅ ĐỘC LẬP - Mỗi hệ thống lưu data riêng |
| **Storage** | ✅ ĐỘC LẬP - 3 databases riêng biệt |
| **Query** | ✅ SONG SONG - Gọi nhiều hệ thống cùng lúc |
| **Kết hợp kết quả** | ✅ RRF FUSION - Merge sau khi search |
| **Phụ thuộc** | ❌ KHÔNG - 1 hệ thống lỗi, còn 2 hoạt động |

**Lợi ích của kiến trúc này:**
- ⚡ **Nhanh**: Query song song → thời gian = max(các thread)
- 🛡️ **An toàn**: 1 hệ thống die → 2 hệ thống còn lại vẫn hoạt động (degraded mode)
- 🔧 **Linh hoạt**: Có thể rebuild/reindex 1 hệ thống mà không ảnh hưởng hệ thống khác
- 🎯 **Tối ưu**: Mỗi hệ thống làm việc nó giỏi nhất (semantic/keyword/spatial)

---

### 4.1.2 KỸ THUẬT KẾT HỢP: RRF FUSION (Reciprocal Rank Fusion)

#### **Vấn đề cần giải quyết:**

❓ **"Làm sao gọi 2-3 hệ thống cùng lúc mà vẫn ra được 1 câu trả lời duy nhất?"**

Mỗi hệ thống trả về kết quả với **thang điểm KHÁC NHAU**:
- Weaviate: cosine similarity (0.0 → 1.0)
- OpenSearch BM25: BM25 score (0 → 50+)
- Spatial: proximity score (0 → 100)

→ **KHÔNG THỂ** so sánh trực tiếp!

```
VÍ DỤ:
Weaviate trả về:  chunk_A (score = 0.92)
OpenSearch trả về: chunk_B (score = 8.5)

❌ So sánh 0.92 vs 8.5? → VÔ NGHĨA!
✅ Cần phương pháp CHUẨN HÓA!
```

#### **Giải pháp: RRF (Reciprocal Rank Fusion)**

RRF không so sánh **điểm số** mà so sánh **THỨ HẠNG** (rank)!

**Công thức RRF:**
```
RRF_score(chunk) = Σ [ weight_i / (rank_i + k) ]

Trong đó:
- rank_i = thứ hạng của chunk trong hệ thống i (1, 2, 3...)
- k = hằng số (thường = 60)
- weight_i = trọng số của hệ thống i
```

#### **Ví dụ chi tiết: Technical Doc Query**

```
═══════════════════════════════════════════════════════════════
QUERY: "Áp suất vận hành của K06101?"
═══════════════════════════════════════════════════════════════

[BƯỚC 1] GỌI 2 HỆ THỐNG SONG SONG

┌─────────────────────────────────────┐
│ WEAVIATE RESULTS                    │
│ (semantic search)                   │
├─────────────────────────────────────┤
│ 1. chunk_A (score = 0.92)           │ ← Rank 1
│ 2. chunk_C (score = 0.88)           │ ← Rank 2
│ 3. chunk_D (score = 0.85)           │ ← Rank 3
│ 4. chunk_B (score = 0.82)           │ ← Rank 4
│ 5. chunk_E (score = 0.78)           │ ← Rank 5
│ ...                                 │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ OPENSEARCH BM25 RESULTS             │
│ (keyword search)                    │
├─────────────────────────────────────┤
│ 1. chunk_B (score = 12.5)           │ ← Rank 1
│ 2. chunk_F (score = 9.8)            │ ← Rank 2
│ 3. chunk_A (score = 8.3)            │ ← Rank 3
│ 4. chunk_G (score = 7.1)            │ ← Rank 4
│ 5. chunk_C (score = 6.5)            │ ← Rank 5
│ ...                                 │
└─────────────────────────────────────┘

[BƯỚC 2] TÍNH RRF SCORE

Công thức: RRF_score = weight_wv/(rank_wv + 60) + weight_os/(rank_os + 60)

Trọng số mặc định:
- weight_wv (Weaviate) = 0.7
- weight_os (OpenSearch) = 0.7

Chunk A:
├─ Rank in Weaviate = 1
├─ Rank in OpenSearch = 3
├─ RRF = 0.7/(1+60) + 0.7/(3+60)
└─ RRF = 0.7/61 + 0.7/63 = 0.0115 + 0.0111 = 0.0226

Chunk B:
├─ Rank in Weaviate = 4
├─ Rank in OpenSearch = 1
├─ RRF = 0.7/(4+60) + 0.7/(1+60)
└─ RRF = 0.7/64 + 0.7/61 = 0.0109 + 0.0115 = 0.0224

Chunk C:
├─ Rank in Weaviate = 2
├─ Rank in OpenSearch = 5
├─ RRF = 0.7/(2+60) + 0.7/(5+60)
└─ RRF = 0.7/62 + 0.7/65 = 0.0113 + 0.0108 = 0.0221

Chunk D:
├─ Rank in Weaviate = 3
├─ KHÔNG có trong OpenSearch → rank = 999 (penalty)
├─ RRF = 0.7/(3+60) + 0.7/(999+60)
└─ RRF = 0.7/63 + 0.7/1059 = 0.0111 + 0.0007 = 0.0118

Chunk F:
├─ KHÔNG có trong Weaviate → rank = 999
├─ Rank in OpenSearch = 2
├─ RRF = 0.7/(999+60) + 0.7/(2+60)
└─ RRF = 0.7/1059 + 0.7/62 = 0.0007 + 0.0113 = 0.0120

[BƯỚC 3] SẮP XẾP LẠI THEO RRF SCORE

┌─────────────────────────────────────────────────────────┐
│ KẾT QUẢ SAU RRF FUSION (Top 10)                        │
├─────────────────────────────────────────────────────────┤
│ 1. chunk_A (RRF = 0.0226) ← XH cao ở CẢ 2 hệ thống!    │
│ 2. chunk_B (RRF = 0.0224) ← XH cao ở CẢ 2 hệ thống     │
│ 3. chunk_C (RRF = 0.0221) ← XH cao ở CẢ 2 hệ thống     │
│ 4. chunk_F (RRF = 0.0120) ← Chỉ tốt ở OpenSearch       │
│ 5. chunk_D (RRF = 0.0118) ← Chỉ tốt ở Weaviate         │
│ ...                                                     │
└─────────────────────────────────────────────────────────┘

[BƯỚC 4] GỬI TOP 10 CHUNKS CHO LLM

→ LLM đọc 10 chunks này và sinh câu trả lời
→ Trích dẫn từ các chunks liên quan
```

#### **Tại sao RRF hiệu quả?**

```
✅ ƯU ĐIỂM:

1. KHÔNG cần chuẩn hóa điểm số
   → Chỉ cần thứ hạng (rank)
   → Đơn giản, ổn định

2. Ưu tiên chunks xuất hiện ở NHIỀU hệ thống
   → chunk_A (rank 1+3) > chunk_D (rank 3+999)
   → "Consensus" = tin cậy hơn

3. Công bằng với tất cả hệ thống
   → Không bị bias bởi thang điểm
   → Mỗi hệ thống đóng góp đều

4. Xử lý lỗi tốt
   → 1 hệ thống die → vẫn có kết quả từ hệ thống còn lại
   → Degraded mode tự nhiên
```

#### **Ví dụ P&ID Query (3 hệ thống)**

```
═══════════════════════════════════════════════════════════════
QUERY: "Tag 04 PSAL 2207 ở đâu?"
═══════════════════════════════════════════════════════════════

[BƯỚC 1] GỌI 3 HỆ THỐNG SONG SONG

Branch A - Spatial:
  1. component_cluster_X (10 matches) → rank 1-10

Branch B - Weaviate:
  1. chunk_M (rank 1)
  2. chunk_N (rank 2)
  ...

Branch B - OpenSearch:
  1. chunk_P (rank 1)
  2. chunk_M (rank 2)
  ...

[BƯỚC 2] ADAPTIVE RRF (trọng số khác nhau)

Với P&ID query, trọng số ADAPTIVE:
- weight_spatial = 1.0  ← CAO NHẤT (quan trọng nhất)
- weight_weaviate = 0.2 ← THẤP (ít quan trọng)
- weight_opensearch = 0.6 ← TRUNG BÌNH

Tỷ lệ: Spatial:OpenSearch:Weaviate = 1.0:0.6:0.2 = 5:3:1
→ Spatial chiếm 62.5% ảnh hưởng (nhấn mạnh vị trí không gian)

Lý do: P&ID cần độ chính xác TUYỆT ĐỐI về vị trí!

Chunk M (từ tag cluster):
├─ Rank spatial = 1
├─ Rank weaviate = 1
├─ Rank opensearch = 2
├─ RRF = 1.0/61 + 0.2/61 + 0.6/62
└─ RRF = 0.0164 + 0.0033 + 0.0097 = 0.0294 ← SCORE CAO NHẤT!

[BƯỚC 3] TOP RESULTS

1. chunk_M (từ spatial cluster) - RRF = 0.0326
2. chunk_N (từ spatial + text) - RRF = 0.0287
3. chunk_P (chỉ từ text) - RRF = 0.0145
...

→ Spatial results được ƯU TIÊN
→ Nhưng vẫn có context từ text search
```

#### **Xử lý vấn đề khi gọi đồng thời**

```
❓ "Có gây vấn đề gì không?"

✅ KHÔNG gây vấn đề nếu thiết kế đúng:

1. TIMEOUT HANDLING
   ├─ Mỗi thread có timeout riêng (5s)
   ├─ Nếu 1 thread chậm → vẫn chờ
   └─ Nếu timeout → dùng kết quả từ threads còn lại

2. ERROR HANDLING
   ├─ Try-catch cho từng thread
   ├─ Thread lỗi → return empty list
   └─ RRF vẫn chạy với results còn lại

3. RESOURCE CONTENTION (tranh tài nguyên)
   ├─ Mỗi hệ thống chạy trên server/port riêng
   ├─ Weaviate: localhost:8080
   ├─ OpenSearch: localhost:9200
   └─ KHÔNG tranh tài nguyên với nhau

4. NETWORK LATENCY
   ├─ Tất cả localhost → latency thấp (<1ms)
   ├─ Nếu remote → có thể caching
   └─ Connection pooling để tái sử dụng connections
```

#### **Code flow đơn giản hóa**

```python
# Pseudocode minh họa

def hybrid_search(query):
    # BƯỚC 1: Gọi song song
    results = parallel_call([
        lambda: weaviate.search(query, limit=50),    # Thread 1
        lambda: opensearch.search(query, limit=50),  # Thread 2
        lambda: spatial.search(query, limit=50)      # Thread 3 (nếu cần)
    ])

    # BƯỚC 2: RRF Fusion
    merged = rrf_fusion(
        results[0],  # Weaviate results
        results[1],  # OpenSearch results
        results[2],  # Spatial results (có thể empty)
        weights=[0.7, 0.7, 1.0]
    )

    # BƯỚC 3: Lấy top K
    top_chunks = merged[:10]

    # BƯỚC 4: Gửi cho LLM
    answer = llm.generate(query, top_chunks)

    return answer
```

#### **Tóm tắt:**

| Câu hỏi | Trả lời |
|---------|----------|
| **Gọi đồng thời có lỗi không?** | ❌ KHÔNG - Mỗi hệ thống độc lập |
| **Làm sao kết hợp điểm số khác nhau?** | ✅ RRF - Dùng RANK thay vì SCORE |
| **Nếu 1 hệ thống lỗi?** | ✅ Degraded mode - Dùng hệ thống còn lại |
| **Có chậm không?** | ❌ KHÔNG - Thời gian = max(threads) |
| **Ai quyết định kết quả cuối?** | ✅ LLM - Đọc top 10 chunks sau RRF |

### 4.2 Index 1: Weaviate (Vector Search)

```
BIẾN TEXT THÀNH VECTOR VÀ INDEX
│
├─ Input: chunks.jsonl (6758 chunks)
│
├─ BƯỚC 1: Tạo embedding (vector 768 chiều)
│  │
│  ├─ Gửi text đến Gemini Embedding API
│  │  → Text: "29 SG 2201A steam generator..."
│  │  → Gemini trả về: [0.123, -0.456, 0.789, ..., 0.234]
│  │                    (768 số thực)
│  │
│  ├─ Batch processing: 100 chunks/lần
│  │  → Tránh quá tải API
│  │  → Rate limit: 1000 requests/phút
│  │
│  └─ Tiến độ: 6758 chunks / 100 = 68 batches
│     → Thời gian: ~35 phút
│
├─ BƯỚC 2: Index vào Weaviate
│  │
│  ├─ Collection: "Chunk"
│  │
│  ├─ Với mỗi chunk:
│  │  {
│  │    "uuid": "generated_from_chunk_id",
│  │    "properties": {
│  │      "text": "29 SG 2201A steam...",
│  │      "doc_id": "Ammonia_P&ID",
│  │      "page": 113,
│  │      "tags": ["29 SG 2201A"]
│  │    },
│  │    "vector": [0.123, -0.456, ..., 0.234]
│  │  }
│  │
│  └─ Weaviate lưu vector + build index HNSW
│     → Cho phép tìm kiếm nhanh (< 100ms)
│
└─ Kết quả: 6758 vectors được index
```

**Cách hoạt động tìm kiếm:**
```
User hỏi: "Áp suất vận hành là bao nhiêu?"
│
├─ Chuyển câu hỏi thành vector
│  → [0.234, -0.123, 0.567, ..., 0.890]
│
├─ Weaviate tính cosine similarity với 6758 vectors
│  → Tìm 50 vectors gần nhất
│  → Ví dụ: chunk #1234 có similarity = 0.92
│
└─ Trả về chunks có similarity cao nhất
```

### 4.3 Index 2: OpenSearch rag_chunks (BM25)

```
INDEX KEYWORD SEARCH
│
├─ Input: chunks.jsonl (6758 chunks)
│
├─ KHÔNG CẦN embedding!
│  → Chỉ index text thuần
│
├─ Index document OpenSearch:
│  {
│    "_id": "Ammonia_P&ID_chunk_0",
│    "text": "29 SG 2201A steam generator...",
│    "doc_id": "Ammonia_P&ID",
│    "page": 113,
│    "tags": ["29 SG 2201A", "04 PSAL 2207"],
│    "doc_type": "CAD-like"
│  }
│
├─ OpenSearch tạo inverted index:
│  │
│  ├─ Token "steam" → [chunk_0, chunk_45, chunk_203]
│  ├─ Token "generator" → [chunk_0, chunk_67, chunk_189]
│  ├─ Token "K06101" → [chunk_123, chunk_456]
│  └─ ...
│
└─ Thời gian: ~5 phút cho 6758 documents
```

**Cách hoạt động tìm kiếm:**
```
User hỏi: "K06101"
│
├─ OpenSearch lookup inverted index
│  → Token "K06101" → [chunk_123, chunk_456]
│
├─ Tính BM25 score cho mỗi chunk
│  → chunk_123: score = 8.5
│  → chunk_456: score = 7.2
│
└─ Trả về chunks theo thứ tự score giảm dần
```

### 4.4 Index 3: OpenSearch spatial_components (Spatial)

```
INDEX SPATIAL COMPONENTS (CHỈ P&ID)
│
├─ Input: Spatial components từ ingestion
│  → 12,450 components từ 5 P&ID files
│
├─ Index mỗi component:
│  {
│    "_id": "Ammonia_P&ID#113#29",
│    "doc_id": "Ammonia_P&ID",
│    "page": 113,
│    "component": "29",
│    "component_type": "unit",
│    "bbox": {"x0": 1688, "y0": 525, "x1": 1698, "y1": 537},
│    "center_x": 1693,
│    "center_y": 531
│  }
│
├─ OpenSearch lưu với geo-point hoặc custom spatial index
│  → Cho phép query theo proximity (khoảng cách)
│
└─ Thời gian: ~2 phút cho 12,450 components
```

**Cách hoạt động tìm kiếm:**
```
User hỏi: "04 PSAL 2207"
│
├─ Parse query:
│  → UNIT: "04"
│  → PREFIX: "PSAL"
│  → SUFFIX: "2207"
│
├─ Tìm 3 components riêng lẻ:
│  → "04" (unit) ở (x:100, y:200)
│  → "PSAL" (prefix) ở (x:98, y:220)
│  → "2207" (suffix) ở (x:102, y:240)
│
├─ Kiểm tra proximity:
│  → Distance(04, PSAL) = 20px ✓
│  → Distance(PSAL, 2207) = 20px ✓
│  → Cùng cột (X gần nhau) ✓
│
└─ Kết luận: "04 PSAL 2207" tồn tại ở page 113, bbox (98,200,104,242)
```

### 4.5 Tổng kết indexing

```
TỔNG HỢP 3 INDEXES:

┌─────────────────────────────────────────────────────────┐
│ Weaviate "Chunk"                                        │
│ ├─ 6,758 vectors (768D)                               │
│ ├─ Size: ~500 MB                                       │
│ └─ Query time: 50-100ms                                │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ OpenSearch "rag_chunks"                                 │
│ ├─ 6,758 documents                                     │
│ ├─ Size: ~200 MB                                       │
│ └─ Query time: 20-50ms                                 │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ OpenSearch "pvcfc_pid_spatial_components"               │
│ ├─ 12,450 components (chỉ P&ID)                        │
│ ├─ Size: ~50 MB                                        │
│ └─ Query time: 10-30ms                                 │
└─────────────────────────────────────────────────────────┘

TỔNG THỜI GIAN INDEXING: ~40 phút
```

---

## 5. SO SÁNH HAI LOẠI TÀI LIỆU

### 5.1 Bảng so sánh chi tiết

| Đặc điểm | P&ID (CAD-like) | Technical Document |
|----------|-----------------|-------------------|
| **Phân loại** | CAD-like Gate score ≥ 0.55 | CAD-like Gate score < 0.55 |
| **OCR Threshold** | < 1700 chars/page | < 40 chars/page |
| **OCR Enhancement** | ✅ Real-ESRGAN 2x | ❌ Không |
| **Page Layout** | ✅ Trích xuất (bbox, font) | ❌ Không |
| **Tag Extraction** | ✅ Geometric Assembly | ❌ Không |
| **Spatial Components** | ✅ Level 2 (12,450 components) | ❌ Không |
| **Crops** | ✅ 347 PNG images | ❌ Không |
| **Chunking** | ✅ Hierarchical + metadata | ✅ Hierarchical only |
| **Indexes** | 3 (BM25 + Vector + Spatial) | 2 (BM25 + Vector) |
| **Thời gian xử lý** | 5 phút/file (25 trang) | 1 phút/file (150 trang) |
| **Kích thước output** | ~50 MB/file | ~5 MB/file |

### 5.2 Ví dụ thực tế

#### **Case 1: P&ID File**

```
FILE: "01. P&ID Ammonia Unit Rev12 (04000).pdf"
├─ Số trang: 25
├─ Kích thước: 15 MB
│
INGESTION:
├─ Gate score: 0.78 → CAD-LIKE
├─ OCR: 22/25 trang (3 trang đủ text)
├─ Real-ESRGAN: Áp dụng cho 22 trang
├─ Tags extracted: 347 tags
├─ Spatial components: 1,245 components
├─ Chunks: 67 chunks
├─ Crops: 347 PNG files
└─ Thời gian: 5 phút 12 giây

INDEXING:
├─ Weaviate: 67 vectors
├─ OpenSearch rag_chunks: 67 docs
├─ OpenSearch spatial: 1,245 components
└─ Thời gian: 3 phút

TỔNG: 8 phút 12 giây
```

#### **Case 2: Technical Manual**

```
FILE: "Compressor Manual ABC-123.pdf"
├─ Số trang: 150
├─ Kích thước: 8 MB
│
INGESTION:
├─ Gate score: 0.12 → NON-CAD-LIKE
├─ OCR: 2/150 trang (148 trang đủ text)
├─ Real-ESRGAN: Không áp dụng
├─ Tags extracted: Không
├─ Spatial components: Không
├─ Chunks: 456 chunks
├─ Crops: Không
└─ Thời gian: 3 phút 5 giây

INDEXING:
├─ Weaviate: 456 vectors
├─ OpenSearch rag_chunks: 456 docs
├─ OpenSearch spatial: Không
└─ Thời gian: 12 phút

TỔNG: 15 phút 5 giây
```

### 5.3 Sơ đồ luồng so sánh

```
┌──────────────────────────────────────────────────────────┐
│                    PDF INPUT                             │
└─────────────────────┬────────────────────────────────────┘
                      │
                      ↓
           ┌──────────────────────┐
           │   CAD-like Gate      │
           │   Score = ?          │
           └──────┬───────┬───────┘
                  │       │
        score ≥0.55      score <0.55
                  │       │
    ┌─────────────▼─┐   ┌▼─────────────┐
    │   P&ID        │   │  MANUAL      │
    └─────────────┬─┘   └┬─────────────┘
                  │       │
    ┌─────────────▼────────▼──────────────┐
    │      TEXT EXTRACTION                │
    │  P&ID: Threshold 1700, Real-ESRGAN  │
    │  Manual: Threshold 40, No ESRGAN    │
    └─────────────┬──────────────────────┘
                  │
    ┌─────────────┴──────────────────────┐
    │                                     │
    ↓                                     ↓
┌──────────────┐                    ┌──────────────┐
│ P&ID         │                    │ MANUAL       │
│ ├─ Layout    │                    │ ├─ Text      │
│ ├─ Tags      │                    │ └─ Chunks    │
│ ├─ Spatial   │                    │              │
│ ├─ Crops     │                    │              │
│ └─ Chunks    │                    │              │
└──────┬───────┘                    └──────┬───────┘
       │                                   │
       └───────────────┬───────────────────┘
                       │
                       ↓
┌──────────────────────────────────────────────────────────┐
│                 TRIPLE INDEXING                          │
│  ├─ Weaviate (vectors)                                  │
│  ├─ OpenSearch rag_chunks (BM25)                        │
│  └─ OpenSearch spatial (P&ID only)                      │
└──────────────────────────────────────────────────────────┘
```

---

## 6. CẤU HÌNH QUAN TRỌNG

### 6.1 Biến môi trường (.env)

```
# ============================================
# GOOGLE CLOUD VISION (OCR)
# ============================================
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json

# ============================================
# OCR THRESHOLDS (ký tự/trang)
# ============================================
OCR_THRESHOLD_CAD=1700        # P&ID: OCR nếu < 1700 chars
OCR_THRESHOLD_NON_CAD=40      # Manual: OCR nếu < 40 chars

# ============================================
# REAL-ESRGAN
# ============================================
ENABLE_REAL_ESRGAN=true       # Bật/tắt upscaling
REAL_ESRGAN_SCALE=2           # Upscale 2x (1 → 2, 2 → 4)

# ============================================
# CAD-LIKE GATE
# ============================================
CADLIKE_GATE_THRESHOLD=0.55   # Ngưỡng phân loại

# ============================================
# CHUNKING
# ============================================
CHUNK_MAX_SIZE=1000           # ký tự/chunk
CHUNK_OVERLAP=200             # ký tự overlap
CHUNK_STRATEGY=hierarchical   # hierarchical | sentence-window | small-to-big

# ============================================
# INDEXING
# ============================================
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
OPENSEARCH_INDEX_CHUNKS=rag_chunks
OPENSEARCH_INDEX_SPATIAL=pvcfc_pid_spatial_components

WEAVIATE_HOST=localhost
WEAVIATE_PORT=8080
WEAVIATE_GRPC_PORT=50051
WEAVIATE_COLLECTION=Chunk

# ============================================
# EMBEDDING
# ============================================
EMBEDDING_MODEL=embedding-001  # Gemini
EMBEDDING_DIMENSION=768
EMBEDDING_BATCH_SIZE=100

# ============================================
# BATCH SIZES
# ============================================
INDEX_BATCH_SIZE_OPENSEARCH=1000
INDEX_BATCH_SIZE_WEAVIATE=256
EMBEDDING_BATCH_SIZE=100
```

### 6.2 Thông số quan trọng

#### **OCR Thresholds**
```
Tại sao 1700 và 40?

P&ID (1700):
- Bản vẽ thường có nhiều annotation nhỏ
- Text nằm rải rác, khó extract bằng PDF parser
- Real-ESRGAN giúp cải thiện text nhỏ
→ Ngưỡng cao = OCR nhiều hơn = chính xác hơn

Technical Document (40):
- Văn bản liên tục, PDF parser hoạt động tốt
- Chỉ OCR khi thực sự là scan (< 40 chars/page)
- Không cần Real-ESRGAN (tốn thời gian)
→ Ngưỡng thấp = OCR ít hơn = nhanh hơn
```

#### **Chunk Size**
```
Tại sao 1000 chars, 200 overlap?

1000 chars ≈ 200-250 tokens:
- Đủ dài để giữ ngữ cảnh
- Đủ ngắn để tìm kiếm chính xác
- Không vượt quá giới hạn embedding model

200 chars overlap:
- Tránh mất ngữ cảnh ở biên chunk
- Ví dụ: "...pressure valve..." | "...valve settings..."
  → Overlap giữ "valve" ở cả 2 chunks
```

#### **Batch Sizes**
```
OpenSearch: 1000 docs/batch
- Bulk API hiệu quả với batch lớn
- Timeout: 60 giây

Weaviate: 256 objects/batch
- Cần tính embedding + index vector
- Batch nhỏ hơn để tránh timeout

Embedding: 100 texts/batch
- Giới hạn API: 100 texts/request
- Rate limit: 1000 requests/phút
```

---

## 7. VÍ DỤ THỰC TẾ

### 7.1 Ví dụ 1: Xử lý file P&ID từ đầu đến cuối

```
════════════════════════════════════════════════════════
FILE: "01. P&ID Ammonia Unit Rev12 (04000).pdf"
════════════════════════════════════════════════════════

[00:00:00] Bắt đầu xử lý...

[00:00:01] BƯỚC 1: Phát hiện file
├─ Tìm thấy file: D:\Data_Raw\Ammonia\01. P&ID...
├─ Kích thước: 15.2 MB
├─ Tính file hash: SHA256 = abc123def456...
└─ Kiểm tra trùng: KHÔNG trùng ✓

[00:00:02] BƯỚC 2: Phân loại (CAD-like Gate)
├─ Lấy mẫu 5 trang: 1, 2, 3, 13, 25
├─ Phân tích trang 1:
│  ├─ Producer: "AutoCAD" → +0.20
│  ├─ Geometry density: 0.85 → +0.15
│  ├─ Short CAPS rate: 0.25 → +0.15
│  ├─ 3-piece regex hits: 12 → +0.20
│  ├─ Technical suffixes: 8 → +0.10
│  ├─ Page size: A1 → +0.10
│  ├─ Rotated text: Yes → +0.05
│  └─ Leader patterns: 5 → +0.05
├─ Score trang 1: 0.92
├─ Score trung bình 5 trang: 0.78
└─ QUYẾT ĐỊNH: CAD-LIKE ✓

[00:00:15] BƯỚC 3: Xử lý trang 113
├─ Extract vector text: 1376 chars
├─ So sánh threshold: 1376 < 1700 → CẦN OCR
│
├─ [00:00:16] Render page to PNG (DPI=192)
│  → Size: 3508 x 2480 pixels
│
├─ [00:00:18] Apply Real-ESRGAN 2x
│  → Upscale: 3508 → 7016 pixels
│  → Quality: Excellent (text rõ nét)
│  → Time: 21.3 seconds
│
├─ [00:00:39] Google Cloud Vision OCR
│  → Request: DOCUMENT_TEXT_DETECTION
│  → Language: vie+eng
│  → Response: 247 text annotations
│  → Time: 2.8 seconds
│
├─ [00:00:42] Geometric Assembly
│  ├─ Tìm PREFIX: "PSAL", "SG", "PT", "FIC"...
│  ├─ Tìm UNIT: "04", "29", "8"...
│  ├─ Tìm SUFFIX: "2207", "2201A"...
│  ├─ Tổ hợp triplets:
│  │  ├─ "04" + "PSAL" + "2207" → "04 PSAL 2207" ✓
│  │  ├─ "29" + "SG" + "2201A" → "29 SG 2201A" ✓
│  │  └─ ...
│  └─ Tổng: 14 tags found
│
├─ [00:00:43] Extract Spatial Components
│  ├─ Classify components:
│  │  ├─ "04" → unit (x:100, y:200)
│  │  ├─ "PSAL" → prefix (x:98, y:220)
│  │  ├─ "2207" → suffix (x:102, y:240)
│  │  └─ ...
│  └─ Tổng: 247 components
│
└─ [00:00:44] Page 113 hoàn thành

[00:04:32] Xử lý 25 trang hoàn thành

[00:04:33] BƯỚC 4: Chunking
├─ Merge all page texts
├─ Apply hierarchical chunking
├─ Size: 1000 chars, overlap: 200
└─ Result: 67 chunks

[00:04:35] BƯỚC 5: Finalization
├─ Write chunks.jsonl: 67 chunks
├─ Write tags.jsonl: 347 tags
├─ Write spatial components: 1,245 components
├─ Write doc_id_map.json
└─ Statistics:
   ├─ Total pages: 25
   ├─ OCR pages: 22
   ├─ Tags: 347
   ├─ Spatial components: 1,245
   ├─ Chunks: 67
   └─ Time: 5m 12s

[00:04:35] INGESTION HOÀN TẤT ✓
```

### 7.2 Ví dụ 2: Indexing chunks

```
════════════════════════════════════════════════════════
INDEXING: chunks.jsonl (6,758 chunks)
════════════════════════════════════════════════════════

[00:00:00] Khởi động indexing...

[00:00:01] Kết nối services
├─ Weaviate: localhost:8080 → Connected ✓
├─ OpenSearch: localhost:9200 → Connected ✓
└─ Gemini Embedding API → Ready ✓

[00:00:03] Đọc chunks.jsonl
├─ Đọc file: artifacts/ingestion_production/chunks/chunks.jsonl
├─ Total lines: 6,758
└─ Prepare batches: 68 batches (100 chunks/batch)

[00:00:05] Batch 1/68 (chunks 0-99)
│
├─ [00:00:05] Generate embeddings
│  ├─ Send 100 texts to Gemini API
│  ├─ Response: 100 vectors (768D)
│  └─ Time: 2.3s
│
├─ [00:00:08] Index to Weaviate
│  ├─ Prepare 100 objects
│  ├─ Bulk insert via gRPC
│  └─ Success: 100/100 ✓
│
├─ [00:00:09] Index to OpenSearch
│  ├─ Prepare 100 docs
│  ├─ Bulk API: POST /_bulk
│  └─ Success: 100/100 ✓
│
└─ Batch 1 completed: 2.8s

[00:00:11] Batch 2/68 (chunks 100-199)
...

[00:32:45] Batch 68/68 (chunks 6700-6757)
└─ Remaining: 58 chunks
   → Success: 58/58 ✓

[00:32:48] Indexing spatial components
├─ Total: 12,450 components
├─ Batch size: 1000
├─ Index to: pvcfc_pid_spatial_components
└─ Time: 1m 23s

[00:34:11] INDEXING HOÀN TẤT ✓

Thống kê:
├─ Weaviate "Chunk": 6,758 objects
├─ OpenSearch "rag_chunks": 6,758 docs
├─ OpenSearch "pvcfc_pid_spatial_components": 12,450 docs
└─ Total time: 34m 11s
```

### 7.3 Ví dụ 3: Query P&ID tag

```
════════════════════════════════════════════════════════
QUERY: "Tìm tag 04 PSAL 2207 trên bản vẽ"
════════════════════════════════════════════════════════

[00:00:00] Parse query
├─ Detect tag pattern: "04 PSAL 2207"
├─ Extract components:
│  ├─ UNIT: "04"
│  ├─ PREFIX: "PSAL"
│  └─ SUFFIX: "2207"
└─ Query type: P&ID spatial search

[00:00:01] Search spatial components index
│
├─ Query 1: Find "04" (type=unit)
│  → Found 15 matches across 5 pages
│
├─ Query 2: Find "PSAL" (type=prefix)
│  → Found 8 matches across 3 pages
│
└─ Query 3: Find "2207" (type=suffix)
   → Found 2 matches on page 113

[00:00:02] Component-based clustering
│
├─ Group components by proximity:
│  │
│  ├─ Cluster 1 (page 113, area A):
│  │  ├─ "04" at (100, 200)
│  │  ├─ "PSAL" at (98, 220)  ← Distance 20px ✓
│  │  └─ "2207" at (102, 240) ← Distance 20px ✓
│  │  → MATCH! Confidence: 0.96
│  │
│  └─ Cluster 2 (page 117, area B):
│     ├─ "04" at (500, 300)
│     ├─ "PSV" at (498, 320)  ← Wrong PREFIX ✗
│     └─ Rejected
│
└─ Result: 1 match found

[00:00:03] Retrieve full context
├─ Load page 113 layout
├─ Get bbox: (98, 200, 104, 242)
├─ Load chunk containing tag
└─ Get crop image: crops/Ammonia_p113_04_PSAL_2207.png

[00:00:04] BUILD RESPONSE
├─ Tag: "04 PSAL 2207"
├─ Location: Page 113
├─ Bbox: (98, 200, 104, 242)
├─ Confidence: 0.96
├─ Crop: Available ✓
└─ Context: "...pressure alarm low 04 PSAL 2207..."

[00:00:04] QUERY HOÀN TẤT ✓
Total time: 43ms
```

---

## 8. TÓM TẮT VÀ KẾT LUẬN

### 8.1 Quy trình tổng thể (Simplified)

```
INGESTION (4-5 giờ cho 25 files):
1. Quét thư mục → Tìm PDF
2. Loại trùng → Skip duplicates
3. Phân loại → P&ID hay Manual?
4. Trích xuất text → Vector + OCR
5. [P&ID only] Layout + Tags + Spatial
6. Chunking → Chia nhỏ text
7. Lưu kết quả → chunks.jsonl, tags.jsonl

INDEXING (30-40 phút):
1. Đọc chunks.jsonl
2. Generate embeddings → Gemini API
3. Index Weaviate → Vector search
4. Index OpenSearch rag_chunks → BM25
5. Index OpenSearch spatial → P&ID only

READY TO QUERY!
```

### 8.2 Điểm mạnh của hệ thống

✅ **Tự động phân loại**: Không cần label thủ công
✅ **Xử lý đa dạng**: PDF vector, scan, P&ID, manual
✅ **OCR thông minh**: Real-ESRGAN + Google Cloud Vision
✅ **Spatial search**: Tìm tag P&ID chính xác tuyệt đối
✅ **Triple indexing**: Phục vụ nhiều kiểu truy vấn
✅ **Scalable**: Xử lý hàng nghìn tài liệu

### 8.3 Các con số quan trọng

```
Ingestion:
├─ P&ID: 5 phút/file (25 trang)
├─ Manual: 3 phút/file (150 trang)
└─ OCR với Real-ESRGAN: ~21 giây/trang

Indexing:
├─ Embedding: ~3 giây/100 texts
├─ Weaviate: ~1 giây/100 vectors
└─ OpenSearch: ~0.5 giây/100 docs

Query:
├─ Vector search: 50-100ms
├─ BM25 search: 20-50ms
└─ Spatial search: 10-30ms

Dung lượng:
├─ P&ID file: ~50 MB artifacts
├─ Manual file: ~5 MB artifacts
└─ Index total: ~750 MB cho 25 files
```

### 8.4 Lưu ý khi vận hành

⚠️ **OCR tốn thời gian**: Real-ESRGAN chậm (~21s/page) nhưng chính xác
⚠️ **Cần GPU**: Real-ESRGAN chạy nhanh hơn 10x với GPU
⚠️ **Rate limit**: Gemini API giới hạn 1000 requests/phút
⚠️ **Disk space**: Mỗi P&ID file → ~50 MB artifacts
⚠️ **Memory**: Cần ~12 GB RAM khi xử lý batch lớn

---

## PHỤ LỤC

### A. Đường dẫn quan trọng

```
Input:
D:\Data_Raw\                        # Thư mục chứa PDF gốc

Output:
artifacts/ingestion_production/
├── chunks/
│   └── chunks.jsonl                # TẤT CẢ chunks
├── entities/
│   └── tags.jsonl                  # Tags P&ID
├── page_layout/
│   └── page_*.json                 # Layout data
├── crops/
│   └── *.png                       # Tag images
├── manifests/
│   ├── corpus.jsonl
│   └── doc_id_map.json
└── logs/
    └── tag_extraction_telemetry.jsonl
```

### B. Commands quan trọng

```powershell
# Ingestion
python tools/ingest.py `
  --source-dir "D:\Data_Raw" `
  --output-dir "artifacts\ingestion_production" `
  --enable-pid-tags `
  --workers 2

# Tạo OpenSearch indexes
python scripts/opensearch/create_rag_chunks_index.py --delete-if-exists
python scripts/opensearch/create_spatial_components_index.py --delete-if-exists

# Indexing
python scripts/utilities/index_production_chunks.py

# Start API
.\launchers\start_api.ps1
```

### C. Thuật ngữ

| Tiếng Anh | Tiếng Việt | Giải thích |
|-----------|-----------|------------|
| Ingestion | Nhập liệu | Xử lý PDF thành chunks |
| Indexing | Lập chỉ mục | Đưa chunks vào database |
| Chunking | Chia nhỏ | Chia text thành đoạn nhỏ |
| Embedding | Vector hóa | Chuyển text thành số |
| OCR | Nhận dạng ký tự | Đọc text từ ảnh |
| Spatial | Không gian | Liên quan đến vị trí |
| Pipeline | Luồng xử lý | Chuỗi bước xử lý |
| Gate | Cổng phân loại | Điểm quyết định |

---

**HẾT TÀI LIỆU**

*Nếu có câu hỏi hoặc cần làm rõ phần nào, vui lòng liên hệ team kỹ thuật.*
