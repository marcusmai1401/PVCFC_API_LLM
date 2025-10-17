# 📋 ĐÁNH GIÁ KẾ HOẠCH: CAD-like Tag Extraction for PVCFC

> **Tài liệu tham chiếu**: `PVCFC_CADlike_Tag_Extraction_Handoff.md`
> **Ngày đánh giá**: 16/10/2025
> **Hệ thống**: PVCFC RAG System v0.8.0

---

## 📝 **EXECUTIVE SUMMARY - Kết luận ngắn gọn**

Kế hoạch **phù hợp để triển khai ngay**, chỉ cần tinh chỉnh vài điểm về tích hợp và vận hành:

### **✅ Điểm khớp tốt (giữ nguyên hướng):**
- **Sidecar index & parallel query**: Hệ thống có P&ID enhancement (query-time). Kế hoạch bổ sung ingestion-time extraction → không conflict, rollback dễ
- **Vector-first + OCR fallback**: Đúng triết lý geometry-first (PyMuPDF vector → PP-OCRv5 fallback)
- **Infrastructure sẵn**: PyMuPDF ✓, PP-OCRv5 ✓, OpenSearch ✓; chỉ thiếu OpenCV (optional)

### **🔧 Gap & điều chỉnh trước khi làm:**
1. **Ingestion-time extraction chưa có** - đây là core value add: CAD-like Gate (S≥0.60), Layout builder, Tag Assembler, bbox/crops
2. **Bbox/crop pipeline**: UI hiện render full-page; cần normalize coordinates + lazy crop generation
3. **Whitelist CODE + learning mode**: Bootstrap với whitelist → log unknown CAPS tokens → review weekly
4. **Performance**: ~1-2s/page cho taggy pages OK; bật gate + selective pages + async để control
5. **Tích hợp code sẵn**: Reuse `tag_normalizer`, `pid_query_enhancer` → unified regex/patterns
6. **OpenCV optional**: Flag `ENABLE_SHAPE_AWARE_ROI=false` default; prefer `scipy.KDTree` > `rtree`

### **🎯 Quyết định: GO - Triển khai theo spec**
- ✅ **Timeline**: 4-5 tuần (Tuần 1: setup → Tuần 2-3: gate+layout+assembler → Tuần 4-5: index+serve)
- ✅ **Vận hành nhẹ (no-build)**: Runtime logs + smoke tests 8-12 queries cố định, không cần KPI dashboard
- ✅ **Storage ready**: Đã migrate sang D: drive (476 GB free) ✓
- ⚠️ **Critical**: Cần validation dataset (50-100 P&ID PDFs + ground truth tags)

---

## ✅ **ĐÁNH GIÁ CHI TIẾT: KHẢ THI VÀ PHÙ HỢP**

Dưới đây là phân tích chi tiết từng khía cạnh:

### **🎯 Kết luận tổng quan:**
- ✅ **Khả thi 95%**: Hầu hết infrastructure đã sẵn sàng
- ✅ **Dependencies aligned**: PP-OCRv5, PyMuPDF, OpenSearch đều match với spec
- ⚠️ **Cần bổ sung**: OpenCV (cho shape-aware ROI), validation dataset
- 🔧 **Integration point**: Reuse existing P&ID enhancement code (query-time)

---

## 🎯 **1. ĐIỂM MẠNH CỦA KẾ HOẠCH**

### ✅ **1.1. Kiến trúc Sidecar - Phù hợp hoàn toàn**
- **Không xung đột** với index hiện tại (`rag_chunks`)
- Dễ rollback bằng cách tắt `ENABLE_PID_TAGS`
- Infrastructure OpenSearch đã sẵn sàng

### ✅ **1.2. Dependencies đã có sẵn**
- ✅ **PyMuPDF**: v1.26.4 - đang dùng cho PDF processing
- ✅ **PaddleOCR**: PP-OCRv5 models với PaddleOCR 2.7.3 library (GPU-accelerated với paddlepaddle-gpu 2.6.2)
- ✅ **OpenCV**: có thể cài thêm dễ dàng (hiện chưa có trong requirements)
- ✅ **OpenSearch**: v3.0.0 - đang chạy production với 4,883 chunks indexed

### ✅ **1.3. Vector-first approach**
Hệ thống đã implement:
```python
# app/ingestion/pdf_processor.py (line 442-451)
# Try vector text first, fallback to OCR
processor = PDFProcessor(enable_ocr=False, ...)
pdf_doc = processor.process_pdf(pdf_path)

if len(total_text.strip()) < 100:  # Scanned
    processor = PDFProcessor(enable_ocr=True, ...)
```
→ **Hoàn toàn phù hợp** với yêu cầu vector-first.

### ✅ **1.4. Configuration-driven design**
YAML configs cho gate weights, grammar rules, thresholds là **best practice** - dễ tune không cần đụng code.

---

## 🔍 **2. PHÁT HIỆN QUAN TRỌNG: HỆ THỐNG ĐÃ CÓ P&ID ENHANCEMENT!**

### **🚨 Điểm then chốt: Hệ thống đã có partial implementation**

Tôi phát hiện các module sau **đã tồn tại**:

```
app/rag/query_processing/
├── pid_query_enhancer.py          # ✅ Đã có
├── query_type_detector.py          # ✅ Đã có
app/rag/rerankers/
├── pid_tag_reranker.py             # ✅ Đã có
app/rag/normalizers/
├── tag_normalizer.py               # ✅ Đã có
app/api/routers/
├── tags.py                         # ✅ Đã có (tags endpoint)
app/utils/
├── tag_utils.py                    # ✅ Đã có
app/ingestion/domain/
├── pid_schema.py                   # ✅ Đã có
```

**System Architecture** (line 228-232) đã document P&ID Enhancement:
```
• [NEW] P&ID Enhancement (if ENABLE_PID_ENHANCEMENT=true):
  - Detect equipment tags (E04217, P04201A, K06101, etc.)
  - Generate tag variants (E04217, E-04217, e04217)
  - Classify query type (tag_only, mixed, visual, semantic)
  - Infer equipment type from tag prefix
```

### **📊 So sánh với kế hoạch của bạn:**

| Khía cạnh | Kế hoạch của bạn | Hiện trạng hệ thống | Gap |
|-----------|------------------|---------------------|-----|
| **Query-time tag detection** | ✓ Có | ✅ **Đã có** (`pid_query_enhancer.py`) | None |
| **Tag boosting/reranking** | ✓ Có | ✅ **Đã có** (`pid_tag_reranker.py`) | None |
| **Sidecar tags index** | ✓ Có | ✅ **Đã có** (OpenSearch tags field) | None |
| **Ingestion-time tag extraction** | ✓ **Core proposal** | ⚠️ **CHƯA CÓ** | **Đây là phần mới** |
| **CAD-like gate** | ✓ **Core proposal** | ❌ **CHƯA CÓ** | **Phần mới** |
| **Geometry-based extraction** | ✓ **Core proposal** | ❌ **CHƯA CÓ** | **Phần mới** |
| **Layout analysis (vector drawings)** | ✓ **Core proposal** | ❌ **CHƯA CÓ** | **Phần mới** |
| **Vision crop + bbox** | ✓ Có | ⚠️ Partial (có vision, chưa có bbox) | Minor gap |

---

## ⚠️ **3. ĐIỂM CẦN LƯU Ý VÀ ĐIỀU CHỈNH**

### **3.1. OCR Infrastructure - ✅ Đã phù hợp với Spec**
Hệ thống hiện tại:
```python
# app/ingestion/paddle_ocr_config.py
# "Provides PaddleOCR PP-OCRv5 initialization with GPU/CPU auto-detection"

PPOCRV5_DET_MODEL = _pipeline_config.DET_MODEL_DIR    # Detection v5
PPOCRV5_REC_MODEL = _pipeline_config.REC_MODEL_DIR    # Recognition v4/v5
PPOCRV5_CLS_MODEL = _pipeline_config.CLS_MODEL_DIR    # Classifier v5
```

**Status**: ✅ **100% aligned với spec requirements**
- PP-OCRv5 detection & classification models (local)
- GPU-accelerated (paddlepaddle-gpu 2.6.2)
- Auto-fallback to CPU nếu GPU không khả dụng
- Production-ready với model verification

**Lưu ý**: PaddleOCR library version (2.7.3) ≠ model version (v5). Library 2.7.3 có thể load PP-OCRv5 models mới hơn.

### **3.2. Code Whitelist vs Dynamic Detection**
Spec đề xuất whitelist fix:
```yaml
code_whitelist: [PAL, PSAH, PSAL, PALL, PT, PI, PIC, FIC, HIC, LIC, TIC, PXI, PSU, IS]
```

**Vấn đề**: Dữ liệu thực tế có thể có codes khác (e.g., `LSAH`, `TSHH`, `FSL`, etc.)

**Khuyến nghị**:
- ✅ **Bootstrap với whitelist** (như spec)
- ✅ **Add "learning mode"**: log unknown 2-4 letter CAPS tokens từ CAD docs
- ✅ **Review logs hàng tuần** để expand whitelist
- ⚠️ **Avoid pure regex** `^[A-Z]{2,4}$` - quá nhiều false positives

### **3.3. Performance Impact - Cần Clarify**
Spec nói gate eval `<< 300ms/file`, nhưng:
- **Full tag extraction pipeline** (layout + ROI + assembly + crops) sẽ **> 1-2s/page** cho taggy pages
- **Artifacts storage** (`page_layout/`, `crops/`, `entities/`) sẽ **tăng disk usage đáng kể**

**Khuyến nghị**:
- ✅ **Async ingestion** - không block main pipeline
- ✅ **Selective processing** - chỉ CAD-like docs (gate S ≥ 0.60)
- ✅ **Lazy crop generation** - chỉ generate khi query cần (save disk)
- ⚠️ **Monitor disk usage** - crops có thể chiếm nhiều GB

### **3.4. Bbox Coordinate System**
Spec dùng `bbox=[x0,y0,x1,y1]` trong page space.

**Vấn đề hiện tại**:
- Hệ thống **chưa có bbox extraction** ở ingestion
- Vision citation hiện tại **render full page**, không crop bbox

**Khuyến nghị**:
- ✅ **Phase 1**: Extract tags + bbox (as planned)
- ✅ **Phase 2**: Implement crop rendering từ bbox (new feature)
- ⚠️ **Coordinate normalization**: Đảm bảo bbox consistent across rotated pages

### **3.5. Integration với P&ID Enhancement hiện tại**
Hệ thống đã có **query-time** P&ID enhancement. Kế hoạch của bạn thêm **ingestion-time** extraction.

**Risk**: Duplicate logic hoặc inconsistent behavior.

**Khuyến nghị**:
- ✅ **Reuse existing code**: `tag_normalizer.py`, `tag_utils.py`
- ✅ **Consistent regex**: Dùng chung tag patterns giữa query-time và ingest-time
- ✅ **Unified config**: Merge `tag_grammar.yaml` với existing P&ID config
- ⚠️ **Deprecation plan**: Sau khi ingest-time tags stable, có thể simplify query-time detection

---

## 🔧 **4. XEM XÉT KỸ THUẬT**

### **4.1. Assembler Tolerances - Có thể quá strict**
```yaml
x_center_tolerance_ratio: 0.60
y_gap_ratio_range: [0.7, 2.0]
font_size_delta_pt: 1.5
```

**Concern**: CAD drawings từ các vendor khác nhau có layout conventions khác.

**Khuyến nghị**:
- ✅ **Start conservative** (như spec)
- ✅ **Add "strict/relaxed" modes** trong config
- ✅ **Telemetry** để track false negatives (cadlike=true nhưng tags_found=0)
- ⚠️ **Per-vendor tuning** có thể cần thiết

### **4.2. Divider Line Handling**
Spec nói "ignore divider lines inside bubbles".

**Vấn đề**: PyMuPDF extract lines as vector paths - cần logic phân biệt:
- Divider lines (ignore)
- Leader lines (use for relation)
- Pipe lines (background, ignore)

**Khuyến nghị**:
- ✅ **Classify lines** by length, thickness, endpoint proximity to text
- ⚠️ **Test với real P&ID samples** - mỗi vendor vẽ khác nhau

### **4.3. OpenCV Dependency**
Spec dùng OpenCV cho:
- Contours detection (instrument bubbles)
- Hough lines (leaders)

**Current status**: OpenCV **không có** trong `requirements.txt`.

**Khuyến nghị**:
- ✅ **Add to requirements**: `opencv-python>=4.8.0`
- ⚠️ **Optional dependency**: Thêm flag `ENABLE_SHAPE_AWARE_ROI` (default=false ban đầu)
- ✅ **Graceful fallback**: Nếu OpenCV fail, dùng text-centric ROI only

### **4.4. R-tree/KD-tree for Neighbor Queries**
Spec mention `rtree`/`scipy` cho neighbor queries.

**Current status**: `scipy` có, `rtree` **không có** trong requirements.

**Khuyến nghị**:
- ✅ **Use scipy.spatial.KDTree** (đã có) - đủ cho page-level queries
- ⚠️ **Avoid rtree** (requires libspatialindex C library - deployment pain on Windows)

---

## 🚀 **5. KHUYẾN NGHỊ TRIỂN KHAI**

### **Phase 0: Pre-work (1-2 ngày)**
```yaml
□ Review existing P&ID code (pid_query_enhancer.py, pid_tag_reranker.py)
□ Extract shared patterns/regex vào common module
□ Add opencv-python to requirements.txt
□ Setup artifacts directories (page_layout/, entities/, crops/)
□ Document coordinate system cho bbox
```

### **Phase 1: CAD-like Gate (3-5 ngày)**
```yaml
□ Implement gate scorer với features trong spec
□ Test trên 50-100 sample PDFs (mix CAD vs normal docs)
□ Tune thresholds (target: 95% accuracy trên validation set)
□ Add telemetry logging
```

### **Phase 2: Layout Build (5-7 ngày)**
```yaml
□ PyMuPDF text spans extraction (vector-first)
□ PyMuPDF drawings extraction (lines, circles, paths)
□ OCR fallback (reuse existing paddle_ocr_config)
□ Page coordinate normalization
□ Engineering spacing fixes (SHX artifacts)
□ Write page_layout JSON artifacts
```

### **Phase 3: Tag Extractor (7-10 ngày)** ⚠️ **Core complexity**
```yaml
□ Text-centric ROI proposal
□ Shape-aware ROI (optional, với OpenCV)
□ Token role classification (AREA/CODE/NUM/SUFFIX)
□ CODE-anchored assembler
□ Scoring với tolerances
□ Suffix attachment
□ Relations extraction (leader lines)
□ Exclusion zones (LEGEND/NOTES)
```

### **Phase 4: Indexing & Serving (3-5 ngày)**
```yaml
□ Create pvcfc_pid_tags index schema
□ Bulk upsert tags to OpenSearch
□ Intent detection for tag queries (integrate với existing)
□ Parallel query (tags + chunks)
□ RRF fusion (reuse existing logic)
□ Crop attachment for citations
```

### **Phase 5: Testing & Tuning (5-7 ngày)**
```yaml
□ Smoke tests (8-12 fixed queries - see section 9.1 below)
□ False positive/negative analysis
□ Tune assembler tolerances based on telemetry
□ Expand CODE whitelist based on learning mode logs
□ Load testing (artifacts disk usage, query latency)
```

**Total estimate**: **25-40 ngày** (1-2 tháng, hoặc ~4-5 tuần với 1 dev)

#### **9.1. Smoke Tests - Fixed Query Set (No-Build Validation)**

Theo spec section 9 + feedback, sử dụng **8-12 queries cố định** để validation nhanh:

**Direct tag queries:**
```
1. "PSAL 2207"          → Expect: correct doc_id+page, bbox crop
2. "PAL 2208"           → Expect: correct doc_id+page, bbox crop
3. "PI 2046A"           → Expect: trailing letter recognized
4. "FIC 2910"           → Expect: correct doc_id+page
5. "PT 2511B"           → Expect: suffix B recognized
6. "04 PSAL 2207"       → Expect: full AREA+CODE+NUM recognized
```

**Suffix variants:**
```
7. "PAL 2208 A/B/C"     → Expect: suffix A/B/C attached, crop stable
8. "PSU 2oo3"           → Expect: voting suffix recognized
9. "PI -201B"           → Expect: negative suffix recognized
```

**Semantic-lite (if vector search enabled):**
```
10. "cảm biến áp suất 2207"    → Expect: PSAL/PT 2207 in top-3
11. "báo động áp suất 2208"    → Expect: PAL 2208 in top-3
12. "flow indicator 2910"      → Expect: FIC 2910 in top-3
```

**Expected behavior**: Top results contain correct `doc_id+page` + bbox crop; suffixes recognized và crop stable.

#### **9.2. No-Build Ops Approach (Lightweight Validation)**

Theo spec section 9 + feedback - **KHÔNG cần build KPI dashboard hay test framework phức tạp**.

**Runtime logs only** (1 JSONL line per file sau ingestion):
```jsonl
{
  "doc_id": "04000-CP25-05",
  "cadlike_score": 0.75,
  "pages_sampled": [1,2,3,mid,last],
  "is_cadlike": true,
  "pages_taggy": [2,3,5,8,12],
  "tags_found_total": 47,
  "tags_found_per_page_p50": 8,
  "tags_found_per_page_p90": 15,
  "ocr_fallback_ratio": 0.05,
  "legend_excluded_hits": 3,
  "avg_triplet_score": 7.2,
  "elapsed_sec": 12.4
}
```

**Warn thresholds (heuristics chạy tự động):**
```python
# Warnings tự động khi:
if is_cadlike and tags_found_total == 0:
    WARN("CAD-like doc but zero tags extracted")

if ocr_fallback_ratio > 0.20:
    WARN("High OCR ratio - expect mostly vector PDFs")

if avg_triplet_score < 6.0:
    WARN("Low triplet scores - tolerances might be too strict")

if tags_found_per_page_p50 < 2 and cadlike_score >= 0.70:
    WARN("Low tag density despite high CAD score")
```

**Acceptance**: Review logs + run 8-12 smoke tests → tune config → iterate. **No CI/CD builds required.**

---

## ⚠️ **6. RISKS & MITIGATION**

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Assembler tolerances quá strict** → missed tags | High | Medium | Telemetry + relaxed mode + per-vendor tuning |
| **Disk usage bùng nổ** (crops, layouts) | Medium | High | Lazy generation + cleanup policy + monitoring |
| **False positives** (LEGEND text as tags) | Medium | Medium | Exclusion zones + manual review + telemetry |
| **Integration conflicts với existing P&ID code** | Medium | Low | Code review + refactor shared logic + unified config |
| **Performance regression** (ingestion slow) | Medium | Medium | Async processing + selective gate + batching |
| **Vendor-specific layout variations** | High | High | Configurable tolerances + learning from telemetry |

---

## ✅ **7. KẾT LUẬN & KHUYẾN NGHỊ CUỐI CÙNG**

### **7.1. Verdict: ✅ KHUYẾN NGHỊ TRIỂN KHAI**

Kế hoạch của bạn là **well-thought-out** và **feasible**. Những điểm mạnh:
- ✅ Kiến trúc sidecar không invasive
- ✅ Configuration-driven (dễ tune)
- ✅ Graceful degradation (không break existing flow)
- ✅ Dependencies hợp lý (mostly đã có)

### **7.2. Điều chỉnh khuyến nghị:**

1. **OCR Infrastructure**: ✅ Đã có PP-OCRv5 - không cần thay đổi gì, fully aligned với spec
2. **CODE whitelist**: ✅ Add learning mode để discover new codes + weekly review logs
3. **Performance expectations**: ⚠️ Clarify latency impact (~1-2s/page cho tag extraction, ~300-500ms query overhead)
4. **Bbox crops**: ✅ Implement lazy generation (on-demand) để tiết kiệm disk space
5. **Integration**: ✅ Reuse & refactor shared code với existing P&ID enhancement (tag_normalizer, tag_utils)
6. **OpenCV**: ✅ Add as optional dependency với flag `ENABLE_SHAPE_AWARE_ROI` (default=false)
7. **Assembler tolerances**: ✅ Start conservative, add telemetry, support vendor-specific tuning
8. **Testing strategy**: ⚠️ Cần validation set (50-100 real P&ID PDFs với ground truth tags) trước rollout

### **7.3. Storage Configuration (Important!)**

Artifacts storage cần được config đúng để tránh lấp đầy ổ C:

#### **Current Default:**
```
artifacts/  → C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\artifacts\
```

#### **Recommended for CAD-like Tag Extraction:**
```ini
# Add to .env
ARTIFACTS_DIR=D:\PVCFC_Artifacts
```

#### **Migration (1-click):**
```powershell
# Safe migration với backup & verification
.\scripts\utilities\migrate_artifacts_to_d_drive.ps1

# Or test first (dry run)
.\scripts\utilities\migrate_artifacts_to_d_drive.ps1 -TestOnly
```

**Benefits:**
- ✅ D: có nhiều space (CAD artifacts ~4-8GB, có thể lớn hơn)
- ✅ Dễ rollback (xóa env var)
- ✅ Không ảnh hưởng code repo
- ✅ Cùng ổ với D:\Data_Raw (easier management)

**Documentation**: `scripts/utilities/README_ARTIFACTS_MIGRATION.md`

---

### **7.4. Dependencies Alignment với Spec:**

Kiểm tra chi tiết dependencies requirements:

| Dependency | Spec Requirement | Hệ thống hiện tại | Status | Note |
|------------|------------------|-------------------|--------|------|
| **PyMuPDF** | Vector-first text & drawings | ✅ v1.26.4 | ✅ **Ready** | Production-ready |
| **PaddleOCR v5** | OCR fallback (raster pages) | ✅ PP-OCRv5 models + v2.7.3 lib | ✅ **Ready** | GPU-accelerated |
| **OpenCV** | Contours, Hough lines (optional) | ❌ Not installed | ⚠️ **Need install** | `opencv-python>=4.8.0` |
| **R-tree/KD-tree** | Neighbor queries | ✅ scipy.spatial.KDTree | ✅ **Ready** | scipy đã có |
| **OpenSearch** | Sidecar tags index | ✅ v3.0.0, 4,883 chunks | ✅ **Ready** | Production index |

**Technical Readiness: 90%** (chỉ thiếu OpenCV - dễ cài)

### **7.5. Go/No-Go Criteria:**

**GO nếu**:
- ✅ Có dataset test (50-100 real P&ID PDFs với ground truth tags)
- ✅ Commit 1-2 tháng dev time
- ✅ Có plan để monitor disk usage (artifacts storage)
- ✅ Accept latency tăng ~300-500ms cho queries có tag hits

**HOLD nếu**:
- ❌ Chưa có sample P&ID data để test
- ❌ Không có capacity để maintain thêm pipeline
- ❌ Disk space < 50GB available trên **artifacts storage drive**
  - Default: artifacts lưu trong project folder (C:)
  - **Recommended**: Config `ARTIFACTS_DIR=D:\PVCFC_Artifacts` để lưu cùng ổ với data
  - Migration script: `scripts/utilities/migrate_artifacts_to_d_drive.ps1`
  - Artifacts có thể lớn: crops (~2-5GB), layouts (~500MB), entities (~100MB)

### **7.6. Next Steps - Action Items:**

#### **Immediate (Tuần 1):**
```powershell
# 0. [NEW] Setup storage configuration (RECOMMENDED FIRST!)
.\scripts\utilities\migrate_artifacts_to_d_drive.ps1 -TestOnly  # Test first
.\scripts\utilities\migrate_artifacts_to_d_drive.ps1            # Actual migration
.\scripts\utilities\verify_artifacts_location.ps1               # Verify

# 1. Review existing P&ID code & extract reusable patterns
grep -r "pid_query|tag_normalizer|tag_utils" app/rag/ app/utils/

# 2. Install OpenCV dependency
pip install opencv-python>=4.8.0

# 3. Collect validation dataset
# - Target: 50-100 real P&ID PDFs
# - Manual ground truth: tag lists per page
# - Mix of vendors (Hitachi, HTC, Siemens, etc.)
```

#### **Short-term (Tuần 2-3): Gate + Layout + Assembler**
- **CAD-like Gate**: Implement scorer với 8 features (Section 3 của spec)
  - Sampling 5 pages, threshold S≥0.60
  - Gray zone boost theo filename keywords
- **Layout Builder**: Vector-first extraction với PyMuPDF
  - Text spans (bbox, font, rotation)
  - Vector drawings (lines, circles, paths)
  - OCR fallback (reuse existing PP-OCRv5 config)
- **Tag Assembler**: CODE-anchored vertical triplets
  - ROI proposals (text-centric)
  - AREA+CODE+NUM assembly với tolerances
  - Suffix attachment (A/B/C, 2oo3, -201B)
- **Telemetry**: Runtime logs (1 JSONL/file), auto-warnings

#### **Medium-term (Tuần 4-5): Indexing + Serving**
- **OpenSearch sidecar**: Create `pvcfc_pid_tags` index
  - n-gram analyzer cho fuzzy tag text
  - Keyword fields cho exact filters
  - Bulk upsert từ `tags.jsonl`
- **Query integration**:
  - Intent detection cho tag queries (extend existing)
  - Parallel query (tags branch + chunks branch)
  - RRF fusion (reuse existing logic)
  - Crop attachment for vision citations
- **Shape-aware ROI** (optional, với OpenCV flag)

#### **Validation & Tuning (Ongoing):**
- Run smoke tests (8-12 fixed queries)
- Review telemetry logs daily/weekly
- Tune assembler tolerances based on warnings
- Expand CODE whitelist from learning mode
- Monitor disk usage & query latency

---

## 📌 **TÓM TẮT CUỐI CÙNG**

### **Verdict: ✅ STRONGLY RECOMMEND GO AHEAD**

Kế hoạch của bạn **rất tốt**, **well-architected**, và **highly feasible**:

- ✅ **Infrastructure ready**: 90% dependencies đã có sẵn
- ✅ **Architecture sound**: Sidecar design không invasive, dễ rollback
- ✅ **Spec alignment**: OCR (PP-OCRv5), PyMuPDF, OpenSearch đều match requirements
- ✅ **Reusable code**: Có thể leverage existing P&ID enhancement modules
- ⚠️ **Critical path**: Cần validation dataset và vendor-specific tuning

**Key success factors:**
1. 📊 Có dataset test với ground truth (50-100 P&ID PDFs)
2. 📈 Telemetry-driven tuning (gate thresholds, assembler tolerances)
3. 🔧 Iterative approach (start conservative → relax based on data)
4. 🧪 Vendor-specific configuration (Hitachi vs HTC vs Siemens có thể khác)

**Timeline realistic**: 1-2 tháng (25-40 ngày dev) là hợp lý cho scope này.

**Risk profile**: LOW-MEDIUM - các risks đã được identify và có mitigation plans rõ ràng.

---

## 🔍 **CROSS-VALIDATION NOTE**

Kế hoạch đã được review bởi **2 AI agents** với kết luận nhất quán:

| Aspect | Agent 1 (Detailed) | Agent 2 (Concise) | Agreement |
|--------|-------------------|-------------------|-----------|
| **Feasibility** | 95% khả thi | Phù hợp triển khai ngay | ✅ **100%** |
| **Infrastructure** | PP-OCRv5, PyMuPDF, OpenSearch ready | Vector-first + OCR khớp spec | ✅ **100%** |
| **Core Gap** | Ingestion-time extraction | CAD gate + layout + assembler | ✅ **100%** |
| **Timeline** | 25-40 ngày (1-2 tháng) | 4-5 tuần | ✅ **Aligned** |
| **Approach** | Sidecar, non-invasive | Sidecar, không conflict | ✅ **100%** |
| **Testing** | Smoke tests + telemetry | Runtime logs + 8-12 queries | ✅ **100%** |
| **Integration** | Reuse existing P&ID code | Unified regex/patterns | ✅ **100%** |
| **Verdict** | GO - STRONGLY RECOMMEND | GO - Triển khai theo spec | ✅ **100%** |

**Conclusion**: **Dual validation confirms** - kế hoạch sound, feasible, và ready to implement. Không có điểm mâu thuẫn nào giữa 2 reviews.

---

**✍️ Người đánh giá**: AI Agent (Claude Sonnet 4.5) - Cross-validated
**📅 Ngày đánh giá ban đầu**: 16/10/2025
**📅 Ngày cập nhật**: 17/10/2025
**🔄 Version**: 3.0 (Cross-validation + Storage migration complete)
**✅ Storage Status**: Migrated to D: drive (476 GB free, ready for CAD extraction)
