# ROOT CAUSE ANALYSIS REPORT
## Lỗi "Page X out of range" trong Hệ thống RAG

**Ngày phân tích:** 2025-10-09
**Người phân tích:** AI Agent (Automated Diagnostic)
**Phiên bản hệ thống:** API_LLM_PVCFC v1.x

---

## 📋 TÓM TẮT ĐIỀU TRA (EXECUTIVE SUMMARY)

### Vấn đề được báo cáo:
- Người dùng nhận được lỗi **"Page 10 out of range. PDF has 8 pages"** khi click vào nút "View Page" trong giao diện Streamlit
- Citations hiển thị số trang không tồn tại trong file PDF thực tế

### Nguyên nhân gốc rễ (Root Cause):
**Dữ liệu trong `doc_id_map.json` không khớp với số trang thực tế của các file PDF vật lý.**

Cụ thể:
- File `doc_id_map.json` lưu số trang **sai/cũ** cho 20/76 documents (26.3%)
- Các file PDF thực tế có **nhiều trang hơn** so với số trang được ghi nhận trong metadata
- Khi Vision Generation tạo citations với page numbers từ các trang thực tế, nhưng doc_id_map chứa giới hạn trang nhỏ hơn → xung đột

### Mức độ nghiêm trọng:
🔴 **CRITICAL** - Ảnh hưởng đến tính chính xác của citations và user experience

---

## 🔍 QUÁ TRÌNH PHÂN TÍCH CHI TIẾT

### 1. Phát hiện ban đầu

Từ conversation history, người dùng báo cáo:
```
"PDF path not available for this citation"
"Page 10 out of range. PDF has 8 pages"
```

Điều này xảy ra khi:
- Citation chứa `doc_id` cho "KT06101_TURBINE_HTC"
- Citation reference đến page 10
- Nhưng `doc_id_map.json` ghi rằng document này chỉ có 8 pages

### 2. Xác thực dữ liệu (Data Validation)

**Script chạy:** `diagnose_pages.py`
**Kết quả:**

```
Total documents: 76
Valid documents: 56 (73.7%)
Page count mismatches: 20 (26.3%)
Missing PDFs: 0
```

### 3. Các documents bị mismatch nghiêm trọng:

| File Name | Doc ID | Expected (map) | Actual (PDF) | Difference |
|-----------|--------|----------------|--------------|------------|
| **K03-K04 O&M.pdf** | ...Manual_K03-K04_O_M... | 494 | **1437** | +943 |
| **MANUAL(COMPRESSOR)l.pdf** | ...Manual_MANUAL_COMPRE... | 496 | **1437** | +941 |
| **Operating Manual KT06101...** | ...Manual_Operating_Manual... | 233 | **281** | +48 |
| **manual.pdf** | ...Manual_manual... | 253 | **286** | +33 |
| **KT06101-technical spare part list** | ...Spare_parts_KT06101... | 1 | **30** | +29 |
| **KT06101_Assembly Clearance Records** | ...Maintenance_KT06101... | 28 | **50** | +22 |

**Top cases:**
- 2 file manual có sai lệch ~940 pages (dự đoán: file bị thay thế/merge nhưng metadata không cập nhật)
- File "KT06101-technical spare part list" ghi 1 page nhưng thực tế có 30 pages (lỗi nghiêm trọng)

### 4. Phân tích luồng xử lý (Process Flow Analysis)

#### A. Quá trình Ingestion (Giai đoạn tạo `doc_id_map.json`):
```python
# Trong quá trình ingestion, page count được tính:
with fitz.open(pdf_path) as doc:
    total_pages = doc.page_count  # Ghi vào doc_id_map
```

**Giả thuyết về nguyên nhân mismatch:**
1. ✅ **File PDF bị thay thế/cập nhật sau khi ingestion** (most likely)
2. ❓ Lỗi trong quá trình đếm trang ban đầu (ít khả năng - PyMuPDF reliable)
3. ❓ File bị corrupt/truncated trong lần ingestion đầu tiên

#### B. Quá trình Generation & Citation:

**Vision Generation Flow:**
```
1. Retriever → trả về docs với metadata từ vector DB
2. _build_vision_pages() → tính page_start, page_end từ metadata
3. Vision LLM → đọc TOÀN BỘ TRANG THỰC TẾ của PDF → tạo citations với page numbers
4. Citation extraction → ghi page number từ vision response
5. UI rendering → lấy pdf_path từ doc_id_map → gọi render_page_to_image(page_num)
6. ❌ render_page_to_image() validate:
   - if page_num > doc.page_count → FAIL "Page X out of range"
```

**Vấn đề:** Vision LLM thấy và cite page 10 (thật), nhưng `doc_id_map.json` nói doc chỉ có 8 pages.

---

## 🎯 KẾT LUẬN VÀ KHUYẾN NGHỊ

### Nguyên nhân gốc rễ (Root Cause):

**Mismatch giữa dữ liệu metadata (`doc_id_map.json`) và file PDF vật lý.**

Không phải lỗi của:
- ❌ LLM generation logic
- ❌ Citation extraction algorithm
- ❌ Vision processing
- ❌ PDF rendering code

Mà là:
- ✅ **Data inconsistency** - Metadata cũ/sai không đồng bộ với PDF files hiện tại

### Khuyến nghị sửa lỗi:

#### 🔥 **URGENT (Immediate Action Required):**

**Option 1: Re-index toàn bộ documents (Recommended)**
```bash
# Chạy lại ingestion pipeline để cập nhật doc_id_map.json
python -m pipelines.ingestion.run_ingestion --reindex-all
```

**Option 2: Hotfix - Cập nhật doc_id_map.json (Quick fix)**
```python
# Script để sửa chữa doc_id_map.json
import json
import fitz
from pathlib import Path

doc_id_map_path = Path("artifacts/ingestion/doc_id_map.json")
with open(doc_id_map_path, "r", encoding="utf-8") as f:
    doc_id_map = json.load(f)

# Update page counts
for doc_id, doc_info in doc_id_map.items():
    pdf_path = doc_info.get("pdf_path")
    if pdf_path and Path(pdf_path).exists():
        try:
            with fitz.open(pdf_path) as doc:
                actual_pages = doc.page_count
                doc_info["total_pages"] = actual_pages
                print(f"Updated {doc_id}: {actual_pages} pages")
        except Exception as e:
            print(f"Error updating {doc_id}: {e}")

# Save updated map
with open(doc_id_map_path, "w", encoding="utf-8") as f:
    json.dump(doc_id_map, f, indent=2, ensure_ascii=False)
```

#### ⚙️ **MEDIUM PRIORITY (System Improvements):**

1. **Thêm validation trong pipeline ingestion:**
   ```python
   # Verify page count after ingestion
   assert stored_page_count == actual_pdf_page_count
   ```

2. **Thêm health check endpoint:**
   ```python
   @app.get("/api/health/doc-metadata")
   def check_doc_metadata_consistency():
       """Validate doc_id_map vs actual PDFs"""
       # Return mismatches
   ```

3. **Runtime validation trong generator:**
   ```python
   # Before rendering page, check actual page count
   actual_page_count = get_pdf_page_count(pdf_path)
   if page_num > actual_page_count:
       logger.warning(f"Page {page_num} exceeds actual count {actual_page_count}")
       # Clamp or skip
   ```

#### 🛡️ **LONG TERM (Preventive Measures):**

1. **Implement file versioning:**
   - Track PDF file hashes/checksums
   - Detect when PDFs are updated
   - Auto-trigger re-indexing

2. **Add monitoring:**
   - Alert when page count mismatch detected
   - Log validation errors centrally

3. **Improve ingestion pipeline:**
   - Validate metadata after write
   - Store file modification timestamps
   - Compare with current file state

---

## 📊 THỐNG KÊ PHÂN TÍCH

### Tổng quan:
- **Total documents analyzed:** 76
- **Valid documents:** 56 (73.7%)
- **Documents with page mismatch:** 20 (26.3%)
- **Missing PDF files:** 0 (0%)

### Phân loại mismatch:
- **Minor (<5 pages difference):** 14 documents (70%)
- **Moderate (5-50 pages):** 4 documents (20%)
- **Severe (>50 pages):** 2 documents (10%)

### Tài liệu tham khảo:
- `artifacts/page_mismatch_report.json` - Full detailed report
- `diagnose_pages.py` - Diagnostic script

---

## ✅ HÀNH ĐỘNG ĐƯỢC THỰC HIỆN

1. ✅ Phân tích toàn bộ 76 documents trong doc_id_map.json
2. ✅ So sánh page counts với file PDF thực tế
3. ✅ Xác định 20 documents có mismatch
4. ✅ Lưu báo cáo chi tiết vào `artifacts/page_mismatch_report.json`
5. ✅ Tạo diagnostic script `diagnose_pages.py` để tái sử dụng
6. ✅ Viết báo cáo phân tích nguyên nhân gốc rễ

---

## 🚀 NEXT STEPS (Bước tiếp theo)

**Cho người dùng:**

1. **Chọn 1 trong 2 options:**
   - Option A: Chạy lại full ingestion (recommended, mất thời gian hơn)
   - Option B: Chạy script hotfix để cập nhật doc_id_map.json (nhanh)

2. **Restart backend service** sau khi cập nhật metadata

3. **Test lại** với query đã gặp lỗi trước đó

4. **Xác nhận** "View Page" button hoạt động chính xác

**Tôi có thể hỗ trợ:**
- Viết script hotfix hoàn chỉnh
- Hướng dẫn chạy re-ingestion
- Thêm validation logic vào code
- Setup monitoring/alerting

---

## 📝 KẾT LUẬN

Lỗi **"Page X out of range"** xảy ra do **DATA INCONSISTENCY** giữa metadata file (`doc_id_map.json`) và PDF files thực tế trên hệ thống.

**Không phải lỗi code hay logic xử lý**, mà là vấn đề về **data synchronization**.

Giải pháp: **Cập nhật doc_id_map.json** để phản ánh đúng số trang thực tế của các file PDF.

---

**Report generated by:** Automated Diagnostic System
**Timestamp:** 2025-10-09T09:43:17Z
**Status:** ✅ Root cause identified - Awaiting fix implementation
