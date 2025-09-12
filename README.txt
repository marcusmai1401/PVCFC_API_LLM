# **README.md - Dự án API Truy vấn Tài liệu Kỹ thuật PVCFC**

## **1. Tổng Quan Dự Án**

### **1.1. Mục tiêu**

Xây dựng một nền tảng API dựa trên Mô hình Ngôn ngữ Lớn (LLM) và kiến trúc Truy xuất Tăng cường (RAG) để truy xuất, phân tích và tóm tắt tri thức từ kho tài liệu kỹ thuật đa định dạng tại PVCFC. Hệ thống sẽ hoạt động như một "bộ não tri thức kỹ thuật" trung tâm, cung cấp các câu trả lời chính xác, có kiểm chứng và trích dẫn trực tiếp từ tài liệu gốc.

### **1.2. Phạm vi Thí điểm (MVP)**

Giai đoạn đầu của dự án sẽ tập trung vào một bộ tài liệu giới hạn để xác thực kiến trúc và đo lường hiệu quả trước khi mở rộng.

*   **Thiết bị Trọng tâm:** Máy nén CO2 (CO2 COMPRESSOR) - Mã hiệu **KT06101**.
*   **Tài liệu Đầu vào:**
    *   Bản vẽ P&ID của Cụm Amoniac (Ammonia Unit) - Mã hiệu **04000**.
    *   Bảng dữ liệu kỹ thuật (Datasheet) của thiết bị KT06101.
    *   Các quy trình vận hành (SOP) và hướng dẫn bảo trì (OM) liên quan.

## **2. Kiến trúc Hệ thống**

Hệ thống được xây dựng dựa trên kiến trúc RAG nâng cao, bao gồm hai luồng chính: Ingest Pipeline (ngoại tuyến) và Query Pipeline (trực tuyến).

```mermaid
graph TD
    subgraph Ingest_Pipeline_Offline
        A[Raw Docs: Vector/Scanned PDF] --> B{Parsing & Layout Analysis}
        B -->|Vector| B1[PyMuPDF4LLM]
        B -->|Scanned| B2[unstructured.io]
        B1 --> C[Standardized Markdown]
        B2 --> C
        C --> D[Hierarchical Chunking]
        D --> E[Small-to-Big Chunks]
        E --> F{Hybrid Indexing}
        F --> G[Vector Index - FAISS]
        F --> H[Keyword Index - BM25]
    end

    subgraph Query_Pipeline_Online
        I[User Query] --> J{LLM 2-Tier Architecture}
        J --> J1[Tier 1 Small LLM: Query Transformation]
        J1 --> K[Hybrid Retrieval]
        G --> K
        H --> K
        K --> L[Cross-Encoder Reranking]
        L --> J2[Tier 2 Large LLM: CoVe Generation]
        J2 --> M[Answer + Citations]
    end
```

## **3. Các Thách Thức Kỹ Thuật Chính và Giải Pháp**

### **3.1. Xử lý Tài liệu Kỹ thuật Không đồng nhất**
*   **Thách thức:** Xử lý cả PDF vector và PDF scan; trích xuất thông tin từ các layout phức tạp (bảng biểu, sơ đồ) mà không làm mất ngữ cảnh.
*   **Giải pháp:**
    1.  **Parsing Đa luồng:** Dùng `unstructured.io` làm công cụ parsing chính, có khả năng tự động xử lý cả hai loại PDF và nhận dạng bố cục.
    2.  **Chuẩn hóa sang Markdown:** Chuyển đổi toàn bộ tài liệu thành định dạng Markdown có cấu trúc để bảo toàn tiêu đề, bảng, và danh sách.
    3.  **Chunking Thông minh:** Áp dụng chiến lược "Small-to-Big", phân đoạn dựa trên cấu trúc Markdown để giữ lại các đơn vị ngữ nghĩa hoàn chỉnh.

### **3.2. Nâng cao Độ chính xác Truy xuất**
*   **Thách thức:** Vượt qua "khoảng trống ngữ nghĩa" giữa câu hỏi của người dùng và từ vựng trong tài liệu; đảm bảo các kết quả truy xuất có độ liên quan cao nhất.
*   **Giải pháp:**
    1.  **Query Transformation:** Dùng một LLM tầng nhẹ (Tier 1) để thực hiện các kỹ thuật như **HyDE** (tạo tài liệu giả định) nhằm tối ưu hóa truy vấn.
    2.  **Hybrid Search:** Kết hợp tìm kiếm từ khóa (**BM25**) và tìm kiếm ngữ nghĩa (**Vector Search**), hợp nhất kết quả bằng thuật toán **RRF**.
    3.  **Reranking:** Dùng một mô hình **Cross-Encoder** để tinh lọc và sắp xếp lại top 5-8 chunk chất lượng nhất trước khi đưa vào LLM chính.

### **3.3. Đảm bảo Tính Tin cậy của LLM**
*   **Thách thức:** Giảm thiểu tối đa hiện tượng "ảo giác" (hallucination) và đảm bảo mọi thông tin đều có thể kiểm chứng.
*   **Giải pháp:**
    1.  **Grounded Generation:** Thiết kế prompt nghiêm ngặt, buộc LLM chỉ được trả lời dựa trên ngữ cảnh được cung cấp.
    2.  **Chain-of-Verification (CoVe):** Triển khai quy trình tự kiểm tra 4 bước (Draft -> Plan -> Execute -> Finalize) để LLM tự xác minh thông tin trước khi trả lời.
    3.  **Forced Citation:** Yêu cầu LLM phải trích dẫn nguồn (`Doc_ID; Trang`) cho mọi thông tin và có cơ chế từ chối trả lời nếu không có bằng chứng.

## **4. Đặc tả API**

Hệ thống sẽ cung cấp 3 điểm cuối API chính:

*   **`POST /ask`**: Nhận một câu hỏi, trả về câu trả lời đã được tổng hợp và một danh sách các trích dẫn nguồn.
*   **`POST /locate`**: Nhận một mã hiệu (tag), trả về danh sách các vị trí (`doc_id`, `page`, `bbox` nếu có) trên bản vẽ P&ID.
*   **`POST /report`**: Nhận một yêu cầu tạo báo cáo, trả về một file báo cáo (Word/PDF) đã được tự động điền thông tin.

## **5. Công nghệ và Công cụ**

| Lĩnh vực              | Công cụ/Công nghệ                                                                                               |
| :-------------------- | :------------------------------------------------------------------------------------------------------------- |
| **Backend & API**     | Python 3.11+, FastAPI, Uvicorn                                                                                 |
| **Parsing & OCR**     | `unstructured.io`, `PyMuPDF`, `pytesseract` (fallback)                                                         |
| **Indexing**          | `rank_bm25` (Keyword), `FAISS` (Vector)                                                                        |
| **RAG Pipeline**      | `LlamaIndex` / `LangChain`                                                                                     |
| **Mô hình Embedding**   | **Lựa chọn 1 (API):** `text-embedding-3-large` (OpenAI)<br>**Lựa chọn 2 (Open Source):** `BGE-large-en-v1.5`     |
| **Mô hình Reranker**  | `cross-encoder/ms-marco-MiniLM-L-6-v2` (hoặc các phiên bản mạnh hơn)                                            |
| **LLM Tầng Nhẹ**      | `GPT-5 mini` / `Gemini 1.5 Flash`                                                                              |
| **LLM Tầng Nặng**      | `Gemini 2.5 Pro` / `GPT-5`                                                                                     |
| **UI Demo**           | Streamlit                                                                                                      |
| **Đánh giá & Giám sát** | `RAGAs`, `LangSmith` / `TruLens`                                                                               |

## **6. Kế hoạch Triển khai (4 Giai đoạn)**

1.  **Giai đoạn 1: Xây dựng Nền tảng Ingest & Indexing:** Tập trung vào việc xây dựng pipeline xử lý dữ liệu hoàn chỉnh, tạo ra Index v1.0 chất lượng cao.
2.  **Giai đoạn 2: Xây dựng API & Tầng Truy xuất:** Hoàn thiện các API, triển khai luồng RAG nâng cao từ truy vấn đến tạo sinh câu trả lời.
3.  **Giai đoạn 3: Kiểm thử, Đánh giá và Tinh chỉnh:** Xây dựng Golden Set, UI Demo, và thực hiện các vòng lặp đánh giá (tự động và bởi SME) để tối ưu hệ thống.
4.  **Giai đoạn 4: Hoàn thiện, Đóng gói và Chuyển giao:** Tối ưu hóa hiệu năng, đóng gói ứng dụng bằng Docker, và hoàn thiện toàn bộ tài liệu dự án.

NOTE: Lưu ý trong quá trình viết code không sử dụng icon, emoji, v..v
