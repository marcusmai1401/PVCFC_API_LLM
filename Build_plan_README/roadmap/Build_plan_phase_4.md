# PHASE 4 — TỐI ƯU, BẢO MẬT & CHUYỂN GIAO (RELEASE)

Tài liệu pha 4 cho PVCFC RAG (V1). Mục tiêu: tối ưu hiệu năng/chi phí dựa trên kết quả Phase 3; hardening bảo mật; thiết lập CI/CD; đóng gói triển khai; quan sát hoá (metrics/logs/tracing); backup/restore index; runbook vận hành & đào tạo.

---

## 1) Mục tiêu & Kết quả mong đợi

- Cải thiện latency/cost mà giữ hoặc nâng chất lượng (faithfulness/citation).
- Củng cố bảo mật: secrets, SBOM & scan CVE, image hardening, rate-limit/headers/log retention.
- CI/CD hoàn chỉnh: lint/test → build → scan → push → deploy (compose/helm); release notes & changelog.
- Sẵn sàng vận hành: dashboards/alerts, backup/restore index, runbook & training.

---

## 2) Phạm vi & Không phạm vi

- Có (Phase 4):
  - Ablation/A-B tối ưu tham số pipeline; token saving.
  - Bảo mật: secrets manager, SBOM, CVE scan, secret scan, headers, log retention; non-root containers.
  - CI/CD: GH Actions/GitLab CI; image scan; SBOM; deploy compose/helm; release notes.
  - Monitoring/Alerting: Prometheus, Grafana; OTel tracing.
  - Backup/Restore: artifacts/index & manifests.
  - Runbook & đào tạo người dùng/vận hành.
- Không (để roadmap):
  - Chức năng mới lớn ngoài phạm vi V1 (bbox bắt buộc, database lớn, normalized PDF quy mô lớn, Lucene/IVF-PQ ở prod nếu chưa cần).

---

## 3) Tối ưu hiệu năng & chi phí (Ablation/A-B)

- Tham số cần khảo sát:
  - MAX_CONTEXT: 6/8/10/12/20
  - TOP_RERANK: 10/20/30/40
  - HyDE: on/off; số biến thể 0/1/2
  - Prompts: ngắn/gọn vs chi tiết; chỉ dẫn citation cứng/linh hoạt
  - Degrade policy: ngưỡng timeout/retry; BM25_K_WHEN_DEGRADE; RERANK_TOP_N_WHEN_DEGRADE
- Quy trình A-B:
  - Lấy 120–150 QA từ Golden (Phase 3), chia stratified theo doc_category/type/difficulty.
  - Chạy công cụ ablation → bảng: Faithfulness, Citation precision/recall, Recall@10, Latency p50/p95, Cost.
  - Chọn cấu hình cân bằng theo trọng số (ví dụ 40% Faithfulness, 25% Citation, 20% Recall@10, 10% Latency, 5% Cost).
- Mục tiêu tối ưu (gợi ý):
  - + ≥ 0.05 điểm Faithfulness trung bình hoặc giảm ≥ 10% p95 latency.
  - Giữ Citation precision ≥ 95%.

---

## 4) Tiết kiệm token & RAM

- Nén context: loại trùng, tóm tắt parent dài, cắt phần không liên quan.
- Giảm MAX_CONTEXT khi rerank score cao (dynamic K).
- Cache kết quả retrieve/rerank 10–30 phút; cache answer cho câu tĩnh (không PII; TTL/etag) nếu cần.
- Memory-map FAISS (nếu hỗ trợ) & warm-up cache với top queries.

---

## 5) Bảo mật & Tuân thủ

- Secrets & cấu hình:
  - Prod dùng secrets manager (Vault/SOPS/Cloud Secret Manager); không commit secrets.
  - Không log secrets; mask Authorization/api_key/cookie.
- Supply chain & SBOM:
  - Khoá phiên bản; sinh SBOM (cyclonedx-py); scan image (Trivy) + pip-audit.
  - Chặn merge nếu có High/Critical CVE (policy; ngoại lệ cần phê duyệt).
- Hardening container:
  - Dockerfile multi-stage; base python:3.11-slim hoặc distroless; non-root; readOnlyRootFilesystem; drop capabilities.
  - Healthcheck liveness/readiness `/healthz`.
- Network & API:
  - Rate-limit & throttling; CORS tối thiểu; security headers: X-Content-Type-Options, X-Frame-Options, Referrer-Policy.
  - Input validation Pydantic; giới hạn kích thước payload; 4xx/5xx monitoring.
- Data governance:
  - Log retention 90 ngày; ẩn snippet dài; không lưu ngữ cảnh có PII nhạy cảm.
  - RBAC (nếu có) cho index & manifests; audit trail thao tác admin.

---

## 6) CI/CD

- Pipeline (gợi ý):
  - Lint/test → build image → SBOM + Trivy scan → push registry (stage) → e2e smoke → manual approval → deploy prod.
  - Tag image theo semver + commit_sha; release notes + CHANGELOG.
- Secrets qua OIDC/Secrets Manager; không để secrets trong repo.
- Secret scan ở CI: gitleaks/detect-secrets trên PR, chặn leak trước khi merge.

---

## 7) Đóng gói & Triển khai

- Docker Compose (stage):
  - services: api (pvcfc/rag-api:VERSION), redis (tùy chọn), otel collector, prometheus, grafana.
  - Volumes: mount `artifacts/index` để persist FAISS/BM25; cấu hình ENV từ secrets.
- Helm (tuỳ chọn sau compose):
  - Chart: Deployment + Service + HPA; ConfigMap/Secret; Ingress + TLS.

---

## 8) Monitoring & Alerting

- Prometheus metrics: latency tổng/thành phần, cache hit rate, error 4xx/5xx, rate-limit, token usage.
- Alert rules (gợi ý):
  - p95_latency > 8s (5m), error_rate > 2% (5m), model_timeout surge, cache_hit < 10% (30m).
- Dashboards Grafana: tổng quan RAG, chi tiết step, heatmap lỗi theo endpoint, traffic theo doc_category.
- Tracing OTel: trace end-to-end; log correlation qua trace_id.

---

## 9) Backup & Phục hồi

- Sao lưu: `artifacts/index/faiss`, `artifacts/index/bm25`, `artifacts/ingestion/manifests/` hàng ngày; gắn `index_version`.
- Khôi phục: script `tools/restore_index.py`; kiểm checksum; smoke test 10 truy vấn.
- Lưu `index_vX.Y.Z` để rollback nhanh.

---

## 10) Runbook & Đào tạo

- Runbook Incident:
  - Checklist sự cố: API 5xx, model timeout/quota, index hỏng, cache chết, secrets lộ.
  - Quy trình chẩn đoán: healthz, logs, tracing, Prometheus; khôi phục index.
  - Ma trận mức độ (sev1/2/3) + RACI.
- Tài liệu kỹ thuật: kiến trúc; luồng dữ liệu; định dạng citations; schema metadata; default & override cấu hình.
- Hướng dẫn người dùng: cách gọi /ask, /locate, /report; template câu hỏi tốt; giới hạn hệ thống; cách báo lỗi.
- Đào tạo: kiến trúc & vận hành (2 giờ) + API & UI demo (1.5 giờ); biên bản nghiệm thu.

---

## 11) Định nghĩa Hoàn thành (DoD)

- Báo cáo ablation/A-B: cải thiện ≥ 0.05 Faithfulness hoặc giảm ≥ 10% p95 latency; Citation precision vẫn ≥ 95%.
- Docker image cứng hoá (non-root, scan pass: không High/Critical CVE mở); compose chạy ổn; monitoring & alert hoạt động.
- CI/CD trơn tru; SBOM tự động; scan bắt buộc trước merge.
- Backup/restore index chạy thành công; smoke retrieval pass.
- Runbook & tài liệu bàn giao hoàn chỉnh; đào tạo xong, có biên bản nghiệm thu.

---

## 12) Phụ lục (tham khảo)

- `.env` Prod gợi ý (tối giản, không chứa secrets thực):
```ini
APP_ENV=prod
API_PORT=8000
LOG_LEVEL=INFO
LLM_MODEL_HEAVY=gemini-2.5-pro
LLM_MODEL_LIGHT=gemini-2.5-flash
EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=gemini-embedding-001
MAX_CONTEXT=8
TOP_RERANK=20
VISION_PAGE_SELECTOR_ENABLED=true
TEXT_RANGE_SCAN_ENABLED=false
RETRIEVAL_ALLOW_BM25_ONLY_FALLBACK=true
BM25_K_WHEN_DEGRADE=80
RERANK_TOP_N_WHEN_DEGRADE=50
RATE_LIMIT_RPM=60
RATE_LIMIT_BURST=20
RETRIEVE_CACHE_TTL_MIN=10
```
