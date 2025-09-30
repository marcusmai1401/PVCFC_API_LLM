# Nâng cấp embedding sang Gemini 768D — Kiến trúc, Cấu hình, Quy trình triển khai, và Kết quả chạy

Tài liệu này mô tả chi tiết toàn bộ quá trình chuyển đổi hệ thống embedding sang model Gemini (gemini-embedding-001), các thay đổi kiến trúc/cấu hình, cách triển khai, và kết quả thực thi thực tế. Đồng thời, phần cuối có danh sách câu hỏi mở để làm rõ các nội dung chưa xác định.

---

## 1) Bối cảnh và mục tiêu

- Trước đây: hệ thống embedding chưa có cấu hình đầy đủ cho Gemini; định hướng ban đầu hướng tới 1536 chiều (1536D).
- Thực tế API: qua kiểm thử trực tiếp, các model embedding khả dụng của Gemini hiện trả về tối đa 768 chiều (768D). Do đó, chúng tôi điều chỉnh cấu hình và toàn bộ pipeline để dùng 768D một cách nhất quán.
- Mục tiêu:
  - Chuẩn hóa alias model và thông số đầu ra (output_dim) theo khả năng hỗ trợ thực tế của Gemini.
  - Tối ưu hiệu năng bằng micro-batching + ước lượng token, xử lý bất đồng bộ với retry + exponential backoff, và cache embedding bằng SQLite.
  - Cải thiện khả năng quan sát (observability) bằng log/metric và quarantine logging các case lỗi (không sử dụng vector zero làm fallback).
  - Cập nhật tool build FAISS để đọc biến môi trường mới và in metric chi tiết, tạo FAISS index ổn định, nhất quán với 768D.

---

## 2) Các thay đổi chính (Summary)

A. Model alias mapping và output dimensionality
- Hỗ trợ alias `gemini-embedding-001` → resolve sang `models/embedding-001` của Gemini.
- Truyền tham số `output_dim` (trước nhắm 1536D, nay chuẩn 768D sau kiểm chứng thực tế API).

B. Micro-batching với ước lượng token
- Chia mẻ (micro-batch) dựa trên `batch_size` và giới hạn `max_tokens` để tối ưu qua API.
- Nhật ký cho biết số micro-batch tạo ra từ tổng số văn bản.

C. Bất đồng bộ + Retry/Exponential backoff + Rate limit handling
- Thực thi embedding theo lô bất đồng bộ (concurrency cấu hình được).
- Cơ chế retry có exponential backoff; xử lý các lỗi 429 (rate limit) và lỗi tạm thời.

D. Cache SQLite cho embedding + metric cache hit
- Lưu embedding theo khóa nội dung đã chuẩn hóa để tránh gọi API lặp lại.
- Ghi nhận metric cache hit/miss.

E. Quarantine logging cho case lỗi (không dùng zero vector)
- Bất kỳ văn bản không embedding được sẽ đi vào quarantine log (`.jsonl`) để phân tích và re-try sau.

F. Cập nhật FAISS build tool
- Đọc biến môi trường embedding mới (model, output_dim, batch_size, concurrency, max_tokens, task_type…).
- In metric đầy đủ (số văn bản, micro-batches, kích thước index, v.v.).

G. Cập nhật .env và test script
- Cung cấp file mẫu `.env` cho Gemini; ban đầu đặt 1536D nhưng đã điều chỉnh thành 768D khi xác nhận giới hạn API.
- Viết script kiểm thử nhỏ `tools/test_embedding_implementation.py` để xác minh dim, cache hit, quarantine và metric cơ bản.

---

## 3) Cấu hình môi trường (.env) đề xuất cho Gemini (768D)

Ví dụ cấu hình (mang tính tham khảo — không commit secrets):

```
# Provider + Model
EMBED_PROVIDER=gemini
EMBED_MODEL=gemini-embedding-001
EMBED_TASK_TYPE=RETRIEVAL_DOCUMENT

# Output dimension (đã xác thực hiện tại: tối đa 768)
EMBED_OUTPUT_DIM=768

# Hiệu năng
EMBED_BATCH_SIZE=256
EMBED_CONCURRENCY=8
EMBED_MAX_TOKENS=20000

# API key (thiết lập qua secret manager / env, KHÔNG hardcode)
GEMINI_API_KEY={{GEMINI_API_KEY}}

# Cache & Quarantine
EMBED_CACHE_PATH=artifacts/ingestion/cache/embeddings.sqlite
EMBED_QUARANTINE_PATH=artifacts/ingestion/quarantine.jsonl

# Log level/metrics (tùy hệ thống logging)
LOG_LEVEL=INFO
```

Lưu ý:
- Nếu đang dùng Pydantic Settings cho cấu hình: đã thay đổi để bỏ chặn/cho phép các biến env “extra” (như EMBED_OUTPUT_DIM, EMBED_BATCH_SIZE…) nhằm tránh lỗi validation.
- Trong code, có thể dùng `os.getenv` cho phần biến env mở rộng/không được Pydantic map sang field rõ ràng.

---

## 4) Cập nhật trong mã nguồn (kiến trúc dịch vụ embedding)

Dưới đây là các điểm cập nhật đáng chú ý trong lớp dịch vụ embedding (ví dụ: `UniversalEmbeddingService`):

- Alias model + init Gemini client
  - Hỗ trợ alias `gemini-embedding-001` và resolve sang `models/embedding-001`.
  - In log: model thực tế khởi tạo và `output_dim` đang sử dụng.

- Truyền tham số output_dim và kiểm tra hình dạng kết quả
  - Với Gemini hiện tại, API trả tối đa 768D. Dịch vụ đảm bảo kiểm tra kích thước vector nhận về để cảnh báo mismatch (nếu có).

- Micro-batching + ước lượng token
  - Hàm build micro-batches dựa trên `batch_size` và `EMBED_MAX_TOKENS`.
  - Log số micro-batch tạo ra trên tổng số văn bản đầu vào.

- Bất đồng bộ + retry/backoff + rate limit
  - Thực thi embedding bằng async với `concurrency` cấu hình được.
  - Retry với exponential backoff khi gặp lỗi tạm thời (bao gồm 429).

- SQLite cache
  - Khởi tạo DB cache nếu chưa tồn tại.
  - Lưu và đọc cache theo khóa nội dung (đã chuẩn hóa) để tránh trùng lặp.
  - Ghi log cache hit/miss, tổng hợp metric cache.

- Quarantine logging
  - Ghi các input lỗi vào `quarantine.jsonl` thay vì tạo zero vector.

- Sửa lỗi placement method
  - Đưa các private method như `_init_cache_db` và `_add_to_quarantine` vào bên trong class để tránh not-bound method.

---

## 5) Cập nhật FAISS index builder

- Đọc các biến môi trường embedding nêu trên (model, output_dim, batch_size, concurrency, max_tokens, task_type…).
- Log cấu hình và tiến trình: số tài liệu, kích thước batch, concurrency, số micro-batch, kích thước index, đường dẫn output, v.v.
- Xây dựng FAISS index tương thích 768D.

Ví dụ lệnh chạy (PowerShell):

```
python tools\build_faiss_local.py \
  --bm25-dir "artifacts\ingestion\bm25" \
  --faiss-dir "artifacts\ingestion\faiss_test" \
  --max-memory-gb 8
```

---

## 6) Kiểm thử và xác minh

### 6.1 Kiểm thử đơn vị/tích hợp nhỏ
- Script: `tools/test_embedding_implementation.py` (dataset 10 texts)
- Mục tiêu kiểm thử:
  - Xác minh kích thước embedding là 768.
  - Kiểm tra cache hit hoạt động.
  - Kiểm tra quarantine log khi có lỗi.
  - In một số metric như thời gian/throughput cơ bản.

### 6.2 Chạy end-to-end build FAISS
- Thời gian chạy: bắt đầu ~ 04:03:41, kết thúc ~ 04:27:09 (~23.5 phút).
- Tham số log chính:
  - Provider/Model: gemini (gemini-embedding-001 → models/embedding-001).
  - Output dimension: 768D.
  - Batch size: 256.
  - Concurrency: 8.
  - Max tokens per request: 20,000.
  - Số micro-batch: 135 (từ 27,306 văn bản).

- Đầu vào:
  - Nguồn BM25: `artifacts/ingestion/bm25`.
  - Tổng văn bản cần embedding: 27,306.

- Đầu ra (thư mục `artifacts/ingestion/faiss_test`):
  - `faiss.index` ~ 83,884,077 bytes (04:27:09).
  - `metadatas.json` ~ 9,978,798 bytes (04:27:09).
  - `texts.json` ~ 6,862,011 bytes (04:27:09).
  - Số phần tử trong `texts.json` và `metadatas.json`: 27,306.

- Kiểm tra kích thước index theo lý thuyết:
  - 27,306 vectors × 768 dims × 4 bytes/float = 83,884,032 bytes.
  - File thực tế 83,884,077 bytes (chênh lệch do header/overhead) → hợp lệ.

- Cache embedding (SQLite):
  - File: `artifacts/ingestion/cache/embeddings.sqlite` ~ 53,751,808 bytes (~51.3 MiB).
  - Bảng: `cache`.
  - Số bản ghi: 12,672.
  - Ghi chú: Số bản ghi nhỏ hơn tổng văn bản vì trùng lặp nội dung (đã chuẩn hóa) hoặc cache đã có sẵn một phần từ lần chạy trước.

- Quarantine:
  - Có file `artifacts/ingestion/quarantine.jsonl` (~90.4 KB) với `LastWriteTime` 02:06:22 (trước lần chạy end-to-end này); không xuất hiện bản ghi quarantine mới trong lần build nêu trên.

- Lưu ý log:
  - Trong builder có dòng `Model resolved: None` (mang tính hiển thị), nhưng trong service đã resolve đúng sang `models/embedding-001` (được log ở bước khởi tạo model). Không ảnh hưởng chức năng.

---

## 7) Khuyến nghị vận hành và tối ưu

- Concurrency/Batch size:
  - Với Paid Tier 1 của Gemini, `EMBED_CONCURRENCY=8` và `EMBED_BATCH_SIZE=256` hoạt động ổn trong lần chạy này. Khi dữ liệu tăng mạnh hoặc quota thay đổi, cân nhắc tinh chỉnh để tránh 429.

- Token budget:
  - `EMBED_MAX_TOKENS=20000` phù hợp cho đa số trường hợp; nếu văn bản rất dài, cân nhắc phân mảnh sớm ở bước tiền xử lý để giảm retry.

- Quản lý secrets:
  - Thiết lập `GEMINI_API_KEY` qua secret manager/CI runner env. Không ghi trực tiếp vào repo hoặc log.

- Observability:
  - Khuyến nghị thêm metric: throughput (docs/s), tổng token, tỷ lệ cache hit, tỷ lệ retry, số lượng 429, 5xx, chi phí ước lượng.
  - Giảm `DEBUG` trong production để tối ưu I/O log.

- Lịch re-index:
  - Xem xét lịch re-index định kỳ và chính sách làm tươi (refresh) để đảm bảo chất lượng tìm kiếm khi nội dung thay đổi nhanh.

---

## 8) Ảnh hưởng tới các thành phần khác

- Kích thước vector chuẩn 768D:
  - Tất cả chỗ dùng embedding/FAISS phải đồng bộ 768D. Nếu có code/ML pipeline trước đây giả định 1536D, cần cập nhật ngay.

- Chất lượng tìm kiếm:
  - Thiếu bộ benchmark nội bộ để so sánh chất lượng trước/sau (1536D kỳ vọng vs 768D thực tế). Đề xuất chạy A/B hoặc offline eval.

- Truy vấn vs tài liệu (task_type):
  - Hiện đang đặt `EMBED_TASK_TYPE=RETRIEVAL_DOCUMENT`. Nếu pipeline query cần embedding khác (ví dụ `RETRIEVAL_QUERY`), cân nhắc tạo flow riêng cho query embedding hoặc unify cấu hình.

---

## 9) Hướng dẫn tái chạy nhanh (tham khảo)

1) Đảm bảo đã thiết lập `GEMINI_API_KEY` dưới dạng biến môi trường runtime (không commit vào repo).
2) Kiểm tra/cập nhật `.env` theo mẫu ở mục 3.
3) Chạy build FAISS:

```
python tools\build_faiss_local.py \
  --bm25-dir "artifacts\ingestion\bm25" \
  --faiss-dir "artifacts\ingestion\faiss_test" \
  --max-memory-gb 8
```

4) Kiểm tra kết quả output trong `artifacts/ingestion/faiss_test` và cache/quarantine trong `artifacts/ingestion`.

---

## 10) Câu hỏi mở/chưa rõ cần xác nhận

1) Mục tiêu dài hạn về chiều embedding:
   - Có yêu cầu cố định 1536D trong tương lai không? Nếu Gemini vẫn giới hạn 768D, có cần phương án thay thế (model khác) để đạt 1536D?

2) Chuẩn hóa task type cho query:
   - Có cần phát sinh embedding riêng cho truy vấn (`RETRIEVAL_QUERY`) hay dùng cùng `RETRIEVAL_DOCUMENT` là đủ? Chiến lược nào cho hai loại embedding này nếu muốn tối ưu độ liên quan?

3) Chính sách concurrency/batch-size theo quota thực tế:
   - Mức concurrency/batch-size mục tiêu ở môi trường production là bao nhiêu? Có cần auto-tuning dựa trên tỷ lệ 429?

4) Observability mở rộng:
   - Có muốn hiển thị thêm metric chi phí (ước lượng), tổng token, QPS và dashboard hoá trên hệ thống giám sát hiện có không?

5) Quarantine lifecycle:
   - Quy trình xử lý lại các record trong quarantine như thế nào? Tự động re-try theo lịch hay điều tra thủ công? Thời gian lưu giữ/quy mô tệp?

6) Cache policy:
   - Chính sách dọn dẹp/expire cache embedding? Có cần kiểm soát kích thước DB khi dữ liệu tăng trưởng nhanh không?

7) Tương thích ngược với client/service khác:
   - Có service nào đang giả định kích thước vector khác 768D hoặc dùng index cũ không? Kế hoạch cutover/rollback?

8) Kiến trúc FAISS:
   - Có nhu cầu chuyển từ Flat index sang IVF/PQ/HNSW để tối ưu tốc độ/footprint khi dữ liệu tăng lớn? Mức recall mục tiêu là bao nhiêu?

9) Chuẩn hoá log "Model resolved: None":
   - Có muốn sửa thông điệp log này trong builder để phản ánh model đã resolve rõ ràng nhằm giảm nhiễu khi đọc log?

10) Tiền xử lý văn bản:
    - Có yêu cầu chuẩn hoá/cleaning/chunking văn bản trước khi embed (loại bỏ boilerplate, xác định chunk size/token) để tối ưu chất lượng và giảm retry?

---

## 11) Kết luận

- Hệ thống embedding đã chuyển sang Gemini với 768D, được kiểm chứng thực tế và đồng bộ end-to-end.
- Pipeline hiện hỗ trợ alias model, micro-batching, bất đồng bộ + retry/backoff, cache SQLite, quarantine logging và build FAISS với log/metric chi tiết.
- Lần chạy e2e đã tạo index đúng kích thước, số phần tử đầy đủ, không phát sinh quarantine mới. Đây là nền tảng ổn định để mở rộng.
- Cần xác nhận các câu hỏi mở ở mục 10 để chốt cấu hình production, chiến lược đánh giá chất lượng và lộ trình tối ưu tiếp theo.
