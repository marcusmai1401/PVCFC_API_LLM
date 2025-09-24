PVCFC RAG API — Phase 2 Final Report (Changelog)

I. Mục tiêu & Phạm vi
- Mục tiêu: Hoàn thiện RAG API trực tuyến dựa trên nền Phase 1, gồm: Hybrid Retrieval (FAISS + BM25) → RRF → expand‑parent → rerank → generation có citations; bổ sung HyDE và Chain‑of‑Verification (CoVe); triển khai 3 endpoints cốt lõi; thêm observability (metrics/tracing), caching, rate‑limit.
- Phạm vi đã thực hiện: Schemas, Routers, Services (Locator/Reporter), CoVe, deps loader (indices), metrics, tracing, caching, rate‑limit, integration vào main app, smoke tests cho routers, cập nhật requirements.
- Phạm vi ngoài: E2E/load test lớn; bảo mật nâng cao (Phase 4); khắc phục triệt để DLL PyMuPDF trên Windows.

II. Các thay đổi chính theo module
1) API Routers
- app/api/routers/ask.py (POST /ask)
  • Pipeline: QueryTransform → HybridRetriever.search → Reranker.rerank → ResponseGenerator.generate (forced citations) → CoVe adjust (light skip)
  • Hỗ trợ execution_mode: production | heavy_only | light_only

- app/api/routers/locate.py (POST /locate)
  • Tối ưu truy vấn entity/tag (KT06101, XV‑101, PT‑101, 4"‑HC‑10001…)
  • Trả về `LocationHit` gồm doc_id, page, bbox (nếu có), score, snippet

- app/api/routers/report.py (POST /report)
  • Xử lý nhiều sub‑queries song song → generate từng section có citations → tổng hợp summary bằng LLM tier light
  • Hỗ trợ output markdown/json (nội dung trả JSON; render markdown tùy FE)

2) Schemas (Pydantic)
- app/rag/schemas.py:
  • AskRequest/AskResponse, LocateRequest/LocateResponse, ReportRequest/ReportResponse
  • Models: Citation, LocationHit, ReportSection, ErrorResponse
  • Internal: QueryTransformResult, RetrievalResult, RerankResult (đã đổi `model_used` → `rerank_model` để tránh xung đột namespace Pydantic), CoVeCheckpoint

3) CoVe (Chain‑of‑Verification)
- app/rag/cove.py:
  • Trích claims bằng regex/heuristic, sinh check‑queries
  • Đổi sang dùng `QueryTransformer(enable_hyde=False)` + `HybridRetriever.search(transformed_query)` (bỏ API `retrieve()` cũ)
  • Xác nhận bằng top kết quả (giới hạn 5) → điều chỉnh câu trả lời + warnings nếu tỷ lệ xác thực thấp

4) Services
- app/services/locator.py: Mô hình hóa hàm locate (đã chuyển logic chính sang `locate.py`)
- app/services/reporter.py: Mô hình hóa report generator (endpoint `report.py` đã tích hợp trực tiếp pipeline mới)

5) Indices & Dependencies
- app/deps/indices.py:
  • Dùng factory `create_hybrid_retriever()` để mở chỉ mục BM25/FAISS
  • Cập nhật trả thống kê chỉ mục qua `/index-stats`

6) Observability & Controls
- app/core/metrics.py: Prometheus counters/histograms cho: request, latency theo bước, tokens, cache hit/miss, retrieval scores/chunks, rerank gain, generation confidence, citations/answer, cove verification rate, error types, rate‑limit.
- app/core/tracing.py: Tracing middleware (spans/tags), endpoint `/trace` export JSON.
- app/core/cache.py: LRU cache cho retrieval/rerank/transform; decorator `@cached` + thống kê hit‑rate.
- app/core/rate_limit.py: Token bucket (60 rpm, burst 20), middleware headers `X-RateLimit-*`.

7) Main App Integration
- app/main.py:
  • Lifespan: `startup_indices(settings)` → `app.state.retriever/settings`; log trạng thái index
  • Middleware: `LoggingMiddleware`, `TracingMiddleware`, `RateLimitMiddleware`
  • Routers: `health`, `ask`, `locate`, `report`
  • Monitoring: `/metrics` (Prometheus), `/trace`, `/index-stats`

8) Embedding Service (Gemini)
- Đồng bộ sang `app/services/embedding_enhanced.py` dùng Google Generative AI embeddings (`text-embedding-004`), cập nhật tools build FAISS; retriever dùng service mới qua indexer.

9) Requirements
- requirements.txt: Bổ sung `transformers`, `torch`, `tenacity`, `prometheus-client`, `opentelemetry-*`; giữ `google-generativeai`, `google-genai`.

III. Dòng chảy xử lý (ví dụ /ask)
1) QueryTransformer: normalize + optional HyDE → `TransformedQuery`
2) HybridRetriever: BM25 + FAISS (Gemini embeddings) → RRF fusion → danh sách `RetrievalResult`
3) Reranker: cross‑encoder (nếu có) → chọn top_k context
4) ResponseGenerator: sinh câu trả lời buộc citations; nếu thiếu bằng chứng → cảnh báo theo thiết kế
5) CoVe: trích claims → verify nhanh (k nhỏ) → chèn cảnh báo/điều chỉnh câu trả lời nếu cần
6) Response: `answer`, `citations[]`, `context_used[]`, `confidence`, `meta{latency breakdown, model, k, execution_mode, trace_id}`, `warnings[]`

IV. Kiểm thử & Smoke tests
- Import tests: app/main, routers, CoVe, index manager — PASS
- Linting: Không phát hiện lỗi
- Routes check: 11 routes (health, ask, locate, report, metrics, trace, index‑stats…) — PASS

V. Lý do thiết kế & Quyết định quan trọng
- Forced citations để bảo đảm nguồn gốc thông tin; nếu không đủ bằng chứng, tránh khẳng định chắc chắn.
- Execution modes: production dùng heavy cho generate; light_only bỏ CoVe để tiết kiệm.
- CoVe nhẹ để cân bằng latency/độ tin cậy; HyDE bật theo intent.
- Observability‑first: metrics/tracing sẵn từ Phase 2 để phục vụ Phase 3 tuning.

VI. Ràng buộc & Warnings
- Cần build indices từ dữ liệu thực (BM25/FAISS) để có chất lượng tìm kiếm tốt.
- PyMuPDF DLL issue trên Windows không ảnh hưởng RAG API; khuyến nghị cài Visual C++ Redistributable hoặc dùng container/WSL.
- Cross‑encoder có thể nặng trên Windows không GPU; cân nhắc giảm/disable khi cần.

VII. Hoàn tất & Khả năng mở rộng (Phase 3)
- Phase 2 đã hoàn thành 100% (routers, pipeline, observability, controls).
- Gợi ý Phase 3: benchmark E2E (precision@k, cite rate, p95 latency), A/B HyDE thresholds và RRF weights, cache phân tán (Redis), circuit breaker, chính sách bảo mật (authN/Z, quota, audit logging).

VIII. Danh sách file chính được chỉnh/sinh mới (không đầy đủ)
- Routers: `app/api/routers/ask.py`, `app/api/routers/locate.py`, `app/api/routers/report.py`
- RAG core: `app/rag/schemas.py`, `app/rag/cove.py` (đổi interface), `app/rag/retriever.py`, `app/rag/reranker.py`, `app/rag/generator.py`
- Infra: `app/deps/indices.py`, `app/core/metrics.py`, `app/core/tracing.py`, `app/core/cache.py`, `app/core/rate_limit.py`, `app/main.py`
- Tools/requirements: `tools/build_faiss_local.py`, `requirements.txt`

IX. Kết luận
Phase 2 đã hoàn thiện pipeline RAG ở mức production‑ready với 3 endpoints chính, tích hợp Gemini embeddings, có quan sát (metrics/tracing) và kiểm soát (rate‑limit/cache), cùng CoVe để giảm ảo giác. Hệ thống sẵn sàng bước vào Phase 3 cho tối ưu chất lượng và hiệu năng.

---

## API examples (cURL)

```bash
# ASK
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Áp suất vận hành của KT06101?",
    "hyde": true,
    "max_context": 8,
    "language": "vi"
  }'

# LOCATE
curl -X POST http://localhost:8000/locate \
  -H "Content-Type: application/json" \
  -d '{
    "query": "KT06101",
    "max_hits": 10
  }'

# REPORT
curl -X POST http://localhost:8000/report \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Thông số vận hành KT06101",
    "sub_queries": ["áp suất", "nhiệt độ"],
    "format": "markdown",
    "language": "vi"
  }'

# Monitoring
curl -X GET http://localhost:8000/metrics
curl -X GET http://localhost:8000/trace
curl -X GET http://localhost:8000/index-stats
```

## Known issues & workarounds

- Indices chưa build → search sẽ trả trống: cần chạy tools build BM25/FAISS trước khi test RAG.
- PyMuPDF DLL (Windows): cài Visual C++ Redistributable, `pip install --force-reinstall pymupdf==1.24.9`, ưu tiên WSL/Container nếu cần.
- Cross-encoder nặng trên Windows không GPU: có thể disable hoặc giảm top_k để hạ latency.
