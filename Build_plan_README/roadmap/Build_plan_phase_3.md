# PHASE 3 — EVALUATION, UI DEMO & OBSERVABILITY (V1)

Tài liệu pha 3 cho PVCFC RAG (V1). Mục tiêu: thiết lập bộ đánh giá chuẩn (offline + online), xây dựng UI demo (Streamlit) cho SME, và hoàn thiện observability (logs/metrics/tracing) để đo lường Recall/Precision, Faithfulness/Groundedness, Citation correctness, Latency/Cost.

---

## 1) Mục tiêu & Kết quả mong đợi

- Golden set ≥ 120 QA (có negative cases), bao phủ datasheet/P&ID/SOP/OM, nhiều loại câu hỏi (lookup, locate, quy trình, phủ định) và mức độ khó (easy/medium/hard).
- Đánh giá Retrieval & End-to-end với các thước đo rõ ràng; xuất báo cáo phase3_report.md + CSV/JSON.
- UI demo (Streamlit) cho SME xem câu trả lời + citations; UI render footnote từ citations; preview ảnh trang (không yêu cầu bbox).
- Observability: logs JSONL, Prometheus/OTel metrics, dashboard biểu đồ latency/cache-hit/lỗi.

---

## 2) Phạm vi & Không phạm vi

- Có (Phase 3):
  - Golden set & evaluation scripts (retrieval/e2e; với/không HyDE; cấu hình k/top_rerank).
  - Streamlit UI demo: answer markdown + citations, preview ảnh trang từ cache/render.
  - Logs/metrics/tracing; dashboard cơ bản; export sessions.
- Không (để Phase 4):
  - Bbox overlay bắt buộc; ablation tối ưu sâu; phát hành production chính thức.

---

## 3) Golden Set (thiết kế & quản lý)

- Quy mô & phân bố:
  - Tối thiểu 120 QA (khuyến nghị 150); ngôn ngữ chính: VI, bổ sung 10–20% EN.
  - Phân bố theo doc_category: datasheet / P&ID / SOP / OM (mỗi nhóm ≥ 25–30 câu cấp độ tổng thể).
  - Loại truy vấn: lookup tham số; locate tag/trang; quy trình/safety; sơ đồ/luồng; negative/unsupported; ambiguous.
  - Độ khó: easy/medium/hard (mỗi mức ~1/3).
- Cấu trúc JSONL (ví dụ):
```json
{
  "id": "Q0001",
  "query": "Áp suất vận hành tối đa của KT06101?",
  "expected_answer": "... (ngắn gọn, có con số/đơn vị) ...",
  "doc_hints": ["PVCFC-KT06101-datasheet-v1"],
  "expected_citations": [{"doc_id":"...","page":12}],
  "language": "vi",
  "category": "datasheet",
  "type": "lookup",
  "difficulty": "easy"
}
```
- Quy trình tạo:
  - Draft bởi kỹ sư (tham chiếu trực tiếp tài liệu), review chéo, SME phê duyệt.
  - ≥ 10% câu negative (không đủ bằng chứng).
  - Lưu version: `golden_vX.jsonl` + CHANGELOG.md.

---

## 4) Thước đo & Mục tiêu định lượng (gợi ý)

- Retrieval-level (offline/online): Recall@k (k=5,10), MRR@k, nDCG@k; Context Precision/Recall (RAGAs).
  - Chỉ tiêu gợi ý: Recall@10 ≥ 80% tổng thể.
- Answer-level: Faithfulness / Groundedness (RAGAs/TruLens), Answer Correctness (SME rubric), Citation precision/recall (so doc_id/page).
  - Chỉ tiêu gợi ý: Faithfulness ≥ 0.8; Citation precision ≥ 95%; Citation recall ≥ 90%.
- Hiệu năng: Latency p50/p95; time breakdown (transform/retrieve/rerank/generate); tokens/chi phí.

---

## 5) Evaluation pipeline (scripts)

- Retrieval eval (offline):
  - Input: golden queries (+ doc_hints nếu có).
  - Chạy retriever (BM25+FAISS → hợp nhất) không sinh answer → tính Recall/MRR/nDCG; log topN & params.
- End-to-end eval:
  - Chạy full pipeline với cấu hình chuẩn (MAX_CONTEXT, TOP_RERANK) và biến thể (với/không HyDE).
  - Tính RAGAs (Faithfulness/Context Precision/Answer Relevancy) khi áp dụng được; kiểm tra tự động citation (doc_id/page).
- Output:
  - CSV/JSON: bảng chi tiết + tổng hợp theo category/type/difficulty.
  - Report: `artifacts/eval/phase3_report.md` + đồ thị (plotly) (tuỳ chọn).

---

## 6) UI Demo (Streamlit)

- Thành phần UI:
  - Form nhập query (auto-language); optional filters doc_id/doc_category; bật/tắt HyDE; chỉnh MAX_CONTEXT/TOP_RERANK (developer tab).
  - Kết quả: answer (Markdown) + danh sách citations (doc_id, page, pdf_path? nếu có).
  - **Footnote display**: UI render `[n] {doc_id}; p.{page}` dựa trên mảng citations[] (backend không chèn footnote vào answer để tránh trùng).
  - **Preview ảnh trang**: gọi renderer on-demand, dùng cache (`artifacts\cache\pdf_pages`).
  - Bảng “Top hits” (BM25/FAISS/RRF) + scores (developer tab).
  - Telemetry: tổng latency, breakdown theo bước, cache hit, model_generation/model_query_transform, flags vision/text-range/degrade.
- Export sessions:
  - Lưu `logs/ui_sessions.jsonl`: query, answer, citations, params (k, rerank, flags), timestamps.

---

## 7) Observability (Logs/Metrics/Tracing)

- Logging JSONL: `logs/requests.jsonl` (mỗi request gồm timing_by_stage, flags, citations_used, degrade_mode/reason).
- Prometheus metrics: tổng latency, breakdown theo bước, cache hit rate, error rate; counters cho Vision ON/OFF, degrade events.
- Tracing (OTel): trace end-to-end; correlate logs qua trace_id.

---

## 8) Lệnh chạy demo & eval (tham khảo)

- Chạy UI demo:
```bash
streamlit run streamlit_app\Main.py
```
- Chạy eval offline (gợi ý):
```bash
python tools\eval_retrieval.py --golden artifacts\golden\golden_v1.jsonl --k 10
python tools\eval_e2e.py --golden artifacts\golden\golden_v1.jsonl --max_context 8 --top_rerank 20
```

---

## 9) Định nghĩa Hoàn thành (DoD)

- Golden set ≥ 120 QA (có negative) và lưu version/changelog.
- Batch eval chạy được; xuất `artifacts/eval/phase3_report.md` + CSV/JSON; có bảng tổng hợp metrics.
- UI demo: answer + citations; **UI render footnote từ citations**; preview ảnh trang (không bắt buộc bbox).
- Telemetry/metrics/tracing đầy đủ: hiển thị flags vision/text-range/degrade và breakdown thời gian; dashboard latency/cache-hit/lỗi.

---

## 10) Rủi ro & Ứng phó

- Bbox không sẵn (V1): dùng preview ảnh trang + footnote citations; overlay bbox để roadmap.
- Sai số đánh giá tự động: dùng SME rubric làm ground truth; kiểm tra chéo 10–15% (Cohen’s κ).
- Streamlit hiệu năng thấp cho file lớn: cache preview trang; chỉ render khi click; giới hạn pages preview.

---

## 11) Phụ lục

- Gợi ý Golden Set categories & sampling: giữ cân bằng giữa 4 nhóm tài liệu; thêm negative/ambiguous đủ tỷ lệ.
- Tham số mặc định: MAX_CONTEXT=8, TOP_RERANK=20 (đồng bộ ENV); HyDE bật/tắt theo kịch bản.
