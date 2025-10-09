# Báo cáo vấn đề & mục tiêu – Độ chính xác trích nguồn (Citations)

Ngày: 2025-10-07
Tài liệu: Problem statement + Goals (phục vụ nghiên cứu và lựa chọn giải pháp)

## 1) Bối cảnh & Tóm tắt điều hành
- Hệ thống RAG hiện tại trả lời nội dung nhìn chung tốt, nhưng phần trích nguồn (doc_id + trang) **không ổn định**.
- Kết quả kiểm thử golden gần nhất (5 câu hỏi):
  - Pass rate (đúng doc + đúng trang): 20%
  - Doc match rate (đúng tài liệu): 80%
  - Page error rate (sai trang): 80%
  - Validator không sửa được trích nguồn nào (0% correction)
- Nhận định: Lỗi chính tập trung ở **khâu chọn trang** (page selection) sau khi đã tìm đúng tài liệu, cộng với **thiếu kiểm chứng/hậu kiểm** hiệu quả.

## 2) Triệu chứng quan sát được (từ kiểm thử)
Nguồn số liệu: `reports/test_results/citation_accuracy_golden_*.json`, `reports/test_results/page_flow_trace_*.json`
- Có nhiều trường hợp:
  - Đúng tài liệu nhưng lệch 1 trang (ví dụ: kỳ vọng p.8, thực tế p.9).
  - Đúng tài liệu nhưng trích nhiều trang (p.2, p.1, p.4) thay vì 1 trang tốt nhất.
  - Lệch trang lớn (±7–8 trang) với các tài liệu dài.
- LLM đôi khi chèn `[Doc X, p.Y]` nhiều lần cho các chunk khác nhau trong cùng tài liệu → sinh ra nhiều citations khác trang.

## 3) Chẩn đoán & Nguyên nhân gốc
- (R1) **Metadata.page thiếu chính xác/không đồng nhất**:
  - Chunk có thể bao phủ nhiều trang; `metadata.page` đôi lúc là trang giữa hoặc fallback về 1.
  - Dấu mốc trang từ markdown/OCR không khớp với nguồn `text_by_page` dùng để so sánh.
- (R2) **Thiếu chọn trang ở cấp page (page-level)**:
  - Pipeline đang dựa vào `metadata.page` của chunk thay vì **ranking trang** trong tài liệu.
  - Chưa bật/thiết lập đúng Page Reranker (BM25 page + cross-encoder trên trang).
- (R3) **Hậu kiểm (Validator) chưa hiệu quả**:
  - Không sửa được trang (0% correction) do ngưỡng fuzzy cao, dải neighbor quá hẹp (±2), và/hoặc chênh lệch extractor giữa `text_by_page` và nội dung LLM sử dụng.

## 4) Tác động
- Người dùng khó kiểm chứng câu trả lời vì citation không trỏ đúng vị trí.
- Giảm niềm tin, tăng thời gian tra soát thủ công.
- Rủi ro vận hành/tuân thủ nếu citation sai dẫn đến quyết định sai.

## 5) Mục tiêu (định lượng – SMART)
- **Citation Accuracy**:
  - Exact (±0): ≥75%
  - Tolerant (±1): ≥90%
- **Coverage**: ≥98% câu trả lời có ≥1 citation hợp lệ.
- **Groundedness** (RAGAS/TruLens): ≥85%.
- **Latency p95**: <3 giây (không vision), <4.5 giây (khi bật vision chọn lọc).
- **Stability**: độ lệch chuẩn <5% qua 3 lần chạy.
- **Observability**: có log đầy đủ retrieval→rerank→LLM→validate theo từng câu hỏi.

## 6) Phạm vi / Ngoài phạm vi
- Trong phạm vi: Nghiên cứu kiến trúc, chỉ số, kịch bản đánh giá, lựa chọn phương án.
- Ngoài phạm vi (giai đoạn này): Chỉnh sửa mã nguồn/triển khai (sẽ đề xuất ở roadmap, nhưng không thực hiện ngay).

## 7) Ràng buộc & Thực tế hệ thống
- Pipeline hiện có: BM25 + FAISS, LLM giải đáp, validator cơ bản; có `text_by_page.jsonl`, chưa bật page-level reranking.
- Hỗ trợ vision render (khi cần).
- Yêu cầu có thể cần cân bằng giữa độ chính xác và độ trễ.

## 8) Phương pháp đánh giá (không can thiệp code)
- **Dataset**: 20–50 câu hỏi có nhãn (doc_id + page + quote), bao phủ bảng/hình, VI/EN.
- **Metrics**: exact, ±1, coverage, groundedness, latency, stability.
- **Quy trình**: chạy mỗi truy vấn 3 lần, trung bình; log chi tiết; tổng hợp JSON + báo cáo MD với phân tích top lỗi.
- **Gate chấp nhận**: exact ≥75% AND (±1) ≥90%, coverage ≥98%, groundedness ≥85%.

## 9) Dữ kiện & Bằng chứng
- `reports/CITATION_INVESTIGATION_FINAL_REPORT.md` – Phân tích gốc: lỗi tập trung ở chọn trang.
- `reports/test_results/page_flow_trace_*.json` – Cho thấy **đúng tài liệu** nhưng **không có trang đúng** trong các chunks được gửi vào LLM; hoặc có nhiều trang trộn lẫn.
- `reports/test_results/index_coverage_audit.json` – Kiểm tra phủ trang trong index; xác minh tài liệu có mặt trong corpus.

## 10) Các hướng giải pháp (để bạn tự cân nhắc)
- **Phương án A – Page‑First RAG (khuyến nghị)**:
  - Xây page index (BM25 + embeddings), rerank bằng cross‑encoder ở cấp trang; structured citations; CiteFix ±2..4 + NLI nhẹ; vision theo nhu cầu.
  - Kỳ vọng: 70–85% exact; 85–92% (±1); groundedness ≥85%; p95 <3s.
- **Phương án B – Late‑Interaction (ColBERT/SPLADE)**:
  - Tăng precision ở cấp đoạn → gom theo trang → rerank/verify như A.
  - Kỳ vọng: 75–88% exact; 88–94% (±1) nhưng chi phí/độ trễ cao hơn.
- **Phương án C – Managed Grounded Generation (Vectara/Vespa/Elastic)**:
  - Thời gian triển khai nhanh, built‑in citations/quotes; thêm lớp verify nhẹ.
  - Kỳ vọng: 80–90% tùy domain; đối mặt lock‑in/chi phí.

## 11) Rủi ro & Giảm thiểu
- **Mismatch extractor** (OCR/markdown): thống nhất extractor cho `text_by_page` và nội dung đưa vào LLM.
- **Chi phí rerank/NLI**: dùng mô hình nhẹ (MiniLM), cache/batch, giới hạn top‑K.
- **Độ trễ**: tách cấu hình fast/accurate; cho phép fallback.
- **Drift dữ liệu**: theo dõi quality & refresh gold set định kỳ.

## 12) Tiêu chí chọn phương án
- Ưu tiên **tính kiểm soát + on‑prem** → nghiêng về Phương án A.
- Ưu tiên **exact‑only ≥85%** và có GPU → cân nhắc Phương án B.
- Ưu tiên **time‑to‑value** → cân nhắc Phương án C.

## 13) Kế hoạch tiếp theo (no‑code)
- D1–D3: Chuẩn hóa bộ tiêu chí + hoàn thiện gold set 20–50 câu; xác nhận rubric.
- D4–D5: Đặc tả chi tiết 3 phương án (chỉ mục, rerank, verify, structured output).
- D6: Thiết kế A/B blueprint, ma trận bật/tắt (cross‑encoder, NLI, neighbor…).
- D7: Tổng hợp báo cáo so sánh & đề xuất kiến trúc chọn.

---

Tài liệu này mô tả rõ vấn đề, mục tiêu và khung đánh giá. Bạn có thể dựa vào đây để tự nghiên cứu thêm và lựa chọn phương án triển khai phù hợp với ràng buộc hạ tầng, chi phí và mục tiêu chất lượng của hệ thống.
