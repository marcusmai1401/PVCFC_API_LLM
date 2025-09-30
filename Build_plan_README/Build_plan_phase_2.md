# PHASE 2 — RETRIEVAL & API (HYBRID + RERANK + VISION + CITATIONS)

Tài liệu pha 2 cho PVCFC RAG (V1). Mục tiêu: triển khai pipeline truy vấn trực tuyến với Hybrid Retrieval (BM25 + FAISS), Rerank (Cross-Encoder cho EN; score fallback cho VI), Generation (Gemini 2.5 Pro), và Vision page selector ưu tiên để chọn đúng trang/citation. Bảo đảm citations trang 1-based, RAM vận hành ≤ 12 GB, và telemetry/metrics đầy đủ.

---

## 1) Mục tiêu & Kết quả mong đợi

- Pipeline online hoàn chỉnh: QueryTransform → Hybrid Retrieval → Rerank → Generation → Citations.
- Vision ưu tiên: render ảnh trang on-demand + cache, chọn đúng trang trước khi sinh trả lời/citation.
- Citations bắt buộc (khi có bằng chứng) ở mức trang 1-based; nêu rõ “không đủ bằng chứng” khi thiếu nguồn.
- Degrade BM25-only khi embedding/mạng lỗi (không rebuild index); có log/meta nêu bật degrade.
- Telemetry/meta đầy đủ cho giám sát & debug; rate-limit & cache hợp lý.

---

## 2) Phạm vi & Không phạm vi

- Có (Phase 2):
  - Hybrid Retrieval (BM25 + FAISS); Rerank CE cho EN; VI fallback score/hybrid.
  - Generation (Gemini 2.5 Pro); QueryTransform/HyDE (Gemini 2.5 Flash) — routing nội bộ (tiers không lộ UI).
  - Vision page selector (on-demand render + cache; max 10 trang; 1-based).
  - Endpoints: `/ask`, `/locate`, `/report`; telemetry/meta; rate-limit & cache.
- Không (để pha sau/ngoài V1):
  - Bbox bắt buộc; overlay bbox bắt buộc; pre-render toàn bộ ảnh trang; normalized PDF; IVF-PQ/Lucene (đưa vào roadmap).

---

## 3) Luồng xử lý truy vấn (end-to-end)

1) Query Transform (Flash)
   - Chuẩn hoá truy vấn (lower/casefold, strip, nhẹ nhàng với từ kỹ thuật), chuẩn hóa ngôn ngữ.
   - HyDE (tùy chọn): sinh 1–2 biến thể ngắn để tăng recall vector.

2) Hybrid Retrieval
   - BM25 và FAISS chạy song song.
   - Hợp nhất (RRF hoặc score fusion nội bộ) → tập ứng viên.

3) Rerank
   - Cross-Encoder (EN) để tinh lọc; với VI dùng score-based/hybrid fallback nếu CE không phù hợp hoặc gây NaN.
   - Chọn TOP_RERANK theo ENV, rồi lấy FINAL_CONTEXT_K (MAX_CONTEXT) cho bước sinh.

4) Vision Page Selector (mặc định ON)
   - Dựa trên tập ứng viên (và doc_id_map) → xây danh sách (pdf_path, page) để render on-demand.
   - Vision (Gemini 2.5 Pro) dùng context văn bản + ảnh trang để tăng độ chính xác/citation.

5) Generation (Pro)
   - Sinh câu trả lời theo ngôn ngữ truy vấn; giữ nguyên giá trị/đơn vị.
   - Không bịa: nếu thiếu nguồn → nêu “không đủ bằng chứng”.

6) Citations & Response
   - Trả citations 1-based (doc_id, page, pdf_path? nếu có map); UI render footnote.
   - Meta/telemetry đầy đủ: model routing, flags, degrade, timing_by_stage, cache_hit.

---

## 4) Cấu trúc module (tham chiếu code hiện có)

- `app/rag/query_transform.py` — chuẩn hoá; HyDE (tùy chọn); ngôn ngữ.
- `app/rag/retriever.py` — BM25 + FAISS; hợp nhất.
- `app/rag/reranker.py` — CE EN; VI fallback score/hybrid; TOP_RERANK.
- `app/rag/generator.py` — Generation (Pro), Vision page selector, citations, meta.
- `app/rag/cove.py` — (tùy chọn) Chain-of-Verification nhẹ (text-only), không áp dụng riêng cho Vision.
- `app/api/routers/{ask, locate, report}.py` — API endpoints; xây response meta/telemetry.
- `app/core/{rate_limit, metrics, tracing}.py` — rate-limit, Prometheus/OTel, tracing.
- `app/services/{llm, llm_client}.py` — routing model tiers nội bộ; timeouts/retry.

Ghi chú: Tiers (heavy/light) **chỉ** dùng nội bộ cho routing theo tác vụ, **không lộ** ra UI.

---

## 5) Routing nội bộ & ENV mapping

- Generation → `LLM_MODEL_HEAVY=gemini-2.5-pro` (Vision + text generation).
- Query Transform / HyDE / paraphrase → `LLM_MODEL_LIGHT=gemini-2.5-flash`.
- Embedding duy nhất V1: `EMBEDDING_MODEL=gemini-embedding-001` (ingest & query). Cho phép override, nhưng default & khuyến nghị là model này.

ENV tham chiếu chính:
- `MAX_CONTEXT=8` (FINAL_CONTEXT_K) — số đoạn vào step sinh.
- `TOP_RERANK=20` — số ứng viên CE trước khi chọn MAX_CONTEXT.
- `VISION_PAGE_SELECTOR_ENABLED=true` — bật Vision page selector.
- `TEXT_RANGE_SCAN_ENABLED=false` — tắt page-range scanning text-only (debug mới bật).

---

## 6) Retrieval & Rerank (defaults)

- BM25 + FAISS chạy song song; hợp nhất → TOP_RERANK theo ENV.
- Rerank CE EN; fallback VI dùng score/hybrid khi CE không phù hợp/ổn định.
- Lấy MAX_CONTEXT đoạn tốt nhất cho bước sinh; giữ thăng bằng giữa coverage & độ chính xác.

---

## 7) Vision page selector (mặc định ON)

- Điều kiện: có ứng viên từ retrieval + có map `doc_id → pdf_path` trong `doc_id_map.json`.
- Chọn trang:
  - Nếu metadata có **cả** `page_start` và `page_end` (non-None) → lấy **full range**; nếu start > end thì swap.
  - Nếu chỉ có `page` → **cửa sổ ±2** (start = max(1, page-2), end = page+2).
  - **Clamp** theo tổng số trang PDF (nếu biết); **tối đa 10 trang**;
  - 1-based; **dedup theo (pdf_path, page)**; bảo toàn thứ tự ưu tiên theo xếp hạng tài liệu.
- Render ảnh trang **on-demand + cache** (ví dụ `artifacts\cache\pdf_pages`), **không pre-render** toàn bộ.
- Khi Vision thành công: meta chứa `vision_generation.pages_used`, `pages_failed`, và danh sách trang.

---

## 8) Degrade BM25-only (khi embedding/mạng lỗi)

- Cho phép fallback: `RETRIEVAL_ALLOW_BM25_ONLY_FALLBACK=true`.
- Khi lỗi embedding/network/quota/timeouts:
  - Bật `meta.degrade_mode=true`, đặt `meta.degrade_reason` (network_error|embedding_timeout|quota|…).
  - **Tăng k BM25** và **TOP_RERANK** tạm thời:
    - `BM25_K_WHEN_DEGRADE=80`
    - `RERANK_TOP_N_WHEN_DEGRADE=50`
- Không rebuild index; pipeline tiếp tục trả lời (chất lượng giảm nhẹ nhưng không gián đoạn).

---

## 9) API Endpoints (Schema & Ví dụ)

### 9.1 POST `/ask`

- Request (JSON, rút gọn):
```json
{
  "query": "Áp suất vận hành tối đa của KT06101?",
  "filters": {"doc_id": ["PVCFC-KT06101-datasheet-v1"]},
  "hyde": true,
  "max_context": 8,
  "language": "vi",
  "enable_vision_generation": true
}
```

- Response (JSON, rút gọn):
```json
{
  "answer": "...",
  "citations": [
    {"doc_id": "DOCID_abc123", "page": 12, "bbox": null, "confidence": 0.95, "pdf_path": "D:\\...\\manual.pdf"}
  ],
  "context_used": ["chunk_abc123", "chunk_def456"],
  "confidence": 0.82,
  "meta": {
    "latency_ms": 1430,
    "breakdown": {"transform_ms": 120, "retrieve_ms": 450, "rerank_ms": 280, "generate_ms": 580},
    "k": 8,
    "execution_mode": "production",
    "trace_id": "xyz789",

    "model_generation": "gemini-2.5-pro",
    "model_query_transform": "gemini-2.5-flash",
    "embed_model": "gemini-embedding-001",

    "degrade_mode": false,
    "bm25_k_current": 50,
    "top_rerank_current": 20,

    "vision_page_selector_enabled": true,
    "text_range_scan_enabled": false,

    "vision_generation": {
      "pages_used": [{"pdf_path": "D:\\...\\manual.pdf", "page": 12}],
      "pages_failed": [],
      "excerpts": []
    }
  },
  "warnings": null
}
```

- Ràng buộc:
  - Citations 1-based; nếu thiếu nguồn → trả lời “không đủ bằng chứng”.
  - UI sẽ tự render footnote `[n] {doc_id}; p.{page}` từ mảng `citations[]`.

### 9.2 POST `/locate`

- Dùng khi người dùng thật sự hỏi “ở đâu/trang nào”. Trả `hits[]` với `doc_id`, `page` 1-based, `bbox?`, `snippet`, `score`.

### 9.3 POST `/report`

- Sinh markdown tóm tắt có citations ở cuối; không cần Vision riêng.

---

## 10) Telemetry / Meta bắt buộc

- Ghi vào `meta` và logs mỗi request:
  - `model_generation`, `model_query_transform`, `embed_model`;
  - `degrade_mode` (bool), `degrade_reason` (string?);
  - `bm25_k_current`, `top_rerank_current`;
  - `vision_page_selector_enabled`, `text_range_scan_enabled`;
  - `timing_by_stage` (transform/retrieve/rerank/generate), `cache_hit`.
- Không log secrets; mask Authorization/api_key; giới hạn snippet dài.

---

## 11) Rate-limit & Cache

- Rate-limit: token bucket `RATE_LIMIT_RPM=60`, `RATE_LIMIT_BURST=20`; per-IP/tenant; header phản hồi `X-RateLimit-*` (tùy chọn).
- Cache LRU: `RETRIEVE_CACHE_TTL_MIN=10` phút cho retrieve/rerank; không cache answer nhạy cảm.

---

## 12) RAM guard (runtime)

- Giới hạn Vision pages_used ≤ 10; ảnh render on-demand, giải phóng bộ nhớ sau sử dụng.
- MAX_CONTEXT nhỏ gọn (mặc định 8; tối đa 20) để tránh context phình to.
- Nếu p95 latency tăng/pressure: giảm TOP_RERANK, tắt HyDE, tăng cache TTL.

---

## 13) Logging (gợi ý theo thực tế)

- Khi Vision OFF do thiếu mapping/docs: `Vision gating: OFF (reason=no_docs_or_mapping)`.
- Khi Vision ON: `Vision gating: ON (config enabled)` và `Vision pages: used=..., failed=..., total_limit=10; pages=[...]`.
- Khi degrade: log rõ `degrade_mode=true`, `degrade_reason` và k hiện hành.

---

## 14) Lệnh thử nhanh (tham khảo)

- Powershell:
```powershell
$body = @{ query = "Áp suất vận hành tối đa của KT06101?"; language = "vi"; max_context = 8; enable_vision_generation = $true } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/ask" -Method Post -ContentType 'application/json' -Body $body
```

- Hoặc cURL:
```bash
curl -X POST http://127.0.0.1:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"query":"Áp suất vận hành tối đa của KT06101?","language":"vi","max_context":8,"enable_vision_generation":true}'
```

---

## 15) Định nghĩa Hoàn thành (DoD)

- `/ask` trả lời đúng ngôn ngữ; **citations 1-based** (hoặc từ chối có lý khi thiếu bằng chứng).
- Vision hoạt động: `pages_used ≤ 10`, render on-demand + cache; log gating rõ ràng.
- Degrade BM25-only hoạt động khi embedding/mạng lỗi; `meta.degrade_mode=true` + reason; dùng k degrade.
- Telemetry/meta đầy đủ trường; rate-limit & cache hoạt động; RAM vận hành ≤ 12 GB.

---

## 16) Rủi ro & Ứng phó

- Model timeouts/quotas: degrade BM25-only; giảm TOP_RERANK; tắt HyDE; tăng cache TTL; retry hợp lý.
- CE với VI không ổn định: fallback score-based/hybrid; điều chỉnh tham số rerank.
- Thiếu `doc_id_map.json`: Vision OFF; vẫn trả lời text-only với citations (doc_id + page nếu có), không fail.
- Chi phí/latency cao: hạ MAX_CONTEXT/TOP_RERANK; bật cache; tắt HyDE theo tình huống.

---

## 17) Phụ lục ENV (Phase 2)

```ini
# Routing nội bộ
LLM_MODEL_HEAVY=gemini-2.5-pro
LLM_MODEL_LIGHT=gemini-2.5-flash

# Embedding duy nhất (V1)
EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=gemini-embedding-001

# Retrieval defaults
MAX_CONTEXT=8
TOP_RERANK=20

# Vision & text-range
VISION_PAGE_SELECTOR_ENABLED=true
TEXT_RANGE_SCAN_ENABLED=false

# Degrade
RETRIEVAL_ALLOW_BM25_ONLY_FALLBACK=true
BM25_K_WHEN_DEGRADE=80
RERANK_TOP_N_WHEN_DEGRADE=50

# Rate limit & cache
RATE_LIMIT_RPM=60
RATE_LIMIT_BURST=20
RETRIEVE_CACHE_TTL_MIN=10
```
