PVCFC RAG API — Phase 2 Implementation Summary

I. Mục tiêu Phase 2
- Hoàn thiện pipeline RAG trực tuyến dựa trên hạ tầng Phase 1: Hybrid Retrieval (FAISS + BM25) → RRF → expand‑parent → rerank → generation có citations.
- Triển khai 3 endpoints chuẩn: /ask, /locate, /report với tính ổn định, rate‑limit, caching, logging/metrics/tracing.
- Áp dụng HyDE và Chain‑of‑Verification (CoVe) nhẹ để tăng độ tin cậy đầu ra.

II. Phạm vi thực thi
- Đã làm: Schemas, Routers, Services (Locator, Reporter), CoVe, deps loader (indices), metrics, tracing, caching, rate‑limit, cập nhật main app, tests cho routers, cập nhật requirements.
- Không làm: Load/E2E test cường độ cao, bảo mật nâng cao (để Phase 4), khắc phục triệt để lỗi DLL PyMuPDF trên Windows.

III. Kiến trúc & Modules mới/được cập nhật
1) API Routers
- app/api/routers/ask.py: POST /ask
  • Pipeline: QueryTransform → Hybrid Retrieve → Rerank → Generate (forced citations) → CoVe adjust
  • Hỗ trợ execution_mode: production | heavy_only | light_only

- app/api/routers/locate.py: POST /locate
  • Tối ưu truy vấn entity/tag (KT06101, XV‑101, PT‑101, 4"‑HC‑10001…)
  • Trả về hits với page và bbox nếu có

- app/api/routers/report.py: POST /report
  • Xử lý nhiều sub‑queries song song → sections có citations → summary
  • Hỗ trợ markdown/json

2) Schemas (Pydantic)
- app/rag/schemas.py: AskRequest/Response, LocateRequest/Response, ReportRequest/Response, Citation, LocationHit, ReportSection, ErrorResponse, các kết quả nội bộ (Transform/Retrieval/Rerank/CoVeCheckpoint).

3) CoVe (Chain‑of‑Verification)
- app/rag/cove.py: Tách claim đơn giản bằng regex + heuristic, sinh check‑queries, retrieve nhanh (k nhỏ), đánh giá confidence, điều chỉnh câu trả lời (chèn cảnh báo nếu cần) và xuất warnings.

4) Services
- app/services/locator.py: Phát hiện loại entity, tìm kiếm bằng BM25/Hybrid, trả snippet theo window, dedup theo (doc_id, page, bbox).
- app/services/reporter.py: Chạy sub‑queries song song (semaphore), rerank (nếu sẵn), generate per‑section, gom citations, tạo summary và format markdown.

5) Indices & Dependencies
- app/deps/indices.py: IndexManager khởi tạo EmbeddingService (Gemini), load BM25/FAISS, tạo HybridRetriever + Reranker, trả thống kê (doc_count, chunk_count, vector_count…).

6) Observability & Controls
- app/core/metrics.py: Prometheus counters/histograms (request, latency theo bước, tokens, cache hit/miss, retrieval, rerank gain, generation confidence, citations/answer, cove rate, error types, rate‑limit).
- app/core/tracing.py: Tracing middleware đơn giản (spans, tags, export JSON), endpoint /trace.
- app/core/cache.py: LRU cache (retrieval/rerank/transform) với TTL, thống kê hit‑rate; decorator cached.
- app/core/rate_limit.py: Token bucket (60 rpm, burst 20), middleware thêm headers X‑RateLimit‑*.

7) Main App Integration
- app/main.py:
  • Lifespan: startup_indices(settings) → app.state.retriever/settings; log trạng thái index.
  • Middleware: LoggingMiddleware, TracingMiddleware, RateLimitMiddleware.
  • Routers: health, ask, locate, report.
  • Monitoring endpoints: /metrics (Prometheus), /trace (trace hiện tại), /index‑stats (thống kê index).

8) Embedding Service (Gemini)
- Sửa import để dùng app/services/embedding_enhanced.py (Google Generative AI embeddings, model text‑embedding‑004) cho retriever và tool build FAISS.

9) Tests
- tests/test_api_routers.py: Smoke/mocked tests cho /ask, /locate, /report và endpoints monitoring.

10) Requirements
- requirements.txt: Bổ sung transformers, torch (rerank), tenacity (retry), prometheus‑client, opentelemetry libs; giữ google‑generativeai/google‑genai.

IV. Dòng chảy xử lý (ví dụ /ask)
1) QueryTransformer: normalize + tùy chọn HyDE → transformed_query, hyde_queries, filters.
2) HybridRetriever: BM25 + FAISS (Gemini embeddings) → hợp nhất RRF → trả chunks+scores.
3) Reranker: cross‑encoder (nếu có) → chọn top_k context.
4) Generator: sinh câu trả lời buộc citations (nếu thiếu nguồn → trả thông báo theo thiết kế).
5) CoVe: trích claim quan trọng → verify nhanh k=5 → cảnh báo/điều chỉnh answer nếu confidence thấp.
6) Response: answer, citations, context_used, confidence, meta (latency breakdown, model, k, execution_mode, trace_id), warnings.

V. Cách sử dụng & chạy thử
1) Cài dependencies
   pip install -r requirements.txt

2) Build chỉ mục (nếu chưa có)
   python tools/build_bm25_index.py
   python tools/build_faiss_local.py

3) Chạy API
   python -m app.main

4) Kiểm tra nhanh
   - POST /ask    : {"query":"Áp suất vận hành KT06101?"}
   - POST /locate : {"query":"KT06101"}
   - POST /report : {"topic":"Thông số KT06101","sub_queries":["áp suất","nhiệt độ"]}
   - GET  /metrics, /trace, /index-stats

VI. Các quyết định thiết kế chính
- Forced citations: bắt buộc nguồn, nếu không có bằng chứng đủ → cảnh báo hoặc từ chối trả chắc chắn.
- Mode thực thi: production dùng heavy cho generate; light_only bỏ CoVe để tiết kiệm.
- Verification nhẹ: CoVe chạy nhanh (k nhỏ, không expand) để cân bằng latency.
- Observability‑first: thêm metrics/tracing ngay từ Phase 2 để hỗ trợ Phase 3 tuning.

VII. Ràng buộc & cảnh báo
- Indices cần được build từ data thật để đạt chất lượng tìm kiếm.
- PyMuPDF có thể lỗi DLL trên Windows (không ảnh hưởng luồng chính RAG/API); có thể cài lại hoặc dùng container.
- Rerank local (transformers/torch) có thể nặng trên Windows không GPU; cân nhắc tắt/giảm khi cần.

VIII. Công việc tiếp theo (gợi ý cho Phase 3)
- E2E benchmarks (latency breakdown, precision@k, cite rate) trên bộ QA thật.
- A/B HyDE thresholds, RRF weights, top_k các bước.
- Triển khai cache phân tán (Redis) và circuit breaker.
- Bảo mật (authN/Z), audit logging, quota per tenant.

IX. Kết luận
Phase 2 đã hoàn thiện pipeline RAG sản xuất với 3 endpoints chính, Gemini embeddings, quan sát (metrics/tracing), kiểm soát (rate‑limit/cache) và CoVe giảm ảo giác. Hệ thống sẵn sàng cho Phase 3 tối ưu chất lượng/hiệu năng và mở rộng dữ liệu thật.
