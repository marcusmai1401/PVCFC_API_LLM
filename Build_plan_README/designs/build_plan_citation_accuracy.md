# BUILD PLAN – NÂNG ĐỘ CHÍNH XÁC TRÍCH DẪN (CITATION) CHO PVCFC_API_LLM

> Mục tiêu: loại bỏ lỗi “đáp án đúng nhưng trích dẫn sai trang”, tiến tới **trích dẫn có cấu trúc**, **xác thực hậu kiểm**, và **vision theo vùng bằng chứng (bbox)**. Tài liệu này viết để **AI Agent** có thể thực thi tuần tự.

---

## 0) BỐI CẢNH & VẤN ĐỀ
- Hiện tại đường **Text-only** và **Vision** dùng **hai không gian nhãn [Doc N]** khác nhau; extractor ở Vision map toàn bộ citation theo **vision_doc_mapping** ⇒ dễ lẫn sang **trang ảnh không chứa nội dung** (ví dụ trang bìa 1238).
- Thuật toán chọn trang ảnh Vision dùng heuristic **center-of-range** ±2, chưa lọc **trang rỗng/bìa**; **không có hậu kiểm** đảm bảo nội dung trang chứa claim.

---

## ADDENDUM v1.1 – Điều chỉnh theo feedback (không dùng golden set giai đoạn đầu)

**Mục đích**: Nâng độ chính xác trích dẫn sớm hơn, giảm rủi ro lệch trang; triển khai được ngay **không cần golden set**.

### A) Bổ sung bước **Claim Extraction** (tách câu trả lời thành các mệnh đề sự thật)
- Thêm module `claims.py` để tách answer → danh sách claims (numerical/categorical/procedural).
- Mỗi claim sẽ được **attribution riêng** (map sang 1..N citations). Điều này tránh “pha loãng” điểm khi answer dài.

### B) **Groundedness Check** đưa lên **P1** (không đợi P3)
- Sau CiteFix-lite, chạy **entailment nhẹ** (NLI) cho từng claim với `page_text`.
- Nếu entailment < ngưỡng (mặc định 0.5), hạ confidence hoặc thử dịch sang trang lân cận.

### C) **Smart Vision Strategy** (bbox-first, skip khi không cần)
- Với `evidence_type = table/figure`: ưu tiên **crop theo bbox**; nếu chưa có, `find_bbox_by_quote()`.
- Với trích dẫn text ngắn (`quote < 200 chars`): **bỏ qua Vision** để tiết kiệm latency.

### D) **OCR/Page Index Validation** (nhẹ, tự động)
- Trong `tools/build_page_index.py`, **lấy mẫu 5 trang/tài liệu**: OCR kép (engine phụ nếu có) → cảnh báo mismatch; log để review sau.

### E) **Confidence Calibration – no-golden-set mode**
- Tạm thời dùng **sigmoid transform** trên điểm tổng hợp (lexical/semantic/entailment) thay cho baseline cố định; calibration học máy sẽ bật khi có golden set.

### F) **No-Golden-Set Evaluation (tạm)**
- Dùng **proxy metrics** tự động: (1) Groundedness ≥ 85% (NLI), (2) Citation Coverage ≥ 98%, (3) Page Distance ≤ 1 (sau CiteFix), (4) Vision-Need Ratio (tỉ lệ case cần/bật Vision) & Skip-Rate.

---

## 1) MỤC TIÊU & CHỈ SỐ THÀNH CÔNG (KPI)
- **Citation Correctness (proxy) ≥ 90%**: một citation được coi là đúng nếu (a) entailment ≥ 0.5 **và** (b) lexical match ≥ 0.5 trên đúng `doc_id + page` sau hậu kiểm. (Khi có golden set, thay bằng đo có giám định.)
- **Answer Faithfulness ≥ 85%** (RAGAS/Groundedness proxy): mọi claim đều được page-text ủng hộ.
- **Citation Coverage ≥ 98%**: hầu như mọi fact đều có citation.
- **Vision-grounded (khi bật) ≥ 80%**: bảng/hình có bbox hợp lệ.

---

## 2) PHẠM VI
### In scope
- Chuẩn hoá **đầu ra trích dẫn dạng JSON (structured citations)**.
- **Intra-document page rerank** (doc→page) để chọn đúng trang.
- **Post-validation (CiteFix-lite)**: lexical + semantic + entailment nhẹ để sửa page.
- **Vision theo trang & vùng (bbox)**.
- **Confidence** dựa trên điểm hậu kiểm thay vì cố định.
- Bộ **metric & test** kèm **gate** phát hành.

### Out of scope
- Thay đổi model LLM/embedding chính (trừ khi cần để hỗ trợ tool-calling/structured output).
- OCR/Parser nâng cao beyond baseline (có gợi ý, nhưng không bắt buộc ở P0).

---

## 3) KIẾN TRÚC GIẢI PHÁP (HIGH-LEVEL)
1) **Structured Output**: LLM trả về `{answer, citations:[{doc_id,page,quote?,bbox?,evidence_type}]}`; **không** dùng regex `[Doc i]`.
2) **Hybrid Retrieval** (BM25 ∪ FAISS) → **Rerank** (cross-encoder) ở cấp **passage**.
3) **Intra-doc Page Rerank**: với mỗi doc được chọn, chấm **toàn bộ trang** (hoặc vùng lân cận) để lấy **trang vàng**.
4) **Post-Validation (CiteFix-lite)**: so khớp claim ↔ page_text; nếu điểm thấp, quét ±2 trang lân cận để **tự sửa page** và tính **confidence**.
5) **Vision**: render **đúng trang** đã xác nhận; nếu có **bbox**, highlight; nếu không, trích **quote** rồi tìm **bbox** bằng text search/PyMuPDF.
6) **Metrics & Gate**: log, dashboard, và ngưỡng chặn release.

Sơ đồ khối (mô tả):
```
Query → Retrieval (BM25 ∪ Vector) → Rerank → Candidate Docs
            ↓
   Intra-doc Page Rerank → Best Page(s)
            ↓
   LLM (Structured Output: JSON citations)
            ↓
 Post-Validation (CiteFix-lite: fix page + confidence)
            ↓
 Vision Render (page/bbox) + UI highlight
            ↓
  Response (answer + citations JSON + confidence)
```

---

## 4) THAY ĐỔI KIỆN TẠO DỮ LIỆU (DATA ARTIFACTS)
- **text_by_page.jsonl** (mới): `{doc_id, page, text}` để hậu kiểm & page-rerank.
- **page_index** (mới): chỉ mục cấp **trang** (lexical/semantic) cho intra-doc rerank (có thể build on-the-fly từ chunks hoặc dựng riêng khi ingest).
- **doc_id_map.json** (đang có): cần đảm bảo map **doc_id → pdf_path**.
- **bbox_store.jsonl** (tuỳ chọn P2+): `{doc_id, page, spans:[{text, bbox}...]}` nếu parser hỗ trợ layout.

---

## 5) THIẾT KẾ API/SCHEMA & PROMPT
### 5.1 Schema Structured Citations (bắt buộc)
```json
{
  "answer": "string",
  "citations": [
    {
      "doc_id": "string",
      "page": 123,
      "quote": "optional exact snippet",
      "bbox": [x1, y1, x2, y2],
      "evidence_type": "text|table|figure",
      "confidence": 0.0
    }
  ]
}
```
- **Bắt buộc**: `doc_id`, `page`.
- **Khuyến nghị**: `quote` khi trích số liệu/cụm kỹ thuật.
- `bbox` optional (P2+). `confidence` được **thuật toán** điền (không yêu cầu LLM).

### 5.2 Prompt (tool-calling / structured outputs)
- Chỉ trả **JSON đúng schema**; mọi fact cần citation. Nếu chưa chắc `page`, vẫn trả `doc_id` + `quote` để hệ thống tự xác minh.

Ghi chú JSON mode (Gemini 2.5):
- Structured output/JSON mode hiện là tính năng chính thức. Nên ép JSON bằng `response_mime_type: "application/json"` kết hợp `response_schema` (GenAI SDK).
- Không kết hợp JSON mode và function/tool calling trong cùng một request với các model dòng 2.5; thường gặp lỗi: `INVALID_ARGUMENT: Function calling with a response mime type: 'application/json' is unsupported`.
- Nếu cần tool calling và vẫn muốn output cuối cùng là JSON chuẩn: chạy 2 bước (a) call có tools để lấy kết quả → (b) call riêng ở JSON mode (không tools) để chuẩn hoá theo schema.
- Khuyến nghị migrate sang `google-genai` SDK mới (thay vì thư viện cũ) để dùng structured output ổn định.

### 5.3 Claim Extraction & Per-Claim Attribution (mới)
- **LLM tách claims** từ answer → mảng `claims[]` (id, text, type, keywords).
- **Ràng buộc**: mỗi claim phải có ≥1 citation. Hậu kiểm & confidence tính **theo claim**, sau đó tổng hợp lên cấp câu trả lời.

---

## 6) THAY ĐỔI MÃ NGUỒN (MODULE LEVEL)
### 6.0 app/rag/claims.py (mới)
- `extract_factual_claims(answer) -> List[Claim]`
- Phân loại claim: numerical/categorical/procedural + trích `keywords` (đơn vị, tham số kỹ thuật…)

### 6.1 app/rag/generator.py
- **Thêm**: `StructuredCitationModel` + `StructuredAnswer` (có `claims[]`).
- **Sửa**: bỏ regex; parse JSON; enforce mỗi claim phải có citation.
- **Thêm**: `post_validate_citations()` (theo claim) + `compute_confidence()` (sigmoid, chưa calibration học máy).

### 6.2 app/api/routers/ask.py
- Wire structured output → hậu kiểm → attach `pdf_path`/`bbox` → response.
- **Không** auto-chèn trang 1; thiếu `page` → chạy CiteFix-lite.

### 6.3 app/rag/page_reranker.py (mới)
- `rank_pages_for_doc(query|claim, doc_id)`; 2–3 tầng: lexical → semantic → (tuỳ chọn) entailment nhẹ.

### 6.4 tools/build_page_index.py (mới/đã mở rộng)
- Sinh `text_by_page.jsonl`; **validate OCR** (lấy mẫu), log mismatch.

### 6.5 app/vision/renderer.py (mở rộng)
- `render_page`, `render_bbox`, `find_bbox_by_quote` (PyMuPDF/text search).
- `smart_vision_strategy(citation, page_content)` để **skip** khi text-only.

### 6.6 NLI/Entailment (mới)
- Tích hợp model nhẹ (khuyến nghị: MiniLM-L6-v2). Cho phép cấu hình `NLI_MODEL=mini|deberta`.

### 6.7 Cấu hình (.env / settings)
- `STRUCTURED_OUTPUT=on|off`, `PAGE_RERANK_TOPK=20`, `CITEFIX_NEIGHBOR=2`, `VISION_BBOX=on|off`, `NLI_MODEL=mini`.

### 6.8 SDK Requirements (Gemini JSON mode)
- Runtime/Packages:
  - `google-genai >= 1.36.0` (bắt buộc để dùng `response_mime_type` + `response_schema`; đồng thời API `types.Part(text=...)` thay thế `from_text()` như đã sửa trong generator.py).
  - Không dùng thư viện cũ `google.generativeai` song song. Khuyến nghị migrate theo hướng dẫn “Migrate to the Google GenAI SDK”.
- Giới hạn quan trọng (model 2.5):
  - Không kết hợp `response_mime_type='application/json'` với function/tool calling trong cùng 1 request (thường lỗi `INVALID_ARGUMENT`). Nếu cần tools, tách 2 bước: (a) gọi tools, (b) gọi riêng JSON mode để chuẩn hoá schema.
- Ví dụ cấu hình gọi JSON mode với schema citations:
```python path=null start=null
from google import genai
from google.genai import types

client = genai.Client(api_key=API_KEY)

citation_item = types.Schema(
    type="OBJECT",
    properties={
        "doc_id": types.Schema(type="STRING"),
        "page": types.Schema(type="INTEGER"),
        "quote": types.Schema(type="STRING", nullable=True),
        "bbox": types.Schema(type="ARRAY", items=types.Schema(type="NUMBER"), nullable=True),
        "evidence_type": types.Schema(type="STRING", enum=["text", "table", "figure"], nullable=True),
    },
    required=["doc_id", "page"],
)

schema = types.Schema(
    type="OBJECT",
    properties={
        "answer": types.Schema(type="STRING"),
        "citations": types.Schema(type="ARRAY", items=citation_item),
    },
    required=["answer", "citations"],
)

cfg = types.GenerateContentConfig(
    response_mime_type="application/json",
    response_schema=schema,
    temperature=0.2,
)

resp = client.models.generate_content(
    model="models/gemini-2.5-flash",
    contents=[types.Content(role="user", parts=[types.Part(text="...prompt...")])],
    config=cfg,
)
# resp.text sẽ là JSON hợp lệ theo schema
```

### 6.9 Checklist nâng cấp SDK (khuyến nghị)
1. Gỡ bản cũ (nếu đang dùng):
```bash path=null start=null
pip uninstall -y google-generativeai
```
2. Cài đặt/ghi phiên bản tối thiểu:
```bash path=null start=null
pip install -U google-genai>=1.36.0
```
3. Rà soát import & API thay đổi:
- Thay `from google import generativeai as genai` → `from google import genai`.
- Sử dụng `from google.genai import types` thay cho `generativeai.types`.
- Phần tạo content: dùng `types.Part(text=...)` thay cho `types.Part.from_text()`.
- Cấu hình JSON mode: bổ sung `GenerateContentConfig(response_mime_type, response_schema)`.
4. Smoke test JSON mode:
```python path=null start=null
from google import genai
from google.genai import types

client = genai.Client(api_key=API_KEY)

schema = types.Schema(type="OBJECT", properties={"ok": types.Schema(type="BOOLEAN")}, required=["ok"])
cfg = types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema)

resp = client.models.generate_content(
    model="models/gemini-2.5-flash",
    contents=[types.Content(role="user", parts=[types.Part(text="Return {\"ok\": true}")])],
    config=cfg,
)
assert resp.text.strip() == '{"ok": true}'
print("JSON mode OK")
```
5. Kiểm tra các call có tool/function calling:
- Nếu đang dùng tools, đảm bảo tách 2 bước như đã nêu.
6. Cập nhật tài liệu nội bộ & CI:
- Ghi rõ phiên bản tối thiểu `google-genai` và test smoke bắt buộc.

---

## 7) THUẬT TOÁN CHI TIẾT
### 7.1 Intra-Document Page Rerank
```
Input: query, doc_id
1) Lấy tất cả page của doc_id (hoặc topK page từ page_index lexical).
2) Tính điểm lexical (BM25) → chọn topK1.
3) Cross-encoder rerank trên topK1 → chọn topK2 (ví dụ 5 trang).
4) Trả danh sách [(page, score)] theo thứ tự giảm dần.
```

### 7.2 Post-Validation (CiteFix-lite)
```
Input: citations[], text_by_page, neighbor=2
For each citation c:
  p0 = c.page
  S0 = score(page(p0))
  For p in [p0-neighbor .. p0+neighbor]:
     Sp = score(page(p))
     keep best p* with highest Sp
  If p* != p0 or S0 < threshold:
     c.page = p*
  c.confidence = f(Sp_lexical, Sp_semantic, Sp_entailment)
```
**score(page)** = `α·lexical_match + β·embedding_similarity + γ·entailment_prob`.
- `lexical_match`: tỉ lệ từ khoá/số-đơn-vị trong answer/quote xuất hiện ở page.
- `embedding_similarity`: cosine giữa (answer/quote) và page_text.
- `entailment_prob`: xác suất “page_text ⇒ claim” từ cross-encoder nhẹ (tuỳ chọn P1+).
- Khuyến nghị: `α=0.5, β=0.3, γ=0.2` (tinh chỉnh sau A/B).

### 7.3 Vision (bbox-first khi có)
```
If evidence_type ∈ {table, figure} or quote length > L:
   Use render_page(doc_id, page)
   If bbox provided → render_bbox()
   Else bbox := find_bbox_by_quote()
   Attach bbox to citation
```
- Nếu dùng Vision chỉ để “làm đẹp”, **tắt** khi không cần; ưu tiên bật khi chứng cứ là bảng/hình.

### 7.4 Confidence
```
confidence = clamp(w1*rerank_score + w2*lexical + w3*entailment)
```
- Loại bỏ `confidence=1.0` cứng cho Vision.

---

## 8) KẾ HOẠCH THỰC THI THEO PHA (cập nhật – no-golden-set mode)
### P0 – Structured + Claims (2–3 ngày)
- [ ] Bật **structured citations**; thêm `claims[]`.
- [ ] Gỡ regex; enforce claim→citation.
- [ ] Unit tests: malformed JSON, claim without citation ⇒ fail.
- **Acceptance**: Coverage ≥ 98%, proxy groundedness ≥ 80%.

### P1 – Page Rerank + CiteFix-lite + Groundedness (3–5 ngày)
- [ ] `text_by_page.jsonl` + page_index.
- [ ] `rank_pages_for_doc()`; hậu kiểm per-claim (lexical+semantic+entailment).
- [ ] Confidence = sigmoid(score tổng hợp). Log thêm `page_distance`.
- **Acceptance**: Citation Correctness (proxy) ≥ 85%, Groundedness ≥ 85%.

### P2 – Smart Vision (bbox-first, skip) (3–6 ngày)
- [ ] Render đúng trang; crop bbox nếu có/đoán được; skip vision khi text-only.
- [ ] UI highlight bbox.
- **Acceptance**: Vision cases ≥ 80% bbox hợp lệ; P95 < 2500ms.

### P3 – Calibration & Tối ưu (2–3 ngày, **sau** khi có golden set)
- [ ] Huấn luyện calibrator (Platt/Isotonic) trên labeled data.
- [ ] A/B test.
- **Acceptance**: Citation Correctness ≥ 90% (proxy→labelled khi có), Groundedness ≥ 85%.

---

## 9) KẾ HOẠCH KIỂM THỬ
### Unit tests
- Parse structured JSON (happy/edge/repair).
- Page-rerank: cho query tổng hợp → trang đúng đứng top.
- CiteFix: case lệch trang → được sửa về trang chứa quote.

### Integration/E2E
- Pipeline `POST /api/ask` với 10–20 câu hỏi gold: assert `doc_id/page` đúng, `confidence` ≥ ngưỡng.
- Vision bật/tắt; case bảng có bbox.

### Regression & Perf
- Giữ tập câu hỏi baseline; đo latency, memory.

---

## 10) QUẢN TRỊ RỦI RO & GIẢM THIỂU
- **JSON không đúng schema**: bật chế độ **structured outputs** (tool-calling) + auto-repair 1 lần.
- **Thiếu text_by_page**: fallback OCR nhanh; log cảnh báo; loại tài liệu khỏi page-rerank nếu rỗng.
- **Latency tăng**: đặt `MAX_LATENCY_BUDGET_MS`; giảm topK trong page-rerank; tắt entailment nếu vượt ngưỡng.
- **BBox sai**: nếu không tìm thấy bbox, vẫn trả page + quote, không chặn response.

---

## 11) GÓI CÔNG VIỆC CHO AI AGENT (WBS)
1) **Refactor Structured Citations**
   - Tạo `schemas/citation.py` (pydantic models).
   - Sửa `generator.py` để gọi LLM ở chế độ structured; parse JSON; remove regex.
   - Sửa `ask.py` để trả `citations[]` + `pdf_path`.
2) **Page Index & Intra-doc Rerank**
   - Viết `tools/build_page_index.py` → tạo `text_by_page.jsonl`.
   - Viết `app/rag/page_reranker.py` + tests.
   - Gắn vào pipeline sau doc-rerank.
3) **CiteFix-lite & Confidence**
   - Viết `post_validate_citations()` + `compute_confidence()`.
   - Hook vào `generator.py` workflow.
4) **Vision BBox**
   - Viết `app/vision/renderer.py` (render_page, render_bbox, find_bbox_by_quote).
   - Sửa UI endpoint trả bbox overlay data.
5) **Metrics & Gate**
   - Tạo `GET /metrics` (RAGAS/Groundedness/Citation Correctness).
   - Viết script chấm bộ gold; tạo báo cáo Markdown.

---

## 12) DELIVERABLES & ACCEPTANCE CRITERIA
- **Code**: PR chứa 4 module mới/sửa; test coverage ≥ 70% cho phần citation.
- **Artifacts**: `text_by_page.jsonl`, `page_index/`, cập nhật `doc_id_map.json` nếu cần.
- **Docs**: README cập nhật; tài liệu hướng dẫn bật structured outputs & vision bbox.
- **Kết quả đánh giá**: bảng KPI trước/sau (golden set ≥ 20 câu), đạt ngưỡng ở Mục 1.

---

## 13) TIMELINE GỢI Ý (cập nhật)
- Tuần 1: P0 + khởi động P1 (page_index).
- Tuần 2: Hoàn tất P1; bắt đầu P2 (smart vision).
- Tuần 3: Ổn định P2, tinh chỉnh threshold; chuẩn bị P3 (calibration – đợi golden set).


---

## 14) PHỤ LỤC) PHỤ LỤC
### 14.1 Ví dụ Request/Response `/api/ask`
**Request**
```json
{
  "query": "Momen thiết kế yêu cầu của trục K-06101 là bao nhiêu?",
  "language": "vi",
  "enable_vision_generation": true
}
```
**Response (rút gọn)**
```json
{
  "answer": "Momen thiết kế là 1420 Nm...",
  "citations": [
    {
      "doc_id": "K06101_INSTALL_2021",
      "page": 15,
      "quote": "Design torque ... 1420 Nm",
      "bbox": [120, 340, 520, 390],
      "evidence_type": "table",
      "confidence": 0.87
    }
  ]
}
```

### 14.2 Pseudo-code `post_validate_citations`
```
for c in citations:
  kws = extract_numbers_units(answer + c.quote)
  p0 = c.page
  S0 = lexical(page[p0], kws) * 0.5 + cosine(answer, page[p0]) * 0.3 + entail(page[p0], answer) * 0.2
  best = (p0, S0)
  for q in neighbors(p0, ±2):
    Sq = lexical(page[q], kws)*0.5 + cosine(answer, page[q])*0.3 + entail(page[q], answer)*0.2
    if Sq > best.S: best = (q, Sq)
  c.page = best.page
  c.confidence = clamp(0.4 + best.S)
```

### 14.3 Gợi ý cấu hình
```
STRUCTURED_OUTPUT=on
PAGE_RERANK_TOPK=20
CITEFIX_NEIGHBOR=2
VISION_BBOX=on
MAX_LATENCY_BUDGET_MS=1800
```
