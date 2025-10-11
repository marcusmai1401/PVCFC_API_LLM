# ADR-2025-10: Nâng độ chính xác trích nguồn (citation) cho PVCFC_API_LLM

**Ngày:** 2025-10-10
**Tình trạng:** Chốt & triển khai
**Phạm vi:** Truy hồi → rerank → sắp trang cho VLM (vision) → sinh câu trả lời có bằng chứng → hậu xử lý citation
**Không nằm trong phạm vi:** Xây Field Store/KB (trì hoãn)

---

## 1) Quyết định cốt lõi

1. **Reranker:** dùng **BAAI/bge-reranker-v2-m3** làm **cross-encoder reranker** ở 2 tầng (doc/chunk-level và page-level). Điểm trả về chuẩn hóa sigmoid về [0,1]. Mục tiêu: “lật kèo” các kết quả sai miền & đẩy **đúng trang** chứa bằng chứng lên đầu.
2. **Ràng buộc miền (domain prefilter):** sinh **bộ lọc metadata** từ truy vấn (self-query) và **áp pre-filter** trước truy hồi (BM25 ∪ vector). Ưu tiên các vector DB có filter ngay khi search; nếu FAISS thuần thì route sang index theo miền.
3. **Vision re-order (page order cho VLM):** **OCR từng trang**, tính **điểm rerank ở mức trang** bằng BGE, rồi chọn top-N với **MMR** để vừa liên quan vừa đa dạng (giảm trùng lặp). Không dùng công thức `retrieval_score × 10`.
4. **Đầu ra có cấu trúc (JSON-with-evidence):** LLM **bắt buộc** trả JSON theo claim, mỗi claim gắn `{doc_id, page, span, score}`. Áp dụng structured outputs + “RAG with citations” trong framework bạn dùng.
5. **Hậu xử lý trích dẫn (mặc định):** **CiteFix-style** — so khớp keyword + semantic (ví dụ BERTScore) + LLM nhẹ để **sửa citation yếu**, tác động nhỏ đến latency/cost; ghi nhận cải thiện đáng kể độ chính xác trích dẫn.
6. **RARR (tuỳ chọn, gated):** **không bật mặc định**. Chỉ kích hoạt khi **support rate** thấp hoặc ở **strict mode** (tuân thủ/audit), vì RARR là hậu kỳ “research & revision” tốn thêm LLM/time nhưng cải thiện attribution rõ rệt.
7. **Field Store/KB:** **tạm hoãn** (không cần nếu factuality đã tốt). Sẽ cân nhắc lại khi cần governance/đổi đơn vị hệ thống hoặc audit cấp doanh nghiệp.

---

## 2) Mục tiêu & KPI nghiệm thu

- **Citation Accuracy@Doc ≥ 0.90**, **Citation Accuracy@Page ≥ 0.80** (golden set).
- **Support rate ≥ 0.85** (tỷ lệ claim có span đạt ngưỡng).
- **MRR@10 (sau rerank) tăng ≥ 20%** so baseline trước đây.
- **Latency ngân sách:** +150–500 ms ở doc-level rerank; +300–800 ms ở page-level (tùy batch & VRAM); lớp CiteFix thêm rất ít. (Cross-encoder dùng cho **top-K** nhỏ để cân bằng chính xác/thời gian.)

---

## 3) Kiến trúc sau khi nâng cấp

```mermaid
flowchart LR
A[Query] --> B[Self-query\n→ JSON Filters]
B --> C[Hybrid Retrieve\n(BM25 ∪ Vector\nwith Prefilter)]
C --> D[Doc/Chunk Rerank\nBGE v2-m3]
D --> E[Collect Pages\n+ OCR per page]
E --> F[Page Rerank (BGE)\n+ MMR select Top-N]
F --> G[LLM → JSON with Evidence\n(per-claim {doc,page,span,score})]
G --> H[CiteFix Post-hoc\n(fix weak citations)]
H --> I[Answer + References\n(“lấy ở đâu trích ở đó”)]
```

- **Self-query & Filters:** suy ra `equipment_type`, `doc_type`, `equipment_id/tag`, … rồi **áp pre-filter** ở DB/vector store.
- **Page-level:** sử dụng **PaddleOCR** (đã sẵn) hoặc pipeline parsing `hi_res` khi cần layout fidelity cao.
- **MMR:** chọn trang **liên quan + đa dạng**, giảm 5 trang gần giống nhau.

---

## 4) Cấu hình khuyến nghị (v1)

**BGE v2-m3 (FlagEmbedding):**
```python
from FlagEmbedding import FlagReranker
rerank = FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=True)
scores = rerank.compute_score(pairs, normalize=True, max_length=1024)
# sort by score desc; keep top-M
```
- `K_doc` = 200 (BM25 ∪ vector), `K_page` = 40, `M_final` = 20.
- `max_length=1024`, `normalize=True`, batch theo VRAM.

**Prefilter theo miền:**
- Dùng filter của vector DB (pre-filtering) hoặc tách nhiều FAISS index theo miền + router.

**Vision re-order:**
- `score_page = BGE(query, page_text_OCR)` → **MMR** (λ≈0.4) → render ảnh trang theo thứ tự mới.

**JSON-with-evidence (schema gợi ý):**
```json
{
  "question": "...",
  "claims": [
    {
      "id":"c1","field":"discharge_pressure","value":79.5,"unit":"bar.a",
      "evidence":[{"doc_id":"CO2_COMPRESSOR_DS","page":3,"span":"...79.5 bar.a...","score":0.92}],
      "supported": true
    }
  ],
  "confidence_overall": 0.90
}
```

**CiteFix (mặc định):**
- Cross-check citations bằng keyword + semantic/BERTScore + LLM nhẹ; **chỉ sửa citation**, **không sửa giá trị**.

**RARR (gated):**
- Chỉ chạy khi `support_rate < 0.8` hoặc **strict mode**; RARR tự tìm bằng chứng và **sửa đoạn không được chứng minh** (post-hoc).

---

## 5) Thay đổi ở quy trình ingest (nhẹ, đủ dùng)

- **Auto-tag metadata** (equipment_type, doc_type, id/tag, vendor, …) để self-query có dữ liệu lọc.
- **Parsing/partition:** `strategy="hi_res"` cho layout-aware, kết hợp **PaddleOCR** và **Camelot** để bóc **bảng** kỹ thuật khi cần.

> Ghi chú: “Field Store/KB” **tạm hoãn** — chỉ cân nhắc khi cần governance/chuẩn đơn vị hệ thống & audit.

---

## 6) Kế hoạch triển khai (2 tuần)

**Tuần 1**
- Thay lớp reranker → **BGE v2-m3** (doc-level).
- Bổ sung **self-query filters** và **prefilter** ở vector/BM25.
- Thêm endpoint trả **JSON-with-evidence** (schema cố định).

**Tuần 2**
- Page-level OCR → **BGE rerank** + **MMR** cho vision re-order.
- Cắm **CiteFix** hậu xử lý citation (mặc định ON).
- Golden-set & dashboard KPI (Citation@Doc/@Page, Support rate, MRR@10, latency).

---

## 7) Rủi ro & biện pháp

- **Latency tăng** do cross-encoder: khống chế **K** hợp lý, batch theo VRAM, chỉ rerank page cho **ứng viên** sau doc-level.
- **OCR noise**: ưu tiên PDF text-based; với scan, dùng PaddleOCR + (tuỳ chọn) `hi_res` partition để cải thiện block detection.
- **Sai miền còn sót:** tăng cường từ điển miền + siết filter (ví dụ loại turbine khi hỏi compressor).

---

## 8) Tiêu chí “Hoàn tất” (DoD)

- ≥ **0.90 / 0.80** Citation Accuracy **Doc/Page** trên golden-set.
- **100%** câu trả lời dạng kỹ thuật **trả JSON-with-evidence** hợp lệ; claim thiếu bằng chứng → `supported=false` (không chèn citation “bừa”).
- Latency trong ngân sách; **CiteFix** bật mặc định; **RARR** chạy khi gated.

---

## 9) Tài liệu tham khảo (gợi ý đọc thêm)

- BGE v2-m3 (model card & hướng dẫn, FlagEmbedding).
- Self-RAG (ý tưởng reflect/retrieve khi cần).
- RARR (Retrofit Attribution using Research & Revision).
- CiteFix (chỉnh citation sau sinh, chi phí thấp).
- LangChain How-to: Structured Outputs, Add citations, Self-query filters.
- MMR (Carbonell & Goldstein, SIGIR’98).
- Parsing/OCR: Unstructured `hi_res`, PaddleOCR, Camelot.
