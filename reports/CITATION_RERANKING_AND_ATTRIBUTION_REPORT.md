# Báo cáo kỹ thuật: Hiện trạng Citation sai, nguyên nhân nghi ngờ, đề xuất khắc phục và “Lấy ở đâu thì trích nguồn ở đó”

Ngày: 2025-10-09
Ngữ cảnh hệ thống (rút từ logs hiện tại):
- LLM provider: Gemini
- Generation models: gemini-2.5-pro (heavy), gemini-2.5-flash (light)
- Embedding model: gemini-embedding-001 (models/embedding-001), 768 chiều
- Chỉ mục: BM25 + FAISS (dim=768)
- Reranker: cross-encoder/ms-marco-MiniLM-L-6-v2
- Vision: Reorder trang ảnh dựa trên (retrieval_score × 10) + keyword overlap

---

## 1) Vấn đề hiện tại

- Người dùng nhận được câu trả lời có nội dung đúng (ví dụ các giá trị: 79.5 BAR.A, 50.0 °C, 43.40) nhưng phần “References” trỏ về tài liệu không chứa thông tin đó (ví dụ TURBINE PDF thay vì CO2 COMPRESSOR PDF).
- Khi mở PDF từ References, trang không có dữ liệu liên quan; trong khi file đúng (CO2 compressor datasheet, trang 3) thực sự tồn tại trong index và chứa đáp án.
- Tình huống gây mất niềm tin: “Answer đúng tuyệt đối” nhưng “Citation sai hoàn toàn”.

Hệ quả:
- Người dùng nghi ngờ độ tin cậy của hệ thống.
- Không thể dùng câu trả lời để audit/tuân thủ vì không lần theo nguồn được.

---

## 2) Nguyên nhân nghi ngờ (từ quan sát + logging)

Tóm lược chuỗi lệch tín hiệu trong pipeline:
1) BM25/FAISS retrieval xếp hạng sai miền: tài liệu TURBINE được chấm điểm cao hơn CO2 COMPRESSOR cho truy vấn về “CO2 compressor 4th stage”. Nguyên nhân chủ đạo: trùng từ vựng kỹ thuật (rated, stage, pressure, temperature, K06101…), embedding tổng quát chưa đủ đặc thù miền.
2) Reranker không đảo ngược được sai lệch: mô hình cross-encoder nhỏ, general-purpose, vẫn ưu tiên TURBINE do nhiều token khớp bề mặt.
3) Vision re-order khuếch đại sai lệch: điểm vision = retrieval_score × 10 + keywords → trang TURBINE trở thành [Doc 1..5], trang CO2 bị đẩy xuống [Doc 6..10]. “Bản đồ Doc” cho citation vì thế lệch.
4) LLM position/citation bias và hợp nhất đa nguồn: LLM có thể đọc đúng số liệu từ CO2 (Doc 6..10) hoặc từ parametric memory, nhưng khi chèn [Doc X] theo chỉ dẫn, nó có xu hướng chọn các Doc xuất hiện đầu (Doc 1), dẫn đến citation trỏ sai.

Kết luận bản chất: Không phải bug hiển thị; đây là sự cộng hưởng của: (a) tín hiệu retrieval chưa “ràng buộc miền”, (b) reranker chưa đủ mạnh miền kỹ thuật, (c) vision scoring tin tưởng mù quáng điểm retrieval, và (d) cơ chế citation hiện tại là “cam kết mềm” (không kèm con trỏ cứng đến span nguồn).

---

## 3) Đề xuất khắc phục (ưu tiên nâng cấp reranker, kèm ràng buộc miền)

Ưu tiên 1 — Nâng cấp reranker
- Lý do: Bạn đang dùng embedding tốt; điểm nghẽn là reranker general-purpose (L-6). Nâng cấp reranker sẽ cải thiện xếp hạng cuối cùng ngay cả khi retrieval còn nhiễu.
- Ứng viên đề xuất:
  - BGE Reranker (bge-reranker-large / bge-reranker-base): reranker SOTA thực dụng, mạnh với technical text.
  - cross-encoder/ms-marco-MiniLM-L-12-v2: biến thể lớn hơn, cải thiện ngữ nghĩa sâu.
  - Dịch vụ rerank thương mại (Cohere Rerank v3, Azure AI Search semantic ranker…): hiệu năng cao, ít phải vận hành, có chi phí API.
- Tiêu chí đánh giá: MRR@10, Recall@5/10, Citation Accuracy@Doc/Page trên bộ “golden questions”.

Ưu tiên 2 — Bổ sung ràng buộc miền (domain constraints) trước khi rerank
- Mục tiêu: Giảm nhiễu turbine/compressor từ gốc.
- Cách làm (kết hợp):
  - Phân vùng chỉ mục/collection theo miền (CO2_COMPRESSOR, TURBINE, P&ID…). Truy vấn “compressor” định tuyến mặc định vào collection compressor trước.
  - Lọc/ưu tiên theo metadata (đường dẫn/tên file/trường loại thiết bị): khi có tín hiệu “CO2/compressor”, tăng trọng số tài liệu trong thư mục CO2 COMPRESSOR; phạt TURBINE.
  - Phân loại intent (router): xác định loại thiết bị trong truy vấn rồi áp bộ lọc/collection tương ứng.
  - Trọng số trường (BM25 field weighting): ưu tiên field equipment_type, tag, unit, giảm text chung.
  - Từ điển miền/ontology: synonym (CO2/carbon dioxide), negative keywords (loại turbine khi hỏi compressor), chuẩn hóa đơn vị.

Ưu tiên 3 — Điều chỉnh vision re-order
- Mục tiêu: Tránh “nhân đôi” sai của retrieval.
- Hướng: Giảm/loại bỏ nhân hệ số theo retrieval_score; dùng keyword/intent match hoặc điểm reranker ở mức trang; có thể thêm kiểm chứng nhẹ (mini-rerank) bằng cross-encoder trên trích đoạn OCR trang.

Ưu tiên 4 — Quan trắc và thước đo
- Lập bộ “golden set” 25–50 câu hỏi then chốt (đã có ground-truth doc/page).
- Đo: Citation Accuracy@Doc, Citation Accuracy@Page, Evidence Coverage, Answer Factuality, Latency.
- Theo dõi drift theo thời gian, nhất là khi bổ sung tài liệu mới.

---

## 4) “Lấy ở đâu thì trích nguồn ở đó” — Ý tưởng và phương án thực thi

Mục tiêu: Mỗi con số/kết luận trong trả lời phải gắn được về đúng doc_id/page (và tốt nhất là có trích đoạn/ảnh minh họa). Có 4 con đường chính, tăng dần mức ràng buộc/độ tin cậy:

Phương án A — Evidence-first (tool-calling theo claim)
- Quy trình: LLM tách các “claim” (ví dụ 3 thông số: pressure, temperature, molecular weight) → gọi máy tìm bằng chứng cho từng claim → bắt buộc thu được {doc_id, page, excerpt} → sau đó mới được in câu trả lời kèm citation.
- Ưu: Ràng buộc nguồn theo claim ngay từ đầu; giảm nguy cơ “trả lời rồi mới điền [Doc 1]”.
- Nhược: Nhiều bước hơn, độ trễ tăng; cần thiết kế giao thức giữa LLM và công cụ tìm bằng chứng.
- Khi dùng vision: OCR trang trước để trích excerpt text gắn kèm page.

Phương án B — Structured output with evidence
- Quy trình: Buộc LLM trả về JSON có cấu trúc: mỗi mục gồm {field, value, unit, doc_id, page, excerpt/quote}. UI từ JSON này dựng ra câu + references.
- Ưu: Dễ kiểm thử/đánh giá; downstream (UI, báo cáo) tin cậy hơn.
- Nhược: Cần xử lý khi thiếu bằng chứng (fallback), và phải giám sát tính tuân thủ schema.

Phương án C — Post-hoc attribution (gán nguồn sau sinh)
- Quy trình: LLM sinh câu trả lời trước; hệ thống sau đó quét từng con số/cụm text trong câu trả lời, tìm khớp “tốt nhất” trong context (text/OCR) bằng exact/fuzzy + cross-encoder, rồi gán doc_id/page.
- Ưu: Không đổi nhiều hành vi sinh; dễ cắm thêm vào hệ thống hiện hữu.
- Nhược: Có thể gán nhầm nếu nhiều tài liệu chứa số giống nhau; cần ưu tiên “nguồn hiện diện trong context đã cung cấp”.

Phương án D — Extract-then-compose (Field Store/KB)
- Quy trình: Trước giờ trả lời, pipeline trích xuất các trường chuẩn (pressure/temperature/molecular weight/limitations…) từ tài liệu vào “bảng sự thật” kèm doc_id/page/quote. Khi trả lời, chỉ lấy từ bảng này, nên citation là cơ học và chính xác.
- Ưu: Độ tin cậy cao nhất, truy vết rõ ràng, phù hợp truy vấn thông số/kỹ thuật lặp lại.
- Nhược: Cần đầu tư ETL/chuẩn hóa dữ liệu; linh hoạt thấp hơn cho câu hỏi ngoài bộ trường; đổi lại chất lượng citation rất tốt với các thông số trọng tâm.

Khuyến nghị triển khai theo giai đoạn
- Ngắn hạn: C + (một phần) A
  - Bật post-hoc attribution cho số liệu/ký pháp đơn vị; nếu không tìm thấy bằng chứng trong context hiện tại → cảnh báo/giảm confidence; ưu tiên nguồn xuất hiện trong truy vấn hiện tại (đã retrieve/vision).
  - Với câu hỏi có cấu trúc (điền 3 thông số), áp dụng mini evidence-first: LLM liệt kê 3 trường và yêu cầu bằng chứng tối thiểu 1 snippet/field.
- Trung hạn: B
  - Chuẩn hóa đầu ra JSON kèm evidence cho các câu hỏi kỹ thuật; UI hiển thị trực tiếp từ JSON.
- Dài hạn: D
  - Xây dựng Field Store cho nhóm thông số hay được hỏi; đảm bảo “lấy ở đâu trích ở đó” mang tính cơ học và nhất quán.

Lưu ý quan trọng về “hợp nhất đa nguồn”
- Các mô hình multimodal (như Gemini) tự hợp nhất text + ảnh + tri thức tham số; bạn không cần “tự viết” thuật toán trộn. Tuy nhiên, để kiểm soát nguồn, cần điều phối quy trình (orchestration):
  - Sắp xếp input có trật tự, nêu rõ luật: “chỉ dùng thông tin có trong context/ảnh; nếu khẳng định số liệu phải kèm nguồn; nếu thiếu bằng chứng thì từ chối”.
  - Thêm bước gán/kiểm chứng nguồn (A/B/C/D) để khóa citation theo claim.

---

## Kế hoạch hành động đề xuất (không thay đổi lớn kiến trúc ban đầu)

Tuần 1–2 (nhanh/ít rủi ro)
- Thay/ràng buộc reranker: thử bge-reranker-base/large và cross-encoder L-12; chọn theo MRR@10 & Citation Accuracy.
- Bổ sung ràng buộc miền ở retrieval: prefilter theo collection/metadata; penalty cho thư mục TURBINE khi intent là compressor.
- Bật post-hoc attribution cho số liệu: nếu không tìm được span chứng chứng, đánh dấu citation “uncertain” thay vì gán đại Doc 1.

Tuần 3–4 (ổn định hóa)
- Chuẩn hóa structured output with evidence cho câu hỏi thông số.
- Điều chỉnh vision re-order để không nhân điểm retrieval; ưu tiên keyword/intent match + mini-rerank theo trang OCR.

Quý tiếp theo (bền vững)
- Xây Field Store/KB cho nhóm thông số lặp lại (pressure, temperature, MW, limits…); tích hợp vào pipeline trả lời.
- Mở rộng ontology miền; tinh chỉnh/ràng buộc negative keywords theo equipment type.

Chỉ số nghiệm thu
- Citation Accuracy@Doc ≥ 0.9; Citation Accuracy@Page ≥ 0.8 trên golden set.
- MRR@10 tăng ≥ 20% so với baseline hiện tại.
- “Unattributed claim” (claim không có bằng chứng) ≤ 5%.

---

## Kết luận

- Căn nguyên sự cố không nằm ở tầng hiển thị citation mà ở chuỗi tín hiệu xếp hạng và cơ chế citation “mềm”.
- Với embedding hiện tại đã tốt, nút thắt là reranker và ràng buộc miền. Nâng reranker + thêm domain constraints sẽ giải quyết phần lớn ca “chọn nhầm tài liệu nguồn”.
- Để đạt “lấy ở đâu thì trích nguồn ở đó” một cách tin cậy, cần bổ sung một trong các cơ chế attribution (post-hoc, evidence-first, structured evidence, hoặc Field Store). Đây là bước biến citation từ “cam kết mềm” thành “cam kết có bằng chứng”.
