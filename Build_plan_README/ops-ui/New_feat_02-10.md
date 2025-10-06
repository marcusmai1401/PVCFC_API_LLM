# Build_plan_README — Kế hoạch triển khai tối ưu hóa RAG-OCR (Thực chiến)

Ngày: 2025-10-02
Trạng thái: Kế hoạch triển khai chi tiết + thông số tham chiếu + lộ trình thực thi theo pha

1) Bối cảnh & tóm tắt yêu cầu

- OCR: Đang dùng PP-OCRv5 (.pdmodel) + dual extraction cho P&ID (vector text + OCR full page). GPU hiện đã hoạt động ổn (cuDNN 8.9 qua pip, cài đặt ưu tiên đường dẫn DLL đúng cách). Nếu GPU lỗi DLL → fallback CPU, không chặn ingest.
- Ngôn ngữ: Ưu tiên VI/EN, cho phép mixed-language để tăng recall.
- Ngân sách/độ trễ: Không áp cứng. Dùng safe defaults, tối ưu dần dựa trên số liệu.
- Đầu ra ingest: Ưu tiên bền vững & truy vấn nhanh. Đề xuất lưu Parquet + JSON manifest (lineage + versioning).

2) Sơ đồ pipeline (ngắn gọn)

Data (PDF/TIF) → PDF Parser (PyMuPDF)
                   ├─ Vector text extract (fast)
                   └─ Image render (DPI 150)
                      └─ PaddleOCR (GPU preferred)
                           └─ Text blocks + bbox + page
→ Normalize/Domain (P&ID tag schema, regex, synonyms) → Chunking (task-aware) → Dedup (content_hash)
→ Artifacts (Parquet + Manifest JSON) → Indexes:
   ├─ BM25 (doc_id/page aware)
   └─ FAISS (IndexFlatIP + L2-normalize embeddings)
→ Retrieval (BM25@K_bm25 ∥ FAISS@K_vec) → RRF fuse → N0
→ Stage-1 Rerank (Semantic Ranker) → N1
→ Stage-2 Rerank (LLM 2.5 Flash) → N2
→ Context packing (MMR, K_ctx) → Answer generation

3) Cấu hình tham chiếu (safe defaults, có thể tinh chỉnh)

- Retrieval & Rerank
  - K_bm25 = 100
  - K_vec = 100 (FAISS cosine via IndexFlatIP, embeddings L2-normalized)
  - rrf_k = 60
  - N0 = 120 (ứng viên sau RRF)
  - N1 = 40 (sau Stage-1 Rerank)
  - N2 = 12 (sau Stage-2 Rerank)
  - K_ctx = 8 (chọn vào ngữ cảnh cuối)
  - mmr_lambda = 0.7

- Chunking
  - Văn bản thường: 800–1,000 tokens; overlap 120–160
  - Bảng/spec: column-first; giữ header theo cửa sổ; window-merge cho dòng kẹt trang
  - P&ID: lưu bbox meta (page, zoom, dpi, pixel coords); gom nhãn-cụm (tag + arrow/ký hiệu)

- Embedding
  - Provider: Gemini (AI Studio)
  - Model: gemini-embedding-001
  - Dimension: 768
  - Normalize: L2-normalize trước khi add FAISS (cosine via IP)
  - Batch size: 256; Concurrency: 8; Max tokens/req: 20,000
  - Task: RETRIEVAL_DOCUMENT (document); RETRIEVAL_QUERY (query)

- GPU/cuDNN
  - Prefer GPU = true
  - Auto-detect cuDNN v8.x trong site-packages (pip) và prepend PATH/dll_directory
  - Nếu Paddle 2.6.2 + CUDA 11.8 cần 8.6 nhưng máy có 8.9 (đang chạy tốt) → GIỮ 8.9. Nếu lỗi, fallback CPU.

4) File cấu hình tham chiếu (YAML)

retrieval:
  k_bm25: 100
  k_vec: 100
  rrf_k: 60
  n0_candidates: 120
  n1_candidates: 40
  n2_candidates: 12
  k_ctx: 8
  mmr_lambda: 0.7
  hyde_enabled: false
  language_bias:
    enabled: true
    preferred: ["vi", "en"]

faiss:
  index_type: flat_ip          # cosine via inner product
  l2_normalize: true
  ivfpq:
    enabled: false             # bật khi > 1M vectors
    nlist: 1024
    m: 32
    nprobe: 8

embedding:
  provider: gemini
  model: gemini-embedding-001
  dimension: 768
  batch_size: 256
  concurrency: 8
  max_tokens_per_req: 20000
  task_document: RETRIEVAL_DOCUMENT
  task_query: RETRIEVAL_QUERY

chunking:
  default:
    target_tokens: 900
    overlap_tokens: 140
  table:
    mode: column-first
    keep_headers: true
    window_merge: true
  pid:
    save_bbox: true
    label_cluster: true

ocr:
  dpi: 150
  dual_extraction: true
  gpu:
    prefer_gpu: true
    autodetect_cudnn: true
    fallback_cpu: true

storage:
  format: parquet
  manifest: true
  versioning: true

5) Triển khai theo pha (có điểm kiểm chứng)

P0 — Hạ tầng GPU/cuDNN (sanity & fallback)
- Mục tiêu: Đảm bảo OCR dùng GPU ổn định; nếu DLL mismatch → fallback CPU tự động.
- Hành động:
  1) Viết util khởi tạo NVIDIA DLL path in-process (đã có mẫu trong test_ocr_gpu_infer.py):
     - Prepend bin của nvidia.cuda_runtime (cu11), nvidia.cudnn, nvidia.cublas vào PATH + add_dll_directory.
  2) Sanity test:
     - Paddle set_device('gpu:0') và inference 1 trang OCR → pass.
     - Batch embed 100 texts với Gemini client → đo p95 latency.
  3) Logging:
     - Ghi rõ version CUDA runtime, cuDNN major/minor, provider model.
  4) Fallback:
     - Nếu lỗi dynamic loader → chuyển use_gpu=False, tiếp tục ingest.

P1 — Chunking theo nhiệm vụ & chuẩn hoá miền P&ID
- Mục tiêu: Cải thiện chất lượng chunk cho RAG và giữ ngữ nghĩa không gian của P&ID.
- Hành động:
  1) Văn bản thường:
     - Chunk theo token 800–1,000; overlap 120–160; giữ tiêu đề/section.
  2) Bảng/spec:
     - Column-first; giữ header theo cửa sổ; merge dòng bị cắt trang; chuẩn hoá đơn vị/số liệu.
  3) P&ID:
     - Lưu bbox meta cho mỗi text (page, zoom, dpi, pixel coords).
     - Gom cụm label (tag + arrow/ký hiệu gần kề) để giữ liên hệ.
  4) Ngôn ngữ:
     - Normalize whitespace; giữ CJK nếu tăng recall.
  5) Dedup 100% nội dung trước embed (content_hash) + cache embedding SQLite.

P1.5 — Chuẩn hoá miền P&ID (tag schema nhẹ)
- Mục tiêu: Tăng khả năng match và boost trong rerank.
- Hành động:
  1) Tag schema: EquipmentTag, LineTag, LoopTag, Instrument, Valve, Pump, HeatExchanger...
  2) Rule/Regex: alias map (E-101 == E101), strip prefix vendor, normal hoá.
  3) Synonym dictionary (VI/EN): canonical form; áp dụng boost ở Stage-1.
  4) Entity linking mềm: nếu query có tag/ID → boost chunks có tag khớp/tiệm cận.

P2 — Chỉ mục & lưu trữ
- Mục tiêu: Bền vững, nhanh, versioned.
- Hành động:
  1) Embedding toàn bộ chunks sau ingest, lưu Parquet + manifest JSON (doc_id, hash, version, page, bbox...).
  2) FAISS IndexFlatIP (cosine) với vectors đã L2-normalize.
  3) BM25 xây inverted index theo doc_id + page; hỗ trợ filter by type (P&ID/spec/report).
  4) Versioning: mỗi ingest tạo index_version; retrieval chạy đúng version.

P3 — Retrieval & Rerank 2 tầng (hybrid)
- Mục tiêu: Nâng recall & precision; kiểm soát chi phí/độ trễ.
- Luồng đề xuất:
  1) Hybrid recall (song song):
     - BM25@K_bm25 = 100, FAISS@K_vec = 100
     - RRF(k=60) → N0 = 120
  2) Stage-1 Rerank (Semantic Ranker):
     - Input N0=120 → Output N1=40
     - Batch inference; lưu score; language bias nhẹ ưu tiên VI/EN khi điểm sát nhau
     - Triển khai tuỳ chọn:
       a) Google Vertex AI Semantic Reranker (nếu available qua AI Studio key)
       b) Cross-encoder mạnh (vd: bge-reranker-v2-m3) nếu muốn on-prem
  3) Stage-2 Rerank (LLM 2.5 Flash):
     - Input N1=40 → Output N2=12
     - Scoring theo question-aware salience + evidence density + de-dup theo doc_id/page
     - Fallback: nếu LLM không khả dụng → giữ N1 làm N2
  4) Context packing:
     - Chọn K_ctx=8 từ N2=12 theo MMR(λ=0.7) để đa dạng nguồn và tránh trùng lặp.

- Pseudocode (khung tích hợp):
  candidates_bm25 = bm25.search(query, top_k=K_bm25)
  candidates_vec  = faiss.search(query_vec, top_k=K_vec)
  fused           = RRF(candidates_bm25, candidates_vec, k=rrf_k)[:N0]
  reranked1       = semantic_rerank(query, fused)[:N1]
  reranked2       = llm_rerank_2p5_flash(query, reranked1)[:N2]
  final_context   = MMR_select(reranked2, k=K_ctx, lambda=mmr_lambda)

P4 — Đo lường & chốt SLO (Definition of Done)
- Mục tiêu: Cải thiện chất lượng tìm kiếm mà không nổ chi phí/độ trễ.
- Chỉ tiêu chấp nhận (DoD):
  - +12–20% nDCG@10 & +10% Recall@50 vs baseline (không rerank)
  - Độ trễ p95 ≤ 2.5× baseline (vì thêm 2 tầng rerank)
  - Chi phí: nếu >1.8× baseline → bật cache rerank & giảm N0/N1
  - Ổn định: không crash khi GPU lỗi DLL (tự fallback CPU); không rơi result do mixed-language

- Kịch bản benchmark cần bàn giao:
  1) tools/benchmark_retrieval.py → đo nDCG@10/20, Recall@50, p95 latency, cost/query
  2) Bộ câu hỏi đánh giá (20–30 queries) + ground truth (doc_id/page)
  3) A/B report (CSV + Markdown) baseline vs 2-stage rerank, khuyến nghị tinh chỉnh thông số

6) Deliverables (theo yêu cầu)

1. Sơ đồ pipeline (trên)
2. Cấu hình tham chiếu (YAML ở mục 4)
3. Kịch bản benchmark (tools/benchmark_retrieval.py) — liệt kê tiêu chí đo ở mục P4
4. Báo cáo A/B: template Markdown + CSV xuất từ benchmark
5. Kế hoạch scale (P2):
   - FAISS IVF-PQ khi N > 1M vectors: nlist≈sqrt(N), m=32, nprobe=8–16; đánh đổi ~2–3% recall
   - Sharding theo collection/type (P&ID/spec/report)
   - Pre-warm cache: top queries, popular chunks
   - Backpressure: hạ concurrency, MMR/rrf_k nếu QPS tăng đột biến
   - Observability: log QPS, latency p50/p95, 429, cost/query, cache hit

7) Tích hợp vào codebase (đề xuất module/đường dẫn)

- app/ingestion/
  - parsers/pid_parser.py (bbox + label cluster)
  - normalizers/text_cleanup.py (whitespace/unit/number)
  - domain/pid_schema.py (tag schema, regex, synonyms)
  - writers/parquet_writer.py + manifest_writer.py

- app/rag/
  - retriever.py (mở rộng: RRF, MMR, hooks rerank)
  - rerank/semantic_reranker.py (VertexAI/Gemini hoặc cross-encoder)
  - rerank/llm_reranker_flash.py (LLM 2.5 Flash)
  - utils/metrics.py (nDCG, Recall, MRR, NDCG@K)

- tools/
  - benchmark_retrieval.py (A/B baseline vs rerank 2 tầng)
  - ingest_pipeline.py (batch ingest; dual extraction; GPU fallback)

8) Hỏi lại/thiếu thông tin (cần xác nhận trước khi code)

- Bạn muốn dùng Stage-1 Rerank qua dịch vụ nào? (Vertex AI Semantic Reranker qua AI Studio key, hay cross-encoder on-prem)
- Có sẵn API/endpoint cho LLM “2.5 Flash” chưa? (model name, pricing constraints)
- Có ground-truth set (20–30 câu hỏi + doc_id/page) để benchmark không? Nếu chưa, tôi sẽ đề xuất tạo nhanh từ 10–15 tài liệu tiêu biểu.
- Ưu tiên bộ nhớ/tốc độ vs độ chính xác: chấp nhận tăng chi phí rerank bao nhiêu lần so với baseline? (ngưỡng mặc định 1.8×)

9) Lộ trình thực thi (dự kiến)

- Tuần 1:
  - P0: GPU sanity + fallback, hoàn thiện utils + log → done/validate
  - P1: Chunking task-aware & P&ID schema (parse + bbox + cluster) → PR #1
  - P2: Parquet + manifest + versioning, cập nhật builders → PR #2
- Tuần 2:
  - P3: Rerank Stage-1 + Stage-2 (service adapters + config) → PR #3
  - P4: Benchmark harness + test set + A/B report → PR #4
  - Tune RRF/MMR + language bias → PR #5

10) Lệnh tham khảo (PowerShell)

# Ingest (dual extraction + GPU preferred)
python tools/ingest_pipeline.py `
  --source-dir "D:\Data_Raw" `
  --out "artifacts/ingestion" `
  --dpi 150 --gpu-prefer --fallback-cpu `
  --dedup --parquet --manifest

# Build BM25
python tools/build_bm25_index.py `
  --chunks-jsonl "artifacts/ingestion/chunks/chunks.jsonl" `
  --index-dir   "artifacts/index/bm25"

# Build FAISS (Gemini 768D, cosine via IP, L2-normalize)
$env:EMBEDDING_MODEL = "gemini-embedding-001"
python tools/build_faiss_local.py `
  --bm25-dir "artifacts/index/bm25" `
  --faiss-dir "artifacts/index/faiss"

# Benchmark retrieval (A/B)
python tools/benchmark_retrieval.py `
  --bm25-dir "artifacts/index/bm25" `
  --faiss-dir "artifacts/index/faiss" `
  --queries-file "artifacts/eval/queries.jsonl" `
  --groundtruth-file "artifacts/eval/groundtruth.jsonl" `
  --output "artifacts/eval/report"

11) Ghi chú về GPU/cuDNN hiện tại

- Máy đang hoạt động ổn với cuDNN 8.9 (pip nvidia-cudnn-cu11) + CUDA 11.8 runtime; Paddle 2.6.2 đã xác thực GPU inference OCR ok.
- Không cần cài 8.6 nếu 8.9 chạy ổn. Nếu phát sinh lỗi dynamic loader:
  - Prepend site-packages\nvidia\cudnn\bin vào PATH (ưu tiên trước 9.x)
  - Nếu vẫn lỗi → fallback CPU và log cảnh báo, không dừng pipeline.

12) Kết luận

- Pipeline hiện tại đã tối ưu phía OCR/ingest. Kế hoạch này tập trung nâng chất lượng retrieval thông qua rerank 2 tầng, chunking theo nhiệm vụ và chuẩn hoá miền P&ID, đồng thời bảo toàn hiệu năng/cost bằng batch/concurrency và cache.
- Điểm còn thiếu là benchmark chất lượng (nDCG/Recall) và reranker integration. Sau khi xác nhận các lựa chọn dịch vụ rerank/LLM, tôi sẽ tiến hành PRs theo lộ trình ở mục 9.
