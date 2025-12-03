# PVCFC RAG SYSTEM — ENHANCEMENT REQUIREMENT SPECIFICATION (v2.0)

**Project:** PVCFC RAG & Document Management  
**Version Target:** 2.0.0  
**Date:** 2025-12-03  
**Status:** Draft / Approved for Implementation  
**Focus:** AI Auto-Classification & Deep Discovery Search

---

## 1. TỔNG QUAN & MỤC TIÊU

Hệ thống RAG hiện tại (v1.7.1) đã hoàn thiện tốt khả năng hỏi đáp ngữ nghĩa (Semantic QA) và xử lý P&ID. Giai đoạn tiếp theo tập trung vào **Quản trị tri thức (Knowledge Management)** và **Tìm kiếm toàn diện (Exhaustive Search)**.

### Mục tiêu cốt lõi:
1.  **Cấu trúc hóa dữ liệu:** Tự động phân loại kho tài liệu hỗn độn (77+ files và mở rộng) thành cây thư mục logic, chuẩn hóa theo nghiệp vụ nhà máy Đạm.
2.  **Định danh thông minh:** Sử dụng Multimodal AI (Gemini 2.5 Flash) để "nhìn" và hiểu bản chất tài liệu, giải quyết bài toán "nội dung hỗn hợp" (Mixed Content).
3.  **Tìm kiếm không bỏ sót:** Bổ sung cơ chế tìm kiếm Keyword "Deep Discovery" để truy vết toàn bộ tài liệu chứa từ khóa (vd: KT06101), khắc phục giới hạn `top_k` của RAG.
4.  **An toàn tuyệt đối cho P&ID:** Đảm bảo không bao giờ phân loại sai bản vẽ kỹ thuật thành văn bản thường.

---

## 2. TÍNH NĂNG 1: INTELLIGENT AUTO-CLASSIFICATION

### 2.1 Cấu trúc phân loại (Taxonomy)
Hệ thống sẽ tự động gán Metadata (`category`, `doc_type`) cho mỗi file dựa trên 4 nhóm chính:

| Group (Category) | Doc Type (Sub-category) | Mô tả |
| :--- | :--- | :--- |
| **1. ENGINEERING_DESIGN** | `P&ID` | Bản vẽ công nghệ/đường ống (Ưu tiên số 1). |
| | `Drawing` | Các bản vẽ kỹ thuật khác (Layout, ISO...). |
| | `Technical Data` | Thông số kỹ thuật chung, bản tính. |
| **2. VENDOR_EQUIPMENT** | `Datasheet` | Bảng thông số thiết bị. |
| | `Material Partlist` | Danh sách vật tư, Spare parts, BOM. |
| | `Vendor Manual` | Tài liệu hướng dẫn của hãng sản xuất. |
| **3. OPERATIONS_MAINTENANCE** | `Operation Instruction` | Hướng dẫn vận hành (SOP) nội bộ. |
| | `Maintenance Instruction` | Hướng dẫn bảo trì (SMP) nội bộ. |
| | `Maintenance History` | Nhật ký, Logbook, Work Order (Quá khứ). |
| | `Inventory` | Báo cáo tồn kho. |
| **4. SAFETY_MANAGEMENT** | `MOC` | Quản lý thay đổi (Management of Change). |
| | `RCA` | Phân tích nguyên nhân gốc rễ (Report). |
| | `Pictures` | File chỉ chứa hình ảnh hiện trường. |

### 2.2 Chiến lược lấy mẫu (Adaptive Sampling Strategy)
Sử dụng **Gemini 2.5 Flash** (Context Window lớn, chi phí thấp) với chiến thuật "Nhìn đa điểm" (Panorama View) để tránh bị lừa bởi các trang phụ lục.

*   **Logic:**
    *   Nếu File $\le$ 10 trang: Gửi **TOÀN BỘ** các trang.
    *   Nếu File > 10 trang: Gửi **10 trang đại diện**:
        *   **Head (3 trang):** Trang 1, 2, 3 (Bắt Bìa, Mục lục/TOC).
        *   **Tail (2 trang):** Trang N-1, N (Bắt Phụ lục/Chữ ký).
        *   **Body (5 trang):** Rải đều ở giữa (để kiểm tra sự nhất quán nội dung).

### 2.3 Cơ chế kiểm tra kép (Double Validation & Safety Net)
Để đảm bảo P&ID không bao giờ bị sót hoặc nhận diện sai:

*   **Lớp 1: Code-based Guardrail (`CADLikeGate` hiện tại)**
    *   Nếu thuật toán Vector/Regex chấm điểm `CAD Score >= 0.55`: **FORCE ASSIGN** là `ENGINEERING_DESIGN / P&ID`.
    *   *Lý do:* Code bắt Regex tag (KT-06101) cực nhạy, AI có thể bị mờ mắt bởi ảnh scan xấu, nhưng Code thì không.
*   **Lớp 2: AI Reasoning (Gemini Flash)**
    *   Chỉ chạy khi Lớp 1 không khẳng định là P&ID.
    *   Áp dụng **"Dominant Content Rule"** trong Prompt: Đếm tỷ lệ trang Text vs trang Drawing trong 10 ảnh input.
        *   Nếu Text chiếm đa số (kể cả khi có 2-3 trang bản vẽ chèn vào) $\rightarrow$ Phân loại theo nhóm Text (Manual/Report).
        *   Nếu Drawing chiếm đa số $\rightarrow$ Phân loại là Drawing Set.

---

## 3. TÍNH NĂNG 2: DEEP DISCOVERY SEARCH (Tìm kiếm toàn diện)

### 3.1 Vấn đề cần giải quyết
*   RAG hiện tại chỉ lấy `top_k` (ví dụ 50 chunks). Nếu từ khóa "Compressor" xuất hiện trong 200 file, RAG sẽ bỏ sót 150 file còn lại.
*   Người dùng cần danh sách **"Tất cả tài liệu liên quan đến X"** để phục vụ Audit hoặc tra cứu tổng thể.

### 3.2 Giải pháp kỹ thuật: OpenSearch Aggregation
Xây dựng endpoint `/search/documents` mới, **không dùng LLM**, **không dùng Vector Search**, mà dùng **Inverted Index** của OpenSearch.

*   **Input:** Keyword (ví dụ: "KT06101", "Ammonia", "Pump").
*   **Mechanism:**
    *   Query: `multi_match` (phrase_prefix) trên trường `text`.
    *   Aggregation: Bucket theo `doc_id`.
    *   Size: Unlimited (hoặc 10,000 buckets).
*   **Output:** Danh sách Unique Documents chứa keyword, kèm theo Metadata (`category`, `doc_type`) để hiển thị phân nhóm.

---

## 4. YÊU CẦU UI/UX (STREAMLIT UPDATE)

Giao diện cần được nâng cấp để phản ánh cấu trúc dữ liệu mới và tính năng tìm kiếm sâu. Code base đã có nền tảng, cần hoàn thiện các module sau:

### 4.1 Tab "Document Explorer" (Quản lý tài liệu)
*   **Layout:** Chia màn hình thành 2 phần (Sidebar Tree & Main Content).
*   **Feature 1: Tree View Navigation**
    *   Hiển thị cây thư mục theo 4 Nhóm chính $\rightarrow$ Các Loại con $\rightarrow$ Danh sách File PDF.
    *   Cho phép click vào tên file để xem Preview/Metadata.
*   **Feature 2: Auto-Tagging Status**
    *   Hiển thị trạng thái phân loại của 77 file (Đã phân loại / Chưa / Cần review).
    *   Nút "Run Auto-Classification" để kích hoạt pipeline Gemini Flash cho các file mới.

### 4.2 Tab "Deep Search" (Tìm kiếm toàn diện)
Tách biệt với "Chat RAG". Đây là giao diện giống Google Search / Windows Explorer.

*   **Search Bar:** Nhập keyword (không cần câu hỏi tự nhiên).
*   **Filters:** Dropdown lọc theo `Category` hoặc `Doc Type`.
*   **Result View:**
    *   Không hiện câu trả lời AI.
    *   Hiện danh sách các File tìm thấy, nhóm theo Category.
    *   Hiển thị: Tên file | Loại | Số lần xuất hiện keyword | Nút "View" (Mở PDF tại trang chứa keyword đầu tiên).

---

## 5. LỘ TRÌNH THỰC HIỆN (IMPLEMENTATION PLAN)

### Phase 1: Backend & Core Logic
1.  **Refactor Ingestion Pipeline:**
    *   Tích hợp hàm `get_adaptive_sample_indices` (10 trang).
    *   Cập nhật `CADLikeGate` để trả về flag `is_forced_pid`.
2.  **Implement Gemini Classifier:**
    *   Viết System Prompt mới (Rule: Dominant Content).
    *   Tạo function `classify_document_hybrid(pdf_path)`.
3.  **Update Database Schema:**
    *   Thêm field `metadata.category` và `metadata.doc_type` vào OpenSearch index `rag_chunks` và Weaviate.
    *   Viết script chạy một lần để update metadata cho 77 file hiện có.

### Phase 2: Search API
1.  **New Endpoint:** `GET /api/search/documents`
    *   Logic: OpenSearch Aggregation.
    *   Response: JSON cấu trúc phân tầng (Group -> Type -> File).

### Phase 3: Frontend (Streamlit)
1.  **Update Sidebar:** Thêm mode chuyển đổi giữa "Chat Assistant" và "Document Library".
2.  **Build UI Components:**
    *   `render_folder_structure()`: Hiển thị cây thư mục.
    *   `render_search_results_grid()`: Hiển thị kết quả Deep Search.

---

## 6. TIÊU CHÍ NGHIỆM THU (ACCEPTANCE CRITERIA)

1.  **Độ chính xác P&ID:** 100%. Không file P&ID nào bị xếp vào Manual.
2.  **Xử lý Mixed Content:** Các file Manual dày có chèn hình P&ID phải được xếp đúng là Manual (Operation Instruction/Vendor Manual).
3.  **Deep Search:** Khi tìm "KT06101", hệ thống phải trả về **tất cả** file có chứa từ này, bất kể file đó thuộc nhóm nào.
4.  **UI/UX:** Giao diện cây thư mục hiển thị rõ ràng 4 nhóm, dễ điều hướng.

---
*End of Specification*