# BUILD PLAN — Migration FAISS ➜ Weaviate (Self‑host, Docker) + Domain Prefilter + BGE Rerank + Page‑level Rerank + JSON‑with‑Evidence + CiteFix

Ngày: 2025-10-10
Trạng thái: Ready to implement (accuracy-first on RTX 4060)

---

## 1) Mục tiêu (GOAL)

- Thay FAISS = Weaviate (Docker, self-host) làm vector store; giữ nguyên Embedding Gemini 768d và BM25.
- Retrieval vẫn per‑chunk (không tạo index per‑page). Page‑level được dựng động ở runtime bằng cách gộp chunk theo (doc_id, page).
- Thêm domain prefilter (metadata filter) ngay trong truy vấn vector.
- Rerank bằng BGE v2‑m3 ở doc‑level và page‑level; chọn trang với MMR.
- Đầu ra JSON‑with‑evidence per‑claim; hậu xử lý CiteFix (sửa citation yếu, không đổi giá trị).
- Cho phép feature flag fallback FAISS (tạm thời), đường chính dùng Weaviate.

---

## 2) Bối cảnh / Ràng buộc (CONTEXT)

- Ingest & index per‑chunk: mỗi bản ghi là 1 đoạn text cắt từ tài liệu, metadata gồm: doc_id, page, chunk_id, text…
- BM25 (metadata.json) và FAISS (metadatas.json) hiện đều chunk‑level.
- Vision/pipeline ảnh là per‑page nhưng dựng động ở runtime (render ảnh trang ứng viên).
- Hạ tầng GPU: RTX 4060 (8GB). Ưu tiên accuracy hơn tốc độ; latency cao hơn nhưng trong kiểm soát.

---

## 3) Quyết định chính (KEY DECISIONS)

1) Granularity: per‑chunk (primary). Không xây index per‑page. Page‑level sẽ gộp từ chunks khi rerank/attribution.
2) Self‑query filters: Rule‑based trước (regex từ path/filename + từ điển), LLM fallback khi confidence < 0.7; khi low‑confidence thì filter nới (boost, không must).
   - equipment_type ∈ {compressor, turbine, pump, motor, exchanger, vessel, pid, manual}
   - doc_type ∈ {datasheet, manual, drawing, pid}
3) BM25: P0 = BM25 tách + Weaviate vector (merge ngoài). P1 = thử Weaviate hybrid (alpha=0.5–0.7) nếu KPI & latency ổn.
4) HNSW (Weaviate): giữ default để chạy; preset gợi ý M=64, efConstruction=128, efSearch=64 (tăng 96–128 nếu cần recall).
5) doc_id normalization:
   - doc_id = DOC_{sha1(relative_path)[:10]}_{file_stem_sanitized}
   - page_id = {doc_id}_p{page:04d}
   - chunk_id = {page_id}_c{chunk:02d}
   - Lưu mapping doc_id ↔ full_path; test uniqueness & stability.
6) OCR strategy: ưu tiên text layer; chỉ OCR các trang ứng viên thiếu text (trong K_page).
7) Observability: log đầy đủ các bước (query → filters → top‑K trước/sau filter → điểm BGE doc‑level → danh sách page sau MMR → JSON.support_rate → các chỉnh của CiteFix). Thu KPI: Citation@Doc/Page, MRR@10, Support rate, latency p50/p95, OCR hit‑rate.

---

## 4) Kiến trúc (high‑level)

```mermaid
flowchart LR
Q[Query] --> F[Self-query → Filters]
F -->|Lexical| L[BM25]
F -->|Vector| W[Weaviate (near_vector + filters)]
L --> U[Hợp nhất ứng viên]
W --> U
U --> R[BGE v2-m3 Rerank (doc-level)]
R --> G[Group by (doc_id,page)]
G --> T[Page Text (text layer/OCR)]
T --> PR[BGE Rerank (page-level)]
PR --> M[MMR Select Top-N Pages]
M --> J[LLM → JSON-with-evidence]
J --> C[CiteFix (post-hoc citations)]
C --> A[Answer + References]
```

---

## 5) Weaviate — Schema & Vận hành

- Vectorizer: "none" (dùng embedding 768d từ Gemini); metric: cosine (HNSW).
- Collection/Class: `Chunk` (mỗi record = 1 chunk).
- Properties (types):
  - text: text
  - doc_id: text
  - page: int
  - equipment_type: text
  - doc_type: text
  - equipment_id: text
  - vendor: text
  - source_path: text
  - lang: text (optional)
- Server: Docker local — http://localhost:8080. Không cần GPU cho Weaviate.

### Migration an toàn
- Bước 0: Spin-up Weaviate (Docker) + healthcheck.
- Bước 1: Dual‑write ingest (tạm thời): vẫn build FAISS + upsert Weaviate.
- Bước 2: `PRIMARY_RETRIEVER=weaviate` (feature flag) — bật đường chính.
- Bước 3: Theo dõi KPI (Citation@Doc/Page, MRR@10, latency).
- Bước 4: Nếu KPI đạt, tắt FAISS (hoặc giữ ẩn dự phòng 1–2 tuần).

---

## 6) Pipeline yêu cầu (không đổi logic lớn)

1) Self‑query → Filters (rule‑based; fallback LLM nếu confidence < 0.7; low‑confidence ⇒ boost‑filter).
2) Retrieve:
   - P0: BM25 (hiện tại) + Weaviate.near_vector(filters, limit=K_doc) ⇒ Hợp nhất ứng viên.
   - P1 (tùy chọn): Weaviate.hybrid(query, vector, alpha, filters) nếu muốn.
3) BGE v2‑m3 (doc‑level rerank) cho ứng viên hợp nhất (top‑K nhỏ).
4) Page‑level (dựng động từ chunk):
   - Group by (doc_id, page).
   - score_page = max(chunk_score) + 0.5 * sum(top3_chunk_scores) (hoặc RRF; paramizable).
   - Lấy page_text từ text layer; nếu thiếu ⇒ OCR chỉ các trang ứng viên.
   - BGE page‑level rerank trên page_text.
   - MMR chọn top‑N trang cho VLM/hiển thị.
5) LLM → JSON‑with‑evidence (per‑claim {doc_id, page, span, score, supported}).
6) CiteFix: sửa citation yếu (khớp value+unit + semantic); không đổi value.
7) (Gated) RARR khi support_rate thấp/strict mode.

---

## 7) Thông số mặc định (fit RTX 4060, accuracy‑first)

- Doc‑level: K_doc = 160–220; BGE FP16; batch = 8–16; max_length = 1024.
- Page‑level: K_page = 24–40; M_final = 12–20.
- MMR: λ ≈ 0.4 (grid‑search 0.3–0.6 trên golden set).
- OCR: chỉ khi trang không có text layer.

---

## 8) Interfaces / Data Shapes (tóm tắt)

```python
@dataclass
class Candidate:
    doc_id: str
    page: int
    chunk_id: str
    text: str
    score_raw: float
    source: Literal["weaviate","bm25","faiss"]
    score_rerank: float | None = None

@dataclass
class PageAgg:
    doc_id: str
    page: int
    chunks: list[Candidate]
    score_agg: float

@dataclass
class PageText:
    doc_id: str
    page: int
    text: str | None
    needs_ocr: bool

@dataclass
class PageRank:
    doc_id: str
    page: int
    text: str
    score_page_bge: float
```

Evidence schema (Pydantic):

```python
class Evidence(BaseModel):
    doc_id: str
    page: int
    span: str
    score: float

class Claim(BaseModel):
    id: str
    field: str
    value: Any
    unit: str
    supported: bool
    evidence: list[Evidence]

class Answer(BaseModel):
    question: str
    claims: list[Claim]
    confidence_overall: float
```

---

## 9) Observability & KPI

- Logs: query → filters → top‑K trước/sau filter → điểm BGE doc‑level → danh sách page (sau MMR) → JSON.support_rate → các sửa của CiteFix.
- KPI nghiệm thu:
  - Citation Accuracy@Doc ≥ 0.90; Citation Accuracy@Page ≥ 0.80.
  - Support rate ≥ 0.85.
  - MRR@10 sau rerank tăng ≥ 20% vs. FAISS‑only.
  - Latency p50/p95 trong ngân sách (đo trên RTX 4060 với K_doc≈200, K_page≈32–40, M_final≈12–20, batch 8–16).

---

## 10) Rủi ro & biện pháp

- Metadata thiếu/chưa chuẩn: mở đầu rule‑based từ path/filename; tăng cường auto‑tag ở ingest; low‑confidence ⇒ nới filter/boost.
- Latency tăng do rerank: khống chế K, batch theo VRAM; page‑level chỉ trên ứng viên; OCR chỉ khi cần.
- doc_id không ổn định: áp chuẩn normalization + test uniqueness/stability; lưu mapping doc_id ↔ full_path.
- Network/service: Weaviate Docker cần healthcheck + retry; dùng feature flag để fallback FAISS nếu sự cố.

---

## 11) Plan thực thi (2 tuần)

- Tuần 1:
  - Spin‑up Weaviate (Docker) + dual‑write ingest; thêm client Weaviate + feature flag retriever.
  - Build filters rule‑based; hợp nhất BM25 + Weaviate; BGE doc‑level rerank.
  - Endpoint trả JSON‑with‑evidence (validate Pydantic); log pipeline step‑by‑step.
- Tuần 2:
  - Page‑level: group‑and‑score pages → page_text → OCR thiếu → BGE page‑level rerank + MMR.
  - CiteFix mặc định ON; dashboard KPI (Citation@Doc/@Page, Support rate, MRR@10, latency).
  - Quyết định P1 (Weaviate hybrid) nếu KPI & latency ổn.

---

## 12) Deliverables

- Mã nguồn các module: config.py, weaviate_client.py, (optional) faiss_client.py, bm25_client.py, filters.py, rerank_bge.py, page_aggregator.py, ocr_runner.py, mmr.py, evidence_schema.py, citefix.py, service.py.
- Hướng dẫn chạy: biến môi trường, WEAVIATE_URL, bật PRIMARY_RETRIEVER.
- (Tùy chọn) Script tạo schema `Chunk` trên Weaviate nếu chưa có.

---

## 13) Definition of Done (DoD)

- FAISS được thay bằng Weaviate trong retriever vector (feature flag ON); BM25 giữ nguyên; embedding Gemini 768d giữ nguyên.
- Endpoint trả Answer(JSON‑with‑evidence) hợp lệ; CiteFix chạy mặc định.
- Golden set: Citation@Doc ≥ 0.90; Citation@Page ≥ 0.80; MRR@10 +20% vs. FAISS; latency trong ngân sách.
- Observability đầy đủ; có backout plan (flag về FAISS) nếu cần.
