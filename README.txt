# **README.md - Dự án API Truy vấn Tài liệu Kỹ thuật PVCFC**

## **1. Tổng Quan Dự Án**

### **1.1. Mục tiêu**

Xây dựng một nền tảng API dựa trên Mô hình Ngôn ngữ Lớn (LLM) và kiến trúc Truy xuất Tăng cường (RAG) để truy xuất, phân tích và tóm tắt tri thức từ kho tài liệu kỹ thuật đa định dạng tại PVCFC. Hệ thống sẽ hoạt động như một "bộ não tri thức kỹ thuật" trung tâm, cung cấp các câu trả lời chính xác, có kiểm chứng và trích dẫn trực tiếp từ tài liệu gốc.

### **1.2. Phạm vi Thí điểm (MVP)**

Giai đoạn đầu xác thực kiến trúc trên một tập tài liệu đại diện và các yêu cầu cốt lõi:

*   **Nhóm tài liệu chính (4 loại):** P&ID, Management of Change (MOC), Root Cause Analysis (RCA), Technical Data.
*   **Yêu cầu trọng tâm:**
    *   Tìm kiếm theo tag và mở tài liệu nhảy đúng trang (page-level).
    *   Q&A chi tiết, trích dẫn kiểu footnote (doc_id; page), tự động chọn ngôn ngữ theo input (vi/en).
    *   Report cơ bản (markdown) theo template cố định.

## **2. Kiến trúc Hệ thống**

Hệ thống được xây dựng dựa trên kiến trúc RAG nâng cao, bao gồm hai luồng chính: Ingest Pipeline (ngoại tuyến) và Query Pipeline (trực tuyến).

```mermaid
graph TD
    subgraph Ingest_Pipeline_Offline
        A[Raw Docs: Vector/Scanned PDF] --> B{Parsing & Layout Analysis}
        B -->|Vector| B1[PyMuPDF]
        B -->|Scanned| B2[unstructured / OCR]
        B1 --> C[Chuẩn hoá Markdown]
        B2 --> C
        C --> D[Hierarchical Chunking]
        D --> E[Small-to-Big Chunks]
        E --> F{Hybrid Indexing}
        F --> G[Vector Index - FAISS]
        F --> H[Keyword Index - BM25]
        C --> P[Render Page Previews]
    end

    subgraph Query_Pipeline_Online
        I[User Query] --> J[Query Transformation (HyDE optional)]
        J --> K[Hybrid Retrieval]
        G --> K
        H --> K
        K --> L[Cross-Encoder Reranking]
        L --> X[Page-Range Expansion (Always-On)]
        X --> Y[LLM Generation (Grounded + CoVe)]
        Y --> M[Answer + Footnote Citations]
    end
```

## **3. Các Thách Thức Kỹ Thuật Chính và Giải Pháp**

### **3.1. Xử lý Tài liệu Kỹ thuật Không đồng nhất**
*   **Thách thức:** Xử lý cả PDF vector và PDF scan; trích xuất thông tin từ các layout phức tạp (bảng biểu, sơ đồ) mà không làm mất ngữ cảnh.
*   **Giải pháp:**
    1.  **Parsing đa chiến lược:** PyMuPDF cho vector; unstructured + OCR cho scan.
    2.  **Chuẩn hóa sang Markdown:** Giữ cấu trúc tiêu đề/bảng/danh sách.
    3.  **Chunking theo cấu trúc:** "Small-to-Big" + parent để mở rộng ngữ cảnh.

### **3.2. Nâng cao Độ chính xác Truy xuất**
*   **Thách thức:** Vượt qua "khoảng trống ngữ nghĩa" và gom đúng vùng trang liên tiếp chứa thông tin.
*   **Giải pháp:**
    1.  **Query Transformation (HyDE tùy chọn):** Chuẩn hoá truy vấn, sinh biến thể để tăng recall.
    2.  **Hybrid Search:** Kết hợp BM25 + Vector, hợp nhất bằng **RRF**.
    3.  **Reranking:** **Cross-Encoder** tinh lọc top kết quả.
    4.  **Page-Range Expansion (luôn bật):** Gom cụm trang liên tiếp theo `doc_id` (ví dụ 10–15) có tổng điểm cao, nạp toàn bộ dải trang làm context cho bước sinh.

### **3.3. Đảm bảo Tính Tin cậy của LLM**
*   **Thách thức:** Giảm thiểu "ảo giác"; trả lời dựa trên bằng chứng.
*   **Giải pháp:**
    1.  **Grounded Generation:** Buộc chỉ dùng ngữ cảnh dải trang đã gom.
    2.  **Chain-of-Verification (CoVe):** Kiểm chứng mệnh đề quan trọng bằng truy vấn phụ.
    3.  **Footnote Citations:** Trả lời kèm trích dẫn dạng footnote (`doc_id; page`) và từ chối nếu thiếu bằng chứng.
    4.  **Auto-language:** Trả lời theo ngôn ngữ đầu vào (vi/en) mà không cần người dùng chọn tay.

## **4. Đặc tả API**

Hệ thống sẽ cung cấp 3 điểm cuối API chính:

*   **`POST /ask`**: Nhận câu hỏi, trả về câu trả lời chi tiết (markdown) kèm trích dẫn footnote (doc_id; page). Luôn ưu tiên Q&A (không tách riêng locate nếu câu không mang tính định vị).
*   **`POST /locate`**: Nhận một mã hiệu (tag), trả về danh sách các vị trí (`doc_id`, `page`, `bbox` nếu có) trên bản vẽ P&ID.
*   **`POST /report`**: Nhận yêu cầu tạo báo cáo, trả về **markdown** theo template cố định (sau có thể map sang CSV/Excel).

## **5. Công nghệ và Công cụ**

| Lĩnh vực              | Công cụ/Công nghệ                                                                                               |
| :-------------------- | :------------------------------------------------------------------------------------------------------------- |
| **Backend & API**     | Python 3.11+, FastAPI, Uvicorn                                                                                 |
| **Parsing & OCR**     | `unstructured`, `PyMuPDF`, `pytesseract` (fallback)                                                             |
| **Indexing**          | `rank-bm25` (Keyword), `FAISS` (Vector)                                                                        |
| **RAG Pipeline**      | FastAPI modules (custom): query_transform, retriever (FAISS+BM25), reranker, generator, CoVe                    |
| **Mô hình Embedding** | `sentence-transformers` (BGE-small/base) hoặc `google-generativeai` embeddings                                  |
| **Mô hình Reranker**  | `cross-encoder/ms-marco-MiniLM-L-6-v2` (hoặc phiên bản mạnh hơn)                                               |
| **LLM (Production)**  | `google-genai` (Gemini) / `openai` (tùy cấu hình ENV), không dùng tiers/modes                                   |
| **UI Demo**           | Streamlit                                                                                                       |
| **Đánh giá & Giám sát** | `prometheus-client`, RAGAs/TruLens (tùy chọn)                                                                  |

## **6. Kế hoạch Triển khai (4 Giai đoạn)**

1.  **Giai đoạn 1: Xây dựng Nền tảng Ingest & Indexing:** Tập trung vào pipeline xử lý dữ liệu, chuẩn hoá/metadata (có `page`), build FAISS/BM25, render page previews.
2.  **Giai đoạn 2: Xây dựng API & Tầng Truy xuất:** Hoàn thiện RAG nâng cao, **page-range expansion luôn bật**, Q&A có footnote citations.
3.  **Giai đoạn 3: Kiểm thử, Đánh giá và Tinh chỉnh:** Golden Set, UI Demo (Device Overview, nhảy trang, auto-language), đánh giá để tối ưu.
4.  **Giai đoạn 4: Hoàn thiện, Đóng gói và Chuyển giao:** Tối ưu hiệu năng, Docker/Compose, tài liệu bàn giao.

Chi tiết thực hiện xem trong thư mục `Build_plan_README/` (ngôn ngữ: TIẾNG VIỆT). Cần tuân thủ kế hoạch trừ khi có yêu cầu khác.
