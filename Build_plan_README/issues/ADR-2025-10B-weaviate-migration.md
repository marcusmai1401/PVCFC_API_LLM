# ADR-2025-10B: Thay FAISS bằng Weaviate (Docker) — giữ Embedding & BM25

**Ngày:** 2025-10-10
**Tình trạng:** Chốt & triển khai
**Phạm vi:** Thay lớp **vector store** từ FAISS ➜ **Weaviate** (chạy bằng Docker, self-host) để có **metadata filter** & **hybrid (tùy chọn)**.
**Không thay đổi:** **Embedding model** (Gemini 768d) **giữ nguyên**; **BM25** (lexical) **giữ nguyên** (dùng như hiện tại hoặc chuyển dần sang BM25 built-in của Weaviate sau).

> TL;DR: Đúng — ta **chỉ thay FAISS = Weaviate** cho phần truy hồi vector; **embedding** và **BM25** vẫn dùng như cũ. Các lớp khác (BGE reranker, page-level rerank, JSON-with-evidence, CiteFix) giữ nguyên theo ADR-2025-10.

---

## 1) Lý do thay FAISS bằng Weaviate
- **Filter theo metadata ngay trong query** (equipment_type, doc_type, vendor, tag, page, ...), giúp **lọc miền trước** khi tính vector ⇒ giảm nhiễu TURBINE khi hỏi COMPRESSOR.
- **Hybrid search** (keyword + vector) **built-in** (tùy chọn): nếu muốn, có thể trộn BM25 với vector trong một API (`alpha`).
- **Dịch vụ bền vững**: persistence, HNSW index, API rõ ràng.
- Phù hợp với lộ trình đã chốt: **prefilter miền ➜ BGE rerank ➜ page-level rerank + MMR ➜ JSON-with-evidence ➜ CiteFix**.

---

## 2) Kiến trúc sau khi thay

```mermaid
flowchart LR
Q[User Query] --> F[Self-query → JSON Filters]
F -->|Lexical| L[BM25 hiện có]
F -->|Vector| W[Weaviate (near-vector + filter)]
L --> U[Hợp nhất ứng viên]
W --> U
U --> R[BGE v2-m3 Rerank (doc-level)]
R --> P[Page-level rerank (OCR/text) + MMR]
P --> G[LLM → JSON-with-evidence]
G --> C[CiteFix (post-hoc citations)]
C --> A[Answer + References]
```

- **BM25**: giữ như hiện tại (Elasticsearch/Whoosh/lucene-based…).
- **Weaviate**: thay thế FAISS làm **vector retriever** chính. Có thể bật **hybrid** của Weaviate để gộp keyword+vector nội bộ (tùy chọn).
- **BGE v2-m3**: rerank ở **doc-level** (sau hợp nhất) và **page-level** (trên text OCR) — **không đổi**.

---

## 3) Triển khai Docker (local)

### 3.1. Cài Docker
- Windows/macOS: cài **Docker Desktop**.
- Linux: cài `docker` + `docker compose` (plugin).

Kiểm tra:
```bash
docker --version
docker compose version
```

### 3.2. `docker-compose.yml`
Tạo file sau trong thư mục trống:

```yaml
version: "3.8"
services:
  weaviate:
    image: cr.weaviate.io/semitechnologies/weaviate:latest
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      QUERY_DEFAULTS_LIMIT: "25"
      AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: "true"
      PERSISTENCE_DATA_PATH: "/var/lib/weaviate"
      DEFAULT_VECTORIZER_MODULE: "none"   # dùng embedding Gemini 768d
      CLUSTER_HOSTNAME: "node1"
    volumes:
      - weaviate_data:/var/lib/weaviate
volumes:
  weaviate_data:
```

Chạy:
```bash
docker compose up -d
docker compose logs -f weaviate   # xem log (Ctrl+C để thoát)
curl http://localhost:8080/v1/.well-known/ready   # READY
```

> **GPU không bắt buộc** cho Weaviate. GPU RTX 4060 của bạn dùng cho **BGE reranker** trong app.

---

## 4) Schema & Ingest vào Weaviate

### 4.1. Schema gợi ý
- **Collection/Class**: `Chunk` (một bản ghi = 1 chunk hoặc 1 trang).
- **Vectorizer**: `"none"` (vì bạn tự cấp vector 768d từ Gemini).
- **Properties** (nên có):
  - `text` (string), `doc_id` (string), `page` (int),
  - `equipment_type` (string), `doc_type` (string), `equipment_id`/`tag` (string),
  - `vendor` (string), `source_path` (string), `lang` (string, tùy chọn).

### 4.2. Ingest (pseudo-Python)
```python
from weaviate import Client

client = Client("http://localhost:8080")
col = client.collections.get("Chunk")  # đã tạo schema trước đó

def upsert_chunk(text, meta, embedding_768):
    props = {
        "text": text,
        "doc_id": meta["doc_id"],
        "page": meta["page"],
        "equipment_type": meta["equipment_type"],
        "doc_type": meta["doc_type"],
        "equipment_id": meta.get("equipment_id"),
        "vendor": meta.get("vendor"),
        "source_path": meta.get("source_path"),
        "lang": meta.get("lang", "vi")
    }
    col.data.insert(properties=props, vector=embedding_768)
```

> **Embedding model giữ nguyên**: tiếp tục gọi **Gemini embedding 768d** như trước; chỉ thay nơi **lưu & truy vấn vector**.

---

## 5) Query: Vector + Filter (và/hoặc Hybrid)

### 5.1. Near-vector + Filter (dùng khi vẫn giữ BM25 riêng)
```python
from weaviate.classes.query import Filter

alpha = None  # không dùng hybrid ở đây
filters = Filter.by_property("equipment_type").equal("compressor") & \
          Filter.by_property("doc_type").contains_any(["datasheet","manual"])

res = (col.query.near_vector(
         near_vector=query_vec,     # 768d từ Gemini
         limit=200,
         filters=filters)
       .objects)
candidates_vec = [(o.properties.get("doc_id"), o.properties.get("page")) for o in res]

# Hợp nhất với ứng viên từ BM25 (hệ hiện tại), rồi đưa vào BGE v2-m3 rerank (doc-level).
```

### 5.2. Hybrid (tùy chọn, gộp keyword+vector ngay trong Weaviate)
```python
alpha = 0.5  # 0=BM25, 1=vector; 0.5 = trộn đều
filters = Filter.by_property("equipment_type").equal("compressor") & \
          Filter.by_property("doc_type").contains_any(["datasheet","manual"])

res = (col.query.hybrid(
         query="CO2 compressor 4th stage discharge pressure",
         alpha=alpha,
         filters=filters,
         limit=200)
       .objects)
candidates = [(o.properties.get("doc_id"), o.properties.get("page")) for o in res]
```

> **BM25 vẫn giữ nguyên**: v1 bạn có thể **tiếp tục dùng BM25 cũ** và chỉ thay FAISS bằng Weaviate. Khi ổn định, cân nhắc **chuyển BM25 vào Weaviate hybrid** để giảm số dịch vụ.

---

## 6) Tích hợp với pipeline hiện có (không đổi logic)

1) **Self-query → Filters** (equipment_type/doc_type/...).
2) **Retrieve**:
   - **BM25 hiện tại** (lexical) **+ Weaviate** (vector + filter), hoặc **Weaviate hybrid**.
3) **BGE v2-m3 (doc-level)** → giữ `K_doc ≈ 160–220`, `batch 8–16`, `max_length=1024`, FP16 (RTX 4060).
4) **Page-level rerank** trên **text/OCR** + **MMR** (top-N trang).
5) **LLM → JSON-with-evidence** (claim-level).
6) **CiteFix** (mặc định): sửa citation yếu (chỉ sửa nguồn, **không** đổi giá trị).
7) **RARR** (gated, khi strict mode/thiếu bằng chứng).

---

## 7) Cấu hình khởi điểm (RTX 4060 — “accuracy-first”)

- **Weaviate query**: `limit(K_doc)=160–220`, nếu hybrid dùng `alpha=0.5–0.7`.
- **BGE v2-m3**: FP16, `batch=8–16`, `max_length=1024`.
- **Page-level**: `K_page=24–40`, `M_final=12–20`. OCR **chỉ** khi trang không có text layer.
- **MMR**: `λ≈0.4` (tune 0.3–0.6).

---

## 8) Kế hoạch migration an toàn

- **Bước 0**: Spin-up Weaviate (Docker).
- **Bước 1**: **Dual-write ingest** (tạm thời): tiếp tục build FAISS (để fallback) + upsert Weaviate.
- **Bước 2**: Bật **retriever Weaviate** (feature flag `PRIMARY_RETRIEVER=weaviate`).
- **Bước 3**: Theo dõi KPI (Citation@Doc/Page, MRR@10, latency).
- **Bước 4**: Nếu KPI đạt, **tắt FAISS** (hoặc giữ ẩn làm dự phòng).

> Nếu bạn muốn **cắt FAISS ngay**, có thể bỏ qua bước dual-write. Tuy nhiên khuyến nghị giữ fallback 1–2 tuần để an tâm.

---

## 9) Rủi ro & biện pháp
- **Hạ tầng mới (service)**: cần Docker chạy nền. → Viết **healthcheck** và **retry** trong retriever client.
- **Độ trễ network**: thường **được bù** bởi top-K “sạch” hơn (ít phải rerank). → Giới hạn `limit`, dùng batch BGE hợp lý.
- **Metadata thiếu/chưa chuẩn**: trước mắt suy từ **path/filename + 1–3 trang đầu**; LLM fallback cho low-confidence.
- **Bảo mật**: file compose bật anonymous access. Sau khi ổn định, bật auth/API key, hạn IP/port theo môi trường.

---

## 10) DoD (Definition of Done)
- **FAISS** được thay bằng **Weaviate** trong đường truy hồi vector.
- **Embedding Gemini 768d** và **BM25** vẫn hoạt động như cũ (hoặc Weaviate hybrid nếu bật).
- Golden set cho thấy: **Citation Accuracy@Doc ≥ 0.90**, **@Page ≥ 0.80**, **MRR@10 tăng ≥ 20%** vs. baseline FAISS, latency chấp nhận được.
- Endpoint trả **JSON-with-evidence** hợp lệ; CiteFix mặc định ON.

---

## 11) Backout plan
- Giữ feature flag để switch lại **FAISS** nếu Weaviate gặp sự cố.
- Dữ liệu vector vẫn nằm ở FAISS (nếu dual-write) ⇒ thời gian hoàn nguyên gần như tức thì.
- Nếu đã cắt FAISS: có thể dựng lại từ snapshot/chunk store rồi build FAISS offline (đề phòng sự cố hiếm).

---

## 12) FAQ

**Q:** Embedding và BM25 có đổi không?
**A:** **Không.** Embedding Gemini 768d và BM25 **giữ nguyên**. Ta **chỉ thay FAISS = Weaviate** cho vector retrieval. (Tùy chọn: sau này có thể chuyển BM25 sang **Weaviate hybrid** để gọn hệ thống.)

**Q:** Có cần GPU cho Weaviate?
**A:** **Không.** GPU RTX 4060 dùng cho **BGE reranker/PaddleOCR** trong app của bạn, không phải trong Weaviate.

**Q:** Nếu sau này chuyển môi trường Production?
**A:** Sử dụng Weaviate Cloud (managed) hoặc tự chạy cluster/K8s; thêm auth, snapshot/backup định kỳ.

---

**Chủ sở hữu:** @you
**Liên quan:** ADR-2025-10 (citation accuracy), BGE v2-m3 reranker, JSON-with-evidence + CiteFix.
